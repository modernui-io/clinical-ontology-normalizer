"""Pydantic schemas for Inventory Reconciliation (INV-REC).

Manages investigational product inventory operations: site inventory snapshots,
reconciliation audits, discrepancy records, lot accountability logs, and
inventory reconciliation metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InventoryStatus(str, Enum):
    RECONCILED = "reconciled"
    PENDING_RECONCILIATION = "pending_reconciliation"
    DISCREPANCY_FOUND = "discrepancy_found"
    UNDER_INVESTIGATION = "under_investigation"
    QUARANTINED = "quarantined"
    CLOSED = "closed"


class AuditOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL_PASS = "conditional_pass"
    REQUIRES_FOLLOW_UP = "requires_follow_up"
    INCOMPLETE = "incomplete"
    NOT_APPLICABLE = "not_applicable"


class DiscrepancyType(str, Enum):
    QUANTITY_MISMATCH = "quantity_mismatch"
    LOT_NUMBER_ERROR = "lot_number_error"
    EXPIRY_ISSUE = "expiry_issue"
    DOCUMENTATION_GAP = "documentation_gap"
    TEMPERATURE_EXCURSION = "temperature_excursion"
    MISSING_UNITS = "missing_units"


class DiscrepancySeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATIONAL = "informational"
    OBSERVATION = "observation"


class AccountabilityAction(str, Enum):
    RECEIVED = "received"
    DISPENSED = "dispensed"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    TRANSFERRED = "transferred"
    QUARANTINED = "quarantined"


# --- Main entities ---

class SiteInventorySnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    site_name: str
    snapshot_date: datetime
    inventory_status: InventoryStatus = InventoryStatus.PENDING_RECONCILIATION
    product_name: str
    lot_number: str
    total_received: int = Field(ge=0, default=0)
    total_dispensed: int = Field(ge=0, default=0)
    total_returned: int = Field(ge=0, default=0)
    total_destroyed: int = Field(ge=0, default=0)
    current_on_hand: int = Field(ge=0, default=0)
    expected_on_hand: int = Field(ge=0, default=0)
    expiry_date: datetime | None = None
    storage_condition: str | None = None
    recorded_by: str
    notes: str | None = None
    created_at: datetime


class ReconciliationAudit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    snapshot_id: str
    audit_date: datetime
    audit_outcome: AuditOutcome = AuditOutcome.INCOMPLETE
    auditor_name: str
    auditor_role: str
    units_counted: int = Field(ge=0, default=0)
    units_expected: int = Field(ge=0, default=0)
    variance: int = 0
    documentation_complete: bool = False
    temperature_logs_verified: bool = False
    follow_up_required: bool = False
    follow_up_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class DiscrepancyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    snapshot_id: str | None = None
    audit_id: str | None = None
    discrepancy_type: DiscrepancyType
    discrepancy_severity: DiscrepancySeverity = DiscrepancySeverity.MINOR
    description: str
    quantity_affected: int = Field(ge=0, default=0)
    lot_number: str | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    resolved: bool = False
    resolved_date: datetime | None = None
    reported_by: str
    assigned_to: str | None = None
    notes: str | None = None
    created_at: datetime


class LotAccountabilityLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    lot_number: str
    product_name: str
    accountability_action: AccountabilityAction
    action_date: datetime
    quantity: int = Field(ge=0, default=0)
    subject_id: str | None = None
    dispensing_record_id: str | None = None
    performed_by: str
    witnessed_by: str | None = None
    documentation_reference: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class SiteInventorySnapshotCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    site_name: str
    product_name: str
    lot_number: str
    snapshot_date: datetime
    recorded_by: str
    total_received: int = Field(ge=0, default=0)


class SiteInventorySnapshotUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    inventory_status: InventoryStatus | None = None
    total_dispensed: int | None = None
    total_returned: int | None = None
    total_destroyed: int | None = None
    current_on_hand: int | None = None
    notes: str | None = None


class ReconciliationAuditCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    snapshot_id: str
    audit_date: datetime
    auditor_name: str
    auditor_role: str
    units_counted: int = Field(ge=0, default=0)
    units_expected: int = Field(ge=0, default=0)


class ReconciliationAuditUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    audit_outcome: AuditOutcome | None = None
    documentation_complete: bool | None = None
    temperature_logs_verified: bool | None = None
    follow_up_required: bool | None = None
    follow_up_date: datetime | None = None
    notes: str | None = None


class DiscrepancyRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    discrepancy_type: DiscrepancyType
    description: str
    reported_by: str
    quantity_affected: int = Field(ge=0, default=0)
    discrepancy_severity: DiscrepancySeverity = DiscrepancySeverity.MINOR
    snapshot_id: str | None = None
    audit_id: str | None = None


class DiscrepancyRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    root_cause: str | None = None
    corrective_action: str | None = None
    resolved: bool | None = None
    resolved_date: datetime | None = None
    assigned_to: str | None = None
    notes: str | None = None


class LotAccountabilityLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    lot_number: str
    product_name: str
    accountability_action: AccountabilityAction
    action_date: datetime
    quantity: int = Field(ge=0, default=0)
    performed_by: str


class LotAccountabilityLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subject_id: str | None = None
    witnessed_by: str | None = None
    documentation_reference: str | None = None
    notes: str | None = None


# --- List responses ---

class SiteInventorySnapshotListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteInventorySnapshot] = Field(default_factory=list)
    total: int = Field(ge=0)


class ReconciliationAuditListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ReconciliationAudit] = Field(default_factory=list)
    total: int = Field(ge=0)


class DiscrepancyRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiscrepancyRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class LotAccountabilityLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LotAccountabilityLog] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class InventoryReconciliationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_snapshots: int = Field(ge=0)
    snapshots_by_status: dict[str, int] = Field(default_factory=dict)
    reconciliation_rate: float = Field(ge=0)
    total_audits: int = Field(ge=0)
    audits_by_outcome: dict[str, int] = Field(default_factory=dict)
    audit_pass_rate: float = Field(ge=0)
    total_discrepancies: int = Field(ge=0)
    discrepancies_by_type: dict[str, int] = Field(default_factory=dict)
    discrepancies_by_severity: dict[str, int] = Field(default_factory=dict)
    discrepancy_resolution_rate: float = Field(ge=0)
    total_accountability_logs: int = Field(ge=0)
    logs_by_action: dict[str, int] = Field(default_factory=dict)
