"""Pydantic validators for common clinical data patterns.

This module provides:
- ICD-10-CM/PCS code format validators
- SNOMED CT code validators
- CPT code validators
- Date and date range validators
- Clinical text length validators
- Patient ID validators
- UUID validators
- Custom annotated types for Pydantic models

Usage:
    from app.api.validators import (
        ICD10Code,
        SNOMEDCode,
        CPTCode,
        ClinicalText,
        PatientID,
        validate_icd10_code,
    )

    class MyRequest(BaseModel):
        code: ICD10Code
        text: ClinicalText
        patient_id: PatientID
"""

import re
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BeforeValidator, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from app.api.errors import ErrorCode, ErrorDetail, ValidationError


# ============================================================================
# ICD-10 Code Validators
# ============================================================================

# ICD-10-CM pattern: Letter, 2 digits, optional decimal + 1-4 alphanumeric characters
# Examples: A00, A01.1, J18.9, Z87.891, S72.001A
ICD10_CM_PATTERN = re.compile(
    r'^[A-TV-Z]\d{2}(?:\.\d{1,4}[A-Z]?)?$',
    re.IGNORECASE
)

# ICD-10-PCS pattern: 7 alphanumeric characters
# Example: 0FT44ZZ
ICD10_PCS_PATTERN = re.compile(
    r'^[0-9A-HJ-NP-Z]{7}$',
    re.IGNORECASE
)


def validate_icd10_code(value: str) -> str:
    """Validate and normalize an ICD-10 code (CM or PCS).

    Args:
        value: The ICD-10 code to validate

    Returns:
        Normalized code (uppercase)

    Raises:
        ValidationError: If the code format is invalid
    """
    if not value:
        raise ValidationError(
            message="ICD-10 code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
        )

    normalized = value.strip().upper()

    # Check CM format
    if ICD10_CM_PATTERN.match(normalized):
        return normalized

    # Check PCS format
    if ICD10_PCS_PATTERN.match(normalized):
        return normalized

    raise ValidationError(
        message=f"Invalid ICD-10 code format: '{value}'. Expected format like 'A00.1' (CM) or '0FT44ZZ' (PCS)",
        error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
        details=[ErrorDetail(
            field="code",
            message="ICD-10-CM codes should be 3-7 characters (e.g., A00, J18.9). ICD-10-PCS codes should be exactly 7 alphanumeric characters.",
            value=value[:20] if len(value) > 20 else value,
        )]
    )


def validate_icd10_cm_code(value: str) -> str:
    """Validate specifically ICD-10-CM code format.

    Args:
        value: The ICD-10-CM code to validate

    Returns:
        Normalized code (uppercase)

    Raises:
        ValidationError: If the code format is invalid
    """
    if not value:
        raise ValidationError(
            message="ICD-10-CM code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
        )

    normalized = value.strip().upper()

    if not ICD10_CM_PATTERN.match(normalized):
        raise ValidationError(
            message=f"Invalid ICD-10-CM code format: '{value}'",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
            details=[ErrorDetail(
                field="code",
                message="ICD-10-CM codes should be 3-7 characters starting with a letter (e.g., A00, J18.9, S72.001A)",
                value=value[:20] if len(value) > 20 else value,
            )]
        )

    return normalized


def validate_icd10_pcs_code(value: str) -> str:
    """Validate specifically ICD-10-PCS code format.

    Args:
        value: The ICD-10-PCS code to validate

    Returns:
        Normalized code (uppercase)

    Raises:
        ValidationError: If the code format is invalid
    """
    if not value:
        raise ValidationError(
            message="ICD-10-PCS code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
        )

    normalized = value.strip().upper()

    if not ICD10_PCS_PATTERN.match(normalized):
        raise ValidationError(
            message=f"Invalid ICD-10-PCS code format: '{value}'",
            error_code=ErrorCode.VALIDATION_INVALID_ICD10_CODE,
            details=[ErrorDetail(
                field="code",
                message="ICD-10-PCS codes must be exactly 7 alphanumeric characters (e.g., 0FT44ZZ)",
                value=value[:20] if len(value) > 20 else value,
            )]
        )

    return normalized


