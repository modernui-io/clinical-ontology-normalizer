"""
FastAPI Authentication Middleware for Knowledge Graph Endpoints.

This middleware integrates the KG API Key Service with FastAPI to provide:
- API key authentication for all KG endpoints
- Scope-based authorization
- Rate limiting enforcement
- Request context propagation
- Audit logging integration
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class AuthErrorCode(str, Enum):
    """Authentication error codes."""
    MISSING_API_KEY = "missing_api_key"
    INVALID_API_KEY = "invalid_api_key"
    EXPIRED_API_KEY = "expired_api_key"
    SUSPENDED_API_KEY = "suspended_api_key"
    REVOKED_API_KEY = "revoked_api_key"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    IP_NOT_ALLOWED = "ip_not_allowed"
    INTERNAL_ERROR = "internal_error"


@dataclass
class AuthResult:
    """Result of authentication attempt."""
    success: bool
    key_id: str | None = None
    key_name: str | None = None
    scopes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_code: AuthErrorCode | None = None
    error_message: str | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: datetime | None = None


@dataclass
class EndpointAuthConfig:
    """Configuration for endpoint authentication."""
    required_scopes: list[str] = field(default_factory=list)
    require_any_scope: bool = False  # If True, any scope is sufficient
    rate_limit_override: int | None = None  # Override default rate limit
    allow_unauthenticated: bool = False  # Allow without API key
    audit_access: bool = True  # Log access to audit trail


@dataclass
class AuthMiddlewareConfig:
    """Configuration for the authentication middleware."""
    enabled: bool = True
    api_key_header: str = "X-API-Key"
    api_key_query_param: str = "api_key"
    api_key_prefix: str = "kg_"

    # Rate limiting
    default_rate_limit: int = 1000  # requests per hour
    rate_limit_window_seconds: int = 3600

    # IP restrictions
    ip_whitelist: list[str] = field(default_factory=list)
    ip_blacklist: list[str] = field(default_factory=list)

    # Endpoint patterns to skip
    skip_patterns: list[str] = field(default_factory=lambda: [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    ])

    # Audit integration
    audit_enabled: bool = True

    # Error response format
    include_debug_info: bool = False


class ScopeRegistry:
    """Registry of scopes required for different endpoints."""

    def __init__(self):
        self._endpoint_configs: dict[str, EndpointAuthConfig] = {}
        self._pattern_configs: list[tuple[str, EndpointAuthConfig]] = []
        self._default_config = EndpointAuthConfig()

        # Initialize with default KG endpoint scopes
        self._init_default_scopes()

    def _init_default_scopes(self):
        """Initialize default scope requirements for KG endpoints."""
        # Health endpoints - no auth required
        self.register_pattern("/kg/health", EndpointAuthConfig(
            allow_unauthenticated=True,
            audit_access=False
        ))

        # Read operations
        self.register_pattern("/kg/concepts", EndpointAuthConfig(
            required_scopes=["read:concepts"]
        ))
        self.register_pattern("/kg/relationships", EndpointAuthConfig(
            required_scopes=["read:relationships"]
        ))
        self.register_pattern("/kg/patients", EndpointAuthConfig(
            required_scopes=["read:patients"]
        ))

        # Reasoning operations (more expensive)
        self.register_pattern("/kg/reasoning", EndpointAuthConfig(
            required_scopes=["read:reasoning"],
            rate_limit_override=100
        ))
        self.register_pattern("/kg/orchestration/reasoning", EndpointAuthConfig(
            required_scopes=["read:reasoning"],
            rate_limit_override=100
        ))

        # Write operations
        self.register_pattern("/kg/concepts", EndpointAuthConfig(
            required_scopes=["write:concepts"]
        ), methods=["POST", "PUT", "DELETE"])
        self.register_pattern("/kg/relationships", EndpointAuthConfig(
            required_scopes=["write:relationships"]
        ), methods=["POST", "PUT", "DELETE"])

        # Admin operations
        self.register_pattern("/kg/admin", EndpointAuthConfig(
            required_scopes=["admin:system"]
        ))
        self.register_pattern("/kg/keys", EndpointAuthConfig(
            required_scopes=["admin:keys"]
        ))

        # Batch operations
        self.register_pattern("/batch", EndpointAuthConfig(
            required_scopes=["batch:read"],
            rate_limit_override=50
        ))

        # Export operations
        self.register_pattern("/kg/export", EndpointAuthConfig(
            required_scopes=["export:data"],
            rate_limit_override=20
        ))
        self.register_pattern("/fhir", EndpointAuthConfig(
            required_scopes=["export:fhir"],
            rate_limit_override=50
        ))

        # Benchmark operations (resource intensive)
        self.register_pattern("/kg/benchmark", EndpointAuthConfig(
            required_scopes=["admin:system"],
            rate_limit_override=10
        ))

        # MDT sessions
        self.register_pattern("/kg/mdt", EndpointAuthConfig(
            required_scopes=["read:reasoning", "read:patients"],
            require_any_scope=False,
            rate_limit_override=30
        ))

    def register_endpoint(
        self,
        path: str,
        config: EndpointAuthConfig,
        methods: list[str | None] = None
    ):
        """Register exact endpoint path with auth config."""
        if methods:
            for method in methods:
                key = f"{method}:{path}"
                self._endpoint_configs[key] = config
        else:
            self._endpoint_configs[path] = config

    def register_pattern(
        self,
        pattern: str,
        config: EndpointAuthConfig,
        methods: list[str | None] = None
    ):
        """Register URL pattern with auth config."""
        if methods:
            for method in methods:
                self._pattern_configs.append((f"{method}:{pattern}", config))
        else:
            self._pattern_configs.append((pattern, config))

    def get_config(self, path: str, method: str = "GET") -> EndpointAuthConfig:
        """Get auth config for an endpoint."""
        # Check exact match first
        method_path = f"{method}:{path}"
        if method_path in self._endpoint_configs:
            return self._endpoint_configs[method_path]
        if path in self._endpoint_configs:
            return self._endpoint_configs[path]

        # Check patterns
        for pattern, config in self._pattern_configs:
            if ":" in pattern:
                # Pattern includes method
                pattern_method, pattern_path = pattern.split(":", 1)
                if method == pattern_method and path.startswith(pattern_path):
                    return config
            elif path.startswith(pattern):
                return config

        return self._default_config

    def set_default_config(self, config: EndpointAuthConfig):
        """Set default config for unmatched endpoints."""
        self._default_config = config


class RateLimitTracker:
    """Track rate limits per API key."""

    def __init__(self, default_limit: int = 1000, window_seconds: int = 3600):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._counters: dict[str, dict[str, Any]] = {}

    def check_and_increment(
        self,
        key_id: str,
        limit_override: int | None = None
    ) -> tuple[bool, int, datetime]:
        """
        Check if request is allowed and increment counter.
        Returns (allowed, remaining, reset_time).
        """
        limit = limit_override or self.default_limit
        now = time.time()

        if key_id not in self._counters:
            self._counters[key_id] = {
                "count": 0,
                "window_start": now
            }

        counter = self._counters[key_id]

        # Check if window has expired
        if now - counter["window_start"] >= self.window_seconds:
            counter["count"] = 0
            counter["window_start"] = now

        # Check limit
        if counter["count"] >= limit:
            reset_time = datetime.fromtimestamp(
                counter["window_start"] + self.window_seconds
            )
            return False, 0, reset_time

        # Increment and return
        counter["count"] += 1
        remaining = limit - counter["count"]
        reset_time = datetime.fromtimestamp(
            counter["window_start"] + self.window_seconds
        )

        return True, remaining, reset_time

    def get_usage(self, key_id: str) -> dict[str, Any]:
        """Get current usage for a key."""
        if key_id not in self._counters:
            return {"count": 0, "limit": self.default_limit}

        counter = self._counters[key_id]
        return {
            "count": counter["count"],
            "limit": self.default_limit,
            "window_start": datetime.fromtimestamp(counter["window_start"]),
            "remaining": max(0, self.default_limit - counter["count"])
        }

    def reset(self, key_id: str):
        """Reset counter for a key."""
        if key_id in self._counters:
            del self._counters[key_id]

    def cleanup_expired(self):
        """Remove expired counters."""
        now = time.time()
        expired = [
            key_id for key_id, counter in self._counters.items()
            if now - counter["window_start"] >= self.window_seconds * 2
        ]
        for key_id in expired:
            del self._counters[key_id]


class MockAPIKeyService:
    """
    Mock API key service for when the real service isn't available.
    In production, this would be replaced with the actual KGAPIKeyService.
    """

    def __init__(self):
        self._keys: dict[str, dict[str, Any]] = {}
        self._key_hashes: dict[str, str] = {}  # hash -> key_id

    def register_key(
        self,
        key_id: str,
        raw_key: str,
        scopes: list[str],
        name: str = "test",
        metadata: dict[str, Any | None] = None
    ):
        """Register a key for testing."""
        import hashlib
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        self._keys[key_id] = {
            "id": key_id,
            "name": name,
            "scopes": scopes,
            "status": "active",
            "metadata": metadata or {},
            "hash": key_hash
        }
        self._key_hashes[key_hash] = key_id

    def authenticate(self, raw_key: str) -> AuthResult:
        """Authenticate an API key."""
        import hashlib
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        if key_hash not in self._key_hashes:
            return AuthResult(
                success=False,
                error_code=AuthErrorCode.INVALID_API_KEY,
                error_message="Invalid API key"
            )

        key_id = self._key_hashes[key_hash]
        key_data = self._keys[key_id]

        if key_data["status"] == "expired":
            return AuthResult(
                success=False,
                error_code=AuthErrorCode.EXPIRED_API_KEY,
                error_message="API key has expired"
            )

        if key_data["status"] == "suspended":
            return AuthResult(
                success=False,
                error_code=AuthErrorCode.SUSPENDED_API_KEY,
                error_message="API key is suspended"
            )

        if key_data["status"] == "revoked":
            return AuthResult(
                success=False,
                error_code=AuthErrorCode.REVOKED_API_KEY,
                error_message="API key has been revoked"
            )

        return AuthResult(
            success=True,
            key_id=key_id,
            key_name=key_data["name"],
            scopes=key_data["scopes"],
            metadata=key_data["metadata"]
        )

    def has_scope(self, scopes: list[str], required_scope: str) -> bool:
        """Check if scopes include the required scope."""
        if "*" in scopes or "admin:*" in scopes:
            return True

        if required_scope in scopes:
            return True

        # Check wildcards
        scope_parts = required_scope.split(":")
        if len(scope_parts) == 2:
            wildcard = f"{scope_parts[0]}:*"
            if wildcard in scopes:
                return True

        return False


class KGAuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for KG authentication."""

    def __init__(
        self,
        app,
        config: AuthMiddlewareConfig | None = None,
        api_key_service: Any | None = None,
        scope_registry: ScopeRegistry | None = None,
        rate_limiter: RateLimitTracker | None = None
    ):
        super().__init__(app)
        self.config = config or AuthMiddlewareConfig()
        self.api_key_service = api_key_service or MockAPIKeyService()
        self.scope_registry = scope_registry or ScopeRegistry()
        self.rate_limiter = rate_limiter or RateLimitTracker(
            default_limit=self.config.default_rate_limit,
            window_seconds=self.config.rate_limit_window_seconds
        )

        # Audit logging callback
        self._audit_callback: Callable | None = None

    def set_audit_callback(self, callback: Callable):
        """Set callback for audit logging."""
        self._audit_callback = callback

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request through authentication middleware."""
        if not self.config.enabled:
            return await call_next(request)

        path = request.url.path
        method = request.method

        # Check skip patterns
        for pattern in self.config.skip_patterns:
            if path.startswith(pattern):
                return await call_next(request)

        # Get endpoint auth config
        endpoint_config = self.scope_registry.get_config(path, method)

        # Check if auth is required
        if endpoint_config.allow_unauthenticated:
            return await call_next(request)

        # Extract API key
        api_key = self._extract_api_key(request)

        if not api_key:
            return self._error_response(
                AuthErrorCode.MISSING_API_KEY,
                "API key required. Provide via X-API-Key header or api_key query param.",
                status_code=401
            )

        # Validate key prefix
        if not api_key.startswith(self.config.api_key_prefix):
            return self._error_response(
                AuthErrorCode.INVALID_API_KEY,
                f"Invalid API key format. Key must start with '{self.config.api_key_prefix}'",
                status_code=401
            )

        # Check IP restrictions
        client_ip = self._get_client_ip(request)
        if not self._check_ip_allowed(client_ip):
            return self._error_response(
                AuthErrorCode.IP_NOT_ALLOWED,
                "Access denied from this IP address",
                status_code=403
            )

        # Authenticate key
        auth_result = self.api_key_service.authenticate(api_key)

        if not auth_result.success:
            status_code = 401 if auth_result.error_code in [
                AuthErrorCode.INVALID_API_KEY,
                AuthErrorCode.EXPIRED_API_KEY
            ] else 403

            return self._error_response(
                auth_result.error_code,
                auth_result.error_message,
                status_code=status_code
            )

        # Check required scopes
        if endpoint_config.required_scopes:
            if endpoint_config.require_any_scope:
                # Any one scope is sufficient
                has_scope = any(
                    self.api_key_service.has_scope(auth_result.scopes, scope)
                    for scope in endpoint_config.required_scopes
                )
            else:
                # All scopes required
                has_scope = all(
                    self.api_key_service.has_scope(auth_result.scopes, scope)
                    for scope in endpoint_config.required_scopes
                )

            if not has_scope:
                return self._error_response(
                    AuthErrorCode.INSUFFICIENT_SCOPE,
                    f"Insufficient scope. Required: {endpoint_config.required_scopes}",
                    status_code=403
                )

        # Check rate limit
        rate_limit = endpoint_config.rate_limit_override or self.config.default_rate_limit
        allowed, remaining, reset_time = self.rate_limiter.check_and_increment(
            auth_result.key_id,
            rate_limit
        )

        if not allowed:
            return self._error_response(
                AuthErrorCode.RATE_LIMIT_EXCEEDED,
                f"Rate limit exceeded. Resets at {reset_time.isoformat()}",
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_time.isoformat(),
                    "Retry-After": str(int((reset_time - datetime.now()).total_seconds()))
                }
            )

        # Add auth info to request state
        request.state.auth = auth_result
        request.state.key_id = auth_result.key_id
        request.state.scopes = auth_result.scopes

        # Log to audit if enabled
        if self.config.audit_enabled and endpoint_config.audit_access:
            self._log_audit(request, auth_result, endpoint_config)

        # Call the actual endpoint
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = reset_time.isoformat()

        # Log response to audit if enabled
        if self.config.audit_enabled and endpoint_config.audit_access:
            self._log_audit_response(
                request, auth_result, response.status_code, duration_ms
            )

        return response

    def _extract_api_key(self, request: Request) -> str | None:
        """Extract API key from request."""
        # Try header first
        api_key = request.headers.get(self.config.api_key_header)
        if api_key:
            return api_key

        # Try query parameter
        api_key = request.query_params.get(self.config.api_key_query_param)
        if api_key:
            return api_key

        return None

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        # Check forwarded headers first
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client host
        if request.client:
            return request.client.host

        return "unknown"

    def _check_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed."""
        # Check blacklist first
        if self.config.ip_blacklist and ip in self.config.ip_blacklist:
            return False

        # Check whitelist if configured
        if self.config.ip_whitelist:
            return ip in self.config.ip_whitelist

        return True

    def _error_response(
        self,
        error_code: AuthErrorCode,
        message: str,
        status_code: int = 401,
        headers: dict[str, str | None] = None
    ) -> JSONResponse:
        """Create error response."""
        content = {
            "error": {
                "code": error_code.value,
                "message": message
            }
        }

        if self.config.include_debug_info:
            content["error"]["status_code"] = status_code

        response = JSONResponse(content=content, status_code=status_code)

        if headers:
            for key, value in headers.items():
                response.headers[key] = value

        # Add WWW-Authenticate header for 401 responses
        if status_code == 401:
            response.headers["WWW-Authenticate"] = "ApiKey"

        return response

    def _log_audit(
        self,
        request: Request,
        auth_result: AuthResult,
        config: EndpointAuthConfig
    ):
        """Log request to audit trail."""
        if self._audit_callback:
            self._audit_callback(
                event_type="api_access",
                key_id=auth_result.key_id,
                key_name=auth_result.key_name,
                path=request.url.path,
                method=request.method,
                client_ip=self._get_client_ip(request),
                scopes=auth_result.scopes,
                required_scopes=config.required_scopes
            )

    def _log_audit_response(
        self,
        request: Request,
        auth_result: AuthResult,
        status_code: int,
        duration_ms: float
    ):
        """Log response to audit trail."""
        if self._audit_callback:
            self._audit_callback(
                event_type="api_response",
                key_id=auth_result.key_id,
                path=request.url.path,
                method=request.method,
                status_code=status_code,
                duration_ms=duration_ms
            )


