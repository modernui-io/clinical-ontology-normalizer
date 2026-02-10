"""Pydantic schemas for Central IRB/EC Management (CLINICAL-8).

Manages Institutional Review Board and Ethics Committee operations: board
registration, submission lifecycle (initial, amendment, continuing review,
reportable events, study closure), review tracking with outcomes, regulatory
document management, correspondence tracking, and IRB operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubmissionType(str, Enum):
    """Type of IRB/EC submission."""

    INITIAL = "initial"
    AMENDMENT = "amendment"
    CONTINUING_REVIEW = "continuing_review"
    REPORTABLE_EVENT = "reportable_event"
    STUDY_CLOSURE = "study_closure"
    PROTOCOL_DEVIATION = "protocol_deviation"
    SAFETY_REPORT = "safety_report"


class ReviewStatus(str, Enum):
    """Lifecycle status of an IRB/EC submission."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    DEFERRED = "deferred"
    DISAPPROVED = "disapproved"
    WITHDRAWN = "withdrawn"
    ACKNOWLEDGED = "acknowledged"


class BoardType(str, Enum):
    """Type of review board or ethics committee."""

    CENTRAL_IRB = "central_irb"
    LOCAL_IRB = "local_irb"
    ETHICS_COMMITTEE = "ethics_committee"
    DATA_SAFETY_MONITORING_BOARD = "data_safety_monitoring_board"


class ReviewOutcome(str, Enum):
    """Outcome of a board review decision."""

    APPROVED = "approved"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    TABLED = "tabled"
    DEFERRED = "deferred"
    DISAPPROVED = "disapproved"


class DocumentType(str, Enum):
    """Type of regulatory document submitted to or tracked by the IRB."""

    PROTOCOL = "protocol"
    ICF = "icf"
    INVESTIGATOR_BROCHURE = "investigator_brochure"
    RECRUITMENT_MATERIAL = "recruitment_material"
    CASE_REPORT_FORM = "case_report_form"
    SAFETY_REPORT = "safety_report"
    ANNUAL_REPORT = "annual_report"


class CorrespondenceDirection(str, Enum):
    """Direction of IRB correspondence."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"


class EventSeverity(str, Enum):
    """Severity classification for reportable events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(str, Enum):
    """Status of a reportable event."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DocumentStatus(str, Enum):
    """Status of a regulatory document."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class IRBBoard(BaseModel):
    """An Institutional Review Board or Ethics Committee."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique board identifier")
    name: str = Field(..., description="Board name")
    board_type: BoardType = Field(..., description="Type of review board")
    organization: str = Field(..., description="Parent organization name")
    country: str = Field(..., description="Country where board is located")
    contact_email: str = Field(..., description="Primary contact email for the board")
    meeting_schedule: str = Field(
        ..., description="Description of the board's meeting schedule (e.g., 'Monthly, 3rd Thursday')"
    )
    submission_lead_time_days: int = Field(
        ..., ge=0, description="Required lead time in days for submissions before a meeting"
    )
    active: bool = Field(default=True, description="Whether the board is currently active")


class IRBSubmission(BaseModel):
    """A submission to an IRB/EC for review and approval."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique submission identifier")
    board_id: str = Field(..., description="Board this submission is directed to")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str | None = Field(None, description="Site identifier (if site-specific)")
    submission_type: SubmissionType = Field(..., description="Type of submission")
    submission_number: str = Field(..., description="Submission tracking number")
    protocol_version: str = Field(..., description="Protocol version being submitted")
    submitted_date: datetime | None = Field(None, description="Date the submission was sent to the board")
    submitted_by: str = Field(..., description="Name of person who prepared/submitted")
    review_date: datetime | None = Field(None, description="Date the board reviewed the submission")
    status: ReviewStatus = Field(default=ReviewStatus.DRAFT, description="Current submission status")
    outcome: ReviewOutcome | None = Field(None, description="Board's review outcome")
    approval_date: datetime | None = Field(None, description="Date of approval")
    expiry_date: datetime | None = Field(None, description="Date the approval expires")
    conditions: str | None = Field(None, description="Conditions attached to the approval")
    response_due_date: datetime | None = Field(None, description="Deadline for sponsor response to board")
    notes: str | None = Field(None, description="Additional notes or comments")


