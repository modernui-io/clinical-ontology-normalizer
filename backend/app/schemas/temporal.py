"""Pydantic schemas for temporal reasoning in clinical trial eligibility.

CMO-1.3: Temporal Reasoning Validation

Defines schemas for temporal criteria (time windows, date ranges, active
status), temporal evaluation results, and filter configuration.  These
schemas are consumed by the TemporalEligibilityService to filter
ClinicalFacts by recency before evaluating trial eligibility criteria.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TemporalDirection(str, Enum):
    """Direction of a temporal window relative to the reference point."""

    WITHIN_LAST = "within_last"     # e.g., "within last 90 days"
    BEFORE = "before"               # e.g., "before screening date"
    AFTER = "after"                 # e.g., "after enrollment date"
    BETWEEN = "between"             # e.g., "between date1 and date2"
    ACTIVE = "active"               # No end date or end date > now


class TemporalReferencePoint(str, Enum):
    """What the temporal window is relative to."""

    NOW = "now"                       # Current datetime (default)
    ENROLLMENT_DATE = "enrollment_date"
    SCREENING_DATE = "screening_date"


class TemporalStatus(str, Enum):
    """Outcome of a temporal criterion evaluation."""

    MET = "MET"                       # Criterion is satisfied
    NOT_MET = "NOT_MET"               # Data exists but outside window
    UNKNOWN = "UNKNOWN"               # Facts lack dates; can't determine
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # No facts at all


class MissingDatePolicy(str, Enum):
    """How to handle facts that lack date information."""

    EXCLUDE = "exclude"   # Treat undated facts as not matching
    INCLUDE = "include"   # Treat undated facts as matching
    UNKNOWN = "unknown"   # Flag as UNKNOWN status


# ---------------------------------------------------------------------------
# Temporal Criterion
# ---------------------------------------------------------------------------


class TemporalCriterion(BaseModel):
    """A temporal constraint that can be attached to an eligibility criterion.

    Examples:
        - HbA1c within last 90 days:
            direction=WITHIN_LAST, time_window_days=90
        - Active diagnosis (no end date):
            direction=ACTIVE
        - No cancer in last 5 years:
            direction=WITHIN_LAST, time_window_days=1825
        - Between two specific dates:
            direction=BETWEEN, start_date=..., end_date=...
    """

    direction: TemporalDirection = Field(
        ...,
        description="Direction of the temporal filter",
    )
    time_window_days: int | None = Field(
        None,
        ge=0,
        description="Number of days for the temporal window (used with WITHIN_LAST, BEFORE, AFTER)",
    )
    reference_point: TemporalReferencePoint = Field(
        default=TemporalReferencePoint.NOW,
        description="What the temporal window is relative to",
    )
    start_date: datetime | None = Field(
        None,
        description="Start of date range (used with BETWEEN direction)",
    )
    end_date: datetime | None = Field(
        None,
        description="End of date range (used with BETWEEN direction)",
    )
    missing_date_policy: MissingDatePolicy = Field(
        default=MissingDatePolicy.UNKNOWN,
        description="How to handle facts without date information",
    )
    min_duration_days: int | None = Field(
        None,
        ge=0,
        description="Minimum duration requirement (e.g., diagnosis for >= 365 days)",
    )


# ---------------------------------------------------------------------------
# Temporal Result
# ---------------------------------------------------------------------------


class TemporalResult(BaseModel):
    """Result of evaluating a temporal criterion for a patient."""

    criterion: TemporalCriterion = Field(
        ...,
        description="The temporal criterion that was evaluated",
    )
    status: TemporalStatus = Field(
        ...,
        description="Outcome of the temporal evaluation",
    )
    matched_fact_ids: list[str] = Field(
        default_factory=list,
        description="IDs of ClinicalFacts that passed the temporal filter",
    )
    excluded_fact_ids: list[str] = Field(
        default_factory=list,
        description="IDs of ClinicalFacts outside the temporal window",
    )
    undated_fact_ids: list[str] = Field(
        default_factory=list,
        description="IDs of ClinicalFacts with no date information",
    )
    total_facts_evaluated: int = Field(
        default=0,
        description="Total number of facts considered",
    )
    evidence: str = Field(
        default="",
        description="Human-readable explanation of the temporal evaluation",
    )
    window_start: datetime | None = Field(
        None,
        description="Computed start of the temporal window",
    )
    window_end: datetime | None = Field(
        None,
        description="Computed end of the temporal window",
    )


# ---------------------------------------------------------------------------
# Filter Configuration
# ---------------------------------------------------------------------------


class TemporalFilterConfig(BaseModel):
    """Global configuration for temporal filtering behavior."""

    default_lookback_days: int = Field(
        default=365,
        ge=0,
        description="Default lookback window when no explicit window is specified",
    )
    require_dates: bool = Field(
        default=False,
        description="If True, facts without dates are automatically excluded",
    )
    missing_date_policy: MissingDatePolicy = Field(
        default=MissingDatePolicy.UNKNOWN,
        description="Global policy for facts missing date information",
    )
