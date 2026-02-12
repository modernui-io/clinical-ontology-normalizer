"""Pydantic schemas for Health Authority Meeting Tracker (HA-MEET).

Manages health authority interactions: meeting requests, briefing document
preparation, meeting minutes, action item tracking, commitment management,
and HA meeting operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MeetingType(str, Enum):
    PRE_IND = "pre_ind"
    END_OF_PHASE_2 = "end_of_phase_2"
    PRE_NDA = "pre_nda"
    PRE_BLA = "pre_bla"
    TYPE_A = "type_a"
    TYPE_B = "type_b"
    TYPE_C = "type_c"
    SCIENTIFIC_ADVICE = "scientific_advice"
    PROTOCOL_ASSISTANCE = "protocol_assistance"
    PEDIATRIC = "pediatric"


class MeetingStatus(str, Enum):
    PLANNING = "planning"
    REQUEST_SUBMITTED = "request_submitted"
    SCHEDULED = "scheduled"
    BRIEFING_DOC_SUBMITTED = "briefing_doc_submitted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class HealthAuthority(str, Enum):
    FDA = "fda"
    EMA = "ema"
    PMDA = "pmda"
    NMPA = "nmpa"
    HEALTH_CANADA = "health_canada"
    MHRA = "mhra"
    TGA = "tga"
    ANVISA = "anvisa"


class ActionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommitmentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    WAIVED = "waived"


class HAMeeting(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    meeting_type: MeetingType
    health_authority: HealthAuthority
    status: MeetingStatus = MeetingStatus.PLANNING
    title: str
    objective: str
    request_date: datetime | None = None
    scheduled_date: datetime | None = None
    actual_date: datetime | None = None
    duration_minutes: int = Field(ge=0, default=60)
    format: str = "in_person"
    key_questions: list[str] = Field(default_factory=list)
    attendees: list[str] = Field(default_factory=list)
    regulatory_lead: str
    medical_lead: str | None = None
    created_at: datetime


class BriefingDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    title: str
    version: str
    page_count: int = Field(ge=0, default=0)
    sections: list[str] = Field(default_factory=list)
    status: str = "draft"
    author: str
    reviewer: str | None = None
    approved_date: datetime | None = None
    submission_date: datetime | None = None
    ha_receipt_date: datetime | None = None
    created_at: datetime


class MeetingMinutes(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    summary: str
    key_outcomes: list[str] = Field(default_factory=list)
    ha_feedback: str | None = None
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    recorded_by: str
    approved_by: str | None = None
    approved_date: datetime | None = None
    created_at: datetime


class MeetingActionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    action_description: str
    assigned_to: str
    priority: ActionPriority = ActionPriority.MEDIUM
    due_date: datetime
    status: CommitmentStatus = CommitmentStatus.OPEN
    completed_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class HACommitment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    trial_id: str
    commitment_text: str
    health_authority: HealthAuthority
    source: str
    status: CommitmentStatus = CommitmentStatus.OPEN
    due_date: datetime | None = None
    responsible_person: str
    completed_date: datetime | None = None
    evidence_reference: str | None = None
    regulatory_impact: str | None = None
    created_at: datetime


class HAMeetingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    meeting_type: MeetingType
    health_authority: HealthAuthority
    title: str
    objective: str
    regulatory_lead: str
    medical_lead: str | None = None
    key_questions: list[str] = Field(default_factory=list)


class HAMeetingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: MeetingStatus | None = None
    scheduled_date: datetime | None = None
    duration_minutes: int | None = None
    format: str | None = None
    attendees: list[str] | None = None


class BriefingDocumentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    meeting_id: str
    title: str
    version: str
    author: str
    sections: list[str] = Field(default_factory=list)


class BriefingDocumentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    reviewer: str | None = None
    page_count: int | None = None


class MeetingMinutesCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    meeting_id: str
    summary: str
    recorded_by: str
    key_outcomes: list[str] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)


class MeetingMinutesUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ha_feedback: str | None = None
    disagreements: list[str] | None = None
    approved_by: str | None = None


class MeetingActionItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    meeting_id: str
    action_description: str
    assigned_to: str
    priority: ActionPriority = ActionPriority.MEDIUM
    due_date: datetime


class MeetingActionItemUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: CommitmentStatus | None = None
    assigned_to: str | None = None
    notes: str | None = None


class HACommitmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    meeting_id: str
    trial_id: str
    commitment_text: str
    health_authority: HealthAuthority
    source: str
    responsible_person: str
    due_date: datetime | None = None


class HACommitmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: CommitmentStatus | None = None
    evidence_reference: str | None = None
    regulatory_impact: str | None = None


class HAMeetingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[HAMeeting] = Field(default_factory=list)
    total: int = Field(ge=0)


class BriefingDocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[BriefingDocument] = Field(default_factory=list)
    total: int = Field(ge=0)


class MeetingMinutesListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MeetingMinutes] = Field(default_factory=list)
    total: int = Field(ge=0)


class MeetingActionItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MeetingActionItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class HACommitmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[HACommitment] = Field(default_factory=list)
    total: int = Field(ge=0)


class HAMeetingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_meetings: int = Field(ge=0)
    meetings_by_type: dict[str, int] = Field(default_factory=dict)
    meetings_by_status: dict[str, int] = Field(default_factory=dict)
    meetings_by_authority: dict[str, int] = Field(default_factory=dict)
    total_briefing_docs: int = Field(ge=0)
    approved_briefing_docs: int = Field(ge=0)
    total_minutes: int = Field(ge=0)
    total_action_items: int = Field(ge=0)
    action_items_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_actions: int = Field(ge=0)
    total_commitments: int = Field(ge=0)
    commitments_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_commitments: int = Field(ge=0)
