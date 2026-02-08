"""Response schemas for the ROI summary dashboard.

These schemas power the "money slide" for the Regeneron pitch:
screening volume, eligibility rates, projected enrollment uplift,
cost analysis, and time-series trends.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrialEligibilitySummary(BaseModel):
    """Eligibility stats for a single trial."""

    trial_id: str
    trial_name: str | None = None
    total_screened: int = 0
    eligible_count: int = 0
    ineligible_count: int = 0
    unknown_count: int = 0
    pass_rate: float = Field(0.0, description="eligible / total_screened")


class SiteTrialBreakdown(BaseModel):
    """Eligible patient count for one site-trial combination."""

    site_id: str
    site_name: str | None = None
    trial_id: str
    trial_name: str | None = None
    eligible_count: int = 0


class DualEnrollmentCandidate(BaseModel):
    """A patient eligible for multiple trials."""

    patient_id: str
    eligible_trial_ids: list[str] = []
    eligible_trial_names: list[str] = []
    trial_count: int = 0


class TimeSeriesBucket(BaseModel):
    """Screening volume and match rate for one time bucket."""

    period: str = Field(..., description="Date string (YYYY-MM-DD or YYYY-Www)")
    screenings: int = 0
    eligible: int = 0
    match_rate: float = 0.0


class ScreeningOverview(BaseModel):
    """Top-level screening volume numbers."""

    total_screenings: int = 0
    total_patients_screened: int = 0
    unique_trials_screened: int = 0
    total_eligible: int = 0
    total_ineligible: int = 0
    total_unknown: int = 0
    overall_pass_rate: float = 0.0


class ProjectedEnrollment(BaseModel):
    """Enrollment uplift projection."""

    eligible_patients: int = 0
    conversion_rate: float = 0.15
    projected_enrollments: int = 0


class CostAnalysis(BaseModel):
    """Simple cost vs. value analysis."""

    patients_screened: int = 0
    screening_cost_per_patient: float = 1.0
    total_screening_cost: float = 0.0
    projected_enrollments: int = 0
    estimated_value_per_enrollment: float = 50_000.0
    projected_enrollment_value: float = 0.0
    roi_ratio: float | None = Field(
        None, description="projected_value / screening_cost"
    )


class ROISummaryResponse(BaseModel):
    """Full ROI dashboard payload."""

    generated_at: datetime
    screening_overview: ScreeningOverview
    eligibility_by_trial: list[TrialEligibilitySummary] = []
    site_breakdown: list[SiteTrialBreakdown] = []
    dual_enrollment_candidates: list[DualEnrollmentCandidate] = []
    dual_enrollment_count: int = 0
    projected_enrollment: ProjectedEnrollment
    cost_analysis: CostAnalysis
    time_series: list[TimeSeriesBucket] = []
