"""Request ID middleware for request tracing.

This module provides:
- Request ID generation and tracking
- Context variables for request-scoped state
- Integration with logging
- Headers for request tracing (X-Request-ID)
- VP-DevOps-3: Database request context integration

Usage:
    from app.api.middleware.request_id import RequestIdMiddleware, get_request_id

    # Add middleware
    app.add_middleware(RequestIdMiddleware)

    # Get current request ID anywhere in request context
    request_id = get_request_id()
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# Import database context for integration
from app.core.database import DatabaseRequestContext, set_db_request_context

logger = logging.getLogger(__name__)

# Context variable for request ID - accessible throughout the request lifecycle
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Context variable for request context (additional metadata)
_request_context_ctx: ContextVar[dict[str, Any]] = ContextVar("request_context", default={})

# Header names
REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


# ============================================================================
# Context Accessors
# ============================================================================


def get_request_id() -> str | None:
    """Get the current request ID from context.

    Returns:
        The request ID for the current request, or None if not in a request context.

    Example:
        from app.api.middleware.request_id import get_request_id

        def my_function():
            request_id = get_request_id()
            logger.info(f"Processing with request_id={request_id}")
    """
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context.

    This is primarily used internally by the middleware, but can be
    used to set a request ID in non-HTTP contexts (e.g., background jobs).

    Args:
        request_id: The request ID to set
    """
    _request_id_ctx.set(request_id)


def get_request_context() -> dict[str, Any]:
    """Get the current request context.

    Returns:
        Dictionary with request metadata (method, path, client IP, etc.)
    """
    return _request_context_ctx.get()


def set_request_context(context: dict[str, Any]) -> None:
    """Set the request context.

    Args:
        context: Dictionary with request metadata
    """
    _request_context_ctx.set(context)


def clear_request_context() -> None:
    """Clear the request context and ID.

    Called at the end of request processing.
    """
    _request_id_ctx.set(None)
    _request_context_ctx.set({})


def generate_request_id() -> str:
    """Generate a new unique request ID.

    Returns:
        A unique string identifier in the format 'req-{uuid}'
    """
    return f"req-{uuid.uuid4().hex[:12]}"


