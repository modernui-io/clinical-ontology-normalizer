"""Pydantic schemas for Study Startup & Feasibility Assessment (CLINICAL-15).

Manages study startup operations: site feasibility assessments with weighted
scoring, country feasibility evaluation, startup timeline tracking with
critical path analysis, protocol feasibility assessment, bottleneck analysis,
and startup operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FeasibilityStatus(str, Enum):
    """Status of a site feasibility assessment."""

    SCREENING = "screening"
    SHORTLISTED = "shortlisted"
    SELECTED = "selected"
    DECLINED = "declined"
    BACKUP = "backup"


class FeasibilityScore(str, Enum):
    """Overall feasibility score classification."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    MARGINAL = "marginal"
    POOR = "poor"


class StartupPhase(str, Enum):
    """Phase in the study startup lifecycle."""

    FEASIBILITY = "feasibility"
    SITE_SELECTION = "site_selection"
    REGULATORY_PREP = "regulatory_prep"
    IRB_SUBMISSION = "irb_submission"
    CONTRACT_NEGOTIATION = "contract_negotiation"
    BUDGET_FINALIZATION = "budget_finalization"
    SITE_INITIATION_VISIT = "site_initiation_visit"
    ACTIVE = "active"


class StartupBlocker(str, Enum):
    """Type of blocker delaying study startup."""

    REGULATORY_DELAY = "regulatory_delay"
    CONTRACT_DELAY = "contract_delay"
    BUDGET_DISPUTE = "budget_dispute"
    STAFF_SHORTAGE = "staff_shortage"
    EQUIPMENT_PENDING = "equipment_pending"
    IRB_QUERY = "irb_query"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SiteFeasibility(BaseModel):
    """Feasibility assessment for a clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assessment identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    trial_id: str = Field(..., description="Trial identifier")
    investigator_name: str = Field(..., description="Principal investigator name")
    specialty: str = Field(..., description="Medical specialty of the site")
    status: FeasibilityStatus = Field(..., description="Current feasibility status")
    overall_score: float = Field(
        ge=0.0, le=100.0, description="Composite feasibility score (0-100)"
    )
    patient_pool_estimate: int = Field(ge=0, description="Estimated eligible patient pool")
    competing_studies: int = Field(ge=0, description="Number of competing studies at the site")
    staff_available: int = Field(ge=0, description="Number of qualified staff available")
    experience_score: float = Field(
        ge=0.0, le=100.0, description="Site experience score (0-100)"
    )
    infrastructure_score: float = Field(
        ge=0.0, le=100.0, description="Infrastructure readiness score (0-100)"
    )
    enrollment_potential: float = Field(
        ge=0.0, le=100.0, description="Enrollment potential score (0-100)"
    )
    geographic_region: str = Field(..., description="Geographic region of the site")
    assessment_date: datetime = Field(..., description="Date of feasibility assessment")
    assessor: str = Field(..., description="Name of the assessor")


class CountryFeasibility(BaseModel):
    """Feasibility assessment for a country in a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique country assessment identifier")
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    country_name: str = Field(..., description="Country name")
    trial_id: str = Field(..., description="Trial identifier")
    regulatory_complexity: int = Field(
        ge=1, le=5, description="Regulatory complexity rating (1=simple, 5=very complex)"
    )
    approval_timeline_months: float = Field(
        ge=0.0, description="Estimated regulatory approval timeline in months"
    )
    import_requirements: str = Field(
        ..., description="Drug import and customs requirements"
    )
    data_privacy_requirements: str = Field(
        ..., description="Data privacy and protection requirements"
    )
    local_representation_required: bool = Field(
        ..., description="Whether a local legal representative is required"
    )
    estimated_sites: int = Field(ge=0, description="Estimated number of sites in country")
    estimated_patients: int = Field(ge=0, description="Estimated patient pool in country")
    cost_index: float = Field(
        ge=0.0, description="Relative cost index (1.0 = baseline US cost)"
    )


