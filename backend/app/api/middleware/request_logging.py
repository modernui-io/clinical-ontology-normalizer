"""Request/Response Logging Middleware (CTO-6).

Logs every HTTP request and response with structured fields:
- method, path, status_code, duration_ms, request_id
- Skips noise endpoints (/health, /ready, /metrics, /favicon.ico)
- Integrates with contextvar-based request_id from RequestIdMiddleware

This middleware should be added *after* RequestIdMiddleware in the
middleware stack so that the request_id context variable is already set
when this middleware runs.

Usage:
    from app.api.middleware.request_logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.access")

# Paths that are excluded from access logging to reduce noise.
# These are typically called by health-check probes every few seconds.
_SKIP_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/ready",
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/health/live",
        "/api/v1/metrics",
        "/metrics",
        "/favicon.ico",
    }
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that emits a structured log line for every request/response.

    Fields logged:
    - method: HTTP method (GET, POST, ...)
    - path: URL path (without query string)
    - status_code: HTTP response status code
    - duration_ms: Wall-clock time to process the request
    - request_id: From RequestIdMiddleware context
    - client_ip: Client IP address
    - content_length: Response content-length (if available)
    - user_agent: Truncated User-Agent header

    Noise endpoints (health checks, metrics) are silently skipped.
    """

    def __init__(self, app: Any, skip_paths: frozenset[str] | None = None):
        super().__init__(app)
        self.skip_paths = skip_paths or _SKIP_PATHS

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path

        # Skip noise endpoints
        if path in self.skip_paths:
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500  # default in case of unhandled exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # Let the exception propagate; it will be caught by ErrorHandlerMiddleware.
            # We still log the request with a 500 status.
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            # Pull request_id from request.state (set by RequestIdMiddleware)
            request_id = getattr(request.state, "request_id", None)

            extra: dict[str, Any] = {
                "method": request.method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "event": "http_request",
            }

            if request_id:
                extra["request_id"] = request_id

            client_ip = request.client.host if request.client else None
            if client_ip:
                extra["client_ip"] = client_ip

            user_agent = request.headers.get("user-agent", "")
            if user_agent:
                extra["user_agent"] = user_agent[:200]  # truncate long UAs

            # Choose log level based on status code
            if status_code >= 500:
                logger.error(
                    "%s %s %d %.1fms",
                    request.method,
                    path,
                    status_code,
                    duration_ms,
                    extra=extra,
                )
            elif status_code >= 400:
                logger.warning(
                    "%s %s %d %.1fms",
                    request.method,
                    path,
                    status_code,
                    duration_ms,
                    extra=extra,
                )
            else:
                logger.info(
                    "%s %s %d %.1fms",
                    request.method,
                    path,
                    status_code,
                    duration_ms,
                    extra=extra,
                )
