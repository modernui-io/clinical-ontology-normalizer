"""Rate limiting middleware for Clinical Ontology Normalizer API.

This module provides:
- In-memory token bucket rate limiting (can be extended to Redis)
- Configurable limits per endpoint
- Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
- 429 Too Many Requests responses when limits are exceeded

Usage:
    from app.api.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)
"""

import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.errors import ErrorCode, ErrorResponse
from app.api.middleware.request_id import get_request_id
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Rate Limit Configuration
# ============================================================================


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule.

    Attributes:
        requests_per_window: Maximum requests allowed in the window
        window_seconds: Duration of the rate limit window in seconds
        burst_limit: Maximum burst requests (optional, defaults to requests_per_window)
    """

    requests_per_window: int = 100
    window_seconds: int = 60
    burst_limit: int | None = None

    def __post_init__(self) -> None:
        if self.burst_limit is None:
            self.burst_limit = self.requests_per_window


# Default rate limits per endpoint pattern
DEFAULT_RATE_LIMITS: dict[str, RateLimitConfig] = {
    # High-traffic endpoints - more permissive
    "/api/v1/health": RateLimitConfig(requests_per_window=1000, window_seconds=60),
    "/api/v1/ready": RateLimitConfig(requests_per_window=1000, window_seconds=60),
    "/health": RateLimitConfig(requests_per_window=1000, window_seconds=60),
    "/ready": RateLimitConfig(requests_per_window=1000, window_seconds=60),

    # Search endpoints - moderate limits
    "/api/v1/search": RateLimitConfig(requests_per_window=200, window_seconds=60),
    "/api/v1/coding/suggest": RateLimitConfig(requests_per_window=300, window_seconds=60),

    # Document processing - lower limits (expensive operations)
    "/api/v1/documents": RateLimitConfig(requests_per_window=100, window_seconds=60),
    "/api/v1/llm": RateLimitConfig(requests_per_window=50, window_seconds=60),

    # Batch operations - very limited
    "/api/v1/documents/batch": RateLimitConfig(requests_per_window=20, window_seconds=60),
    "/api/v1/patients/batch": RateLimitConfig(requests_per_window=20, window_seconds=60),

    # Export operations - limited
    "/api/v1/export": RateLimitConfig(requests_per_window=30, window_seconds=60),

    # Knowledge Graph endpoints
    # KG Health monitoring - permissive (monitoring tools)
    "/api/v1/kg/health": RateLimitConfig(requests_per_window=500, window_seconds=60),
    "/api/v1/kg/health/liveness": RateLimitConfig(requests_per_window=1000, window_seconds=60),
    "/api/v1/kg/health/readiness": RateLimitConfig(requests_per_window=1000, window_seconds=60),
    "/api/v1/kg/health/metrics": RateLimitConfig(requests_per_window=300, window_seconds=60),

    # KG Orchestration - moderate limits
    "/api/v1/kg/orchestration/status": RateLimitConfig(requests_per_window=200, window_seconds=60),
    "/api/v1/kg/orchestration/query": RateLimitConfig(requests_per_window=100, window_seconds=60),
    "/api/v1/kg/orchestration/clinical-question": RateLimitConfig(requests_per_window=60, window_seconds=60),

    # KG Reasoning - lower limits (expensive operations)
    "/api/v1/kg/orchestration/reasoning-path": RateLimitConfig(requests_per_window=30, window_seconds=60),
    "/api/v1/kg/orchestration/patient": RateLimitConfig(requests_per_window=50, window_seconds=60),

    # KG MDT sessions - very limited (expensive multi-agent operations)
    "/api/v1/kg/orchestration/mdt-session": RateLimitConfig(requests_per_window=10, window_seconds=60),

    # KG Export - limited
    "/api/v1/kg/orchestration/export": RateLimitConfig(requests_per_window=20, window_seconds=60),

    # KG Benchmark endpoints - limited (resource-intensive)
    "/api/v1/kg/benchmark/run": RateLimitConfig(requests_per_window=5, window_seconds=60),
    "/api/v1/kg/benchmark/suite": RateLimitConfig(requests_per_window=3, window_seconds=60),
    "/api/v1/kg/benchmark/drknows": RateLimitConfig(requests_per_window=5, window_seconds=60),
    "/api/v1/kg/benchmark": RateLimitConfig(requests_per_window=30, window_seconds=60),

    # Default for all other endpoints
    "*": RateLimitConfig(requests_per_window=100, window_seconds=60),
}


# ============================================================================
# Token Bucket Implementation
# ============================================================================


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Uses the token bucket algorithm:
    - Bucket starts full with `capacity` tokens
    - Tokens are consumed by requests
    - Tokens are refilled at `refill_rate` per second
    - If no tokens available, request is rate limited
    """

    capacity: int
    refill_rate: float
    tokens: float = field(default=0.0, init=False)
    last_refill: float = field(default_factory=time.time, init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> tuple[bool, float]:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            Tuple of (success, time_until_available)
            - success: True if tokens were consumed
            - time_until_available: Seconds until tokens will be available (0 if success)
        """
        now = time.time()
        self._refill(now)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # Calculate time until enough tokens are available
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            return False, wait_time

    def _refill(self, now: float) -> None:
        """Refill tokens based on elapsed time."""
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    @property
    def remaining(self) -> int:
        """Get remaining tokens (refills first)."""
        self._refill(time.time())
        return int(self.tokens)


# ============================================================================
# Rate Limiter Store
# ============================================================================


class RateLimiterStore:
    """Thread-safe store for rate limiter buckets.

    Stores token buckets per client IP and endpoint combination.
    Can be extended to use Redis for distributed rate limiting.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = Lock()
        self._cleanup_interval = 300  # Cleanup every 5 minutes
        self._last_cleanup = time.time()

    def get_bucket(
        self,
        client_id: str,
        endpoint: str,
        config: RateLimitConfig,
    ) -> TokenBucket:
        """Get or create a token bucket for a client/endpoint combination.

        Args:
            client_id: Client identifier (usually IP address)
            endpoint: The API endpoint path
            config: Rate limit configuration for this endpoint

        Returns:
            TokenBucket for this client/endpoint
        """
        key = f"{client_id}:{endpoint}"

        with self._lock:
            # Periodic cleanup of old buckets
            self._maybe_cleanup()

            if key not in self._buckets:
                # Create new bucket
                refill_rate = config.requests_per_window / config.window_seconds
                self._buckets[key] = TokenBucket(
                    capacity=config.burst_limit or config.requests_per_window,
                    refill_rate=refill_rate,
                )

            return self._buckets[key]

    def _maybe_cleanup(self) -> None:
        """Clean up old buckets that haven't been used recently."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        # Remove buckets that are full (haven't been used recently)
        keys_to_remove = []
        for key, bucket in self._buckets.items():
            if bucket.remaining >= bucket.capacity * 0.95:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._buckets[key]

        self._last_cleanup = now
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} idle rate limit buckets")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the rate limiter store."""
        with self._lock:
            return {
                "total_buckets": len(self._buckets),
                "last_cleanup": datetime.fromtimestamp(self._last_cleanup, tz=UTC).isoformat(),
            }


# Global rate limiter store (singleton)
_rate_limiter_store: RateLimiterStore | None = None


def get_rate_limiter_store() -> RateLimiterStore:
    """Get the global rate limiter store."""
    global _rate_limiter_store
    if _rate_limiter_store is None:
        _rate_limiter_store = RateLimiterStore()
    return _rate_limiter_store


# ============================================================================
# Rate Limit Middleware
# ============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits on API requests.

    Features:
    - Token bucket algorithm for smooth rate limiting
    - Configurable limits per endpoint
    - Rate limit headers in responses
    - 429 responses with Retry-After header when exceeded
    - In-memory storage (can be extended to Redis)

    Usage:
        app.add_middleware(RateLimitMiddleware)

        # Or with custom rate limits:
        app.add_middleware(
            RateLimitMiddleware,
            rate_limits={"/api/v1/custom": RateLimitConfig(100, 60)}
        )
    """

    def __init__(
        self,
        app: Any,
        rate_limits: dict[str, RateLimitConfig] | None = None,
        enabled: bool = True,
    ):
        """Initialize the rate limit middleware.

        Args:
            app: The ASGI application
            rate_limits: Custom rate limits per endpoint (merged with defaults)
            enabled: Whether rate limiting is enabled (can be disabled for testing)
        """
        super().__init__(app)
        self.enabled = enabled
        self.store = get_rate_limiter_store()

        # Merge custom rate limits with defaults
        self.rate_limits = DEFAULT_RATE_LIMITS.copy()
        if rate_limits:
            self.rate_limits.update(rate_limits)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request with rate limiting.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response from handler or 429 if rate limited
        """
        # Skip rate limiting if disabled or for non-API requests
        if not self.enabled:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Get rate limit config for this endpoint
        endpoint = str(request.url.path)
        config = self._get_rate_limit_config(endpoint)

        # Get token bucket and try to consume a token
        bucket = self.store.get_bucket(client_id, endpoint, config)
        allowed, wait_time = bucket.consume()

        if not allowed:
            # Rate limit exceeded
            return self._create_rate_limit_response(
                request=request,
                config=config,
                wait_time=wait_time,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        self._add_rate_limit_headers(response, config, bucket)

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get a unique identifier for the client.

        Uses X-Forwarded-For header if behind a proxy, otherwise client IP.

        Args:
            request: The HTTP request

        Returns:
            Client identifier string
        """
        # Check for forwarded header (when behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _get_rate_limit_config(self, endpoint: str) -> RateLimitConfig:
        """Get the rate limit configuration for an endpoint.

        Checks for exact matches first, then prefix matches, then default.

        Args:
            endpoint: The request path

        Returns:
            RateLimitConfig for this endpoint
        """
        # Exact match
        if endpoint in self.rate_limits:
            return self.rate_limits[endpoint]

        # Prefix match (longest match wins)
        best_match: str | None = None
        best_match_len = 0

        for pattern in self.rate_limits:
            if pattern == "*":
                continue
            if endpoint.startswith(pattern) and len(pattern) > best_match_len:
                best_match = pattern
                best_match_len = len(pattern)

        if best_match:
            return self.rate_limits[best_match]

        # Default
        return self.rate_limits.get("*", RateLimitConfig())

    def _create_rate_limit_response(
        self,
        request: Request,
        config: RateLimitConfig,
        wait_time: float,
    ) -> JSONResponse:
        """Create a 429 Too Many Requests response.

        Args:
            request: The HTTP request
            config: Rate limit configuration
            wait_time: Seconds until rate limit resets

        Returns:
            JSONResponse with 429 status
        """
        request_id = get_request_id()
        retry_after = int(wait_time) + 1  # Round up

        error_response = ErrorResponse(
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            request_id=request_id,
            path=str(request.url.path),
        )

        logger.warning(
            f"Rate limit exceeded for {request.url.path}",
            extra={
                "request_id": request_id,
                "path": str(request.url.path),
                "client_ip": self._get_client_id(request),
                "retry_after": retry_after,
            }
        )

        reset_time = int(time.time() + wait_time)

        return JSONResponse(
            status_code=429,
            content=error_response.model_dump(mode="json", exclude_none=True),
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(config.requests_per_window),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
            },
        )

    def _add_rate_limit_headers(
        self,
        response: Response,
        config: RateLimitConfig,
        bucket: TokenBucket,
    ) -> None:
        """Add rate limit headers to the response.

        Args:
            response: The HTTP response
            config: Rate limit configuration
            bucket: The token bucket for this request
        """
        reset_time = int(time.time() + config.window_seconds)

        response.headers["X-RateLimit-Limit"] = str(config.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(bucket.remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)


# ============================================================================
# Rate Limit Decorators (for custom per-route limits)
# ============================================================================


def rate_limit(
    requests_per_window: int = 100,
    window_seconds: int = 60,
) -> Callable:
    """Decorator to set custom rate limits on specific routes.

    This is a placeholder for future implementation that would allow
    per-route rate limit customization via decorators.

    Usage:
        @router.get("/expensive-operation")
        @rate_limit(requests_per_window=10, window_seconds=60)
        async def expensive_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Store rate limit config as function attribute
        func._rate_limit_config = RateLimitConfig(  # type: ignore[attr-defined]
            requests_per_window=requests_per_window,
            window_seconds=window_seconds,
        )
        return func
    return decorator
