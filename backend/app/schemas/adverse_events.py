"""Pydantic schemas for Adverse Event Monitoring & Safety Reporting (CMO-9).

Tracks adverse events across clinical trials, detects safety signals via
statistical analysis, manages expedited regulatory reporting obligations,
and provides safety dashboard metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AESeverity(str, Enum):
    """Severity grading of an adverse event."""

    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    LIFE_THREATENING = "LIFE_THREATENING"
    FATAL = "FATAL"


class AERelatedness(str, Enum):
    """Causality assessment of an adverse event to study treatment."""

    UNRELATED = "UNRELATED"
    UNLIKELY = "UNLIKELY"
    POSSIBLE = "POSSIBLE"
    PROBABLE = "PROBABLE"
    DEFINITE = "DEFINITE"


class AEStatus(str, Enum):
    """Lifecycle status of an adverse event."""

    REPORTED = "REPORTED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class AECategory(str, Enum):
    """System Organ Class category for adverse events."""

    GENERAL = "GENERAL"
    CARDIOVASCULAR = "CARDIOVASCULAR"
    NEUROLOGICAL = "NEUROLOGICAL"
    GASTROINTESTINAL = "GASTROINTESTINAL"
    DERMATOLOGICAL = "DERMATOLOGICAL"
    HEPATIC = "HEPATIC"
    RENAL = "RENAL"
    HEMATOLOGICAL = "HEMATOLOGICAL"
    RESPIRATORY = "RESPIRATORY"
    MUSCULOSKELETAL = "MUSCULOSKELETAL"
    IMMUNOLOGICAL = "IMMUNOLOGICAL"
    OPHTHALMIC = "OPHTHALMIC"


class AEActionTaken(str, Enum):
    """Action taken with study treatment in response to the adverse event."""

    NONE = "NONE"
    DOSE_REDUCED = "DOSE_REDUCED"
    DOSE_INTERRUPTED = "DOSE_INTERRUPTED"
    DISCONTINUED = "DISCONTINUED"
    OTHER = "OTHER"


class AEOutcome(str, Enum):
    """Outcome of the adverse event."""

    RECOVERED = "RECOVERED"
    RECOVERING = "RECOVERING"
    NOT_RECOVERED = "NOT_RECOVERED"
    FATAL = "FATAL"
    UNKNOWN = "UNKNOWN"


class ExpeditedReportType(str, Enum):
    """Type of expedited regulatory report."""

    IND_SAFETY = "IND_SAFETY"
    SUSAR = "SUSAR"
    CIOMS = "CIOMS"


class ExpeditedReportStatus(str, Enum):
    """Status of an expedited report."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OVERDUE = "OVERDUE"


class SafetySignalStatus(str, Enum):
    """Status of a detected safety signal."""

    NEW = "NEW"
    INVESTIGATING = "INVESTIGATING"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class AdverseEvent(BaseModel):
    """A single adverse event record with full clinical detail."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique adverse event identifier")
    trial_id: str = Field(..., description="Trial the AE belongs to")
    patient_id: str = Field(..., description="Patient who experienced the AE")
    site_id: str = Field(..., description="Site where the AE was reported")
    event_term: str = Field(..., description="Reported adverse event term")
    preferred_term: str = Field(..., description="MedDRA preferred term")
    category: AECategory = Field(..., description="System organ class category")
    severity: AESeverity = Field(..., description="Severity grading")
    relatedness: AERelatedness = Field(..., description="Causality assessment")
    serious: bool = Field(default=False, description="Whether this is a Serious Adverse Event (SAE)")
    expected: bool = Field(default=True, description="Whether the AE is listed in the IB/label")
    status: AEStatus = Field(
        default=AEStatus.REPORTED, description="Current lifecycle status"
    )
    onset_date: datetime = Field(..., description="Date of AE onset")
    resolution_date: datetime | None = Field(None, description="Date the AE resolved")
    reported_date: datetime = Field(..., description="Date the AE was reported")
    reporter: str = Field(..., description="Person who reported the AE")
    description: str = Field(..., description="Detailed description of the AE")
    action_taken: AEActionTaken = Field(
        default=AEActionTaken.NONE, description="Action taken with study treatment"
    )
    outcome: AEOutcome = Field(
        default=AEOutcome.UNKNOWN, description="Outcome of the AE"
    )
    requires_expedited_reporting: bool = Field(
        default=False, description="Whether expedited regulatory reporting is required"
    )
    expedited_report_date: datetime | None = Field(
        None, description="Date the expedited report was submitted"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class SafetySignal(BaseModel):
    """A detected safety signal from statistical analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique signal identifier")
    signal_term: str = Field(..., description="Adverse event term triggering the signal")
    trials_affected: list[str] = Field(
        default_factory=list, description="Trial IDs where the signal was observed"
    )
    events_count: int = Field(ge=0, description="Number of events contributing to the signal")
    expected_rate: float = Field(ge=0.0, description="Expected background rate")
    observed_rate: float = Field(ge=0.0, description="Observed rate in trial population")
    relative_risk: float = Field(ge=0.0, description="Relative risk (observed / expected)")
    p_value: float = Field(ge=0.0, le=1.0, description="Statistical p-value")
    detected_at: datetime = Field(..., description="When the signal was detected")
    status: SafetySignalStatus = Field(
        default=SafetySignalStatus.NEW, description="Current signal status"
    )
    assessed_by: str | None = Field(None, description="Person who assessed the signal")


