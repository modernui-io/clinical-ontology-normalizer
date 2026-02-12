"""Pydantic schemas for Biostatistics Operations (BIOSTATS-OPS).

Manages biostatistical operations: interim analysis planning, DSMB report
generation, adaptive design decisions, futility analysis, multiplicity
adjustments, and biostatistics operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AnalysisType(str, Enum):
    INTERIM = "interim"
    FINAL = "final"
    FUTILITY = "futility"
    SAFETY = "safety"
    ADAPTIVE = "adaptive"
    SENSITIVITY = "sensitivity"
    SUBGROUP = "subgroup"


class AnalysisStatus(str, Enum):
    PLANNED = "planned"
    SAP_APPROVED = "sap_approved"
    DATA_CUT = "data_cut"
    IN_ANALYSIS = "in_analysis"
    QC_REVIEW = "qc_review"
    COMPLETED = "completed"
    REPORTED = "reported"


class DecisionOutcome(str, Enum):
    CONTINUE = "continue"
    STOP_EFFICACY = "stop_for_efficacy"
    STOP_FUTILITY = "stop_for_futility"
    STOP_SAFETY = "stop_for_safety"
    MODIFY_DOSE = "modify_dose"
    EXPAND_ENROLLMENT = "expand_enrollment"
    REDUCE_SAMPLE = "reduce_sample_size"


class MultiplicityMethod(str, Enum):
    BONFERRONI = "bonferroni"
    HOLM = "holm"
    HOCHBERG = "hochberg"
    GATEKEEPING = "gatekeeping"
    GRAPHICAL = "graphical"
    ALPHA_SPENDING = "alpha_spending"
    GROUP_SEQUENTIAL = "group_sequential"


class ReportType(str, Enum):
    DSMB_REPORT = "dsmb_report"
    INTERIM_REPORT = "interim_report"
    FUTILITY_REPORT = "futility_report"
    SAFETY_REPORT = "safety_report"
    FINAL_REPORT = "final_report"
    AD_HOC_REPORT = "ad_hoc_report"


class BlindingLevel(str, Enum):
    OPEN = "open"
    BLINDED_AGGREGATE = "blinded_aggregate"
    UNBLINDED = "unblinded"
    PARTIALLY_UNBLINDED = "partially_unblinded"


class InterimAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_number: int = Field(ge=1)
    analysis_type: AnalysisType
    information_fraction: float = Field(ge=0, le=1)
    planned_date: datetime
    actual_date: datetime | None = None
    data_cutoff_date: datetime | None = None
    status: AnalysisStatus = AnalysisStatus.PLANNED
    subjects_enrolled: int = Field(ge=0, default=0)
    subjects_analyzed: int = Field(ge=0, default=0)
    events_observed: int = Field(ge=0, default=0)
    events_required: int = Field(ge=0, default=0)
    alpha_spent: float | None = None
    alpha_remaining: float | None = None
    spending_function: str | None = None
    lead_statistician: str
    created_at: datetime


class AdaptiveDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    analysis_id: str
    decision_date: datetime
    outcome: DecisionOutcome
    rationale: str
    conditional_power: float | None = None
    predictive_probability: float | None = None
    p_value: float | None = None
    test_statistic: float | None = None
    boundary_value: float | None = None
    crossed_boundary: bool | None = None
    blinding_level: BlindingLevel = BlindingLevel.UNBLINDED
    decided_by: str
    dsmb_recommendation: str | None = None


class MultiplicityAdjustment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    method: MultiplicityMethod
    family_name: str
    endpoints: list[str] = Field(default_factory=list)
    overall_alpha: float = Field(ge=0, le=1, default=0.05)
    allocated_alphas: dict[str, float] = Field(default_factory=dict)
    adjusted_p_values: dict[str, float] = Field(default_factory=dict)
    rejection_decisions: dict[str, bool] = Field(default_factory=dict)
    description: str
    statistician: str
    created_at: datetime


class StatisticalReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_id: str | None = None
    report_type: ReportType
    title: str
    version: str
    blinding_level: BlindingLevel
    status: str = "draft"
    author: str
    reviewer: str | None = None
    approval_date: datetime | None = None
    distribution_list: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    created_at: datetime


class FutilityAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    analysis_id: str
    conditional_power: float | None = None
    predictive_power: float | None = None
    futility_boundary: float | None = None
    observed_statistic: float | None = None
    futility_met: bool = False
    stochastic_curtailment_pct: float | None = None
    recommendation: str
    assessed_by: str
    assessment_date: datetime


class InterimAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_number: int = Field(ge=1)
    analysis_type: AnalysisType
    information_fraction: float = Field(ge=0, le=1)
    planned_date: datetime
    events_required: int = Field(ge=0, default=0)
    spending_function: str | None = None
    lead_statistician: str


class InterimAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AnalysisStatus | None = None
    actual_date: datetime | None = None
    data_cutoff_date: datetime | None = None
    subjects_enrolled: int | None = None
    subjects_analyzed: int | None = None
    events_observed: int | None = None
    alpha_spent: float | None = None
    alpha_remaining: float | None = None


class AdaptiveDecisionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: str
    outcome: DecisionOutcome
    rationale: str
    blinding_level: BlindingLevel = BlindingLevel.UNBLINDED
    decided_by: str
    conditional_power: float | None = None
    predictive_probability: float | None = None
    p_value: float | None = None
    dsmb_recommendation: str | None = None


class MultiplicityAdjustmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    method: MultiplicityMethod
    family_name: str
    endpoints: list[str] = Field(default_factory=list)
    overall_alpha: float = Field(ge=0, le=1, default=0.05)
    description: str
    statistician: str


class MultiplicityAdjustmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    allocated_alphas: dict[str, float] | None = None
    adjusted_p_values: dict[str, float] | None = None
    rejection_decisions: dict[str, bool] | None = None


class StatisticalReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_id: str | None = None
    report_type: ReportType
    title: str
    version: str
    blinding_level: BlindingLevel
    author: str
    distribution_list: list[str] = Field(default_factory=list)


class StatisticalReportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    reviewer: str | None = None
    key_findings: list[str] | None = None


class FutilityAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: str
    recommendation: str
    assessed_by: str
    conditional_power: float | None = None
    predictive_power: float | None = None
    futility_boundary: float | None = None
    observed_statistic: float | None = None
    stochastic_curtailment_pct: float | None = None


class InterimAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InterimAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdaptiveDecisionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AdaptiveDecision] = Field(default_factory=list)
    total: int = Field(ge=0)


class MultiplicityAdjustmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MultiplicityAdjustment] = Field(default_factory=list)
    total: int = Field(ge=0)


class StatisticalReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StatisticalReport] = Field(default_factory=list)
    total: int = Field(ge=0)


class FutilityAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FutilityAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class BiostatisticsMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_analyses: int = Field(ge=0)
    analyses_by_type: dict[str, int] = Field(default_factory=dict)
    analyses_by_status: dict[str, int] = Field(default_factory=dict)
    total_decisions: int = Field(ge=0)
    decisions_by_outcome: dict[str, int] = Field(default_factory=dict)
    total_multiplicity_adjustments: int = Field(ge=0)
    adjustments_by_method: dict[str, int] = Field(default_factory=dict)
    total_reports: int = Field(ge=0)
    reports_by_type: dict[str, int] = Field(default_factory=dict)
    total_futility_assessments: int = Field(ge=0)
    futility_met_count: int = Field(ge=0)
    avg_information_fraction: float = Field(ge=0, le=1)
