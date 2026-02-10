"""Pydantic schemas for Data Review & Lock (CLINICAL-DL).

Manages database lock lifecycle for clinical trials: data freeze, soft/hard
lock workflows, clean data flagging, unblinding procedures, interim analysis
locks, data cut management, lock checklists, and pre-lock validation summaries.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LockType(str, Enum):
    """Type of database lock."""

    SOFT_LOCK = "soft_lock"
    HARD_LOCK = "hard_lock"
    INTERIM_LOCK = "interim_lock"
    FINAL_LOCK = "final_lock"


class LockStatus(str, Enum):
    """Lifecycle status of a database lock."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    CANCELLED = "cancelled"


class DataCutType(str, Enum):
    """Type of data cut."""

    INTERIM_ANALYSIS = "interim_analysis"
    FINAL_ANALYSIS = "final_analysis"
    DSMB_REVIEW = "dsmb_review"
    REGULATORY_SUBMISSION = "regulatory_submission"


class CleanDataStatus(str, Enum):
    """Status of a clean data record."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CLEAN = "clean"
    FLAGGED = "flagged"


class UnblindingType(str, Enum):
    """Type of unblinding request."""

    PARTIAL = "partial"
    FULL = "full"
    EMERGENCY = "emergency"


class ChecklistItemStatus(str, Enum):
    """Status of a lock checklist item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class DataLock(BaseModel):
    """A database lock record for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique lock identifier")
    trial_id: str = Field(..., description="Trial identifier")
    lock_type: LockType = Field(..., description="Type of database lock")
    status: LockStatus = Field(default=LockStatus.PLANNED, description="Lock lifecycle status")
    description: str = Field(..., description="Description of the lock scope and purpose")
    planned_date: datetime = Field(..., description="Planned lock date")
    executed_date: datetime | None = Field(None, description="Actual lock execution date")
    unlocked_date: datetime | None = Field(None, description="Date lock was removed (if unlocked)")
    locked_by: str | None = Field(None, description="Person who executed the lock")
    unlocked_by: str | None = Field(None, description="Person who unlocked (if applicable)")
    unlock_reason: str | None = Field(None, description="Reason for unlocking")
    subjects_locked: int = Field(default=0, ge=0, description="Number of subjects included in lock")
    forms_locked: int = Field(default=0, ge=0, description="Number of CRF forms locked")
    sites_included: list[str] = Field(default_factory=list, description="Sites included in the lock")
    audit_trail: list[str] = Field(
        default_factory=list, description="Audit trail entries for lock lifecycle"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class DataCut(BaseModel):
    """A data cut associated with a database lock."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique data cut identifier")
    lock_id: str = Field(..., description="Associated lock identifier")
    cut_type: DataCutType = Field(..., description="Type of data cut")
    cutoff_date: datetime = Field(..., description="Data cutoff date")
    subjects_included: int = Field(default=0, ge=0, description="Number of subjects in the cut")
    forms_included: int = Field(default=0, ge=0, description="Number of forms in the cut")
    description: str = Field(default="", description="Description of the data cut")
    created_at: datetime = Field(..., description="Record creation timestamp")


