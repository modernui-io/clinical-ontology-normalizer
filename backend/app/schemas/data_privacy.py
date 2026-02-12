"""Pydantic schemas for Data Privacy Management (DATA-PRIV).

Manages data privacy operations: consent records, anonymization tracking,
data subject requests (DSR), privacy impact assessments, data retention
policies, and privacy compliance metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ConsentType(str, Enum):
    BROAD = "broad"
    SPECIFIC = "specific"
    TIERED = "tiered"
    DYNAMIC = "dynamic"
    BLANKET = "blanket"


class ConsentStatus(str, Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"
    RESTRICTED = "restricted"


class AnonymizationMethod(str, Enum):
    K_ANONYMITY = "k_anonymity"
    L_DIVERSITY = "l_diversity"
    T_CLOSENESS = "t_closeness"
    DIFFERENTIAL_PRIVACY = "differential_privacy"
    PSEUDONYMIZATION = "pseudonymization"
    DATA_MASKING = "data_masking"


class DSRType(str, Enum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"
    RESTRICTION = "restriction"
    PORTABILITY = "portability"
    OBJECTION = "objection"


class DSRStatus(str, Enum):
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DENIED = "denied"
    EXTENDED = "extended"


class PIAStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REQUIRES_ACTION = "requires_action"
    APPROVED = "approved"


class ConsentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    consent_type: ConsentType
    consent_status: ConsentStatus = ConsentStatus.PENDING
    consent_date: datetime | None = None
    withdrawal_date: datetime | None = None
    consent_version: str = "1.0"
    purpose: str
    data_categories: list[str] = Field(default_factory=list)
    retention_period_months: int = Field(ge=0, default=60)
    third_party_sharing: bool = False
    guardian_consent: bool = False
    consent_method: str = "electronic"
    collected_by: str
    notes: str | None = None
    created_at: datetime


class AnonymizationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    dataset_name: str
    method: AnonymizationMethod
    anonymization_date: datetime
    records_processed: int = Field(ge=0, default=0)
    fields_anonymized: list[str] = Field(default_factory=list)
    k_value: int | None = None
    epsilon_value: float | None = None
    re_identification_risk: float = Field(ge=0, le=100, default=0.0)
    quality_score: float = Field(ge=0, le=100, default=0.0)
    validated: bool = False
    validated_by: str | None = None
    performed_by: str
    notes: str | None = None
    created_at: datetime


class DataSubjectRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    request_type: DSRType
    status: DSRStatus = DSRStatus.RECEIVED
    received_date: datetime
    acknowledged_date: datetime | None = None
    due_date: datetime | None = None
    completed_date: datetime | None = None
    request_details: str
    response_details: str | None = None
    denial_reason: str | None = None
    handled_by: str
    data_categories_affected: list[str] = Field(default_factory=list)
    systems_affected: list[str] = Field(default_factory=list)
    days_to_complete: int | None = None
    created_at: datetime


class PrivacyImpactAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    assessment_name: str
    status: PIAStatus = PIAStatus.PLANNED
    assessment_date: datetime
    data_types_assessed: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    findings_count: int = Field(ge=0, default=0)
    high_risk_findings: int = Field(ge=0, default=0)
    mitigations_required: int = Field(ge=0, default=0)
    mitigations_completed: int = Field(ge=0, default=0)
    dpo_review_required: bool = False
    dpo_approved: bool = False
    assessor: str
    reviewer: str | None = None
    notes: str | None = None
    created_at: datetime


class DataRetentionPolicy(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    policy_name: str
    data_category: str
    retention_period_months: int = Field(ge=0, default=60)
    legal_basis: str
    applicable_regulations: list[str] = Field(default_factory=list)
    destruction_method: str = "secure_deletion"
    review_date: datetime | None = None
    next_review_date: datetime | None = None
    is_active: bool = True
    records_covered: int = Field(ge=0, default=0)
    records_due_deletion: int = Field(ge=0, default=0)
    created_by: str
    approved_by: str | None = None
    created_at: datetime


class ConsentRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    consent_type: ConsentType
    purpose: str
    collected_by: str
    data_categories: list[str] = Field(default_factory=list)
    retention_period_months: int = Field(ge=0, default=60)


class ConsentRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    consent_status: ConsentStatus | None = None
    third_party_sharing: bool | None = None
    notes: str | None = None
    consent_version: str | None = None


class AnonymizationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    dataset_name: str
    method: AnonymizationMethod
    performed_by: str
    records_processed: int = Field(ge=0, default=0)
    fields_anonymized: list[str] = Field(default_factory=list)


class AnonymizationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    validated: bool | None = None
    validated_by: str | None = None
    re_identification_risk: float | None = None
    quality_score: float | None = None
    notes: str | None = None


class DataSubjectRequestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    request_type: DSRType
    request_details: str
    handled_by: str
    data_categories_affected: list[str] = Field(default_factory=list)


class DataSubjectRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DSRStatus | None = None
    response_details: str | None = None
    denial_reason: str | None = None
    handled_by: str | None = None


class PrivacyImpactAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    assessment_name: str
    assessor: str
    data_types_assessed: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class PrivacyImpactAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PIAStatus | None = None
    risk_level: str | None = None
    dpo_approved: bool | None = None
    reviewer: str | None = None
    notes: str | None = None


class DataRetentionPolicyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    policy_name: str
    data_category: str
    legal_basis: str
    created_by: str
    retention_period_months: int = Field(ge=0, default=60)


class DataRetentionPolicyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    approved_by: str | None = None
    retention_period_months: int | None = None
    records_due_deletion: int | None = None


class ConsentRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ConsentRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class AnonymizationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AnonymizationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataSubjectRequestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataSubjectRequest] = Field(default_factory=list)
    total: int = Field(ge=0)


class PrivacyImpactAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PrivacyImpactAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataRetentionPolicyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataRetentionPolicy] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataPrivacyMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_consent_records: int = Field(ge=0)
    consents_by_type: dict[str, int] = Field(default_factory=dict)
    consents_by_status: dict[str, int] = Field(default_factory=dict)
    active_consents: int = Field(ge=0)
    withdrawn_consents: int = Field(ge=0)
    total_anonymization_records: int = Field(ge=0)
    records_by_method: dict[str, int] = Field(default_factory=dict)
    avg_re_identification_risk: float = Field(ge=0)
    total_dsr: int = Field(ge=0)
    dsr_by_type: dict[str, int] = Field(default_factory=dict)
    dsr_by_status: dict[str, int] = Field(default_factory=dict)
    avg_dsr_completion_days: float = Field(ge=0)
    total_pia: int = Field(ge=0)
    pia_by_status: dict[str, int] = Field(default_factory=dict)
    total_retention_policies: int = Field(ge=0)
    active_policies: int = Field(ge=0)
    records_due_deletion: int = Field(ge=0)
