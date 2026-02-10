"""Pydantic schemas for Protocol Feasibility Assessment module.

Manages feasibility studies for clinical trial protocols including site evaluation,
competitive landscape analysis, enrollment projections, feasibility scoring,
questionnaire workflows, and operational metrics for protocol planning.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FeasibilityStatus(str, Enum):
    """Lifecycle status of a feasibility study."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class SiteRating(str, Enum):
    """Overall rating for a site's feasibility assessment."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    MARGINAL = "marginal"
    NOT_SUITABLE = "not_suitable"


class CompetitiveThreatLevel(str, Enum):
    """Level of competitive threat from a competing trial."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class EnrollmentRisk(str, Enum):
    """Risk level for enrollment projection scenarios."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class FeasibilityStudy(BaseModel):
    """A protocol feasibility study encompassing site, competitive, and enrollment analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique feasibility study identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    protocol_id: str = Field(..., description="Protocol identifier under evaluation")
    protocol_version: str = Field(..., description="Version of the protocol being assessed")
    therapeutic_area: str = Field(..., description="Therapeutic area (e.g., Oncology, Immunology)")
    indication: str = Field(..., description="Target indication for the trial")
    phase: str = Field(..., description="Trial phase (e.g., Phase I, Phase II, Phase III)")
    status: FeasibilityStatus = Field(
        default=FeasibilityStatus.DRAFT, description="Current study status"
    )
    initiated_date: datetime = Field(..., description="Date the study was initiated")
    completed_date: datetime | None = Field(None, description="Date the study was completed")
    lead_analyst: str = Field(..., description="Name of the lead feasibility analyst")
    target_enrollment: int = Field(ge=1, description="Target number of patients to enroll")
    enrollment_duration_months: int = Field(ge=1, description="Planned enrollment duration in months")
    target_countries: list[str] = Field(
        default_factory=list, description="List of target countries for site selection"
    )
    target_sites_count: int = Field(ge=1, description="Target number of sites to activate")
    overall_feasibility_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Computed feasibility score (0-100)"
    )


class SiteAssessment(BaseModel):
    """Assessment of a potential investigator site for a feasibility study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique site assessment identifier")
    study_id: str = Field(..., description="Parent feasibility study identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Name of the site or institution")
    country: str = Field(..., description="Country where the site is located")
    investigator_name: str = Field(..., description="Principal investigator name")
    investigator_experience_years: int = Field(
        ge=0, description="Years of clinical trial experience"
    )
    competing_studies_count: int = Field(
        ge=0, description="Number of competing studies at this site"
    )
    patient_pool_estimate: int = Field(
        ge=0, description="Estimated relevant patient population at the site"
    )
    annual_enrollment_estimate: int = Field(
        ge=0, description="Estimated annual enrollment capacity"
    )
    site_rating: SiteRating = Field(..., description="Overall site feasibility rating")
    infrastructure_score: float = Field(
        ge=0.0, le=100.0, description="Score for site infrastructure readiness (0-100)"
    )
    regulatory_readiness: float = Field(
        ge=0.0, le=100.0, description="Score for regulatory readiness (0-100)"
    )
    staff_availability: float = Field(
        ge=0.0, le=100.0, description="Score for staff availability and qualifications (0-100)"
    )
    lab_capabilities: float = Field(
        ge=0.0, le=100.0, description="Score for laboratory capabilities (0-100)"
    )
    pharmacy_capabilities: float = Field(
        ge=0.0, le=100.0, description="Score for pharmacy capabilities (0-100)"
    )
    notes: str | None = Field(None, description="Additional assessment notes")
    assessed_date: datetime = Field(..., description="Date of the assessment")
    assessed_by: str = Field(..., description="Name of the assessor")


class CompetitiveLandscape(BaseModel):
    """A competing trial entry within the competitive landscape analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique competitive entry identifier")
    study_id: str = Field(..., description="Parent feasibility study identifier")
    competitor_trial_id: str = Field(..., description="ClinicalTrials.gov or internal trial ID")
    sponsor_name: str = Field(..., description="Competing trial sponsor name")
    phase: str = Field(..., description="Phase of the competing trial")
    indication: str = Field(..., description="Indication of the competing trial")
    estimated_enrollment: int = Field(
        ge=0, description="Estimated target enrollment of the competing trial"
    )
    enrollment_start_date: date | None = Field(
        None, description="Estimated or actual enrollment start date"
    )
    competing_sites_overlap: int = Field(
        ge=0, description="Number of sites overlapping with our candidate sites"
    )
    threat_level: CompetitiveThreatLevel = Field(
        ..., description="Assessed competitive threat level"
    )
    notes: str | None = Field(None, description="Additional notes about this competitor")


