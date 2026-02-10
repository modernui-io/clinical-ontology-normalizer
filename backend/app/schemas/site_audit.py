"""Pydantic schemas for Site Audit Management (QA-AUDIT).

Manages GCP audits, regulatory inspections, sponsor-initiated audits, CRO
audits, and for-cause audits at clinical trial sites. Covers audit planning,
execution, findings classification, CAPA tracking, audit report lifecycle,
and audit metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AuditType(str, Enum):
    """Type of site audit."""

    ROUTINE = "routine"
    FOR_CAUSE = "for_cause"
    REGULATORY_INSPECTION = "regulatory_inspection"
    PRE_APPROVAL = "pre_approval"
    SYSTEMS_AUDIT = "systems_audit"
    CRO_OVERSIGHT = "cro_oversight"
    VENDOR_AUDIT = "vendor_audit"


class AuditStatus(str, Enum):
    """Lifecycle status of an audit."""

    PLANNED = "planned"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    REPORT_DRAFTING = "report_drafting"
    REPORT_REVIEW = "report_review"
    FINALIZED = "finalized"
    CLOSED = "closed"


class FindingClassification(str, Enum):
    """Classification of an audit finding."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"


class FindingStatus(str, Enum):
    """Status of an audit finding."""

    OPEN = "open"
    CAPA_ASSIGNED = "capa_assigned"
    IN_REMEDIATION = "in_remediation"
    VERIFICATION_PENDING = "verification_pending"
    CLOSED = "closed"


class CAPAStatus(str, Enum):
    """Status of a corrective/preventive action."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    CLOSED = "closed"
    OVERDUE = "overdue"


class ReportStatus(str, Enum):
    """Status of an audit report."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DISTRIBUTED = "distributed"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SiteAudit(BaseModel):
    """A site audit record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique audit identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site being audited")
    site_name: str = Field(..., description="Site name")
    audit_type: AuditType = Field(..., description="Type of audit")
    status: AuditStatus = Field(default=AuditStatus.PLANNED, description="Audit lifecycle status")
    planned_date: datetime = Field(..., description="Planned audit date")
    actual_start_date: datetime | None = Field(None, description="Actual audit start date")
    actual_end_date: datetime | None = Field(None, description="Actual audit end date")
    lead_auditor: str = Field(..., description="Lead auditor name")
    audit_team: list[str] = Field(default_factory=list, description="Audit team members")
    scope: str = Field(..., description="Audit scope description")
    regulatory_authority: str | None = Field(None, description="Regulatory authority if inspection")
    created_at: datetime = Field(..., description="Record creation timestamp")


class AuditFinding(BaseModel):
    """A finding identified during an audit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique finding identifier")
    audit_id: str = Field(..., description="Associated audit identifier")
    finding_number: str = Field(..., description="Finding reference number")
    classification: FindingClassification = Field(..., description="Finding classification")
    area: str = Field(..., description="Area of the finding (e.g., informed consent, source data)")
    description: str = Field(..., description="Detailed finding description")
    evidence: str = Field(..., description="Supporting evidence")
    regulation_reference: str | None = Field(None, description="Regulation/GCP reference violated")
    status: FindingStatus = Field(default=FindingStatus.OPEN, description="Finding status")
    response_deadline: datetime | None = Field(None, description="Deadline for site response")
    site_response: str | None = Field(None, description="Site's response to the finding")
    created_at: datetime = Field(..., description="Record creation timestamp")


class AuditCAPA(BaseModel):
    """A corrective/preventive action for an audit finding."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique CAPA identifier")
    finding_id: str = Field(..., description="Associated finding identifier")
    audit_id: str = Field(..., description="Associated audit identifier")
    corrective_action: str = Field(..., description="Corrective action description")
    preventive_action: str = Field(..., description="Preventive action description")
    responsible_party: str = Field(..., description="Person responsible for implementation")
    due_date: datetime = Field(..., description="Implementation due date")
    status: CAPAStatus = Field(default=CAPAStatus.PLANNED, description="CAPA status")
    completion_date: datetime | None = Field(None, description="Date CAPA was completed")
    verification_date: datetime | None = Field(None, description="Date CAPA was verified effective")
    verified_by: str | None = Field(None, description="Person who verified effectiveness")
    effectiveness_evidence: str | None = Field(None, description="Evidence of CAPA effectiveness")


class AuditReport(BaseModel):
    """A formal audit report."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique report identifier")
    audit_id: str = Field(..., description="Associated audit identifier")
    report_number: str = Field(..., description="Report reference number")
    title: str = Field(..., description="Report title")
    executive_summary: str = Field(..., description="Executive summary of findings")
    status: ReportStatus = Field(default=ReportStatus.DRAFT, description="Report status")
    author: str = Field(..., description="Report author")
    reviewed_by: str | None = Field(None, description="Reviewer")
    approved_by: str | None = Field(None, description="Approver")
    approved_date: datetime | None = Field(None, description="Approval date")
    total_findings: int = Field(default=0, ge=0, description="Total findings in this audit")
    critical_findings: int = Field(default=0, ge=0, description="Number of critical findings")
    major_findings: int = Field(default=0, ge=0, description="Number of major findings")
    minor_findings: int = Field(default=0, ge=0, description="Number of minor findings")
    observations: int = Field(default=0, ge=0, description="Number of observations")
    distribution_list: list[str] = Field(default_factory=list, description="Report distribution list")
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SiteAuditCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    site_name: str
    audit_type: AuditType
    planned_date: datetime
    lead_auditor: str
    audit_team: list[str] = Field(default_factory=list)
    scope: str
    regulatory_authority: str | None = None


class SiteAuditUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AuditStatus | None = None
    actual_start_date: datetime | None = None
    actual_end_date: datetime | None = None
    lead_auditor: str | None = None
    audit_team: list[str] | None = None
    scope: str | None = None


class AuditFindingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    audit_id: str
    finding_number: str
    classification: FindingClassification
    area: str
    description: str
    evidence: str
    regulation_reference: str | None = None
    response_deadline: datetime | None = None


class AuditFindingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    classification: FindingClassification | None = None
    description: str | None = None
    status: FindingStatus | None = None
    site_response: str | None = None


class AuditCAPACreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    finding_id: str
    audit_id: str
    corrective_action: str
    preventive_action: str
    responsible_party: str
    due_date: datetime


class AuditCAPAUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    corrective_action: str | None = None
    preventive_action: str | None = None
    status: CAPAStatus | None = None
    verified_by: str | None = None
    effectiveness_evidence: str | None = None


class AuditReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    audit_id: str
    report_number: str
    title: str
    executive_summary: str
    author: str


class AuditReportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    executive_summary: str | None = None
    status: ReportStatus | None = None
    reviewed_by: str | None = None
    approved_by: str | None = None


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SiteAuditListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteAudit] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuditFindingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AuditFinding] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuditCAPAListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AuditCAPA] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuditReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AuditReport] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class SiteAuditMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_audits: int = Field(ge=0)
    audits_by_type: dict[str, int] = Field(default_factory=dict)
    audits_by_status: dict[str, int] = Field(default_factory=dict)
    total_findings: int = Field(ge=0)
    findings_by_classification: dict[str, int] = Field(default_factory=dict)
    open_findings: int = Field(ge=0)
    closed_findings: int = Field(ge=0)
    total_capas: int = Field(ge=0)
    open_capas: int = Field(ge=0)
    overdue_capas: int = Field(ge=0)
    total_reports: int = Field(ge=0)
    approved_reports: int = Field(ge=0)
    avg_findings_per_audit: float = Field(ge=0.0)