class ContinuingReview(BaseModel):
    """A continuing/annual review submission to maintain ongoing approval."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique continuing review identifier")
    submission_id: str = Field(..., description="Parent submission identifier")
    board_id: str = Field(..., description="Board identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    review_period_start: datetime = Field(..., description="Start of the review period")
    review_period_end: datetime = Field(..., description="End of the review period")
    enrollment_since_last_review: int = Field(
        ge=0, description="Number of subjects enrolled since last review"
    )
    total_enrolled: int = Field(ge=0, description="Total subjects enrolled to date")
    adverse_events_count: int = Field(ge=0, description="Number of adverse events during period")
    protocol_deviations_count: int = Field(ge=0, description="Number of protocol deviations during period")
    amendments_since_last: int = Field(ge=0, description="Number of amendments since last review")
    risk_assessment: str = Field(..., description="Updated risk assessment summary")
    submitted_date: datetime | None = Field(None, description="Date submitted to board")
    status: ReviewStatus = Field(default=ReviewStatus.DRAFT, description="Review status")
    next_review_date: datetime | None = Field(None, description="Anticipated next continuing review date")


class ReportableEvent(BaseModel):
    """A reportable event submitted to the IRB/EC."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique event identifier")
    board_id: str = Field(..., description="Board to which the event is reported")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str | None = Field(None, description="Site where event occurred")
    event_type: str = Field(..., description="Type of reportable event (e.g., SAE, protocol deviation)")
    event_description: str = Field(..., description="Detailed description of the event")
    event_date: datetime = Field(..., description="Date the event occurred")
    reported_date: datetime | None = Field(None, description="Date reported to the board")
    severity: EventSeverity = Field(..., description="Severity classification")
    requires_immediate_report: bool = Field(
        default=False, description="Whether this event requires immediate reporting (24-72 hrs)"
    )
    report_deadline: datetime | None = Field(None, description="Deadline for reporting to the board")
    status: EventStatus = Field(default=EventStatus.DRAFT, description="Event reporting status")
    board_response: str | None = Field(None, description="Board's response to the event report")
    resolution: str | None = Field(None, description="Resolution details")


class RegulatoryDocument(BaseModel):
    """A regulatory document tracked as part of an IRB submission."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document identifier")
    submission_id: str = Field(..., description="Associated submission identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    document_type: DocumentType = Field(..., description="Type of regulatory document")
    document_name: str = Field(..., description="Document name/title")
    version: str = Field(..., description="Document version (e.g., '3.0', 'Amendment 2')")
    effective_date: datetime | None = Field(None, description="Date the document became effective")
    expiry_date: datetime | None = Field(None, description="Date the document expires")
    file_reference: str = Field(..., description="File path or reference key for the document")
    uploaded_by: str = Field(..., description="Name of person who uploaded the document")
    uploaded_date: datetime = Field(..., description="Date the document was uploaded")
    status: DocumentStatus = Field(default=DocumentStatus.DRAFT, description="Document status")


class IRBCorrespondence(BaseModel):
    """A correspondence record between sponsor/site and the IRB/EC."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique correspondence identifier")
    submission_id: str = Field(..., description="Associated submission identifier")
    direction: CorrespondenceDirection = Field(
        ..., description="Whether the correspondence is outgoing (to board) or incoming (from board)"
    )
    subject: str = Field(..., description="Subject line of the correspondence")
    content: str = Field(..., description="Full text content of the correspondence")
    sent_date: datetime = Field(..., description="Date the correspondence was sent")
    sent_by: str = Field(..., description="Name of the person who sent the correspondence")
    response_required: bool = Field(
        default=False, description="Whether a response is required"
    )
    response_deadline: datetime | None = Field(
        None, description="Deadline for response if required"
    )
    response_received_date: datetime | None = Field(
        None, description="Date the response was received"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class IRBBoardCreate(BaseModel):
    """Request to create a new IRB/EC board."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Board name")
    board_type: BoardType = Field(..., description="Type of review board")
    organization: str = Field(..., description="Parent organization")
    country: str = Field(..., description="Country")
    contact_email: str = Field(..., description="Contact email")
    meeting_schedule: str = Field(..., description="Meeting schedule description")
    submission_lead_time_days: int = Field(ge=0, description="Lead time in days")


class IRBBoardUpdate(BaseModel):
    """Request to update an IRB/EC board."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Board name")
    board_type: BoardType | None = Field(None, description="Type of review board")
    organization: str | None = Field(None, description="Parent organization")
    country: str | None = Field(None, description="Country")
    contact_email: str | None = Field(None, description="Contact email")
    meeting_schedule: str | None = Field(None, description="Meeting schedule")
    submission_lead_time_days: int | None = Field(None, ge=0, description="Lead time in days")
    active: bool | None = Field(None, description="Active status")


