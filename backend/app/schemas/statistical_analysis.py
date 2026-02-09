"""Pydantic schemas for Statistical Analysis & Interim Analysis Management (CLINICAL-25).

Manages statistical analysis operations: Statistical Analysis Plan (SAP) definitions,
analysis result tracking with multiplicity adjustments, interim analysis with alpha
spending, sample size calculations, subgroup analyses with interaction testing,
and statistical metrics dashboards.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AnalysisType(str, Enum):
    """Type of statistical analysis performed."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPLORATORY = "exploratory"
    SENSITIVITY = "sensitivity"
    SUBGROUP = "subgroup"
    INTERIM = "interim"
    POST_HOC = "post_hoc"
    SAFETY = "safety"


class PopulationType(str, Enum):
    """Analysis population definition."""

    ITT = "itt"
    MODIFIED_ITT = "modified_itt"
    PER_PROTOCOL = "per_protocol"
    SAFETY = "safety"
    FULL_ANALYSIS_SET = "full_analysis_set"


class StatisticalMethod(str, Enum):
    """Statistical method used for analysis."""

    T_TEST = "t_test"
    CHI_SQUARE = "chi_square"
    COX_REGRESSION = "cox_regression"
    LOGISTIC_REGRESSION = "logistic_regression"
    ANCOVA = "ancova"
    MMRM = "mmrm"
    KAPLAN_MEIER = "kaplan_meier"
    FISHER_EXACT = "fisher_exact"
    WILCOXON = "wilcoxon"
    LOG_RANK = "log_rank"


class MultiplicityCorrectionMethod(str, Enum):
    """Multiplicity correction approach for multiple comparisons."""

    BONFERRONI = "bonferroni"
    HOLM = "holm"
    HOCHBERG = "hochberg"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    GATEKEEPING = "gatekeeping"
    GRAPHICAL = "graphical"
    NONE = "none"