class EnrollmentProjection(BaseModel):
    """An enrollment projection scenario for a feasibility study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique enrollment projection identifier")
    study_id: str = Field(..., description="Parent feasibility study identifier")
    scenario_name: str = Field(..., description="Name of the projection scenario")
    sites_count: int = Field(ge=1, description="Number of sites assumed in this scenario")
    patients_per_site_per_month: float = Field(
        ge=0.0, description="Expected patients enrolled per site per month"
    )
    screen_failure_rate: float = Field(
        ge=0.0, le=1.0, description="Expected screen failure rate (0.0-1.0)"
    )
    dropout_rate: float = Field(
        ge=0.0, le=1.0, description="Expected dropout rate (0.0-1.0)"
    )
    enrollment_start_date: date | None = Field(
        None, description="Projected enrollment start date"
    )
    projected_enrollment_months: int = Field(
        ge=1, description="Projected months to complete enrollment"
    )
    projected_total_enrolled: int = Field(
        ge=0, description="Projected total number of patients enrolled"
    )
    confidence_level: float = Field(
        ge=0.0, le=100.0, description="Confidence level of this projection (0-100%)"
    )
    risk_level: EnrollmentRisk = Field(
        ..., description="Risk level associated with this scenario"
    )
    assumptions: str | None = Field(None, description="Key assumptions underlying the projection")


class FeasibilityQuestion(BaseModel):
    """A questionnaire question for site feasibility assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique question identifier")
    study_id: str = Field(..., description="Parent feasibility study identifier")
    category: str = Field(..., description="Question category (e.g., regulatory, logistics)")
    question_text: str = Field(..., description="The question text")
    response_type: str = Field(
        ..., description="Expected response type (text, number, yes_no, scale)"
    )
    required: bool = Field(default=True, description="Whether the question requires a response")
    display_order: int = Field(ge=1, description="Display order in the questionnaire")


class SiteQuestionnaireResponse(BaseModel):
    """A site's response to a feasibility questionnaire question."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique response identifier")
    study_id: str = Field(..., description="Parent feasibility study identifier")
    site_id: str = Field(..., description="Site that submitted the response")
    question_id: str = Field(..., description="Question being answered")
    response_value: str = Field(..., description="The response value")
    responded_date: datetime = Field(..., description="Date the response was submitted")
    responded_by: str = Field(..., description="Name of the person who submitted the response")


class FeasibilitySummary(BaseModel):
    """Aggregated summary of a feasibility study."""

    model_config = ConfigDict(from_attributes=True)

    study_id: str = Field(..., description="Feasibility study identifier")
    total_sites_assessed: int = Field(ge=0, description="Total number of sites assessed")
    sites_by_rating: dict[str, int] = Field(
        default_factory=dict, description="Site counts grouped by rating"
    )
    avg_feasibility_score: float = Field(
        ge=0.0, description="Average feasibility score across assessed sites"
    )
    projected_enrollment_range: dict[str, int] = Field(
        default_factory=dict,
        description="Min and max projected enrollment across scenarios",
    )
    top_risks: list[str] = Field(
        default_factory=list, description="Top identified risks"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Key recommendations from the study"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class FeasibilityStudyCreate(BaseModel):
    """Request to create a new feasibility study."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    protocol_id: str = Field(..., description="Protocol identifier")
    protocol_version: str = Field(..., description="Protocol version")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    indication: str = Field(..., description="Target indication")
    phase: str = Field(..., description="Trial phase")
    lead_analyst: str = Field(..., description="Lead feasibility analyst")
    target_enrollment: int = Field(ge=1, description="Target enrollment count")
    enrollment_duration_months: int = Field(ge=1, description="Enrollment duration in months")
    target_countries: list[str] = Field(default_factory=list, description="Target countries")
    target_sites_count: int = Field(ge=1, description="Target number of sites")


class FeasibilityStudyUpdate(BaseModel):
    """Request to update a feasibility study."""

    model_config = ConfigDict(from_attributes=True)

    protocol_version: str | None = Field(None, description="Protocol version")
    status: FeasibilityStatus | None = Field(None, description="Study status")
    lead_analyst: str | None = Field(None, description="Lead analyst")
    target_enrollment: int | None = Field(None, ge=1, description="Target enrollment")
    enrollment_duration_months: int | None = Field(None, ge=1, description="Enrollment duration")
    target_countries: list[str] | None = Field(None, description="Target countries")
    target_sites_count: int | None = Field(None, ge=1, description="Target sites count")


