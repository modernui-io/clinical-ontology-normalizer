"""Pydantic schemas for Clinical Trial Risk Management (RISK-MGMT).

Manages trial-level risk identification, risk assessment, risk mitigation
planning, risk monitoring, risk reviews, issue escalation, and risk metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RiskCategory(str, Enum):
    SAFETY = "safety"
    QUALITY = "quality"
    OPERATIONAL = "operational"
    REGULATORY = "regulatory"
    FINANCIAL = "financial"
    REPUTATIONAL = "reputational"
    SCIENTIFIC = "scientific"
    SUPPLY = "supply"


class RiskProbability(str, Enum):
    RARE = "rare"
    UNLIKELY = "unlikely"
    POSSIBLE = "possible"
    LIKELY = "likely"
    ALMOST_CERTAIN = "almost_certain"


class RiskImpact(str, Enum):
    NEGLIGIBLE = "negligible"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CATASTROPHIC = "catastrophic"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MitigationStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"


class RiskStatus(str, Enum):
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    CLOSED = "closed"
    ESCALATED = "escalated"


class IssueStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    ACTION_REQUIRED = "action_required"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TrialRisk(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    risk_title: str
    category: RiskCategory
    description: str
    probability: RiskProbability
    impact: RiskImpact
    risk_level: RiskLevel
    status: RiskStatus = RiskStatus.IDENTIFIED
    identified_by: str
    identified_date: datetime
    owner: str
    affected_areas: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    residual_risk_level: RiskLevel | None = None
    last_reviewed: datetime | None = None
    closed_date: datetime | None = None
    created_at: datetime


class RiskMitigation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    risk_id: str
    action: str
    responsible_party: str
    due_date: datetime
    status: MitigationStatus = MitigationStatus.PLANNED
    completion_date: datetime | None = None
    effectiveness_notes: str | None = None
    cost_estimate: float | None = None


class RiskReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    risk_id: str
    review_date: datetime
    reviewer: str
    current_probability: RiskProbability
    current_impact: RiskImpact
    current_risk_level: RiskLevel
    notes: str
    action_items: list[str] = Field(default_factory=list)
    next_review_date: datetime | None = None


class RiskIssue(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    risk_id: str | None = None
    title: str
    description: str
    category: RiskCategory
    severity: RiskLevel
    status: IssueStatus = IssueStatus.OPEN
    reported_by: str
    reported_date: datetime
    assigned_to: str | None = None
    resolution: str | None = None
    resolved_date: datetime | None = None


class TrialRiskCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    risk_title: str
    category: RiskCategory
    description: str
    probability: RiskProbability
    impact: RiskImpact
    risk_level: RiskLevel
    identified_by: str
    owner: str
    affected_areas: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)


class TrialRiskUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    risk_title: str | None = None
    probability: RiskProbability | None = None
    impact: RiskImpact | None = None
    risk_level: RiskLevel | None = None
    status: RiskStatus | None = None
    owner: str | None = None
    residual_risk_level: RiskLevel | None = None
    affected_areas: list[str] | None = None
    triggers: list[str] | None = None


class RiskMitigationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    risk_id: str
    action: str
    responsible_party: str
    due_date: datetime
    cost_estimate: float | None = None


class RiskMitigationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    action: str | None = None
    status: MitigationStatus | None = None
    effectiveness_notes: str | None = None
    cost_estimate: float | None = None


class RiskReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    risk_id: str
    reviewer: str
    current_probability: RiskProbability
    current_impact: RiskImpact
    current_risk_level: RiskLevel
    notes: str
    action_items: list[str] = Field(default_factory=list)
    next_review_date: datetime | None = None


class RiskIssueCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    risk_id: str | None = None
    title: str
    description: str
    category: RiskCategory
    severity: RiskLevel
    reported_by: str
    assigned_to: str | None = None


class RiskIssueUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: IssueStatus | None = None
    severity: RiskLevel | None = None
    assigned_to: str | None = None
    resolution: str | None = None


class TrialRiskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TrialRisk] = Field(default_factory=list)
    total: int = Field(ge=0)


class RiskMitigationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RiskMitigation] = Field(default_factory=list)
    total: int = Field(ge=0)


class RiskReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RiskReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class RiskIssueListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RiskIssue] = Field(default_factory=list)
    total: int = Field(ge=0)


class RiskManagementMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_risks: int = Field(ge=0)
    risks_by_category: dict[str, int] = Field(default_factory=dict)
    risks_by_level: dict[str, int] = Field(default_factory=dict)
    risks_by_status: dict[str, int] = Field(default_factory=dict)
    open_risks: int = Field(ge=0)
    critical_risks: int = Field(ge=0)
    total_mitigations: int = Field(ge=0)
    mitigations_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_mitigations: int = Field(ge=0)
    total_reviews: int = Field(ge=0)
    total_issues: int = Field(ge=0)
    open_issues: int = Field(ge=0)
    issues_by_severity: dict[str, int] = Field(default_factory=dict)
