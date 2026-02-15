"""HIPAA-compliant audit middleware for automatic request logging.

This middleware automatically logs all API requests with:
- User identification (from auth headers)
- Request details (method, path, IP)
- Response status
- PHI access detection
- Timing information

Usage:
    from app.api.middleware.audit_middleware import AuditMiddleware

    app.add_middleware(AuditMiddleware)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.database import async_session_maker
from app.services.audit_service import AuditService, get_audit_service

logger = logging.getLogger(__name__)

# Context variable for request ID (shared with error handler middleware)
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get the current request ID from context.

    Returns:
        Current request ID or None if not set
    """
    return request_id_ctx.get()


# Paths that should not be logged (health checks, static files, etc.)
EXCLUDED_PATHS = {
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}

# Paths with prefixes that should not be logged
EXCLUDED_PATH_PREFIXES = (
    "/static/",
    "/assets/",
)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic HIPAA-compliant audit logging.

    Automatically logs all API requests with:
    - Request metadata (method, path, IP, user agent)
    - User identification (extracted from auth headers)
    - Response status and timing
    - PHI access detection based on path and content
    - Request ID for correlation

    The middleware detects PHI access by analyzing:
    - API path patterns (e.g., /patients, /documents)
    - Response status codes (successful access logged)
    - Resource types being accessed

    Configuration:
    - EXCLUDED_PATHS: Paths to skip logging
    - EXCLUDED_PATH_PREFIXES: Path prefixes to skip

    Example:
        # In main.py
        from app.api.middleware.audit_middleware import AuditMiddleware

        app = FastAPI()
        app.add_middleware(AuditMiddleware)
    """

    def __init__(self, app: Any) -> None:
        """Initialize the audit middleware.

        Args:
            app: The FastAPI/Starlette application
        """
        super().__init__(app)
        self._audit_service: AuditService | None = None

    @property
    def audit_service(self) -> AuditService:
        """Get or create the audit service (lazy initialization).

        Returns:
            The AuditService singleton instance
        """
        if self._audit_service is None:
            self._audit_service = get_audit_service()
        return self._audit_service

    def _should_log(self, path: str) -> bool:
        """Determine if a request path should be logged.

        Args:
            path: The request path

        Returns:
            True if the path should be logged
        """
        # Skip exact path matches
        if path in EXCLUDED_PATHS:
            return False

        # Skip paths with excluded prefixes
        if path.startswith(EXCLUDED_PATH_PREFIXES):
            return False

        return True

    def _extract_user_id(self, request: Request) -> str | None:
        """Extract user ID from request headers or auth state.

        Supports multiple authentication patterns:
        - Authenticated user from auth middleware (request.state.user)
        - Bearer token (extracts from X-User-Id header)
        - API key header
        - Basic auth username

        Args:
            request: The incoming request

        Returns:
            User ID if found, None otherwise
        """
        # Check for authenticated user set by auth middleware
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return user.id

        # Check for explicit user ID header
        user_id = request.headers.get("X-User-Id")
        if user_id:
            return user_id

        # Check for API key as user identifier
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Use a hash/prefix of API key as user ID
            return f"api:{api_key[:8]}..."

        # Check for basic auth
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                import base64
                credentials = base64.b64decode(auth_header[6:]).decode()
                username = credentials.split(":")[0]
                return username
            except Exception:
                pass

        # Check for Bearer token subject (would need JWT decoding)
        if auth_header.startswith("Bearer "):
            # For now, just indicate bearer auth was used
            return "bearer_auth"

        return None

    def _extract_actor_role(self, request: Request) -> str | None:
        """Extract actor role from authenticated user context.

        CISO-8: Captures the actor's role for RBAC audit correlation.
        The role is set by the auth middleware on request.state.user.

        Args:
            request: The incoming request

        Returns:
            Comma-separated role string, or None if not authenticated.
        """
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "roles") and user.roles:
            return ",".join(user.roles)
        return None

    # P1-029: Route prefix -> purpose-of-use mapping
    _PURPOSE_ROUTE_MAP: list[tuple[str, str]] = [
        ("/api/v1/clinical", "treatment"),
        ("/api/v1/billing", "payment"),
        ("/api/v1/admin", "operations"),
        ("/api/v1/analytics", "quality_assurance"),
    ]

    _VALID_PURPOSES = frozenset({
        "treatment",
        "payment",
        "operations",
        "research",
        "public_health",
        "quality_assurance",
    })

    def _determine_purpose_of_use(self, request: Request) -> str | None:
        """Determine purpose-of-use for audit events (P1-029).

        Priority:
        1. X-Purpose-Of-Use header (explicit override)
        2. Auto-detection from API route prefix
        3. None if no match

        Args:
            request: The incoming request

        Returns:
            Purpose-of-use string or None
        """
        # Check for explicit header override
        header_val = request.headers.get("X-Purpose-Of-Use")
        if header_val:
            normalized = header_val.strip().lower().replace("-", "_")
            if normalized in self._VALID_PURPOSES:
                return normalized

        # Auto-detect from route prefix
        path = request.url.path.lower()
        for prefix, purpose in self._PURPOSE_ROUTE_MAP:
            if path.startswith(prefix):
                return purpose

        return None

    def _extract_ip_address(self, request: Request) -> str:
        """Extract client IP address from request.

        Handles proxy headers for accurate IP detection:
        - X-Forwarded-For (most common)
        - X-Real-IP
        - Direct client IP

        Args:
            request: The incoming request

        Returns:
            Client IP address
        """
        # Check X-Forwarded-For header (from proxies/load balancers)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP in the list is the original client
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _determine_resource_type(self, path: str, method: str) -> str:
        """Determine the resource type from the request path.

        Maps API paths to resource types for audit logging.

        Args:
            path: The request path
            method: The HTTP method

        Returns:
            Resource type string
        """
        path_lower = path.lower()

        # Map path patterns to resource types
        if "/documents" in path_lower:
            return "document"
        elif "/patients" in path_lower:
            return "patient"
        elif "/facts" in path_lower or "/clinical_facts" in path_lower:
            return "clinical_fact"
        elif "/mentions" in path_lower:
            return "mention"
        elif "/fhir" in path_lower:
            return "fhir_resource"
        elif "/kg" in path_lower or "/knowledge_graph" in path_lower:
            return "knowledge_graph"
        elif "/vocabulary" in path_lower or "/coding" in path_lower:
            return "vocabulary"
        elif "/search" in path_lower:
            return "search"
        elif "/export" in path_lower:
            return "export"
        elif "/audit" in path_lower:
            return "audit_log"
        elif "/jobs" in path_lower:
            return "job"
        elif "/dashboard" in path_lower:
            return "dashboard"
        else:
            return "system"

    def _determine_action(self, method: str, path: str) -> str:
        """Determine the action type from HTTP method and path.

        Args:
            method: The HTTP method
            path: The request path

        Returns:
            Action type string
        """
        method = method.upper()

        # Special handling for specific paths
        if "/search" in path.lower():
            return "search"
        if "/export" in path.lower():
            return "export"

        # Map HTTP methods to actions
        method_map = {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }

        return method_map.get(method, "access")

    def _extract_resource_id(self, path: str) -> str | None:
        """Extract resource ID from path if present.

        Looks for UUID-like patterns in the path.

        Args:
            path: The request path

        Returns:
            Resource ID if found, None otherwise
        """
        import re

        # UUID pattern
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        match = re.search(uuid_pattern, path, re.IGNORECASE)
        if match:
            return match.group(0)

        # Check for numeric IDs at the end of path segments
        parts = path.strip("/").split("/")
        for part in reversed(parts):
            if part.isdigit():
                return part

        return None

    def _extract_patient_id(self, path: str, query_params: dict) -> str | None:
        """Extract patient ID from request if present.

        Checks both path parameters and query parameters.

        Args:
            path: The request path
            query_params: Query parameters dict

        Returns:
            Patient ID if found, None otherwise
        """
        # Check query parameters
        patient_id = query_params.get("patient_id")
        if patient_id:
            return patient_id[0] if isinstance(patient_id, list) else patient_id

        # Check for patient ID in path
        path_lower = path.lower()
        if "/patients/" in path_lower:
            parts = path.split("/patients/")
            if len(parts) > 1:
                patient_part = parts[1].split("/")[0]
                if patient_part:
                    return patient_part

        return None

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and log audit trail.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            The response from the handler
        """
        # Generate and set request ID
        request_id = str(uuid4())
        request_id_ctx.set(request_id)

        # Add request ID to request state for downstream access
        request.state.request_id = request_id

        # Check if we should log this path
        path = request.url.path
        if not self._should_log(path):
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            return response

        # Extract request metadata
        start_time = time.perf_counter()
        method = request.method
        user_id = self._extract_user_id(request)
        actor_role = self._extract_actor_role(request)
        ip_address = self._extract_ip_address(request)
        user_agent = request.headers.get("User-Agent", "")
        query_params = dict(request.query_params)

        # Determine resource information
        resource_type = self._determine_resource_type(path, method)
        action = self._determine_action(method, path)
        resource_id = self._extract_resource_id(path)
        patient_id = self._extract_patient_id(path, query_params)

        # P1-029: Determine purpose-of-use
        purpose_of_use = self._determine_purpose_of_use(request)

        # Process the request
        response: Response | None = None
        error_message: str | None = None
        success = True

        try:
            response = await call_next(request)
        except Exception as e:
            success = False
            error_message = str(e)
            logger.exception(f"Request failed: {e}")
            raise
        finally:
            # Calculate request duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Get response status
            response_status = response.status_code if response else 500

            # Determine if request was successful
            if response_status >= 400:
                success = False
                if not error_message:
                    error_message = f"HTTP {response_status}"

            # Determine PHI access
            phi_accessed = self.audit_service.auto_detect_phi(
                resource_type=resource_type,
                request_path=path,
            )

            # Log the audit entry asynchronously
            # CISO-8: Re-extract user_id and actor_role after request processing,
            # since auth middleware may have populated request.state.user
            # during call_next(request).
            post_user_id = self._extract_user_id(request)
            post_actor_role = self._extract_actor_role(request)

            try:
                async with async_session_maker() as db:
                    await self.audit_service.log_event(
                        db=db,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        user_id=post_user_id or user_id,
                        actor_role=post_actor_role or actor_role,
                        ip_address=ip_address,
                        user_agent=user_agent[:500] if user_agent else None,
                        request_id=request_id,
                        request_method=method,
                        request_path=path,
                        response_status=response_status,
                        details={
                            "duration_ms": round(duration_ms, 2),
                            "query_params": query_params if query_params else None,
                        },
                        phi_accessed=phi_accessed,
                        patient_id=patient_id,
                        success=success,
                        error_message=error_message,
                        purpose_of_use=purpose_of_use,
                    )
                    await db.commit()
            except Exception as log_error:
                # Don't fail the request if audit logging fails
                logger.error(f"Failed to log audit entry: {log_error}")

        # Add request ID to response headers
        if response:
            response.headers["X-Request-Id"] = request_id

        return response