# ============================================================================
# Request ID Middleware
# ============================================================================


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns and tracks request IDs.

    Features:
    - Generates unique request ID for each request
    - Accepts client-provided X-Request-ID header
    - Stores request ID in context variable for access throughout request
    - Adds X-Request-ID header to response
    - Supports correlation IDs for distributed tracing
    - Integrates with logging

    Usage:
        app.add_middleware(RequestIdMiddleware)

        # Optional: accept client-provided IDs
        app.add_middleware(RequestIdMiddleware, accept_client_id=True)
    """

    def __init__(
        self,
        app: Any,
        accept_client_id: bool = True,
        header_name: str = REQUEST_ID_HEADER,
        prefix: str = "req-",
    ):
        """Initialize the middleware.

        Args:
            app: The ASGI application
            accept_client_id: Whether to accept X-Request-ID from client
            header_name: Header name for request ID
            prefix: Prefix for generated request IDs
        """
        super().__init__(app)
        self.accept_client_id = accept_client_id
        self.header_name = header_name
        self.prefix = prefix

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process the request with request ID tracking.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response with X-Request-ID header added
        """
        # Get or generate request ID
        request_id = self._get_or_generate_request_id(request)

        # Get correlation ID (for distributed tracing)
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)

        # Set context variables
        set_request_id(request_id)
        set_request_context({
            "request_id": request_id,
            "correlation_id": correlation_id,
            "method": request.method,
            "path": str(request.url.path),
            "query": str(request.url.query) if request.url.query else None,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        })

        # VP-DevOps-3: Set database request context for exception logging
        set_db_request_context(DatabaseRequestContext(
            request_id=request_id,
            user_id=None,  # Will be set by auth middleware if available
            endpoint=str(request.url.path),
            method=request.method,
        ))

        # Store in request state for access in route handlers
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        try:
            # Log request start
            logger.debug(
                f"Request started: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                }
            )

            # Process request
            response = await call_next(request)

            # Add request ID to response headers
            response.headers[self.header_name] = request_id
            if correlation_id:
                response.headers[CORRELATION_ID_HEADER] = correlation_id

            # Log request completion
            logger.debug(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                }
            )

            return response

        except Exception as e:
            # Log error with request context
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {type(e).__name__}",
                extra={
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

        finally:
            # Clear context
            clear_request_context()
            # VP-DevOps-3: Clear database context
            set_db_request_context(None)

    def _get_or_generate_request_id(self, request: Request) -> str:
        """Get request ID from header or generate a new one.

        Args:
            request: The HTTP request

        Returns:
            Request ID string
        """
        if self.accept_client_id:
            client_id = request.headers.get(self.header_name)
            if client_id and self._is_valid_request_id(client_id):
                return client_id

        return self._generate_request_id()

    def _generate_request_id(self) -> str:
        """Generate a new request ID.

        Returns:
            Generated request ID with configured prefix
        """
        return f"{self.prefix}{uuid.uuid4().hex[:12]}"

    def _is_valid_request_id(self, request_id: str) -> bool:
        """Validate a client-provided request ID.

        Args:
            request_id: The request ID to validate

        Returns:
            True if valid, False otherwise
        """
        # Basic validation: non-empty, reasonable length, no weird characters
        if not request_id:
            return False
        if len(request_id) > 64:
            return False
        # Allow alphanumeric, dash, underscore
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', request_id):
            return False
        return True


# ============================================================================
# Logging Integration
# ============================================================================


class RequestIdLogFilter(logging.Filter):
    """Logging filter that adds request ID to log records.

    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(RequestIdLogFilter())

        # In format string, use %(request_id)s
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(request_id)s] %(levelname)s - %(message)s'
        ))
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id to log record.

        Args:
            record: The log record

        Returns:
            True (always allows the record through)
        """
        record.request_id = get_request_id() or "no-request"
        return True


def configure_logging_with_request_id(
    logger_name: str | None = None,
    log_format: str | None = None,
) -> None:
    """Configure logging to include request IDs.

    Args:
        logger_name: Name of logger to configure (None for root)
        log_format: Custom format string (must include %(request_id)s)

    Example:
        configure_logging_with_request_id()
        # Or with custom format:
        configure_logging_with_request_id(
            log_format='%(asctime)s [%(request_id)s] %(levelname)s - %(message)s'
        )
    """
    if log_format is None:
        log_format = (
            "%(asctime)s [%(request_id)s] %(levelname)s "
            "%(name)s:%(lineno)d - %(message)s"
        )

    target_logger = logging.getLogger(logger_name)

    # Add filter to all handlers
    for handler in target_logger.handlers:
        handler.addFilter(RequestIdLogFilter())

    # If no handlers, add a default one
    if not target_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format))
        handler.addFilter(RequestIdLogFilter())
        target_logger.addHandler(handler)


# ============================================================================
# Dependency for FastAPI Routes
# ============================================================================


def get_request_id_dependency(request: Request) -> str:
    """FastAPI dependency to get the current request ID.

    Usage:
        from fastapi import Depends
        from app.api.middleware.request_id import get_request_id_dependency

        @router.get("/example")
        async def example(request_id: str = Depends(get_request_id_dependency)):
            return {"request_id": request_id}
    """
    return getattr(request.state, "request_id", None) or get_request_id() or "unknown"


# ============================================================================
# Background Task Support
# ============================================================================


class RequestIdContext:
    """Context manager for setting request ID in background tasks.

    Use this when running code outside of an HTTP request context
    but you want to maintain request ID continuity.

    Usage:
        from app.api.middleware.request_id import RequestIdContext

        # In a background task
        with RequestIdContext("job-abc123"):
            # Code here will have request_id = "job-abc123"
            process_something()
    """

    def __init__(self, request_id: str | None = None):
        """Initialize the context.

        Args:
            request_id: Request ID to use, or None to generate one
        """
        self.request_id = request_id or generate_request_id()
        self._token = None

    def __enter__(self) -> str:
        """Enter the context and set the request ID."""
        self._token = _request_id_ctx.set(self.request_id)
        return self.request_id

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context and reset the request ID."""
        if self._token is not None:
            _request_id_ctx.reset(self._token)


async def with_request_id(request_id: str | None = None) -> str:
    """Async context manager version of RequestIdContext.

    Usage:
        async with with_request_id("job-123"):
            await some_async_operation()
    """
    ctx = RequestIdContext(request_id)
    return ctx.__enter__()
