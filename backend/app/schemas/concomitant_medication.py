"""Pydantic schemas for Concomitant Medication Tracking (CMT-TRK).

Manages concomitant medication operations: medication records, drug interaction
checks, prohibited medication alerts, medication reconciliation tasks, and
concomitant medication metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MedicationStatus(str, Enum):
    ONGOING = "ongoing"
    COMPLETED = "completed"
    DISCONTINUED = "discontinued"
    ON_HOLD = "on_hold"
    PRN = "prn"
    NOT_STARTED = "not_started"


class InteractionSeverity(str, Enum):
    CONTRAINDICATED = "contraindicated"
    SEVERE = "severe"
    MODERATE = "moderate"
    MILD = "mild"
    NONE_KNOWN = "none_known"
    UNKNOWN = "unknown"


class AlertPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    OVERRIDDEN = "overridden"
    EXPIRED = "expired"
    DISMISSED = "dismissed"


class ReconciliationOutcome(str, Enum):
    RECONCILED = "reconciled"
    DISCREPANCY_FOUND = "discrepancy_found"
    PENDING = "pending"
    ESCALATED = "escalated"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"


# --- Main entities ---

class MedicationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    medication_name: str
    generic_name: str | None = None
    rxnorm_code: str | None = None
    atc_code: str | None = None
    medication_status: MedicationStatus = MedicationStatus.ONGOING
    indication: str
    dose: str
    dose_unit: str
    frequency: str
    route: str
    start_date: datetime
    end_date: datetime | None = None
    prescriber_name: str | None = None
    recorded_by: str
    notes: str | None = None
    created_at: datetime


class DrugInteractionCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    medication_record_id: str
    study_drug_name: str
    interaction_severity: InteractionSeverity = InteractionSeverity.UNKNOWN
    interaction_description: str
    clinical_significance: str | None = None
    recommendation: str | None = None
    checked_date: datetime
    checked_by: str
    source_database: str | None = None
    override_approved: bool = False
    override_by: str | None = None
    override_rationale: str | None = None
    notes: str | None = None
    created_at: datetime


class ProhibitedMedicationAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    medication_record_id: str | None = None
    alert_priority: AlertPriority = AlertPriority.MEDIUM
    alert_status: AlertStatus = AlertStatus.ACTIVE
    medication_name: str
    prohibition_reason: str
    protocol_section: str | None = None
    detected_date: datetime
    acknowledged_by: str | None = None
    acknowledged_date: datetime | None = None
    resolution_action: str | None = None
    resolution_date: datetime | None = None
    deviation_filed: bool = False
    notes: str | None = None
    created_at: datetime


class MedicationReconciliation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    reconciliation_outcome: ReconciliationOutcome = ReconciliationOutcome.PENDING
    visit_number: int = Field(ge=0, default=1)
    reconciliation_date: datetime
    medications_reviewed: int = Field(ge=0, default=0)
    discrepancies_found: int = Field(ge=0, default=0)
    new_medications_added: int = Field(ge=0, default=0)
    medications_discontinued: int = Field(ge=0, default=0)
    performed_by: str
    verified_by: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class MedicationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    medication_name: str
    indication: str
    dose: str
    dose_unit: str
    frequency: str
    route: str
    start_date: datetime
    recorded_by: str


class MedicationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    medication_status: MedicationStatus | None = None
    end_date: datetime | None = None
    generic_name: str | None = None
    rxnorm_code: str | None = None
    notes: str | None = None


class DrugInteractionCheckCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    medication_record_id: str
    study_drug_name: str
    interaction_description: str
    checked_date: datetime
    checked_by: str
    interaction_severity: InteractionSeverity = InteractionSeverity.UNKNOWN


class DrugInteractionCheckUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    clinical_significance: str | None = None
    recommendation: str | None = None
    override_approved: bool | None = None
    override_by: str | None = None
    override_rationale: str | None = None
    notes: str | None = None


class ProhibitedMedicationAlertCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    medication_name: str
    prohibition_reason: str
    detected_date: datetime
    alert_priority: AlertPriority = AlertPriority.MEDIUM
    medication_record_id: str | None = None


class ProhibitedMedicationAlertUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    alert_status: AlertStatus | None = None
    acknowledged_by: str | None = None
    acknowledged_date: datetime | None = None
    resolution_action: str | None = None
    resolution_date: datetime | None = None
    deviation_filed: bool | None = None
    notes: str | None = None


class MedicationReconciliationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    reconciliation_date: datetime
    performed_by: str
    visit_number: int = Field(ge=0, default=1)


class MedicationReconciliationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reconciliation_outcome: ReconciliationOutcome | None = None
    medications_reviewed: int | None = None
    discrepancies_found: int | None = None
    new_medications_added: int | None = None
    verified_by: str | None = None
    notes: str | None = None


# --- List responses ---

class MedicationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MedicationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class DrugInteractionCheckListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DrugInteractionCheck] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProhibitedMedicationAlertListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProhibitedMedicationAlert] = Field(default_factory=list)
    total: int = Field(ge=0)


class MedicationReconciliationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MedicationReconciliation] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class ConcomitantMedicationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_medication_records: int = Field(ge=0)
    records_by_status: dict[str, int] = Field(default_factory=dict)
    total_interaction_checks: int = Field(ge=0)
    interactions_by_severity: dict[str, int] = Field(default_factory=dict)
    override_rate: float = Field(ge=0)
    total_prohibited_alerts: int = Field(ge=0)
    alerts_by_priority: dict[str, int] = Field(default_factory=dict)
    alerts_by_status: dict[str, int] = Field(default_factory=dict)
    total_reconciliations: int = Field(ge=0)
    reconciliations_by_outcome: dict[str, int] = Field(default_factory=dict)
    reconciliation_rate: float = Field(ge=0)
