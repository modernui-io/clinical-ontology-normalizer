"""Pydantic schemas for Regulatory Correspondence Tracking (CLO-7).

Tracks regulatory correspondence, action items, timelines, and agency contacts
for clinical trial programs across FDA, EMA, MHRA, and other regulatory bodies.

Provides structured models for:
- Correspondence records (meetings, letters, reports, requests)
- Action items with deadline tracking
- Regulatory timelines with milestones
- Agency contact management
- Metrics and deadline reporting
- Agency relationship summaries
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RegulatoryAgency(str, Enum):
    """Regulatory agencies that issue or receive correspondence."""

    FDA = "FDA"
    EMA = "EMA"
    MHRA = "MHRA"
    HEALTH_CANADA = "HEALTH_CANADA"
    PMDA = "PMDA"
    TGA = "TGA"
    ANVISA = "ANVISA"
    NMPA = "NMPA"


class CorrespondenceType(str, Enum):
    """Types of regulatory correspondence."""

    PRE_IND_MEETING = "PRE_IND_MEETING"
    TYPE_A_MEETING = "TYPE_A_MEETING"
    TYPE_B_MEETING = "TYPE_B_MEETING"
    TYPE_C_MEETING = "TYPE_C_MEETING"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    COMPLETE_RESPONSE_LETTER = "COMPLETE_RESPONSE_LETTER"
    WARNING_LETTER = "WARNING_LETTER"
    FORM_483 = "FORM_483"
    ANNUAL_REPORT = "ANNUAL_REPORT"
    IND_SAFETY_REPORT = "IND_SAFETY_REPORT"
    PROTOCOL_AMENDMENT = "PROTOCOL_AMENDMENT"
    DMCR_REPORT = "DMCR_REPORT"
    ADVISORY_COMMITTEE = "ADVISORY_COMMITTEE"


class CorrespondenceStatus(str, Enum):
    """Lifecycle status of a correspondence record."""

    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


class Priority(str, Enum):
    """Priority level for correspondence and action items."""

    URGENT = "URGENT"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class ResponseDeadline(str, Enum):
    """Standard response deadline categories."""

    DAYS_15 = "DAYS_15"
    DAYS_30 = "DAYS_30"
    DAYS_60 = "DAYS_60"
    DAYS_90 = "DAYS_90"
    DAYS_120 = "DAYS_120"
    CALENDAR_DRIVEN = "CALENDAR_DRIVEN"
    NONE = "NONE"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class Correspondence(BaseModel):
    """A regulatory correspondence record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique correspondence identifier")
    title: str = Field(..., description="Correspondence title/subject")
    correspondence_type: CorrespondenceType = Field(
        ..., description="Type of correspondence"
    )
    agency: RegulatoryAgency = Field(..., description="Regulatory agency")
    status: CorrespondenceStatus = Field(
        default=CorrespondenceStatus.DRAFT, description="Current status"
    )
    priority: Priority = Field(
        default=Priority.NORMAL, description="Priority level"
    )
    trial_id: str = Field(..., description="Associated trial identifier")
    trial_name: str = Field(..., description="Human-readable trial name")
    description: str | None = Field(None, description="Detailed description")
    submission_date: datetime | None = Field(
        None, description="Date submitted to agency"
    )
    response_deadline: ResponseDeadline = Field(
        default=ResponseDeadline.NONE, description="Response deadline category"
    )
    response_deadline_date: datetime | None = Field(
        None, description="Calculated response deadline date"
    )
    response_received_date: datetime | None = Field(
        None, description="Date response was received from agency"
    )
    assigned_to: str | None = Field(
        None, description="Person assigned to this correspondence"
    )
    reviewer: str | None = Field(None, description="Reviewer for this correspondence")
    attachments_count: int = Field(
        default=0, description="Number of attached documents"
    )
    related_correspondence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of related correspondence records",
    )
    tags: list[str] = Field(
        default_factory=list, description="Categorization tags"
    )
    key_points: list[str] = Field(
        default_factory=list, description="Key discussion or decision points"
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Summary action item descriptions",
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last-updated timestamp")


class CorrespondenceAttachment(BaseModel):
    """Attachment metadata for a correspondence record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Attachment identifier")
    correspondence_id: str = Field(..., description="Parent correspondence ID")
    filename: str = Field(..., description="File name")
    file_type: str = Field(..., description="MIME type or extension")
    uploaded_by: str | None = Field(None, description="Uploader name")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    description: str | None = Field(None, description="File description")


class ActionItem(BaseModel):
    """An action item arising from a correspondence."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Action item identifier")
    correspondence_id: str = Field(..., description="Parent correspondence ID")
    description: str = Field(..., description="Action item description")
    assigned_to: str | None = Field(None, description="Assignee")
    due_date: datetime = Field(..., description="Due date")
    completed: bool = Field(default=False, description="Completion flag")
    completed_date: datetime | None = Field(
        None, description="Date completed"
    )
    priority: Priority = Field(
        default=Priority.NORMAL, description="Priority level"
    )


