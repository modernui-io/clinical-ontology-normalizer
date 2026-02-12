"""Pydantic schemas for Investigator Meeting Management (INV-MTG).

Manages investigator meeting operations: meeting planning, attendance
tracking, training session records, presentation materials management,
and action item tracking with meeting metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MeetingType(str, Enum):
    INVESTIGATOR_MEETING = "investigator_meeting"
    SITE_INITIATION = "site_initiation"
    INTERIM_REVIEW = "interim_review"
    ADVISORY_BOARD = "advisory_board"
    TRAINING_SESSION = "training_session"
    CLOSE_OUT = "close_out"


class MeetingFormat(str, Enum):
    IN_PERSON = "in_person"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"


class MeetingStatus(str, Enum):
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class AttendanceStatus(str, Enum):
    INVITED = "invited"
    CONFIRMED = "confirmed"
    ATTENDED = "attended"
    DECLINED = "declined"
    NO_SHOW = "no_show"
    EXCUSED = "excused"


class ActionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MeetingPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    meeting_name: str
    meeting_type: MeetingType
    meeting_format: MeetingFormat = MeetingFormat.HYBRID
    status: MeetingStatus = MeetingStatus.PLANNED
    planned_date: datetime
    actual_date: datetime | None = None
    duration_hours: float = Field(ge=0, default=8.0)
    location: str | None = None
    virtual_platform: str | None = None
    max_attendees: int = Field(ge=0, default=0)
    budget_estimate: float = Field(ge=0, default=0.0)
    actual_cost: float | None = None
    agenda_finalized: bool = False
    logistics_confirmed: bool = False
    organized_by: str
    sponsor_representative: str | None = None
    notes: str | None = None
    created_at: datetime


class AttendanceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    meeting_id: str
    attendee_name: str
    role: str
    site_id: str | None = None
    attendance_status: AttendanceStatus = AttendanceStatus.INVITED
    invitation_date: datetime | None = None
    rsvp_date: datetime | None = None
    check_in_time: datetime | None = None
    travel_required: bool = False
    travel_arranged: bool = False
    accommodation_required: bool = False
    dietary_requirements: str | None = None
    managed_by: str
    notes: str | None = None
    created_at: datetime


class TrainingSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    meeting_id: str | None = None
    session_title: str
    topic: str
    trainer: str
    session_date: datetime
    duration_minutes: int = Field(ge=0, default=60)
    attendee_count: int = Field(ge=0, default=0)
    assessment_required: bool = False
    pass_rate_pct: float = Field(ge=0, le=100, default=0.0)
    materials_distributed: bool = False
    recording_available: bool = False
    certificate_issued: bool = False
    gcp_training: bool = False
    protocol_training: bool = False
    created_by: str
    notes: str | None = None
    created_at: datetime


class PresentationMaterial(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    meeting_id: str
    title: str
    presenter: str
    material_type: str = "slides"
    version: str = "1.0"
    slide_count: int = Field(ge=0, default=0)
    duration_minutes: int = Field(ge=0, default=30)
    approved_for_distribution: bool = False
    confidential: bool = True
    medical_review_completed: bool = False
    legal_review_completed: bool = False
    translated: bool = False
    languages: list[str] = Field(default_factory=list)
    uploaded_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ActionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    meeting_id: str
    action_description: str
    assigned_to: str
    priority: ActionPriority = ActionPriority.MEDIUM
    due_date: datetime
    completed_date: datetime | None = None
    status: str = "open"
    follow_up_required: bool = False
    follow_up_meeting_id: str | None = None
    escalated: bool = False
    escalated_to: str | None = None
    days_overdue: int | None = None
    created_by: str
    notes: str | None = None
    created_at: datetime


class MeetingPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    meeting_name: str
    meeting_type: MeetingType
    planned_date: datetime
    organized_by: str
    meeting_format: MeetingFormat = MeetingFormat.HYBRID
    duration_hours: float = Field(ge=0, default=8.0)


class MeetingPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: MeetingStatus | None = None
    agenda_finalized: bool | None = None
    logistics_confirmed: bool | None = None
    location: str | None = None
    notes: str | None = None


class AttendanceRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    meeting_id: str
    attendee_name: str
    role: str
    managed_by: str
    site_id: str | None = None


class AttendanceRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attendance_status: AttendanceStatus | None = None
    travel_arranged: bool | None = None
    accommodation_required: bool | None = None
    notes: str | None = None


class TrainingSessionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    session_title: str
    topic: str
    trainer: str
    created_by: str
    meeting_id: str | None = None
    duration_minutes: int = Field(ge=0, default=60)


class TrainingSessionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    assessment_required: bool | None = None
    pass_rate_pct: float | None = None
    recording_available: bool | None = None
    certificate_issued: bool | None = None
    notes: str | None = None


class PresentationMaterialCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    meeting_id: str
    title: str
    presenter: str
    uploaded_by: str
    material_type: str = "slides"
    slide_count: int = Field(ge=0, default=0)


class PresentationMaterialUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approved_for_distribution: bool | None = None
    medical_review_completed: bool | None = None
    legal_review_completed: bool | None = None
    approved_by: str | None = None
    notes: str | None = None


class ActionItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    meeting_id: str
    action_description: str
    assigned_to: str
    due_date: datetime
    created_by: str
    priority: ActionPriority = ActionPriority.MEDIUM


class ActionItemUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    priority: ActionPriority | None = None
    escalated: bool | None = None
    escalated_to: str | None = None
    notes: str | None = None


class MeetingPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MeetingPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class AttendanceRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AttendanceRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class TrainingSessionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TrainingSession] = Field(default_factory=list)
    total: int = Field(ge=0)


class PresentationMaterialListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PresentationMaterial] = Field(default_factory=list)
    total: int = Field(ge=0)


class ActionItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ActionItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class InvestigatorMeetingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_meetings: int = Field(ge=0)
    meetings_by_type: dict[str, int] = Field(default_factory=dict)
    meetings_by_status: dict[str, int] = Field(default_factory=dict)
    meetings_by_format: dict[str, int] = Field(default_factory=dict)
    total_attendance_records: int = Field(ge=0)
    attendance_by_status: dict[str, int] = Field(default_factory=dict)
    avg_attendance_rate_pct: float = Field(ge=0)
    total_training_sessions: int = Field(ge=0)
    avg_pass_rate_pct: float = Field(ge=0)
    total_presentations: int = Field(ge=0)
    approved_presentations: int = Field(ge=0)
    total_action_items: int = Field(ge=0)
    action_items_by_priority: dict[str, int] = Field(default_factory=dict)
    open_action_items: int = Field(ge=0)
    overdue_action_items: int = Field(ge=0)
