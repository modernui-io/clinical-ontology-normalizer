"""Pydantic schemas for Adverse Event Reconciliation (AER-REC).

Manages adverse event reconciliation operations: reconciliation tasks,
discrepancy records, line-item comparisons, and reconciliation sign-offs
with metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISCREPANCIES_FOUND = "discrepancies_found"
    ESCALATED = "escalated"
    CLOSED = "closed"


class DiscrepancyType(str, Enum):
    MISSING_IN_SAFETY_DB = "missing_in_safety_db"
    MISSING_IN_CLINICAL_DB = "missing_in_clinical_db"
    DATE_MISMATCH = "date_mismatch"
    SEVERITY_MISMATCH = "severity_mismatch"
    CAUSALITY_MISMATCH = "causality_mismatch"
    CODING_MISMATCH = "coding_mismatch"


class DiscrepancySeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    ADMINISTRATIVE = "administrative"
    INFORMATIONAL = "informational"
    NOT_APPLICABLE = "not_applicable"


class ComparisonOutcome(str, Enum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    PARTIAL_MATCH = "partial_match"
    NOT_FOUND = "not_found"
    PENDING_REVIEW = "pending_review"
    EXCLUDED = "excluded"


class SignOffStatus(str, Enum):
    PENDING = "pending"
    SIGNED_OFF = "signed_off"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"
    DEFERRED = "deferred"
    REVOKED = "revoked"


# --- Main entities ---

class ReconciliationTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.SCHEDULED
    reconciliation_period_start: datetime
    reconciliation_period_end: datetime
    safety_db_name: str
    clinical_db_name: str
    total_safety_records: int = Field(ge=0, default=0)
    total_clinical_records: int = Field(ge=0, default=0)
    matched_records: int = Field(ge=0, default=0)
    unmatched_records: int = Field(ge=0, default=0)
    assigned_to: str
    started_date: datetime | None = None
    completed_date: datetime | None = None
    target_completion_date: datetime
    notes: str | None = None
    created_at: datetime


class DiscrepancyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reconciliation_task_id: str
    discrepancy_type: DiscrepancyType
    discrepancy_severity: DiscrepancySeverity = DiscrepancySeverity.MINOR
    subject_id: str
    ae_identifier: str
    safety_db_value: str | None = None
    clinical_db_value: str | None = None
    field_name: str
    description: str
    root_cause: str | None = None
    corrective_action: str | None = None
    resolved: bool = False
    resolved_date: datetime | None = None
    resolved_by: str | None = None
    identified_by: str
    identified_date: datetime
    notes: str | None = None
    created_at: datetime


class LineItemComparison(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reconciliation_task_id: str
    comparison_outcome: ComparisonOutcome = ComparisonOutcome.PENDING_REVIEW
    subject_id: str
    ae_identifier: str
    safety_db_record_id: str | None = None
    clinical_db_record_id: str | None = None
    ae_term_safety: str | None = None
    ae_term_clinical: str | None = None
    onset_date_safety: datetime | None = None
    onset_date_clinical: datetime | None = None
    severity_safety: str | None = None
    severity_clinical: str | None = None
    compared_by: str
    comparison_date: datetime
    discrepancy_count: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


class ReconciliationSignOff(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reconciliation_task_id: str
    sign_off_status: SignOffStatus = SignOffStatus.PENDING
    sign_off_role: str
    signer_name: str
    sign_off_date: datetime | None = None
    open_discrepancies_at_signoff: int = Field(ge=0, default=0)
    resolved_discrepancies: int = Field(ge=0, default=0)
    waived_discrepancies: int = Field(ge=0, default=0)
    conditions: str | None = None
    rejection_reason: str | None = None
    next_review_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class ReconciliationTaskCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reconciliation_period_start: datetime
    reconciliation_period_end: datetime
    safety_db_name: str
    clinical_db_name: str
    assigned_to: str
    target_completion_date: datetime
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.SCHEDULED


class ReconciliationTaskUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reconciliation_status: ReconciliationStatus | None = None
    total_safety_records: int | None = None
    total_clinical_records: int | None = None
    matched_records: int | None = None
    completed_date: datetime | None = None
    notes: str | None = None


class DiscrepancyRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reconciliation_task_id: str
    discrepancy_type: DiscrepancyType
    subject_id: str
    ae_identifier: str
    field_name: str
    description: str
    identified_by: str
    identified_date: datetime
    discrepancy_severity: DiscrepancySeverity = DiscrepancySeverity.MINOR


class DiscrepancyRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    discrepancy_severity: DiscrepancySeverity | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    resolved: bool | None = None
    resolved_date: datetime | None = None
    resolved_by: str | None = None
    notes: str | None = None


class LineItemComparisonCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reconciliation_task_id: str
    subject_id: str
    ae_identifier: str
    compared_by: str
    comparison_date: datetime
    comparison_outcome: ComparisonOutcome = ComparisonOutcome.PENDING_REVIEW


class LineItemComparisonUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comparison_outcome: ComparisonOutcome | None = None
    ae_term_safety: str | None = None
    ae_term_clinical: str | None = None
    severity_safety: str | None = None
    severity_clinical: str | None = None
    discrepancy_count: int | None = None
    notes: str | None = None


class ReconciliationSignOffCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reconciliation_task_id: str
    sign_off_role: str
    signer_name: str
    sign_off_status: SignOffStatus = SignOffStatus.PENDING


class ReconciliationSignOffUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sign_off_status: SignOffStatus | None = None
    sign_off_date: datetime | None = None
    conditions: str | None = None
    rejection_reason: str | None = None
    next_review_date: datetime | None = None
    notes: str | None = None


# --- List responses ---

class ReconciliationTaskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ReconciliationTask] = Field(default_factory=list)
    total: int = Field(ge=0)


class DiscrepancyRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiscrepancyRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class LineItemComparisonListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LineItemComparison] = Field(default_factory=list)
    total: int = Field(ge=0)


class ReconciliationSignOffListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ReconciliationSignOff] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class AdverseEventReconciliationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_reconciliation_tasks: int = Field(ge=0)
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    total_discrepancies: int = Field(ge=0)
    discrepancies_by_type: dict[str, int] = Field(default_factory=dict)
    discrepancies_by_severity: dict[str, int] = Field(default_factory=dict)
    discrepancy_resolution_rate: float = Field(ge=0)
    total_comparisons: int = Field(ge=0)
    comparisons_by_outcome: dict[str, int] = Field(default_factory=dict)
    match_rate: float = Field(ge=0)
    total_sign_offs: int = Field(ge=0)
    sign_offs_by_status: dict[str, int] = Field(default_factory=dict)
