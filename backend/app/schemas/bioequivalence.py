"""Pydantic schemas for Bioequivalence Study Management (BE-STUDY).

Manages bioequivalence study operations: BE study tracking,
PK parameter analysis, formulation comparison, statistical
assessments, and regulatory filing with compliance metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StudyDesign(str, Enum):
    CROSSOVER_2X2 = "crossover_2x2"
    CROSSOVER_3X3 = "crossover_3x3"
    PARALLEL = "parallel"
    REPLICATE = "replicate"
    SEQUENTIAL = "sequential"
    ADAPTIVE = "adaptive"


class StudyStatus(str, Enum):
    PLANNED = "planned"
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    FAILED = "failed"


class PKParameterName(str, Enum):
    AUC_0_T = "AUC_0_t"
    AUC_0_INF = "AUC_0_inf"
    CMAX = "Cmax"
    TMAX = "Tmax"
    T_HALF = "t_half"
    CL_F = "CL_F"


class BECriterion(str, Enum):
    STANDARD_80_125 = "80_125"
    NARROW_90_111 = "90_111"
    WIDE_75_133 = "75_133"
    SCALED_ABE = "scaled_ABE"
    TMAX_NONPARAMETRIC = "Tmax_nonparametric"


class BEResult(str, Enum):
    BIOEQUIVALENT = "bioequivalent"
    NOT_BIOEQUIVALENT = "not_bioequivalent"
    INCONCLUSIVE = "inconclusive"
    PENDING = "pending"


class BEStudy(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_name: str
    study_design: StudyDesign
    status: StudyStatus = StudyStatus.PLANNED
    reference_product: str
    test_product: str
    route_of_administration: str = "oral"
    dosage_strength: str
    subjects_planned: int = Field(ge=0, default=0)
    subjects_enrolled: int = Field(ge=0, default=0)
    subjects_completed: int = Field(ge=0, default=0)
    washout_period_days: int = Field(ge=0, default=7)
    fasting_fed: str = "fasting"
    be_criterion: BECriterion = BECriterion.STANDARD_80_125
    overall_result: BEResult = BEResult.PENDING
    start_date: datetime | None = None
    completion_date: datetime | None = None
    principal_investigator: str
    sponsor: str | None = None
    notes: str | None = None
    created_at: datetime


class PKParameter(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str
    parameter_name: PKParameterName
    formulation: str
    subject_count: int = Field(ge=0, default=0)
    geometric_mean: float | None = None
    arithmetic_mean: float | None = None
    cv_pct: float = Field(ge=0, le=100, default=0.0)
    median: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str = "ng*h/mL"
    ln_transformed: bool = True
    analyzed_by: str
    analysis_date: datetime
    notes: str | None = None
    created_at: datetime


class FormulationComparison(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str
    parameter_name: PKParameterName
    test_gmean: float | None = None
    reference_gmean: float | None = None
    ratio_pct: float | None = None
    ci_lower_pct: float | None = None
    ci_upper_pct: float | None = None
    be_criterion: BECriterion
    within_limits: bool = False
    result: BEResult = BEResult.PENDING
    intra_subject_cv_pct: float | None = None
    power_pct: float | None = None
    method: str = "ANOVA"
    analyzed_by: str
    analysis_date: datetime
    notes: str | None = None
    created_at: datetime


class StatisticalAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str
    assessment_name: str
    model_used: str = "mixed_effects_ANOVA"
    factors: list[str] = Field(default_factory=list)
    sequence_effect_p: float | None = None
    period_effect_p: float | None = None
    treatment_effect_p: float | None = None
    subject_within_sequence_p: float | None = None
    residual_variance: float | None = None
    outliers_detected: int = Field(ge=0, default=0)
    outliers_excluded: int = Field(ge=0, default=0)
    sensitivity_analysis_done: bool = False
    consistent_with_primary: bool = True
    assessed_by: str
    assessment_date: datetime
    notes: str | None = None
    created_at: datetime


class RegulatoryFiling(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str
    filing_type: str
    regulatory_authority: str
    submission_date: datetime | None = None
    target_date: datetime | None = None
    reference_number: str | None = None
    status: str = "draft"
    study_report_attached: bool = False
    dissolution_data_included: bool = False
    bioanalytical_report_included: bool = False
    statistical_report_included: bool = False
    response_date: datetime | None = None
    outcome: str | None = None
    prepared_by: str
    reviewer: str | None = None
    notes: str | None = None
    created_at: datetime


class BEStudyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_name: str
    study_design: StudyDesign
    reference_product: str
    test_product: str
    dosage_strength: str
    principal_investigator: str
    subjects_planned: int = Field(ge=0, default=0)


class BEStudyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: StudyStatus | None = None
    overall_result: BEResult | None = None
    subjects_enrolled: int | None = None
    subjects_completed: int | None = None
    notes: str | None = None


class PKParameterCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_id: str
    parameter_name: PKParameterName
    formulation: str
    analyzed_by: str
    subject_count: int = Field(ge=0, default=0)


class PKParameterUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    geometric_mean: float | None = None
    cv_pct: float | None = None
    unit: str | None = None
    notes: str | None = None


class FormulationComparisonCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_id: str
    parameter_name: PKParameterName
    be_criterion: BECriterion
    analyzed_by: str
    method: str = "ANOVA"


class FormulationComparisonUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    result: BEResult | None = None
    ratio_pct: float | None = None
    ci_lower_pct: float | None = None
    ci_upper_pct: float | None = None
    notes: str | None = None


class StatisticalAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_id: str
    assessment_name: str
    assessed_by: str
    model_used: str = "mixed_effects_ANOVA"
    factors: list[str] = Field(default_factory=list)


class StatisticalAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sensitivity_analysis_done: bool | None = None
    consistent_with_primary: bool | None = None
    outliers_excluded: int | None = None
    notes: str | None = None


class RegulatoryFilingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_id: str
    filing_type: str
    regulatory_authority: str
    prepared_by: str
    target_date: datetime | None = None


class RegulatoryFilingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    outcome: str | None = None
    reviewer: str | None = None
    reference_number: str | None = None
    notes: str | None = None


class BEStudyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[BEStudy] = Field(default_factory=list)
    total: int = Field(ge=0)


class PKParameterListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PKParameter] = Field(default_factory=list)
    total: int = Field(ge=0)


class FormulationComparisonListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FormulationComparison] = Field(default_factory=list)
    total: int = Field(ge=0)


class StatisticalAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StatisticalAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegulatoryFilingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegulatoryFiling] = Field(default_factory=list)
    total: int = Field(ge=0)


class BioequivalenceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_studies: int = Field(ge=0)
    studies_by_design: dict[str, int] = Field(default_factory=dict)
    studies_by_status: dict[str, int] = Field(default_factory=dict)
    studies_by_result: dict[str, int] = Field(default_factory=dict)
    total_pk_parameters: int = Field(ge=0)
    parameters_by_name: dict[str, int] = Field(default_factory=dict)
    total_comparisons: int = Field(ge=0)
    comparisons_within_limits: int = Field(ge=0)
    total_assessments: int = Field(ge=0)
    total_filings: int = Field(ge=0)
    filings_by_status: dict[str, int] = Field(default_factory=dict)
