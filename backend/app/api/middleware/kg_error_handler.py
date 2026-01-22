"""Error handling middleware for Knowledge Graph endpoints.

This module provides specialized error handling for KG operations:
- Structured error responses
- Error categorization by type
- Correlation ID tracking
- Retry information for transient errors
"""

from __future__ import annotations

import logging
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

T = TypeVar("T")


class KGErrorType(str, Enum):
    """Categories of KG errors."""

    # Client errors (4xx)
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    INVALID_CUI = "invalid_cui"
    INVALID_QUERY = "invalid_query"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"

    # Server errors (5xx)
    DATABASE_ERROR = "database_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"

    # KG-specific errors
    GRAPH_TRAVERSAL_ERROR = "graph_traversal_error"
    EMBEDDING_ERROR = "embedding_error"
    CACHE_ERROR = "cache_error"
    REASONING_ERROR = "reasoning_error"


@dataclass
class KGError(Exception):
    """Structured error for Knowledge Graph operations."""

    error_type: KGErrorType
    message: str
    status_code: int = 500
    details: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    retryable: bool = False
    retry_after_seconds: int | None = None

    def __str__(self) -> str:
        return f"{self.error_type.value}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "error": {
                "type": self.error_type.value,
                "message": self.message,
                "status_code": self.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }

        if self.correlation_id:
            result["error"]["correlation_id"] = self.correlation_id

        if self.details:
            result["error"]["details"] = self.details

        if self.retryable:
            result["error"]["retryable"] = True
            if self.retry_after_seconds:
                result["error"]["retry_after_seconds"] = self.retry_after_seconds

        return result


