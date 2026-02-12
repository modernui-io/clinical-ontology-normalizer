"""Pydantic schemas for Safety Signal Detection (SAFETY-SIGNAL).

Manages pharmacovigilance signal detection: disproportionality analysis,
signal evaluation, safety signal lifecycle, cumulative review tracking,
aggregate safety reports, and signal detection operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SignalMethod(str, Enum):
    PRR = "proportional_reporting_ratio"
    ROR = "reporting_odds_ratio"
    BCPNN = "bayesian_confidence_propagation"
    MGPS = "multi_item_gamma_poisson"
    EBGM = "empirical_bayes_geometric_mean"
    FREQUENTIST = "frequentist"
    BAYESIAN = "bayesian"


class SignalStatus(str, Enum):
    DETECTED = "detected"
    UNDER_EVALUATION = "under_evaluation"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    ONGOING_MONITORING = "ongoing_monitoring"
    CLOSED = "closed"


class SignalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CausalityAssessment(str, Enum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    CONDITIONAL = "conditional"
    UNASSESSABLE = "unassessable"


class ReportPeriod(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"


class SafetySignal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    signal_name: str
    preferred_term: str
    meddra_code: str | None = None
    soc: str | None = None
    detection_method: SignalMethod
    status: SignalStatus = SignalStatus.DETECTED
    priority: SignalPriority = SignalPriority.MEDIUM
    detected_date: datetime
    drug_name: str
    comparator: str | None = None
    observed_cases: int = Field(ge=0, default=0)
    expected_cases: float = Field(ge=0, default=0)
    prr_value: float | None = None
    ror_value: float | None = None
    ebgm_value: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None
    causality: CausalityAssessment | None = None
    detected_by: str
    assigned_to: str | None = None
    created_at: datetime


class SignalEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    signal_id: str
    evaluation_date: datetime
    evaluator: str
    clinical_significance: str
    biological_plausibility: str | None = None
    temporal_relationship: bool | None = None
    dose_response: bool | None = None
    dechallenge_positive: bool | None = None
    rechallenge_positive: bool | None = None
    alternative_explanations: str | None = None
    literature_support: str | None = None
    overall_assessment: CausalityAssessment
    recommendation: str
    action_items: list[str] = Field(default_factory=list)


class CumulativeReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    signal_id: str
    review_date: datetime
    review_period: ReportPeriod
    cumulative_cases: int = Field(ge=0, default=0)
    new_cases_in_period: int = Field(ge=0, default=0)
    total_exposure_patient_years: float = Field(ge=0, default=0)
    incidence_rate: float | None = None
    trend: str | None = None
    reviewer: str
    conclusion: str
    next_review_date: datetime | None = None


class DisproportionalityAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_name: str
    method: SignalMethod
    run_date: datetime
    data_cutoff_date: datetime
    total_events_analyzed: int = Field(ge=0, default=0)
    signals_detected: int = Field(ge=0, default=0)
    threshold_prr: float | None = None
    threshold_ror: float | None = None
    threshold_ebgm: float | None = None
    min_case_count: int = Field(ge=1, default=3)
    run_by: str
    status: str = "completed"
    report_reference: str | None = None


class AggregateSafetyReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    report_type: str
    period: ReportPeriod
    period_start: datetime
    period_end: datetime
    total_subjects_exposed: int = Field(ge=0, default=0)
    total_aes: int = Field(ge=0, default=0)
    total_saes: int = Field(ge=0, default=0)
    deaths: int = Field(ge=0, default=0)
    new_signals: int = Field(ge=0, default=0)
    ongoing_signals: int = Field(ge=0, default=0)
    benefit_risk_conclusion: str | None = None
    author: str
    reviewer: str | None = None
    approval_date: datetime | None = None
    submitted_date: datetime | None = None
    created_at: datetime


class SafetySignalCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    signal_name: str
    preferred_term: str
    meddra_code: str | None = None
    soc: str | None = None
    detection_method: SignalMethod
    priority: SignalPriority = SignalPriority.MEDIUM
    drug_name: str
    comparator: str | None = None
    observed_cases: int = Field(ge=0, default=0)
    expected_cases: float = Field(ge=0, default=0)
    detected_by: str


class SafetySignalUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SignalStatus | None = None
    priority: SignalPriority | None = None
    causality: CausalityAssessment | None = None
    prr_value: float | None = None
    ror_value: float | None = None
    ebgm_value: float | None = None
    assigned_to: str | None = None


class SignalEvaluationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    signal_id: str
    evaluator: str
    clinical_significance: str
    overall_assessment: CausalityAssessment
    recommendation: str
    action_items: list[str] = Field(default_factory=list)
    biological_plausibility: str | None = None
    temporal_relationship: bool | None = None
    dose_response: bool | None = None


class CumulativeReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    signal_id: str
    review_period: ReportPeriod
    cumulative_cases: int = Field(ge=0, default=0)
    new_cases_in_period: int = Field(ge=0, default=0)
    total_exposure_patient_years: float = Field(ge=0, default=0)
    reviewer: str
    conclusion: str
    next_review_date: datetime | None = None


class DisproportionalityAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_name: str
    method: SignalMethod
    data_cutoff_date: datetime
    min_case_count: int = Field(ge=1, default=3)
    run_by: str
    threshold_prr: float | None = None
    threshold_ror: float | None = None


class DisproportionalityAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    signals_detected: int | None = None
    total_events_analyzed: int | None = None
    status: str | None = None
    report_reference: str | None = None


class AggregateSafetyReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    report_type: str
    period: ReportPeriod
    period_start: datetime
    period_end: datetime
    total_subjects_exposed: int = Field(ge=0, default=0)
    author: str


class AggregateSafetyReportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_aes: int | None = None
    total_saes: int | None = None
    deaths: int | None = None
    new_signals: int | None = None
    benefit_risk_conclusion: str | None = None
    reviewer: str | None = None


class SafetySignalListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SafetySignal] = Field(default_factory=list)
    total: int = Field(ge=0)


class SignalEvaluationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SignalEvaluation] = Field(default_factory=list)
    total: int = Field(ge=0)


class CumulativeReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CumulativeReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class DisproportionalityAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DisproportionalityAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class AggregateSafetyReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AggregateSafetyReport] = Field(default_factory=list)
    total: int = Field(ge=0)


class SafetySignalMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_signals: int = Field(ge=0)
    signals_by_status: dict[str, int] = Field(default_factory=dict)
    signals_by_priority: dict[str, int] = Field(default_factory=dict)
    signals_by_method: dict[str, int] = Field(default_factory=dict)
    confirmed_signals: int = Field(ge=0)
    total_evaluations: int = Field(ge=0)
    evaluations_by_causality: dict[str, int] = Field(default_factory=dict)
    total_cumulative_reviews: int = Field(ge=0)
    total_analyses: int = Field(ge=0)
    total_aggregate_reports: int = Field(ge=0)
    reports_by_period: dict[str, int] = Field(default_factory=dict)
    avg_signal_to_evaluation_days: float = Field(ge=0)