class SiteAssessmentCreate(BaseModel):
    """Request to create a site assessment."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    country: str = Field(..., description="Country")
    investigator_name: str = Field(..., description="Investigator name")
    investigator_experience_years: int = Field(ge=0, description="Experience years")
    competing_studies_count: int = Field(ge=0, description="Competing studies count")
    patient_pool_estimate: int = Field(ge=0, description="Patient pool estimate")
    annual_enrollment_estimate: int = Field(ge=0, description="Annual enrollment estimate")
    infrastructure_score: float = Field(ge=0.0, le=100.0, description="Infrastructure score")
    regulatory_readiness: float = Field(ge=0.0, le=100.0, description="Regulatory readiness")
    staff_availability: float = Field(ge=0.0, le=100.0, description="Staff availability")
    lab_capabilities: float = Field(ge=0.0, le=100.0, description="Lab capabilities")
    pharmacy_capabilities: float = Field(ge=0.0, le=100.0, description="Pharmacy capabilities")
    notes: str | None = Field(None, description="Notes")
    assessed_by: str = Field(..., description="Assessor name")


class SiteAssessmentUpdate(BaseModel):
    """Request to update a site assessment."""

    model_config = ConfigDict(from_attributes=True)

    investigator_name: str | None = Field(None, description="Investigator name")
    investigator_experience_years: int | None = Field(None, ge=0, description="Experience years")
    competing_studies_count: int | None = Field(None, ge=0, description="Competing studies")
    patient_pool_estimate: int | None = Field(None, ge=0, description="Patient pool")
    annual_enrollment_estimate: int | None = Field(None, ge=0, description="Annual enrollment")
    infrastructure_score: float | None = Field(None, ge=0.0, le=100.0, description="Infrastructure")
    regulatory_readiness: float | None = Field(None, ge=0.0, le=100.0, description="Regulatory")
    staff_availability: float | None = Field(None, ge=0.0, le=100.0, description="Staff")
    lab_capabilities: float | None = Field(None, ge=0.0, le=100.0, description="Lab")
    pharmacy_capabilities: float | None = Field(None, ge=0.0, le=100.0, description="Pharmacy")
    notes: str | None = Field(None, description="Notes")


class CompetitiveLandscapeCreate(BaseModel):
    """Request to add a competitive landscape entry."""

    model_config = ConfigDict(from_attributes=True)

    competitor_trial_id: str = Field(..., description="Competitor trial ID")
    sponsor_name: str = Field(..., description="Sponsor name")
    phase: str = Field(..., description="Trial phase")
    indication: str = Field(..., description="Indication")
    estimated_enrollment: int = Field(ge=0, description="Estimated enrollment")
    enrollment_start_date: date | None = Field(None, description="Enrollment start date")
    competing_sites_overlap: int = Field(ge=0, description="Sites overlap count")
    threat_level: CompetitiveThreatLevel = Field(..., description="Threat level")
    notes: str | None = Field(None, description="Notes")


class CompetitiveLandscapeUpdate(BaseModel):
    """Request to update a competitive landscape entry."""

    model_config = ConfigDict(from_attributes=True)

    sponsor_name: str | None = Field(None, description="Sponsor name")
    phase: str | None = Field(None, description="Phase")
    estimated_enrollment: int | None = Field(None, ge=0, description="Estimated enrollment")
    enrollment_start_date: date | None = Field(None, description="Start date")
    competing_sites_overlap: int | None = Field(None, ge=0, description="Sites overlap")
    threat_level: CompetitiveThreatLevel | None = Field(None, description="Threat level")
    notes: str | None = Field(None, description="Notes")


class EnrollmentProjectionCreate(BaseModel):
    """Request to create an enrollment projection scenario."""

    model_config = ConfigDict(from_attributes=True)

    scenario_name: str = Field(..., description="Scenario name")
    sites_count: int = Field(ge=1, description="Number of sites")
    patients_per_site_per_month: float = Field(ge=0.0, description="Patients per site per month")
    screen_failure_rate: float = Field(ge=0.0, le=1.0, description="Screen failure rate")
    dropout_rate: float = Field(ge=0.0, le=1.0, description="Dropout rate")
    enrollment_start_date: date | None = Field(None, description="Enrollment start date")
    assumptions: str | None = Field(None, description="Key assumptions")


class FeasibilityQuestionCreate(BaseModel):
    """Request to create a questionnaire question."""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(..., description="Question category")
    question_text: str = Field(..., description="Question text")
    response_type: str = Field(..., description="Response type (text, number, yes_no, scale)")
    required: bool = Field(default=True, description="Whether required")
    display_order: int = Field(ge=1, description="Display order")


class QuestionnaireResponseCreate(BaseModel):
    """Request to submit a questionnaire response."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    question_id: str = Field(..., description="Question identifier")
    response_value: str = Field(..., description="Response value")
    responded_by: str = Field(..., description="Responder name")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class FeasibilityStudyListResponse(BaseModel):
    """List of feasibility studies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FeasibilityStudy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteAssessmentListResponse(BaseModel):
    """List of site assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CompetitiveLandscapeListResponse(BaseModel):
    """List of competitive landscape entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CompetitiveLandscape] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EnrollmentProjectionListResponse(BaseModel):
    """List of enrollment projections."""

    model_config = ConfigDict(from_attributes=True)

    items: list[EnrollmentProjection] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class FeasibilityQuestionListResponse(BaseModel):
    """List of feasibility questions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FeasibilityQuestion] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteQuestionnaireResponseListResponse(BaseModel):
    """List of site questionnaire responses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteQuestionnaireResponse] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class FeasibilityMetrics(BaseModel):
    """Aggregated feasibility operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_studies: int = Field(ge=0, description="Total feasibility studies")
    active_studies: int = Field(ge=0, description="Studies in draft or in_progress status")
    avg_sites_per_study: float = Field(ge=0.0, description="Average sites assessed per study")
    avg_feasibility_score: float = Field(ge=0.0, description="Average feasibility score")
    sites_assessed_total: int = Field(ge=0, description="Total sites assessed across all studies")
    avg_enrollment_projection: float = Field(
        ge=0.0, description="Average projected enrollment across all scenarios"
    )
