"""Pydantic schemas for Patient Screening Dashboard (VP-Product-8).

Provides saved searches, screening filters, screening sessions,
dashboard summaries, and screening metrics for the clinical trial
patient recruitment screening dashboard.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FilterOperator(str, Enum):
    """Operators for screening filter comparisons."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    CONTAINS = "contains"
    IN = "in"
    BETWEEN = "between"


class ScreeningStatus(str, Enum):
    """Possible screening status for a patient."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    INDETERMINATE = "indeterminate"


# ---------------------------------------------------------------------------
# Screening Filter
# ---------------------------------------------------------------------------


class ScreeningFilter(BaseModel):
    """A single filter condition for patient screening."""

    field: str = Field(..., description="Field to filter on (e.g., 'age', 'condition', 'lab.HbA1c')")
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: str | float | int | bool | None = Field(None, description="Single value for comparison")
    values: list[str | float | int] | None = Field(
        None, description="Multiple values for IN or BETWEEN operators"
    )


# ---------------------------------------------------------------------------
# Saved Search
# ---------------------------------------------------------------------------


class SavedSearchFilters(BaseModel):
    """Filter configuration stored in a saved search."""

    trial_id: str | None = Field(None, description="Associated trial ID")
    conditions: list[str] = Field(default_factory=list, description="Required conditions")
    age_range: dict[str, int] | None = Field(None, description="Min/max age range, e.g., {'min': 18, 'max': 75}")
    lab_ranges: dict[str, dict[str, float]] | None = Field(
        None, description="Lab value ranges, e.g., {'HbA1c': {'min': 6.5, 'max': 10.0}}"
    )
    exclusions: list[str] = Field(default_factory=list, description="Exclusion criteria")


class SavedSearch(BaseModel):
    """A saved screening search with filter criteria."""

    id: str = Field(..., description="Unique saved search identifier")
    name: str = Field(..., description="Human-readable search name")
    description: str | None = Field(None, description="Description of the search purpose")
    created_by: str = Field(default="system", description="User who created the search")
    filters: SavedSearchFilters = Field(..., description="Filter configuration")
    patient_count: int = Field(0, description="Cached count of matching patients")
    last_run: datetime | None = Field(None, description="When this search was last executed")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class SavedSearchCreate(BaseModel):
    """Request body for creating a saved search."""

    name: str = Field(..., min_length=1, max_length=200, description="Search name")
    description: str | None = Field(None, max_length=1000, description="Search description")
    created_by: str = Field(default="system", description="Creator identifier")
    filters: SavedSearchFilters = Field(..., description="Filter configuration")


class SavedSearchUpdate(BaseModel):
    """Request body for updating a saved search."""

    name: str | None = Field(None, min_length=1, max_length=200, description="Updated name")
    description: str | None = Field(None, max_length=1000, description="Updated description")
    filters: SavedSearchFilters | None = Field(None, description="Updated filters")


# ---------------------------------------------------------------------------
# Screening Result (per-patient)
# ---------------------------------------------------------------------------


class ScreeningResult(BaseModel):
    """Result of screening a single patient against trial criteria."""

    patient_id: str = Field(..., description="Patient identifier")
    patient_name: str = Field(..., description="Patient display name")
    age: int = Field(..., description="Patient age in years")
    gender: str = Field(..., description="Patient gender")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Overall match score (0-1)")
    matched_criteria: list[str] = Field(default_factory=list, description="Criteria the patient met")
    unmatched_criteria: list[str] = Field(default_factory=list, description="Criteria the patient did not meet")
    missing_data: list[str] = Field(default_factory=list, description="Criteria with insufficient data")
    last_visit_date: str | None = Field(None, description="Date of last clinical visit")
    primary_conditions: list[str] = Field(default_factory=list, description="Patient primary conditions")
    status: ScreeningStatus = Field(..., description="Screening eligibility status")


# ---------------------------------------------------------------------------
# Screening Session
# ---------------------------------------------------------------------------


class ScreeningSession(BaseModel):
    """A screening session recording a batch screening run."""

    id: str = Field(..., description="Unique session identifier")
    trial_id: str = Field(..., description="Trial screened against")
    filters_applied: list[ScreeningFilter] = Field(default_factory=list, description="Filters used")
    total_screened: int = Field(0, description="Total patients screened")
    total_eligible: int = Field(0, description="Patients meeting all criteria")
    total_ineligible: int = Field(0, description="Patients failing one or more criteria")
    total_indeterminate: int = Field(0, description="Patients with insufficient data")
    results: list[ScreeningResult] = Field(default_factory=list, description="Per-patient results")
    started_at: datetime = Field(..., description="Session start timestamp")
    completed_at: datetime | None = Field(None, description="Session completion timestamp")
    created_by: str = Field(default="system", description="User who initiated the session")


# ---------------------------------------------------------------------------
# Dashboard Summary
# ---------------------------------------------------------------------------


class TopMatchingTrial(BaseModel):
    """A trial with high patient match counts."""

    trial_id: str
    trial_name: str
    eligible_count: int = 0


class DashboardSummary(BaseModel):
    """High-level overview for the screening dashboard."""

    active_trials: int = Field(0, description="Number of active trials")
    total_patients: int = Field(0, description="Total patients in the system")
    total_screened_today: int = Field(0, description="Patients screened today")
    total_eligible_today: int = Field(0, description="Patients found eligible today")
    screening_rate_trend: list[dict[str, int | str]] = Field(
        default_factory=list,
        description="Screening volume trend, e.g., [{'date': '2025-01-15', 'count': 42}]",
    )
    top_matching_trials: list[TopMatchingTrial] = Field(
        default_factory=list, description="Trials with the most eligible patients"
    )


# ---------------------------------------------------------------------------
# Screening Metrics
# ---------------------------------------------------------------------------


class ExclusionReason(BaseModel):
    """A commonly encountered exclusion reason."""

    reason: str
    count: int = 0


class DailyVolume(BaseModel):
    """Screening volume for a single day."""

    date: str
    sessions: int = 0
    patients_screened: int = 0


class ScreeningMetrics(BaseModel):
    """Analytics metrics for screening activity."""

    total_sessions: int = Field(0, description="Total screening sessions")
    avg_patients_per_session: float = Field(0.0, description="Average patients per session")
    avg_match_score: float = Field(0.0, description="Average match score across all results")
    most_common_exclusion_reasons: list[ExclusionReason] = Field(
        default_factory=list, description="Most frequent exclusion reasons"
    )
    screening_volume_by_day: list[DailyVolume] = Field(
        default_factory=list, description="Daily screening volume"
    )


# ---------------------------------------------------------------------------
# Request / Response Wrappers
# ---------------------------------------------------------------------------


class RunScreeningRequest(BaseModel):
    """Request body for executing a screening run."""

    trial_id: str = Field(..., description="Trial to screen against")
    filters: list[ScreeningFilter] = Field(default_factory=list, description="Additional filters")
    created_by: str = Field(default="system", description="User initiating the screening")


class ExportResultsResponse(BaseModel):
    """Response for a results export."""

    session_id: str = Field(..., description="Session that was exported")
    format: str = Field(..., description="Export format (csv or json)")
    row_count: int = Field(0, description="Number of rows exported")
    columns: list[str] = Field(default_factory=list, description="Column names")
    data: list[dict] = Field(default_factory=list, description="Exported data rows")


class ScreeningHistoryItem(BaseModel):
    """Summary of a past screening session (without full results)."""

    id: str
    trial_id: str
    total_screened: int = 0
    total_eligible: int = 0
    total_ineligible: int = 0
    total_indeterminate: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    created_by: str = "system"
