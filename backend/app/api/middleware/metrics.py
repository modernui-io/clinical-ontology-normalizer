"""Metrics collection middleware for request tracking.

Automatically collects metrics for all HTTP requests:
- Request count by method, endpoint, and status code
- Request duration histogram
- Active request gauge
- Error tracking

Usage:
    from app.api.middleware.metrics import MetricsMiddleware

    app.add_middleware(MetricsMiddleware)

The collected metrics are exposed via the /api/v1/metrics endpoint.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Paths to exclude from metrics collection (internal endpoints)
EXCLUDED_PATHS = {
    "/api/v1/metrics",
    "/api/v1/health",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/favicon.ico",
}


# =============================================================================
# Metrics Middleware
# =============================================================================


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that collects HTTP request metrics.

    Tracks:
    - Total request count by method, endpoint, and status
    - Request duration histogram
    - Currently active requests (in-flight)
    - Error counts by type

    Metrics are stored in the global MetricsRegistry and exposed
    via the /api/v1/metrics endpoint.

    Usage:
        app.add_middleware(MetricsMiddleware)

        # Optional: exclude additional paths
        app.add_middleware(
            MetricsMiddleware,
            exclude_paths={"/internal/debug"}
        )
    """

    def __init__(
        self,
        app: Any,
        exclude_paths: set[str] | None = None,
    ) -> None:
        """Initialize the metrics middleware.

        Args:
            app: The ASGI application.
            exclude_paths: Additional paths to exclude from metrics.
        """
        super().__init__(app)
        self.exclude_paths = EXCLUDED_PATHS.copy()
        if exclude_paths:
            self.exclude_paths.update(exclude_paths)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process the request and collect metrics.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response.
        """
        # Skip excluded paths
        path = request.url.path
        if path in self.exclude_paths or self._should_exclude(path):
            return await call_next(request)

        # Import here to avoid circular imports
        from app.api.metrics import get_metrics_registry

        registry = get_metrics_registry()

        # Track in-flight request
        registry.request_started()
        start_time = time.perf_counter()

        try:
            # Process the request
            response = await call_next(request)

            # Calculate duration
            duration = time.perf_counter() - start_time

            # Record metrics
            registry.record_request(
                method=request.method,
                endpoint=path,
                status_code=response.status_code,
                duration_seconds=duration,
            )

            return response

        except Exception as e:
            # Calculate duration even on error
            duration = time.perf_counter() - start_time

            # Record error metrics
            registry.record_request(
                method=request.method,
                endpoint=path,
                status_code=500,  # Internal server error
                duration_seconds=duration,
            )

            # Record specific error type
            registry.http_request_errors_total.inc(
                labels=(request.method.upper(), path, type(e).__name__)
            )

            # Re-raise the exception
            raise

        finally:
            # Decrement in-flight counter
            registry.request_finished()

    def _should_exclude(self, path: str) -> bool:
        """Check if a path should be excluded from metrics.

        Args:
            path: The request path.

        Returns:
            True if the path should be excluded.
        """
        # Exclude paths that start with excluded prefixes
        excluded_prefixes = ["/docs", "/redoc", "/static"]
        return any(path.startswith(prefix) for prefix in excluded_prefixes)


# =============================================================================
# Context Manager for Manual Timing
# =============================================================================


class MetricsTimer:
    """Context manager for manually timing operations.

    Usage:
        from app.api.middleware.metrics import MetricsTimer

        with MetricsTimer("database", "query") as timer:
            result = await db.execute(query)
        # timer.duration contains the elapsed time
    """

    def __init__(self, operation: str, sub_operation: str = "default") -> None:
        """Initialize the timer.

        Args:
            operation: The operation being timed (e.g., "database").
            sub_operation: Sub-operation name (e.g., "query").
        """
        self.operation = operation
        self.sub_operation = sub_operation
        self.start_time: float = 0
        self.duration: float = 0

    def __enter__(self) -> "MetricsTimer":
        """Start the timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the timer and optionally record the metric."""
        self.duration = time.perf_counter() - self.start_time

        # Could record to custom histogram here if needed
        logger.debug(
            f"Operation {self.operation}/{self.sub_operation} took {self.duration*1000:.2f}ms"
        )


# =============================================================================
# Decorator for Function Timing
# =============================================================================


def track_time(operation: str) -> Callable:
    """Decorator to track execution time of a function.

    Args:
        operation: Name of the operation for metrics.

    Returns:
        Decorator function.

    Usage:
        @track_time("search")
        async def search_patients(query: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        import asyncio
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with MetricsTimer(operation, func.__name__):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with MetricsTimer(operation, func.__name__):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
