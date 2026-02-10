"""Pydantic schemas for Study Closeout module.

Manages end-of-study activities including site closure visits, document
archiving, IP reconciliation, database lock confirmation, final reports,
regulatory notifications, and financial reconciliation for clinical trials.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CloseoutStatus(str, Enum):
    """Overall status of a study closeout."""

    NOT_STARTED = "not_started"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class SiteCloseoutStatus(str, Enum):
    """Status of a site closeout within a study."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    VISIT_COMPLETED = "visit_completed"
    DOCUMENTS_COLLECTED = "documents_collected"
    IP_RECONCILED = "ip_reconciled"
    CLOSED = "closed"


class CloseoutTaskType(str, Enum):
    """Type of closeout task."""

    SITE_CLOSURE_VISIT = "site_closure_visit"
    IP_RECONCILIATION = "ip_reconciliation"
    DOCUMENT_COLLECTION = "document_collection"
    DATABASE_LOCK = "database_lock"
    DATA_ARCHIVING = "data_archiving"
    FINAL_REPORT = "final_report"
    REGULATORY_NOTIFICATION = "regulatory_notification"
    FINANCIAL_RECONCILIATION = "financial_reconciliation"
    SAMPLE_DISPOSITION = "sample_disposition"


class TaskStatus(str, Enum):
    """Status of a closeout task."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    WAIVED = "waived"
    NA = "na"


class ArchiveType(str, Enum):
    """Type of document archive."""

    ELECTRONIC = "electronic"
    PAPER = "paper"
    HYBRID = "hybrid"


class FinancialReconciliationStatus(str, Enum):
    """Status of a financial reconciliation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RECONCILED = "reconciled"
    DISPUTED = "disputed"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class StudyCloseout(BaseModel):
    """Top-level study closeout record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique closeout identifier")
    trial_id: str = Field(..., description="Trial identifier")
    trial_name: str = Field(..., description="Trial name")
    status: CloseoutStatus = Field(
        default=CloseoutStatus.NOT_STARTED, description="Overall closeout status"
    )
    planned_start_date: datetime | None = Field(
        None, description="Planned closeout start date"
    )
    actual_start_date: datetime | None = Field(
        None, description="Actual closeout start date"
    )
    target_completion_date: datetime | None = Field(
        None, description="Target closeout completion date"
    )
    actual_completion_date: datetime | None = Field(
        None, description="Actual closeout completion date"
    )
    closeout_lead: str = Field(..., description="Name of the closeout lead")
    total_sites: int = Field(default=0, ge=0, description="Total sites in the trial")
    sites_closed: int = Field(default=0, ge=0, description="Number of sites closed")
    database_locked: bool = Field(
        default=False, description="Whether the database is locked"
    )
    database_lock_date: datetime | None = Field(
        None, description="Date the database was locked"
    )
    final_csr_submitted: bool = Field(
        default=False, description="Whether the final CSR has been submitted"
    )
    final_csr_date: datetime | None = Field(
        None, description="Date the final CSR was submitted"
    )
    regulatory_notifications_sent: int = Field(
        default=0, ge=0, description="Number of regulatory notifications sent"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class SiteCloseout(BaseModel):
    """Site-level closeout record within a study closeout."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique site closeout identifier")
    closeout_id: str = Field(..., description="Parent study closeout identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    status: SiteCloseoutStatus = Field(
        default=SiteCloseoutStatus.PENDING, description="Site closeout status"
    )
    scheduled_visit_date: datetime | None = Field(
        None, description="Scheduled closure visit date"
    )
    actual_visit_date: datetime | None = Field(
        None, description="Actual closure visit date"
    )
    monitor: str | None = Field(None, description="Assigned monitor for closure visit")
    ip_reconciled: bool = Field(
        default=False, description="Whether IP has been reconciled"
    )
    ip_reconciliation_date: datetime | None = Field(
        None, description="Date IP was reconciled"
    )
    documents_collected: bool = Field(
        default=False, description="Whether all documents have been collected"
    )
    documents_collection_date: datetime | None = Field(
        None, description="Date documents were collected"
    )
    outstanding_queries_count: int = Field(
        default=0, ge=0, description="Number of outstanding data queries"
    )
    outstanding_queries_resolved_date: datetime | None = Field(
        None, description="Date all outstanding queries were resolved"
    )
    financial_reconciled: bool = Field(
        default=False, description="Whether site finances have been reconciled"
    )
    notes: str | None = Field(None, description="Site closeout notes")


