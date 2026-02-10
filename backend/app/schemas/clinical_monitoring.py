"""Pydantic schemas for Clinical Monitoring (CLINICAL-18).

Manages CRA monitoring visit scheduling, source data verification (SDV),
query management, findings tracking, CAPA integration, monitoring reports,
and monitoring metrics from the CRO/CMO perspective.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VisitType(str, Enum):
    """Type of monitoring visit."""

    ROUTINE = "routine"
    FOR_CAUSE = "for_cause"
    CLOSEOUT = "closeout"
    REMOTE = "remote"
    TRIGGERED = "triggered"


class VisitStatus(str, Enum):
    """Lifecycle status of a monitoring visit."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REPORT_PENDING = "report_pending"


class FindingSeverity(str, Enum):
    """Severity level for monitoring findings."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"


class FindingCategory(str, Enum):
    """Category for monitoring findings."""

    INFORMED_CONSENT = "informed_consent"
    PROTOCOL_DEVIATION = "protocol_deviation"
    SOURCE_DATA = "source_data"
    REGULATORY = "regulatory"
    SAFETY_REPORTING = "safety_reporting"
    IP_MANAGEMENT = "ip_management"
    DATA_ENTRY = "data_entry"
    FACILITIES = "facilities"
    TRAINING = "training"


class FindingStatus(str, Enum):
    """Status of a monitoring finding."""

    OPEN = "open"
    RESPONSE_REQUIRED = "response_required"
    RESPONSE_RECEIVED = "response_received"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class SDVStatus(str, Enum):
    """Status of a source data verification record."""

    VERIFIED = "verified"
    DISCREPANCY = "discrepancy"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"


class CAPAStatus(str, Enum):
    """Status of a CAPA item."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    CLOSED = "closed"
    OVERDUE = "overdue"


class ReportStatus(str, Enum):
    """Status of a monitoring report."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    APPROVED = "approved"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class MonitoringVisit(BaseModel):
    """A CRA monitoring visit record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique monitoring visit identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    visit_type: VisitType = Field(..., description="Type of monitoring visit")
    status: VisitStatus = Field(default=VisitStatus.SCHEDULED, description="Visit status")
    cra_name: str = Field(..., description="Clinical Research Associate name")
    cra_id: str = Field(..., description="CRA identifier")
    scheduled_date: datetime = Field(..., description="Scheduled visit date")
    actual_start_date: datetime | None = Field(None, description="Actual visit start date")
    actual_end_date: datetime | None = Field(None, description="Actual visit end date")
    objectives: list[str] = Field(default_factory=list, description="Visit objectives")
    notes: str | None = Field(None, description="Visit notes")
    created_at: datetime = Field(..., description="Record creation timestamp")


class MonitoringFinding(BaseModel):
    """A monitoring finding record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique finding identifier")
    visit_id: str = Field(..., description="Associated monitoring visit")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    severity: FindingSeverity = Field(..., description="Finding severity")
    category: FindingCategory = Field(..., description="Finding category")
    status: FindingStatus = Field(default=FindingStatus.OPEN, description="Finding status")
    description: str = Field(..., description="Finding description")
    corrective_action: str | None = Field(None, description="Required corrective action")
    response: str | None = Field(None, description="Site response to finding")
    response_due_date: datetime | None = Field(None, description="Due date for site response")
    resolved_date: datetime | None = Field(None, description="Date finding was resolved")
    capa_id: str | None = Field(None, description="Associated CAPA item ID")
    created_at: datetime = Field(..., description="Record creation timestamp")


class SDVRecord(BaseModel):
    """A source data verification record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique SDV record identifier")
    visit_id: str = Field(..., description="Associated monitoring visit")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    subject_id: str = Field(..., description="Subject/patient identifier")
    form: str = Field(..., description="CRF form name")
    field: str = Field(..., description="CRF field name")
    status: SDVStatus = Field(default=SDVStatus.PENDING, description="SDV status")
    source_verified: bool = Field(default=False, description="Whether source data matches CRF")
    discrepancy_noted: bool = Field(default=False, description="Whether discrepancy was found")
    discrepancy_description: str | None = Field(None, description="Description of discrepancy")
    verified_by: str | None = Field(None, description="CRA who performed verification")
    verified_date: datetime | None = Field(None, description="Date of verification")
    created_at: datetime = Field(..., description="Record creation timestamp")


