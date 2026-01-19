"""Global exception handler middleware for Clinical Ontology Normalizer API.

This module provides:
- Global exception handling for all API errors
- Structured error logging with request context
- Sanitization of sensitive data in error responses
- Integration with request ID tracking
- Stack traces in development mode for debugging

Usage:
    from app.api.middleware.error_handler import ErrorHandlerMiddleware

    app.add_middleware(ErrorHandlerMiddleware)
"""

import logging
import sys
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.errors import (
    APIError,
    AuthenticationError,
    ConflictError,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    InternalError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
    create_validation_errors_from_pydantic,
)
from app.api.middleware.request_id import get_request_id
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Sensitive Data Patterns for Sanitization
# ============================================================================

# Fields that should be redacted from logs
SENSITIVE_FIELDS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "ssn",
    "social_security",
    "mrn",
    "medical_record_number",
    "dob",
    "date_of_birth",
    "credit_card",
    "card_number",
}

# Headers that should be redacted from logs
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "cookie",
    "set-cookie",
}


# ============================================================================
# Error Handler Middleware
# ============================================================================


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware that catches all exceptions and returns standardized error responses.

    Features:
    - Catches and handles all exception types
    - Converts exceptions to standardized ErrorResponse format
    - Logs errors with request context
    - Sanitizes sensitive data from responses
    - Preserves request IDs for tracing
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and handle any exceptions.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response from the handler or error response
        """
        request_id = get_request_id()

        try:
            response = await call_next(request)
            return response

        except Exception as exc:
            return await self._handle_exception(request, exc, request_id)

    async def _handle_exception(
        self,
        request: Request,
        exc: Exception,
        request_id: str | None,
    ) -> JSONResponse:
        """Handle an exception and return appropriate error response.

        Args:
            request: The HTTP request
            exc: The exception that was raised
            request_id: Request ID for tracing

        Returns:
            JSONResponse with error details
        """
        # Convert exception to APIError if needed
        api_error = self._convert_to_api_error(exc)

        # Log the error with context
        self._log_error(request, api_error, exc, request_id)

        # Build error response
        error_response = api_error.to_response(
            request_id=request_id,
            path=str(request.url.path),
        )

        # Build response content
        response_content = error_response.model_dump(mode="json", exclude_none=True)

        # Include stack trace in development mode for server errors
        if settings.debug and api_error.status_code >= 500:
            response_content["debug"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "stack_trace": traceback.format_exception(type(exc), exc, exc.__traceback__),
            }

        # Create JSON response
        response = JSONResponse(
            status_code=api_error.status_code,
            content=response_content,
            headers=api_error.headers,
        )

        return response

    def _convert_to_api_error(self, exc: Exception) -> APIError:
        """Convert any exception to an appropriate APIError.

        Args:
            exc: The exception to convert

        Returns:
            APIError instance with appropriate error code and message
        """
        # Already an APIError
        if isinstance(exc, APIError):
            return exc

        # FastAPI/Pydantic validation errors
        if isinstance(exc, (RequestValidationError, PydanticValidationError)):
            return self._handle_validation_error(exc)

        # SQLAlchemy errors
        if isinstance(exc, SQLAlchemyError):
            return self._handle_sqlalchemy_error(exc)

        # Standard HTTP exceptions (from FastAPI)
        if hasattr(exc, "status_code") and hasattr(exc, "detail"):
            return self._handle_http_exception(exc)

        # Unknown exceptions become internal errors
        return InternalError(
            message="An unexpected error occurred while processing your request",
            error_code=ErrorCode.INTERNAL_ERROR,
        )

    def _handle_validation_error(
        self, exc: RequestValidationError | PydanticValidationError
    ) -> ValidationError:
        """Convert Pydantic validation errors to our ValidationError format.

        Args:
            exc: The validation error

        Returns:
            ValidationError with field-level details and suggestions
        """
        errors = exc.errors() if hasattr(exc, "errors") else []

        # Use the enhanced validation error converter
        details = create_validation_errors_from_pydantic(errors)

        return ValidationError(
            message="Request validation failed",
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
        )

    def _handle_sqlalchemy_error(self, exc: SQLAlchemyError) -> APIError:
        """Convert SQLAlchemy errors to appropriate API errors.

        Args:
            exc: The SQLAlchemy error

        Returns:
            APIError with appropriate error code
        """
        if isinstance(exc, OperationalError):
            # Database connection issues
            return ServiceUnavailableError(
                message="Database is temporarily unavailable. Please try again later.",
                error_code=ErrorCode.SERVICE_DATABASE_UNAVAILABLE,
                retry_after=30,
            )

        if isinstance(exc, IntegrityError):
            # Unique constraint violations, foreign key errors
            error_msg = str(exc.orig) if exc.orig else str(exc)

            if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
                return ConflictError(
                    message="A resource with this identifier already exists",
                    error_code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
                )

            return ValidationError(
                message="Data integrity constraint violation",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        # Generic database error
        return InternalError(
            message="A database error occurred",
            error_code=ErrorCode.INTERNAL_DATABASE_ERROR,
        )

    def _handle_http_exception(self, exc: Any) -> APIError:
        """Convert FastAPI HTTPException to our error format.

        Args:
            exc: Exception with status_code and detail attributes

        Returns:
            Appropriate APIError subclass
        """
        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", "An error occurred")

        if status_code == 400:
            return ValidationError(
                message=detail,
                error_code=ErrorCode.VALIDATION_ERROR,
            )
        elif status_code == 401:
            return AuthenticationError(
                message=detail,
                error_code=ErrorCode.AUTH_INVALID_TOKEN,
            )
        elif status_code == 403:
            from app.api.errors import AuthorizationError
            return AuthorizationError(
                message=detail,
                error_code=ErrorCode.FORBIDDEN_INSUFFICIENT_PERMISSIONS,
            )
        elif status_code == 404:
            return NotFoundError(
                message=detail,
                error_code=ErrorCode.NOT_FOUND_RESOURCE,
            )
        elif status_code == 409:
            return ConflictError(
                message=detail,
                error_code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
            )
        elif status_code == 429:
            return RateLimitError(
                message=detail,
                error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            )
        elif status_code == 503:
            return ServiceUnavailableError(
                message=detail,
                error_code=ErrorCode.SERVICE_UNAVAILABLE,
            )
        else:
            return InternalError(
                message=detail,
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    def _sanitize_value(self, value: Any, field: str | None = None) -> Any:
        """Sanitize a value for inclusion in error responses.

        Args:
            value: The value to sanitize
            field: The field name (used to detect sensitive fields)

        Returns:
            Sanitized value safe for logging/response
        """
        # Check if field is sensitive
        if field and any(s in field.lower() for s in SENSITIVE_FIELDS):
            return "[REDACTED]"

        if value is None:
            return None

        if isinstance(value, str):
            # Truncate long strings
            if len(value) > 100:
                return value[:97] + "..."

            # Redact potential PII patterns
            import re
            # SSN pattern
            value = re.sub(r'\d{3}-\d{2}-\d{4}', '[REDACTED-SSN]', value)
            # Phone patterns
            value = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED-PHONE]', value)
            # Email pattern (partial redaction)
            value = re.sub(r'(\w{1,2})\w*@', r'\1***@', value)

            return value

        if isinstance(value, bytes):
            return f"<{len(value)} bytes>"

        if isinstance(value, (list, dict)):
            return f"<{type(value).__name__} with {len(value)} items>"

        return value

    def _log_error(
        self,
        request: Request,
        api_error: APIError,
        original_exc: Exception,
        request_id: str | None,
    ) -> None:
        """Log error with full context for debugging.

        Args:
            request: The HTTP request
            api_error: The converted APIError
            original_exc: The original exception
            request_id: Request ID for tracing
        """
        # Build log context
        log_context = {
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "query_params": self._sanitize_dict(dict(request.query_params)),
            "error_code": api_error.error_code.value,
            "status_code": api_error.status_code,
            "error_type": type(original_exc).__name__,
        }

        # Add client info if available
        if request.client:
            log_context["client_ip"] = request.client.host

        # Log at appropriate level
        if api_error.status_code >= 500:
            # Server errors - include full traceback
            exc_info = sys.exc_info()
            logger.error(
                f"Server error: {api_error.message}",
                extra=log_context,
                exc_info=exc_info,
            )
        elif api_error.status_code >= 400:
            # Client errors - info level, no traceback
            logger.info(
                f"Client error: {api_error.message}",
                extra=log_context,
            )
        else:
            # Other errors
            logger.warning(
                f"Error: {api_error.message}",
                extra=log_context,
            )

    def _sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize a dictionary for logging.

        Args:
            data: Dictionary to sanitize

        Returns:
            Dictionary with sensitive values redacted
        """
        sanitized = {}
        for key, value in data.items():
            if any(s in key.lower() for s in SENSITIVE_FIELDS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:197] + "..."
            else:
                sanitized[key] = value
        return sanitized


