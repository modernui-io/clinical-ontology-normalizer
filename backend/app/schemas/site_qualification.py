"""Pydantic schemas for Site Qualification Management (SITE-QUAL).

Manages site qualification operations: capability assessments,
equipment verification, staff credentialing, infrastructure audits,
and qualification status with compliance metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCategory(str, Enum):
    THERAPEUTIC_EXPERIENCE = "therapeutic_experience"
    PATIENT_POPULATION = "patient_population"
    REGULATORY_HISTORY = "regulatory_history"
    INFRASTRUCTURE = "infrastructure"
    STAFF_CAPABILITY = "staff_capability"
    DATA_MANAGEMENT = "data_management"


class QualificationStatus(str, Enum):
    PENDING_ASSESSMENT = "pending_assessment"
    IN_ASSESSMENT = "in_assessment"
    QUALIFIED = "qualified"
    CONDITIONALLY_QUALIFIED = "conditionally_qualified"
    NOT_QUALIFIED = "not_qualified"
    SUSPENDED = "suspended"


class EquipmentStatus(str, Enum):
    OPERATIONAL = "operational"
    NEEDS_CALIBRATION = "needs_calibration"
    UNDER_MAINTENANCE = "under_maintenance"
    OUT_OF_SERVICE = "out_of_service"
    DECOMMISSIONED = "decommissioned"


class CredentialType(str, Enum):
    MEDICAL_LICENSE = "medical_license"
    GCP_CERTIFICATION = "gcp_certification"
    SPECIALTY_BOARD = "specialty_board"
    RESEARCH_TRAINING = "research_training"
    INSTITUTIONAL_APPROVAL = "institutional_approval"
    DEA_REGISTRATION = "dea_registration"


class AuditRating(str, Enum):
    EXCELLENT = "excellent"
    SATISFACTORY = "satisfactory"
    NEEDS_IMPROVEMENT = "needs_improvement"
    UNSATISFACTORY = "unsatisfactory"
    CRITICAL = "critical"


class CapabilityAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    category: AssessmentCategory
    assessment_date: datetime
    score: float = Field(ge=0, le=100, default=0.0)
    max_score: float = Field(ge=0, le=100, default=100.0)
    pass_threshold: float = Field(ge=0, le=100, default=70.0)
    passed: bool = False
    prior_trial_count: int = Field(ge=0, default=0)
    therapeutic_area_experience: bool = False
    patient_pool_estimate: int = Field(ge=0, default=0)
    competing_trials: int = Field(ge=0, default=0)
    findings: list[str] = Field(default_factory=list)
    assessor: str
    reviewer: str | None = None
    notes: str | None = None
    created_at: datetime


class EquipmentVerification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    equipment_name: str
    equipment_type: str
    serial_number: str | None = None
    manufacturer: str | None = None
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    last_calibration_date: datetime | None = None
    next_calibration_date: datetime | None = None
    calibration_certificate_on_file: bool = False
    maintenance_contract_active: bool = False
    meets_protocol_requirements: bool = True
    verified_by: str
    verification_date: datetime
    notes: str | None = None
    created_at: datetime


class StaffCredential(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    staff_name: str
    role: str
    credential_type: CredentialType
    credential_number: str | None = None
    issuing_authority: str
    issue_date: datetime
    expiry_date: datetime | None = None
    is_current: bool = True
    verified: bool = False
    verified_by: str | None = None
    verification_date: datetime | None = None
    delegation_log_entry: bool = False
    cv_on_file: bool = False
    managed_by: str
    notes: str | None = None
    created_at: datetime


class InfrastructureAudit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    audit_date: datetime
    audit_type: str = "pre_study"
    rating: AuditRating = AuditRating.SATISFACTORY
    pharmacy_adequate: bool = True
    storage_adequate: bool = True
    temperature_monitoring: bool = True
    emergency_equipment: bool = True
    source_document_storage: bool = True
    patient_privacy_adequate: bool = True
    it_infrastructure_adequate: bool = True
    findings_count: int = Field(ge=0, default=0)
    critical_findings: int = Field(ge=0, default=0)
    corrective_actions_required: int = Field(ge=0, default=0)
    corrective_actions_completed: int = Field(ge=0, default=0)
    auditor: str
    follow_up_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class QualificationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    qualification_status: QualificationStatus = QualificationStatus.PENDING_ASSESSMENT
    overall_score: float = Field(ge=0, le=100, default=0.0)
    capability_score: float = Field(ge=0, le=100, default=0.0)
    equipment_score: float = Field(ge=0, le=100, default=0.0)
    staff_score: float = Field(ge=0, le=100, default=0.0)
    infrastructure_score: float = Field(ge=0, le=100, default=0.0)
    qualification_date: datetime | None = None
    expiry_date: datetime | None = None
    conditions: list[str] = Field(default_factory=list)
    conditions_met: int = Field(ge=0, default=0)
    risk_tier: str = "medium"
    qualified_by: str | None = None
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class CapabilityAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    category: AssessmentCategory
    assessor: str
    score: float = Field(ge=0, le=100, default=0.0)
    pass_threshold: float = Field(ge=0, le=100, default=70.0)


class CapabilityAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    score: float | None = None
    passed: bool | None = None
    reviewer: str | None = None
    patient_pool_estimate: int | None = None
    notes: str | None = None


class EquipmentVerificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    equipment_name: str
    equipment_type: str
    verified_by: str
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL


class EquipmentVerificationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: EquipmentStatus | None = None
    calibration_certificate_on_file: bool | None = None
    meets_protocol_requirements: bool | None = None
    notes: str | None = None


class StaffCredentialCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    staff_name: str
    role: str
    credential_type: CredentialType
    issuing_authority: str
    managed_by: str


class StaffCredentialUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_current: bool | None = None
    verified: bool | None = None
    verified_by: str | None = None
    cv_on_file: bool | None = None
    notes: str | None = None


class InfrastructureAuditCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    auditor: str
    audit_type: str = "pre_study"
    rating: AuditRating = AuditRating.SATISFACTORY


class InfrastructureAuditUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rating: AuditRating | None = None
    critical_findings: int | None = None
    corrective_actions_completed: int | None = None
    follow_up_date: datetime | None = None
    notes: str | None = None


class QualificationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    qualified_by: str | None = None
    risk_tier: str = "medium"
    conditions: list[str] = Field(default_factory=list)


class QualificationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    qualification_status: QualificationStatus | None = None
    overall_score: float | None = None
    approved_by: str | None = None
    risk_tier: str | None = None
    notes: str | None = None


class CapabilityAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CapabilityAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class EquipmentVerificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EquipmentVerification] = Field(default_factory=list)
    total: int = Field(ge=0)


class StaffCredentialListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StaffCredential] = Field(default_factory=list)
    total: int = Field(ge=0)


class InfrastructureAuditListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InfrastructureAudit] = Field(default_factory=list)
    total: int = Field(ge=0)


class QualificationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[QualificationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteQualificationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_assessments: int = Field(ge=0)
    assessments_by_category: dict[str, int] = Field(default_factory=dict)
    avg_assessment_score: float = Field(ge=0)
    total_equipment: int = Field(ge=0)
    equipment_by_status: dict[str, int] = Field(default_factory=dict)
    total_credentials: int = Field(ge=0)
    credentials_by_type: dict[str, int] = Field(default_factory=dict)
    expired_credentials: int = Field(ge=0)
    total_audits: int = Field(ge=0)
    audits_by_rating: dict[str, int] = Field(default_factory=dict)
    total_qualifications: int = Field(ge=0)
    qualifications_by_status: dict[str, int] = Field(default_factory=dict)
    sites_qualified: int = Field(ge=0)