class MonitoringReport(BaseModel):
    """A monitoring visit report."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique report identifier")
    visit_id: str = Field(..., description="Associated monitoring visit")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    status: ReportStatus = Field(default=ReportStatus.DRAFT, description="Report status")
    summary: str = Field(..., description="Visit summary")
    findings_count: int = Field(default=0, ge=0, description="Number of findings")
    critical_findings: int = Field(default=0, ge=0, description="Number of critical findings")
    major_findings: int = Field(default=0, ge=0, description="Number of major findings")
    sdv_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="SDV completion rate (%)")
    subjects_reviewed: int = Field(default=0, ge=0, description="Subjects reviewed during visit")
    follow_up_items: list[str] = Field(default_factory=list, description="Follow-up action items")
    submitted_date: datetime | None = Field(None, description="Date report was submitted")
    approved_date: datetime | None = Field(None, description="Date report was approved")
    created_at: datetime = Field(..., description="Record creation timestamp")


class CAPAItem(BaseModel):
    """A Corrective and Preventive Action (CAPA) item."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique CAPA identifier")
    finding_id: str = Field(..., description="Associated finding identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    status: CAPAStatus = Field(default=CAPAStatus.OPEN, description="CAPA status")
    root_cause: str = Field(..., description="Root cause analysis")
    corrective_action: str = Field(..., description="Corrective action description")
    preventive_action: str = Field(..., description="Preventive action description")
    responsible_party: str = Field(..., description="Person responsible for CAPA")
    due_date: datetime = Field(..., description="CAPA due date")
    completion_date: datetime | None = Field(None, description="Date CAPA was completed")
    verification_date: datetime | None = Field(None, description="Date CAPA was verified")
    effectiveness_check: str | None = Field(None, description="Effectiveness check notes")
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class MonitoringVisitCreate(BaseModel):
    """Request to create a monitoring visit."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    visit_type: VisitType = Field(..., description="Type of monitoring visit")
    cra_name: str = Field(..., description="CRA name")
    cra_id: str = Field(..., description="CRA identifier")
    scheduled_date: datetime = Field(..., description="Scheduled visit date")
    objectives: list[str] = Field(default_factory=list, description="Visit objectives")
    notes: str | None = Field(None, description="Visit notes")


class MonitoringVisitUpdate(BaseModel):
    """Request to update a monitoring visit."""

    model_config = ConfigDict(from_attributes=True)

    visit_type: VisitType | None = Field(None, description="Type of monitoring visit")
    status: VisitStatus | None = Field(None, description="Visit status")
    cra_name: str | None = Field(None, description="CRA name")
    scheduled_date: datetime | None = Field(None, description="Scheduled visit date")
    objectives: list[str] | None = Field(None, description="Visit objectives")
    notes: str | None = Field(None, description="Visit notes")


class MonitoringFindingCreate(BaseModel):
    """Request to create a monitoring finding."""

    model_config = ConfigDict(from_attributes=True)

    visit_id: str = Field(..., description="Associated monitoring visit")
    severity: FindingSeverity = Field(..., description="Finding severity")
    category: FindingCategory = Field(..., description="Finding category")
    description: str = Field(..., description="Finding description")
    corrective_action: str | None = Field(None, description="Required corrective action")
    response_due_date: datetime | None = Field(None, description="Due date for site response")


class MonitoringFindingUpdate(BaseModel):
    """Request to update a monitoring finding."""

    model_config = ConfigDict(from_attributes=True)

    severity: FindingSeverity | None = Field(None, description="Finding severity")
    category: FindingCategory | None = Field(None, description="Finding category")
    status: FindingStatus | None = Field(None, description="Finding status")
    description: str | None = Field(None, description="Finding description")
    corrective_action: str | None = Field(None, description="Required corrective action")
    response: str | None = Field(None, description="Site response")
    response_due_date: datetime | None = Field(None, description="Due date for site response")


class SDVRecordCreate(BaseModel):
    """Request to create an SDV record."""

    model_config = ConfigDict(from_attributes=True)

    visit_id: str = Field(..., description="Associated monitoring visit")
    subject_id: str = Field(..., description="Subject/patient identifier")
    form: str = Field(..., description="CRF form name")
    field: str = Field(..., description="CRF field name")
    source_verified: bool = Field(default=False, description="Whether source data matches CRF")
    discrepancy_noted: bool = Field(default=False, description="Whether discrepancy was found")
    discrepancy_description: str | None = Field(None, description="Description of discrepancy")


class MonitoringReportCreate(BaseModel):
    """Request to create a monitoring report."""

    model_config = ConfigDict(from_attributes=True)

    visit_id: str = Field(..., description="Associated monitoring visit")
    summary: str = Field(..., description="Visit summary")
    follow_up_items: list[str] = Field(default_factory=list, description="Follow-up action items")


class MonitoringReportUpdate(BaseModel):
    """Request to update a monitoring report."""

    model_config = ConfigDict(from_attributes=True)

    summary: str | None = Field(None, description="Visit summary")
    status: ReportStatus | None = Field(None, description="Report status")
    follow_up_items: list[str] | None = Field(None, description="Follow-up action items")


class CAPAItemCreate(BaseModel):
    """Request to create a CAPA item."""

    model_config = ConfigDict(from_attributes=True)

    finding_id: str = Field(..., description="Associated finding identifier")
    root_cause: str = Field(..., description="Root cause analysis")
    corrective_action: str = Field(..., description="Corrective action description")
    preventive_action: str = Field(..., description="Preventive action description")
    responsible_party: str = Field(..., description="Person responsible for CAPA")
    due_date: datetime = Field(..., description="CAPA due date")


class CAPAItemUpdate(BaseModel):
    """Request to update a CAPA item."""

    model_config = ConfigDict(from_attributes=True)

    status: CAPAStatus | None = Field(None, description="CAPA status")
    root_cause: str | None = Field(None, description="Root cause analysis")
    corrective_action: str | None = Field(None, description="Corrective action description")
    preventive_action: str | None = Field(None, description="Preventive action description")
    responsible_party: str | None = Field(None, description="Person responsible")
    due_date: datetime | None = Field(None, description="CAPA due date")
    effectiveness_check: str | None = Field(None, description="Effectiveness check notes")


class VisitStartPayload(BaseModel):
    """Request to start a monitoring visit."""

    model_config = ConfigDict(from_attributes=True)

    actual_start_date: datetime = Field(..., description="Actual visit start date")


class VisitCompletePayload(BaseModel):
    """Request to complete a monitoring visit."""

    model_config = ConfigDict(from_attributes=True)

    actual_end_date: datetime = Field(..., description="Actual visit end date")


class ReportSubmitPayload(BaseModel):
    """Request to submit a monitoring report."""

    model_config = ConfigDict(from_attributes=True)

    submitted_date: datetime = Field(..., description="Submission date")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class MonitoringVisitListResponse(BaseModel):
    """List of monitoring visits."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MonitoringVisit] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MonitoringFindingListResponse(BaseModel):
    """List of monitoring findings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MonitoringFinding] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SDVRecordListResponse(BaseModel):
    """List of SDV records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SDVRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MonitoringReportListResponse(BaseModel):
    """List of monitoring reports."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MonitoringReport] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CAPAItemListResponse(BaseModel):
    """List of CAPA items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CAPAItem] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class SDVSiteSummary(BaseModel):
    """SDV summary for a single site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    total_records: int = Field(default=0, ge=0, description="Total SDV records")
    verified_count: int = Field(default=0, ge=0, description="Verified records")
    discrepancy_count: int = Field(default=0, ge=0, description="Records with discrepancies")
    sdv_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="SDV rate (%)")


class SiteMonitoringSummary(BaseModel):
    """Monitoring summary for a single site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    total_visits: int = Field(default=0, ge=0, description="Total monitoring visits")
    completed_visits: int = Field(default=0, ge=0, description="Completed visits")
    open_findings: int = Field(default=0, ge=0, description="Open findings count")
    critical_findings: int = Field(default=0, ge=0, description="Critical findings count")
    sdv_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="SDV rate (%)")
    open_capas: int = Field(default=0, ge=0, description="Open CAPA items")
    last_visit_date: datetime | None = Field(None, description="Date of last completed visit")