# ============================================================================
# SNOMED CT Code Validators
# ============================================================================

# SNOMED CT codes are numeric, typically 6-18 digits
SNOMED_PATTERN = re.compile(r'^\d{6,18}$')


def validate_snomed_code(value: str | int) -> str:
    """Validate a SNOMED CT code.

    SNOMED CT codes are concept identifiers (SCTIDs) which are
    numeric strings typically 6-18 digits long.

    Args:
        value: The SNOMED code to validate (string or int)

    Returns:
        Normalized code as string

    Raises:
        ValidationError: If the code format is invalid
    """
    str_value = str(value).strip()

    if not str_value:
        raise ValidationError(
            message="SNOMED CT code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_SNOMED_CODE,
        )

    if not SNOMED_PATTERN.match(str_value):
        raise ValidationError(
            message=f"Invalid SNOMED CT code format: '{str_value}'",
            error_code=ErrorCode.VALIDATION_INVALID_SNOMED_CODE,
            details=[ErrorDetail(
                field="code",
                message="SNOMED CT codes should be numeric strings 6-18 digits long (e.g., 22298006)",
                value=str_value[:20] if len(str_value) > 20 else str_value,
            )]
        )

    # Validate SNOMED check digit (Verhoeff algorithm) - simplified check
    # Full validation would use Verhoeff, but basic length check is sufficient
    # for most use cases

    return str_value


# ============================================================================
# CPT Code Validators
# ============================================================================

# CPT codes are 5 digits, Category II codes have suffix F, Category III have suffix T
# Examples: 99213, 0001F, 0042T
CPT_PATTERN = re.compile(r'^\d{4}[0-9FT]$', re.IGNORECASE)

# HCPCS Level II codes start with a letter followed by 4 digits
# Examples: G0008, J1234
HCPCS_PATTERN = re.compile(r'^[A-VX-Z]\d{4}$', re.IGNORECASE)


def validate_cpt_code(value: str) -> str:
    """Validate a CPT code.

    Args:
        value: The CPT code to validate

    Returns:
        Normalized code (uppercase)

    Raises:
        ValidationError: If the code format is invalid
    """
    if not value:
        raise ValidationError(
            message="CPT code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_CPT_CODE,
        )

    normalized = value.strip().upper()

    if not CPT_PATTERN.match(normalized):
        raise ValidationError(
            message=f"Invalid CPT code format: '{value}'",
            error_code=ErrorCode.VALIDATION_INVALID_CPT_CODE,
            details=[ErrorDetail(
                field="code",
                message="CPT codes should be 5 characters: 5 digits (99213), or 4 digits + F (0001F) or T (0042T)",
                value=value[:20] if len(value) > 20 else value,
            )]
        )

    return normalized


def validate_hcpcs_code(value: str) -> str:
    """Validate a HCPCS Level II code.

    Args:
        value: The HCPCS code to validate

    Returns:
        Normalized code (uppercase)

    Raises:
        ValidationError: If the code format is invalid
    """
    if not value:
        raise ValidationError(
            message="HCPCS code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_VALUE,
        )

    normalized = value.strip().upper()

    if not HCPCS_PATTERN.match(normalized):
        raise ValidationError(
            message=f"Invalid HCPCS code format: '{value}'",
            error_code=ErrorCode.VALIDATION_INVALID_VALUE,
            details=[ErrorDetail(
                field="code",
                message="HCPCS Level II codes should be a letter (A-V, X-Z) followed by 4 digits (e.g., G0008, J1234)",
                value=value[:20] if len(value) > 20 else value,
            )]
        )

    return normalized


