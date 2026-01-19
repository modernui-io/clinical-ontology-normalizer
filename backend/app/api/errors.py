"""Custom exception classes and standardized error responses for Clinical Ontology Normalizer API.

This module provides:
- Custom exception classes for different error types
- Standardized error response models
- Error codes enumeration for all API errors
- Helper functions for creating error responses

Usage:
    from app.api.errors import NotFoundError, ValidationError, ErrorCode

    # Raise a custom exception
    raise NotFoundError(
        message="Document not found",
        error_code=ErrorCode.DOCUMENT_NOT_FOUND,
        details={"document_id": doc_id}
    )
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Error Codes Enum
# ============================================================================


class ErrorCode(str, Enum):
    """Enumeration of all API error codes.

    Error codes follow the pattern: CATEGORY_SPECIFIC_ERROR
    Categories:
    - VALIDATION_*: Input validation errors (400)
    - AUTH_*: Authentication errors (401)
    - FORBIDDEN_*: Authorization errors (403)
    - NOT_FOUND_*: Resource not found errors (404)
    - CONFLICT_*: Resource conflict errors (409)
    - RATE_LIMIT_*: Rate limiting errors (429)
    - INTERNAL_*: Internal server errors (500)
    - SERVICE_*: External service errors (502/503)
    """

    # Validation Errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    VALIDATION_MISSING_FIELD = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_VALUE = "VALIDATION_INVALID_VALUE"
    VALIDATION_TEXT_TOO_LONG = "VALIDATION_TEXT_TOO_LONG"
    VALIDATION_TEXT_TOO_SHORT = "VALIDATION_TEXT_TOO_SHORT"
    VALIDATION_INVALID_ICD10_CODE = "VALIDATION_INVALID_ICD10_CODE"
    VALIDATION_INVALID_SNOMED_CODE = "VALIDATION_INVALID_SNOMED_CODE"
    VALIDATION_INVALID_CPT_CODE = "VALIDATION_INVALID_CPT_CODE"
    VALIDATION_INVALID_DATE_RANGE = "VALIDATION_INVALID_DATE_RANGE"
    VALIDATION_INVALID_UUID = "VALIDATION_INVALID_UUID"
    VALIDATION_INVALID_PATIENT_ID = "VALIDATION_INVALID_PATIENT_ID"
    VALIDATION_BATCH_SIZE_EXCEEDED = "VALIDATION_BATCH_SIZE_EXCEEDED"

    # Authentication Errors (401)
    AUTH_MISSING_TOKEN = "AUTH_MISSING_TOKEN"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"

    # Authorization Errors (403)
    FORBIDDEN_INSUFFICIENT_PERMISSIONS = "FORBIDDEN_INSUFFICIENT_PERMISSIONS"
    FORBIDDEN_RESOURCE_ACCESS_DENIED = "FORBIDDEN_RESOURCE_ACCESS_DENIED"

    # Not Found Errors (404)
    NOT_FOUND_RESOURCE = "NOT_FOUND_RESOURCE"
    NOT_FOUND_DOCUMENT = "NOT_FOUND_DOCUMENT"
    NOT_FOUND_PATIENT = "NOT_FOUND_PATIENT"
    NOT_FOUND_JOB = "NOT_FOUND_JOB"
    NOT_FOUND_CONCEPT = "NOT_FOUND_CONCEPT"
    NOT_FOUND_MENTION = "NOT_FOUND_MENTION"
    NOT_FOUND_ENDPOINT = "NOT_FOUND_ENDPOINT"

    # Conflict Errors (409)
    CONFLICT_RESOURCE_EXISTS = "CONFLICT_RESOURCE_EXISTS"
    CONFLICT_DOCUMENT_EXISTS = "CONFLICT_DOCUMENT_EXISTS"
    CONFLICT_CONCURRENT_MODIFICATION = "CONFLICT_CONCURRENT_MODIFICATION"
    CONFLICT_JOB_ALREADY_PROCESSING = "CONFLICT_JOB_ALREADY_PROCESSING"

    # Rate Limit Errors (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RATE_LIMIT_BURST = "RATE_LIMIT_BURST"
    RATE_LIMIT_DAILY_QUOTA = "RATE_LIMIT_DAILY_QUOTA"

    # Internal Errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INTERNAL_DATABASE_ERROR = "INTERNAL_DATABASE_ERROR"
    INTERNAL_PROCESSING_ERROR = "INTERNAL_PROCESSING_ERROR"
    INTERNAL_NLP_ERROR = "INTERNAL_NLP_ERROR"
    INTERNAL_MAPPING_ERROR = "INTERNAL_MAPPING_ERROR"

    # External Service Errors (502/503)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    SERVICE_DATABASE_UNAVAILABLE = "SERVICE_DATABASE_UNAVAILABLE"
    SERVICE_REDIS_UNAVAILABLE = "SERVICE_REDIS_UNAVAILABLE"
    SERVICE_NLP_UNAVAILABLE = "SERVICE_NLP_UNAVAILABLE"
    SERVICE_TIMEOUT = "SERVICE_TIMEOUT"


# ============================================================================
# Error Response Models
# ============================================================================


class ErrorDetail(BaseModel):
    """Detailed information about a specific error."""

    field: str | None = Field(None, description="Field that caused the error (for validation errors)")
    message: str = Field(..., description="Human-readable error message")
    code: str | None = Field(None, description="Specific error sub-code")
    value: Any = Field(None, description="The invalid value (sanitized)")


class ErrorResponse(BaseModel):
    """Standardized API error response.

    All API errors return this structure for consistent error handling.

    Example:
        {
            "error_code": "NOT_FOUND_DOCUMENT",
            "message": "Document with ID abc123 not found",
            "details": [{"field": "document_id", "message": "Document does not exist"}],
            "request_id": "req-xyz789",
            "timestamp": "2024-01-15T10:30:00Z",
            "path": "/api/documents/abc123"
        }
    """

    error_code: ErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: list[ErrorDetail] = Field(
        default_factory=list,
        description="Additional error details (e.g., validation errors for specific fields)"
    )
    request_id: str | None = Field(None, description="Request ID for tracing")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 timestamp of when the error occurred"
    )
    path: str | None = Field(None, description="Request path that caused the error")
    documentation_url: str | None = Field(
        None,
        description="URL to documentation for this error"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "NOT_FOUND_DOCUMENT",
                "message": "Document with ID abc123 not found",
                "details": [],
                "request_id": "req-xyz789",
                "timestamp": "2024-01-15T10:30:00Z",
                "path": "/api/documents/abc123",
            }
        }


# ============================================================================
# Custom Exception Classes
# ============================================================================


class APIError(Exception):
    """Base exception class for all API errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code from ErrorCode enum
        status_code: HTTP status code
        details: Additional error details
        headers: Optional headers to include in response
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = 500,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or []
        self.headers = headers
        super().__init__(message)

    def to_response(self, request_id: str | None = None, path: str | None = None) -> ErrorResponse:
        """Convert exception to ErrorResponse model."""
        return ErrorResponse(
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            request_id=request_id,
            path=path,
        )