class InterimRecommendation(str, Enum):
    """DSMB recommendation after interim analysis."""

    CONTINUE = "continue"
    STOP_EFFICACY = "stop_efficacy"
    STOP_FUTILITY = "stop_futility"
    MODIFY = "modify"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class StatisticalAnalysisPlan(BaseModel):
    """Statistical Analysis Plan (SAP) for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique SAP identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    version: str = Field(..., description="SAP version (e.g., 1.0, 2.0)")
    title: str = Field(..., description="SAP title")
    primary_endpoint: str = Field(..., description="Primary efficacy endpoint definition")
    secondary_endpoints: list[str] = Field(
        default_factory=list, description="Secondary endpoint definitions"
    )
    sample_size_calculation: str = Field(
        ..., description="Sample size calculation methodology summary"
    )
    randomization_ratio: str = Field(
        ..., description="Randomization ratio (e.g., 1:1, 2:1)"
    )
    alpha_level: float = Field(
        ..., ge=0.0, le=1.0, description="Overall type I error rate (alpha)"
    )
    power: float = Field(
        ..., ge=0.0, le=1.0, description="Statistical power (1 - beta)"
    )
    populations: list[PopulationType] = Field(
        default_factory=list, description="Analysis populations defined in the SAP"
    )
    analysis_methods: list[StatisticalMethod] = Field(
        default_factory=list, description="Statistical methods planned"
    )
    multiplicity_strategy: MultiplicityCorrectionMethod = Field(
        ..., description="Multiplicity adjustment strategy"
    )
    status: str = Field(default="draft", description="SAP status (draft, final, amended)")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AnalysisResult(BaseModel):
    """Result of a statistical analysis for a specific endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique result identifier")
    plan_id: str = Field(..., description="Associated SAP identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    analysis_type: AnalysisType = Field(..., description="Type of analysis")
    endpoint: str = Field(..., description="Endpoint analyzed")
    population: PopulationType = Field(..., description="Analysis population used")
    method: StatisticalMethod = Field(..., description="Statistical method applied")
    estimate: float = Field(..., description="Point estimate of treatment effect")
    confidence_interval_lower: float = Field(
        ..., description="Lower bound of confidence interval"
    )
    confidence_interval_upper: float = Field(
        ..., description="Upper bound of confidence interval"
    )
    p_value: float = Field(..., ge=0.0, le=1.0, description="Unadjusted p-value")
    adjusted_p_value: float | None = Field(
        None, ge=0.0, le=1.0, description="Multiplicity-adjusted p-value"
    )
    clinically_significant: bool = Field(
        ..., description="Whether the result is considered clinically significant"
    )
    n_treatment: int = Field(..., ge=0, description="Sample size in treatment arm")
    n_control: int = Field(..., ge=0, description="Sample size in control arm")
    effect_size: float = Field(..., description="Standardized effect size (e.g., Cohen's d)")
    test_statistic: float = Field(..., description="Test statistic value")
    created_at: datetime = Field(..., description="Record creation timestamp")


class InterimAnalysis(BaseModel):
    """Interim analysis record with alpha spending tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique interim analysis identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    analysis_number: int = Field(..., ge=1, description="Sequential interim analysis number")
    planned_info_fraction: float = Field(
        ..., ge=0.0, le=1.0, description="Planned information fraction at this look"
    )
    actual_info_fraction: float = Field(
        ..., ge=0.0, le=1.0, description="Actual information fraction achieved"
    )
    analysis_date: datetime = Field(..., description="Date the interim analysis was conducted")
    alpha_spent: float = Field(
        ..., ge=0.0, le=1.0, description="Alpha spent at this interim look"
    )
    cumulative_alpha_spent: float = Field(
        ..., ge=0.0, le=1.0, description="Cumulative alpha spent across all looks"
    )
    boundary_crossed: bool = Field(
        ..., description="Whether the efficacy or futility boundary was crossed"
    )
    recommendation: InterimRecommendation = Field(
        ..., description="DSMB recommendation after this interim analysis"
    )
    dsmb_review_date: datetime | None = Field(
        None, description="Date the DSMB reviewed the interim results"
    )
    z_statistic: float | None = Field(None, description="Z-statistic at this interim look")
    efficacy_boundary: float | None = Field(
        None, description="Efficacy boundary (critical value) at this look"
    )
    futility_boundary: float | None = Field(
        None, description="Futility boundary at this look"
    )
    notes: str | None = Field(None, description="DSMB notes or recommendations")
    created_at: datetime = Field(..., description="Record creation timestamp")


class SampleSizeCalc(BaseModel):
    """Sample size calculation for a trial endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique calculation identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    endpoint: str = Field(..., description="Endpoint for which sample size is calculated")
    assumed_effect_size: float = Field(
        ..., description="Assumed treatment effect size"
    )
    alpha: float = Field(
        ..., ge=0.0, le=1.0, description="Type I error rate"
    )
    power: float = Field(
        ..., ge=0.0, le=1.0, description="Desired statistical power"
    )
    dropout_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Expected dropout rate"
    )
    calculated_n_per_arm: int = Field(
        ..., ge=1, description="Calculated sample size per treatment arm"
    )
    total_n_with_dropout: int = Field(
        ..., ge=1, description="Total sample size accounting for dropout"
    )
    method: str = Field(
        ..., description="Calculation method used (e.g., two-sample t-test, log-rank)"
    )
    assumptions: str = Field(
        ..., description="Key assumptions underlying the calculation"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class SubgroupAnalysis(BaseModel):
    """Subgroup analysis result with interaction testing."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique subgroup analysis identifier")
    result_id: str = Field(..., description="Associated primary analysis result ID")
    subgroup_variable: str = Field(
        ..., description="Variable defining the subgroup (e.g., age, sex, region)"
    )
    subgroup_value: str = Field(
        ..., description="Specific value of the subgroup variable (e.g., >=65, Male)"
    )
    estimate: float = Field(
        ..., description="Treatment effect estimate within this subgroup"
    )
    ci_lower: float = Field(..., description="Lower bound of confidence interval")
    ci_upper: float = Field(..., description="Upper bound of confidence interval")
    p_value: float = Field(
        ..., ge=0.0, le=1.0, description="P-value within this subgroup"
    )
    n: int = Field(..., ge=0, description="Sample size in this subgroup")
    interaction_p_value: float = Field(
        ..., ge=0.0, le=1.0,
        description="P-value for treatment-by-subgroup interaction test",
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SAPCreate(BaseModel):
    """Request to create a new Statistical Analysis Plan."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    version: str = Field(..., description="SAP version")
    title: str = Field(..., description="SAP title")
    primary_endpoint: str = Field(..., description="Primary endpoint definition")
    secondary_endpoints: list[str] = Field(
        default_factory=list, description="Secondary endpoints"
    )
    sample_size_calculation: str = Field(
        ..., description="Sample size calculation summary"
    )
    randomization_ratio: str = Field(..., description="Randomization ratio")
    alpha_level: float = Field(..., ge=0.0, le=1.0, description="Alpha level")
    power: float = Field(..., ge=0.0, le=1.0, description="Power")
    populations: list[PopulationType] = Field(
        default_factory=list, description="Analysis populations"
    )
    analysis_methods: list[StatisticalMethod] = Field(
        default_factory=list, description="Statistical methods"
    )
    multiplicity_strategy: MultiplicityCorrectionMethod = Field(
        ..., description="Multiplicity strategy"
    )


class SAPUpdate(BaseModel):
    """Request to update a Statistical Analysis Plan."""

    model_config = ConfigDict(from_attributes=True)

    version: str | None = Field(None, description="SAP version")
    title: str | None = Field(None, description="SAP title")
    primary_endpoint: str | None = Field(None, description="Primary endpoint")
    secondary_endpoints: list[str] | None = Field(None, description="Secondary endpoints")
    sample_size_calculation: str | None = Field(None, description="Sample size calc summary")
    randomization_ratio: str | None = Field(None, description="Randomization ratio")
    alpha_level: float | None = Field(None, ge=0.0, le=1.0, description="Alpha level")
    power: float | None = Field(None, ge=0.0, le=1.0, description="Power")
    populations: list[PopulationType] | None = Field(None, description="Populations")
    analysis_methods: list[StatisticalMethod] | None = Field(None, description="Methods")
    multiplicity_strategy: MultiplicityCorrectionMethod | None = Field(
        None, description="Multiplicity strategy"
    )
    status: str | None = Field(None, description="SAP status")


class AnalysisResultCreate(BaseModel):
    """Request to record a new analysis result."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: str = Field(..., description="SAP identifier")
    trial_id: str = Field(..., description="Trial identifier")
    analysis_type: AnalysisType = Field(..., description="Type of analysis")
    endpoint: str = Field(..., description="Endpoint analyzed")
    population: PopulationType = Field(..., description="Analysis population")
    method: StatisticalMethod = Field(..., description="Statistical method")
    estimate: float = Field(..., description="Point estimate")
    confidence_interval_lower: float = Field(..., description="CI lower bound")
    confidence_interval_upper: float = Field(..., description="CI upper bound")
    p_value: float = Field(..., ge=0.0, le=1.0, description="P-value")
    adjusted_p_value: float | None = Field(None, ge=0.0, le=1.0, description="Adjusted p-value")
    clinically_significant: bool = Field(..., description="Clinically significant")
    n_treatment: int = Field(..., ge=0, description="N treatment")
    n_control: int = Field(..., ge=0, description="N control")
    effect_size: float = Field(..., description="Effect size")
    test_statistic: float = Field(..., description="Test statistic")


class InterimAnalysisCreate(BaseModel):
    """Request to record a new interim analysis."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    analysis_number: int = Field(..., ge=1, description="Analysis number")
    planned_info_fraction: float = Field(
        ..., ge=0.0, le=1.0, description="Planned information fraction"
    )
    actual_info_fraction: float = Field(
        ..., ge=0.0, le=1.0, description="Actual information fraction"
    )
    analysis_date: datetime = Field(..., description="Analysis date")
    alpha_spent: float = Field(..., ge=0.0, le=1.0, description="Alpha spent")
    cumulative_alpha_spent: float = Field(
        ..., ge=0.0, le=1.0, description="Cumulative alpha spent"
    )
    boundary_crossed: bool = Field(..., description="Boundary crossed")
    recommendation: InterimRecommendation = Field(..., description="Recommendation")
    dsmb_review_date: datetime | None = Field(None, description="DSMB review date")
    z_statistic: float | None = Field(None, description="Z-statistic")
    efficacy_boundary: float | None = Field(None, description="Efficacy boundary")
    futility_boundary: float | None = Field(None, description="Futility boundary")
    notes: str | None = Field(None, description="Notes")


class SubgroupAnalysisCreate(BaseModel):
    """Request to record a subgroup analysis result."""

    model_config = ConfigDict(from_attributes=True)

    result_id: str = Field(..., description="Primary analysis result ID")
    subgroup_variable: str = Field(..., description="Subgroup variable")
    subgroup_value: str = Field(..., description="Subgroup value")
    estimate: float = Field(..., description="Treatment effect estimate")
    ci_lower: float = Field(..., description="CI lower bound")
    ci_upper: float = Field(..., description="CI upper bound")
    p_value: float = Field(..., ge=0.0, le=1.0, description="P-value")
    n: int = Field(..., ge=0, description="Sample size")
    interaction_p_value: float = Field(
        ..., ge=0.0, le=1.0, description="Interaction p-value"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SAPListResponse(BaseModel):
    """List of Statistical Analysis Plans."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StatisticalAnalysisPlan] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class AnalysisResultListResponse(BaseModel):
    """List of analysis results."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AnalysisResult] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InterimAnalysisListResponse(BaseModel):
    """List of interim analyses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InterimAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SampleSizeCalcListResponse(BaseModel):
    """List of sample size calculations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SampleSizeCalc] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SubgroupAnalysisListResponse(BaseModel):
    """List of subgroup analyses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SubgroupAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class StatisticalMetrics(BaseModel):
    """Aggregated statistical analysis operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_analyses: int = Field(ge=0, description="Total analysis results recorded")
    analyses_by_type: dict[str, int] = Field(
        default_factory=dict, description="Analysis counts by type"
    )
    significant_results_count: int = Field(
        ge=0, description="Number of statistically significant results (p < alpha)"
    )
    avg_effect_size: float = Field(
        ge=0.0, description="Average absolute effect size across all analyses"
    )
    interim_analyses_completed: int = Field(
        ge=0, description="Number of interim analyses completed"
    )
    alpha_remaining: float = Field(
        ge=0.0, le=1.0, description="Remaining alpha budget across all trials"
    )
    total_saps: int = Field(ge=0, description="Total SAPs defined")
    total_sample_size_calcs: int = Field(ge=0, description="Total sample size calculations")
    total_subgroup_analyses: int = Field(ge=0, description="Total subgroup analyses")
    trials_with_boundary_crossed: int = Field(
        ge=0, description="Number of trials where an interim boundary was crossed"
    )
