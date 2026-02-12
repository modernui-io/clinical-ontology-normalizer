"""Pydantic schemas for Regulatory Inspection Management (REG-INSP).

Manages inspection operations: inspection scheduling, finding tracking,
CAPA response preparation, mock inspection management, inspection readiness
assessment, and regulatory inspection operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InspectionType(str, Enum):
    PRE_APPROVAL = "pre_approval"
    ROUTINE_GCP = "routine_gcp"
    FOR_CAUSE = "for_cause"
    SYSTEMS = "systems"
    DIRECTED = "directed"
    MOCK = "mock"
    READINESS = "readiness"


class InspectionAuthority(str, Enum):
    FDA = "fda"
    EMA = "ema"
    PMDA = "pmda"
    MHRA = "mhra"
    HEALTH_CANADA = "health_canada"
    TGA = "tga"
    INTERNAL = "internal"


class InspectionStatus(str, Enum):
    PLANNED = "planned"
    ANNOUNCED = "announced"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RESPONSE_REQUIRED = "response_required"
    RESPONSE_SUBMITTED = "response_submitted"
    CLOSED = "closed"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"


class FindingClassification(str, Enum):
    FORM_483 = "form_483"
    WARNING_LETTER = "warning_letter"
    GCP_FINDING = "gcp_finding"
    CRITICAL_FINDING = "critical_finding"
    MAJOR_FINDING = "major_finding"
    MINOR_FINDING = "minor_finding"
    RECOMMENDATION = "recommendation"


class Inspection(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str | None = None
    inspection_type: InspectionType
    authority: InspectionAuthority
    status: InspectionStatus = InspectionStatus.PLANNED
    title: str
    scope: str
    announced_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    duration_days: int = Field(ge=0, default=0)
    inspectors: list[str] = Field(default_factory=list)
    areas_covered: list[str] = Field(default_factory=list)
    sponsor_lead: str
    site_contact: str | None = None
    outcome: str | None = None
    response_due_date: datetime | None = None
    created_at: datetime


class InspectionFinding(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    inspection_id: str
    finding_number: str
    severity: FindingSeverity
    classification: FindingClassification
    description: str
    regulatory_reference: str | None = None
    area: str
    root_cause: str | None = None
    response_text: str | None = None
    response_status: str = "pending"
    response_due_date: datetime | None = None
    response_submitted_date: datetime | None = None
    capa_required: bool = False
    capa_id: str | None = None
    assigned_to: str
    created_at: datetime


class MockInspection(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str | None = None
    mock_type: str = "full"
    target_authority: InspectionAuthority
    planned_date: datetime
    actual_date: datetime | None = None
    status: str = "planned"
    lead_auditor: str
    audit_team: list[str] = Field(default_factory=list)
    findings_count: int = Field(ge=0, default=0)
    critical_findings: int = Field(ge=0, default=0)
    readiness_score_pct: float | None = None
    recommendations: list[str] = Field(default_factory=list)
    created_at: datetime


class ReadinessAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str | None = None
    target_authority: InspectionAuthority
    assessment_date: datetime
    overall_score_pct: float = Field(ge=0, le=100, default=0)
    document_readiness_pct: float = Field(ge=0, le=100, default=0)
    process_readiness_pct: float = Field(ge=0, le=100, default=0)
    staff_readiness_pct: float = Field(ge=0, le=100, default=0)
    system_readiness_pct: float = Field(ge=0, le=100, default=0)
    gaps_identified: list[str] = Field(default_factory=list)
    remediation_plan: str | None = None
    assessed_by: str
    next_assessment_date: datetime | None = None
    created_at: datetime


class InspectionCommitment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    inspection_id: str
    finding_id: str | None = None
    commitment_text: str
    authority: InspectionAuthority
    due_date: datetime
    status: str = "open"
    responsible_person: str
    completed_date: datetime | None = None
    evidence_reference: str | None = None
    created_at: datetime


class InspectionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    inspection_type: InspectionType
    authority: InspectionAuthority
    title: str
    scope: str
    sponsor_lead: str
    site_id: str | None = None
    site_contact: str | None = None


class InspectionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: InspectionStatus | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    outcome: str | None = None
    inspectors: list[str] | None = None
    areas_covered: list[str] | None = None


class InspectionFindingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    inspection_id: str
    finding_number: str
    severity: FindingSeverity
    classification: FindingClassification
    description: str
    area: str
    assigned_to: str
    regulatory_reference: str | None = None


class InspectionFindingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    root_cause: str | None = None
    response_text: str | None = None
    response_status: str | None = None
    capa_required: bool | None = None
    capa_id: str | None = None


class MockInspectionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    target_authority: InspectionAuthority
    planned_date: datetime
    lead_auditor: str
    site_id: str | None = None
    mock_type: str = "full"


class MockInspectionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    findings_count: int | None = None
    critical_findings: int | None = None
    readiness_score_pct: float | None = None
    recommendations: list[str] | None = None


class ReadinessAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    target_authority: InspectionAuthority
    assessed_by: str
    site_id: str | None = None


class ReadinessAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    overall_score_pct: float | None = None
    document_readiness_pct: float | None = None
    process_readiness_pct: float | None = None
    staff_readiness_pct: float | None = None
    system_readiness_pct: float | None = None
    gaps_identified: list[str] | None = None
    remediation_plan: str | None = None


class InspectionCommitmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    inspection_id: str
    commitment_text: str
    authority: InspectionAuthority
    due_date: datetime
    responsible_person: str
    finding_id: str | None = None


class InspectionCommitmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    evidence_reference: str | None = None


class InspectionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[Inspection] = Field(default_factory=list)
    total: int = Field(ge=0)


class InspectionFindingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InspectionFinding] = Field(default_factory=list)
    total: int = Field(ge=0)


class MockInspectionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MockInspection] = Field(default_factory=list)
    total: int = Field(ge=0)


class ReadinessAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ReadinessAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class InspectionCommitmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InspectionCommitment] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegulatoryInspectionMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_inspections: int = Field(ge=0)
    inspections_by_type: dict[str, int] = Field(default_factory=dict)
    inspections_by_authority: dict[str, int] = Field(default_factory=dict)
    inspections_by_status: dict[str, int] = Field(default_factory=dict)
    total_findings: int = Field(ge=0)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    open_findings: int = Field(ge=0)
    total_mock_inspections: int = Field(ge=0)
    avg_readiness_score_pct: float = Field(ge=0, le=100)
    total_commitments: int = Field(ge=0)
    overdue_commitments: int = Field(ge=0)
