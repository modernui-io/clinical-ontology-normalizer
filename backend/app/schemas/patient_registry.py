"""Pydantic schemas for Patient Registry & Long-Term Follow-Up (PAT-REG).

Manages disease registries, patient enrollment in registries, long-term
follow-up visit tracking, outcome reporting, registry milestones, and
registry operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RegistryType(str, Enum):
    DISEASE_REGISTRY = "disease_registry"
    PRODUCT_REGISTRY = "product_registry"
    PREGNANCY_REGISTRY = "pregnancy_registry"
    NATURAL_HISTORY = "natural_history"
    POST_MARKETING = "post_marketing"
    EXPANDED_ACCESS = "expanded_access"


class RegistryStatus(str, Enum):
    PLANNING = "planning"
    ENROLLING = "enrolling"
    ACTIVE = "active"
    FOLLOW_UP_ONLY = "follow_up_only"
    CLOSED = "closed"
    ARCHIVED = "archived"


class EnrollmentStatus(str, Enum):
    SCREENED = "screened"
    CONSENTED = "consented"
    ENROLLED = "enrolled"
    ACTIVE = "active"
    LOST_TO_FOLLOW_UP = "lost_to_follow_up"
    WITHDRAWN = "withdrawn"
    DECEASED = "deceased"
    COMPLETED = "completed"


class FollowUpType(str, Enum):
    SCHEDULED = "scheduled"
    UNSCHEDULED = "unscheduled"
    SAFETY = "safety"
    ANNUAL_REVIEW = "annual_review"
    MILESTONE = "milestone"
    END_OF_STUDY = "end_of_study"


class FollowUpStatus(str, Enum):
    SCHEDULED = "scheduled"
    OVERDUE = "overdue"
    COMPLETED = "completed"
    MISSED = "missed"
    CANCELLED = "cancelled"


class OutcomeCategory(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SAFETY = "safety"
    PATIENT_REPORTED = "patient_reported"
    BIOMARKER = "biomarker"
    SURVIVAL = "survival"


class Registry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str | None = None
    name: str
    registry_type: RegistryType
    disease_area: str
    description: str
    status: RegistryStatus = RegistryStatus.PLANNING
    sponsor: str
    target_enrollment: int = Field(ge=0, default=0)
    current_enrollment: int = Field(ge=0, default=0)
    follow_up_duration_months: int = Field(ge=0, default=0)
    countries: list[str] = Field(default_factory=list)
    sites_count: int = Field(ge=0, default=0)
    irb_approved: bool = False
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime


class RegistryPatient(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    registry_id: str
    patient_id: str
    site_id: str
    enrollment_status: EnrollmentStatus = EnrollmentStatus.SCREENED
    consent_date: datetime | None = None
    enrollment_date: datetime | None = None
    last_follow_up_date: datetime | None = None
    next_follow_up_date: datetime | None = None
    follow_up_visits_completed: int = Field(ge=0, default=0)
    follow_up_visits_missed: int = Field(ge=0, default=0)
    withdrawal_reason: str | None = None
    withdrawal_date: datetime | None = None
    notes: str | None = None


class FollowUpVisit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    registry_patient_id: str
    visit_type: FollowUpType
    visit_number: int = Field(ge=1)
    scheduled_date: datetime
    actual_date: datetime | None = None
    status: FollowUpStatus = FollowUpStatus.SCHEDULED
    assessments_completed: list[str] = Field(default_factory=list)
    adverse_events_reported: int = Field(ge=0, default=0)
    data_complete: bool = False
    conducted_by: str | None = None
    notes: str | None = None


class OutcomeReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    registry_patient_id: str
    visit_id: str | None = None
    category: OutcomeCategory
    outcome_name: str
    value: str
    unit: str | None = None
    baseline_value: str | None = None
    change_from_baseline: str | None = None
    clinically_significant: bool | None = None
    reported_date: datetime
    reported_by: str


class RegistryMilestone(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    registry_id: str
    milestone_name: str
    description: str
    target_date: datetime
    actual_date: datetime | None = None
    achieved: bool = False
    responsible_person: str
    notes: str | None = None


class RegistryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str | None = None
    name: str
    registry_type: RegistryType
    disease_area: str
    description: str
    sponsor: str
    target_enrollment: int = Field(ge=0, default=0)
    follow_up_duration_months: int = Field(ge=0, default=0)
    countries: list[str] = Field(default_factory=list)


class RegistryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: RegistryStatus | None = None
    target_enrollment: int | None = None
    current_enrollment: int | None = None
    sites_count: int | None = None
    irb_approved: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class RegistryPatientCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    registry_id: str
    patient_id: str
    site_id: str


class RegistryPatientUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    enrollment_status: EnrollmentStatus | None = None
    consent_date: datetime | None = None
    enrollment_date: datetime | None = None
    withdrawal_reason: str | None = None
    notes: str | None = None


class FollowUpVisitCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    registry_patient_id: str
    visit_type: FollowUpType
    visit_number: int = Field(ge=1)
    scheduled_date: datetime


class FollowUpVisitUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: FollowUpStatus | None = None
    actual_date: datetime | None = None
    assessments_completed: list[str] | None = None
    adverse_events_reported: int | None = None
    data_complete: bool | None = None
    conducted_by: str | None = None
    notes: str | None = None


class OutcomeReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    registry_patient_id: str
    visit_id: str | None = None
    category: OutcomeCategory
    outcome_name: str
    value: str
    unit: str | None = None
    baseline_value: str | None = None
    change_from_baseline: str | None = None
    clinically_significant: bool | None = None
    reported_by: str


class RegistryMilestoneCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    registry_id: str
    milestone_name: str
    description: str
    target_date: datetime
    responsible_person: str


class RegistryMilestoneUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    actual_date: datetime | None = None
    achieved: bool | None = None
    notes: str | None = None


class RegistryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[Registry] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegistryPatientListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegistryPatient] = Field(default_factory=list)
    total: int = Field(ge=0)


class FollowUpVisitListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FollowUpVisit] = Field(default_factory=list)
    total: int = Field(ge=0)


class OutcomeReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[OutcomeReport] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegistryMilestoneListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegistryMilestone] = Field(default_factory=list)
    total: int = Field(ge=0)


class PatientRegistryMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_registries: int = Field(ge=0)
    registries_by_type: dict[str, int] = Field(default_factory=dict)
    registries_by_status: dict[str, int] = Field(default_factory=dict)
    total_patients: int = Field(ge=0)
    patients_by_status: dict[str, int] = Field(default_factory=dict)
    active_patients: int = Field(ge=0)
    lost_to_follow_up: int = Field(ge=0)
    total_follow_up_visits: int = Field(ge=0)
    visits_by_status: dict[str, int] = Field(default_factory=dict)
    visit_completion_rate: float = Field(ge=0, le=100)
    total_outcomes: int = Field(ge=0)
    outcomes_by_category: dict[str, int] = Field(default_factory=dict)
    total_milestones: int = Field(ge=0)
    milestones_achieved: int = Field(ge=0)
    retention_rate: float = Field(ge=0, le=100)
