"""Pydantic schemas for Clinical Trial management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.trial import EnrollmentStatus, TrialPhase, TrialStatus


# ---------------------------------------------------------------------------
# CDS Disclaimer (Cures Act Criterion 4 compliance)
# ---------------------------------------------------------------------------

CDS_DISCLAIMER = (
    "This screening result is intended as clinical decision support only. "
    "A qualified healthcare professional must independently verify all "
    "eligibility determinations before any enrollment actions. This system "
    "does not make autonomous clinical decisions."
)


# ---------------------------------------------------------------------------
# Trial schemas
# ---------------------------------------------------------------------------

class TrialCreate(BaseModel):
    """Schema for creating a new clinical trial."""

    name: str = Field(..., description="Trial name/title")
    nct_number: str | None = Field(None, description="ClinicalTrials.gov NCT number")
    protocol_id: str | None = Field(None, description="Sponsor protocol identifier")
    sponsor: str | None = Field(None, description="Trial sponsor organization")
    phase: TrialPhase = Field(default=TrialPhase.PHASE_3, description="Trial phase")
    status: TrialStatus = Field(default=TrialStatus.DRAFT, description="Recruitment status")
    description: str | None = Field(None, description="Trial description/summary")
    therapeutic_area: str | None = Field(None, description="Therapeutic area (e.g., Dermatology, Oncology)")
    indication_codes: list[str] | None = Field(None, description="OMOP/SNOMED codes for target indications")
    inclusion_criteria: dict | None = Field(None, description="Inclusion criteria as cohort definition JSON")
    exclusion_criteria: dict | None = Field(None, description="Exclusion criteria as cohort definition JSON")
    enrollment_target: int = Field(default=100, ge=1, description="Target number of enrolled patients")
    site_count: int = Field(default=1, ge=1, description="Number of trial sites")
    start_date: datetime | None = Field(None, description="Trial start date")
    end_date: datetime | None = Field(None, description="Projected trial end date")


class TrialUpdate(BaseModel):
    """Schema for updating an existing trial."""

    name: str | None = None
    nct_number: str | None = None
    protocol_id: str | None = None
    sponsor: str | None = None
    phase: TrialPhase | None = None
    status: TrialStatus | None = None
    description: str | None = None
    therapeutic_area: str | None = None
    indication_codes: list[str] | None = None
    inclusion_criteria: dict | None = None
    exclusion_criteria: dict | None = None
    enrollment_target: int | None = None
    site_count: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class TrialResponse(BaseModel):
    """Full trial response with computed fields."""

    id: UUID
    name: str
    nct_number: str | None = None
    protocol_id: str | None = None
    sponsor: str | None = None
    phase: TrialPhase
    status: TrialStatus
    description: str | None = None
    therapeutic_area: str | None = None
    indication_codes: list[str] | None = None
    inclusion_criteria: dict | None = None
    exclusion_criteria: dict | None = None
    enrollment_target: int
    site_count: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime
    enrolled_count: int = Field(default=0, description="Current enrolled patient count")
    enrollment_progress: float = Field(default=0.0, description="Enrollment progress percentage")

    model_config = {"from_attributes": True}


class TrialSummary(BaseModel):
    """Lightweight trial summary for list views."""

    id: UUID
    name: str
    nct_number: str | None = None
    sponsor: str | None = None
    phase: TrialPhase
    status: TrialStatus
    therapeutic_area: str | None = None
    enrollment_target: int
    enrolled_count: int = 0
    enrollment_progress: float = 0.0
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Enrollment schemas
# ---------------------------------------------------------------------------

class EnrollmentCreate(BaseModel):
    """Schema for enrolling/screening a patient in a trial."""

    patient_id: str = Field(..., description="Patient identifier")
    enrollment_status: EnrollmentStatus = Field(
        default=EnrollmentStatus.CANDIDATE,
        description="Initial enrollment status",
    )
    site_id: str | None = Field(None, description="Trial site identifier")
    notes: str | None = Field(None, description="Enrollment notes")


class EnrollmentUpdate(BaseModel):
    """Schema for updating enrollment status."""

    enrollment_status: EnrollmentStatus | None = None
    withdrawal_reason: str | None = None
    notes: str | None = None


class EnrollmentResponse(BaseModel):
    """Full enrollment record response."""

    id: UUID
    trial_id: UUID
    patient_id: str
    enrollment_status: EnrollmentStatus
    match_score: float | None = None
    criteria_met: dict | None = None
    criteria_failed: dict | None = None
    screening_date: datetime | None = None
    enrollment_date: datetime | None = None
    withdrawal_date: datetime | None = None
    withdrawal_reason: str | None = None
    site_id: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Screening / matching schemas
# ---------------------------------------------------------------------------

class CriterionResult(BaseModel):
    """Detailed result for a single eligibility criterion.

    Provides an audit trail entry for regulatory compliance, capturing
    which ClinicalFacts were evaluated, the confidence of the match,
    and whether the criterion was met.
    """

    criterion_name: str = Field(..., description="Human-readable criterion name")
    criterion_type: str = Field(..., description="Type: condition, measurement, demographic")
    status: str = Field(..., description="PASS, FAIL, UNKNOWN, or POSSIBLE_MATCH")
    evidence_fact_ids: list[str] = Field(default_factory=list, description="ClinicalFact IDs supporting this result")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Max confidence from matching facts")
    details: str = Field(default="", description="Human-readable explanation")
    weight: float = Field(default=1.0, ge=0.0, description="Criterion importance weight for scoring")


class PatientEligibility(BaseModel):
    """Result of checking a single patient against trial criteria."""

    patient_id: str
    eligible: bool
    match_score: float = Field(ge=0.0, le=1.0, description="Overall match score 0-1")
    inclusion_met: list[str] = Field(default_factory=list, description="Inclusion criteria met")
    inclusion_total: int = Field(default=0, description="Total inclusion criteria")
    exclusion_triggered: list[str] = Field(default_factory=list, description="Exclusion criteria triggered")
    exclusion_total: int = Field(default=0, description="Total exclusion criteria")
    missing_data: list[str] = Field(default_factory=list, description="Criteria with insufficient data")
    criteria_details: list[CriterionResult] = Field(default_factory=list, description="Per-criterion audit trail")
    evaluable_criteria: int = Field(default=0, description="Criteria with enough data to evaluate")
    screening_timestamp: datetime | None = Field(default=None, description="When this screening was performed")
    requires_clinician_review: bool = Field(
        default=True,
        description="All eligibility results require independent clinician review (Cures Act Criterion 4)",
    )
    review_disclaimer: str = Field(
        default=CDS_DISCLAIMER,
        description="CDS disclaimer text for regulatory compliance",
    )


class ScreeningRequest(BaseModel):
    """Request to screen patients against trial eligibility criteria."""

    patient_ids: list[str] | None = Field(
        None,
        description="Specific patient IDs to screen (None = all patients)",
    )
    min_match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum match score to include in results",
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class ScreeningResponse(BaseModel):
    """Aggregated results of screening patients for a trial."""

    trial_id: UUID
    trial_name: str
    total_patients_screened: int
    eligible_count: int
    ineligible_count: int
    enrollment_target: int
    enrollment_rate: float = Field(description="Percentage of screened patients eligible")
    candidates: list[PatientEligibility] = Field(default_factory=list)
    demographics_summary: dict | None = Field(
        None,
        description="Age/gender/race breakdown of eligible patients",
    )
    exclusion_breakdown: dict | None = Field(
        None,
        description="Count of patients excluded by each criterion",
    )
    requires_clinician_review: bool = Field(
        default=True,
        description="All screening results require independent clinician review (Cures Act Criterion 4)",
    )
    cds_disclaimer: str = Field(
        default=CDS_DISCLAIMER,
        description="CDS disclaimer text for regulatory compliance",
    )


class TrialDashboard(BaseModel):
    """Dashboard summary for a trial's enrollment status."""

    trial_id: UUID
    trial_name: str
    status: TrialStatus
    phase: TrialPhase
    enrollment_target: int
    total_candidates: int = 0
    total_screened: int = 0
    total_eligible: int = 0
    total_enrolled: int = 0
    total_active: int = 0
    total_completed: int = 0
    total_withdrawn: int = 0
    total_screen_failed: int = 0
    enrollment_progress: float = 0.0
    site_count: int = 1
