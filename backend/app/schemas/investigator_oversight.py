"""Pydantic schemas for Investigator Oversight (INV-OVS).

Manages investigator oversight operations: investigator performance reviews,
site supervision records, GCP compliance checks, investigator communications,
and oversight metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PerformanceRating(str, Enum):
    OUTSTANDING = "outstanding"
    EXCEEDS_EXPECTATIONS = "exceeds_expectations"
    MEETS_EXPECTATIONS = "meets_expectations"
    NEEDS_IMPROVEMENT = "needs_improvement"
    UNSATISFACTORY = "unsatisfactory"
    NOT_EVALUATED = "not_evaluated"


class SupervisionType(str, Enum):
    ROUTINE_MONITORING = "routine_monitoring"
    FOR_CAUSE = "for_cause"
    TRIGGERED = "triggered"
    CLOSEOUT = "closeout"
    REMOTE_REVIEW = "remote_review"
    CENTRALIZED = "centralized"


class ComplianceResult(str, Enum):
    COMPLIANT = "compliant"
    MINOR_FINDING = "minor_finding"
    MAJOR_FINDING = "major_finding"
    CRITICAL_FINDING = "critical_finding"
    NOT_ASSESSED = "not_assessed"
    REMEDIATED = "remediated"


class CommunicationType(str, Enum):
    PROTOCOL_UPDATE = "protocol_update"
    SAFETY_ALERT = "safety_alert"
    ENROLLMENT_STATUS = "enrollment_status"
    REGULATORY_NOTICE = "regulatory_notice"
    TRAINING_REMINDER = "training_reminder"
    GENERAL_CORRESPONDENCE = "general_correspondence"


class CommunicationStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


# --- Main entities ---

class InvestigatorPerformance(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    investigator_name: str
    performance_rating: PerformanceRating = PerformanceRating.NOT_EVALUATED
    review_period_start: datetime
    review_period_end: datetime
    enrollment_target: int = Field(ge=0, default=0)
    enrollment_actual: int = Field(ge=0, default=0)
    protocol_deviations: int = Field(ge=0, default=0)
    query_response_days: float = Field(ge=0, default=0.0)
    sae_reporting_compliance_pct: float = Field(ge=0, le=100, default=100.0)
    training_completion_pct: float = Field(ge=0, le=100, default=100.0)
    reviewed_by: str
    notes: str | None = None
    created_at: datetime


class SiteSupervision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    supervision_type: SupervisionType
    visit_date: datetime
    monitor_name: str
    duration_hours: float = Field(ge=0, default=8.0)
    findings_count: int = Field(ge=0, default=0)
    critical_findings: int = Field(ge=0, default=0)
    action_items_generated: int = Field(ge=0, default=0)
    action_items_resolved: int = Field(ge=0, default=0)
    report_finalized: bool = False
    follow_up_required: bool = False
    follow_up_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class GCPComplianceCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    investigator_name: str
    compliance_result: ComplianceResult = ComplianceResult.NOT_ASSESSED
    check_date: datetime
    gcp_area: str
    finding_description: str | None = None
    corrective_action: str | None = None
    corrective_action_due: datetime | None = None
    corrective_action_completed: datetime | None = None
    verified_by: str | None = None
    assessed_by: str
    notes: str | None = None
    created_at: datetime


class InvestigatorCommunication(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str | None = None
    investigator_name: str | None = None
    communication_type: CommunicationType
    communication_status: CommunicationStatus = CommunicationStatus.DRAFT
    subject_line: str
    content_summary: str
    sent_date: datetime | None = None
    acknowledged_date: datetime | None = None
    sent_by: str
    response_required: bool = False
    response_deadline: datetime | None = None
    distribution_count: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class InvestigatorPerformanceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    investigator_name: str
    reviewed_by: str
    review_period_start: datetime
    review_period_end: datetime
    enrollment_target: int = Field(ge=0, default=0)


class InvestigatorPerformanceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    performance_rating: PerformanceRating | None = None
    enrollment_actual: int | None = None
    protocol_deviations: int | None = None
    query_response_days: float | None = None
    sae_reporting_compliance_pct: float | None = None
    notes: str | None = None


class SiteSupervisionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    supervision_type: SupervisionType
    visit_date: datetime
    monitor_name: str
    duration_hours: float = Field(ge=0, default=8.0)


class SiteSupervisionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    findings_count: int | None = None
    critical_findings: int | None = None
    action_items_resolved: int | None = None
    report_finalized: bool | None = None
    follow_up_required: bool | None = None
    follow_up_date: datetime | None = None
    notes: str | None = None


class GCPComplianceCheckCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    investigator_name: str
    gcp_area: str
    check_date: datetime
    assessed_by: str


class GCPComplianceCheckUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compliance_result: ComplianceResult | None = None
    finding_description: str | None = None
    corrective_action: str | None = None
    corrective_action_due: datetime | None = None
    corrective_action_completed: datetime | None = None
    verified_by: str | None = None
    notes: str | None = None


class InvestigatorCommunicationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    communication_type: CommunicationType
    subject_line: str
    content_summary: str
    sent_by: str
    site_id: str | None = None
    investigator_name: str | None = None


class InvestigatorCommunicationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    communication_status: CommunicationStatus | None = None
    sent_date: datetime | None = None
    acknowledged_date: datetime | None = None
    response_required: bool | None = None
    response_deadline: datetime | None = None
    notes: str | None = None


# --- List responses ---

class InvestigatorPerformanceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InvestigatorPerformance] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteSupervisionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteSupervision] = Field(default_factory=list)
    total: int = Field(ge=0)


class GCPComplianceCheckListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[GCPComplianceCheck] = Field(default_factory=list)
    total: int = Field(ge=0)


class InvestigatorCommunicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InvestigatorCommunication] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class InvestigatorOversightMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_performance_reviews: int = Field(ge=0)
    reviews_by_rating: dict[str, int] = Field(default_factory=dict)
    avg_enrollment_achievement_pct: float = Field(ge=0)
    total_supervisions: int = Field(ge=0)
    supervisions_by_type: dict[str, int] = Field(default_factory=dict)
    total_compliance_checks: int = Field(ge=0)
    checks_by_result: dict[str, int] = Field(default_factory=dict)
    compliance_rate: float = Field(ge=0)
    total_communications: int = Field(ge=0)
    communications_by_type: dict[str, int] = Field(default_factory=dict)
    communication_acknowledgment_rate: float = Field(ge=0)
