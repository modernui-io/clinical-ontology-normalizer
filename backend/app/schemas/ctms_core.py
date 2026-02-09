"""Pydantic schemas for Clinical Trial Management System (CTMS) Core (CLINICAL-22).

Manages clinical trial operations: trial lifecycle management, site activation and
enrollment tracking, patient/subject management with visit scheduling, visit window
compliance, source data verification, and CTMS operational metrics.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TrialPhase(str, Enum):
    """Phase of a clinical trial."""

    PHASE1 = "phase1"
    PHASE1B = "phase1b"
    PHASE2 = "phase2"
    PHASE2B = "phase2b"
    PHASE3 = "phase3"
    PHASE3B = "phase3b"
    PHASE4 = "phase4"
    POST_MARKETING = "post_marketing"


class TrialStatus(str, Enum):
    """Lifecycle status of a clinical trial."""

    PLANNING = "planning"
    STARTUP = "startup"
    ENROLLING = "enrolling"
    FULLY_ENROLLED = "fully_enrolled"
    LAST_PATIENT_LAST_VISIT = "last_patient_last_visit"
    DATABASE_LOCK = "database_lock"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class TherapeuticArea(str, Enum):
    """Therapeutic area for a clinical trial."""

    ONCOLOGY = "oncology"
    IMMUNOLOGY = "immunology"
    OPHTHALMOLOGY = "ophthalmology"
    RARE_DISEASE = "rare_disease"
    NEUROLOGY = "neurology"
    CARDIOLOGY = "cardiology"
    INFECTIOUS_DISEASE = "infectious_disease"


class StudyDesign(str, Enum):
    """Study design classification."""

    PARALLEL = "parallel"
    CROSSOVER = "crossover"
    FACTORIAL = "factorial"
    SINGLE_ARM = "single_arm"
    BASKET = "basket"
    UMBRELLA = "umbrella"
    PLATFORM = "platform"
    ADAPTIVE = "adaptive"


class SiteStatus(str, Enum):
    """Status of a clinical trial site."""

    SELECTED = "selected"
    INITIATING = "initiating"
    ACTIVE = "active"
    ENROLLING = "enrolling"
    CLOSED_TO_ENROLLMENT = "closed_to_enrollment"
    CLOSED = "closed"


class PatientStatus(str, Enum):
    """Status of a patient/subject in a trial."""

    SCREENING = "screening"
    ENROLLED = "enrolled"
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    SCREEN_FAILED = "screen_failed"


class VisitStatus(str, Enum):
    """Status of a scheduled visit."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    MISSED = "missed"
    CANCELLED = "cancelled"
    IN_WINDOW = "in_window"
    OUT_OF_WINDOW = "out_of_window"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CTMSTrial(BaseModel):
    """A clinical trial managed in the CTMS."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique trial identifier")
    protocol_number: str = Field(..., description="Protocol number (e.g., R1234-ONC-5678)")
    title: str = Field(..., description="Full trial title")
    phase: TrialPhase = Field(..., description="Trial phase")
    status: TrialStatus = Field(..., description="Current trial status")
    therapeutic_area: TherapeuticArea = Field(..., description="Therapeutic area")
    study_design: StudyDesign = Field(..., description="Study design classification")
    indication: str = Field(..., description="Target indication/disease")
    sponsor: str = Field(..., description="Sponsor organization")
    start_date: date = Field(..., description="Trial start date")
    estimated_end_date: date = Field(..., description="Estimated completion date")
    actual_end_date: date | None = Field(None, description="Actual completion date")
    target_enrollment: int = Field(ge=0, description="Target enrollment count")
    current_enrollment: int = Field(ge=0, description="Current enrollment count")
    countries: list[str] = Field(default_factory=list, description="Countries with active sites")
    sites_planned: int = Field(ge=0, description="Number of planned sites")
    sites_active: int = Field(ge=0, description="Number of currently active sites")
    primary_endpoint: str = Field(..., description="Primary efficacy endpoint")
    secondary_endpoints: list[str] = Field(
        default_factory=list, description="Secondary efficacy endpoints"
    )
    regulatory_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Regulatory identifiers (e.g., FDA IND, EMA, PMDA)",
    )


class CTMSSite(BaseModel):
    """A clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique site identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_number: str = Field(..., description="Site number (e.g., SITE-001)")
    name: str = Field(..., description="Site/institution name")
    pi_name: str = Field(..., description="Principal Investigator name")
    address: str = Field(..., description="Site address")
    country: str = Field(..., description="Country")
    status: SiteStatus = Field(..., description="Site status")
    activation_date: date | None = Field(None, description="Date site was activated")
    first_patient_date: date | None = Field(None, description="Date of first patient enrolled")
    enrollment_target: int = Field(ge=0, description="Site enrollment target")
    enrolled_count: int = Field(default=0, ge=0, description="Number of patients enrolled")
    screen_failure_count: int = Field(
        default=0, ge=0, description="Number of screen failures at this site"
    )


