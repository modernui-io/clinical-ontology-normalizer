"""Pydantic schemas for Patient Stratification Management (STRAT-MGT).

Manages patient stratification operations: stratification factor tracking,
balance assessments, covariate analysis, stratification arm assignments,
randomization balance monitoring, and stratification operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StratFactorType(str, Enum):
    DEMOGRAPHIC = "demographic"
    DISEASE_SEVERITY = "disease_severity"
    BIOMARKER = "biomarker"
    GEOGRAPHIC = "geographic"
    PRIOR_THERAPY = "prior_therapy"
    COMORBIDITY = "comorbidity"


class BalanceStatus(str, Enum):
    BALANCED = "balanced"
    SLIGHTLY_IMBALANCED = "slightly_imbalanced"
    IMBALANCED = "imbalanced"
    CRITICAL = "critical"


class AssignmentMethod(str, Enum):
    PERMUTED_BLOCK = "permuted_block"
    MINIMIZATION = "minimization"
    BIASED_COIN = "biased_coin"
    URN = "urn"
    SIMPLE = "simple"


class CovariateStatus(str, Enum):
    PLANNED = "planned"
    COLLECTING = "collecting"
    COMPLETE = "complete"
    VALIDATED = "validated"
    LOCKED = "locked"


class StratificationFactor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    factor_name: str
    factor_type: StratFactorType
    levels: list[str] = Field(default_factory=list)
    is_dynamic: bool = False
    weight: float = Field(ge=0, le=1.0, default=1.0)
    is_active: bool = True
    description: str | None = None
    created_by: str
    created_at: datetime


class BalanceAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    assessment_date: datetime
    factor_id: str
    factor_name: str
    arm_counts: dict[str, int] = Field(default_factory=dict)
    total_randomized: int = Field(ge=0, default=0)
    imbalance_ratio: float = Field(ge=0, default=0.0)
    balance_status: BalanceStatus = BalanceStatus.BALANCED
    chi_square_statistic: float | None = None
    p_value: float | None = None
    assessed_by: str
    notes: str | None = None
    created_at: datetime


class CovariateAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    covariate_name: str
    covariate_type: str
    status: CovariateStatus = CovariateStatus.PLANNED
    sample_size: int = Field(ge=0, default=0)
    mean_value: float | None = None
    std_deviation: float | None = None
    missing_count: int = Field(ge=0, default=0)
    missing_pct: float = Field(ge=0, le=100, default=0.0)
    distribution_type: str | None = None
    correlation_with_outcome: float | None = None
    analyst: str
    analysis_date: datetime
    notes: str | None = None
    created_at: datetime


class ArmAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str
    arm_name: str
    assignment_method: AssignmentMethod
    assignment_date: datetime
    stratification_values: dict[str, str] = Field(default_factory=dict)
    stratum_id: str | None = None
    block_id: str | None = None
    sequence_number: int = Field(ge=1, default=1)
    is_confirmed: bool = False
    confirmed_by: str | None = None
    confirmed_date: datetime | None = None
    created_at: datetime


class RandomizationBalance(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    snapshot_date: datetime
    total_randomized: int = Field(ge=0, default=0)
    arm_distribution: dict[str, int] = Field(default_factory=dict)
    target_ratio: str = "1:1"
    actual_ratio: str | None = None
    overall_balance_status: BalanceStatus = BalanceStatus.BALANCED
    strata_balance: list[dict] = Field(default_factory=list)
    sites_with_imbalance: int = Field(ge=0, default=0)
    recommendation: str | None = None
    generated_by: str
    created_at: datetime


class StratificationFactorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    factor_name: str
    factor_type: StratFactorType
    levels: list[str] = Field(default_factory=list)
    created_by: str
    is_dynamic: bool = False
    weight: float = Field(ge=0, le=1.0, default=1.0)


class StratificationFactorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    weight: float | None = None
    levels: list[str] | None = None
    description: str | None = None


class BalanceAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    factor_id: str
    factor_name: str
    assessed_by: str
    arm_counts: dict[str, int] = Field(default_factory=dict)


class BalanceAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    balance_status: BalanceStatus | None = None
    notes: str | None = None
    chi_square_statistic: float | None = None
    p_value: float | None = None


class CovariateAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    covariate_name: str
    covariate_type: str
    analyst: str
    sample_size: int = Field(ge=0, default=0)


class CovariateAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: CovariateStatus | None = None
    mean_value: float | None = None
    std_deviation: float | None = None
    missing_count: int | None = None
    correlation_with_outcome: float | None = None
    notes: str | None = None


class ArmAssignmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    subject_id: str
    arm_name: str
    assignment_method: AssignmentMethod
    stratification_values: dict[str, str] = Field(default_factory=dict)


class ArmAssignmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_confirmed: bool | None = None
    confirmed_by: str | None = None


class RandomizationBalanceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    generated_by: str
    target_ratio: str = "1:1"
    arm_distribution: dict[str, int] = Field(default_factory=dict)


class RandomizationBalanceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    overall_balance_status: BalanceStatus | None = None
    recommendation: str | None = None
    sites_with_imbalance: int | None = None


class StratificationFactorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StratificationFactor] = Field(default_factory=list)
    total: int = Field(ge=0)


class BalanceAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[BalanceAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class CovariateAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CovariateAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class ArmAssignmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ArmAssignment] = Field(default_factory=list)
    total: int = Field(ge=0)


class RandomizationBalanceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RandomizationBalance] = Field(default_factory=list)
    total: int = Field(ge=0)


class PatientStratificationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_factors: int = Field(ge=0)
    active_factors: int = Field(ge=0)
    factors_by_type: dict[str, int] = Field(default_factory=dict)
    total_assessments: int = Field(ge=0)
    assessments_by_status: dict[str, int] = Field(default_factory=dict)
    total_covariates: int = Field(ge=0)
    covariates_by_status: dict[str, int] = Field(default_factory=dict)
    total_assignments: int = Field(ge=0)
    assignments_by_method: dict[str, int] = Field(default_factory=dict)
    confirmed_assignments: int = Field(ge=0)
    total_balance_snapshots: int = Field(ge=0)
    current_balance_status: str | None = None