class CleanDataRecord(BaseModel):
    """A clean data review record for a subject/form/visit combination."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique clean data record identifier")
    lock_id: str = Field(..., description="Associated lock identifier")
    subject_id: str = Field(..., description="Subject identifier")
    form: str = Field(..., description="CRF form name")
    visit: str = Field(..., description="Visit name or number")
    status: CleanDataStatus = Field(
        default=CleanDataStatus.NOT_STARTED, description="Clean data status"
    )
    reviewer: str | None = Field(None, description="Reviewer who checked the data")
    flagged_fields: list[str] = Field(
        default_factory=list, description="Fields flagged for review"
    )
    review_date: datetime | None = Field(None, description="Date of review")
    notes: str | None = Field(None, description="Review notes")


class UnblindingRequest(BaseModel):
    """An unblinding request record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique unblinding request identifier")
    lock_id: str = Field(..., description="Associated lock identifier")
    unblinding_type: UnblindingType = Field(..., description="Type of unblinding")
    justification: str = Field(..., description="Justification for unblinding")
    requestor: str = Field(..., description="Person requesting unblinding")
    approver: str | None = Field(None, description="Person who approved unblinding")
    approved_date: datetime | None = Field(None, description="Date of approval")
    executed: bool = Field(default=False, description="Whether unblinding has been executed")
    executed_date: datetime | None = Field(None, description="Date unblinding was executed")
    subjects_unblinded: list[str] = Field(
        default_factory=list, description="List of unblinded subject IDs"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class LockChecklistItem(BaseModel):
    """A single item in a lock checklist."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique checklist item identifier")
    item_description: str = Field(..., description="Description of the checklist item")
    responsible: str = Field(..., description="Person responsible for this item")
    status: ChecklistItemStatus = Field(
        default=ChecklistItemStatus.PENDING, description="Item completion status"
    )
    completion_date: datetime | None = Field(None, description="Date item was completed")


class LockChecklist(BaseModel):
    """A pre-lock checklist for a database lock."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique checklist identifier")
    lock_id: str = Field(..., description="Associated lock identifier")
    name: str = Field(..., description="Checklist name")
    items: list[LockChecklistItem] = Field(default_factory=list, description="Checklist items")
    created_at: datetime = Field(..., description="Record creation timestamp")


class PreLockSummary(BaseModel):
    """Summary of pre-lock validation checks."""

    model_config = ConfigDict(from_attributes=True)

    lock_id: str = Field(..., description="Lock identifier")
    total_queries_open: int = Field(default=0, ge=0, description="Total open data queries")
    total_deviations: int = Field(default=0, ge=0, description="Total outstanding protocol deviations")
    sdv_completion_rate: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Source data verification completion rate (%)"
    )
    clean_data_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of data marked clean (%)"
    )
    outstanding_aes: int = Field(default=0, ge=0, description="Outstanding adverse events to reconcile")
    pending_signatures: int = Field(default=0, ge=0, description="Pending investigator signatures")
    ready_to_lock: bool = Field(
        default=False, description="Whether pre-lock checks pass for lock execution"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class DataLockCreate(BaseModel):
    """Request to create a new database lock."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    lock_type: LockType = Field(..., description="Type of database lock")
    description: str = Field(..., description="Description of the lock scope and purpose")
    planned_date: datetime = Field(..., description="Planned lock date")
    sites_included: list[str] = Field(default_factory=list, description="Sites included in the lock")


class DataLockUpdate(BaseModel):
    """Request to update a database lock."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = Field(None, description="Lock description")
    planned_date: datetime | None = Field(None, description="Planned lock date")
    lock_type: LockType | None = Field(None, description="Lock type")
    sites_included: list[str] | None = Field(None, description="Sites included")


class DataCutCreate(BaseModel):
    """Request to create a data cut."""

    model_config = ConfigDict(from_attributes=True)

    cut_type: DataCutType = Field(..., description="Type of data cut")
    cutoff_date: datetime = Field(..., description="Data cutoff date")
    subjects_included: int = Field(default=0, ge=0, description="Number of subjects in the cut")
    forms_included: int = Field(default=0, ge=0, description="Number of forms in the cut")
    description: str = Field(default="", description="Description of the data cut")


class CleanDataRecordCreate(BaseModel):
    """Request to create a clean data record."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: str = Field(..., description="Subject identifier")
    form: str = Field(..., description="CRF form name")
    visit: str = Field(..., description="Visit name or number")
    reviewer: str | None = Field(None, description="Reviewer name")


class CleanDataRecordUpdate(BaseModel):
    """Request to update a clean data record."""

    model_config = ConfigDict(from_attributes=True)

    status: CleanDataStatus | None = Field(None, description="Clean data status")
    reviewer: str | None = Field(None, description="Reviewer name")
    flagged_fields: list[str] | None = Field(None, description="Fields flagged for review")
    notes: str | None = Field(None, description="Review notes")


class UnblindingRequestCreate(BaseModel):
    """Request to create an unblinding request."""

    model_config = ConfigDict(from_attributes=True)

    unblinding_type: UnblindingType = Field(..., description="Type of unblinding")
    justification: str = Field(..., description="Justification for unblinding")
    requestor: str = Field(..., description="Person requesting unblinding")


class UnblindingApproval(BaseModel):
    """Request to approve an unblinding request."""

    model_config = ConfigDict(from_attributes=True)

    approver: str = Field(..., description="Person approving the unblinding")


class UnblindingExecute(BaseModel):
    """Request to execute an approved unblinding."""

    model_config = ConfigDict(from_attributes=True)

    subjects_unblinded: list[str] = Field(..., description="Subject IDs to unblind")


class LockChecklistCreate(BaseModel):
    """Request to create a lock checklist."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Checklist name")
    items: list[LockChecklistItemCreate] | None = Field(None, description="Initial checklist items")


