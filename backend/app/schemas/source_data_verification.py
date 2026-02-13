"""Pydantic schemas for Source Data Verification (SDV).

Manages source data verification operations: SDV task tracking, finding
documentation, site-level SDV progress, review records, and SDV metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SDVTaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class SDVPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ROUTINE = "routine"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"
    INFORMATIONAL = "informational"


class FindingStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"


class ReviewOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL_PASS = "conditional_pass"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"


# --- Main entities ---

class SDVTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str
    visit_name: str
    crf_name: str
    task_status: SDVTaskStatus = SDVTaskStatus.PENDING
    priority: SDVPriority = SDVPriority.MEDIUM
    assigned_to: str
    due_date: datetime
    completed_date: datetime | None = None
    fields_verified: int = Field(ge=0, default=0)
    fields_total: int = Field(ge=0, default=0)
    discrepancies_found: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


class SDVFinding(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    task_id: str
    site_id: str
    subject_id: str
    field_name: str
    finding_severity: FindingSeverity = FindingSeverity.MINOR
    finding_status: FindingStatus = FindingStatus.OPEN
    source_value: str
    crf_value: str
    description: str
    corrective_action: str | None = None
    identified_by: str
    resolved_by: str | None = None
    resolved_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class SDVSiteProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    site_name: str
    total_subjects: int = Field(ge=0, default=0)
    subjects_verified: int = Field(ge=0, default=0)
    total_crfs: int = Field(ge=0, default=0)
    crfs_verified: int = Field(ge=0, default=0)
    total_fields: int = Field(ge=0, default=0)
    fields_verified: int = Field(ge=0, default=0)
    sdv_completion_pct: float = Field(ge=0, le=100, default=0.0)
    open_findings: int = Field(ge=0, default=0)
    last_sdv_date: datetime | None = None
    next_scheduled_date: datetime | None = None
    assigned_cra: str
    notes: str | None = None
    created_at: datetime


class SDVReviewRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    review_date: datetime
    reviewer_name: str
    review_type: str
    subjects_reviewed: int = Field(ge=0, default=0)
    crfs_reviewed: int = Field(ge=0, default=0)
    findings_generated: int = Field(ge=0, default=0)
    review_outcome: ReviewOutcome = ReviewOutcome.PASS
    duration_hours: float = Field(ge=0, default=0.0)
    follow_up_required: bool = False
    follow_up_due_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class SDVTaskCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    subject_id: str
    visit_name: str
    crf_name: str
    priority: SDVPriority = SDVPriority.MEDIUM
    assigned_to: str
    due_date: datetime
    fields_total: int = Field(ge=0, default=0)


class SDVTaskUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_status: SDVTaskStatus | None = None
    fields_verified: int | None = None
    discrepancies_found: int | None = None
    completed_date: datetime | None = None
    notes: str | None = None


class SDVFindingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    task_id: str
    site_id: str
    subject_id: str
    field_name: str
    finding_severity: FindingSeverity = FindingSeverity.MINOR
    source_value: str
    crf_value: str
    description: str
    identified_by: str


class SDVFindingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    finding_status: FindingStatus | None = None
    corrective_action: str | None = None
    resolved_by: str | None = None
    resolved_date: datetime | None = None
    notes: str | None = None


class SDVSiteProgressCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    site_name: str
    total_subjects: int = Field(ge=0, default=0)
    total_crfs: int = Field(ge=0, default=0)
    total_fields: int = Field(ge=0, default=0)
    assigned_cra: str


class SDVSiteProgressUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subjects_verified: int | None = None
    crfs_verified: int | None = None
    fields_verified: int | None = None
    sdv_completion_pct: float | None = None
    open_findings: int | None = None
    last_sdv_date: datetime | None = None
    next_scheduled_date: datetime | None = None
    notes: str | None = None


class SDVReviewRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    reviewer_name: str
    review_type: str
    subjects_reviewed: int = Field(ge=0, default=0)
    crfs_reviewed: int = Field(ge=0, default=0)
    duration_hours: float = Field(ge=0, default=0.0)


class SDVReviewRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    findings_generated: int | None = None
    review_outcome: ReviewOutcome | None = None
    follow_up_required: bool | None = None
    follow_up_due_date: datetime | None = None
    notes: str | None = None


# --- List responses ---

class SDVTaskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SDVTask] = Field(default_factory=list)
    total: int = Field(ge=0)


class SDVFindingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SDVFinding] = Field(default_factory=list)
    total: int = Field(ge=0)


class SDVSiteProgressListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SDVSiteProgress] = Field(default_factory=list)
    total: int = Field(ge=0)


class SDVReviewRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SDVReviewRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class SourceDataVerificationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_tasks: int = Field(ge=0)
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    tasks_by_priority: dict[str, int] = Field(default_factory=dict)
    task_completion_rate: float = Field(ge=0)
    total_findings: int = Field(ge=0)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_status: dict[str, int] = Field(default_factory=dict)
    open_finding_rate: float = Field(ge=0)
    total_sites_tracked: int = Field(ge=0)
    avg_sdv_completion_pct: float = Field(ge=0)
    total_reviews: int = Field(ge=0)
    reviews_by_outcome: dict[str, int] = Field(default_factory=dict)
