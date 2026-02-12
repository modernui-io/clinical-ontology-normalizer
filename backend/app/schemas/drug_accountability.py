"""Pydantic schemas for Drug Accountability Management (DRUG-ACCT).

Manages drug accountability operations: dispensation records, drug return
tracking, destruction records, accountability reconciliation, deviation
tracking, and drug accountability operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DispensationType(str, Enum):
    INITIAL = "initial"
    REFILL = "refill"
    REPLACEMENT = "replacement"
    EMERGENCY = "emergency"
    OPEN_LABEL = "open_label"


class DrugStatus(str, Enum):
    DISPENSED = "dispensed"
    ADMINISTERED = "administered"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    LOST = "lost"
    EXPIRED = "expired"
    QUARANTINED = "quarantined"


class ReconciliationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RECONCILED = "reconciled"
    DISCREPANCY = "discrepancy"
    ESCALATED = "escalated"
    CLOSED = "closed"


class DeviationSeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class DestructionMethod(str, Enum):
    INCINERATION = "incineration"
    CHEMICAL = "chemical"
    RETURN_TO_SPONSOR = "return_to_sponsor"
    PHARMACY_DISPOSAL = "pharmacy_disposal"
    WITNESSED_DESTRUCTION = "witnessed_destruction"


class DispensationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str
    visit_id: str | None = None
    dispensation_type: DispensationType
    drug_name: str
    batch_number: str
    kit_number: str | None = None
    quantity_dispensed: int = Field(ge=0, default=0)
    quantity_units: str = "tablets"
    dispensation_date: datetime
    dispensed_by: str
    verified_by: str | None = None
    next_dispensation_date: datetime | None = None
    storage_instructions: str | None = None
    status: DrugStatus = DrugStatus.DISPENSED
    randomization_number: str | None = None
    treatment_arm: str | None = None
    created_at: datetime


class DrugReturn(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dispensation_id: str
    trial_id: str
    site_id: str
    subject_id: str
    return_date: datetime
    quantity_returned: int = Field(ge=0, default=0)
    quantity_used: int = Field(ge=0, default=0)
    quantity_lost: int = Field(ge=0, default=0)
    condition: str = "acceptable"
    returned_to: str
    verified_by: str | None = None
    packaging_intact: bool = True
    temperature_excursion: bool = False
    notes: str | None = None
    created_at: datetime


class DestructionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    drug_name: str
    batch_numbers: list[str] = Field(default_factory=list)
    destruction_method: DestructionMethod
    destruction_date: datetime
    quantity_destroyed: int = Field(ge=0, default=0)
    quantity_units: str = "tablets"
    witness_1: str
    witness_2: str | None = None
    certificate_number: str | None = None
    destruction_facility: str | None = None
    approved_by: str
    documentation_complete: bool = False
    created_at: datetime


class AccountabilityReconciliation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    reconciliation_date: datetime
    period_start: datetime
    period_end: datetime
    total_received: int = Field(ge=0, default=0)
    total_dispensed: int = Field(ge=0, default=0)
    total_returned: int = Field(ge=0, default=0)
    total_destroyed: int = Field(ge=0, default=0)
    total_on_hand: int = Field(ge=0, default=0)
    total_lost: int = Field(ge=0, default=0)
    balance_expected: int = Field(ge=0, default=0)
    balance_actual: int = Field(ge=0, default=0)
    discrepancy: int = 0
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    performed_by: str
    verified_by: str | None = None
    notes: str | None = None
    created_at: datetime


class AccountabilityDeviation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str | None = None
    deviation_date: datetime
    description: str
    severity: DeviationSeverity = DeviationSeverity.MINOR
    root_cause: str | None = None
    quantity_affected: int = Field(ge=0, default=0)
    batch_number: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    reported_by: str
    resolved_by: str | None = None
    resolution_date: datetime | None = None
    sponsor_notified: bool = False
    irb_notified: bool = False
    created_at: datetime


class DispensationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    subject_id: str
    dispensation_type: DispensationType
    drug_name: str
    batch_number: str
    quantity_dispensed: int = Field(ge=0, default=0)
    dispensed_by: str
    kit_number: str | None = None
    visit_id: str | None = None


class DispensationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DrugStatus | None = None
    verified_by: str | None = None
    next_dispensation_date: datetime | None = None
    storage_instructions: str | None = None


class DrugReturnCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dispensation_id: str
    trial_id: str
    site_id: str
    subject_id: str
    quantity_returned: int = Field(ge=0, default=0)
    quantity_used: int = Field(ge=0, default=0)
    returned_to: str


class DrugReturnUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    verified_by: str | None = None
    packaging_intact: bool | None = None
    temperature_excursion: bool | None = None
    notes: str | None = None


class DestructionRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    drug_name: str
    destruction_method: DestructionMethod
    quantity_destroyed: int = Field(ge=0, default=0)
    witness_1: str
    approved_by: str
    batch_numbers: list[str] = Field(default_factory=list)


class DestructionRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    witness_2: str | None = None
    certificate_number: str | None = None
    documentation_complete: bool | None = None


class AccountabilityReconciliationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    period_start: datetime
    period_end: datetime
    performed_by: str
    total_received: int = Field(ge=0, default=0)


class AccountabilityReconciliationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ReconciliationStatus | None = None
    verified_by: str | None = None
    total_on_hand: int | None = None
    notes: str | None = None


class AccountabilityDeviationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    description: str
    severity: DeviationSeverity
    reported_by: str
    subject_id: str | None = None
    batch_number: str | None = None


class AccountabilityDeviationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    root_cause: str | None = None
    corrective_action: str | None = None
    resolved_by: str | None = None
    sponsor_notified: bool | None = None


class DispensationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DispensationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class DrugReturnListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DrugReturn] = Field(default_factory=list)
    total: int = Field(ge=0)


class DestructionRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DestructionRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class AccountabilityReconciliationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AccountabilityReconciliation] = Field(default_factory=list)
    total: int = Field(ge=0)


class AccountabilityDeviationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AccountabilityDeviation] = Field(default_factory=list)
    total: int = Field(ge=0)


class DrugAccountabilityMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_dispensations: int = Field(ge=0)
    dispensations_by_type: dict[str, int] = Field(default_factory=dict)
    dispensations_by_status: dict[str, int] = Field(default_factory=dict)
    total_returns: int = Field(ge=0)
    total_quantity_dispensed: int = Field(ge=0)
    total_quantity_returned: int = Field(ge=0)
    total_quantity_destroyed: int = Field(ge=0)
    total_reconciliations: int = Field(ge=0)
    reconciliations_with_discrepancy: int = Field(ge=0)
    total_deviations: int = Field(ge=0)
    deviations_by_severity: dict[str, int] = Field(default_factory=dict)
    open_deviations: int = Field(ge=0)
    destruction_records: int = Field(ge=0)
