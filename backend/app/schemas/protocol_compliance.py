"""Pydantic schemas for Protocol Compliance Management (PROT-COMP).

Manages protocol compliance operations: GCP compliance monitoring,
protocol adherence tracking, compliance audit findings, training
compliance records, corrective action tracking, and compliance metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ComplianceArea(str, Enum):
    GCP = "gcp"
    INFORMED_CONSENT = "informed_consent"
    DATA_INTEGRITY = "data_integrity"
    SAFETY_REPORTING = "safety_reporting"
    DRUG_MANAGEMENT = "drug_management"
    SOURCE_DOCUMENTATION = "source_documentation"
    PROTOCOL_PROCEDURES = "protocol_procedures"
    REGULATORY = "regulatory"


class ComplianceRating(str, Enum):
    FULLY_COMPLIANT = "fully_compliant"
    SUBSTANTIALLY_COMPLIANT = "substantially_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"


class FindingStatus(str, Enum):
    OPEN = "open"
    IN_REMEDIATION = "in_remediation"
    REMEDIATED = "remediated"
    VERIFIED = "verified"
    CLOSED = "closed"


class TrainingStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    WAIVED = "waived"


class ComplianceAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    compliance_area: ComplianceArea
    assessment_date: datetime
    rating: ComplianceRating = ComplianceRating.NOT_ASSESSED
    score: float = Field(ge=0, le=100, default=0.0)
    findings_count: int = Field(ge=0, default=0)
    critical_findings: int = Field(ge=0, default=0)
    assessor: str
    methodology: str | None = None
    next_assessment_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class ComplianceFinding(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    assessment_id: str | None = None
    compliance_area: ComplianceArea
    finding_description: str
    severity: FindingSeverity
    status: FindingStatus = FindingStatus.OPEN
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    responsible_person: str
    due_date: datetime | None = None
    remediation_date: datetime | None = None
    verified_by: str | None = None
    verification_date: datetime | None = None
    days_open: int = Field(ge=0, default=0)
    created_at: datetime


class TrainingCompliance(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    trainee_name: str
    trainee_role: str
    training_topic: str
    training_type: str = "initial"
    status: TrainingStatus = TrainingStatus.NOT_STARTED
    required_date: datetime | None = None
    completion_date: datetime | None = None
    expiry_date: datetime | None = None
    score: float | None = None
    passing_score: float = Field(ge=0, le=100, default=80.0)
    certificate_id: str | None = None
    trainer: str | None = None
    notes: str | None = None
    created_at: datetime


class ProtocolAdherence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str | None = None
    procedure_name: str
    visit_name: str | None = None
    expected_date: datetime | None = None
    actual_date: datetime | None = None
    is_compliant: bool = True
    deviation_type: str | None = None
    deviation_description: str | None = None
    impact_assessment: str | None = None
    reported_by: str
    reviewed_by: str | None = None
    created_at: datetime


class CorrectiveAction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    finding_id: str | None = None
    action_description: str
    action_type: str = "corrective"
    assigned_to: str
    status: FindingStatus = FindingStatus.OPEN
    priority: FindingSeverity = FindingSeverity.MINOR
    due_date: datetime | None = None
    completion_date: datetime | None = None
    effectiveness_check_date: datetime | None = None
    is_effective: bool | None = None
    verified_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ComplianceAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    compliance_area: ComplianceArea
    assessor: str
    score: float = Field(ge=0, le=100, default=0.0)
    rating: ComplianceRating = ComplianceRating.NOT_ASSESSED


class ComplianceAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rating: ComplianceRating | None = None
    score: float | None = None
    notes: str | None = None
    next_assessment_date: datetime | None = None


class ComplianceFindingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    compliance_area: ComplianceArea
    finding_description: str
    severity: FindingSeverity
    responsible_person: str
    assessment_id: str | None = None
    due_date: datetime | None = None


class ComplianceFindingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: FindingStatus | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    verified_by: str | None = None


class TrainingComplianceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    trainee_name: str
    trainee_role: str
    training_topic: str
    required_date: datetime | None = None


class TrainingComplianceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: TrainingStatus | None = None
    score: float | None = None
    certificate_id: str | None = None
    trainer: str | None = None
    notes: str | None = None


class ProtocolAdherenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    procedure_name: str
    reported_by: str
    subject_id: str | None = None
    visit_name: str | None = None
    is_compliant: bool = True


class ProtocolAdherenceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_compliant: bool | None = None
    deviation_type: str | None = None
    deviation_description: str | None = None
    reviewed_by: str | None = None


class CorrectiveActionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    action_description: str
    assigned_to: str
    finding_id: str | None = None
    priority: FindingSeverity = FindingSeverity.MINOR
    due_date: datetime | None = None


class CorrectiveActionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: FindingStatus | None = None
    is_effective: bool | None = None
    verified_by: str | None = None
    notes: str | None = None


class ComplianceAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplianceAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class ComplianceFindingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplianceFinding] = Field(default_factory=list)
    total: int = Field(ge=0)


class TrainingComplianceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TrainingCompliance] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProtocolAdherenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProtocolAdherence] = Field(default_factory=list)
    total: int = Field(ge=0)


class CorrectiveActionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CorrectiveAction] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProtocolComplianceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_assessments: int = Field(ge=0)
    assessments_by_area: dict[str, int] = Field(default_factory=dict)
    assessments_by_rating: dict[str, int] = Field(default_factory=dict)
    avg_compliance_score: float = Field(ge=0)
    total_findings: int = Field(ge=0)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_status: dict[str, int] = Field(default_factory=dict)
    open_findings: int = Field(ge=0)
    total_training_records: int = Field(ge=0)
    training_by_status: dict[str, int] = Field(default_factory=dict)
    training_completion_pct: float = Field(ge=0, le=100)
    total_adherence_records: int = Field(ge=0)
    adherence_rate: float = Field(ge=0, le=100)
    total_corrective_actions: int = Field(ge=0)
    open_corrective_actions: int = Field(ge=0)
