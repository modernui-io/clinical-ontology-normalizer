"""Global exception handlers for Clinical Ontology Normalizer API.

Provides FastAPI exception handlers that ensure ALL error responses
follow the standardized ErrorResponse format with:
- error_code: Machine-readable error code
- message: Human-readable message
- details: Field-level error information
- request_id: Request tracing ID
- timestamp: ISO 8601 timestamp
- path: Request path

Usage:
    from app.api.error_handlers import register_all_exception_handlers

    register_all_exception_handlers(app)
"""

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ErrorCode,
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


# HTTP status code to APIError mapping
_STATUS_CODE_MAP: dict[int, type[APIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}

# Default error codes per HTTP status
_DEFAULT_ERROR_CODES: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.AUTH_INVALID_TOKEN,
    403: ErrorCode.FORBIDDEN_INSUFFICIENT_PERMISSIONS,
    404: ErrorCode.NOT_FOUND_RESOURCE,
    409: ErrorCode.CONFLICT_RESOURCE_EXISTS,
    429: ErrorCode.RATE_LIMIT_EXCEEDED,
    500: ErrorCode.INTERNAL_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


def _build_error_json(
    error_code: ErrorCode,
    message: str,
    status_code: int,
    request: Request,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
    exc: Exception | None = None,
) -> JSONResponse:
    """Build a standardized JSON error response.

    Args:
        error_code: Machine-readable error code.
        message: Human-readable message.
        status_code: HTTP status code.
        request: The incoming request.
        details: Optional field-level error details.
        headers: Optional response headers.
        exc: Original exception for debug info.

    Returns:
        JSONResponse with standardized error body.
    """
    request_id = get_request_id()

    error_response = ErrorResponse(
        error_code=error_code,
        message=message,
        details=details or [],
        request_id=request_id,
        path=str(request.url.path),
    )

    content = error_response.model_dump(mode="json", exclude_none=True)

    # Include debug info in development mode for 5xx errors
    if settings.debug and status_code >= 500 and exc is not None:
        content["debug"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "stack_trace": traceback.format_exception(
                type(exc), exc, exc.__traceback__
            ),
        }

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


def register_all_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers with the FastAPI app.

    This ensures every error response follows the ErrorResponse schema,
    regardless of where the exception originates.

    Handlers registered:
    - APIError and all subclasses
    - RequestValidationError (Pydantic/FastAPI validation)
    - PydanticValidationError (direct Pydantic validation)
    - StarletteHTTPException (Starlette HTTP errors)
    - Exception (catch-all for unhandled errors)

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        """Handle custom APIError exceptions."""
        log_level = logging.ERROR if exc.status_code >= 500 else logging.INFO
        logger.log(
            log_level,
            "APIError: %s (code=%s, status=%d, path=%s)",
            exc.message,
            exc.error_code.value,
            exc.status_code,
            request.url.path,
        )

        return _build_error_json(
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            request=request,
            details=[d.model_dump(mode="json", exclude_none=True) for d in exc.details],
            headers=exc.headers,
            exc=exc,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI request validation errors with field-level details."""
        details = create_validation_errors_from_pydantic(exc.errors())

        logger.info(
            "Validation error: %d field(s) failed (path=%s)",
            len(details),
            request.url.path,
        )

        return _build_error_json(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            request=request,
            details=[d.model_dump(mode="json", exclude_none=True) for d in details],
        )

    @app.exception_handler(PydanticValidationError)
    async def handle_pydantic_validation_error(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        """Handle direct Pydantic validation errors."""
        details = create_validation_errors_from_pydantic(exc.errors())

        return _build_error_json(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Data validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            request=request,
            details=[d.model_dump(mode="json", exclude_none=True) for d in details],
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle Starlette/FastAPI HTTPException."""
        error_code = _DEFAULT_ERROR_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        message = exc.detail if isinstance(exc.detail, str) else "An error occurred"

        headers = None
        if isinstance(exc.headers, dict):
            headers = {str(k): str(v) for k, v in exc.headers.items()}

        return _build_error_json(
            error_code=error_code,
            message=message,
            status_code=exc.status_code,
            request=request,
            headers=headers,
            exc=exc,
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler for unhandled exceptions."""
        logger.error(
            "Unhandled exception: %s: %s (path=%s, method=%s)",
            type(exc).__name__,
            str(exc),
            request.url.path,
            request.method,
            exc_info=True,
        )

        return _build_error_json(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred while processing your request",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request=request,
            exc=exc,
        )
