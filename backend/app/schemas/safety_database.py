"""Pydantic schemas for Safety Database & CIOMS Reporting (CLINICAL-23).

Manages safety database operations: individual case safety reports (ICSRs),
regulatory submissions with expedited timelines (15-day/7-day), CIOMS I/II
form generation, aggregate safety reports (DSUR, PSUR, PBRER, ASR),
MedDRA coding, seriousness/expectedness/relatedness classification,
and safety database operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CaseType(str, Enum):
    """Type of safety case report."""

    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    AMENDMENT = "amendment"


class Seriousness(str, Enum):
    """ICH E2A seriousness criteria."""

    DEATH = "death"
    LIFE_THREATENING = "life_threatening"
    HOSPITALIZATION = "hospitalization"
    DISABILITY = "disability"
    CONGENITAL_ANOMALY = "congenital_anomaly"
    MEDICALLY_IMPORTANT = "medically_important"


class Expectedness(str, Enum):
    """Expectedness classification against reference safety information."""

    EXPECTED = "expected"
    UNEXPECTED = "unexpected"


class Relatedness(str, Enum):
    """Causality assessment between suspect drug and event."""

    RELATED = "related"
    POSSIBLY_RELATED = "possibly_related"
    UNLIKELY_RELATED = "unlikely_related"
    UNRELATED = "unrelated"
    NOT_ASSESSABLE = "not_assessable"


class ReportingStatus(str, Enum):
    """Lifecycle status of a safety case."""

    DRAFT = "draft"
    SUBMITTED_TO_SPONSOR = "submitted_to_sponsor"
    SUBMITTED_TO_AUTHORITY = "submitted_to_authority"
    CLOSED = "closed"


class CIOMSFormType(str, Enum):
    """Regulatory reporting form type."""

    CIOMS_I = "cioms_i"
    CIOMS_II = "cioms_ii"
    MEDWATCH_3500A = "medwatch_3500a"
    E2B_R3 = "e2b_r3"


class RegulatoryAuthority(str, Enum):
    """Regulatory authority for submissions."""

    FDA = "FDA"
    EMA = "EMA"
    PMDA = "PMDA"
    TGA = "TGA"
    MHRA = "MHRA"
    HC = "HC"


class SubmissionStatus(str, Enum):
    """Status of a regulatory submission."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    CLOSED = "closed"


class AggregateReportType(str, Enum):
    """Type of aggregate safety report."""

    DSUR = "DSUR"
    PSUR = "PSUR"
    PBRER = "PBRER"
    ASR = "ASR"


class AggregateReportStatus(str, Enum):
    """Status of an aggregate safety report."""

    DRAFTING = "drafting"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"


class EventOutcome(str, Enum):
    """Outcome of the adverse event."""

    RECOVERED = "recovered"
    RECOVERING = "recovering"
    NOT_RECOVERED = "not_recovered"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class ReporterType(str, Enum):
    """Type of initial reporter."""

    PHYSICIAN = "physician"
    PHARMACIST = "pharmacist"
    NURSE = "nurse"
    PATIENT = "patient"
    OTHER_HCP = "other_hcp"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class RegulatorySubmission(BaseModel):
    """A regulatory submission for a safety case."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique submission identifier")
    case_id: str = Field(..., description="Associated safety case ID")
    authority: RegulatoryAuthority = Field(..., description="Regulatory authority")
    form_type: CIOMSFormType = Field(..., description="Reporting form type")
    submission_date: datetime | None = Field(None, description="Date submitted")
    due_date: datetime = Field(..., description="Regulatory deadline")
    acknowledgment_date: datetime | None = Field(None, description="Authority acknowledgment date")
    status: SubmissionStatus = Field(default=SubmissionStatus.PENDING, description="Submission status")


class SafetyCase(BaseModel):
    """Individual Case Safety Report (ICSR)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique case identifier")
    case_number: str = Field(..., description="Formatted case number (e.g., CASE-2026-0001)")
    trial_id: str = Field(..., description="Clinical trial identifier")
    patient_id: str = Field(..., description="Patient/subject identifier")
    site_id: str = Field(..., description="Site identifier")
    case_type: CaseType = Field(..., description="Case type (initial/follow-up/amendment)")
    initial_receipt_date: datetime = Field(..., description="Date case first received by sponsor")
    most_recent_date: datetime = Field(..., description="Date of most recent information")
    seriousness_criteria: list[Seriousness] = Field(
        default_factory=list, description="Applicable seriousness criteria"
    )
    expectedness: Expectedness = Field(..., description="Expected or unexpected per RSI")
    relatedness: Relatedness = Field(..., description="Causality assessment")
    reporter_type: ReporterType = Field(..., description="Type of initial reporter")
    narrative: str = Field(..., description="Case narrative summary")
    meddra_pt: str = Field(..., description="MedDRA Preferred Term")
    meddra_soc: str = Field(..., description="MedDRA System Organ Class")
    onset_date: datetime = Field(..., description="Event onset date")
    resolution_date: datetime | None = Field(None, description="Event resolution date")
    outcome: EventOutcome = Field(..., description="Event outcome")
    reporting_status: ReportingStatus = Field(
        default=ReportingStatus.DRAFT, description="Case reporting status"
    )
    regulatory_submissions: list[RegulatorySubmission] = Field(
        default_factory=list, description="Associated regulatory submissions"
    )


