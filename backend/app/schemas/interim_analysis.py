"""Pydantic schemas for Interim Analysis Management (IA-MGT).

Manages interim analysis operations: analysis plans, data cut definitions,
DSMB review records, statistical review outcomes, and interim analysis metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AnalysisPlanStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    COMPLETED = "completed"
    AMENDED = "amended"
    CANCELLED = "cancelled"


class DataCutStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VALIDATED = "validated"
    RELEASED = "released"
    SUPERSEDED = "superseded"


class DSMBRecommendation(str, Enum):
    CONTINUE_AS_PLANNED = "continue_as_planned"
    MODIFY_PROTOCOL = "modify_protocol"
    STOP_FOR_EFFICACY = "stop_for_efficacy"
    STOP_FOR_FUTILITY = "stop_for_futility"
    STOP_FOR_SAFETY = "stop_for_safety"
    REQUEST_ADDITIONAL_DATA = "request_additional_data"


class ReviewOutcome(str, Enum):
    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"
    INCONCLUSIVE = "inconclusive"
    BOUNDARY_CROSSED = "boundary_crossed"
    NO_SIGNAL = "no_signal"
    DEFERRED = "deferred"


class BlindingStatus(str, Enum):
    FULLY_BLINDED = "fully_blinded"
    PARTIALLY_UNBLINDED = "partially_unblinded"
    FULLY_UNBLINDED = "fully_unblinded"
    OPEN_LABEL = "open_label"
    INDEPENDENT_REVIEW = "independent_review"


# --- Main entities ---

class AnalysisPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    plan_name: str
    version: str
    analysis_plan_status: AnalysisPlanStatus = AnalysisPlanStatus.DRAFT
    planned_analyses_count: int = Field(ge=0, default=0)
    primary_endpoint: str
    secondary_endpoints: str | None = None
    alpha_spending_function: str | None = None
    information_fraction: float | None = None
    stopping_boundaries: str | None = None
    authored_by: str
    approved_by: str | None = None
    approval_date: datetime | None = None
    effective_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class DataCutDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_plan_id: str
    cut_name: str
    data_cut_status: DataCutStatus = DataCutStatus.PLANNED
    cut_date: datetime | None = None
    target_enrollment: int = Field(ge=0, default=0)
    actual_enrollment: int = Field(ge=0, default=0)
    target_events: int = Field(ge=0, default=0)
    actual_events: int = Field(ge=0, default=0)
    blinding_status: BlindingStatus = BlindingStatus.FULLY_BLINDED
    database_lock_date: datetime | None = None
    data_transfer_date: datetime | None = None
    responsible_statistician: str
    notes: str | None = None
    created_at: datetime


class DSMBReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    data_cut_id: str
    meeting_date: datetime
    meeting_number: int = Field(ge=1, default=1)
    dsmb_recommendation: DSMBRecommendation = DSMBRecommendation.CONTINUE_AS_PLANNED
    attendees_count: int = Field(ge=0, default=0)
    quorum_met: bool = True
    safety_concerns_raised: bool = False
    efficacy_signal_detected: bool = False
    minutes_document_id: str | None = None
    letter_sent_date: datetime | None = None
    sponsor_notified_date: datetime | None = None
    chair_name: str
    notes: str | None = None
    created_at: datetime


class StatisticalReviewOutcome(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    data_cut_id: str
    dsmb_review_id: str | None = None
    review_outcome: ReviewOutcome = ReviewOutcome.INCONCLUSIVE
    test_statistic: float | None = None
    p_value: float | None = None
    confidence_interval_lower: float | None = None
    confidence_interval_upper: float | None = None
    effect_size: float | None = None
    conditional_power: float | None = None
    predictive_probability: float | None = None
    sample_size_reestimation: bool = False
    reviewed_by: str
    review_date: datetime
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class AnalysisPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    plan_name: str
    version: str
    primary_endpoint: str
    authored_by: str
    planned_analyses_count: int = Field(ge=0, default=0)


class AnalysisPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_plan_status: AnalysisPlanStatus | None = None
    approved_by: str | None = None
    approval_date: datetime | None = None
    alpha_spending_function: str | None = None
    stopping_boundaries: str | None = None
    notes: str | None = None


class DataCutDefinitionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_plan_id: str
    cut_name: str
    responsible_statistician: str
    target_enrollment: int = Field(ge=0, default=0)
    target_events: int = Field(ge=0, default=0)


class DataCutDefinitionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data_cut_status: DataCutStatus | None = None
    cut_date: datetime | None = None
    actual_enrollment: int | None = None
    actual_events: int | None = None
    blinding_status: BlindingStatus | None = None
    database_lock_date: datetime | None = None
    notes: str | None = None


class DSMBReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    data_cut_id: str
    meeting_date: datetime
    meeting_number: int = Field(ge=1, default=1)
    chair_name: str
    attendees_count: int = Field(ge=0, default=0)


class DSMBReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dsmb_recommendation: DSMBRecommendation | None = None
    quorum_met: bool | None = None
    safety_concerns_raised: bool | None = None
    efficacy_signal_detected: bool | None = None
    letter_sent_date: datetime | None = None
    notes: str | None = None


class StatisticalReviewOutcomeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    data_cut_id: str
    reviewed_by: str
    review_date: datetime
    dsmb_review_id: str | None = None


class StatisticalReviewOutcomeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    review_outcome: ReviewOutcome | None = None
    test_statistic: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    conditional_power: float | None = None
    sample_size_reestimation: bool | None = None
    notes: str | None = None


# --- List responses ---

class AnalysisPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AnalysisPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataCutDefinitionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataCutDefinition] = Field(default_factory=list)
    total: int = Field(ge=0)


class DSMBReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DSMBReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class StatisticalReviewOutcomeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StatisticalReviewOutcome] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class InterimAnalysisMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_analysis_plans: int = Field(ge=0)
    plans_by_status: dict[str, int] = Field(default_factory=dict)
    total_data_cuts: int = Field(ge=0)
    cuts_by_status: dict[str, int] = Field(default_factory=dict)
    data_cut_completion_rate: float = Field(ge=0)
    total_dsmb_reviews: int = Field(ge=0)
    reviews_by_recommendation: dict[str, int] = Field(default_factory=dict)
    total_statistical_outcomes: int = Field(ge=0)
    outcomes_by_result: dict[str, int] = Field(default_factory=dict)
    boundary_crossing_rate: float = Field(ge=0)
