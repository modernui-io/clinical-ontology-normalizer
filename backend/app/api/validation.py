"""Input validation middleware and dependencies for Clinical Ontology Normalizer API.

Provides:
- Validation dependency that catches Pydantic ValidationError and returns field-level errors
- Custom validators for common clinical data patterns
- Reusable validation utilities for patient_id, UUID, date ranges

Usage:
    from app.api.validation import (
        validate_patient_id_param,
        validate_uuid_param,
        validate_date_range_params,
        ValidatedPatientId,
        ValidatedUUID,
    )

    @router.get("/patients/{patient_id}")
    async def get_patient(
        patient_id: ValidatedPatientId,
    ) -> dict:
        ...
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, Field

from app.api.errors import (
    ErrorCode,
    ErrorDetail,
    ValidationError,
)


# ============================================================================
# Validation Patterns
# ============================================================================

PATIENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
ICD10_PATTERN = re.compile(r"^[A-TV-Z]\d{2}(?:\.\d{1,4}[A-Z]?)?$", re.IGNORECASE)
SNOMED_PATTERN = re.compile(r"^\d{6,18}$")
CPT_PATTERN = re.compile(r"^\d{5}$")


# ============================================================================
# Field-Level Error Helpers
# ============================================================================


def field_error(
    field: str,
    message: str,
    value: Any = None,
    code: ErrorCode = ErrorCode.VALIDATION_ERROR,
) -> ErrorDetail:
    """Create a field-level validation error detail.

    Args:
        field: Name of the invalid field.
        message: Human-readable error message.
        value: The invalid value (will be included in response).
        code: Specific error code.

    Returns:
        ErrorDetail for the field.
    """
    return ErrorDetail(
        field=field,
        message=message,
        value=str(value)[:100] if value is not None else None,
        code=code.value,
    )


def raise_validation_error(
    message: str,
    errors: list[ErrorDetail],
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
) -> None:
    """Raise a ValidationError with field-level details.

    Args:
        message: Summary error message.
        errors: List of field-level error details.
        error_code: Overall error code.

    Raises:
        ValidationError with the provided details.
    """
    raise ValidationError(
        message=message,
        error_code=error_code,
        details=errors,
    )


# ============================================================================
# Parameter Validators (FastAPI Dependencies)
# ============================================================================


def validate_patient_id_param(patient_id: str) -> str:
    """Validate a patient_id path or query parameter.

    Args:
        patient_id: The patient ID to validate.

    Returns:
        The validated patient_id.

    Raises:
        ValidationError: If format is invalid.
    """
    if not patient_id:
        raise ValidationError(
            message="Patient ID is required",
            error_code=ErrorCode.VALIDATION_INVALID_PATIENT_ID,
            details=[field_error("patient_id", "Patient ID cannot be empty")],
        )

    if not PATIENT_ID_PATTERN.match(patient_id):
        raise ValidationError(
            message="Invalid patient ID format",
            error_code=ErrorCode.VALIDATION_INVALID_PATIENT_ID,
            details=[
                field_error(
                    "patient_id",
                    "Patient ID must be 1-64 alphanumeric characters with optional hyphens/underscores",
                    value=patient_id,
                )
            ],
        )

    return patient_id


def validate_uuid_param(id: str) -> str:
    """Validate a UUID path or query parameter.

    Args:
        id: The UUID string to validate.

    Returns:
        The validated UUID string.

    Raises:
        ValidationError: If format is invalid.
    """
    if not id:
        raise ValidationError(
            message="ID is required",
            error_code=ErrorCode.VALIDATION_INVALID_UUID,
            details=[field_error("id", "ID cannot be empty")],
        )

    if not UUID_PATTERN.match(id):
        raise ValidationError(
            message="Invalid UUID format",
            error_code=ErrorCode.VALIDATION_INVALID_UUID,
            details=[
                field_error(
                    "id",
                    "ID must be a valid UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)",
                    value=id,
                )
            ],
        )

    return id


def validate_date_range_params(
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date | None, date | None]:
    """Validate a date range (start must be before end).

    Args:
        start_date: Optional start date.
        end_date: Optional end date.

    Returns:
        Tuple of (start_date, end_date).

    Raises:
        ValidationError: If start is after end.
    """
    if start_date and end_date and start_date > end_date:
        raise ValidationError(
            message="Invalid date range: start_date must be before end_date",
            error_code=ErrorCode.VALIDATION_INVALID_DATE_RANGE,
            details=[
                field_error(
                    "start_date",
                    f"start_date ({start_date}) must be before end_date ({end_date})",
                    value=str(start_date),
                ),
                field_error(
                    "end_date",
                    f"end_date ({end_date}) must be after start_date ({start_date})",
                    value=str(end_date),
                ),
            ],
        )

    return start_date, end_date


def validate_icd10_param(code: str) -> str:
    """Validate an ICD-10 code parameter.

    Args:
        code: The ICD-10 code to validate.

    Returns:
        The normalized (uppercase) code.

    Raises:
        ValidationError: If format is invalid.
    """
    normalized = code.strip().upper()
    if not ICD10_PATTERN.match(normalized):
        raise ValidationError(
            message="Invalid ICD-10 code format",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
            details=[
                field_error(
                    "code",
                    "ICD-10 codes must match format: Letter + 2 digits + optional decimal (e.g., E11.9, J45.20)",
                    value=code,
                )
            ],
        )
    return normalized


def validate_snomed_param(code: str) -> str:
    """Validate a SNOMED CT code parameter.

    Args:
        code: The SNOMED code to validate.

    Returns:
        The validated code.

    Raises:
        ValidationError: If format is invalid.
    """
    if not SNOMED_PATTERN.match(code.strip()):
        raise ValidationError(
            message="Invalid SNOMED CT code format",
            error_code=ErrorCode.VALIDATION_INVALID_SNOMED_CODE,
            details=[
                field_error(
                    "code",
                    "SNOMED CT codes must be 6-18 digit numeric identifiers",
                    value=code,
                )
            ],
        )
    return code.strip()


def validate_pagination_params(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=1000, description="Maximum records to return"),
) -> tuple[int, int]:
    """Validate pagination parameters.

    Args:
        offset: Number of records to skip.
        limit: Maximum number of records to return.

    Returns:
        Tuple of (offset, limit).
    """
    return offset, limit


# ============================================================================
# Annotated Types for Use in Endpoint Signatures
# ============================================================================

ValidatedPatientId = Annotated[str, Depends(validate_patient_id_param)]
ValidatedUUID = Annotated[str, Depends(validate_uuid_param)]


# ============================================================================
# Request Body Validation Models
# ============================================================================


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    offset: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=1000, description="Maximum records to return")


class DateRangeParams(BaseModel):
    """Date range filter parameters."""

    start_date: date | None = Field(None, description="Start date (inclusive)")
    end_date: date | None = Field(None, description="End date (inclusive)")

    def model_post_init(self, __context: Any) -> None:
        """Validate date range after model creation."""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(
                message="Invalid date range: start_date must be before end_date",
                error_code=ErrorCode.VALIDATION_INVALID_DATE_RANGE,
                details=[
                    field_error(
                        "start_date",
                        f"start_date ({self.start_date}) must be before end_date ({self.end_date})",
                        value=str(self.start_date),
                    )
                ],
            )