class CTMSPatient(BaseModel):
    """A patient/subject enrolled in a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique patient identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Associated site identifier")
    subject_number: str = Field(..., description="Subject number (e.g., SUBJ-001)")
    screening_date: date = Field(..., description="Date of screening")
    randomization_date: date | None = Field(None, description="Date of randomization")
    treatment_arm: str | None = Field(None, description="Assigned treatment arm")
    current_visit: str | None = Field(None, description="Current/most recent visit")
    last_visit_date: date | None = Field(None, description="Date of last visit")
    status: PatientStatus = Field(..., description="Patient status")
    withdrawal_reason: str | None = Field(None, description="Reason for withdrawal if applicable")


class CTMSVisit(BaseModel):
    """A scheduled visit for a patient in a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique visit identifier")
    patient_id: str = Field(..., description="Associated patient identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    visit_number: int = Field(ge=0, description="Visit number in the schedule")
    visit_name: str = Field(..., description="Visit name (e.g., Screening, Week 4, Week 12)")
    scheduled_date: date = Field(..., description="Scheduled visit date")
    actual_date: date | None = Field(None, description="Actual visit date")
    window_start: date = Field(..., description="Visit window start date")
    window_end: date = Field(..., description="Visit window end date")
    status: VisitStatus = Field(..., description="Visit status")
    source_data_verified: bool = Field(
        default=False, description="Whether source data has been verified"
    )


class CTMSMetrics(BaseModel):
    """Aggregated CTMS operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_trials: int = Field(ge=0, description="Total number of trials")
    trials_by_phase: dict[str, int] = Field(
        default_factory=dict, description="Trial counts by phase"
    )
    trials_by_status: dict[str, int] = Field(
        default_factory=dict, description="Trial counts by status"
    )
    total_patients: int = Field(ge=0, description="Total patients across all trials")
    total_sites: int = Field(ge=0, description="Total sites across all trials")
    avg_enrollment_rate: float = Field(
        ge=0.0, description="Average enrollment rate (current/target) as percentage"
    )
    screen_failure_rate_overall: float = Field(
        ge=0.0, description="Overall screen failure rate as percentage"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class TrialCreate(BaseModel):
    """Request to create a new clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    protocol_number: str = Field(..., description="Protocol number")
    title: str = Field(..., description="Trial title")
    phase: TrialPhase = Field(..., description="Trial phase")
    therapeutic_area: TherapeuticArea = Field(..., description="Therapeutic area")
    study_design: StudyDesign = Field(..., description="Study design")
    indication: str = Field(..., description="Target indication")
    sponsor: str = Field(..., description="Sponsor organization")
    start_date: date = Field(..., description="Trial start date")
    estimated_end_date: date = Field(..., description="Estimated completion date")
    target_enrollment: int = Field(ge=1, description="Target enrollment count")
    countries: list[str] = Field(default_factory=list, description="Countries")
    sites_planned: int = Field(default=0, ge=0, description="Planned sites")
    primary_endpoint: str = Field(..., description="Primary endpoint")
    secondary_endpoints: list[str] = Field(
        default_factory=list, description="Secondary endpoints"
    )
    regulatory_ids: dict[str, str] = Field(
        default_factory=dict, description="Regulatory identifiers"
    )


class TrialUpdate(BaseModel):
    """Request to update a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Trial title")
    status: TrialStatus | None = Field(None, description="Trial status")
    estimated_end_date: date | None = Field(None, description="Estimated end date")
    actual_end_date: date | None = Field(None, description="Actual end date")
    target_enrollment: int | None = Field(None, ge=1, description="Target enrollment")
    countries: list[str] | None = Field(None, description="Countries")
    sites_planned: int | None = Field(None, ge=0, description="Planned sites")
    primary_endpoint: str | None = Field(None, description="Primary endpoint")
    secondary_endpoints: list[str] | None = Field(None, description="Secondary endpoints")
    regulatory_ids: dict[str, str] | None = Field(None, description="Regulatory identifiers")


class SiteCreate(BaseModel):
    """Request to create a new site for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    site_number: str = Field(..., description="Site number")
    name: str = Field(..., description="Site name")
    pi_name: str = Field(..., description="Principal Investigator name")
    address: str = Field(..., description="Site address")
    country: str = Field(..., description="Country")
    enrollment_target: int = Field(ge=0, description="Enrollment target")


class SiteUpdate(BaseModel):
    """Request to update a site."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Site name")
    pi_name: str | None = Field(None, description="PI name")
    address: str | None = Field(None, description="Address")
    status: SiteStatus | None = Field(None, description="Site status")
    activation_date: date | None = Field(None, description="Activation date")
    enrollment_target: int | None = Field(None, ge=0, description="Enrollment target")


class PatientCreate(BaseModel):
    """Request to create/screen a new patient."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    site_id: str = Field(..., description="Site ID")
    subject_number: str = Field(..., description="Subject number")
    screening_date: date = Field(..., description="Screening date")


class PatientUpdate(BaseModel):
    """Request to update a patient."""

    model_config = ConfigDict(from_attributes=True)

    randomization_date: date | None = Field(None, description="Randomization date")
    treatment_arm: str | None = Field(None, description="Treatment arm")
    status: PatientStatus | None = Field(None, description="Patient status")
    withdrawal_reason: str | None = Field(None, description="Withdrawal reason")


class VisitCreate(BaseModel):
    """Request to schedule a visit."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    trial_id: str = Field(..., description="Trial ID")
    visit_number: int = Field(ge=0, description="Visit number")
    visit_name: str = Field(..., description="Visit name")
    scheduled_date: date = Field(..., description="Scheduled date")
    window_start: date = Field(..., description="Window start")
    window_end: date = Field(..., description="Window end")


class VisitUpdate(BaseModel):
    """Request to update a visit."""

    model_config = ConfigDict(from_attributes=True)

    actual_date: date | None = Field(None, description="Actual visit date")
    status: VisitStatus | None = Field(None, description="Visit status")
    source_data_verified: bool | None = Field(None, description="SDV flag")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class TrialListResponse(BaseModel):
    """List of clinical trials."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CTMSTrial] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteListResponse(BaseModel):
    """List of trial sites."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CTMSSite] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PatientListResponse(BaseModel):
    """List of trial patients."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CTMSPatient] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class VisitListResponse(BaseModel):
    """List of visits."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CTMSVisit] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
