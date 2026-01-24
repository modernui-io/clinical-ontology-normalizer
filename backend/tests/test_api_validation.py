"""Tests for API input validation middleware and dependencies."""

import pytest
from datetime import date

from app.api.validation import (
    PATIENT_ID_PATTERN,
    UUID_PATTERN,
    ICD10_PATTERN,
    SNOMED_PATTERN,
    CPT_PATTERN,
    field_error,
    raise_validation_error,
    validate_patient_id_param,
    validate_uuid_param,
    validate_date_range_params,
    validate_icd10_param,
    validate_snomed_param,
    validate_pagination_params,
    PaginationParams,
    DateRangeParams,
)
from app.api.errors import ErrorCode, ValidationError


# ============================================================================
# Pattern Tests
# ============================================================================


class TestPatientIdPattern:
    """Test patient ID regex pattern."""

    def test_valid_simple_id(self):
        assert PATIENT_ID_PATTERN.match("P12345")

    def test_valid_with_hyphens(self):
        assert PATIENT_ID_PATTERN.match("patient-001")

    def test_valid_with_underscores(self):
        assert PATIENT_ID_PATTERN.match("MRN_2024_001")

    def test_valid_alphanumeric(self):
        assert PATIENT_ID_PATTERN.match("abc123XYZ")

    def test_invalid_empty(self):
        assert not PATIENT_ID_PATTERN.match("")

    def test_invalid_special_chars(self):
        assert not PATIENT_ID_PATTERN.match("patient@123")

    def test_invalid_spaces(self):
        assert not PATIENT_ID_PATTERN.match("patient 001")

    def test_invalid_too_long(self):
        assert not PATIENT_ID_PATTERN.match("a" * 65)

    def test_valid_max_length(self):
        assert PATIENT_ID_PATTERN.match("a" * 64)


class TestUUIDPattern:
    """Test UUID regex pattern."""

    def test_valid_uuid(self):
        assert UUID_PATTERN.match("123e4567-e89b-12d3-a456-426614174000")

    def test_valid_uppercase(self):
        assert UUID_PATTERN.match("123E4567-E89B-12D3-A456-426614174000")

    def test_invalid_no_hyphens(self):
        assert not UUID_PATTERN.match("123e4567e89b12d3a456426614174000")

    def test_invalid_too_short(self):
        assert not UUID_PATTERN.match("123e4567-e89b-12d3-a456")

    def test_invalid_wrong_format(self):
        assert not UUID_PATTERN.match("not-a-valid-uuid-string")


class TestICD10Pattern:
    """Test ICD-10 code regex pattern."""

    def test_valid_simple(self):
        assert ICD10_PATTERN.match("E11")

    def test_valid_with_decimal(self):
        assert ICD10_PATTERN.match("E11.9")

    def test_valid_long_decimal(self):
        assert ICD10_PATTERN.match("J45.20")

    def test_valid_four_decimal(self):
        assert ICD10_PATTERN.match("S72.001A")

    def test_invalid_starts_with_number(self):
        assert not ICD10_PATTERN.match("123.4")

    def test_invalid_too_short(self):
        assert not ICD10_PATTERN.match("E1")

    def test_valid_lowercase(self):
        assert ICD10_PATTERN.match("e11.9")


class TestSNOMEDPattern:
    """Test SNOMED CT code regex pattern."""

    def test_valid_6_digits(self):
        assert SNOMED_PATTERN.match("123456")

    def test_valid_9_digits(self):
        assert SNOMED_PATTERN.match("73211009")

    def test_valid_18_digits(self):
        assert SNOMED_PATTERN.match("123456789012345678")

    def test_invalid_5_digits(self):
        assert not SNOMED_PATTERN.match("12345")

    def test_invalid_letters(self):
        assert not SNOMED_PATTERN.match("73211ABC")


class TestCPTPattern:
    """Test CPT code regex pattern."""

    def test_valid(self):
        assert CPT_PATTERN.match("99213")

    def test_invalid_4_digits(self):
        assert not CPT_PATTERN.match("9921")

    def test_invalid_6_digits(self):
        assert not CPT_PATTERN.match("992130")

    def test_invalid_letters(self):
        assert not CPT_PATTERN.match("9921A")


# ============================================================================
# Validator Function Tests
# ============================================================================


class TestValidatePatientIdParam:
    """Test validate_patient_id_param function."""

    def test_valid_id_returned(self):
        result = validate_patient_id_param("P12345")
        assert result == "P12345"

    def test_empty_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_patient_id_param("")
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_PATIENT_ID

    def test_invalid_chars_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_patient_id_param("patient@#$")
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_PATIENT_ID
        assert len(exc_info.value.details) == 1
        assert exc_info.value.details[0].field == "patient_id"

    def test_too_long_raises_validation_error(self):
        with pytest.raises(ValidationError):
            validate_patient_id_param("a" * 65)