class MonitoringMetrics(BaseModel):
    """Aggregated monitoring metrics across all trials."""

    model_config = ConfigDict(from_attributes=True)

    total_visits: int = Field(default=0, ge=0, description="Total monitoring visits")
    visits_completed: int = Field(default=0, ge=0, description="Completed visits")
    visits_by_type: dict[str, int] = Field(default_factory=dict, description="Visits by type")
    visits_by_status: dict[str, int] = Field(default_factory=dict, description="Visits by status")
    total_findings: int = Field(default=0, ge=0, description="Total findings")
    open_findings: int = Field(default=0, ge=0, description="Open findings")
    findings_by_severity: dict[str, int] = Field(
        default_factory=dict, description="Findings by severity"
    )
    findings_by_category: dict[str, int] = Field(
        default_factory=dict, description="Findings by category"
    )
    overall_sdv_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall SDV rate (%)")
    total_sdv_records: int = Field(default=0, ge=0, description="Total SDV records")
    total_capas: int = Field(default=0, ge=0, description="Total CAPA items")
    open_capas: int = Field(default=0, ge=0, description="Open CAPA items")
    capa_closure_rate: float = Field(
        default=0.0, ge=0.0, le=100.0, description="CAPA closure rate (%)"
    )
    total_reports: int = Field(default=0, ge=0, description="Total monitoring reports")
    reports_pending_review: int = Field(default=0, ge=0, description="Reports pending review")