class TimelineMilestone(BaseModel):
    """A milestone within a regulatory timeline."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Milestone name")
    planned_date: datetime = Field(..., description="Planned date")
    actual_date: datetime | None = Field(None, description="Actual date achieved")
    status: str = Field(
        default="PENDING", description="Milestone status (PENDING, COMPLETED, DELAYED, SKIPPED)"
    )
    correspondence_id: str | None = Field(
        None, description="Related correspondence ID"
    )
    notes: str | None = Field(None, description="Milestone notes")


class RegulatoryTimeline(BaseModel):
    """A regulatory timeline for a trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Timeline identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    trial_name: str = Field(..., description="Human-readable trial name")
    milestones: list[TimelineMilestone] = Field(
        default_factory=list, description="Timeline milestones"
    )


class AgencyContact(BaseModel):
    """A contact person at a regulatory agency."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Contact identifier")
    name: str = Field(..., description="Contact name")
    agency: RegulatoryAgency = Field(..., description="Agency affiliation")
    title: str | None = Field(None, description="Job title")
    division: str | None = Field(None, description="Division/office")
    email: str | None = Field(None, description="Email address")
    phone: str | None = Field(None, description="Phone number")
    notes: str | None = Field(None, description="Additional notes")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CorrespondenceCreate(BaseModel):
    """Request body for creating a correspondence record."""

    title: str = Field(..., description="Correspondence title")
    correspondence_type: CorrespondenceType = Field(
        ..., description="Type of correspondence"
    )
    agency: RegulatoryAgency = Field(..., description="Regulatory agency")
    priority: Priority = Field(
        default=Priority.NORMAL, description="Priority level"
    )
    trial_id: str = Field(..., description="Associated trial ID")
    trial_name: str = Field(..., description="Trial name")
    description: str | None = Field(None, description="Description")
    response_deadline: ResponseDeadline = Field(
        default=ResponseDeadline.NONE, description="Response deadline category"
    )
    assigned_to: str | None = Field(None, description="Assignee")
    reviewer: str | None = Field(None, description="Reviewer")
    tags: list[str] = Field(default_factory=list, description="Tags")
    key_points: list[str] = Field(default_factory=list, description="Key points")


class CorrespondenceUpdate(BaseModel):
    """Request body for updating a correspondence record."""

    title: str | None = Field(None, description="Updated title")
    status: CorrespondenceStatus | None = Field(None, description="Updated status")
    priority: Priority | None = Field(None, description="Updated priority")
    description: str | None = Field(None, description="Updated description")
    response_deadline: ResponseDeadline | None = Field(
        None, description="Updated deadline category"
    )
    response_deadline_date: datetime | None = Field(
        None, description="Updated deadline date"
    )
    assigned_to: str | None = Field(None, description="Updated assignee")
    reviewer: str | None = Field(None, description="Updated reviewer")
    tags: list[str] | None = Field(None, description="Updated tags")
    key_points: list[str] | None = Field(None, description="Updated key points")
    action_items: list[str] | None = Field(None, description="Updated action items")


class ActionItemCreate(BaseModel):
    """Request body for creating an action item."""

    description: str = Field(..., description="Action item description")
    assigned_to: str | None = Field(None, description="Assignee")
    due_date: datetime = Field(..., description="Due date")
    priority: Priority = Field(default=Priority.NORMAL, description="Priority")


class ActionItemUpdate(BaseModel):
    """Request body for updating an action item."""

    description: str | None = Field(None, description="Updated description")
    assigned_to: str | None = Field(None, description="Updated assignee")
    due_date: datetime | None = Field(None, description="Updated due date")
    completed: bool | None = Field(None, description="Completion flag")
    priority: Priority | None = Field(None, description="Updated priority")


class TimelineCreate(BaseModel):
    """Request body for creating a regulatory timeline."""

    trial_id: str = Field(..., description="Trial ID")
    trial_name: str = Field(..., description="Trial name")
    milestones: list[TimelineMilestone] = Field(
        default_factory=list, description="Initial milestones"
    )


class TimelineUpdate(BaseModel):
    """Request body for updating a regulatory timeline."""

    trial_name: str | None = Field(None, description="Updated trial name")


class MilestoneCreate(BaseModel):
    """Request body for adding a milestone to a timeline."""

    name: str = Field(..., description="Milestone name")
    planned_date: datetime = Field(..., description="Planned date")
    correspondence_id: str | None = Field(None, description="Related correspondence")
    notes: str | None = Field(None, description="Notes")


class MilestoneUpdate(BaseModel):
    """Request body for updating a timeline milestone."""

    name: str | None = Field(None, description="Updated name")
    planned_date: datetime | None = Field(None, description="Updated planned date")
    actual_date: datetime | None = Field(None, description="Actual date achieved")
    status: str | None = Field(None, description="Updated status")
    correspondence_id: str | None = Field(None, description="Related correspondence")
    notes: str | None = Field(None, description="Updated notes")


class AgencyContactCreate(BaseModel):
    """Request body for creating an agency contact."""

    name: str = Field(..., description="Contact name")
    agency: RegulatoryAgency = Field(..., description="Agency")
    title: str | None = Field(None, description="Job title")
    division: str | None = Field(None, description="Division")
    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Phone")
    notes: str | None = Field(None, description="Notes")


class AgencyContactUpdate(BaseModel):
    """Request body for updating an agency contact."""

    name: str | None = Field(None, description="Updated name")
    agency: RegulatoryAgency | None = Field(None, description="Updated agency")
    title: str | None = Field(None, description="Updated title")
    division: str | None = Field(None, description="Updated division")
    email: str | None = Field(None, description="Updated email")
    phone: str | None = Field(None, description="Updated phone")
    notes: str | None = Field(None, description="Updated notes")


class LinkCorrespondenceRequest(BaseModel):
    """Request body for linking two correspondence records."""

    related_id: str = Field(..., description="ID of correspondence to link")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CorrespondenceListResponse(BaseModel):
    """Paginated list of correspondence records."""

    items: list[Correspondence] = Field(..., description="Correspondence records")
    total: int = Field(..., description="Total matching records")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class ActionItemListResponse(BaseModel):
    """List of action items."""

    items: list[ActionItem] = Field(..., description="Action items")
    total: int = Field(..., description="Total items")


class TimelineListResponse(BaseModel):
    """List of regulatory timelines."""

    items: list[RegulatoryTimeline] = Field(..., description="Timelines")
    total: int = Field(..., description="Total timelines")


class AgencyContactListResponse(BaseModel):
    """List of agency contacts."""

    items: list[AgencyContact] = Field(..., description="Contacts")
    total: int = Field(..., description="Total contacts")


# ---------------------------------------------------------------------------
# Analytics / reporting schemas
# ---------------------------------------------------------------------------


class CorrespondenceMetrics(BaseModel):
    """Aggregated correspondence metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_correspondence: int = Field(..., description="Total records")
    by_agency: dict[str, int] = Field(
        default_factory=dict, description="Count by agency"
    )
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Count by type"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="Count by status"
    )
    overdue_action_items: int = Field(
        default=0, description="Number of overdue action items"
    )
    avg_response_time_days: float | None = Field(
        None, description="Average agency response time in days"
    )
    open_action_items: int = Field(
        default=0, description="Number of open action items"
    )
    completed_action_items: int = Field(
        default=0, description="Number of completed action items"
    )