class CloseoutTask(BaseModel):
    """Individual task within a study closeout."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique task identifier")
    closeout_id: str = Field(..., description="Parent study closeout identifier")
    site_id: str | None = Field(None, description="Site identifier if site-specific")
    task_type: CloseoutTaskType = Field(..., description="Type of closeout task")
    description: str = Field(..., description="Task description")
    status: TaskStatus = Field(
        default=TaskStatus.NOT_STARTED, description="Task status"
    )
    assigned_to: str = Field(..., description="Person assigned to the task")
    due_date: datetime = Field(..., description="Task due date")
    completed_date: datetime | None = Field(None, description="Task completion date")
    dependencies: list[str] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )
    blockers: list[str] = Field(
        default_factory=list, description="Description of any blockers"
    )
    notes: str | None = Field(None, description="Task notes")


class DocumentArchive(BaseModel):
    """Document archive record for trial documents."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique archive identifier")
    closeout_id: str = Field(..., description="Parent study closeout identifier")
    trial_id: str = Field(..., description="Trial identifier")
    archive_type: ArchiveType = Field(..., description="Type of archive")
    archive_location: str = Field(
        ..., description="Physical or electronic location of the archive"
    )
    total_documents: int = Field(
        default=0, ge=0, description="Total documents to archive"
    )
    archived_documents: int = Field(
        default=0, ge=0, description="Number of documents archived"
    )
    archive_date: datetime | None = Field(None, description="Date archiving completed")
    archived_by: str | None = Field(
        None, description="Person who performed the archiving"
    )
    retention_period_years: int = Field(
        default=25, ge=1, description="Retention period in years"
    )
    destruction_date: datetime | None = Field(
        None, description="Scheduled destruction date"
    )
    verified_by: str | None = Field(
        None, description="Person who verified the archive"
    )
    verification_date: datetime | None = Field(
        None, description="Date archive was verified"
    )


class RegulatoryNotification(BaseModel):
    """Regulatory notification sent as part of study closeout."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique notification identifier")
    closeout_id: str = Field(..., description="Parent study closeout identifier")
    authority_name: str = Field(..., description="Regulatory authority name")
    country: str = Field(..., description="Country of the regulatory authority")
    notification_type: str = Field(
        ..., description="Type of notification (e.g., end_of_study, final_report)"
    )
    sent_date: datetime | None = Field(None, description="Date the notification was sent")
    sent_by: str | None = Field(None, description="Person who sent the notification")
    acknowledgment_received: bool = Field(
        default=False, description="Whether acknowledgment has been received"
    )
    acknowledgment_date: datetime | None = Field(
        None, description="Date acknowledgment was received"
    )
    reference_number: str | None = Field(
        None, description="Reference number from the authority"
    )


class FinancialReconciliation(BaseModel):
    """Financial reconciliation record for a site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique reconciliation identifier")
    closeout_id: str = Field(..., description="Parent study closeout identifier")
    site_id: str = Field(..., description="Site identifier")
    total_paid: float = Field(default=0.0, ge=0.0, description="Total amount paid to site")
    total_owed: float = Field(
        default=0.0, ge=0.0, description="Total amount owed to site"
    )
    outstanding_amount: float = Field(
        default=0.0, description="Outstanding amount (owed - paid)"
    )
    holdback_amount: float = Field(
        default=0.0, ge=0.0, description="Amount held back pending closeout"
    )
    holdback_released: bool = Field(
        default=False, description="Whether holdback has been released"
    )
    final_payment_date: datetime | None = Field(
        None, description="Date of final payment"
    )
    reconciled_by: str | None = Field(
        None, description="Person who performed the reconciliation"
    )
    reconciliation_date: datetime | None = Field(
        None, description="Date reconciliation was completed"
    )
    status: FinancialReconciliationStatus = Field(
        default=FinancialReconciliationStatus.PENDING,
        description="Reconciliation status",
    )


# ---------------------------------------------------------------------------
# Closeout Progress
# ---------------------------------------------------------------------------