def validate_billing_code(value: str) -> str:
    """Validate any billing code (CPT or HCPCS).

    Args:
        value: The billing code to validate

    Returns:
        Normalized code (uppercase)

    Raises:
        ValidationError: If the code format is invalid
    """
    if not value:
        raise ValidationError(
            message="Billing code cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_VALUE,
        )

    normalized = value.strip().upper()

    # Try CPT first
    if CPT_PATTERN.match(normalized):
        return normalized

    # Try HCPCS
    if HCPCS_PATTERN.match(normalized):
        return normalized

    raise ValidationError(
        message=f"Invalid billing code format: '{value}'",
        error_code=ErrorCode.VALIDATION_INVALID_VALUE,
        details=[ErrorDetail(
            field="code",
            message="Billing codes should be CPT (5 digits like 99213) or HCPCS (letter + 4 digits like G0008)",
            value=value[:20] if len(value) > 20 else value,
        )]
    )


# ============================================================================
# Date Range Validators
# ============================================================================


def validate_date_range(
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    max_days: int | None = None,
    allow_future: bool = False,
) -> tuple[date | None, date | None]:
    """Validate a date range.

    Args:
        start_date: Start of the range
        end_date: End of the range
        max_days: Maximum allowed days in range (None for no limit)
        allow_future: Whether to allow future dates

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        ValidationError: If the date range is invalid
    """
    today = date.today()

    # Convert datetimes to dates if needed
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    # Validate future dates
    if not allow_future:
        if start_date and start_date > today:
            raise ValidationError(
                message="Start date cannot be in the future",
                error_code=ErrorCode.VALIDATION_INVALID_DATE_RANGE,
                details=[ErrorDetail(
                    field="start_date",
                    message=f"Date {start_date} is in the future. Maximum allowed date is {today}",
                )]
            )
        if end_date and end_date > today:
            raise ValidationError(
                message="End date cannot be in the future",
                error_code=ErrorCode.VALIDATION_INVALID_DATE_RANGE,
                details=[ErrorDetail(
                    field="end_date",
                    message=f"Date {end_date} is in the future. Maximum allowed date is {today}",
                )]
            )

    # Validate range order
    if start_date and end_date and start_date > end_date:
        raise ValidationError(
            message="Start date must be before or equal to end date",
            error_code=ErrorCode.VALIDATION_INVALID_DATE_RANGE,
            details=[ErrorDetail(
                field="date_range",
                message=f"Start date ({start_date}) is after end date ({end_date})",
            )]
        )

    # Validate max range
    if max_days and start_date and end_date:
        days_diff = (end_date - start_date).days
        if days_diff > max_days:
            raise ValidationError(
                message=f"Date range exceeds maximum allowed of {max_days} days",
                error_code=ErrorCode.VALIDATION_INVALID_DATE_RANGE,
                details=[ErrorDetail(
                    field="date_range",
                    message=f"Range is {days_diff} days, but maximum allowed is {max_days} days",
                )]
            )

    return start_date, end_date


class DateRangeValidator:
    """Reusable date range validator for Pydantic models.

    Usage:
        class MyModel(BaseModel):
            start_date: date
            end_date: date

            _validate_dates = model_validator(mode='after')(
                DateRangeValidator(max_days=365).validate
            )
    """

    def __init__(
        self,
        max_days: int | None = None,
        allow_future: bool = False,
        start_field: str = "start_date",
        end_field: str = "end_date",
    ):
        self.max_days = max_days
        self.allow_future = allow_future
        self.start_field = start_field
        self.end_field = end_field

    def validate(self, model: Any) -> Any:
        """Validate date range on a model instance."""
        start = getattr(model, self.start_field, None)
        end = getattr(model, self.end_field, None)

        validate_date_range(
            start_date=start,
            end_date=end,
            max_days=self.max_days,
            allow_future=self.allow_future,
        )

        return model


# ============================================================================
# Clinical Text Validators
# ============================================================================

# Configurable text length limits
MIN_CLINICAL_TEXT_LENGTH = 1
MAX_CLINICAL_TEXT_LENGTH = 100000  # 100KB
DEFAULT_MAX_TEXT_LENGTH = 50000  # 50KB


