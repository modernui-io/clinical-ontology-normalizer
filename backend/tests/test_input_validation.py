"""Tests for Input Validation Service.

Tests verify:
- Valid/invalid CUI formats
- ICD-10 code pattern validation
- SNOMED CT code validation
- RxNorm code validation
- Field-level error messages
- Decorator applies validation to endpoints
"""

import pytest
from pydantic import ValidationError

from app.services.input_validation import (
    CUICode,
    ICD10Code,
    SNOMEDCode,
    RxNormCode,
    ValidationError as InputValidationError,
    validate_cui,
    validate_icd10,
    validate_snomed,
    validate_rxnorm,
    validate_inputs,
)


class TestCUIValidation:
    """Test valid/invalid CUI formats."""

    def test_valid_cui(self):
        is_valid, error = validate_cui("C0011849")
        assert is_valid is True
        assert error is None

    def test_valid_cui_lowercase(self):
        is_valid, error = validate_cui("c0011849")
        assert is_valid is True

    def test_invalid_cui_missing_prefix(self):
        is_valid, error = validate_cui("0011849")
        assert is_valid is False
        assert "Invalid CUI format" in error

    def test_invalid_cui_too_short(self):
        is_valid, error = validate_cui("C001")
        assert is_valid is False

    def test_invalid_cui_too_long(self):
        is_valid, error = validate_cui("C00118490")
        assert is_valid is False

    def test_invalid_cui_non_numeric(self):
        is_valid, error = validate_cui("C001184X")
        assert is_valid is False

    def test_empty_cui(self):
        is_valid, error = validate_cui("")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_cui_pydantic_model_valid(self):
        code = CUICode(value="C0011849")
        assert code.value == "C0011849"

    def test_cui_pydantic_model_invalid(self):
        with pytest.raises(ValidationError):
            CUICode(value="invalid")


class TestICD10Validation:
    """Test ICD-10 code pattern validation."""

    def test_valid_icd10_basic(self):
        is_valid, error = validate_icd10("E11")
        assert is_valid is True

    def test_valid_icd10_with_decimal(self):
        is_valid, error = validate_icd10("E11.9")
        assert is_valid is True

    def test_valid_icd10_full(self):
        is_valid, error = validate_icd10("J45.20")
        assert is_valid is True

    def test_valid_icd10_long_suffix(self):
        is_valid, error = validate_icd10("S72.001A")
        assert is_valid is True

    def test_invalid_icd10_starts_with_number(self):
        is_valid, error = validate_icd10("111.9")
        assert is_valid is False
        assert "Invalid ICD-10-CM format" in error

    def test_invalid_icd10_too_short(self):
        is_valid, error = validate_icd10("E1")
        assert is_valid is False

    def test_invalid_icd10_invalid_letter(self):
        # U and some letters are reserved
        is_valid, error = validate_icd10("U11.9")
        assert is_valid is False

    def test_empty_icd10(self):
        is_valid, error = validate_icd10("")
        assert is_valid is False

    def test_icd10_pydantic_model_valid(self):
        code = ICD10Code(value="E11.9")
        assert code.value == "E11.9"

    def test_icd10_pydantic_model_invalid(self):
        with pytest.raises(ValidationError):
            ICD10Code(value="invalid")


class TestSNOMEDValidation:
    """Test SNOMED CT code validation."""

    def test_valid_snomed(self):
        is_valid, error = validate_snomed("73211009")
        assert is_valid is True

    def test_valid_snomed_6_digits(self):
        is_valid, error = validate_snomed("123456")
        assert is_valid is True

    def test_valid_snomed_long(self):
        is_valid, error = validate_snomed("1234567890123456")
        assert is_valid is True

    def test_invalid_snomed_too_short(self):
        is_valid, error = validate_snomed("12345")
        assert is_valid is False
        assert "Invalid SNOMED CT format" in error

    def test_invalid_snomed_non_numeric(self):
        is_valid, error = validate_snomed("7321100X")
        assert is_valid is False

    def test_empty_snomed(self):
        is_valid, error = validate_snomed("")
        assert is_valid is False

    def test_snomed_pydantic_model_valid(self):
        code = SNOMEDCode(value="73211009")
        assert code.value == "73211009"


class TestRxNormValidation:
    """Test RxNorm code validation."""

    def test_valid_rxnorm(self):
        is_valid, error = validate_rxnorm("161")
        assert is_valid is True

    def test_valid_rxnorm_long(self):
        is_valid, error = validate_rxnorm("10582")
        assert is_valid is True

    def test_invalid_rxnorm_non_numeric(self):
        is_valid, error = validate_rxnorm("abc")
        assert is_valid is False
        assert "Invalid RxNorm format" in error

    def test_invalid_rxnorm_too_long(self):
        is_valid, error = validate_rxnorm("12345678901")
        assert is_valid is False

    def test_empty_rxnorm(self):
        is_valid, error = validate_rxnorm("")
        assert is_valid is False

    def test_rxnorm_pydantic_model_valid(self):
        code = RxNormCode(value="10582")
        assert code.value == "10582"


class TestFieldLevelErrorMessages:
    """Test field-level error messages with suggested corrections."""

    def test_cui_error_includes_expected_format(self):
        _, error = validate_cui("bad")
        assert "C followed by 7 digits" in error
        assert "C0011849" in error

    def test_icd10_error_includes_expected_format(self):
        _, error = validate_icd10("bad")
        assert "letter + 2 digits" in error
        assert "E11" in error

    def test_snomed_error_includes_expected_format(self):
        _, error = validate_snomed("bad")
        assert "6-18 digit" in error
        assert "73211009" in error

    def test_rxnorm_error_includes_expected_format(self):
        _, error = validate_rxnorm("bad")
        assert "numeric identifier" in error

    def test_error_includes_invalid_value(self):
        _, error = validate_cui("BADVALUE")
        assert "BADVALUE" in error


class TestValidationDecorator:
    """Test decorator applies validation to endpoints."""

    def test_sync_decorator_passes_valid(self):
        @validate_inputs(code="icd10")
        def handler(code: str):
            return {"code": code}

        result = handler(code="E11.9")
        assert result == {"code": "E11.9"}

    def test_sync_decorator_raises_on_invalid(self):
        @validate_inputs(code="icd10")
        def handler(code: str):
            return {"code": code}

        with pytest.raises(InputValidationError) as exc_info:
            handler(code="invalid")
        assert len(exc_info.value.errors) == 1
        assert exc_info.value.errors[0]["field"] == "code"

    @pytest.mark.asyncio
    async def test_async_decorator_passes_valid(self):
        @validate_inputs(code="snomed")
        async def handler(code: str):
            return {"code": code}

        result = await handler(code="73211009")
        assert result == {"code": "73211009"}

    @pytest.mark.asyncio
    async def test_async_decorator_raises_on_invalid(self):
        @validate_inputs(code="snomed")
        async def handler(code: str):
            return {"code": code}

        with pytest.raises(InputValidationError):
            await handler(code="bad")

    def test_decorator_multiple_fields(self):
        @validate_inputs(cui="cui", code="icd10")
        def handler(cui: str, code: str):
            return {"cui": cui, "code": code}

        with pytest.raises(InputValidationError) as exc_info:
            handler(cui="bad", code="bad")
        assert len(exc_info.value.errors) == 2

    def test_decorator_skips_none_values(self):
        @validate_inputs(code="icd10")
        def handler(code: str = None):
            return {"code": code}

        result = handler(code=None)
        assert result == {"code": None}
