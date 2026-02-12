"""Pydantic schemas for Regulatory Intelligence Hub (REG-INTEL).

Manages regulatory intelligence operations: landscape monitoring,
guideline tracking, authority communication records, impact
assessments, and compliance alert management with intelligence metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IntelligenceType(str, Enum):
    GUIDANCE_UPDATE = "guidance_update"
    REGULATION_CHANGE = "regulation_change"
    POLICY_SHIFT = "policy_shift"
    ENFORCEMENT_ACTION = "enforcement_action"
    ADVISORY_NOTICE = "advisory_notice"
    INDUSTRY_TREND = "industry_trend"


class RegionScope(str, Enum):
    US_FDA = "us_fda"
    EU_EMA = "eu_ema"
    UK_MHRA = "uk_mhra"
    JAPAN_PMDA = "japan_pmda"
    CHINA_NMPA = "china_nmpa"
    GLOBAL = "global"


class ImpactLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ACTION_REQUIRED = "action_required"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class CommunicationType(str, Enum):
    WRITTEN_INQUIRY = "written_inquiry"
    PRE_SUBMISSION = "pre_submission"
    TYPE_A_MEETING = "type_a_meeting"
    TYPE_B_MEETING = "type_b_meeting"
    TYPE_C_MEETING = "type_c_meeting"
    SCIENTIFIC_ADVICE = "scientific_advice"


class LandscapeMonitor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    intelligence_type: IntelligenceType
    region: RegionScope
    title: str
    description: str
    source_url: str | None = None
    publication_date: datetime
    effective_date: datetime | None = None
    impact_level: ImpactLevel = ImpactLevel.LOW
    therapeutic_area: str | None = None
    drug_class_affected: str | None = None
    action_required: bool = False
    action_deadline: datetime | None = None
    analyzed: bool = False
    analyzed_by: str | None = None
    analysis_date: datetime | None = None
    monitored_by: str
    notes: str | None = None
    created_at: datetime


class GuidelineTracker(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    guideline_name: str
    issuing_authority: str
    region: RegionScope
    version: str
    effective_date: datetime
    supersedes_version: str | None = None
    key_changes: list[str] = Field(default_factory=list)
    impact_on_protocol: bool = False
    impact_on_operations: bool = False
    compliance_gap_identified: bool = False
    remediation_plan: str | None = None
    remediation_deadline: datetime | None = None
    tracked_by: str
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class AuthorityCommunication(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    communication_type: CommunicationType
    authority: str
    region: RegionScope
    subject: str
    communication_date: datetime
    response_date: datetime | None = None
    reference_number: str | None = None
    questions_submitted: int = Field(ge=0, default=0)
    questions_answered: int = Field(ge=0, default=0)
    outcome_favorable: bool | None = None
    follow_up_required: bool = False
    follow_up_date: datetime | None = None
    meeting_minutes_filed: bool = False
    managed_by: str
    attendees: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime


class ImpactAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    intelligence_id: str | None = None
    guideline_id: str | None = None
    assessment_name: str
    assessment_date: datetime
    impact_level: ImpactLevel = ImpactLevel.LOW
    affected_areas: list[str] = Field(default_factory=list)
    protocol_change_needed: bool = False
    submission_update_needed: bool = False
    training_update_needed: bool = False
    estimated_cost_impact: float = Field(ge=0, default=0.0)
    estimated_timeline_impact_weeks: int = Field(ge=0, default=0)
    risk_mitigation: str | None = None
    stakeholders_notified: bool = False
    assessed_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ComplianceAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    alert_title: str
    severity: AlertSeverity = AlertSeverity.INFORMATIONAL
    region: RegionScope
    source_intelligence_id: str | None = None
    description: str
    alert_date: datetime
    response_deadline: datetime | None = None
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_date: datetime | None = None
    resolved: bool = False
    resolved_date: datetime | None = None
    resolution_details: str | None = None
    escalated: bool = False
    escalated_to: str | None = None
    created_by: str
    notes: str | None = None
    created_at: datetime


class LandscapeMonitorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    intelligence_type: IntelligenceType
    region: RegionScope
    title: str
    description: str
    monitored_by: str
    publication_date: datetime
    impact_level: ImpactLevel = ImpactLevel.LOW


class LandscapeMonitorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analyzed: bool | None = None
    analyzed_by: str | None = None
    impact_level: ImpactLevel | None = None
    action_required: bool | None = None
    notes: str | None = None


class GuidelineTrackerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    guideline_name: str
    issuing_authority: str
    region: RegionScope
    version: str
    effective_date: datetime
    tracked_by: str


class GuidelineTrackerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compliance_gap_identified: bool | None = None
    remediation_plan: str | None = None
    reviewed_by: str | None = None
    impact_on_protocol: bool | None = None
    notes: str | None = None


class AuthorityCommunicationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    communication_type: CommunicationType
    authority: str
    region: RegionScope
    subject: str
    managed_by: str
    communication_date: datetime


class AuthorityCommunicationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    outcome_favorable: bool | None = None
    follow_up_required: bool | None = None
    meeting_minutes_filed: bool | None = None
    questions_answered: int | None = None
    notes: str | None = None


class ImpactAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    assessment_name: str
    assessed_by: str
    impact_level: ImpactLevel = ImpactLevel.LOW
    intelligence_id: str | None = None
    guideline_id: str | None = None


class ImpactAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    impact_level: ImpactLevel | None = None
    protocol_change_needed: bool | None = None
    stakeholders_notified: bool | None = None
    approved_by: str | None = None
    notes: str | None = None


class ComplianceAlertCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    alert_title: str
    description: str
    region: RegionScope
    created_by: str
    severity: AlertSeverity = AlertSeverity.INFORMATIONAL
    source_intelligence_id: str | None = None


class ComplianceAlertUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity: AlertSeverity | None = None
    acknowledged: bool | None = None
    acknowledged_by: str | None = None
    resolved: bool | None = None
    resolution_details: str | None = None
    notes: str | None = None


class LandscapeMonitorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LandscapeMonitor] = Field(default_factory=list)
    total: int = Field(ge=0)


class GuidelineTrackerListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[GuidelineTracker] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuthorityCommunicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AuthorityCommunication] = Field(default_factory=list)
    total: int = Field(ge=0)


class ImpactAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ImpactAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class ComplianceAlertListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplianceAlert] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegulatoryIntelligenceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_intelligence_items: int = Field(ge=0)
    items_by_type: dict[str, int] = Field(default_factory=dict)
    items_by_region: dict[str, int] = Field(default_factory=dict)
    items_by_impact: dict[str, int] = Field(default_factory=dict)
    unanalyzed_items: int = Field(ge=0)
    total_guidelines: int = Field(ge=0)
    guidelines_with_gaps: int = Field(ge=0)
    total_communications: int = Field(ge=0)
    communications_by_type: dict[str, int] = Field(default_factory=dict)
    favorable_outcomes: int = Field(ge=0)
    total_impact_assessments: int = Field(ge=0)
    high_impact_assessments: int = Field(ge=0)
    total_alerts: int = Field(ge=0)
    alerts_by_severity: dict[str, int] = Field(default_factory=dict)
    unresolved_alerts: int = Field(ge=0)