class StartupTimeline(BaseModel):
    """Timeline tracking for a site startup milestone."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique timeline entry identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    phase: StartupPhase = Field(..., description="Startup phase")
    planned_start: datetime = Field(..., description="Planned start date")
    planned_end: datetime = Field(..., description="Planned end date")
    actual_start: datetime | None = Field(None, description="Actual start date")
    actual_end: datetime | None = Field(None, description="Actual end date")
    blockers: list[StartupBlocker] = Field(
        default_factory=list, description="Active blockers for this phase"
    )
    milestone_notes: str | None = Field(None, description="Notes on this milestone")


class ProtocolFeasibility(BaseModel):
    """Feasibility assessment for a clinical trial protocol."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique protocol assessment identifier")
    trial_id: str = Field(..., description="Trial identifier")
    protocol_version: str = Field(..., description="Protocol version identifier")
    inclusion_criteria_count: int = Field(
        ge=0, description="Number of inclusion criteria"
    )
    exclusion_criteria_count: int = Field(
        ge=0, description="Number of exclusion criteria"
    )
    visit_schedule_complexity: float = Field(
        ge=0.0, le=100.0, description="Visit schedule complexity score (0-100)"
    )
    estimated_screen_failure_rate: float = Field(
        ge=0.0, le=100.0, description="Estimated screen failure rate (%)"
    )
    estimated_enrollment_rate_per_site_month: float = Field(
        ge=0.0, description="Estimated enrollment rate per site per month"
    )
    recommended_modifications: list[str] = Field(
        default_factory=list, description="Recommended protocol modifications"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SiteFeasibilityCreate(BaseModel):
    """Request to create a site feasibility assessment."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    trial_id: str = Field(..., description="Trial identifier")
    investigator_name: str = Field(..., description="Principal investigator name")
    specialty: str = Field(..., description="Medical specialty")
    patient_pool_estimate: int = Field(ge=0, description="Estimated patient pool")
    competing_studies: int = Field(ge=0, default=0, description="Competing studies")
    staff_available: int = Field(ge=0, description="Staff available")
    experience_score: float = Field(ge=0.0, le=100.0, description="Experience score")
    infrastructure_score: float = Field(ge=0.0, le=100.0, description="Infrastructure score")
    geographic_region: str = Field(..., description="Geographic region")
    assessor: str = Field(..., description="Assessor name")


class SiteFeasibilityUpdate(BaseModel):
    """Request to update a site feasibility assessment."""

    model_config = ConfigDict(from_attributes=True)

    status: FeasibilityStatus | None = Field(None, description="Feasibility status")
    patient_pool_estimate: int | None = Field(None, ge=0, description="Patient pool estimate")
    competing_studies: int | None = Field(None, ge=0, description="Competing studies")
    staff_available: int | None = Field(None, ge=0, description="Staff available")
    experience_score: float | None = Field(None, ge=0.0, le=100.0, description="Experience score")
    infrastructure_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Infrastructure score"
    )
    assessor: str | None = Field(None, description="Assessor name")


class CountryFeasibilityCreate(BaseModel):
    """Request to create a country feasibility assessment."""

    model_config = ConfigDict(from_attributes=True)

    country_code: str = Field(..., description="ISO country code")
    country_name: str = Field(..., description="Country name")
    trial_id: str = Field(..., description="Trial identifier")
    regulatory_complexity: int = Field(ge=1, le=5, description="Regulatory complexity (1-5)")
    approval_timeline_months: float = Field(ge=0.0, description="Approval timeline months")
    import_requirements: str = Field(..., description="Import requirements")
    data_privacy_requirements: str = Field(..., description="Data privacy requirements")
    local_representation_required: bool = Field(..., description="Local rep required")
    estimated_sites: int = Field(ge=0, description="Estimated sites")
    estimated_patients: int = Field(ge=0, description="Estimated patients")
    cost_index: float = Field(ge=0.0, description="Cost index")


class CountryFeasibilityUpdate(BaseModel):
    """Request to update a country feasibility assessment."""

    model_config = ConfigDict(from_attributes=True)

    regulatory_complexity: int | None = Field(None, ge=1, le=5, description="Regulatory complexity")
    approval_timeline_months: float | None = Field(None, ge=0.0, description="Approval timeline")
    import_requirements: str | None = Field(None, description="Import requirements")
    data_privacy_requirements: str | None = Field(None, description="Data privacy requirements")
    local_representation_required: bool | None = Field(None, description="Local rep required")
    estimated_sites: int | None = Field(None, ge=0, description="Estimated sites")
    estimated_patients: int | None = Field(None, ge=0, description="Estimated patients")
    cost_index: float | None = Field(None, ge=0.0, description="Cost index")


class StartupTimelineCreate(BaseModel):
    """Request to create a startup timeline entry."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    phase: StartupPhase = Field(..., description="Startup phase")
    planned_start: datetime = Field(..., description="Planned start date")
    planned_end: datetime = Field(..., description="Planned end date")


class StartupTimelineUpdate(BaseModel):
    """Request to update a startup timeline entry."""

    model_config = ConfigDict(from_attributes=True)

    actual_start: datetime | None = Field(None, description="Actual start date")
    actual_end: datetime | None = Field(None, description="Actual end date")
    blockers: list[StartupBlocker] | None = Field(None, description="Active blockers")
    milestone_notes: str | None = Field(None, description="Milestone notes")


class ProtocolFeasibilityCreate(BaseModel):
    """Request to create a protocol feasibility assessment."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    protocol_version: str = Field(..., description="Protocol version")
    inclusion_criteria_count: int = Field(ge=0, description="Inclusion criteria count")
    exclusion_criteria_count: int = Field(ge=0, description="Exclusion criteria count")
    visit_schedule_complexity: float = Field(
        ge=0.0, le=100.0, description="Visit schedule complexity"
    )
    estimated_screen_failure_rate: float = Field(
        ge=0.0, le=100.0, description="Screen failure rate"
    )
    estimated_enrollment_rate_per_site_month: float = Field(
        ge=0.0, description="Enrollment rate per site/month"
    )
    recommended_modifications: list[str] = Field(
        default_factory=list, description="Recommended modifications"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SiteFeasibilityListResponse(BaseModel):
    """List of site feasibility assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteFeasibility] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CountryFeasibilityListResponse(BaseModel):
    """List of country feasibility assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CountryFeasibility] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class StartupTimelineListResponse(BaseModel):
    """List of startup timeline entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StartupTimeline] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ProtocolFeasibilityListResponse(BaseModel):
    """List of protocol feasibility assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProtocolFeasibility] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class BottleneckAnalysis(BaseModel):
    """Analysis of which startup phase causes the most delays."""

    model_config = ConfigDict(from_attributes=True)

    phase: StartupPhase = Field(..., description="Startup phase")
    avg_delay_days: float = Field(ge=0.0, description="Average delay in days")
    sites_affected: int = Field(ge=0, description="Number of sites affected")
    common_blockers: list[str] = Field(
        default_factory=list, description="Most common blockers"
    )


class SiteRanking(BaseModel):
    """Ranked site with composite feasibility score."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    trial_id: str = Field(..., description="Trial identifier")
    composite_score: float = Field(
        ge=0.0, le=100.0, description="Weighted composite score"
    )
    score_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Score breakdown by component"
    )
    rank: int = Field(ge=1, description="Rank among assessed sites")
    feasibility_grade: FeasibilityScore = Field(..., description="Feasibility grade")


