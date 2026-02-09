"""Pydantic schemas for Medical Review & Lab Data Review (CLINICAL-14).

Manages medical review operations: review task assignment and tracking, medical
coding (MedDRA AE terms, WHODrug conmeds) with auto-coding confidence scoring,
data listing generation, medical signal detection with risk ratio calculation,
review prioritization, and overdue escalation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReviewStatus(str, Enum):
    """Status of a medical review task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class ReviewPriority(str, Enum):
    """Priority classification for a medical review task."""

    ROUTINE = "routine"
    URGENT = "urgent"
    CRITICAL = "critical"


class ReviewType(str, Enum):
    """Type of medical review."""

    AE_REVIEW = "ae_review"
    LAB_REVIEW = "lab_review"
    CONMED_REVIEW = "conmed_review"
    ELIGIBILITY_REVIEW = "eligibility_review"
    MEDICAL_HISTORY_REVIEW = "medical_history_review"


class CodingDictionary(str, Enum):
    """Medical coding dictionary."""

    MEDDRA = "meddra"
    WHODRUG = "whodrug"
    SNOMED = "snomed"
    ICD10 = "icd10"


class CodingStatus(str, Enum):
    """Status of a coding task."""

    UNCODED = "uncoded"
    AUTO_CODED = "auto_coded"
    MANUALLY_CODED = "manually_coded"
    VERIFIED = "verified"
    QUERY_RAISED = "query_raised"


class CodingLevel(str, Enum):
    """MedDRA hierarchy level or equivalent for other dictionaries."""

    PT = "pt"
    LLT = "llt"
    HLT = "hlt"
    HLGT = "hlgt"
    SOC = "soc"


class ListingType(str, Enum):
    """Type of data listing."""

    AE_LISTING = "ae_listing"
    CONMED_LISTING = "conmed_listing"
    LAB_LISTING = "lab_listing"
    MEDHIST_LISTING = "medhist_listing"
    VITALS_LISTING = "vitals_listing"


class SignalCategory(str, Enum):
    """Medical signal classification."""

    EXPECTED = "expected"
    UNEXPECTED = "unexpected"
    SERIOUS_UNEXPECTED = "serious_unexpected"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class MedicalReviewTask(BaseModel):
    """A medical review task assigned to a reviewer."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique review task identifier")
    trial_id: str = Field(..., description="Trial identifier")
    patient_id: str = Field(..., description="Patient identifier")
    review_type: ReviewType = Field(..., description="Type of medical review")
    status: ReviewStatus = Field(
        default=ReviewStatus.PENDING, description="Current review status"
    )
    priority: ReviewPriority = Field(
        default=ReviewPriority.ROUTINE, description="Review priority"
    )
    assigned_reviewer: str = Field(..., description="Name of assigned medical reviewer")
    created_date: datetime = Field(..., description="Date the review task was created")
    completed_date: datetime | None = Field(
        None, description="Date the review was completed"
    )
    findings: str | None = Field(None, description="Review findings and notes")
    actions_taken: str | None = Field(
        None, description="Actions taken based on the review"
    )


class CodingTask(BaseModel):
    """A medical coding task for a verbatim term."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique coding task identifier")
    verbatim_term: str = Field(..., description="Original verbatim term from CRF")
    dictionary: CodingDictionary = Field(..., description="Coding dictionary used")
    coded_term: str | None = Field(None, description="Coded preferred term")
    coded_code: str | None = Field(None, description="Coded term code")
    level: CodingLevel = Field(
        default=CodingLevel.PT, description="Hierarchy level (pt, llt, hlt, hlgt, soc)"
    )
    status: CodingStatus = Field(
        default=CodingStatus.UNCODED, description="Coding status"
    )
    auto_coded: bool = Field(default=False, description="Whether auto-coded by system")
    confidence_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Auto-coding confidence score (0.0-1.0)"
    )
    coder: str | None = Field(None, description="Coder who performed manual coding")
    verified_by: str | None = Field(None, description="Reviewer who verified the coding")


