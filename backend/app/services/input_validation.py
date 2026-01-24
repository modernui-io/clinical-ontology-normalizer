"""Input Validation Service with clinical code validators.

Provides Pydantic validators for common clinical terminology codes:
- CUI (UMLS Concept Unique Identifier)
- ICD-10-CM codes
- SNOMED CT codes
- RxNorm codes

Also provides a validation decorator for API endpoints that automatically
validates specified parameters and returns field-level error messages.
"""

import re
import functools
import logging
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger(__name__)


# =============================================================================
# Code Pattern Definitions
# =============================================================================

# CUI format: C followed by 7 digits (e.g., C0011849)
CUI_PATTERN = re.compile(r"^C\d{7}$")

# ICD-10-CM: Letter + 2 digits, optionally followed by dot and 1-4 alphanumeric chars
ICD10_PATTERN = re.compile(r"^[A-TV-Z]\d{2}(\.[A-Z0-9]{1,4})?$")

# SNOMED CT: 6-18 digit numeric identifier
SNOMED_PATTERN = re.compile(r"^\d{6,18}$")

# RxNorm: Numeric identifier (typically 5-7 digits but can vary)
RXNORM_PATTERN = re.compile(r"^\d{1,10}$")


# =============================================================================
# Validation Functions
# =============================================================================


def validate_cui(value: str) -> tuple[bool, str | None]:
    """Validate a UMLS CUI format.

    Args:
        value: The CUI string to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not value:
        return False, "CUI cannot be empty"
    value = value.strip().upper()
    if not CUI_PATTERN.match(value):
        return False, (
            f"Invalid CUI format: '{value}'. "
            "Expected format: C followed by 7 digits (e.g., C0011849)"
        )
    return True, None


def validate_icd10(value: str) -> tuple[bool, str | None]:
    """Validate an ICD-10-CM code format.

    Args:
        value: The ICD-10 code to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not value:
        return False, "ICD-10 code cannot be empty"
    value = value.strip().upper()
    if not ICD10_PATTERN.match(value):
        return False, (
            f"Invalid ICD-10-CM format: '{value}'. "
            "Expected format: letter + 2 digits, optionally followed by '.' and 1-4 characters "
            "(e.g., E11, E11.9, J45.20)"
        )
    return True, None


def validate_snomed(value: str) -> tuple[bool, str | None]:
    """Validate a SNOMED CT code format.

    Args:
        value: The SNOMED code to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not value:
        return False, "SNOMED CT code cannot be empty"
    value = value.strip()
    if not SNOMED_PATTERN.match(value):
        return False, (
            f"Invalid SNOMED CT format: '{value}'. "
            "Expected format: 6-18 digit numeric identifier (e.g., 73211009)"
        )
    return True, None


def validate_rxnorm(value: str) -> tuple[bool, str | None]:
    """Validate an RxNorm code format.

    Args:
        value: The RxNorm code to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not value:
        return False, "RxNorm code cannot be empty"
    value = value.strip()
    if not RXNORM_PATTERN.match(value):
        return False, (
            f"Invalid RxNorm format: '{value}'. "
            "Expected format: numeric identifier (e.g., 161, 10582)"
        )
    return True, None


# =============================================================================
# Validator Registry
# =============================================================================

VALIDATORS = {
    "cui": validate_cui,
    "icd10": validate_icd10,
    "snomed": validate_snomed,
    "rxnorm": validate_rxnorm,
}


# =============================================================================
# Pydantic Models with Validators
# =============================================================================


class CUICode(BaseModel):
    """Validated UMLS CUI code."""

    value: str

    @field_validator("value")
    @classmethod
    def validate_cui_format(cls, v: str) -> str:
        is_valid, error = validate_cui(v)
        if not is_valid:
            raise ValueError(error)
        return v.strip().upper()


class ICD10Code(BaseModel):
    """Validated ICD-10-CM code."""

    value: str

    @field_validator("value")
    @classmethod
    def validate_icd10_format(cls, v: str) -> str:
        is_valid, error = validate_icd10(v)
        if not is_valid:
            raise ValueError(error)
        return v.strip().upper()


class SNOMEDCode(BaseModel):
    """Validated SNOMED CT code."""

    value: str

    @field_validator("value")
    @classmethod
    def validate_snomed_format(cls, v: str) -> str:
        is_valid, error = validate_snomed(v)
        if not is_valid:
            raise ValueError(error)
        return v.strip()


class RxNormCode(BaseModel):
    """Validated RxNorm code."""

    value: str

    @field_validator("value")
    @classmethod
    def validate_rxnorm_format(cls, v: str) -> str:
        is_valid, error = validate_rxnorm(v)
        if not is_valid:
            raise ValueError(error)
        return v.strip()


# =============================================================================
# Validation Decorator
# =============================================================================


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        messages = "; ".join(e.get("message", "") for e in errors)
        super().__init__(f"Validation failed: {messages}")


def validate_inputs(**field_validators: str):
    """Decorator that validates specified function parameters.

    Usage:
        @validate_inputs(code="icd10", cui="cui")
        async def lookup_code(code: str, cui: str):
            ...

    Args:
        **field_validators: Mapping of parameter names to validator types
            (cui, icd10, snomed, rxnorm).

    Raises:
        ValidationError: If any validation fails, with field-level error details.
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            errors = _run_validations(func, field_validators, args, kwargs)
            if errors:
                raise ValidationError(errors)
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            errors = _run_validations(func, field_validators, args, kwargs)
            if errors:
                raise ValidationError(errors)
            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _run_validations(
    func, field_validators: dict[str, str], args: tuple, kwargs: dict
) -> list[dict[str, str]]:
    """Run validations on function arguments.

    Returns list of error dicts with field and message keys.
    """
    import inspect
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Build a mapping of param name -> value from args and kwargs
    bound_args = {}
    for i, arg in enumerate(args):
        if i < len(params):
            bound_args[params[i]] = arg
    bound_args.update(kwargs)

    errors = []
    for field_name, validator_type in field_validators.items():
        value = bound_args.get(field_name)
        if value is None:
            continue

        validator_fn = VALIDATORS.get(validator_type)
        if validator_fn is None:
            logger.warning(f"Unknown validator type: {validator_type}")
            continue

        is_valid, error_msg = validator_fn(str(value))
        if not is_valid:
            errors.append({
                "field": field_name,
                "message": error_msg,
                "value": str(value),
                "validator": validator_type,
            })

    return errors
