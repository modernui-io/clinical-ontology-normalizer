"""Pydantic schemas for Regulatory Intelligence (REG-INTEL).

Tracks regulatory landscape changes, authority communications, guidance updates,
submission tracking across jurisdictions (FDA, EMA, PMDA, TGA, Health Canada),
regulatory risk assessments, and compliance gap analysis for clinical trials.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RegulatoryAuthority(str, Enum):
    """Regulatory authority / jurisdiction."""

    FDA = "fda"
    EMA = "ema"
    PMDA = "pmda"
    TGA = "tga"
    HEALTH_CANADA = "health_canada"
    MHRA = "mhra"
    ANVISA = "anvisa"
    NMPA = "nmpa"


class IntelligenceType(str, Enum):
    """Type of regulatory intelligence item."""

    GUIDANCE_UPDATE = "guidance_update"
    REGULATION_CHANGE = "regulation_change"
    ADVISORY_COMMITTEE = "advisory_committee"
    SAFETY_ALERT = "safety_alert"
    APPROVAL_DECISION = "approval_decision"
    INSPECTION_TREND = "inspection_trend"
    ENFORCEMENT_ACTION = "enforcement_action"
    POLICY_ANNOUNCEMENT = "policy_announcement"


class ImpactLevel(str, Enum):
    """Impact level on clinical operations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntelligenceStatus(str, Enum):
    """Processing status of a regulatory intelligence item."""

    NEW = "new"
    UNDER_REVIEW = "under_review"
    ASSESSED = "assessed"
    ACTION_REQUIRED = "action_required"
    IMPLEMENTED = "implemented"
    ARCHIVED = "archived"


class SubmissionType(str, Enum):
    """Type of regulatory submission."""

    IND = "ind"
    NDA = "nda"
    BLA = "bla"
    ANDA = "anda"
    CTA = "cta"
    MAA = "maa"
    AMENDMENT = "amendment"
    ANNUAL_REPORT = "annual_report"
    SAFETY_REPORT = "safety_report"


class SubmissionStatus(str, Enum):
    """Status of a regulatory submission."""

    DRAFTING = "drafting"
    INTERNAL_REVIEW = "internal_review"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    QUESTIONS_RECEIVED = "questions_received"
    APPROVED = "approved"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"


class GapSeverity(str, Enum):
    """Severity of a compliance gap."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class GapStatus(str, Enum):
    """Remediation status of a compliance gap."""

    IDENTIFIED = "identified"
    REMEDIATION_PLANNED = "remediation_planned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class RegulatoryIntelligenceItem(BaseModel):
    """A regulatory intelligence item tracking a landscape change."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique intelligence item identifier")
    authority: RegulatoryAuthority = Field(..., description="Issuing regulatory authority")
    intelligence_type: IntelligenceType = Field(..., description="Type of intelligence")
    title: str = Field(..., description="Title or headline of the intelligence item")
    summary: str = Field(..., description="Summary of the regulatory change or event")
    published_date: datetime = Field(..., description="Date published by the authority")
    effective_date: datetime | None = Field(None, description="Effective date of the change")
    impact_level: ImpactLevel = Field(..., description="Assessed impact on operations")
    affected_trials: list[str] = Field(default_factory=list, description="Trial IDs affected")
    affected_therapeutic_areas: list[str] = Field(
        default_factory=list, description="Therapeutic areas affected"
    )
    status: IntelligenceStatus = Field(
        default=IntelligenceStatus.NEW, description="Processing status"
    )
    assessed_by: str | None = Field(None, description="Person who assessed the item")
    assessed_date: datetime | None = Field(None, description="Date of assessment")
    action_items: list[str] = Field(default_factory=list, description="Required action items")
    source_url: str | None = Field(None, description="URL to the source document")
    created_at: datetime = Field(..., description="Record creation timestamp")


class RegulatorySubmissionTracker(BaseModel):
    """Tracks a regulatory submission across its lifecycle."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique submission tracker identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    authority: RegulatoryAuthority = Field(..., description="Target regulatory authority")
    submission_type: SubmissionType = Field(..., description="Type of submission")
    submission_number: str = Field(..., description="Submission reference number")
    title: str = Field(..., description="Submission title")
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFTING, description="Current submission status"
    )
    planned_date: datetime = Field(..., description="Planned submission date")
    actual_submission_date: datetime | None = Field(None, description="Actual submission date")
    response_date: datetime | None = Field(None, description="Date response received")
    target_approval_date: datetime | None = Field(None, description="Target approval date")
    lead_reviewer: str = Field(..., description="Internal lead reviewer")
    assigned_team: list[str] = Field(default_factory=list, description="Team members assigned")
    documents_included: list[str] = Field(
        default_factory=list, description="Documents included in submission"
    )
    questions_received: int = Field(default=0, ge=0, description="Number of questions received")
    responses_submitted: int = Field(default=0, ge=0, description="Number of responses submitted")
    created_at: datetime = Field(..., description="Record creation timestamp")


class ComplianceGap(BaseModel):
    """A compliance gap identified during regulatory assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique gap identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    authority: RegulatoryAuthority = Field(..., description="Relevant regulatory authority")
    regulation_reference: str = Field(..., description="Reference to the regulation or guidance")
    gap_description: str = Field(..., description="Description of the compliance gap")
    severity: GapSeverity = Field(..., description="Severity of the gap")
    status: GapStatus = Field(
        default=GapStatus.IDENTIFIED, description="Current remediation status"
    )
    identified_date: datetime = Field(..., description="Date the gap was identified")
    identified_by: str = Field(..., description="Person who identified the gap")
    remediation_plan: str | None = Field(None, description="Planned remediation steps")
    remediation_owner: str | None = Field(None, description="Person responsible for remediation")
    target_resolution_date: datetime | None = Field(None, description="Target resolution date")
    resolved_date: datetime | None = Field(None, description="Actual resolution date")
    evidence_of_closure: str | None = Field(None, description="Evidence that the gap is closed")