# Pre-defined error factories
class KGErrors:
    """Factory methods for common KG errors."""

    @staticmethod
    def not_found(resource_type: str, identifier: str) -> KGError:
        """Resource not found error."""
        return KGError(
            error_type=KGErrorType.NOT_FOUND,
            message=f"{resource_type} not found: {identifier}",
            status_code=404,
            details={"resource_type": resource_type, "identifier": identifier},
        )

    @staticmethod
    def invalid_cui(cui: str, reason: str = "Invalid CUI format") -> KGError:
        """Invalid CUI error."""
        return KGError(
            error_type=KGErrorType.INVALID_CUI,
            message=f"Invalid CUI '{cui}': {reason}",
            status_code=400,
            details={"cui": cui, "reason": reason},
        )

    @staticmethod
    def invalid_query(query: str, reason: str) -> KGError:
        """Invalid query error."""
        return KGError(
            error_type=KGErrorType.INVALID_QUERY,
            message=f"Invalid query: {reason}",
            status_code=400,
            details={"query": query[:200] if len(query) > 200 else query, "reason": reason},
        )

    @staticmethod
    def database_error(operation: str, details: str | None = None) -> KGError:
        """Database operation error."""
        return KGError(
            error_type=KGErrorType.DATABASE_ERROR,
            message=f"Database error during {operation}",
            status_code=503,
            details={"operation": operation, "error_details": details} if details else {"operation": operation},
            retryable=True,
            retry_after_seconds=5,
        )

    @staticmethod
    def connection_error(service: str, details: str | None = None) -> KGError:
        """Service connection error."""
        return KGError(
            error_type=KGErrorType.CONNECTION_ERROR,
            message=f"Failed to connect to {service}",
            status_code=503,
            details={"service": service, "error_details": details} if details else {"service": service},
            retryable=True,
            retry_after_seconds=10,
        )

    @staticmethod
    def timeout_error(operation: str, timeout_seconds: float) -> KGError:
        """Operation timeout error."""
        return KGError(
            error_type=KGErrorType.TIMEOUT_ERROR,
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            status_code=504,
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            retryable=True,
            retry_after_seconds=30,
        )

    @staticmethod
    def rate_limited(limit: int, window_seconds: int, retry_after: int) -> KGError:
        """Rate limit exceeded error."""
        return KGError(
            error_type=KGErrorType.RATE_LIMITED,
            message=f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            status_code=429,
            details={"limit": limit, "window_seconds": window_seconds},
            retryable=True,
            retry_after_seconds=retry_after,
        )

    @staticmethod
    def service_unavailable(service: str, reason: str | None = None) -> KGError:
        """Service unavailable error."""
        return KGError(
            error_type=KGErrorType.SERVICE_UNAVAILABLE,
            message=f"Service '{service}' is unavailable" + (f": {reason}" if reason else ""),
            status_code=503,
            details={"service": service, "reason": reason} if reason else {"service": service},
            retryable=True,
            retry_after_seconds=60,
        )

    @staticmethod
    def validation_error(field: str, message: str, value: Any = None) -> KGError:
        """Input validation error."""
        details: dict[str, Any] = {"field": field, "message": message}
        if value is not None:
            details["received_value"] = str(value)[:100]

        return KGError(
            error_type=KGErrorType.VALIDATION_ERROR,
            message=f"Validation error for '{field}': {message}",
            status_code=400,
            details=details,
        )

    @staticmethod
    def graph_traversal_error(
        start_cui: str,
        end_cui: str | None = None,
        reason: str = "Graph traversal failed"
    ) -> KGError:
        """Graph traversal error."""
        details: dict[str, Any] = {"start_cui": start_cui, "reason": reason}
        if end_cui:
            details["end_cui"] = end_cui

        return KGError(
            error_type=KGErrorType.GRAPH_TRAVERSAL_ERROR,
            message=f"Graph traversal error: {reason}",
            status_code=500,
            details=details,
        )

    @staticmethod
    def embedding_error(text: str, reason: str) -> KGError:
        """Embedding generation error."""
        return KGError(
            error_type=KGErrorType.EMBEDDING_ERROR,
            message=f"Failed to generate embedding: {reason}",
            status_code=500,
            details={"text_preview": text[:50] if text else "", "reason": reason},
            retryable=True,
            retry_after_seconds=5,
        )

    @staticmethod
    def cache_error(operation: str, reason: str) -> KGError:
        """Cache operation error."""
        return KGError(
            error_type=KGErrorType.CACHE_ERROR,
            message=f"Cache {operation} failed: {reason}",
            status_code=500,
            details={"operation": operation, "reason": reason},
        )

    @staticmethod
    def reasoning_error(query: str, reason: str) -> KGError:
        """Reasoning operation error."""
        return KGError(
            error_type=KGErrorType.REASONING_ERROR,
            message=f"Reasoning failed: {reason}",
            status_code=500,
            details={"query_preview": query[:100] if query else "", "reason": reason},
        )

    @staticmethod
    def internal_error(message: str = "An unexpected error occurred") -> KGError:
        """Internal server error."""
        return KGError(
            error_type=KGErrorType.INTERNAL_ERROR,
            message=message,
            status_code=500,
        )


class KGErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling KG errors with structured responses."""

    def __init__(self, app: Any, include_stack_trace: bool = False) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            include_stack_trace: Whether to include stack traces in responses (dev only)
        """
        super().__init__(app)
        self._include_stack_trace = include_stack_trace

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle errors.

        Args:
            request: The incoming request
            call_next: The next middleware/handler

        Returns:
            Response with structured error if an error occurred
        """
        # Generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

        # Check if this is a KG endpoint
        if not self._is_kg_endpoint(request.url.path):
            return await call_next(request)

        try:
            response = await call_next(request)

            # Add correlation ID to response
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except KGError as e:
            e.correlation_id = correlation_id
            return self._create_error_response(e, correlation_id)

        except HTTPException as e:
            # Convert HTTPException to KGError
            kg_error = KGError(
                error_type=self._classify_http_error(e.status_code),
                message=str(e.detail),
                status_code=e.status_code,
                correlation_id=correlation_id,
            )
            return self._create_error_response(kg_error, correlation_id)

        except Exception as e:
            logger.exception(f"Unhandled exception in KG endpoint: {e}")

            kg_error = KGError(
                error_type=KGErrorType.INTERNAL_ERROR,
                message="An unexpected error occurred",
                status_code=500,
                correlation_id=correlation_id,
            )

            if self._include_stack_trace:
                kg_error.details["stack_trace"] = traceback.format_exc()

            return self._create_error_response(kg_error, correlation_id)

    def _is_kg_endpoint(self, path: str) -> bool:
        """Check if the path is a KG endpoint."""
        kg_prefixes = [
            "/api/v1/kg/",
            "/api/v1/graph/",
            "/api/v1/graph-rag/",
            "/api/v1/concepts/",
            "/api/v1/reasoning/",
        ]
        return any(path.startswith(prefix) for prefix in kg_prefixes)

    def _classify_http_error(self, status_code: int) -> KGErrorType:
        """Classify HTTP error code to KGErrorType."""
        if status_code == 400:
            return KGErrorType.VALIDATION_ERROR
        elif status_code == 401:
            return KGErrorType.AUTHENTICATION_ERROR
        elif status_code == 403:
            return KGErrorType.AUTHORIZATION_ERROR
        elif status_code == 404:
            return KGErrorType.NOT_FOUND
        elif status_code == 429:
            return KGErrorType.RATE_LIMITED
        elif status_code == 503:
            return KGErrorType.SERVICE_UNAVAILABLE
        elif status_code == 504:
            return KGErrorType.TIMEOUT_ERROR
        else:
            return KGErrorType.INTERNAL_ERROR

    def _create_error_response(
        self,
        error: KGError,
        correlation_id: str
    ) -> JSONResponse:
        """Create a JSON error response.

        Args:
            error: The KG error
            correlation_id: Request correlation ID

        Returns:
            JSONResponse with error details
        """
        headers = {"X-Correlation-ID": correlation_id}

        if error.retryable and error.retry_after_seconds:
            headers["Retry-After"] = str(error.retry_after_seconds)

        return JSONResponse(
            status_code=error.status_code,
            content=error.to_dict(),
            headers=headers,
        )


def handle_kg_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to handle KG errors in route handlers.

    Converts common exceptions to KGError for consistent error handling.

    Usage:
        @router.get("/concept/{cui}")
        @handle_kg_errors
        async def get_concept(cui: str) -> dict:
            ...
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        except KGError:
            # Re-raise KGError as-is
            raise
        except HTTPException:
            # Let HTTPException propagate
            raise
        except ValueError as e:
            raise KGErrors.validation_error("input", str(e))
        except TimeoutError as e:
            raise KGErrors.timeout_error("operation", 30.0)
        except ConnectionError as e:
            raise KGErrors.connection_error("external_service", str(e))
        except Exception as e:
            logger.exception(f"Unhandled error in KG handler: {e}")
            raise KGErrors.internal_error(str(e))

    return wrapper


def validate_cui(cui: str) -> str:
    """Validate and normalize a CUI.

    Args:
        cui: The CUI to validate

    Returns:
        Normalized CUI (uppercase)

    Raises:
        KGError: If the CUI is invalid
    """
    if not cui:
        raise KGErrors.invalid_cui(cui, "CUI cannot be empty")

    cui = cui.strip().upper()

    # Basic CUI format validation (C followed by 7 digits)
    if not cui.startswith("C") or len(cui) != 8:
        raise KGErrors.invalid_cui(cui, "CUI must be in format CXXXXXXX (C followed by 7 digits)")

    if not cui[1:].isdigit():
        raise KGErrors.invalid_cui(cui, "CUI digits portion must be numeric")

    return cui


def validate_patient_id(patient_id: str) -> str:
    """Validate a patient ID.

    Args:
        patient_id: The patient ID to validate

    Returns:
        Normalized patient ID

    Raises:
        KGError: If the patient ID is invalid
    """
    if not patient_id:
        raise KGErrors.validation_error("patient_id", "Patient ID cannot be empty")

    patient_id = patient_id.strip()

    if len(patient_id) < 3 or len(patient_id) > 50:
        raise KGErrors.validation_error(
            "patient_id",
            "Patient ID must be between 3 and 50 characters",
            patient_id
        )

    return patient_id


def validate_max_hops(max_hops: int, min_value: int = 1, max_value: int = 10) -> int:
    """Validate max_hops parameter.

    Args:
        max_hops: The max_hops value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Validated max_hops value

    Raises:
        KGError: If max_hops is out of range
    """
    if max_hops < min_value or max_hops > max_value:
        raise KGErrors.validation_error(
            "max_hops",
            f"max_hops must be between {min_value} and {max_value}",
            max_hops
        )

    return max_hops
