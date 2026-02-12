"""Pydantic schemas for Pharmacogenomics Management (PGx-MGT).

Manages pharmacogenomics operations: genotype-phenotype mapping, drug-gene
interaction tracking, PGx test orders, dosing recommendation generation,
variant interpretation, and pharmacogenomics operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MetabolizerStatus(str, Enum):
    ULTRA_RAPID = "ultra_rapid"
    RAPID = "rapid"
    NORMAL = "normal"
    INTERMEDIATE = "intermediate"
    POOR = "poor"
    INDETERMINATE = "indeterminate"


class VariantSignificance(str, Enum):
    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    UNCERTAIN = "uncertain_significance"
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"


class EvidenceLevel(str, Enum):
    LEVEL_1A = "1a"
    LEVEL_1B = "1b"
    LEVEL_2A = "2a"
    LEVEL_2B = "2b"
    LEVEL_3 = "3"
    LEVEL_4 = "4"


class TestStatus(str, Enum):
    ORDERED = "ordered"
    SAMPLE_COLLECTED = "sample_collected"
    IN_PROCESS = "in_process"
    RESULTED = "resulted"
    REPORTED = "reported"
    CANCELLED = "cancelled"


class RecommendationAction(str, Enum):
    STANDARD_DOSE = "standard_dose"
    DOSE_INCREASE = "dose_increase"
    DOSE_DECREASE = "dose_decrease"
    ALTERNATIVE_DRUG = "alternative_drug"
    CONTRAINDICATED = "contraindicated"
    MONITORING_REQUIRED = "monitoring_required"
    NO_ACTION = "no_action"


class DrugGeneInteraction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    drug_name: str
    gene_symbol: str
    gene_id: str | None = None
    interaction_type: str
    evidence_level: EvidenceLevel
    clinical_significance: str
    affected_metabolizer_statuses: list[str] = Field(default_factory=list)
    guideline_source: str
    guideline_id: str | None = None
    population_frequency_pct: float | None = None
    description: str
    actionable: bool = True
    last_reviewed: datetime
    created_at: datetime


class GenotypePhenotype(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    gene_symbol: str
    diplotype: str
    phenotype: str
    metabolizer_status: MetabolizerStatus
    activity_score: float | None = None
    allele_1: str
    allele_2: str
    functional_status_1: str | None = None
    functional_status_2: str | None = None
    frequency_european_pct: float | None = None
    frequency_african_pct: float | None = None
    frequency_asian_pct: float | None = None
    reference_source: str
    created_at: datetime


class PGxTestOrder(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    panel_name: str
    genes_tested: list[str] = Field(default_factory=list)
    status: TestStatus = TestStatus.ORDERED
    ordered_by: str
    ordered_date: datetime
    sample_type: str = "blood"
    sample_collected_date: datetime | None = None
    lab_name: str | None = None
    lab_accession: str | None = None
    resulted_date: datetime | None = None
    reported_date: datetime | None = None
    turnaround_days: int | None = None
    created_at: datetime


class VariantResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    test_order_id: str
    subject_id: str
    gene_symbol: str
    variant_name: str
    rs_id: str | None = None
    hgvs_coding: str | None = None
    hgvs_protein: str | None = None
    zygosity: str
    allele_frequency: float | None = None
    significance: VariantSignificance = VariantSignificance.UNCERTAIN
    diplotype: str | None = None
    phenotype: str | None = None
    metabolizer_status: MetabolizerStatus | None = None
    activity_score: float | None = None
    interpretation: str | None = None
    reviewed_by: str | None = None
    created_at: datetime


class DosingRecommendation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    drug_name: str
    gene_symbol: str
    metabolizer_status: MetabolizerStatus
    action: RecommendationAction
    standard_dose: str
    recommended_dose: str | None = None
    alternative_drug: str | None = None
    recommendation_text: str
    evidence_level: EvidenceLevel
    guideline_source: str
    variant_result_id: str | None = None
    accepted: bool | None = None
    accepted_by: str | None = None
    accepted_date: datetime | None = None
    override_reason: str | None = None
    created_at: datetime


class DrugGeneInteractionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    drug_name: str
    gene_symbol: str
    interaction_type: str
    evidence_level: EvidenceLevel
    clinical_significance: str
    guideline_source: str
    description: str
    gene_id: str | None = None
    actionable: bool = True


class DrugGeneInteractionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evidence_level: EvidenceLevel | None = None
    clinical_significance: str | None = None
    actionable: bool | None = None
    population_frequency_pct: float | None = None


class GenotypePhenotypeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gene_symbol: str
    diplotype: str
    phenotype: str
    metabolizer_status: MetabolizerStatus
    allele_1: str
    allele_2: str
    reference_source: str
    activity_score: float | None = None


class GenotypePhenotypeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    frequency_european_pct: float | None = None
    frequency_african_pct: float | None = None
    frequency_asian_pct: float | None = None
    functional_status_1: str | None = None
    functional_status_2: str | None = None


class PGxTestOrderCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    panel_name: str
    genes_tested: list[str] = Field(default_factory=list)
    ordered_by: str
    sample_type: str = "blood"
    lab_name: str | None = None


class PGxTestOrderUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: TestStatus | None = None
    lab_accession: str | None = None
    sample_collected_date: datetime | None = None


class VariantResultCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    test_order_id: str
    subject_id: str
    gene_symbol: str
    variant_name: str
    zygosity: str
    rs_id: str | None = None
    significance: VariantSignificance = VariantSignificance.UNCERTAIN
    diplotype: str | None = None
    phenotype: str | None = None
    metabolizer_status: MetabolizerStatus | None = None


class VariantResultUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    significance: VariantSignificance | None = None
    interpretation: str | None = None
    reviewed_by: str | None = None
    activity_score: float | None = None


class DosingRecommendationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    drug_name: str
    gene_symbol: str
    metabolizer_status: MetabolizerStatus
    action: RecommendationAction
    standard_dose: str
    recommendation_text: str
    evidence_level: EvidenceLevel
    guideline_source: str
    recommended_dose: str | None = None
    alternative_drug: str | None = None
    variant_result_id: str | None = None


class DosingRecommendationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    accepted: bool | None = None
    accepted_by: str | None = None
    override_reason: str | None = None


class DrugGeneInteractionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DrugGeneInteraction] = Field(default_factory=list)
    total: int = Field(ge=0)


class GenotypePhenotypeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[GenotypePhenotype] = Field(default_factory=list)
    total: int = Field(ge=0)


class PGxTestOrderListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PGxTestOrder] = Field(default_factory=list)
    total: int = Field(ge=0)


class VariantResultListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[VariantResult] = Field(default_factory=list)
    total: int = Field(ge=0)


class DosingRecommendationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DosingRecommendation] = Field(default_factory=list)
    total: int = Field(ge=0)


class PharmacogenomicsMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_interactions: int = Field(ge=0)
    actionable_interactions: int = Field(ge=0)
    interactions_by_evidence: dict[str, int] = Field(default_factory=dict)
    total_genotype_phenotypes: int = Field(ge=0)
    genotypes_by_metabolizer: dict[str, int] = Field(default_factory=dict)
    total_test_orders: int = Field(ge=0)
    orders_by_status: dict[str, int] = Field(default_factory=dict)
    avg_turnaround_days: float = Field(ge=0)
    total_variant_results: int = Field(ge=0)
    variants_by_significance: dict[str, int] = Field(default_factory=dict)
    total_recommendations: int = Field(ge=0)
    recommendations_by_action: dict[str, int] = Field(default_factory=dict)
    recommendation_acceptance_pct: float = Field(ge=0, le=100)
