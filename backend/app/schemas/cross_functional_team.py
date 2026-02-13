"""Pydantic schemas for Cross-Functional Team Management (CFT-MGT).

Manages cross-functional team operations: team formation, role assignments,
meeting cadence records, deliverable tracking, and performance review
with team metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TeamType(str, Enum):
    CORE_TEAM = "core_team"
    EXTENDED_TEAM = "extended_team"
    SUB_TEAM = "sub_team"
    GOVERNANCE = "governance"
    ADVISORY = "advisory"
    TASK_FORCE = "task_force"


class TeamStatus(str, Enum):
    FORMING = "forming"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    DISBANDED = "disbanded"
    TRANSITIONING = "transitioning"
    ARCHIVED = "archived"


class FunctionalRole(str, Enum):
    MEDICAL_MONITOR = "medical_monitor"
    CLINICAL_LEAD = "clinical_lead"
    BIOSTATISTICIAN = "biostatistician"
    REGULATORY_LEAD = "regulatory_lead"
    SAFETY_OFFICER = "safety_officer"
    DATA_MANAGER = "data_manager"


class MeetingCadence(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    AD_HOC = "ad_hoc"


class DeliverableStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class TeamFormation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    team_name: str
    team_type: TeamType
    status: TeamStatus = TeamStatus.FORMING
    charter_approved: bool = False
    sponsor_name: str
    formation_date: datetime
    target_completion_date: datetime | None = None
    actual_completion_date: datetime | None = None
    max_members: int = Field(ge=0, default=20)
    current_members: int = Field(ge=0, default=0)
    objectives: list[str] = Field(default_factory=list)
    created_by: str
    notes: str | None = None
    created_at: datetime


class RoleAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    team_id: str
    member_name: str
    functional_role: FunctionalRole
    department: str
    is_primary: bool = True
    start_date: datetime
    end_date: datetime | None = None
    time_commitment_pct: float = Field(ge=0, le=100, default=50.0)
    backup_member: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    assigned_by: str
    notes: str | None = None
    created_at: datetime


class MeetingCadenceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    team_id: str
    cadence: MeetingCadence
    meeting_day: str = "Tuesday"
    meeting_time: str = "10:00"
    duration_minutes: int = Field(ge=0, default=60)
    platform: str = "Microsoft Teams"
    recurring: bool = True
    total_meetings_held: int = Field(ge=0, default=0)
    average_attendance: int = Field(ge=0, default=0)
    minutes_distributed: bool = True
    next_meeting_date: datetime | None = None
    managed_by: str
    notes: str | None = None
    created_at: datetime


class DeliverableTracker(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    team_id: str
    deliverable_name: str
    description: str
    status: DeliverableStatus = DeliverableStatus.NOT_STARTED
    owner: str
    due_date: datetime
    completed_date: datetime | None = None
    priority: str = "medium"
    dependency_ids: list[str] = Field(default_factory=list)
    pct_complete: float = Field(ge=0, le=100, default=0.0)
    review_required: bool = True
    reviewer: str | None = None
    created_by: str
    notes: str | None = None
    created_at: datetime


class PerformanceReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    team_id: str
    review_period: str
    review_date: datetime
    overall_rating: float = Field(ge=1.0, le=5.0, default=3.0)
    collaboration_score: float = Field(ge=1.0, le=5.0, default=3.0)
    delivery_score: float = Field(ge=1.0, le=5.0, default=3.0)
    communication_score: float = Field(ge=1.0, le=5.0, default=3.0)
    goals_met_pct: float = Field(ge=0, le=100, default=0.0)
    strengths: list[str] = Field(default_factory=list)
    improvement_areas: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    reviewed_by: str
    acknowledged: bool = False
    notes: str | None = None
    created_at: datetime


class TeamFormationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    team_name: str
    team_type: TeamType
    sponsor_name: str
    created_by: str
    max_members: int = Field(ge=0, default=20)


class TeamFormationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: TeamStatus | None = None
    charter_approved: bool | None = None
    current_members: int | None = None
    target_completion_date: datetime | None = None
    notes: str | None = None


class RoleAssignmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    team_id: str
    member_name: str
    functional_role: FunctionalRole
    department: str
    assigned_by: str
    time_commitment_pct: float = Field(ge=0, le=100, default=50.0)


class RoleAssignmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_primary: bool | None = None
    time_commitment_pct: float | None = None
    end_date: datetime | None = None
    backup_member: str | None = None
    notes: str | None = None


class MeetingCadenceRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    team_id: str
    cadence: MeetingCadence
    managed_by: str
    meeting_day: str = "Tuesday"
    duration_minutes: int = Field(ge=0, default=60)


class MeetingCadenceRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cadence: MeetingCadence | None = None
    total_meetings_held: int | None = None
    average_attendance: int | None = None
    next_meeting_date: datetime | None = None
    notes: str | None = None


class DeliverableTrackerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    team_id: str
    deliverable_name: str
    description: str
    owner: str
    due_date: datetime
    created_by: str
    priority: str = "medium"


class DeliverableTrackerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DeliverableStatus | None = None
    pct_complete: float | None = None
    completed_date: datetime | None = None
    reviewer: str | None = None
    notes: str | None = None


class PerformanceReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    team_id: str
    review_period: str
    reviewed_by: str
    overall_rating: float = Field(ge=1.0, le=5.0, default=3.0)
    collaboration_score: float = Field(ge=1.0, le=5.0, default=3.0)


class PerformanceReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    overall_rating: float | None = None
    goals_met_pct: float | None = None
    acknowledged: bool | None = None
    delivery_score: float | None = None
    notes: str | None = None


class TeamFormationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TeamFormation] = Field(default_factory=list)
    total: int = Field(ge=0)


class RoleAssignmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RoleAssignment] = Field(default_factory=list)
    total: int = Field(ge=0)


class MeetingCadenceRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MeetingCadenceRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class DeliverableTrackerListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DeliverableTracker] = Field(default_factory=list)
    total: int = Field(ge=0)


class PerformanceReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PerformanceReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class CrossFunctionalTeamMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_teams: int = Field(ge=0)
    teams_by_type: dict[str, int] = Field(default_factory=dict)
    teams_by_status: dict[str, int] = Field(default_factory=dict)
    active_teams: int = Field(ge=0)
    total_role_assignments: int = Field(ge=0)
    assignments_by_role: dict[str, int] = Field(default_factory=dict)
    total_meeting_records: int = Field(ge=0)
    meetings_by_cadence: dict[str, int] = Field(default_factory=dict)
    total_deliverables: int = Field(ge=0)
    deliverables_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_deliverables: int = Field(ge=0)
    total_reviews: int = Field(ge=0)
    avg_overall_rating: float = Field(ge=0)