class LockChecklistItemCreate(BaseModel):
    """Request to create a checklist item."""

    model_config = ConfigDict(from_attributes=True)

    item_description: str = Field(..., description="Description of the checklist item")
    responsible: str = Field(..., description="Person responsible")


class LockChecklistItemUpdate(BaseModel):
    """Request to update a checklist item."""

    model_config = ConfigDict(from_attributes=True)

    status: ChecklistItemStatus | None = Field(None, description="Item status")
    responsible: str | None = Field(None, description="Responsible person")
    completion_date: datetime | None = Field(None, description="Completion date")


class LockExecute(BaseModel):
    """Request to execute a lock (soft or hard)."""

    model_config = ConfigDict(from_attributes=True)

    locked_by: str = Field(..., description="Person executing the lock")
    subjects_locked: int = Field(default=0, ge=0, description="Number of subjects locked")
    forms_locked: int = Field(default=0, ge=0, description="Number of forms locked")


class LockUnlock(BaseModel):
    """Request to unlock a previously locked database."""

    model_config = ConfigDict(from_attributes=True)

    unlocked_by: str = Field(..., description="Person unlocking the database")
    unlock_reason: str = Field(..., description="Reason for unlocking")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class DataLockListResponse(BaseModel):
    """List of database locks."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DataLock] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DataCutListResponse(BaseModel):
    """List of data cuts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DataCut] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CleanDataRecordListResponse(BaseModel):
    """List of clean data records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CleanDataRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class UnblindingRequestListResponse(BaseModel):
    """List of unblinding requests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UnblindingRequest] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class LockChecklistListResponse(BaseModel):
    """List of lock checklists."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LockChecklist] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class DataLockMetrics(BaseModel):
    """Aggregated data lock metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_locks: int = Field(ge=0, description="Total locks across all trials")
    locks_by_status: dict[str, int] = Field(
        default_factory=dict, description="Lock counts by status"
    )
    locks_by_type: dict[str, int] = Field(
        default_factory=dict, description="Lock counts by type"
    )
    avg_lock_duration_days: float = Field(
        ge=0.0, description="Average duration from planned to executed (days)"
    )
    total_data_cuts: int = Field(ge=0, description="Total data cuts")
    total_clean_records: int = Field(ge=0, description="Total clean data records")
    clean_data_pct: float = Field(
        ge=0.0, le=100.0, description="Overall clean data percentage"
    )
    total_unblinding_requests: int = Field(ge=0, description="Total unblinding requests")
    pending_unblinding_requests: int = Field(ge=0, description="Pending unblinding requests")


# Fix forward reference for LockChecklistCreate
LockChecklistCreate.model_rebuild()
