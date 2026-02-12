"""Pydantic schemas for Health Economics & Outcomes Research (HEOR).

Manages health economic analyses: cost-effectiveness studies, quality-adjusted
life year (QALY) analyses, budget impact models, value dossier generation,
payer evidence packages, and HEOR operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AnalysisType(str, Enum):
    COST_EFFECTIVENESS = "cost_effectiveness"
    COST_UTILITY = "cost_utility"
    COST_BENEFIT = "cost_benefit"
    COST_MINIMIZATION = "cost_minimization"
    BUDGET_IMPACT = "budget_impact"
    COMPARATIVE_EFFECTIVENESS = "comparative_effectiveness"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"


class StudyStatus(str, Enum):
    PLANNED = "planned"
    PROTOCOL_DEVELOPMENT = "protocol_development"
    DATA_COLLECTION = "data_collection"
    ANALYSIS = "analysis"
    REPORTING = "reporting"
    COMPLETED = "completed"
    PUBLISHED = "published"


class ModelType(str, Enum):
    MARKOV = "markov"
    DISCRETE_EVENT = "discrete_event_simulation"
    DECISION_TREE = "decision_tree"
    PARTITIONED_SURVIVAL = "partitioned_survival"
    MICROSIMULATION = "microsimulation"
    HYBRID = "hybrid"


class EvidenceGrade(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class DossierStatus(str, Enum):
    DRAFT = "draft"
    INTERNAL_REVIEW = "internal_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REVISION_REQUESTED = "revision_requested"


class PayerType(str, Enum):
    COMMERCIAL = "commercial"
    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    NATIONAL_HTA = "national_hta"
    REGIONAL_HTA = "regional_hta"
    PRIVATE_PAYER = "private_payer"
    GOVERNMENT = "government"


class HEORStudy(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    title: str
    analysis_type: AnalysisType
    comparator: str
    perspective: str
    time_horizon: str
    discount_rate_pct: float = Field(ge=0, le=100, default=3.0)
    status: StudyStatus = StudyStatus.PLANNED
    principal_analyst: str
    target_publication: str | None = None
    start_date: datetime | None = None
    completion_date: datetime | None = None
    country: str
    data_sources: list[str] = Field(default_factory=list)
    created_at: datetime


class CostEffectivenessResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    model_type: ModelType
    icer: float | None = None
    icer_currency: str = "USD"
    incremental_cost: float | None = None
    incremental_qaly: float | None = None
    incremental_ly: float | None = None
    wtp_threshold: float | None = None
    cost_effective: bool | None = None
    nmb: float | None = None
    sensitivity_analysis_type: str | None = None
    confidence_interval_low: float | None = None
    confidence_interval_high: float | None = None
    probability_cost_effective_pct: float | None = None
    analysis_date: datetime
    analyst: str


class BudgetImpactModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    target_population_size: int = Field(ge=0)
    market_share_year1_pct: float = Field(ge=0, le=100)
    market_share_year2_pct: float = Field(ge=0, le=100)
    market_share_year3_pct: float = Field(ge=0, le=100)
    drug_cost_per_patient: float = Field(ge=0)
    comparator_cost_per_patient: float = Field(ge=0)
    total_budget_impact_year1: float | None = None
    total_budget_impact_year2: float | None = None
    total_budget_impact_year3: float | None = None
    cumulative_budget_impact: float | None = None
    pmpm_impact: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    model_date: datetime
    modeler: str


class ValueDossier(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    product_name: str
    indication: str
    target_payer_type: PayerType
    target_market: str
    status: DossierStatus = DossierStatus.DRAFT
    evidence_grade: EvidenceGrade = EvidenceGrade.MODERATE
    clinical_value_summary: str
    economic_value_summary: str
    unmet_need_description: str
    key_messages: list[str] = Field(default_factory=list)
    supporting_studies: list[str] = Field(default_factory=list)
    author: str
    reviewer: str | None = None
    submission_date: datetime | None = None
    created_at: datetime


class PayerEvidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dossier_id: str
    payer_name: str
    payer_type: PayerType
    country: str
    submission_date: datetime | None = None
    response_date: datetime | None = None
    outcome: str | None = None
    coverage_decision: str | None = None
    restrictions: list[str] = Field(default_factory=list)
    feedback_summary: str | None = None
    next_review_date: datetime | None = None
    contact_person: str


class HEORStudyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    title: str
    analysis_type: AnalysisType
    comparator: str
    perspective: str
    time_horizon: str
    discount_rate_pct: float = Field(ge=0, le=100, default=3.0)
    principal_analyst: str
    country: str
    data_sources: list[str] = Field(default_factory=list)


class HEORStudyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    status: StudyStatus | None = None
    target_publication: str | None = None
    start_date: datetime | None = None
    completion_date: datetime | None = None


class CostEffectivenessResultCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: str
    model_type: ModelType
    icer: float | None = None
    incremental_cost: float | None = None
    incremental_qaly: float | None = None
    incremental_ly: float | None = None
    wtp_threshold: float | None = None
    analyst: str


class CostEffectivenessResultUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    icer: float | None = None
    incremental_cost: float | None = None
    incremental_qaly: float | None = None
    nmb: float | None = None
    sensitivity_analysis_type: str | None = None
    confidence_interval_low: float | None = None
    confidence_interval_high: float | None = None
    probability_cost_effective_pct: float | None = None


class BudgetImpactModelCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: str
    target_population_size: int = Field(ge=0)
    market_share_year1_pct: float = Field(ge=0, le=100)
    market_share_year2_pct: float = Field(ge=0, le=100)
    market_share_year3_pct: float = Field(ge=0, le=100)
    drug_cost_per_patient: float = Field(ge=0)
    comparator_cost_per_patient: float = Field(ge=0)
    assumptions: list[str] = Field(default_factory=list)
    modeler: str


class BudgetImpactModelUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_budget_impact_year1: float | None = None
    total_budget_impact_year2: float | None = None
    total_budget_impact_year3: float | None = None
    cumulative_budget_impact: float | None = None
    pmpm_impact: float | None = None


class ValueDossierCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    product_name: str
    indication: str
    target_payer_type: PayerType
    target_market: str
    clinical_value_summary: str
    economic_value_summary: str
    unmet_need_description: str
    key_messages: list[str] = Field(default_factory=list)
    author: str


class ValueDossierUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DossierStatus | None = None
    evidence_grade: EvidenceGrade | None = None
    reviewer: str | None = None
    key_messages: list[str] | None = None
    supporting_studies: list[str] | None = None


class PayerEvidenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dossier_id: str
    payer_name: str
    payer_type: PayerType
    country: str
    contact_person: str


class PayerEvidenceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    outcome: str | None = None
    coverage_decision: str | None = None
    restrictions: list[str] | None = None
    feedback_summary: str | None = None
    next_review_date: datetime | None = None


class HEORStudyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[HEORStudy] = Field(default_factory=list)
    total: int = Field(ge=0)


class CostEffectivenessResultListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CostEffectivenessResult] = Field(default_factory=list)
    total: int = Field(ge=0)


class BudgetImpactModelListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[BudgetImpactModel] = Field(default_factory=list)
    total: int = Field(ge=0)


class ValueDossierListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ValueDossier] = Field(default_factory=list)
    total: int = Field(ge=0)


class PayerEvidenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PayerEvidence] = Field(default_factory=list)
    total: int = Field(ge=0)


class HEORMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_studies: int = Field(ge=0)
    studies_by_type: dict[str, int] = Field(default_factory=dict)
    studies_by_status: dict[str, int] = Field(default_factory=dict)
    total_ce_results: int = Field(ge=0)
    results_by_model: dict[str, int] = Field(default_factory=dict)
    cost_effective_count: int = Field(ge=0)
    total_budget_models: int = Field(ge=0)
    total_dossiers: int = Field(ge=0)
    dossiers_by_status: dict[str, int] = Field(default_factory=dict)
    total_payer_submissions: int = Field(ge=0)
    payer_by_type: dict[str, int] = Field(default_factory=dict)
    avg_icer: float | None = None