class CIOMSForm(BaseModel):
    """CIOMS/MedWatch form data for regulatory submission."""

    model_config = ConfigDict(from_attributes=True)

    case_id: str = Field(..., description="Associated safety case ID")
    form_type: CIOMSFormType = Field(..., description="Form type")
    patient_initials: str = Field(..., description="Patient initials")
    age: int = Field(..., ge=0, le=120, description="Patient age")
    sex: str = Field(..., description="Patient sex (M/F/Unknown)")
    reaction_terms: list[str] = Field(default_factory=list, description="MedDRA reaction terms")
    suspect_drug: str = Field(..., description="Suspect drug name")
    dose: str = Field(..., description="Drug dose and frequency")
    route: str = Field(..., description="Route of administration")
    indication: str = Field(..., description="Indication for use")
    event_onset: datetime = Field(..., description="Event onset date")
    event_outcome: EventOutcome = Field(..., description="Event outcome")
    reporter_assessment: Relatedness = Field(..., description="Reporter causality assessment")
    company_assessment: Relatedness = Field(..., description="Sponsor/company causality assessment")


class AggregateReport(BaseModel):
    """Aggregate safety report (DSUR, PSUR, PBRER, ASR)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique report identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    report_type: AggregateReportType = Field(..., description="Type of aggregate report")
    period_start: datetime = Field(..., description="Reporting period start date")
    period_end: datetime = Field(..., description="Reporting period end date")
    due_date: datetime = Field(..., description="Submission due date")
    submission_date: datetime | None = Field(None, description="Actual submission date")
    status: AggregateReportStatus = Field(
        default=AggregateReportStatus.DRAFTING, description="Report status"
    )
    total_cases: int = Field(default=0, ge=0, description="Total cases in period")
    serious_cases: int = Field(default=0, ge=0, description="Serious cases in period")
    fatal_cases: int = Field(default=0, ge=0, description="Fatal cases in period")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SafetyCaseCreate(BaseModel):
    """Request to create a new safety case."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    patient_id: str = Field(..., description="Patient identifier")
    site_id: str = Field(..., description="Site identifier")
    case_type: CaseType = Field(default=CaseType.INITIAL, description="Case type")
    seriousness_criteria: list[Seriousness] = Field(
        default_factory=list, description="Seriousness criteria"
    )
    expectedness: Expectedness = Field(..., description="Expectedness classification")
    relatedness: Relatedness = Field(..., description="Causality assessment")
    reporter_type: ReporterType = Field(default=ReporterType.PHYSICIAN, description="Reporter type")
    narrative: str = Field(..., description="Case narrative")
    meddra_pt: str = Field(..., description="MedDRA Preferred Term")
    meddra_soc: str = Field(..., description="MedDRA System Organ Class")
    onset_date: datetime = Field(..., description="Event onset date")
    resolution_date: datetime | None = Field(None, description="Event resolution date")
    outcome: EventOutcome = Field(..., description="Event outcome")


