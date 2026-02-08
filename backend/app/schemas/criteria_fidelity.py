"""Pydantic schemas for Trial Eligibility Criteria Fidelity (CSO-2.4).

Defines structured schemas for parsing, validating, and reporting on
clinical trial eligibility criteria definitions. Ensures criteria are
complete, unambiguous, and machine-executable before they enter the
screening pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CriterionType(str, Enum):
    """Supported criterion domain types."""

    CONDITION = "condition"
    MEASUREMENT = "measurement"
    DEMOGRAPHIC = "demographic"
    MEDICATION = "medication"
    PROCEDURE = "procedure"


class Operator(str, Enum):
    """Comparison operators for criterion values."""

    EQUALS = "equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    BETWEEN = "between"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class IssueSeverity(str, Enum):
    """Severity levels for criterion validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueType(str, Enum):
    """Categories of criterion validation issues."""

    MISSING_UNIT = "MISSING_UNIT"
    AMBIGUOUS_TERM = "AMBIGUOUS_TERM"
    UNRESOLVABLE_CONCEPT = "UNRESOLVABLE_CONCEPT"
    IMPOSSIBLE_RANGE = "IMPOSSIBLE_RANGE"
    CONFLICTING = "CONFLICTING"
    INCOMPLETE = "INCOMPLETE"
    MISSING_OPERATOR = "MISSING_OPERATOR"
    MISSING_VALUE = "MISSING_VALUE"


# ---------------------------------------------------------------------------
# Parsed criterion
# ---------------------------------------------------------------------------


class TemporalConstraint(BaseModel):
    """Temporal constraint on a criterion."""

    direction: str = Field(..., description="e.g., 'within_last', 'before', 'after', 'active'")
    window_days: int | None = Field(None, description="Number of days for the time window")
    reference_point: str | None = Field(None, description="e.g., 'screening_date', 'enrollment'")


class ParsedCriterion(BaseModel):
    """A structured, machine-executable representation of a single criterion.

    Produced by parsing free-text eligibility criteria into a normalized
    format suitable for automated screening.
    """

    original_text: str = Field(..., description="Original free-text criterion")
    criterion_type: CriterionType = Field(..., description="Domain type of the criterion")
    domain: str = Field(..., description="OMOP domain label (e.g., 'Condition', 'Measurement')")
    concept_terms: list[str] = Field(
        default_factory=list,
        description="Extracted clinical concept terms (e.g., ['Type 2 Diabetes', 'T2DM'])",
    )
    operator: Operator = Field(..., description="Comparison operator")
    value: Any | None = Field(None, description="Primary value for comparison")
    value_high: Any | None = Field(None, description="Upper bound for BETWEEN operator")
    unit: str | None = Field(None, description="Unit of measurement (e.g., '%', 'mg/dL', 'years')")
    temporal_constraint: TemporalConstraint | None = Field(
        None, description="Temporal constraint, if any"
    )
    is_exclusion: bool = Field(False, description="Whether this is an exclusion criterion")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Parser confidence in the structured interpretation",
    )
    parse_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings generated during parsing (e.g., assumed units)",
    )


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


class CriterionIssue(BaseModel):
    """A single validation issue found in a criterion definition."""

    issue_type: IssueType = Field(..., description="Category of the issue")
    description: str = Field(..., description="Human-readable description of the issue")
    severity: IssueSeverity = Field(..., description="Severity level")
    field: str | None = Field(None, description="Which field is problematic (if applicable)")


class ValidationResult(BaseModel):
    """Result of validating a single criterion definition."""

    criterion: ParsedCriterion = Field(..., description="The criterion that was validated")
    is_valid: bool = Field(..., description="Whether the criterion passes all validation checks")
    issues: list[CriterionIssue] = Field(
        default_factory=list, description="List of validation issues found"
    )
    suggested_fix: str | None = Field(
        None, description="Suggested correction for the most severe issue"
    )


# ---------------------------------------------------------------------------
# Trial-level validation report
# ---------------------------------------------------------------------------


class TrialValidationReport(BaseModel):
    """Aggregate validation report for all criteria in a trial."""

    trial_id: str = Field(..., description="Trial identifier")
    total_criteria: int = Field(..., description="Total number of criteria validated")
    valid_count: int = Field(0, description="Number of criteria that passed validation")
    warning_count: int = Field(0, description="Number of criteria with warnings only")
    error_count: int = Field(0, description="Number of criteria with errors")
    results: list[ValidationResult] = Field(
        default_factory=list, description="Per-criterion validation results"
    )
    overall_fidelity_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Aggregate fidelity score (1.0 = all criteria valid, "
            "0.0 = no criteria valid). Warnings reduce by 0.1 each, "
            "errors reduce by full weight."
        ),
    )
    validated_at: datetime | None = Field(None, description="Timestamp of validation")


# ---------------------------------------------------------------------------
# API request/response schemas
# ---------------------------------------------------------------------------


class ParseCriterionRequest(BaseModel):
    """Request body for parsing a single criterion text."""

    text: str = Field(..., min_length=1, description="Free-text eligibility criterion to parse")
    is_exclusion: bool = Field(False, description="Whether this is an exclusion criterion")


class ValidateCriterionRequest(BaseModel):
    """Request body for validating a criterion definition."""

    criterion: ParsedCriterion = Field(..., description="Parsed criterion to validate")


class ValidateTrialCriteriaRequest(BaseModel):
    """Request body for validating all criteria for a trial.

    If criteria_texts is provided, they are parsed first. Otherwise,
    the trial's existing criteria definitions are validated.
    """

    criteria_texts: list[str] | None = Field(
        None,
        description="Optional list of free-text criteria to parse and validate",
    )