# ============================================================================
# Exception Handler Registration
# ============================================================================


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with a FastAPI app.

    This registers handlers for specific exception types that will be
    caught before the middleware, allowing for more specific handling.

    Args:
        app: The FastAPI application instance
    """

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle APIError exceptions."""
        request_id = get_request_id()
        error_response = exc.to_response(
            request_id=request_id,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(mode="json", exclude_none=True),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI validation errors with field-level details and suggestions."""
        request_id = get_request_id()

        # Use the enhanced validation error converter for suggestions
        details = create_validation_errors_from_pydantic(exc.errors())

        error_response = ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
            details=details,
            request_id=request_id,
            path=str(request.url.path),
        )

        logger.info(
            f"Validation error: {len(details)} field(s) failed validation",
            extra={
                "request_id": request_id,
                "path": str(request.url.path),
                "fields": [d.field for d in details],
            }
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump(mode="json", exclude_none=True),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle all uncaught exceptions."""
        request_id = get_request_id()

        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": str(request.url.path),
                "method": request.method,
            },
            exc_info=True,
        )

        error_response = ErrorResponse(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred while processing your request",
            request_id=request_id,
            path=str(request.url.path),
        )

        response_content = error_response.model_dump(mode="json", exclude_none=True)

        # Include stack trace in development mode
        if settings.debug:
            response_content["debug"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "stack_trace": traceback.format_exception(type(exc), exc, exc.__traceback__),
            }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_content,
        )