class ValidationError(APIError):
    """Exception raised for input validation errors (HTTP 400).

    Use this for:
    - Invalid field formats
    - Missing required fields
    - Values outside allowed ranges
    - Invalid code formats (ICD-10, SNOMED, etc.)

    Example:
        raise ValidationError(
            message="Invalid ICD-10 code format",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
            details=[ErrorDetail(field="code", message="Code must match pattern A00-Z99")]
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details,
            headers=headers,
        )


class NotFoundError(APIError):
    """Exception raised when a resource is not found (HTTP 404).

    Use this for:
    - Document not found
    - Patient not found
    - Job not found
    - Concept not found

    Example:
        raise NotFoundError(
            message=f"Document {doc_id} not found",
            error_code=ErrorCode.NOT_FOUND_DOCUMENT
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.NOT_FOUND_RESOURCE,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=404,
            details=details,
            headers=headers,
        )


class ConflictError(APIError):
    """Exception raised for resource conflicts (HTTP 409).

    Use this for:
    - Resource already exists
    - Concurrent modification detected
    - Job already processing

    Example:
        raise ConflictError(
            message="Document already exists",
            error_code=ErrorCode.CONFLICT_DOCUMENT_EXISTS
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.CONFLICT_RESOURCE_EXISTS,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=409,
            details=details,
            headers=headers,
        )


class AuthenticationError(APIError):
    """Exception raised for authentication failures (HTTP 401).

    Use this for:
    - Missing authentication token
    - Invalid token
    - Expired token

    Example:
        raise AuthenticationError(
            message="Invalid or expired token",
            error_code=ErrorCode.AUTH_INVALID_TOKEN
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.AUTH_INVALID_TOKEN,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        # Add WWW-Authenticate header for 401 responses
        if headers is None:
            headers = {}
        headers.setdefault("WWW-Authenticate", "Bearer")

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=401,
            details=details,
            headers=headers,
        )