class DeadlineEntry(BaseModel):
    """A single deadline entry in a deadline report."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Correspondence or action item ID")
    title: str = Field(..., description="Title or description")
    deadline_date: datetime = Field(..., description="Deadline date")
    days_until_due: int = Field(..., description="Days until due (negative = overdue)")
    is_overdue: bool = Field(..., description="Whether deadline is past")
    source_type: str = Field(
        ..., description="Source type: 'correspondence' or 'action_item'"
    )
    agency: RegulatoryAgency | None = Field(None, description="Agency if applicable")
    priority: Priority = Field(
        default=Priority.NORMAL, description="Priority"
    )


class DeadlineReport(BaseModel):
    """Report of upcoming and overdue deadlines."""

    model_config = ConfigDict(from_attributes=True)

    upcoming: list[DeadlineEntry] = Field(
        default_factory=list, description="Upcoming deadlines"
    )
    overdue: list[DeadlineEntry] = Field(
        default_factory=list, description="Overdue deadlines"
    )
    total_upcoming: int = Field(default=0, description="Count of upcoming deadlines")
    total_overdue: int = Field(default=0, description="Count of overdue deadlines")


class AgencyRelationshipSummary(BaseModel):
    """Summary of relationship with a regulatory agency."""

    model_config = ConfigDict(from_attributes=True)

    agency: RegulatoryAgency = Field(..., description="Agency")
    total_correspondence: int = Field(
        default=0, description="Total correspondence count"
    )
    open_items: int = Field(default=0, description="Open correspondence")
    closed_items: int = Field(default=0, description="Closed correspondence")
    avg_response_time_days: float | None = Field(
        None, description="Average response time in days"
    )
    contacts: list[AgencyContact] = Field(
        default_factory=list, description="Known contacts at this agency"
    )
    recent_correspondence: list[Correspondence] = Field(
        default_factory=list, description="Most recent 5 correspondence items"
    )