class CloseoutProgress(BaseModel):
    """Progress summary for a study closeout."""

    model_config = ConfigDict(from_attributes=True)

    closeout_id: str = Field(..., description="Closeout identifier")
    overall_status: CloseoutStatus = Field(..., description="Overall closeout status")
    total_sites: int = Field(default=0, ge=0, description="Total sites")
    sites_closed: int = Field(default=0, ge=0, description="Sites fully closed")
    sites_in_progress: int = Field(
        default=0, ge=0, description="Sites with closure in progress"
    )
    sites_pending: int = Field(default=0, ge=0, description="Sites pending closure")
    total_tasks: int = Field(default=0, ge=0, description="Total closeout tasks")
    tasks_completed: int = Field(default=0, ge=0, description="Tasks completed")
    tasks_in_progress: int = Field(default=0, ge=0, description="Tasks in progress")
    tasks_blocked: int = Field(default=0, ge=0, description="Tasks blocked")
    tasks_overdue: int = Field(default=0, ge=0, description="Tasks overdue")
    database_locked: bool = Field(
        default=False, description="Whether database is locked"
    )
    archives_complete: bool = Field(
        default=False, description="Whether archiving is complete"
    )
    financial_reconciliation_complete: bool = Field(
        default=False, description="Whether financial reconciliation is complete"
    )
    regulatory_notifications_sent: int = Field(
        default=0, ge=0, description="Number of regulatory notifications sent"
    )
    regulatory_notifications_acknowledged: int = Field(
        default=0, ge=0, description="Number of notifications acknowledged"
    )
    completion_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Overall completion percentage"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class StudyCloseoutCreate(BaseModel):
    """Request to create a new study closeout."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    trial_name: str = Field(..., description="Trial name")
    closeout_lead: str = Field(..., description="Closeout lead name")
    planned_start_date: datetime | None = Field(
        None, description="Planned start date"
    )
    target_completion_date: datetime | None = Field(
        None, description="Target completion date"
    )
    total_sites: int = Field(default=0, ge=0, description="Total sites")


class StudyCloseoutUpdate(BaseModel):
    """Request to update a study closeout."""

    model_config = ConfigDict(from_attributes=True)

    status: CloseoutStatus | None = Field(None, description="Overall status")
    closeout_lead: str | None = Field(None, description="Closeout lead")
    planned_start_date: datetime | None = Field(None, description="Planned start date")
    target_completion_date: datetime | None = Field(
        None, description="Target completion date"
    )
    database_locked: bool | None = Field(None, description="Database locked")
    database_lock_date: datetime | None = Field(None, description="Database lock date")
    final_csr_submitted: bool | None = Field(None, description="Final CSR submitted")
    final_csr_date: datetime | None = Field(None, description="Final CSR date")


class SiteCloseoutCreate(BaseModel):
    """Request to create a site closeout within a study closeout."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    monitor: str | None = Field(None, description="Assigned monitor")
    scheduled_visit_date: datetime | None = Field(
        None, description="Scheduled visit date"
    )


class SiteCloseoutUpdate(BaseModel):
    """Request to update a site closeout."""

    model_config = ConfigDict(from_attributes=True)

    status: SiteCloseoutStatus | None = Field(None, description="Site closeout status")
    scheduled_visit_date: datetime | None = Field(
        None, description="Scheduled visit date"
    )
    actual_visit_date: datetime | None = Field(None, description="Actual visit date")
    monitor: str | None = Field(None, description="Assigned monitor")
    ip_reconciled: bool | None = Field(None, description="IP reconciled")
    ip_reconciliation_date: datetime | None = Field(
        None, description="IP reconciliation date"
    )
    documents_collected: bool | None = Field(None, description="Documents collected")
    documents_collection_date: datetime | None = Field(
        None, description="Documents collection date"
    )
    outstanding_queries_count: int | None = Field(
        None, ge=0, description="Outstanding queries count"
    )
    outstanding_queries_resolved_date: datetime | None = Field(
        None, description="Queries resolved date"
    )
    financial_reconciled: bool | None = Field(
        None, description="Financial reconciled"
    )
    notes: str | None = Field(None, description="Notes")


class ScheduleVisitRequest(BaseModel):
    """Request to schedule a site closure visit."""

    model_config = ConfigDict(from_attributes=True)

    scheduled_visit_date: datetime = Field(..., description="Visit date to schedule")
    monitor: str = Field(..., description="Monitor assigned to the visit")


class CompleteSiteClosureRequest(BaseModel):
    """Request to complete a site closure."""

    model_config = ConfigDict(from_attributes=True)

    actual_visit_date: datetime | None = Field(None, description="Actual visit date")
    notes: str | None = Field(None, description="Closure notes")