class CountryOptimization(BaseModel):
    """Optimized country recommendation based on cost, timeline, and patient pool."""

    model_config = ConfigDict(from_attributes=True)

    country_code: str = Field(..., description="Country code")
    country_name: str = Field(..., description="Country name")
    optimization_score: float = Field(
        ge=0.0, le=100.0, description="Optimization score (higher = better)"
    )
    cost_score: float = Field(ge=0.0, le=100.0, description="Cost efficiency score")
    timeline_score: float = Field(ge=0.0, le=100.0, description="Timeline efficiency score")
    patient_pool_score: float = Field(ge=0.0, le=100.0, description="Patient pool score")
    recommendation: str = Field(..., description="Recommendation rationale")


class CriticalPath(BaseModel):
    """Critical path analysis for a site startup."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    total_planned_days: int = Field(ge=0, description="Total planned startup days")
    total_actual_days: int | None = Field(None, description="Total actual startup days so far")
    critical_phase: StartupPhase | None = Field(
        None, description="Phase on the critical path (longest delay)"
    )
    delay_days: int = Field(default=0, description="Days behind schedule")
    on_track: bool = Field(..., description="Whether the site is on track")


class ScreenFailurePrediction(BaseModel):
    """Predicted screen failure rate based on protocol complexity."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    protocol_version: str = Field(..., description="Protocol version")
    predicted_rate: float = Field(
        ge=0.0, le=100.0, description="Predicted screen failure rate (%)"
    )
    criteria_complexity_factor: float = Field(
        ge=0.0, description="Complexity factor from criteria count"
    )
    visit_complexity_factor: float = Field(
        ge=0.0, description="Complexity factor from visit schedule"
    )
    confidence: str = Field(..., description="Prediction confidence level")


class StartupMetrics(BaseModel):
    """Aggregated study startup operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_sites_assessed: int = Field(ge=0, description="Total sites assessed for feasibility")
    sites_selected: int = Field(ge=0, description="Number of sites selected")
    avg_startup_time_days: float = Field(ge=0.0, description="Average startup time in days")
    sites_by_phase: dict[str, int] = Field(
        default_factory=dict, description="Site counts by startup phase"
    )
    countries_assessed: int = Field(ge=0, description="Number of countries assessed")
    protocol_amendments: int = Field(
        ge=0, description="Number of protocol feasibility assessments"
    )
    avg_feasibility_score: float = Field(
        ge=0.0, le=100.0, description="Average feasibility score"
    )
    bottleneck_analysis: list[BottleneckAnalysis] = Field(
        default_factory=list, description="Bottleneck analysis by phase"
    )
