"""Pydantic schemas for Clinical Data Review Management (DATA-REV).

Manages clinical data review operations: data review listings, query
resolution tracking, data cleaning tasks, edit check management,
reviewer assignments, and data review operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ListingType(str, Enum):
    PATIENT = "patient"
    VISIT = "visit"
    LABORATORY = "laboratory"
    ADVERSE_EVENT = "adverse_event"
    CONCOMITANT_MEDICATION = "concomitant_medication"
    VITAL_SIGNS = "vital_signs"
    EFFICACY = "efficacy"
    PROTOCOL_DEVIATION = "protocol_deviation"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    QUERIES_ISSUED = "queries_issued"
    CLEAN = "clean"
    LOCKED = "locked"


class QueryStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"
    REQUERIED = "requeried"
    CANCELLED = "cancelled"


class QueryPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EditCheckSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
    HARD_STOP = "hard_stop"
    INFORMATIONAL = "informational"


class DataReviewListing(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str | None = None
    listing_type: ListingType
    listing_name: str
    review_status: ReviewStatus = ReviewStatus.PENDING
    total_records: int = Field(ge=0, default=0)
    reviewed_records: int = Field(ge=0, default=0)
    clean_records: int = Field(ge=0, default=0)
    records_with_queries: int = Field(ge=0, default=0)
    completion_pct: float = Field(ge=0, le=100, default=0.0)
    data_cutoff_date: datetime | None = None
    assigned_reviewer: str | None = None
    review_start_date: datetime | None = None
    review_end_date: datetime | None = None
    locked_by: str | None = None
    locked_date: datetime | None = None
    created_at: datetime


class DataQuery(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str
    listing_id: str | None = None
    form_name: str
    field_name: str
    visit_name: str | None = None
    query_text: str
    query_status: QueryStatus = QueryStatus.OPEN
    priority: QueryPriority = QueryPriority.MEDIUM
    query_type: str = "manual"
    current_value: str | None = None
    expected_value: str | None = None
    response_text: str | None = None
    response_date: datetime | None = None
    responded_by: str | None = None
    issued_by: str
    issued_date: datetime
    closed_by: str | None = None
    closed_date: datetime | None = None
    days_open: int = Field(ge=0, default=0)
    requery_count: int = Field(ge=0, default=0)
    created_at: datetime


class DataCleaningTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    task_name: str
    description: str
    listing_id: str | None = None
    assigned_to: str
    status: str = "pending"
    priority: QueryPriority = QueryPriority.MEDIUM
    records_to_review: int = Field(ge=0, default=0)
    records_cleaned: int = Field(ge=0, default=0)
    queries_generated: int = Field(ge=0, default=0)
    due_date: datetime | None = None
    completed_date: datetime | None = None
    verification_required: bool = False
    verified_by: str | None = None
    notes: str | None = None
    created_at: datetime


class EditCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    check_name: str
    check_description: str
    form_name: str
    field_name: str
    severity: EditCheckSeverity = EditCheckSeverity.WARNING
    check_logic: str
    is_active: bool = True
    auto_query: bool = False
    total_firings: int = Field(ge=0, default=0)
    false_positive_count: int = Field(ge=0, default=0)
    false_positive_rate: float = Field(ge=0, le=100, default=0.0)
    last_run_date: datetime | None = None
    created_by: str
    approved_by: str | None = None
    version: str = "1.0"
    created_at: datetime


class ReviewerAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reviewer_name: str
    reviewer_role: str
    assigned_sites: list[str] = Field(default_factory=list)
    assigned_listings: list[str] = Field(default_factory=list)
    assignment_date: datetime
    workload_records: int = Field(ge=0, default=0)
    completed_records: int = Field(ge=0, default=0)
    queries_issued: int = Field(ge=0, default=0)
    avg_review_time_minutes: float | None = None
    is_active: bool = True
    last_review_date: datetime | None = None
    created_at: datetime


class DataReviewListingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    listing_type: ListingType
    listing_name: str
    site_id: str | None = None
    total_records: int = Field(ge=0, default=0)


class DataReviewListingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    review_status: ReviewStatus | None = None
    assigned_reviewer: str | None = None
    reviewed_records: int | None = None
    locked_by: str | None = None


class DataQueryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    subject_id: str
    form_name: str
    field_name: str
    query_text: str
    issued_by: str
    listing_id: str | None = None
    priority: QueryPriority = QueryPriority.MEDIUM


class DataQueryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    query_status: QueryStatus | None = None
    response_text: str | None = None
    responded_by: str | None = None
    closed_by: str | None = None
    priority: QueryPriority | None = None


class DataCleaningTaskCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    task_name: str
    description: str
    assigned_to: str
    records_to_review: int = Field(ge=0, default=0)
    listing_id: str | None = None
    due_date: datetime | None = None


class DataCleaningTaskUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    records_cleaned: int | None = None
    queries_generated: int | None = None
    verified_by: str | None = None
    notes: str | None = None


class EditCheckCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    check_name: str
    check_description: str
    form_name: str
    field_name: str
    check_logic: str
    created_by: str
    severity: EditCheckSeverity = EditCheckSeverity.WARNING


class EditCheckUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    auto_query: bool | None = None
    approved_by: str | None = None
    severity: EditCheckSeverity | None = None


class ReviewerAssignmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reviewer_name: str
    reviewer_role: str
    assigned_sites: list[str] = Field(default_factory=list)


class ReviewerAssignmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    assigned_listings: list[str] | None = None
    workload_records: int | None = None


class DataReviewListingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataReviewListing] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataQueryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataQuery] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataCleaningTaskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataCleaningTask] = Field(default_factory=list)
    total: int = Field(ge=0)


class EditCheckListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EditCheck] = Field(default_factory=list)
    total: int = Field(ge=0)


class ReviewerAssignmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ReviewerAssignment] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalDataReviewMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_listings: int = Field(ge=0)
    listings_by_type: dict[str, int] = Field(default_factory=dict)
    listings_by_status: dict[str, int] = Field(default_factory=dict)
    overall_review_completion_pct: float = Field(ge=0, le=100)
    total_queries: int = Field(ge=0)
    queries_by_status: dict[str, int] = Field(default_factory=dict)
    queries_by_priority: dict[str, int] = Field(default_factory=dict)
    avg_query_resolution_days: float = Field(ge=0)
    total_cleaning_tasks: int = Field(ge=0)
    cleaning_tasks_completed: int = Field(ge=0)
    total_edit_checks: int = Field(ge=0)
    active_edit_checks: int = Field(ge=0)
    avg_false_positive_rate: float = Field(ge=0)
    total_reviewers: int = Field(ge=0)
    active_reviewers: int = Field(ge=0)