class DataListing(BaseModel):
    """A generated data listing for review."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique listing identifier")
    trial_id: str = Field(..., description="Trial identifier")
    listing_type: ListingType = Field(..., description="Type of data listing")
    generated_date: datetime = Field(..., description="Date the listing was generated")
    record_count: int = Field(ge=0, description="Number of records in the listing")
    flagged_records: int = Field(
        ge=0, default=0, description="Number of flagged/anomalous records"
    )
    filters_applied: dict[str, str] = Field(
        default_factory=dict, description="Filters applied to generate the listing"
    )


class MedicalSignal(BaseModel):
    """A detected medical signal from safety data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique signal identifier")
    trial_id: str = Field(..., description="Trial identifier")
    signal_category: SignalCategory = Field(
        ..., description="Signal classification (expected, unexpected, serious_unexpected)"
    )
    term: str = Field(..., description="Medical term associated with the signal")
    observed_count: int = Field(ge=0, description="Observed event count")
    expected_count: int = Field(ge=0, description="Expected event count based on background rate")
    patients_affected: int = Field(ge=0, description="Number of patients affected")
    risk_ratio: float = Field(ge=0.0, description="Risk ratio (observed / expected)")
    p_value: float = Field(
        ge=0.0, le=1.0, description="Statistical p-value for the signal"
    )
    assessment: str = Field(..., description="Medical assessment of the signal")
    action_required: bool = Field(
        default=False, description="Whether action is required based on the signal"
    )


class MedicalReviewMetrics(BaseModel):
    """Aggregated medical review operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_tasks: int = Field(ge=0, description="Total review tasks")
    tasks_by_status: dict[str, int] = Field(
        default_factory=dict, description="Task counts by status"
    )
    avg_review_time_hours: float = Field(
        ge=0.0, description="Average review completion time in hours"
    )
    coding_accuracy_rate: float = Field(
        ge=0.0, le=1.0, description="Rate of coding tasks verified without changes"
    )
    auto_coding_rate: float = Field(
        ge=0.0, le=1.0, description="Percentage of tasks auto-coded by the system"
    )
    open_signals: int = Field(ge=0, description="Number of signals requiring action")
    overdue_reviews: int = Field(ge=0, description="Number of overdue review tasks")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class MedicalReviewTaskCreate(BaseModel):
    """Request to create a medical review task."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    patient_id: str = Field(..., description="Patient ID")
    review_type: ReviewType = Field(..., description="Type of review")
    priority: ReviewPriority = Field(
        default=ReviewPriority.ROUTINE, description="Review priority"
    )
    assigned_reviewer: str = Field(..., description="Assigned reviewer name")


class MedicalReviewTaskUpdate(BaseModel):
    """Request to update a medical review task."""

    model_config = ConfigDict(from_attributes=True)

    status: ReviewStatus | None = Field(None, description="Review status")
    priority: ReviewPriority | None = Field(None, description="Review priority")
    assigned_reviewer: str | None = Field(None, description="Assigned reviewer")
    findings: str | None = Field(None, description="Review findings")
    actions_taken: str | None = Field(None, description="Actions taken")


class CodingTaskCreate(BaseModel):
    """Request to create a coding task."""

    model_config = ConfigDict(from_attributes=True)

    verbatim_term: str = Field(..., description="Verbatim term from CRF")
    dictionary: CodingDictionary = Field(..., description="Dictionary to use")
    level: CodingLevel = Field(default=CodingLevel.PT, description="Hierarchy level")


class CodingTaskUpdate(BaseModel):
    """Request to update a coding task."""

    model_config = ConfigDict(from_attributes=True)

    coded_term: str | None = Field(None, description="Coded term")
    coded_code: str | None = Field(None, description="Coded code")
    level: CodingLevel | None = Field(None, description="Level")
    status: CodingStatus | None = Field(None, description="Status")
    coder: str | None = Field(None, description="Coder name")
    verified_by: str | None = Field(None, description="Verifier name")


class DataListingCreate(BaseModel):
    """Request to generate a data listing."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    listing_type: ListingType = Field(..., description="Type of listing")
    filters_applied: dict[str, str] = Field(
        default_factory=dict, description="Filters to apply"
    )


class MedicalSignalCreate(BaseModel):
    """Request to create a medical signal record."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    signal_category: SignalCategory = Field(..., description="Signal category")
    term: str = Field(..., description="Medical term")
    observed_count: int = Field(ge=0, description="Observed count")
    expected_count: int = Field(ge=0, description="Expected count")
    patients_affected: int = Field(ge=0, description="Patients affected")
    assessment: str = Field(..., description="Medical assessment")


class MedicalSignalUpdate(BaseModel):
    """Request to update a medical signal record."""

    model_config = ConfigDict(from_attributes=True)

    signal_category: SignalCategory | None = Field(None, description="Signal category")
    assessment: str | None = Field(None, description="Assessment")
    action_required: bool | None = Field(None, description="Action required flag")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class MedicalReviewTaskListResponse(BaseModel):
    """List of medical review tasks."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MedicalReviewTask] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CodingTaskListResponse(BaseModel):
    """List of coding tasks."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CodingTask] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DataListingListResponse(BaseModel):
    """List of data listings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DataListing] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MedicalSignalListResponse(BaseModel):
    """List of medical signals."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MedicalSignal] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
