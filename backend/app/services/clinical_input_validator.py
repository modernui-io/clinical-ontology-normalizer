"""Clinical Input Plausibility Validator.

Validates clinical input values against physiologically plausible ranges
before they reach calculator logic. Two tiers:

- Flag range: value is physiologically unusual but possible.
  The calculator proceeds, but warnings are attached to the result.
- Block range: value is physiologically impossible or almost certainly
  a data-entry error. The calculator refuses to run.

This module is intended as a safety envelope and should be called
before any calculator execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlausibilityResult:
    """Result of clinical input plausibility validation."""

    valid: bool
    warnings: list[str] = field(default_factory=list)
    blocked: bool = False
    blocked_reason: str | None = None


# Each entry: (flag_min, flag_max, block_min, block_max, unit)
# Flag range: values outside [flag_min, flag_max] get a warning.
# Block range: values outside [block_min, block_max] are rejected.
PLAUSIBILITY_RANGES: dict[str, dict[str, Any]] = {
    "heart_rate": {
        "flag_min": 20,
        "flag_max": 300,
        "block_min": 0,
        "block_max": 300,
        "unit": "bpm",
    },
    "systolic_bp": {
        "flag_min": 40,
        "flag_max": 300,
        "block_min": 40,
        "block_max": 300,
        "unit": "mmHg",
    },
    "diastolic_bp": {
        "flag_min": 20,
        "flag_max": 200,
        "block_min": 20,
        "block_max": 200,
        "unit": "mmHg",
    },
    "temperature": {
        "flag_min": 25.0,
        "flag_max": 45.0,
        "block_min": 25.0,
        "block_max": 45.0,
        "unit": "°C",
    },
    "weight_kg": {
        "flag_min": 0.5,
        "flag_max": 500,
        "block_min": 0.5,
        "block_max": 500,
        "unit": "kg",
    },
    "height_cm": {
        "flag_min": 20,
        "flag_max": 280,
        "block_min": 20,
        "block_max": 280,
        "unit": "cm",
    },
    "age": {
        "flag_min": 0,
        "flag_max": 150,
        "block_min": 0,
        "block_max": 150,
        "unit": "years",
    },
    "creatinine": {
        "flag_min": 0.1,
        "flag_max": 30,
        "block_min": 0.1,
        "block_max": 30,
        "unit": "mg/dL",
    },
    "gfr": {
        "flag_min": 0,
        "flag_max": 200,
        "block_min": 0,
        "block_max": 200,
        "unit": "mL/min",
    },
}

# Aliases so callers can use various naming conventions and still
# match the canonical range key above.
_INPUT_ALIASES: dict[str, str] = {
    "hr": "heart_rate",
    "pulse": "heart_rate",
    "sbp": "systolic_bp",
    "systolic_blood_pressure": "systolic_bp",
    "dbp": "diastolic_bp",
    "diastolic_blood_pressure": "diastolic_bp",
    "temp": "temperature",
    "temperature_c": "temperature",
    "weight": "weight_kg",
    "height": "height_cm",
    "cr": "creatinine",
    "scr": "creatinine",
    "serum_creatinine": "creatinine",
    "egfr": "gfr",
}


def _resolve_key(name: str) -> str | None:
    """Resolve an input name to its canonical plausibility-range key."""
    lower = name.lower().strip()
    if lower in PLAUSIBILITY_RANGES:
        return lower
    return _INPUT_ALIASES.get(lower)


def validate_clinical_inputs(inputs: dict[str, float | int]) -> PlausibilityResult:
    """Validate a dict of clinical inputs against plausibility ranges.

    Args:
        inputs: Mapping of input names to numeric values.  Keys are
            matched case-insensitively and common aliases are accepted
            (e.g. ``"hr"`` for ``"heart_rate"``).

    Returns:
        PlausibilityResult describing validation outcome.  If
        ``blocked`` is True the calculator should refuse to run.
    """
    warnings: list[str] = []
    blocked = False
    blocked_reason: str | None = None

    for name, value in inputs.items():
        canonical = _resolve_key(name)
        if canonical is None:
            # No plausibility range defined for this input -- skip.
            continue

        spec = PLAUSIBILITY_RANGES[canonical]

        # Block check (outside hard limits)
        if value < spec["block_min"] or value > spec["block_max"]:
            blocked = True
            blocked_reason = (
                f"{canonical} value {value} {spec['unit']} is outside "
                f"plausible range [{spec['block_min']}-{spec['block_max']}]; "
                f"input rejected"
            )
            logger.warning("Blocked clinical input: %s", blocked_reason)
            break  # First blocking value is enough

        # Flag check (inside hard limits but outside soft limits)
        if value < spec["flag_min"] or value > spec["flag_max"]:
            msg = (
                f"{canonical} value {value} {spec['unit']} is unusual "
                f"(expected {spec['flag_min']}-{spec['flag_max']})"
            )
            warnings.append(msg)
            logger.info("Flagged clinical input: %s", msg)

    return PlausibilityResult(
        valid=not blocked,
        warnings=warnings,
        blocked=blocked,
        blocked_reason=blocked_reason,
    )
