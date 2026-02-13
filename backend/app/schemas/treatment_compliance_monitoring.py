"""Pydantic schemas for Treatment Compliance Monitoring (TCM-MON).

Manages treatment compliance monitoring operations: dosing records, compliance
assessments, medication accountability logs, and treatment interruption events
with metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DosingStatus(str, Enum):
    ADMINISTERED = "administered"
    MISSED = "missed"
    DELAYED = "delayed"
    PARTIAL = "partial"
    REFUSED = "refused"
    HELD = "held"


class ComplianceLevel(str, Enum):
    FULLY_COMPLIANT = "fully_compliant"
    MOSTLY_COMPLIANT = "mostly_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"
    UNABLE_TO_ASSESS = "unable_to_assess"


class AccountabilityAction(str, Enum):
    DISPENSED = "dispensed"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    LOST = "lost"
    TRANSFERRED = "transferred"
    QUARANTINED = "quarantined"


class InterruptionReason(str, Enum):
    ADVERSE_EVENT = "adverse_event"
    PROTOCOL_DEVIATION = "protocol_deviation"
    PATIENT_REQUEST = "patient_request"
    INVESTIGATOR_DECISION = "investigator_decision"
    SUPPLY_ISSUE = "supply_issue"
    ADMINISTRATIVE = "administrative"


class InterruptionStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    PERMANENT = "permanent"
    UNDER_REVIEW = "under_review"
    DOSE_MODIFIED = "dose_modified"
    TREATMENT_DISCONTINUED = "treatment_discontinued"


# --- Main entities ---

class DosingRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    dosing_status: DosingStatus = DosingStatus.ADMINISTERED
    study_drug_name: str
    dose_amount: float = Field(ge=0, default=0.0)
    dose_unit: str
    route_of_administration: str
    scheduled_date: datetime
    actual_date: datetime | None = None
    visit_number: int = Field(ge=0, default=1)
    cycle_number: int = Field(ge=0, default=1)
    lot_number: str | None = None
    administered_by: str | None = None
    witnessed_by: str | None = None
    reason_not_given: str | None = None
    notes: str | None = None
    created_at: datetime


class ComplianceAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    compliance_level: ComplianceLevel = ComplianceLevel.NOT_ASSESSED
    assessment_date: datetime
    assessment_period_start: datetime
    assessment_period_end: datetime
    doses_scheduled: int = Field(ge=0, default=0)
    doses_taken: int = Field(ge=0, default=0)
    doses_missed: int = Field(ge=0, default=0)
    compliance_percentage: float = Field(ge=0, le=100, default=0.0)
    assessment_method: str
    pill_count_performed: bool = False
    diary_reviewed: bool = False
    assessed_by: str
    intervention_recommended: bool = False
    intervention_description: str | None = None
    notes: str | None = None
    created_at: datetime


class MedicationAccountabilityLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    accountability_action: AccountabilityAction = AccountabilityAction.DISPENSED
    study_drug_name: str
    lot_number: str
    quantity_units: int = Field(ge=0, default=0)
    quantity_dispensed: int = Field(ge=0, default=0)
    quantity_returned: int = Field(ge=0, default=0)
    quantity_consumed: int = Field(ge=0, default=0)
    quantity_lost: int = Field(ge=0, default=0)
    action_date: datetime
    performed_by: str
    verified_by: str | None = None
    storage_conditions_met: bool = True
    temperature_excursion: bool = False
    notes: str | None = None
    created_at: datetime


class TreatmentInterruptionEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    interruption_reason: InterruptionReason
    interruption_status: InterruptionStatus = InterruptionStatus.ACTIVE
    study_drug_name: str
    interruption_date: datetime
    expected_duration_days: int = Field(ge=0, default=0)
    actual_duration_days: int = Field(ge=0, default=0)
    dose_modification: str | None = None
    resumption_date: datetime | None = None
    resumed_at_same_dose: bool | None = None
    new_dose_amount: float | None = None
    reported_by: str
    approved_by: str | None = None
    irb_notification_required: bool = False
    sponsor_notified: bool = False
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class DosingRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    study_drug_name: str
    dose_amount: float = Field(ge=0, default=0.0)
    dose_unit: str
    route_of_administration: str
    scheduled_date: datetime
    dosing_status: DosingStatus = DosingStatus.ADMINISTERED


class DosingRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dosing_status: DosingStatus | None = None
    actual_date: datetime | None = None
    administered_by: str | None = None
    witnessed_by: str | None = None
    reason_not_given: str | None = None
    lot_number: str | None = None
    notes: str | None = None


class ComplianceAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    assessment_date: datetime
    assessment_period_start: datetime
    assessment_period_end: datetime
    assessment_method: str
    assessed_by: str
    compliance_level: ComplianceLevel = ComplianceLevel.NOT_ASSESSED


class ComplianceAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compliance_level: ComplianceLevel | None = None
    doses_scheduled: int | None = None
    doses_taken: int | None = None
    compliance_percentage: float | None = None
    intervention_recommended: bool | None = None
    intervention_description: str | None = None
    notes: str | None = None


class MedicationAccountabilityLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    study_drug_name: str
    lot_number: str
    action_date: datetime
    performed_by: str
    accountability_action: AccountabilityAction = AccountabilityAction.DISPENSED
    quantity_units: int = Field(ge=0, default=0)


class MedicationAccountabilityLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    accountability_action: AccountabilityAction | None = None
    quantity_returned: int | None = None
    quantity_consumed: int | None = None
    verified_by: str | None = None
    temperature_excursion: bool | None = None
    notes: str | None = None


class TreatmentInterruptionEventCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    interruption_reason: InterruptionReason
    study_drug_name: str
    interruption_date: datetime
    reported_by: str
    interruption_status: InterruptionStatus = InterruptionStatus.ACTIVE


class TreatmentInterruptionEventUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    interruption_status: InterruptionStatus | None = None
    actual_duration_days: int | None = None
    resumption_date: datetime | None = None
    resumed_at_same_dose: bool | None = None
    new_dose_amount: float | None = None
    approved_by: str | None = None
    sponsor_notified: bool | None = None
    notes: str | None = None


# --- List responses ---

class DosingRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DosingRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class ComplianceAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplianceAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class MedicationAccountabilityLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MedicationAccountabilityLog] = Field(default_factory=list)
    total: int = Field(ge=0)


class TreatmentInterruptionEventListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TreatmentInterruptionEvent] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class TreatmentComplianceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_dosing_records: int = Field(ge=0)
    records_by_status: dict[str, int] = Field(default_factory=dict)
    total_compliance_assessments: int = Field(ge=0)
    assessments_by_level: dict[str, int] = Field(default_factory=dict)
    avg_compliance_percentage: float = Field(ge=0)
    total_accountability_logs: int = Field(ge=0)
    logs_by_action: dict[str, int] = Field(default_factory=dict)
    total_interruptions: int = Field(ge=0)
    interruptions_by_reason: dict[str, int] = Field(default_factory=dict)
    interruptions_by_status: dict[str, int] = Field(default_factory=dict)
    avg_interruption_duration_days: float = Field(ge=0)
