"""Pydantic schemas for Adaptive Trial Design Management (ADAPT-TRIAL).

Manages adaptive trial design operations: interim analysis tracking,
adaptation decision records, sample size re-estimation, futility
assessments, treatment arm modifications, and adaptive trial metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AnalysisType(str, Enum):
    INTERIM = "interim"
    FUTILITY = "futility"
    EFFICACY = "efficacy"
    SAFETY = "safety"
    SAMPLE_SIZE_REESTIMATION = "sample_size_reestimation"
    DOSE_SELECTION = "dose_selection"


class AnalysisOutcome(str, Enum):
    CONTINUE = "continue"
    STOP_EFFICACY = "stop_efficacy"
    STOP_FUTILITY = "stop_futility"
    STOP_SAFETY = "stop_safety"
    MODIFY = "modify"
    PENDING = "pending"


class AdaptationType(str, Enum):
    SAMPLE_SIZE = "sample_size"
    TREATMENT_ARM_DROP = "treatment_arm_drop"
    TREATMENT_ARM_ADD = "treatment_arm_add"
    DOSE_MODIFICATION = "dose_modification"
    ENDPOINT_CHANGE = "endpoint_change"
    POPULATION_ENRICHMENT = "population_enrichment"
    RANDOMIZATION_RATIO = "randomization_ratio"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class FutilityResult(str, Enum):
    NOT_FUTILE = "not_futile"
    POSSIBLY_FUTILE = "possibly_futile"
    FUTILE = "futile"
    OVERWHELMINGLY_FUTILE = "overwhelmingly_futile"


class InterimAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_number: int = Field(ge=1, default=1)
    analysis_type: AnalysisType
    planned_date: datetime
    actual_date: datetime | None = None
    information_fraction: float = Field(ge=0, le=1.0, default=0.0)
    subjects_analyzed: int = Field(ge=0, default=0)
    events_observed: int = Field(ge=0, default=0)
    outcome: AnalysisOutcome = AnalysisOutcome.PENDING
    alpha_spent: float = Field(ge=0, le=1.0, default=0.0)
    cumulative_alpha: float = Field(ge=0, le=1.0, default=0.0)
    spending_function: str = "OBrien-Fleming"
    test_statistic: float | None = None
    p_value: float | None = None
    boundary_value: float | None = None
    conditional_power: float | None = None
    performed_by: str
    dsmb_reviewed: bool = False
    notes: str | None = None
    created_at: datetime


class AdaptationDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_id: str | None = None
    adaptation_type: AdaptationType
    status: DecisionStatus = DecisionStatus.PROPOSED
    decision_date: datetime
    rationale: str
    proposed_change: str
    impact_assessment: str | None = None
    regulatory_notification_required: bool = False
    regulatory_notified: bool = False
    protocol_amendment_required: bool = False
    amendment_id: str | None = None
    proposed_by: str
    approved_by: str | None = None
    approval_date: datetime | None = None
    implementation_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class SampleSizeReestimation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_id: str | None = None
    reestimation_date: datetime
    original_sample_size: int = Field(ge=0, default=0)
    observed_effect_size: float | None = None
    assumed_effect_size: float | None = None
    observed_variance: float | None = None
    new_sample_size: int = Field(ge=0, default=0)
    change_pct: float = 0.0
    target_power: float = Field(ge=0, le=1.0, default=0.80)
    method: str = "CHW"
    blinded: bool = True
    statistician: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class FutilityAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_id: str | None = None
    assessment_date: datetime
    futility_boundary: float | None = None
    observed_statistic: float | None = None
    conditional_power: float = Field(ge=0, le=1.0, default=0.0)
    predictive_probability: float = Field(ge=0, le=1.0, default=0.0)
    result: FutilityResult = FutilityResult.NOT_FUTILE
    recommendation: str
    information_fraction: float = Field(ge=0, le=1.0, default=0.0)
    subjects_at_assessment: int = Field(ge=0, default=0)
    assessed_by: str
    dsmb_concurrence: bool | None = None
    notes: str | None = None
    created_at: datetime


class TreatmentArmModification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    decision_id: str | None = None
    arm_name: str
    modification_type: str
    modification_date: datetime
    reason: str
    subjects_affected: int = Field(ge=0, default=0)
    subjects_reassigned: int = Field(ge=0, default=0)
    new_allocation_ratio: str | None = None
    previous_allocation_ratio: str | None = None
    effective_date: datetime | None = None
    regulatory_approved: bool = False
    irb_approved: bool = False
    modified_by: str
    notes: str | None = None
    created_at: datetime


class InterimAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_type: AnalysisType
    planned_date: datetime
    performed_by: str
    analysis_number: int = Field(ge=1, default=1)
    spending_function: str = "OBrien-Fleming"


class InterimAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    outcome: AnalysisOutcome | None = None
    test_statistic: float | None = None
    p_value: float | None = None
    conditional_power: float | None = None
    dsmb_reviewed: bool | None = None
    notes: str | None = None


class AdaptationDecisionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    adaptation_type: AdaptationType
    rationale: str
    proposed_change: str
    proposed_by: str
    analysis_id: str | None = None


class AdaptationDecisionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DecisionStatus | None = None
    approved_by: str | None = None
    regulatory_notified: bool | None = None
    impact_assessment: str | None = None
    notes: str | None = None


class SampleSizeReestimationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    statistician: str
    original_sample_size: int = Field(ge=0, default=0)
    target_power: float = Field(ge=0, le=1.0, default=0.80)
    analysis_id: str | None = None


class SampleSizeReestimationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    new_sample_size: int | None = None
    observed_effect_size: float | None = None
    approved_by: str | None = None
    notes: str | None = None


class FutilityAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    recommendation: str
    assessed_by: str
    analysis_id: str | None = None
    conditional_power: float = Field(ge=0, le=1.0, default=0.0)


class FutilityAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    result: FutilityResult | None = None
    dsmb_concurrence: bool | None = None
    predictive_probability: float | None = None
    notes: str | None = None


class TreatmentArmModificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    arm_name: str
    modification_type: str
    reason: str
    modified_by: str
    decision_id: str | None = None
    subjects_affected: int = Field(ge=0, default=0)


class TreatmentArmModificationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    regulatory_approved: bool | None = None
    irb_approved: bool | None = None
    new_allocation_ratio: str | None = None
    notes: str | None = None


class InterimAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InterimAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdaptationDecisionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AdaptationDecision] = Field(default_factory=list)
    total: int = Field(ge=0)


class SampleSizeReestimationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SampleSizeReestimation] = Field(default_factory=list)
    total: int = Field(ge=0)


class FutilityAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FutilityAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class TreatmentArmModificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TreatmentArmModification] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdaptiveTrialMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_interim_analyses: int = Field(ge=0)
    analyses_by_type: dict[str, int] = Field(default_factory=dict)
    analyses_by_outcome: dict[str, int] = Field(default_factory=dict)
    total_adaptations: int = Field(ge=0)
    adaptations_by_type: dict[str, int] = Field(default_factory=dict)
    adaptations_by_status: dict[str, int] = Field(default_factory=dict)
    implemented_adaptations: int = Field(ge=0)
    total_reestimations: int = Field(ge=0)
    avg_sample_size_change_pct: float = 0.0
    total_futility_assessments: int = Field(ge=0)
    futility_by_result: dict[str, int] = Field(default_factory=dict)
    total_arm_modifications: int = Field(ge=0)
    arms_dropped: int = Field(ge=0)
    arms_added: int = Field(ge=0)
