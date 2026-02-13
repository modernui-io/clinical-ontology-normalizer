"""Pydantic schemas for Post-Marketing Surveillance (PMS).

Manages post-marketing surveillance operations: safety signal tracking,
periodic safety update reports, risk management plan updates, product
quality review, and post-marketing commitment tracking with PMS metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SignalSource(str, Enum):
    SPONTANEOUS_REPORT = "spontaneous_report"
    LITERATURE = "literature"
    CLINICAL_TRIAL = "clinical_trial"
    REGISTRY = "registry"
    SOCIAL_MEDIA = "social_media"
    HEALTH_AUTHORITY = "health_authority"


class SignalStatus(str, Enum):
    DETECTED = "detected"
    UNDER_EVALUATION = "under_evaluation"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    MONITORING = "monitoring"
    CLOSED = "closed"


class PSURStatus(str, Enum):
    PLANNING = "planning"
    DATA_COLLECTION = "data_collection"
    DRAFTING = "drafting"
    MEDICAL_REVIEW = "medical_review"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"


class RiskCategory(str, Enum):
    IDENTIFIED_RISK = "identified_risk"
    POTENTIAL_RISK = "potential_risk"
    MISSING_INFORMATION = "missing_information"
    IMPORTANT_IDENTIFIED = "important_identified"
    IMPORTANT_POTENTIAL = "important_potential"


class CommitmentType(str, Enum):
    CLINICAL_STUDY = "clinical_study"
    REGISTRY = "registry"
    SAFETY_STUDY = "safety_study"
    EFFECTIVENESS_STUDY = "effectiveness_study"
    LABEL_UPDATE = "label_update"
    REMS = "rems"


class SafetySignalTracker(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    signal_name: str
    signal_source: SignalSource
    status: SignalStatus = SignalStatus.DETECTED
    detection_date: datetime
    product_name: str
    event_term: str
    meddra_pt: str | None = None
    case_count: int = Field(ge=0, default=0)
    reporting_rate: float = Field(ge=0, default=0.0)
    pro_score: float | None = None
    disproportionality_score: float | None = None
    clinical_significance: str | None = None
    regulatory_impact: bool = False
    label_change_needed: bool = False
    assessed_by: str
    notes: str | None = None
    created_at: datetime


class PSURRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    psur_number: int = Field(ge=1)
    reporting_period_start: datetime
    reporting_period_end: datetime
    status: PSURStatus = PSURStatus.PLANNING
    product_name: str
    submission_date: datetime | None = None
    submission_deadline: datetime
    regulatory_authority: str
    total_cases_reviewed: int = Field(ge=0, default=0)
    new_signals_identified: int = Field(ge=0, default=0)
    benefit_risk_conclusion: str = "favorable"
    label_changes_proposed: int = Field(ge=0, default=0)
    prepared_by: str
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class RiskManagementPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    plan_version: str
    effective_date: datetime
    product_name: str
    risk_category: RiskCategory
    risk_description: str
    pharmacovigilance_activity: str
    risk_minimization_measure: str | None = None
    milestones: list[str] = Field(default_factory=list)
    milestone_status: str = "on_track"
    next_update_due: datetime | None = None
    regulatory_requirement: bool = True
    managed_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ProductQualityReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    product_name: str
    batch_number: str
    review_period: str
    review_date: datetime
    batches_reviewed: int = Field(ge=0, default=0)
    batches_within_spec: int = Field(ge=0, default=0)
    out_of_spec_events: int = Field(ge=0, default=0)
    stability_data_adequate: bool = True
    trend_analysis_performed: bool = False
    deviations_identified: int = Field(ge=0, default=0)
    capa_required: bool = False
    overall_compliance: str = "compliant"
    reviewed_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class PostMarketingCommitment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    commitment_type: CommitmentType
    commitment_number: str
    description: str
    regulatory_authority: str
    product_name: str
    agreed_date: datetime
    due_date: datetime
    status: str = "open"
    progress_pct: float = Field(ge=0, le=100, default=0.0)
    last_update_date: datetime | None = None
    annual_report_included: bool = False
    milestone_met: bool = False
    responsible_party: str
    notes: str | None = None
    created_at: datetime


class SafetySignalTrackerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    signal_name: str
    signal_source: SignalSource
    product_name: str
    event_term: str
    assessed_by: str
    case_count: int = Field(ge=0, default=0)


class SafetySignalTrackerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SignalStatus | None = None
    case_count: int | None = None
    label_change_needed: bool | None = None
    clinical_significance: str | None = None
    notes: str | None = None


class PSURRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    psur_number: int = Field(ge=1)
    product_name: str
    regulatory_authority: str
    submission_deadline: datetime
    prepared_by: str
    reporting_period_start: datetime
    reporting_period_end: datetime


class PSURRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PSURStatus | None = None
    total_cases_reviewed: int | None = None
    benefit_risk_conclusion: str | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class RiskManagementPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    plan_version: str
    product_name: str
    risk_category: RiskCategory
    risk_description: str
    pharmacovigilance_activity: str
    managed_by: str


class RiskManagementPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    milestone_status: str | None = None
    risk_minimization_measure: str | None = None
    approved_by: str | None = None
    next_update_due: datetime | None = None
    notes: str | None = None


class ProductQualityReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    product_name: str
    batch_number: str
    review_period: str
    reviewed_by: str
    batches_reviewed: int = Field(ge=0, default=0)


class ProductQualityReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    overall_compliance: str | None = None
    capa_required: bool | None = None
    trend_analysis_performed: bool | None = None
    approved_by: str | None = None
    notes: str | None = None


class PostMarketingCommitmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    commitment_type: CommitmentType
    commitment_number: str
    description: str
    regulatory_authority: str
    product_name: str
    due_date: datetime
    responsible_party: str


class PostMarketingCommitmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    progress_pct: float | None = None
    milestone_met: bool | None = None
    annual_report_included: bool | None = None
    notes: str | None = None


class SafetySignalTrackerListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SafetySignalTracker] = Field(default_factory=list)
    total: int = Field(ge=0)


class PSURRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PSURRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class RiskManagementPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RiskManagementPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProductQualityReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProductQualityReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class PostMarketingCommitmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PostMarketingCommitment] = Field(default_factory=list)
    total: int = Field(ge=0)


class PostMarketingSurveillanceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_signals: int = Field(ge=0)
    signals_by_source: dict[str, int] = Field(default_factory=dict)
    signals_by_status: dict[str, int] = Field(default_factory=dict)
    confirmed_signals: int = Field(ge=0)
    total_psurs: int = Field(ge=0)
    psurs_by_status: dict[str, int] = Field(default_factory=dict)
    psurs_pending_submission: int = Field(ge=0)
    total_risk_plans: int = Field(ge=0)
    risks_by_category: dict[str, int] = Field(default_factory=dict)
    total_quality_reviews: int = Field(ge=0)
    out_of_spec_reviews: int = Field(ge=0)
    total_commitments: int = Field(ge=0)
    commitments_by_type: dict[str, int] = Field(default_factory=dict)
    open_commitments: int = Field(ge=0)