class AuthorizationError(APIError):
    """Exception raised for authorization failures (HTTP 403).

    Use this for:
    - Insufficient permissions
    - Resource access denied

    Example:
        raise AuthorizationError(
            message="You do not have permission to access this resource",
            error_code=ErrorCode.FORBIDDEN_RESOURCE_ACCESS_DENIED
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.FORBIDDEN_INSUFFICIENT_PERMISSIONS,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=403,
            details=details,
            headers=headers,
        )


class RateLimitError(APIError):
    """Exception raised when rate limits are exceeded (HTTP 429).

    Use this for:
    - Request rate limit exceeded
    - Burst limit exceeded
    - Daily quota exceeded

    Example:
        raise RateLimitError(
            message="Rate limit exceeded. Try again in 60 seconds.",
            retry_after=60
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.RATE_LIMIT_EXCEEDED,
        details: list[ErrorDetail] | None = None,
        retry_after: int | None = None,
        headers: dict[str, str] | None = None,
    ):
        if headers is None:
            headers = {}

        # Add Retry-After header
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=429,
            details=details,
            headers=headers,
        )

        self.retry_after = retry_after


class InternalError(APIError):
    """Exception raised for internal server errors (HTTP 500).

    Use this for:
    - Database errors
    - Unexpected processing failures
    - NLP service failures

    Example:
        raise InternalError(
            message="An unexpected error occurred while processing your request",
            error_code=ErrorCode.INTERNAL_PROCESSING_ERROR
        )
    """

    def __init__(
        self,
        message: str = "An internal error occurred",
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details,
            headers=headers,
        )


class ServiceUnavailableError(APIError):
    """Exception raised when external services are unavailable (HTTP 503).

    Use this for:
    - Database connection failures
    - Redis unavailable
    - External API failures

    Example:
        raise ServiceUnavailableError(
            message="Database is temporarily unavailable",
            error_code=ErrorCode.SERVICE_DATABASE_UNAVAILABLE,
            retry_after=30
        )
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE,
        details: list[ErrorDetail] | None = None,
        retry_after: int | None = None,
        headers: dict[str, str] | None = None,
    ):
        if headers is None:
            headers = {}

        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=503,
            details=details,
            headers=headers,
        )

        self.retry_after = retry_after


# ============================================================================
# Helper Functions
# ============================================================================


def create_validation_error(
    message: str,
    field: str | None = None,
    value: Any = None,
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
) -> ValidationError:
    """Create a validation error with a single field detail.

    Args:
        message: Human-readable error message
        field: The field that caused the error
        value: The invalid value (will be sanitized)
        error_code: Specific validation error code

    Returns:
        ValidationError with the specified details
    """
    details = []
    if field:
        # Sanitize value to avoid exposing sensitive data
        sanitized_value = _sanitize_value(value)
        details.append(ErrorDetail(
            field=field,
            message=message,
            value=sanitized_value,
        ))

    return ValidationError(
        message=message,
        error_code=error_code,
        details=details,
    )


def create_not_found_error(
    resource_type: str,
    resource_id: str,
    error_code: ErrorCode | None = None,
) -> NotFoundError:
    """Create a not found error for a specific resource.

    Args:
        resource_type: Type of resource (e.g., "Document", "Patient")
        resource_id: ID of the resource
        error_code: Specific not found error code (auto-detected if None)

    Returns:
        NotFoundError with appropriate message and code
    """
    if error_code is None:
        # Auto-detect error code based on resource type
        resource_codes = {
            "document": ErrorCode.NOT_FOUND_DOCUMENT,
            "patient": ErrorCode.NOT_FOUND_PATIENT,
            "job": ErrorCode.NOT_FOUND_JOB,
            "concept": ErrorCode.NOT_FOUND_CONCEPT,
            "mention": ErrorCode.NOT_FOUND_MENTION,
        }
        error_code = resource_codes.get(resource_type.lower(), ErrorCode.NOT_FOUND_RESOURCE)

    return NotFoundError(
        message=f"{resource_type} with ID '{resource_id}' not found",
        error_code=error_code,
    )


def _sanitize_value(value: Any) -> Any:
    """Sanitize a value to avoid exposing sensitive data in error responses.

    Truncates long strings and masks potential PII/PHI patterns.
    """
    if value is None:
        return None

    if isinstance(value, str):
        # Truncate long strings
        if len(value) > 100:
            return value[:97] + "..."

        # Mask potential SSN patterns
        import re
        value = re.sub(r'\d{3}-\d{2}-\d{4}', '***-**-****', value)

        # Mask potential MRN patterns (varies by institution)
        value = re.sub(r'\b[A-Z]{2,3}\d{6,10}\b', '[REDACTED]', value)

        return value

    if isinstance(value, (list, dict)):
        # Don't include complex structures in error messages
        return f"<{type(value).__name__}>"

    return value