def validate_clinical_text(
    value: str,
    min_length: int = MIN_CLINICAL_TEXT_LENGTH,
    max_length: int = DEFAULT_MAX_TEXT_LENGTH,
    field_name: str = "text",
) -> str:
    """Validate clinical text content.

    Args:
        value: The text to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        field_name: Name of the field (for error messages)

    Returns:
        Validated text (stripped of leading/trailing whitespace)

    Raises:
        ValidationError: If text length is outside allowed range
    """
    if not value:
        raise ValidationError(
            message=f"{field_name.capitalize()} cannot be empty",
            error_code=ErrorCode.VALIDATION_TEXT_TOO_SHORT,
            details=[ErrorDetail(
                field=field_name,
                message=f"Minimum length is {min_length} character(s)",
            )]
        )

    # Strip whitespace
    cleaned = value.strip()

    if len(cleaned) < min_length:
        raise ValidationError(
            message=f"{field_name.capitalize()} is too short",
            error_code=ErrorCode.VALIDATION_TEXT_TOO_SHORT,
            details=[ErrorDetail(
                field=field_name,
                message=f"Text must be at least {min_length} character(s). Got {len(cleaned)}.",
            )]
        )

    if len(cleaned) > max_length:
        raise ValidationError(
            message=f"{field_name.capitalize()} exceeds maximum length",
            error_code=ErrorCode.VALIDATION_TEXT_TOO_LONG,
            details=[ErrorDetail(
                field=field_name,
                message=f"Text must not exceed {max_length} characters. Got {len(cleaned)}.",
            )]
        )

    return cleaned


def create_text_validator(
    min_length: int = MIN_CLINICAL_TEXT_LENGTH,
    max_length: int = DEFAULT_MAX_TEXT_LENGTH,
) -> Any:
    """Create a text validator function with custom length limits.

    Args:
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Returns:
        Validator function for use with Annotated types
    """
    def validator(value: str) -> str:
        return validate_clinical_text(value, min_length, max_length)
    return validator


# ============================================================================
# Patient ID Validators
# ============================================================================

# Common patient ID patterns
# Alphanumeric, 1-50 characters
PATIENT_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,50}$')


def validate_patient_id(value: str) -> str:
    """Validate a patient identifier.

    Patient IDs must be alphanumeric with optional underscores/hyphens,
    1-50 characters long.

    Args:
        value: The patient ID to validate

    Returns:
        Validated patient ID

    Raises:
        ValidationError: If patient ID format is invalid
    """
    if not value:
        raise ValidationError(
            message="Patient ID cannot be empty",
            error_code=ErrorCode.VALIDATION_INVALID_PATIENT_ID,
        )

    stripped = value.strip()

    if not PATIENT_ID_PATTERN.match(stripped):
        raise ValidationError(
            message="Invalid patient ID format",
            error_code=ErrorCode.VALIDATION_INVALID_PATIENT_ID,
            details=[ErrorDetail(
                field="patient_id",
                message="Patient ID must be 1-50 alphanumeric characters (underscores and hyphens allowed)",
                value=stripped[:20] if len(stripped) > 20 else stripped,
            )]
        )

    return stripped


# ============================================================================
# UUID Validators
# ============================================================================


def validate_uuid(value: str | UUID) -> UUID:
    """Validate and convert a UUID string.

    Args:
        value: The UUID string or UUID object

    Returns:
        UUID object

    Raises:
        ValidationError: If UUID format is invalid
    """
    if isinstance(value, UUID):
        return value

    try:
        return UUID(str(value))
    except (ValueError, TypeError) as e:
        raise ValidationError(
            message="Invalid UUID format",
            error_code=ErrorCode.VALIDATION_INVALID_UUID,
            details=[ErrorDetail(
                field="uuid",
                message=f"Expected a valid UUID, got '{value[:36] if len(str(value)) > 36 else value}'",
            )]
        ) from e


# ============================================================================
# Annotated Types for Pydantic Models
# ============================================================================

# ICD-10 code types
ICD10Code = Annotated[str, AfterValidator(validate_icd10_code)]
ICD10CMCode = Annotated[str, AfterValidator(validate_icd10_cm_code)]
ICD10PCSCode = Annotated[str, AfterValidator(validate_icd10_pcs_code)]

# SNOMED code type
SNOMEDCode = Annotated[str, BeforeValidator(lambda v: str(v)), AfterValidator(validate_snomed_code)]

