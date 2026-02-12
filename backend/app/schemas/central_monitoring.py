"""Pydantic schemas for Central Monitoring Management (CTR-MON).

Manages central/remote monitoring operations: remote monitoring visits,
KRI signal detection, site risk indicators, monitoring action items,
centralized review activities, and central monitoring operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MonitoringType(str, Enum):
    REMOTE = "remote"
    CENTRALIZED = "centralized"
    RISK_BASED = "risk_based"
    STATISTICAL = "statistical"
    DATA_DRIVEN = "data_driven"


class SignalCategory(str, Enum):
    ENROLLMENT = "enrollment"
    DATA_QUALITY = "data_quality"
    SAFETY = "safety"
    PROTOCOL_DEVIATION = "protocol_deviation"
    CONSENT = "consent"
    REGULATORY = "regulatory"
    OPERATIONAL = "operational"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_RESPONSE = "pending_response"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ReviewOutcome(str, Enum):
    NO_ACTION = "no_action"
    ACTION_REQUIRED = "action_required"
    SITE_CONTACT = "site_contact"
    TRIGGERED_VISIT = "triggered_visit"
    ESCALATED = "escalated"


class MonitoringVisit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    monitoring_type: MonitoringType
    visit_date: datetime
    completed_date: datetime | None = None
    monitor: str
    subjects_reviewed: int = Field(ge=0, default=0)
    queries_generated: int = Field(ge=0, default=0)
    findings_count: int = Field(ge=0, default=0)
    critical_findings: int = Field(ge=0, default=0)
    data_points_reviewed: int = Field(ge=0, default=0)
    deviations_identified: int = Field(ge=0, default=0)
    review_outcome: ReviewOutcome = ReviewOutcome.NO_ACTION
    follow_up_required: bool = False
    report_finalized: bool = False
    next_review_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class KRISignal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    signal_category: SignalCategory
    kri_name: str
    kri_value: float
    threshold_value: float
    breach_direction: str = "above"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    detection_date: datetime
    consecutive_breaches: int = Field(ge=1, default=1)
    trend_direction: str | None = None
    benchmark_value: float | None = None
    percentile_rank: float | None = None
    acknowledged: bool = False
    acknowledged_by: str | None = None
    resolution_date: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime


class SiteRiskIndicator(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    assessment_date: datetime
    overall_risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel = RiskLevel.LOW
    enrollment_score: float = Field(ge=0, le=100, default=0.0)
    data_quality_score: float = Field(ge=0, le=100, default=0.0)
    safety_score: float = Field(ge=0, le=100, default=0.0)
    compliance_score: float = Field(ge=0, le=100, default=0.0)
    operational_score: float = Field(ge=0, le=100, default=0.0)
    active_signals: int = Field(ge=0, default=0)
    open_actions: int = Field(ge=0, default=0)
    days_since_last_review: int = Field(ge=0, default=0)
    triggered_visit_recommended: bool = False
    assessed_by: str
    created_at: datetime


class MonitoringAction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    signal_id: str | None = None
    visit_id: str | None = None
    action_description: str
    category: SignalCategory
    priority: RiskLevel = RiskLevel.MEDIUM
    status: ActionStatus = ActionStatus.OPEN
    assigned_to: str
    due_date: datetime
    completed_date: datetime | None = None
    response_text: str | None = None
    escalated_to: str | None = None
    escalation_date: datetime | None = None
    days_open: int = Field(ge=0, default=0)
    created_by: str
    created_at: datetime


class CentralReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    review_period_start: datetime
    review_period_end: datetime
    reviewer: str
    review_date: datetime
    sites_reviewed: int = Field(ge=0, default=0)
    total_signals_reviewed: int = Field(ge=0, default=0)
    new_actions_created: int = Field(ge=0, default=0)
    escalations: int = Field(ge=0, default=0)
    triggered_visits_recommended: int = Field(ge=0, default=0)
    summary: str | None = None
    attendees: list[str] = Field(default_factory=list)
    minutes_document_id: str | None = None
    next_review_date: datetime | None = None
    created_at: datetime


class MonitoringVisitCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    monitoring_type: MonitoringType
    monitor: str
    subjects_reviewed: int = Field(ge=0, default=0)


class MonitoringVisitUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    review_outcome: ReviewOutcome | None = None
    follow_up_required: bool | None = None
    report_finalized: bool | None = None
    findings_count: int | None = None
    notes: str | None = None


class KRISignalCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    signal_category: SignalCategory
    kri_name: str
    kri_value: float
    threshold_value: float
    breach_direction: str = "above"


class KRISignalUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    risk_level: RiskLevel | None = None
    acknowledged: bool | None = None
    acknowledged_by: str | None = None
    resolution_notes: str | None = None


class SiteRiskIndicatorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    assessed_by: str
    enrollment_score: float = Field(ge=0, le=100, default=50.0)
    data_quality_score: float = Field(ge=0, le=100, default=50.0)
    safety_score: float = Field(ge=0, le=100, default=50.0)
    compliance_score: float = Field(ge=0, le=100, default=50.0)


class SiteRiskIndicatorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    risk_level: RiskLevel | None = None
    triggered_visit_recommended: bool | None = None
    operational_score: float | None = None


class MonitoringActionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    action_description: str
    category: SignalCategory
    assigned_to: str
    due_date: datetime
    created_by: str
    signal_id: str | None = None
    visit_id: str | None = None


class MonitoringActionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ActionStatus | None = None
    response_text: str | None = None
    escalated_to: str | None = None
    priority: RiskLevel | None = None


class CentralReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    review_period_start: datetime
    review_period_end: datetime
    reviewer: str
    sites_reviewed: int = Field(ge=0, default=0)


class CentralReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    summary: str | None = None
    next_review_date: datetime | None = None
    escalations: int | None = None
    triggered_visits_recommended: int | None = None


class MonitoringVisitListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MonitoringVisit] = Field(default_factory=list)
    total: int = Field(ge=0)


class KRISignalListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[KRISignal] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteRiskIndicatorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteRiskIndicator] = Field(default_factory=list)
    total: int = Field(ge=0)


class MonitoringActionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MonitoringAction] = Field(default_factory=list)
    total: int = Field(ge=0)


class CentralReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CentralReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class CentralMonitoringMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_visits: int = Field(ge=0)
    visits_by_type: dict[str, int] = Field(default_factory=dict)
    visits_by_outcome: dict[str, int] = Field(default_factory=dict)
    total_signals: int = Field(ge=0)
    signals_by_category: dict[str, int] = Field(default_factory=dict)
    signals_by_risk: dict[str, int] = Field(default_factory=dict)
    unresolved_signals: int = Field(ge=0)
    total_actions: int = Field(ge=0)
    actions_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_actions: int = Field(ge=0)
    avg_action_resolution_days: float = Field(ge=0)
    total_reviews: int = Field(ge=0)
    sites_at_high_risk: int = Field(ge=0)