# Dependency injection helpers for FastAPI

def get_current_auth(request: Request) -> AuthResult:
    """FastAPI dependency to get current auth context."""
    if not hasattr(request.state, "auth"):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    return request.state.auth


def require_scope(scope: str):
    """FastAPI dependency factory to require a specific scope."""
    def dependency(request: Request) -> AuthResult:
        auth = get_current_auth(request)

        # Check scope
        has_scope = (
            "*" in auth.scopes or
            scope in auth.scopes or
            f"{scope.split(':')[0]}:*" in auth.scopes if ":" in scope else False
        )

        if not has_scope:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope. Required: {scope}"
            )

        return auth

    return dependency


def require_any_scope(*scopes: str):
    """FastAPI dependency factory to require any of the specified scopes."""
    def dependency(request: Request) -> AuthResult:
        auth = get_current_auth(request)

        for scope in scopes:
            has_scope = (
                "*" in auth.scopes or
                scope in auth.scopes or
                (f"{scope.split(':')[0]}:*" in auth.scopes if ":" in scope else False)
            )
            if has_scope:
                return auth

        raise HTTPException(
            status_code=403,
            detail=f"Insufficient scope. Required one of: {list(scopes)}"
        )

    return dependency


def require_all_scopes(*scopes: str):
    """FastAPI dependency factory to require all specified scopes."""
    def dependency(request: Request) -> AuthResult:
        auth = get_current_auth(request)

        for scope in scopes:
            has_scope = (
                "*" in auth.scopes or
                scope in auth.scopes or
                (f"{scope.split(':')[0]}:*" in auth.scopes if ":" in scope else False)
            )
            if not has_scope:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient scope. Required: {list(scopes)}"
                )

        return auth

    return dependency


# Factory function to create configured middleware

def create_kg_auth_middleware(
    app,
    enabled: bool = True,
    api_key_service: Any | None = None,
    audit_callback: Callable | None = None,
    ip_whitelist: list[str | None] = None,
    ip_blacklist: list[str | None] = None,
    rate_limit: int = 1000,
    include_debug: bool = False
) -> KGAuthMiddleware:
    """Factory function to create configured auth middleware."""
    config = AuthMiddlewareConfig(
        enabled=enabled,
        ip_whitelist=ip_whitelist or [],
        ip_blacklist=ip_blacklist or [],
        default_rate_limit=rate_limit,
        include_debug_info=include_debug
    )

    middleware = KGAuthMiddleware(
        app,
        config=config,
        api_key_service=api_key_service
    )

    if audit_callback:
        middleware.set_audit_callback(audit_callback)

    return middleware