class AuthorityCommunication(BaseModel):
    """A communication to/from a regulatory authority."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique communication identifier")
    submission_id: str | None = Field(None, description="Related submission tracker ID")
    trial_id: str = Field(..., description="Associated trial identifier")
    authority: RegulatoryAuthority = Field(..., description="Regulatory authority")
    direction: str = Field(..., description="Direction: inbound or outbound")
    subject: str = Field(..., description="Communication subject")
    content_summary: str = Field(..., description="Summary of the communication content")
    communication_date: datetime = Field(..., description="Date of communication")
    response_deadline: datetime | None = Field(None, description="Deadline to respond")
    responded: bool = Field(default=False, description="Whether a response has been sent")
    response_date: datetime | None = Field(None, description="Date response was sent")
    handled_by: str = Field(..., description="Person who handled the communication")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class IntelligenceItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    authority: RegulatoryAuthority
    intelligence_type: IntelligenceType
    title: str
    summary: str
    published_date: datetime
    effective_date: datetime | None = None
    impact_level: ImpactLevel
    affected_trials: list[str] = Field(default_factory=list)
    affected_therapeutic_areas: list[str] = Field(default_factory=list)
    source_url: str | None = None


class IntelligenceItemUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    summary: str | None = None
    impact_level: ImpactLevel | None = None
    status: IntelligenceStatus | None = None
    assessed_by: str | None = None
    action_items: list[str] | None = None
    affected_trials: list[str] | None = None


class SubmissionTrackerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    authority: RegulatoryAuthority
    submission_type: SubmissionType
    submission_number: str
    title: str
    planned_date: datetime
    lead_reviewer: str
    assigned_team: list[str] = Field(default_factory=list)
    target_approval_date: datetime | None = None


class SubmissionTrackerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SubmissionStatus | None = None
    actual_submission_date: datetime | None = None
    response_date: datetime | None = None
    target_approval_date: datetime | None = None
    lead_reviewer: str | None = None
    assigned_team: list[str] | None = None
    questions_received: int | None = None
    responses_submitted: int | None = None


class ComplianceGapCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    authority: RegulatoryAuthority
    regulation_reference: str
    gap_description: str
    severity: GapSeverity
    identified_by: str
    remediation_plan: str | None = None
    remediation_owner: str | None = None
    target_resolution_date: datetime | None = None


class ComplianceGapUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity: GapSeverity | None = None
    status: GapStatus | None = None
    remediation_plan: str | None = None
    remediation_owner: str | None = None
    target_resolution_date: datetime | None = None
    evidence_of_closure: str | None = None


class AuthorityCommunicationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    submission_id: str | None = None
    trial_id: str
    authority: RegulatoryAuthority
    direction: str
    subject: str
    content_summary: str
    communication_date: datetime
    response_deadline: datetime | None = None
    handled_by: str


class AuthorityCommunicationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subject: str | None = None
    content_summary: str | None = None
    responded: bool | None = None
    response_date: datetime | None = None


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class IntelligenceItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegulatoryIntelligenceItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class SubmissionTrackerListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegulatorySubmissionTracker] = Field(default_factory=list)
    total: int = Field(ge=0)


class ComplianceGapListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplianceGap] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuthorityCommunicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AuthorityCommunication] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class RegulatoryIntelligenceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_intelligence_items: int = Field(ge=0)
    items_by_authority: dict[str, int] = Field(default_factory=dict)
    items_by_type: dict[str, int] = Field(default_factory=dict)
    items_by_status: dict[str, int] = Field(default_factory=dict)
    items_by_impact: dict[str, int] = Field(default_factory=dict)
    total_submissions: int = Field(ge=0)
    submissions_by_status: dict[str, int] = Field(default_factory=dict)
    submissions_by_authority: dict[str, int] = Field(default_factory=dict)
    pending_submissions: int = Field(ge=0)
    total_compliance_gaps: int = Field(ge=0)
    open_gaps: int = Field(ge=0)
    critical_gaps: int = Field(ge=0)
    gaps_by_severity: dict[str, int] = Field(default_factory=dict)
    total_communications: int = Field(ge=0)
    pending_responses: int = Field(ge=0)
    overdue_responses: int = Field(ge=0)