class ExpeditedReport(BaseModel):
    """An expedited regulatory safety report."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique report identifier")
    ae_id: str = Field(..., description="Linked adverse event ID")
    report_type: ExpeditedReportType = Field(..., description="Type of expedited report")
    regulatory_body: str = Field(..., description="Regulatory authority (e.g., FDA, EMA)")
    due_date: datetime = Field(..., description="Regulatory submission deadline")
    submitted_date: datetime | None = Field(None, description="Actual submission date")
    status: ExpeditedReportStatus = Field(
        default=ExpeditedReportStatus.PENDING, description="Report status"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class AECreate(BaseModel):
    """Request payload for reporting a new adverse event."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial the AE belongs to")
    patient_id: str = Field(..., description="Patient who experienced the AE")
    site_id: str = Field(..., description="Site where the AE was reported")
    event_term: str = Field(..., description="Reported adverse event term")
    preferred_term: str = Field(..., description="MedDRA preferred term")
    category: AECategory = Field(default=AECategory.GENERAL, description="System organ class")
    severity: AESeverity = Field(..., description="Severity grading")
    relatedness: AERelatedness = Field(
        default=AERelatedness.POSSIBLE, description="Causality assessment"
    )
    serious: bool = Field(default=False, description="Whether this is an SAE")
    expected: bool = Field(default=True, description="Whether the AE is expected")
    onset_date: datetime = Field(..., description="Date of AE onset")
    reporter: str = Field(..., description="Person who reported the AE")
    description: str = Field(..., description="Detailed description")
    action_taken: AEActionTaken = Field(
        default=AEActionTaken.NONE, description="Action taken"
    )
    outcome: AEOutcome = Field(default=AEOutcome.UNKNOWN, description="Outcome")


class AEUpdate(BaseModel):
    """Request payload for updating an existing adverse event."""

    model_config = ConfigDict(from_attributes=True)

    status: AEStatus | None = Field(None, description="New status")
    severity: AESeverity | None = Field(None, description="Updated severity")
    relatedness: AERelatedness | None = Field(None, description="Updated relatedness")
    serious: bool | None = Field(None, description="Updated serious flag")
    expected: bool | None = Field(None, description="Updated expected flag")
    resolution_date: datetime | None = Field(None, description="Resolution date")
    action_taken: AEActionTaken | None = Field(None, description="Updated action taken")
    outcome: AEOutcome | None = Field(None, description="Updated outcome")
    description: str | None = Field(None, description="Updated description")


class AEListResponse(BaseModel):
    """Paginated list of adverse events."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AdverseEvent] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
    limit: int = Field(ge=1, description="Page size")
    offset: int = Field(ge=0, description="Page offset")


class SafetySignalListResponse(BaseModel):
    """List of safety signals."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetySignal] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total signals")


class ExpeditedReportListResponse(BaseModel):
    """List of expedited reports."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ExpeditedReport] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total reports")


class ExpeditedReportSubmitRequest(BaseModel):
    """Request to submit an expedited report."""

    report_type: ExpeditedReportType = Field(..., description="Type of report")
    regulatory_body: str = Field(..., description="Regulatory authority")


class CausalityFactor(BaseModel):
    """A single factor in the Naranjo causality assessment."""

    model_config = ConfigDict(from_attributes=True)

    question: str = Field(..., description="Naranjo algorithm question")
    answer: str = Field(..., description="yes / no / unknown")
    score: int = Field(..., description="Score contribution for this factor")


class CausalityAssessment(BaseModel):
    """Result of a Naranjo-based causality assessment."""

    model_config = ConfigDict(from_attributes=True)

    ae_id: str = Field(..., description="Adverse event assessed")
    total_score: int = Field(..., description="Naranjo total score")
    classification: AERelatedness = Field(
        ..., description="Derived relatedness classification"
    )
    factors: list[CausalityFactor] = Field(
        default_factory=list, description="Individual factor scores"
    )


class NarrativeReport(BaseModel):
    """Auto-generated MedWatch-style narrative for an adverse event."""

    model_config = ConfigDict(from_attributes=True)

    ae_id: str = Field(..., description="Adverse event ID")
    narrative: str = Field(..., description="Generated narrative text")
    generated_at: datetime = Field(..., description="Generation timestamp")


class SafetySignalUpdateRequest(BaseModel):
    """Request to update safety signal status."""

    status: SafetySignalStatus = Field(..., description="New signal status")
    assessed_by: str | None = Field(None, description="Assessor name")


class MostCommonEvent(BaseModel):
    """A frequently occurring adverse event term with count."""

    model_config = ConfigDict(from_attributes=True)

    event_term: str = Field(..., description="Adverse event term")
    count: int = Field(ge=0, description="Number of occurrences")


class AEMetrics(BaseModel):
    """Aggregated adverse event metrics for safety dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_events: int = Field(ge=0, description="Total adverse events")
    serious_count: int = Field(ge=0, description="Number of serious adverse events")
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Count per severity level"
    )
    by_category: dict[str, int] = Field(
        default_factory=dict, description="Count per SOC category"
    )
    by_trial: dict[str, int] = Field(
        default_factory=dict, description="Count per trial"
    )
    mean_time_to_resolution_days: float | None = Field(
        None, description="Average days from onset to resolution"
    )
    expedited_reporting_compliance_rate: float = Field(
        ge=0.0, le=1.0, default=0.0,
        description="Fraction of required expedited reports submitted on time",
    )
    active_safety_signals: int = Field(
        ge=0, default=0, description="Number of active (non-dismissed) safety signals"
    )
    most_common_events: list[MostCommonEvent] = Field(
        default_factory=list, description="Most frequently reported AE terms"
    )
