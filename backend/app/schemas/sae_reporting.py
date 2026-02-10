"""Pydantic schemas for SAE Regulatory Reporting (CLINICAL-SAE).

Manages serious adverse event (SAE) regulatory reporting lifecycle: SAE intake,
expedited reporting (7-day/15-day), regulatory authority submission, MedWatch/CIOMS
form generation, causality assessment, narrative writing, and safety metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SAESeriousness(str, Enum):
    """ICH E2A seriousness criteria for SAE classification."""

    DEATH = "death"
    LIFE_THREATENING = "life_threatening"
    HOSPITALIZATION = "hospitalization"
    DISABILITY = "disability"
    CONGENITAL_ANOMALY = "congenital_anomaly"
    IMPORTANT_MEDICAL_EVENT = "important_medical_event"


class SAEOutcome(str, Enum):
    """Outcome of the serious adverse event."""

    RECOVERED = "recovered"
    RECOVERING = "recovering"
    NOT_RECOVERED = "not_recovered"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class CausalityAssessment(str, Enum):
    """Investigator/sponsor causality assessment."""

    RELATED = "related"
    POSSIBLY_RELATED = "possibly_related"
    UNLIKELY_RELATED = "unlikely_related"
    NOT_RELATED = "not_related"
    NOT_ASSESSABLE = "not_assessable"


class ReportType(str, Enum):
    """Type of SAE report in the reporting sequence."""

    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    FINAL = "final"


class RegulatoryAuthority(str, Enum):
    """Target regulatory authority for submission."""

    FDA = "fda"
    EMA = "ema"
    MHRA = "mhra"
    PMDA = "pmda"
    HEALTH_CANADA = "health_canada"


class ReportingTimeline(str, Enum):
    """Expedited reporting timeline requirement."""

    SEVEN_DAY = "seven_day"
    FIFTEEN_DAY = "fifteen_day"
    THIRTY_DAY = "thirty_day"


class SAEStatus(str, Enum):
    """Lifecycle status of an SAE report."""

    DRAFT = "draft"
    MEDICAL_REVIEW = "medical_review"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CausalityRecord(BaseModel):
    """A causality assessment record for an SAE."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique causality record identifier")
    sae_report_id: str = Field(..., description="Parent SAE report identifier")
    assessor: str = Field(..., description="Name/role of the assessor (e.g., 'Investigator', 'Sponsor Medical Monitor')")
    assessment: CausalityAssessment = Field(..., description="Causality assessment determination")
    rationale: str = Field(..., description="Rationale for the assessment")
    assessed_date: datetime = Field(..., description="Date of assessment")