class CloseoutTaskCreate(BaseModel):
    """Request to create a closeout task."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str | None = Field(None, description="Site ID if site-specific")
    task_type: CloseoutTaskType = Field(..., description="Task type")
    description: str = Field(..., description="Task description")
    assigned_to: str = Field(..., description="Person assigned")
    due_date: datetime = Field(..., description="Due date")
    dependencies: list[str] = Field(
        default_factory=list, description="Dependent task IDs"
    )


class CloseoutTaskUpdate(BaseModel):
    """Request to update a closeout task."""

    model_config = ConfigDict(from_attributes=True)

    status: TaskStatus | None = Field(None, description="Task status")
    assigned_to: str | None = Field(None, description="Person assigned")
    due_date: datetime | None = Field(None, description="Due date")
    completed_date: datetime | None = Field(None, description="Completion date")
    dependencies: list[str] | None = Field(None, description="Dependent task IDs")
    blockers: list[str] | None = Field(None, description="Blockers")
    notes: str | None = Field(None, description="Notes")


class DocumentArchiveCreate(BaseModel):
    """Request to create a document archive."""

    model_config = ConfigDict(from_attributes=True)

    archive_type: ArchiveType = Field(..., description="Archive type")
    archive_location: str = Field(..., description="Archive location")
    total_documents: int = Field(default=0, ge=0, description="Total documents")
    retention_period_years: int = Field(
        default=25, ge=1, description="Retention period in years"
    )


class RegulatoryNotificationCreate(BaseModel):
    """Request to create a regulatory notification."""

    model_config = ConfigDict(from_attributes=True)

    authority_name: str = Field(..., description="Authority name")
    country: str = Field(..., description="Country")
    notification_type: str = Field(..., description="Notification type")
    sent_by: str | None = Field(None, description="Sent by")


class FinancialReconciliationCreate(BaseModel):
    """Request to create a financial reconciliation."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    total_paid: float = Field(default=0.0, ge=0.0, description="Total paid")
    total_owed: float = Field(default=0.0, ge=0.0, description="Total owed")
    holdback_amount: float = Field(default=0.0, ge=0.0, description="Holdback amount")


class FinancialReconciliationUpdate(BaseModel):
    """Request to update a financial reconciliation."""

    model_config = ConfigDict(from_attributes=True)

    total_paid: float | None = Field(None, ge=0.0, description="Total paid")
    total_owed: float | None = Field(None, ge=0.0, description="Total owed")
    holdback_amount: float | None = Field(
        None, ge=0.0, description="Holdback amount"
    )
    holdback_released: bool | None = Field(None, description="Holdback released")
    final_payment_date: datetime | None = Field(
        None, description="Final payment date"
    )
    reconciled_by: str | None = Field(None, description="Reconciled by")
    reconciliation_date: datetime | None = Field(
        None, description="Reconciliation date"
    )
    status: FinancialReconciliationStatus | None = Field(None, description="Status")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class StudyCloseoutListResponse(BaseModel):
    """List of study closeouts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StudyCloseout] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteCloseoutListResponse(BaseModel):
    """List of site closeouts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteCloseout] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CloseoutTaskListResponse(BaseModel):
    """List of closeout tasks."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CloseoutTask] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DocumentArchiveListResponse(BaseModel):
    """List of document archives."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DocumentArchive] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RegulatoryNotificationListResponse(BaseModel):
    """List of regulatory notifications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatoryNotification] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class FinancialReconciliationListResponse(BaseModel):
    """List of financial reconciliations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FinancialReconciliation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class CloseoutMetrics(BaseModel):
    """Aggregated study closeout operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    active_closeouts: int = Field(
        default=0, ge=0, description="Number of active closeouts"
    )
    sites_pending_closure: int = Field(
        default=0, ge=0, description="Sites pending closure across all closeouts"
    )
    avg_days_to_close: float = Field(
        default=0.0, ge=0.0, description="Average days to close a site"
    )
    overdue_tasks: int = Field(
        default=0, ge=0, description="Number of overdue closeout tasks"
    )
    documents_archived: int = Field(
        default=0, ge=0, description="Total documents archived across all closeouts"
    )
    financial_reconciliations_pending: int = Field(
        default=0, ge=0, description="Number of pending financial reconciliations"
    )
