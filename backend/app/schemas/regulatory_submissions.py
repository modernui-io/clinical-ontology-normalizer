"""Pydantic schemas for Regulatory Submission Tracking (CLO-5).

Tracks regulatory submissions, milestones, deadlines, and metrics
across multiple regulatory bodies (FDA, EMA, MHRA, PMDA, TGA,
Health Canada, NMPA) for clinical trial programs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubmissionType(str, Enum):
    """Classification of regulatory submission types."""

    IND = "IND"
    NDA = "NDA"
    BLA = "BLA"
    ANDA = "ANDA"
    FIVE10K = "510K"
    PMA = "PMA"
    EUA = "EUA"
    ANNUAL_REPORT = "ANNUAL_REPORT"
    SAFETY_REPORT = "SAFETY_REPORT"
    PROTOCOL_AMENDMENT = "PROTOCOL_AMENDMENT"
    IRB_APPROVAL = "IRB_APPROVAL"
    IEC_APPROVAL = "IEC_APPROVAL"
    DSMB_REPORT = "DSMB_REPORT"


class RegulatoryBody(str, Enum):
    """Regulatory bodies that receive submissions."""

    FDA = "FDA"
    EMA = "EMA"
    MHRA = "MHRA"
    PMDA = "PMDA"
    TGA = "TGA"
    HEALTH_CANADA = "HEALTH_CANADA"
    NMPA = "NMPA"


class SubmissionStatus(str, Enum):
    """Status of a regulatory submission through its lifecycle."""

    DRAFTING = "DRAFTING"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class SubmissionPriority(str, Enum):
    """Priority level for a regulatory submission."""

    URGENT = "URGENT"
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class MilestoneStatus(str, Enum):
    """Status of a submission milestone."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    WAIVED = "WAIVED"


# ---------------------------------------------------------------------------
# Document reference
# ---------------------------------------------------------------------------


class DocumentRef(BaseModel):
    """Reference to a document attached to a submission."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Document identifier")
    name: str = Field(..., description="Document name")
    version: str | None = Field(None, description="Document version")
    uploaded_at: datetime | None = Field(None, description="Upload timestamp")


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class RegulatorySubmission(BaseModel):
    """A single regulatory submission record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique submission identifier")
    title: str = Field(..., description="Submission title")
    submission_type: SubmissionType = Field(..., description="Type of submission")
    regulatory_body: RegulatoryBody = Field(..., description="Target regulatory body")
    trial_id: str = Field(..., description="Associated trial identifier")
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFTING, description="Current submission status"
    )
    reference_number: str | None = Field(
        None, description="Regulatory reference number"
    )
    submitted_date: datetime | None = Field(
        None, description="Date submission was sent to regulatory body"
    )
    expected_response_date: datetime | None = Field(
        None, description="Expected response date from regulatory body"
    )
    actual_response_date: datetime | None = Field(
        None, description="Actual response date from regulatory body"
    )
    assigned_to: str | None = Field(
        None, description="Person assigned to manage this submission"
    )
    reviewer: str | None = Field(
        None, description="Internal reviewer"
    )
    priority: SubmissionPriority = Field(
        default=SubmissionPriority.STANDARD, description="Submission priority"
    )
    documents: list[DocumentRef] = Field(
        default_factory=list, description="Attached document references"
    )
    notes: str | None = Field(None, description="Free-text notes")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class SubmissionMilestone(BaseModel):
    """A milestone within a regulatory submission timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique milestone identifier")
    submission_id: str = Field(..., description="Parent submission identifier")
    milestone_name: str = Field(..., description="Name of the milestone")
    due_date: datetime = Field(..., description="Due date for the milestone")
    completed_date: datetime | None = Field(
        None, description="Date the milestone was completed"
    )
    status: MilestoneStatus = Field(
        default=MilestoneStatus.PENDING, description="Milestone status"
    )
    responsible: str | None = Field(
        None, description="Person responsible for the milestone"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SubmissionCreate(BaseModel):
    """Request payload for creating a new regulatory submission."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="Submission title")
    submission_type: SubmissionType = Field(..., description="Type of submission")
    regulatory_body: RegulatoryBody = Field(..., description="Target regulatory body")
    trial_id: str = Field(..., description="Associated trial identifier")
    priority: SubmissionPriority = Field(
        default=SubmissionPriority.STANDARD, description="Submission priority"
    )
    assigned_to: str | None = Field(None, description="Assigned person")
    reviewer: str | None = Field(None, description="Internal reviewer")
    notes: str | None = Field(None, description="Free-text notes")