class RegulatorySubmission(BaseModel):
    """A regulatory submission record for an SAE report."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique submission identifier")
    sae_report_id: str = Field(..., description="Parent SAE report identifier")
    authority: RegulatoryAuthority = Field(..., description="Regulatory authority")
    submission_type: ReportType = Field(..., description="Type of submission (initial, follow_up, final)")
    submitted_date: datetime = Field(..., description="Date of submission")
    acknowledgment_number: str | None = Field(None, description="Acknowledgment number from authority")
    acknowledgment_date: datetime | None = Field(None, description="Date acknowledgment received")


class SAENarrative(BaseModel):
    """Narrative sections for an SAE report."""

    model_config = ConfigDict(from_attributes=True)

    sae_report_id: str = Field(..., description="Parent SAE report identifier")
    initial_narrative: str = Field(..., description="Initial SAE narrative description")
    follow_up_narratives: list[str] = Field(
        default_factory=list, description="Follow-up narrative updates"
    )
    medical_review_notes: list[str] = Field(
        default_factory=list, description="Medical reviewer notes and comments"
    )


class SAEReport(BaseModel):
    """A serious adverse event report."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique SAE report identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier where SAE occurred")
    subject_id: str = Field(..., description="Subject/patient identifier")
    report_type: ReportType = Field(..., description="Report type (initial, follow_up, final)")
    status: SAEStatus = Field(default=SAEStatus.DRAFT, description="Report lifecycle status")
    seriousness: SAESeriousness = Field(..., description="Seriousness criteria")
    outcome: SAEOutcome = Field(..., description="SAE outcome")
    event_description: str = Field(..., description="Description of the adverse event")
    event_term: str = Field(..., description="Preferred term for the event (MedDRA)")
    study_drug: str = Field(..., description="Study drug name")
    onset_date: datetime = Field(..., description="Date of SAE onset")
    awareness_date: datetime = Field(..., description="Date sponsor became aware")
    reporting_timeline: ReportingTimeline = Field(..., description="Required reporting timeline")
    reporting_deadline: datetime = Field(..., description="Regulatory reporting deadline")
    causality_records: list[CausalityRecord] = Field(
        default_factory=list, description="Causality assessment records"
    )
    regulatory_submissions: list[RegulatorySubmission] = Field(
        default_factory=list, description="Regulatory submissions for this SAE"
    )
    narrative: SAENarrative | None = Field(None, description="SAE narrative")
    parent_report_id: str | None = Field(None, description="Parent report ID for follow-up/final reports")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class MedWatchForm(BaseModel):
    """Auto-generated FDA MedWatch 3500A form data."""

    model_config = ConfigDict(from_attributes=True)

    sae_report_id: str = Field(..., description="SAE report identifier")
    form_version: str = Field(default="3500A", description="MedWatch form version")
    patient_identifier: str = Field(..., description="Patient identifier (de-identified)")
    patient_age: int | None = Field(None, description="Patient age")
    patient_sex: str | None = Field(None, description="Patient sex")
    event_description: str = Field(..., description="Event description for MedWatch")
    event_term: str = Field(..., description="MedDRA preferred term")
    event_onset_date: datetime = Field(..., description="Event onset date")
    event_outcome: str = Field(..., description="Event outcome")
    suspect_product: str = Field(..., description="Suspect product name")
    dose_and_frequency: str = Field(..., description="Dose and frequency of suspect product")
    therapy_start_date: datetime | None = Field(None, description="Therapy start date")
    therapy_end_date: datetime | None = Field(None, description="Therapy end date")
    indication: str = Field(..., description="Indication for use")
    reporter_name: str = Field(..., description="Reporter name")
    reporter_type: str = Field(..., description="Reporter type (e.g., physician, pharmacist)")
    report_date: datetime = Field(..., description="Report date")
    seriousness_criteria: list[str] = Field(
        default_factory=list, description="Applicable seriousness criteria"
    )
    narrative_summary: str = Field(..., description="Narrative summary for MedWatch")
    generated_at: datetime = Field(..., description="Form generation timestamp")