class IRBSubmissionCreate(BaseModel):
    """Request to create a new IRB submission."""

    model_config = ConfigDict(from_attributes=True)

    board_id: str = Field(..., description="Board identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str | None = Field(None, description="Site identifier")
    submission_type: SubmissionType = Field(..., description="Type of submission")
    submission_number: str = Field(..., description="Tracking number")
    protocol_version: str = Field(..., description="Protocol version")
    submitted_by: str = Field(..., description="Submitted by")
    notes: str | None = Field(None, description="Notes")


class IRBSubmissionUpdate(BaseModel):
    """Request to update an IRB submission."""

    model_config = ConfigDict(from_attributes=True)

    protocol_version: str | None = Field(None, description="Protocol version")
    status: ReviewStatus | None = Field(None, description="Submission status")
    conditions: str | None = Field(None, description="Approval conditions")
    response_due_date: datetime | None = Field(None, description="Response due date")
    notes: str | None = Field(None, description="Notes")


class SubmissionSubmitRequest(BaseModel):
    """Request to submit a draft submission to the board for review."""

    model_config = ConfigDict(from_attributes=True)

    submitted_date: datetime | None = Field(None, description="Date of submission (defaults to now)")


class RecordOutcomeRequest(BaseModel):
    """Request to record the outcome of a board review."""

    model_config = ConfigDict(from_attributes=True)

    outcome: ReviewOutcome = Field(..., description="Board review outcome")
    review_date: datetime = Field(..., description="Date the board reviewed")
    approval_date: datetime | None = Field(None, description="Date of approval if approved")
    expiry_date: datetime | None = Field(None, description="Approval expiry date")
    conditions: str | None = Field(None, description="Conditions if conditionally approved")
    notes: str | None = Field(None, description="Review notes")


class ContinuingReviewCreate(BaseModel):
    """Request to create a continuing review."""

    model_config = ConfigDict(from_attributes=True)

    board_id: str = Field(..., description="Board identifier")
    trial_id: str = Field(..., description="Trial identifier")
    review_period_start: datetime = Field(..., description="Period start")
    review_period_end: datetime = Field(..., description="Period end")
    enrollment_since_last_review: int = Field(ge=0, description="Enrolled since last review")
    total_enrolled: int = Field(ge=0, description="Total enrolled")
    adverse_events_count: int = Field(ge=0, description="AE count")
    protocol_deviations_count: int = Field(ge=0, description="PD count")
    amendments_since_last: int = Field(ge=0, description="Amendments since last")
    risk_assessment: str = Field(..., description="Risk assessment")


class ContinuingReviewUpdate(BaseModel):
    """Request to update a continuing review."""

    model_config = ConfigDict(from_attributes=True)

    enrollment_since_last_review: int | None = Field(None, ge=0, description="Enrolled since last review")
    total_enrolled: int | None = Field(None, ge=0, description="Total enrolled")
    adverse_events_count: int | None = Field(None, ge=0, description="AE count")
    protocol_deviations_count: int | None = Field(None, ge=0, description="PD count")
    amendments_since_last: int | None = Field(None, ge=0, description="Amendments since last")
    risk_assessment: str | None = Field(None, description="Risk assessment")
    status: ReviewStatus | None = Field(None, description="Review status")
    next_review_date: datetime | None = Field(None, description="Next review date")


class ReportableEventCreate(BaseModel):
    """Request to file a new reportable event."""

    model_config = ConfigDict(from_attributes=True)

    board_id: str = Field(..., description="Board identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str | None = Field(None, description="Site identifier")
    event_type: str = Field(..., description="Event type")
    event_description: str = Field(..., description="Event description")
    event_date: datetime = Field(..., description="Event date")
    severity: EventSeverity = Field(..., description="Severity")
    requires_immediate_report: bool = Field(default=False, description="Requires immediate report")
    report_deadline: datetime | None = Field(None, description="Reporting deadline")


class ReportableEventUpdate(BaseModel):
    """Request to update a reportable event."""

    model_config = ConfigDict(from_attributes=True)

    event_description: str | None = Field(None, description="Event description")
    severity: EventSeverity | None = Field(None, description="Severity")
    status: EventStatus | None = Field(None, description="Event status")
    board_response: str | None = Field(None, description="Board response")
    resolution: str | None = Field(None, description="Resolution details")


class RegulatoryDocumentCreate(BaseModel):
    """Request to upload/register a regulatory document."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    document_type: DocumentType = Field(..., description="Document type")
    document_name: str = Field(..., description="Document name")
    version: str = Field(..., description="Version")
    file_reference: str = Field(..., description="File reference")
    uploaded_by: str = Field(..., description="Uploaded by")
    effective_date: datetime | None = Field(None, description="Effective date")
    expiry_date: datetime | None = Field(None, description="Expiry date")


class IRBCorrespondenceCreate(BaseModel):
    """Request to create a correspondence record."""

    model_config = ConfigDict(from_attributes=True)

    direction: CorrespondenceDirection = Field(..., description="Direction")
    subject: str = Field(..., description="Subject")
    content: str = Field(..., description="Content")
    sent_by: str = Field(..., description="Sent by")
    response_required: bool = Field(default=False, description="Response required")
    response_deadline: datetime | None = Field(None, description="Response deadline")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class IRBBoardListResponse(BaseModel):
    """List of IRB/EC boards."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IRBBoard] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class IRBSubmissionListResponse(BaseModel):
    """List of IRB submissions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IRBSubmission] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ContinuingReviewListResponse(BaseModel):
    """List of continuing reviews."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ContinuingReview] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ReportableEventListResponse(BaseModel):
    """List of reportable events."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReportableEvent] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RegulatoryDocumentListResponse(BaseModel):
    """List of regulatory documents."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatoryDocument] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class IRBCorrespondenceListResponse(BaseModel):
    """List of IRB correspondence."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IRBCorrespondence] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class IRBMetrics(BaseModel):
    """Aggregated IRB/EC operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_submissions: int = Field(ge=0, description="Total submissions across all boards")
    pending_reviews: int = Field(
        ge=0, description="Submissions currently under review or submitted"
    )
    approved_count: int = Field(
        ge=0, description="Total approved submissions"
    )
    avg_review_days: float = Field(
        ge=0.0, description="Average days from submission to review outcome"
    )
    expiring_approvals_30d: int = Field(
        ge=0, description="Number of approvals expiring within the next 30 days"
    )
    overdue_continuing_reviews: int = Field(
        ge=0, description="Continuing reviews past their scheduled date"
    )
    reportable_events_open: int = Field(
        ge=0, description="Number of reportable events still open"
    )
