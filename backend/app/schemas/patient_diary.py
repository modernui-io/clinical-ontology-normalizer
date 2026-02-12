"""Pydantic schemas for Patient Diary / eDiary Management (EDIARY-MGT).

Manages electronic patient diary operations: diary entry tracking,
symptom recording, compliance monitoring, diary form validation,
diary schedule management, and eDiary operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DiaryType(str, Enum):
    SYMPTOM = "symptom"
    MEDICATION = "medication"
    QUALITY_OF_LIFE = "quality_of_life"
    PAIN = "pain"
    ADVERSE_EVENT = "adverse_event"
    ACTIVITY = "activity"
    SLEEP = "sleep"
    MOOD = "mood"


class EntryStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    MISSED = "missed"
    LATE = "late"
    INVALID = "invalid"


class ComplianceLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    NON_COMPLIANT = "non_compliant"


class ValidationStatus(str, Enum):
    VALID = "valid"
    WARNINGS = "warnings"
    ERRORS = "errors"
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"


class DiaryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    diary_type: DiaryType
    scheduled_date: datetime
    completed_date: datetime | None = None
    status: EntryStatus = EntryStatus.PENDING
    form_version: str
    responses: dict[str, str | float | bool] = Field(default_factory=dict)
    total_questions: int = Field(ge=0, default=0)
    answered_questions: int = Field(ge=0, default=0)
    completion_pct: float = Field(ge=0, le=100, default=0.0)
    time_to_complete_minutes: float | None = None
    device_type: str | None = None
    submission_source: str = "mobile_app"
    validated: bool = False
    created_at: datetime


class SymptomRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entry_id: str
    trial_id: str
    subject_id: str
    symptom_name: str
    severity_score: int = Field(ge=0, le=10)
    frequency: str | None = None
    onset_date: datetime | None = None
    duration_hours: float | None = None
    interference_score: int | None = Field(ge=0, le=10, default=None)
    treatment_taken: bool = False
    treatment_description: str | None = None
    reported_to_site: bool = False
    ae_reference: str | None = None
    created_at: datetime


class DiarySchedule(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    diary_type: DiaryType
    form_name: str
    frequency: str
    window_before_hours: int = Field(ge=0, default=0)
    window_after_hours: int = Field(ge=0, default=24)
    reminder_enabled: bool = True
    reminder_hours_before: int = Field(ge=0, default=2)
    start_visit: str | None = None
    end_visit: str | None = None
    total_entries_expected: int = Field(ge=0, default=0)
    is_active: bool = True
    created_by: str
    created_at: datetime


class DiaryCompliance(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    period_start: datetime
    period_end: datetime
    entries_expected: int = Field(ge=0, default=0)
    entries_completed: int = Field(ge=0, default=0)
    entries_missed: int = Field(ge=0, default=0)
    entries_late: int = Field(ge=0, default=0)
    compliance_rate: float = Field(ge=0, le=100, default=0.0)
    compliance_level: ComplianceLevel = ComplianceLevel.GOOD
    avg_completion_time_min: float | None = None
    consecutive_misses: int = Field(ge=0, default=0)
    alert_triggered: bool = False
    calculated_at: datetime
    created_at: datetime


class DiaryValidation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entry_id: str
    trial_id: str
    validation_status: ValidationStatus = ValidationStatus.PENDING_REVIEW
    total_checks: int = Field(ge=0, default=0)
    passed_checks: int = Field(ge=0, default=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    out_of_range_values: list[str] = Field(default_factory=list)
    reviewer: str | None = None
    review_date: datetime | None = None
    review_notes: str | None = None
    created_at: datetime


class DiaryEntryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    diary_type: DiaryType
    form_version: str
    device_type: str | None = None


class DiaryEntryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: EntryStatus | None = None
    responses: dict[str, str | float | bool] | None = None
    answered_questions: int | None = None
    validated: bool | None = None


class SymptomRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entry_id: str
    trial_id: str
    subject_id: str
    symptom_name: str
    severity_score: int = Field(ge=0, le=10)
    frequency: str | None = None
    treatment_taken: bool = False


class SymptomRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity_score: int | None = Field(ge=0, le=10, default=None)
    reported_to_site: bool | None = None
    ae_reference: str | None = None
    treatment_description: str | None = None


class DiaryScheduleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    diary_type: DiaryType
    form_name: str
    frequency: str
    created_by: str
    window_after_hours: int = 24
    reminder_enabled: bool = True


class DiaryScheduleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    reminder_enabled: bool | None = None
    window_after_hours: int | None = None
    end_visit: str | None = None


class DiaryComplianceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    period_start: datetime
    period_end: datetime


class DiaryComplianceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entries_completed: int | None = None
    entries_missed: int | None = None
    compliance_level: ComplianceLevel | None = None
    alert_triggered: bool | None = None


class DiaryValidationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entry_id: str
    trial_id: str
    total_checks: int = Field(ge=0, default=0)


class DiaryValidationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    validation_status: ValidationStatus | None = None
    reviewer: str | None = None
    review_notes: str | None = None


class DiaryEntryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiaryEntry] = Field(default_factory=list)
    total: int = Field(ge=0)


class SymptomRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SymptomRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class DiaryScheduleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiarySchedule] = Field(default_factory=list)
    total: int = Field(ge=0)


class DiaryComplianceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiaryCompliance] = Field(default_factory=list)
    total: int = Field(ge=0)


class DiaryValidationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiaryValidation] = Field(default_factory=list)
    total: int = Field(ge=0)


class PatientDiaryMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_entries: int = Field(ge=0)
    entries_by_type: dict[str, int] = Field(default_factory=dict)
    entries_by_status: dict[str, int] = Field(default_factory=dict)
    overall_compliance_rate: float = Field(ge=0, le=100)
    compliance_by_level: dict[str, int] = Field(default_factory=dict)
    total_symptoms: int = Field(ge=0)
    avg_severity_score: float = Field(ge=0)
    total_schedules: int = Field(ge=0)
    active_schedules: int = Field(ge=0)
    total_validations: int = Field(ge=0)
    validations_with_errors: int = Field(ge=0)
    avg_completion_time_min: float = Field(ge=0)