class CIOMSForm(BaseModel):
    """Auto-generated CIOMS I form data for international reporting."""

    model_config = ConfigDict(from_attributes=True)

    sae_report_id: str = Field(..., description="SAE report identifier")
    form_version: str = Field(default="CIOMS-I", description="CIOMS form version")
    reaction_onset_date: datetime = Field(..., description="Reaction onset date")
    reaction_end_date: datetime | None = Field(None, description="Reaction end date")
    reaction_description: str = Field(..., description="Reaction description")
    reaction_outcome: str = Field(..., description="Reaction outcome")
    seriousness_criteria: list[str] = Field(
        default_factory=list, description="Seriousness criteria"
    )
    suspect_drug: str = Field(..., description="Suspect drug name")
    daily_dose: str = Field(..., description="Daily dose")
    route_of_administration: str = Field(..., description="Route of administration")
    indication: str = Field(..., description="Indication for use")
    therapy_dates: str = Field(..., description="Therapy date range")
    dechallenge: str | None = Field(None, description="Dechallenge result")
    rechallenge: str | None = Field(None, description="Rechallenge result")
    concomitant_medications: list[str] = Field(
        default_factory=list, description="Concomitant medications"
    )
    patient_initials: str = Field(..., description="Patient initials")
    study_number: str = Field(..., description="Study/protocol number")
    reporter_country: str = Field(..., description="Reporter country")
    date_of_report: datetime = Field(..., description="Date of this report")
    sender_organization: str = Field(..., description="Sending organization")
    narrative_summary: str = Field(..., description="Narrative summary")
    generated_at: datetime = Field(..., description="Form generation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SAEReportCreate(BaseModel):
    """Request to create a new SAE report."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    subject_id: str = Field(..., description="Subject identifier")
    seriousness: SAESeriousness = Field(..., description="Seriousness criteria")
    outcome: SAEOutcome = Field(..., description="SAE outcome")
    event_description: str = Field(..., description="Description of the adverse event")
    event_term: str = Field(..., description="MedDRA preferred term")
    study_drug: str = Field(..., description="Study drug name")
    onset_date: datetime = Field(..., description="Date of SAE onset")
    awareness_date: datetime = Field(..., description="Date sponsor became aware")
    initial_narrative: str = Field(..., description="Initial SAE narrative")


class SAEReportUpdate(BaseModel):
    """Request to update an SAE report."""

    model_config = ConfigDict(from_attributes=True)

    seriousness: SAESeriousness | None = Field(None, description="Seriousness criteria")
    outcome: SAEOutcome | None = Field(None, description="SAE outcome")
    event_description: str | None = Field(None, description="Event description")
    event_term: str | None = Field(None, description="MedDRA preferred term")


class CausalityRecordCreate(BaseModel):
    """Request to create a causality assessment."""

    model_config = ConfigDict(from_attributes=True)

    assessor: str = Field(..., description="Assessor name/role")
    assessment: CausalityAssessment = Field(..., description="Causality assessment")
    rationale: str = Field(..., description="Assessment rationale")


class RegulatorySubmissionCreate(BaseModel):
    """Request to create a regulatory submission."""

    model_config = ConfigDict(from_attributes=True)

    authority: RegulatoryAuthority = Field(..., description="Regulatory authority")
    submission_type: ReportType = Field(..., description="Submission type")
    submitted_date: datetime = Field(..., description="Date of submission")
    acknowledgment_number: str | None = Field(None, description="Acknowledgment number")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SAEReportListResponse(BaseModel):
    """List of SAE reports."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SAEReport] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CausalityRecordListResponse(BaseModel):
    """List of causality records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CausalityRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RegulatorySubmissionListResponse(BaseModel):
    """List of regulatory submissions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatorySubmission] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class SAEMetrics(BaseModel):
    """Aggregated SAE reporting metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_saes: int = Field(ge=0, description="Total SAE reports")
    by_seriousness: dict[str, int] = Field(
        default_factory=dict, description="SAE counts by seriousness"
    )
    by_causality: dict[str, int] = Field(
        default_factory=dict, description="SAE counts by causality assessment"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="SAE counts by status"
    )
    avg_reporting_time_hours: float = Field(
        ge=0.0, description="Average time from awareness to submission (hours)"
    )
    overdue_reports: int = Field(
        ge=0, description="Number of reports past their reporting deadline"
    )
    total_submissions: int = Field(
        ge=0, description="Total regulatory submissions"
    )
    submissions_by_authority: dict[str, int] = Field(
        default_factory=dict, description="Submission counts by regulatory authority"
    )


class TrialSafetySummary(BaseModel):
    """Safety summary for a specific trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    total_saes: int = Field(ge=0, description="Total SAEs for this trial")
    by_seriousness: dict[str, int] = Field(
        default_factory=dict, description="SAE counts by seriousness"
    )
    by_outcome: dict[str, int] = Field(
        default_factory=dict, description="SAE counts by outcome"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="SAE counts by status"
    )
    overdue_reports: int = Field(
        ge=0, description="Overdue reports for this trial"
    )
    recent_saes: list[SAEReport] = Field(
        default_factory=list, description="Most recent SAE reports (up to 5)"
    )
