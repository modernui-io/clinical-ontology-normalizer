"""Pydantic schemas for Clinical Hold Management (CHM-MGT).

Manages clinical hold operations: hold events, impact assessments, corrective
action plans, restart authorizations, and clinical hold metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class HoldType(str, Enum):
    FULL_CLINICAL_HOLD = "full_clinical_hold"
    PARTIAL_CLINICAL_HOLD = "partial_clinical_hold"
    VOLUNTARY_PAUSE = "voluntary_pause"
    REGULATORY_SUSPENSION = "regulatory_suspension"
    SAFETY_PAUSE = "safety_pause"
    ADMINISTRATIVE_HOLD = "administrative_hold"


class HoldStatus(str, Enum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    LIFTED = "lifted"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class ImpactSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"
    UNKNOWN = "unknown"


class ActionPlanStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class RestartDecision(str, Enum):
    APPROVED = "approved"
    CONDITIONAL_APPROVAL = "conditional_approval"
    DENIED = "denied"
    DEFERRED = "deferred"
    PENDING = "pending"
    WITHDRAWN = "withdrawn"


# --- Main entities ---

class HoldEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    hold_type: HoldType
    hold_status: HoldStatus = HoldStatus.ACTIVE
    hold_reason: str
    issuing_authority: str
    hold_date: datetime
    notification_date: datetime | None = None
    affected_sites_count: int = Field(ge=0, default=0)
    affected_subjects_count: int = Field(ge=0, default=0)
    protocol_sections_affected: str | None = None
    regulatory_reference: str | None = None
    lift_date: datetime | None = None
    lifted_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ImpactAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    hold_event_id: str
    impact_severity: ImpactSeverity = ImpactSeverity.UNKNOWN
    assessment_area: str
    impact_description: str
    affected_endpoints: str | None = None
    enrollment_impact: str | None = None
    timeline_impact_days: int = Field(ge=0, default=0)
    financial_impact_usd: float = Field(ge=0, default=0.0)
    assessed_by: str
    assessment_date: datetime
    mitigation_strategy: str | None = None
    notes: str | None = None
    created_at: datetime


class CorrectiveActionPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    hold_event_id: str
    action_plan_status: ActionPlanStatus = ActionPlanStatus.DRAFT
    plan_title: str
    plan_description: str
    corrective_actions: str
    preventive_actions: str | None = None
    responsible_party: str
    submission_date: datetime | None = None
    approval_date: datetime | None = None
    approved_by: str | None = None
    target_completion_date: datetime | None = None
    actual_completion_date: datetime | None = None
    regulatory_submission_id: str | None = None
    notes: str | None = None
    created_at: datetime


class RestartAuthorization(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    hold_event_id: str
    restart_decision: RestartDecision = RestartDecision.PENDING
    authorization_authority: str
    decision_date: datetime | None = None
    conditions: str | None = None
    protocol_modifications_required: bool = False
    consent_updates_required: bool = False
    site_retraining_required: bool = False
    monitoring_plan_changes: str | None = None
    restart_date: datetime | None = None
    sites_reactivated_count: int = Field(ge=0, default=0)
    authorized_by: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class HoldEventCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    hold_type: HoldType
    hold_reason: str
    issuing_authority: str
    hold_date: datetime
    hold_status: HoldStatus = HoldStatus.ACTIVE


class HoldEventUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    hold_status: HoldStatus | None = None
    affected_sites_count: int | None = None
    affected_subjects_count: int | None = None
    protocol_sections_affected: str | None = None
    lift_date: datetime | None = None
    lifted_by: str | None = None
    notes: str | None = None


class ImpactAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    hold_event_id: str
    assessment_area: str
    impact_description: str
    assessed_by: str
    assessment_date: datetime
    impact_severity: ImpactSeverity = ImpactSeverity.UNKNOWN


class ImpactAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    impact_severity: ImpactSeverity | None = None
    timeline_impact_days: int | None = None
    financial_impact_usd: float | None = None
    mitigation_strategy: str | None = None
    notes: str | None = None


class CorrectiveActionPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    hold_event_id: str
    plan_title: str
    plan_description: str
    corrective_actions: str
    responsible_party: str
    action_plan_status: ActionPlanStatus = ActionPlanStatus.DRAFT


class CorrectiveActionPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    action_plan_status: ActionPlanStatus | None = None
    preventive_actions: str | None = None
    approved_by: str | None = None
    approval_date: datetime | None = None
    actual_completion_date: datetime | None = None
    notes: str | None = None


class RestartAuthorizationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    hold_event_id: str
    authorization_authority: str
    restart_decision: RestartDecision = RestartDecision.PENDING


class RestartAuthorizationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    restart_decision: RestartDecision | None = None
    conditions: str | None = None
    protocol_modifications_required: bool | None = None
    consent_updates_required: bool | None = None
    site_retraining_required: bool | None = None
    restart_date: datetime | None = None
    authorized_by: str | None = None
    notes: str | None = None


# --- List responses ---

class HoldEventListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[HoldEvent] = Field(default_factory=list)
    total: int = Field(ge=0)


class ImpactAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ImpactAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class CorrectiveActionPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CorrectiveActionPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class RestartAuthorizationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RestartAuthorization] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class ClinicalHoldMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_hold_events: int = Field(ge=0)
    holds_by_type: dict[str, int] = Field(default_factory=dict)
    holds_by_status: dict[str, int] = Field(default_factory=dict)
    total_impact_assessments: int = Field(ge=0)
    assessments_by_severity: dict[str, int] = Field(default_factory=dict)
    total_action_plans: int = Field(ge=0)
    plans_by_status: dict[str, int] = Field(default_factory=dict)
    total_restart_authorizations: int = Field(ge=0)
    restarts_by_decision: dict[str, int] = Field(default_factory=dict)
    avg_hold_duration_days: float = Field(ge=0)