class AsyncAuditMiddleware:
    """Alternative ASGI middleware implementation for audit logging.

    This implementation uses raw ASGI for better performance and
    compatibility with async contexts. Use this if BaseHTTPMiddleware
    causes issues with streaming responses.

    Usage:
        app.add_middleware(AsyncAuditMiddleware)
    """

    def __init__(self, app: Any) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
        """
        self.app = app
        self._audit_service: AuditService | None = None

    @property
    def audit_service(self) -> AuditService:
        """Get or create the audit service."""
        if self._audit_service is None:
            self._audit_service = get_audit_service()
        return self._audit_service

    async def __call__(
        self, scope: dict, receive: Callable, send: Callable
    ) -> None:
        """Process ASGI request.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate request ID
        request_id = str(uuid4())
        request_id_ctx.set(request_id)

        # Extract basic info from scope
        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # Check if we should log
        if path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Extract headers
        headers = dict(scope.get("headers", []))
        headers = {k.decode(): v.decode() for k, v in headers.items()}

        # Track response status
        response_status = 200
        start_time = time.perf_counter()

        async def send_wrapper(message: dict) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
                # Add request ID header
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Log audit entry
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Extract metadata
            user_id = headers.get("x-user-id")
            ip_address = headers.get("x-forwarded-for", "").split(",")[0].strip()
            user_agent = headers.get("user-agent", "")

            resource_type = "system"
            if "/documents" in path:
                resource_type = "document"
            elif "/patients" in path:
                resource_type = "patient"

            try:
                async with async_session_maker() as db:
                    await self.audit_service.log_event(
                        db=db,
                        action="read" if method == "GET" else "write",
                        resource_type=resource_type,
                        user_id=user_id,
                        ip_address=ip_address or "unknown",
                        user_agent=user_agent[:500] if user_agent else None,
                        request_id=request_id,
                        request_method=method,
                        request_path=path,
                        response_status=response_status,
                        details={"duration_ms": round(duration_ms, 2)},
                        phi_accessed=self.audit_service.auto_detect_phi(
                            resource_type=resource_type,
                            request_path=path,
                        ),
                        success=response_status < 400,
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Failed to log audit entry: {e}")
