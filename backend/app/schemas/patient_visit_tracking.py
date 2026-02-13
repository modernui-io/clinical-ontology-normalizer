"""Pydantic schemas for Patient Visit Tracking (PVT-TRK).

Manages patient visit operations: visit schedules, visit adherence records,
visit window violations, missed visit follow-ups, and visit tracking metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VisitStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    MISSED = "missed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


class VisitType(str, Enum):
    SCREENING = "screening"
    BASELINE = "baseline"
    TREATMENT = "treatment"
    FOLLOW_UP = "follow_up"
    END_OF_STUDY = "end_of_study"
    UNSCHEDULED = "unscheduled"


class AdherenceRating(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    NON_COMPLIANT = "non_compliant"
    NOT_EVALUATED = "not_evaluated"


class ViolationSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATIONAL = "informational"
    WAIVED = "waived"


class FollowUpStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    CLOSED = "closed"
    UNABLE_TO_REACH = "unable_to_reach"


# --- Main entities ---

class VisitSchedule(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit_type: VisitType
    visit_number: int = Field(ge=0, default=1)
    visit_name: str
    visit_status: VisitStatus = VisitStatus.SCHEDULED
    scheduled_date: datetime
    actual_date: datetime | None = None
    window_open_date: datetime | None = None
    window_close_date: datetime | None = None
    duration_minutes: int = Field(ge=0, default=60)
    investigator_name: str | None = None
    location: str | None = None
    procedures_planned: int = Field(ge=0, default=0)
    procedures_completed: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


class VisitAdherence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit_schedule_id: str
    adherence_rating: AdherenceRating = AdherenceRating.NOT_EVALUATED
    days_from_target: int = 0
    within_window: bool = True
    procedures_adherence_pct: float = Field(ge=0, le=100, default=100.0)
    medication_compliance: bool = True
    diary_completion: bool = True
    assessment_date: datetime
    assessed_by: str
    risk_flag: bool = False
    notes: str | None = None
    created_at: datetime


class WindowViolation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit_schedule_id: str
    violation_severity: ViolationSeverity = ViolationSeverity.MINOR
    days_out_of_window: int = Field(ge=0, default=0)
    expected_window_open: datetime
    expected_window_close: datetime
    actual_visit_date: datetime
    reason: str
    impact_on_data: str | None = None
    protocol_deviation_filed: bool = False
    deviation_id: str | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class MissedVisitFollowUp(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit_schedule_id: str
    follow_up_status: FollowUpStatus = FollowUpStatus.PENDING
    contact_attempts: int = Field(ge=0, default=0)
    last_contact_date: datetime | None = None
    reason_for_miss: str | None = None
    reschedule_date: datetime | None = None
    retention_risk: bool = False
    assigned_to: str
    escalated_to: str | None = None
    resolution_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class VisitScheduleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    visit_type: VisitType
    visit_number: int = Field(ge=0, default=1)
    visit_name: str
    scheduled_date: datetime
    duration_minutes: int = Field(ge=0, default=60)


class VisitScheduleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    visit_status: VisitStatus | None = None
    actual_date: datetime | None = None
    investigator_name: str | None = None
    procedures_completed: int | None = None
    notes: str | None = None


class VisitAdherenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    visit_schedule_id: str
    assessed_by: str
    assessment_date: datetime
    days_from_target: int = 0


class VisitAdherenceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    adherence_rating: AdherenceRating | None = None
    within_window: bool | None = None
    procedures_adherence_pct: float | None = None
    medication_compliance: bool | None = None
    risk_flag: bool | None = None
    notes: str | None = None


class WindowViolationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    visit_schedule_id: str
    violation_severity: ViolationSeverity = ViolationSeverity.MINOR
    days_out_of_window: int = Field(ge=0, default=0)
    expected_window_open: datetime
    expected_window_close: datetime
    actual_visit_date: datetime
    reason: str


class WindowViolationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    impact_on_data: str | None = None
    protocol_deviation_filed: bool | None = None
    deviation_id: str | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class MissedVisitFollowUpCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    visit_schedule_id: str
    assigned_to: str
    reason_for_miss: str | None = None


class MissedVisitFollowUpUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    follow_up_status: FollowUpStatus | None = None
    contact_attempts: int | None = None
    last_contact_date: datetime | None = None
    reschedule_date: datetime | None = None
    retention_risk: bool | None = None
    escalated_to: str | None = None
    notes: str | None = None


# --- List responses ---

class VisitScheduleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[VisitSchedule] = Field(default_factory=list)
    total: int = Field(ge=0)


class VisitAdherenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[VisitAdherence] = Field(default_factory=list)
    total: int = Field(ge=0)


class WindowViolationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[WindowViolation] = Field(default_factory=list)
    total: int = Field(ge=0)


class MissedVisitFollowUpListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MissedVisitFollowUp] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class PatientVisitTrackingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_visits: int = Field(ge=0)
    visits_by_status: dict[str, int] = Field(default_factory=dict)
    visits_by_type: dict[str, int] = Field(default_factory=dict)
    visit_completion_rate: float = Field(ge=0)
    total_adherence_records: int = Field(ge=0)
    adherence_by_rating: dict[str, int] = Field(default_factory=dict)
    within_window_rate: float = Field(ge=0)
    total_window_violations: int = Field(ge=0)
    violations_by_severity: dict[str, int] = Field(default_factory=dict)
    total_missed_follow_ups: int = Field(ge=0)
    follow_ups_by_status: dict[str, int] = Field(default_factory=dict)
    missed_visit_resolution_rate: float = Field(ge=0)
