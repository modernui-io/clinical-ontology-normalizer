"""Pydantic schemas for Delegation Log (DELEG-LOG).

Manages delegation of authority operations: delegation entries, authority
records, training verifications, delegation audits, and delegation metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DelegationCategory(str, Enum):
    INFORMED_CONSENT = "informed_consent"
    DISPENSING_IP = "dispensing_ip"
    ADVERSE_EVENT_REPORTING = "adverse_event_reporting"
    LAB_ASSESSMENTS = "lab_assessments"
    DATA_ENTRY = "data_entry"
    PHYSICAL_EXAMINATION = "physical_examination"


class DelegationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"
    SUPERSEDED = "superseded"


class AuthorityLevel(str, Enum):
    PRINCIPAL_INVESTIGATOR = "principal_investigator"
    SUB_INVESTIGATOR = "sub_investigator"
    STUDY_COORDINATOR = "study_coordinator"
    PHARMACIST = "pharmacist"
    NURSE = "nurse"
    LAB_TECHNICIAN = "lab_technician"


class TrainingStatus(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    EXPIRED = "expired"
    WAIVED = "waived"
    OVERDUE = "overdue"


class AuditResult(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"
    REMEDIATION_NEEDED = "remediation_needed"


# --- Main entities ---

class DelegationEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    delegator_name: str
    delegate_name: str
    delegation_category: DelegationCategory
    delegation_status: DelegationStatus = DelegationStatus.ACTIVE
    authority_level: AuthorityLevel
    effective_date: datetime
    expiry_date: datetime | None = None
    specific_tasks: list[str] = Field(default_factory=list)
    restrictions: str | None = None
    approved_by: str
    notes: str | None = None
    created_at: datetime


class AuthorityRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    person_name: str
    authority_level: AuthorityLevel
    license_number: str | None = None
    credential_type: str
    credential_expiry: datetime | None = None
    is_qualified: bool = True
    qualifications: list[str] = Field(default_factory=list)
    supervision_required: bool = False
    supervisor_name: str | None = None
    verified_by: str
    verified_date: datetime
    notes: str | None = None
    created_at: datetime


class TrainingVerification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    trainee_name: str
    training_topic: str
    training_status: TrainingStatus = TrainingStatus.NOT_STARTED
    training_date: datetime | None = None
    completion_date: datetime | None = None
    expiry_date: datetime | None = None
    trainer_name: str | None = None
    certificate_number: str | None = None
    score_pct: float | None = None
    is_gcp_training: bool = False
    notes: str | None = None
    created_at: datetime


class DelegationAudit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    audit_date: datetime
    auditor_name: str
    audit_result: AuditResult = AuditResult.NOT_ASSESSED
    entries_reviewed: int = Field(ge=0, default=0)
    entries_compliant: int = Field(ge=0, default=0)
    findings_count: int = Field(ge=0, default=0)
    critical_findings: int = Field(ge=0, default=0)
    corrective_actions_required: int = Field(ge=0, default=0)
    corrective_actions_completed: int = Field(ge=0, default=0)
    next_audit_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class DelegationEntryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    delegator_name: str
    delegate_name: str
    delegation_category: DelegationCategory
    authority_level: AuthorityLevel
    effective_date: datetime
    approved_by: str
    specific_tasks: list[str] = Field(default_factory=list)


class DelegationEntryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    delegation_status: DelegationStatus | None = None
    expiry_date: datetime | None = None
    restrictions: str | None = None
    notes: str | None = None


class AuthorityRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    person_name: str
    authority_level: AuthorityLevel
    credential_type: str
    verified_by: str
    verified_date: datetime
    qualifications: list[str] = Field(default_factory=list)


class AuthorityRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_qualified: bool | None = None
    credential_expiry: datetime | None = None
    supervision_required: bool | None = None
    supervisor_name: str | None = None
    notes: str | None = None


class TrainingVerificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    trainee_name: str
    training_topic: str
    trainer_name: str | None = None
    is_gcp_training: bool = False


class TrainingVerificationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    training_status: TrainingStatus | None = None
    completion_date: datetime | None = None
    expiry_date: datetime | None = None
    certificate_number: str | None = None
    score_pct: float | None = None
    notes: str | None = None


class DelegationAuditCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    auditor_name: str
    entries_reviewed: int = Field(ge=0, default=0)


class DelegationAuditUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    audit_result: AuditResult | None = None
    entries_compliant: int | None = None
    findings_count: int | None = None
    critical_findings: int | None = None
    corrective_actions_required: int | None = None
    corrective_actions_completed: int | None = None
    next_audit_date: datetime | None = None
    notes: str | None = None


# --- List responses ---

class DelegationEntryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DelegationEntry] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuthorityRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AuthorityRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class TrainingVerificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TrainingVerification] = Field(default_factory=list)
    total: int = Field(ge=0)


class DelegationAuditListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DelegationAudit] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class DelegationLogMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_delegations: int = Field(ge=0)
    delegations_by_category: dict[str, int] = Field(default_factory=dict)
    delegations_by_status: dict[str, int] = Field(default_factory=dict)
    active_delegation_rate: float = Field(ge=0)
    total_authority_records: int = Field(ge=0)
    qualified_personnel_count: int = Field(ge=0)
    total_training_records: int = Field(ge=0)
    training_by_status: dict[str, int] = Field(default_factory=dict)
    training_completion_rate: float = Field(ge=0)
    total_audits: int = Field(ge=0)
    audits_by_result: dict[str, int] = Field(default_factory=dict)
    compliance_rate: float = Field(ge=0)