class SubmissionUpdate(BaseModel):
    """Request payload for updating an existing submission."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Updated title")
    status: SubmissionStatus | None = Field(None, description="New status")
    priority: SubmissionPriority | None = Field(None, description="Updated priority")
    assigned_to: str | None = Field(None, description="Updated assignee")
    reviewer: str | None = Field(None, description="Updated reviewer")
    reference_number: str | None = Field(None, description="Regulatory reference number")
    expected_response_date: datetime | None = Field(None, description="Expected response date")
    notes: str | None = Field(None, description="Updated notes")


class SubmissionListResponse(BaseModel):
    """Paginated list of regulatory submissions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatorySubmission] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
    limit: int = Field(ge=1, description="Page size")
    offset: int = Field(ge=0, description="Page offset")


class MilestoneCreate(BaseModel):
    """Request payload for creating a new milestone."""

    model_config = ConfigDict(from_attributes=True)

    milestone_name: str = Field(..., description="Name of the milestone")
    due_date: datetime = Field(..., description="Due date")
    responsible: str | None = Field(None, description="Responsible person")


class MilestoneUpdate(BaseModel):
    """Request payload for updating an existing milestone."""

    model_config = ConfigDict(from_attributes=True)

    milestone_name: str | None = Field(None, description="Updated name")
    due_date: datetime | None = Field(None, description="Updated due date")
    status: MilestoneStatus | None = Field(None, description="Updated status")
    completed_date: datetime | None = Field(None, description="Completion date")
    responsible: str | None = Field(None, description="Updated responsible person")


class MilestoneListResponse(BaseModel):
    """List of milestones for a submission."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SubmissionMilestone] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total milestones")


class RecordResponseRequest(BaseModel):
    """Request to record a regulatory body response."""

    status: SubmissionStatus = Field(
        ..., description="Response status (APPROVED, REJECTED, INFORMATION_REQUEST)"
    )
    notes: str | None = Field(None, description="Response notes")


class DeadlineAlert(BaseModel):
    """A deadline alert for a milestone or submission."""

    model_config = ConfigDict(from_attributes=True)

    submission_id: str = Field(..., description="Submission identifier")
    submission_title: str = Field(..., description="Submission title")
    milestone_id: str | None = Field(None, description="Milestone identifier (if milestone)")
    milestone_name: str | None = Field(None, description="Milestone name (if milestone)")
    due_date: datetime = Field(..., description="Due date")
    days_until_due: int = Field(..., description="Days until due (negative = overdue)")
    is_overdue: bool = Field(default=False, description="Whether the deadline is overdue")


# ---------------------------------------------------------------------------
# Calendar & Metrics
# ---------------------------------------------------------------------------


class RegulatoryCalendar(BaseModel):
    """Regulatory submission calendar view."""

    model_config = ConfigDict(from_attributes=True)

    upcoming_deadlines: list[DeadlineAlert] = Field(
        default_factory=list, description="Upcoming deadlines within 30 days"
    )
    overdue: list[DeadlineAlert] = Field(
        default_factory=list, description="Overdue deadlines"
    )
    submitted_awaiting_response: list[RegulatorySubmission] = Field(
        default_factory=list, description="Submissions awaiting regulatory response"
    )


class SubmissionMetrics(BaseModel):
    """Aggregated regulatory submission metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_submissions: int = Field(ge=0, description="Total submission count")
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Count per submission type"
    )
    by_body: dict[str, int] = Field(
        default_factory=dict, description="Count per regulatory body"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="Count per status"
    )
    avg_review_time_days: float | None = Field(
        None, description="Average review time in days (submitted to response)"
    )
    approval_rate: float = Field(
        ge=0.0, le=1.0, default=0.0,
        description="Fraction of resolved submissions that were approved",
    )
    overdue_milestones: int = Field(
        ge=0, default=0, description="Count of overdue milestones"
    )
    pending_information_requests: int = Field(
        ge=0, default=0,
        description="Count of submissions with pending information requests",
    )