class SafetyCaseUpdate(BaseModel):
    """Request to update a safety case."""

    model_config = ConfigDict(from_attributes=True)

    case_type: CaseType | None = Field(None, description="Case type")
    seriousness_criteria: list[Seriousness] | None = Field(None, description="Seriousness criteria")
    expectedness: Expectedness | None = Field(None, description="Expectedness")
    relatedness: Relatedness | None = Field(None, description="Relatedness")
    narrative: str | None = Field(None, description="Case narrative")
    meddra_pt: str | None = Field(None, description="MedDRA PT")
    meddra_soc: str | None = Field(None, description="MedDRA SOC")
    resolution_date: datetime | None = Field(None, description="Resolution date")
    outcome: EventOutcome | None = Field(None, description="Outcome")
    reporting_status: ReportingStatus | None = Field(None, description="Reporting status")


class RegulatorySubmissionCreate(BaseModel):
    """Request to create a regulatory submission for a case."""

    model_config = ConfigDict(from_attributes=True)

    authority: RegulatoryAuthority = Field(..., description="Regulatory authority")
    form_type: CIOMSFormType = Field(..., description="Form type")
    due_date: datetime = Field(..., description="Submission deadline")


class RegulatorySubmissionUpdate(BaseModel):
    """Request to update a regulatory submission."""

    model_config = ConfigDict(from_attributes=True)

    submission_date: datetime | None = Field(None, description="Submission date")
    acknowledgment_date: datetime | None = Field(None, description="Acknowledgment date")
    status: SubmissionStatus | None = Field(None, description="Status")


class AggregateReportCreate(BaseModel):
    """Request to create an aggregate safety report."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    report_type: AggregateReportType = Field(..., description="Report type")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    due_date: datetime = Field(..., description="Due date")


class AggregateReportUpdate(BaseModel):
    """Request to update an aggregate report."""

    model_config = ConfigDict(from_attributes=True)

    status: AggregateReportStatus | None = Field(None, description="Status")
    submission_date: datetime | None = Field(None, description="Submission date")
    total_cases: int | None = Field(None, ge=0, description="Total cases")
    serious_cases: int | None = Field(None, ge=0, description="Serious cases")
    fatal_cases: int | None = Field(None, ge=0, description="Fatal cases")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SafetyCaseListResponse(BaseModel):
    """List of safety cases."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetyCase] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RegulatorySubmissionListResponse(BaseModel):
    """List of regulatory submissions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatorySubmission] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CIOMSFormListResponse(BaseModel):
    """List of CIOMS forms."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CIOMSForm] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class AggregateReportListResponse(BaseModel):
    """List of aggregate safety reports."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AggregateReport] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class SafetyDatabaseMetrics(BaseModel):
    """Aggregated Safety Database operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_cases: int = Field(ge=0, description="Total safety cases in database")
    cases_by_seriousness: dict[str, int] = Field(
        default_factory=dict, description="Case counts by seriousness criterion"
    )
    cases_by_relatedness: dict[str, int] = Field(
        default_factory=dict, description="Case counts by relatedness classification"
    )
    overdue_submissions: int = Field(ge=0, description="Number of overdue regulatory submissions")
    avg_submission_time_days: float = Field(
        ge=0.0, description="Average time from receipt to submission in days"
    )
    aggregate_reports_due: int = Field(
        ge=0, description="Number of aggregate reports with upcoming due dates"
    )
    total_submissions: int = Field(ge=0, description="Total regulatory submissions")
    pending_submissions: int = Field(ge=0, description="Submissions pending completion")
    cases_by_outcome: dict[str, int] = Field(
        default_factory=dict, description="Case counts by event outcome"
    )
    fatal_cases: int = Field(ge=0, description="Total fatal cases")
    unexpected_serious_cases: int = Field(
        ge=0, description="Unexpected serious cases (SUSARs)"
    )