class TestValidateUUIDParam:
    """Test validate_uuid_param function."""

    def test_valid_uuid(self):
        result = validate_uuid_param("123e4567-e89b-12d3-a456-426614174000")
        assert result == "123e4567-e89b-12d3-a456-426614174000"

    def test_empty_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_uuid_param("")
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_UUID

    def test_invalid_format_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_uuid_param("not-a-uuid")
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_UUID
        assert len(exc_info.value.details) == 1
        assert exc_info.value.details[0].field == "id"


class TestValidateDateRangeParams:
    """Test validate_date_range_params function."""

    def test_valid_range(self):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        result = validate_date_range_params(start, end)
        assert result == (start, end)

    def test_same_date_valid(self):
        d = date(2024, 6, 15)
        result = validate_date_range_params(d, d)
        assert result == (d, d)

    def test_none_values_valid(self):
        result = validate_date_range_params(None, None)
        assert result == (None, None)

    def test_only_start_valid(self):
        start = date(2024, 1, 1)
        result = validate_date_range_params(start, None)
        assert result == (start, None)

    def test_start_after_end_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range_params(date(2024, 12, 31), date(2024, 1, 1))
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_DATE_RANGE
        assert len(exc_info.value.details) == 2


class TestValidateICD10Param:
    """Test validate_icd10_param function."""

    def test_valid_code_normalized(self):
        result = validate_icd10_param("e11.9")
        assert result == "E11.9"

    def test_valid_code_with_whitespace(self):
        result = validate_icd10_param("  J45.20  ")
        assert result == "J45.20"

    def test_invalid_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_icd10_param("INVALID")
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_ICD10_CODE


class TestValidateSNOMEDParam:
    """Test validate_snomed_param function."""

    def test_valid_code(self):
        result = validate_snomed_param("73211009")
        assert result == "73211009"

    def test_invalid_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_snomed_param("ABC123")
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_SNOMED_CODE


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestFieldError:
    """Test field_error helper."""

    def test_creates_error_detail(self):
        detail = field_error("name", "Name is required")
        assert detail.field == "name"
        assert detail.message == "Name is required"
        assert detail.value is None

    def test_with_value(self):
        detail = field_error("age", "Must be positive", value=-5)
        assert detail.value == "-5"

    def test_long_value_truncated(self):
        long_val = "x" * 200
        detail = field_error("text", "Too long", value=long_val)
        assert len(detail.value) <= 100


class TestRaiseValidationError:
    """Test raise_validation_error helper."""

    def test_raises_with_details(self):
        details = [field_error("field1", "Error 1"), field_error("field2", "Error 2")]
        with pytest.raises(ValidationError) as exc_info:
            raise_validation_error("Multiple errors", details)
        assert len(exc_info.value.details) == 2

    def test_custom_error_code(self):
        with pytest.raises(ValidationError) as exc_info:
            raise_validation_error(
                "Bad format",
                [field_error("code", "Invalid")],
                error_code=ErrorCode.VALIDATION_INVALID_FORMAT,
            )
        assert exc_info.value.error_code == ErrorCode.VALIDATION_INVALID_FORMAT


# ============================================================================
# Pydantic Model Tests
# ============================================================================


class TestPaginationParams:
    """Test PaginationParams model."""

    def test_defaults(self):
        params = PaginationParams()
        assert params.offset == 0
        assert params.limit == 20

    def test_custom_values(self):
        params = PaginationParams(offset=10, limit=50)
        assert params.offset == 10
        assert params.limit == 50

    def test_negative_offset_rejected(self):
        with pytest.raises(Exception):
            PaginationParams(offset=-1)

    def test_zero_limit_rejected(self):
        with pytest.raises(Exception):
            PaginationParams(limit=0)

    def test_limit_over_max_rejected(self):
        with pytest.raises(Exception):
            PaginationParams(limit=1001)


class TestDateRangeParams:
    """Test DateRangeParams model."""

    def test_valid_range(self):
        params = DateRangeParams(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert params.start_date == date(2024, 1, 1)
        assert params.end_date == date(2024, 12, 31)

    def test_none_values(self):
        params = DateRangeParams()
        assert params.start_date is None
        assert params.end_date is None

    def test_invalid_range_raises_error(self):
        with pytest.raises(ValidationError):
            DateRangeParams(
                start_date=date(2024, 12, 31),
                end_date=date(2024, 1, 1),
            )