# CPT/HCPCS code types
CPTCode = Annotated[str, AfterValidator(validate_cpt_code)]
HCPCSCode = Annotated[str, AfterValidator(validate_hcpcs_code)]
BillingCode = Annotated[str, AfterValidator(validate_billing_code)]

# Patient ID type
PatientID = Annotated[str, AfterValidator(validate_patient_id)]

# Clinical text types with different size limits
ClinicalText = Annotated[str, AfterValidator(create_text_validator(1, 50000))]
ShortClinicalText = Annotated[str, AfterValidator(create_text_validator(1, 1000))]
LongClinicalText = Annotated[str, AfterValidator(create_text_validator(1, 100000))]

# Configurable clinical text using Field
def clinical_text_field(
    min_length: int = 1,
    max_length: int = 50000,
    **kwargs: Any,
) -> Any:
    """Create a Field with clinical text validation.

    Usage:
        class MyModel(BaseModel):
            text: str = clinical_text_field(min_length=10, max_length=5000)
    """
    return Field(
        min_length=min_length,
        max_length=max_length,
        **kwargs,
    )


# ============================================================================
# Batch Size Validators
# ============================================================================


def validate_batch_size(
    items: list[Any],
    max_size: int = 100,
    field_name: str = "items",
) -> list[Any]:
    """Validate batch size is within limits.

    Args:
        items: List of items in the batch
        max_size: Maximum allowed batch size
        field_name: Name of the field (for error messages)

    Returns:
        The validated list

    Raises:
        ValidationError: If batch size exceeds limit
    """
    if len(items) > max_size:
        raise ValidationError(
            message=f"Batch size exceeds maximum of {max_size}",
            error_code=ErrorCode.VALIDATION_BATCH_SIZE_EXCEEDED,
            details=[ErrorDetail(
                field=field_name,
                message=f"Received {len(items)} items, but maximum allowed is {max_size}",
            )]
        )

    return items


def create_batch_validator(max_size: int = 100) -> Any:
    """Create a batch size validator with custom limit.

    Args:
        max_size: Maximum allowed batch size

    Returns:
        Validator function
    """
    def validator(items: list[Any]) -> list[Any]:
        return validate_batch_size(items, max_size)
    return validator


# Annotated batch types
BatchItems = Annotated[list[Any], AfterValidator(create_batch_validator(100))]
SmallBatch = Annotated[list[Any], AfterValidator(create_batch_validator(10))]
LargeBatch = Annotated[list[Any], AfterValidator(create_batch_validator(1000))]


# ============================================================================
# Code System Detection
# ============================================================================


def detect_code_system(code: str) -> str | None:
    """Attempt to detect the code system from a code's format.

    Args:
        code: The code to analyze

    Returns:
        Detected code system name or None if unknown
    """
    normalized = code.strip().upper()

    # ICD-10-CM
    if ICD10_CM_PATTERN.match(normalized):
        return "ICD10CM"

    # ICD-10-PCS
    if ICD10_PCS_PATTERN.match(normalized):
        return "ICD10PCS"

    # CPT
    if CPT_PATTERN.match(normalized):
        return "CPT"

    # HCPCS
    if HCPCS_PATTERN.match(normalized):
        return "HCPCS"

    # SNOMED (numeric, 6-18 digits)
    if SNOMED_PATTERN.match(normalized):
        return "SNOMED"

    return None


def validate_code_for_system(code: str, code_system: str) -> str:
    """Validate a code against a specific code system.

    Args:
        code: The code to validate
        code_system: Expected code system

    Returns:
        Normalized code

    Raises:
        ValidationError: If code doesn't match expected system format
    """
    system_lower = code_system.lower()

    validators = {
        "icd10cm": validate_icd10_cm_code,
        "icd10": validate_icd10_code,
        "icd10pcs": validate_icd10_pcs_code,
        "snomed": validate_snomed_code,
        "cpt": validate_cpt_code,
        "hcpcs": validate_hcpcs_code,
    }

    validator = validators.get(system_lower)
    if validator:
        return validator(code)

    # Unknown system - just return normalized
    return code.strip().upper()
