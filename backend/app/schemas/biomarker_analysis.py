"""Pydantic schemas for Biomarker Analysis & Real-World Evidence (VP-DS-9).

Pharma-grade biomarker management and real-world evidence (RWE) platform
for clinical trial patient recruitment.  Supports biomarker discovery,
validation, panel management, patient stratification, RWE study design,
propensity score matching, and RWE-RCT comparability assessment.
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BiomarkerType(str, Enum):
    """Classification of biomarker modality."""

    GENOMIC = "GENOMIC"
    PROTEOMIC = "PROTEOMIC"
    METABOLOMIC = "METABOLOMIC"
    IMAGING = "IMAGING"
    CLINICAL_MEASUREMENT = "CLINICAL_MEASUREMENT"
    COMPOSITE = "COMPOSITE"


class BiomarkerRole(str, Enum):
    """Functional role of the biomarker in clinical context."""

    PROGNOSTIC = "PROGNOSTIC"
    PREDICTIVE = "PREDICTIVE"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACODYNAMIC = "PHARMACODYNAMIC"
    SAFETY = "SAFETY"
    SURROGATE_ENDPOINT = "SURROGATE_ENDPOINT"


class EvidenceLevel(str, Enum):
    """Oxford CEBM evidence level classification."""

    LEVEL_1A = "LEVEL_1A"
    LEVEL_1B = "LEVEL_1B"
    LEVEL_2A = "LEVEL_2A"
    LEVEL_2B = "LEVEL_2B"
    LEVEL_3 = "LEVEL_3"
    LEVEL_4 = "LEVEL_4"
    LEVEL_5 = "LEVEL_5"


class RWEStudyType(str, Enum):
    """Real-world evidence study design classification."""

    RETROSPECTIVE_COHORT = "RETROSPECTIVE_COHORT"
    PROSPECTIVE_COHORT = "PROSPECTIVE_COHORT"
    CASE_CONTROL = "CASE_CONTROL"
    CROSS_SECTIONAL = "CROSS_SECTIONAL"
    TARGET_TRIAL_EMULATION = "TARGET_TRIAL_EMULATION"


class MatchingMethod(str, Enum):
    """Statistical matching method for causal inference."""

    PROPENSITY_SCORE = "PROPENSITY_SCORE"
    EXACT = "EXACT"
    COARSENED_EXACT = "COARSENED_EXACT"
    INVERSE_PROBABILITY_WEIGHTING = "INVERSE_PROBABILITY_WEIGHTING"
    MAHALANOBIS = "MAHALANOBIS"


class BiomarkerStatus(str, Enum):
    """Lifecycle status of a biomarker."""

    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    QUALIFIED = "QUALIFIED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class Biomarker(BaseModel):
    """A clinical biomarker with performance characteristics."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    biomarker_type: BiomarkerType
    role: BiomarkerRole
    description: str = ""
    gene_symbol: Optional[str] = None
    protein_target: Optional[str] = None
    measurement_unit: Optional[str] = None
    normal_range_low: Optional[float] = None
    normal_range_high: Optional[float] = None
    clinical_significance: str = ""
    evidence_level: EvidenceLevel = EvidenceLevel.LEVEL_3
    status: BiomarkerStatus = BiomarkerStatus.DISCOVERED
    associated_conditions: list[str] = Field(default_factory=list)
    associated_trials: list[str] = Field(default_factory=list)
    sensitivity: Optional[float] = None
    specificity: Optional[float] = None
    auc_roc: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BiomarkerAssociation(BaseModel):
    """Statistical association between a biomarker and a clinical condition."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    biomarker_id: str
    condition: str
    effect_size: float
    p_value: float
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    sample_size: int = 0
    study_reference: str = ""
    population: str = ""


class PatientBiomarkerValue(BaseModel):
    """A measured biomarker value for a specific patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    biomarker_id: str
    value: float
    measurement_date: DateType
    source: str = ""
    is_abnormal: bool = False


class BiomarkerPanel(BaseModel):
    """A panel of biomarkers for composite assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str = ""
    biomarkers: list[str] = Field(default_factory=list)
    target_condition: str = ""
    panel_sensitivity: Optional[float] = None
    panel_specificity: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RWEStudy(BaseModel):
    """A real-world evidence study with design parameters and results."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    study_type: RWEStudyType
    description: str = ""
    data_source: str = ""
    sample_size: int = 0
    study_period_start: Optional[DateType] = None
    study_period_end: Optional[DateType] = None
    primary_endpoint: str = ""
    matching_method: Optional[MatchingMethod] = None
    covariates: list[str] = Field(default_factory=list)
    results_summary: str = ""
    treatment_effect: Optional[float] = None
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    p_value: Optional[float] = None
    bias_assessment: str = ""
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "ACTIVE"


class PropensityScoreResult(BaseModel):
    """Results from a propensity score matching analysis."""

    model_config = ConfigDict(from_attributes=True)

    treatment_group_size: int = 0
    control_group_size: int = 0
    matched_pairs: int = 0
    balance_metrics: dict[str, float] = Field(default_factory=dict)
    ate: Optional[float] = None
    att: Optional[float] = None
    standardized_mean_differences: dict[str, float] = Field(default_factory=dict)


class RWEComparability(BaseModel):
    """Comparison between an RWE study and a corresponding RCT."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    rwe_study_id: str
    rct_reference: str
    endpoint_comparison: str = ""
    rwe_effect_size: float = 0.0
    rct_effect_size: float = 0.0
    agreement_score: float = 0.0
    assessment_notes: str = ""


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BiomarkerCreateRequest(BaseModel):
    """Request to create a new biomarker."""

    name: str
    biomarker_type: BiomarkerType
    role: BiomarkerRole
    description: str = ""
    gene_symbol: Optional[str] = None
    protein_target: Optional[str] = None
    measurement_unit: Optional[str] = None
    normal_range_low: Optional[float] = None
    normal_range_high: Optional[float] = None
    clinical_significance: str = ""
    evidence_level: EvidenceLevel = EvidenceLevel.LEVEL_3
    associated_conditions: list[str] = Field(default_factory=list)
    associated_trials: list[str] = Field(default_factory=list)
    sensitivity: Optional[float] = None
    specificity: Optional[float] = None
    auc_roc: Optional[float] = None


class BiomarkerListResponse(BaseModel):
    """Paginated list of biomarkers."""

    items: list[Biomarker]
    total: int


class AssociationCreateRequest(BaseModel):
    """Request to create a biomarker-condition association."""

    biomarker_id: str
    condition: str
    effect_size: float
    p_value: float
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    sample_size: int = 0
    study_reference: str = ""
    population: str = ""


class PatientBiomarkerRequest(BaseModel):
    """Request to record a patient biomarker measurement."""

    patient_id: str
    biomarker_id: str
    value: float
    measurement_date: Optional[DateType] = None
    source: str = ""


class PanelCreateRequest(BaseModel):
    """Request to create a biomarker panel."""

    name: str
    description: str = ""
    biomarkers: list[str] = Field(default_factory=list)
    target_condition: str = ""


class RWEStudyCreateRequest(BaseModel):
    """Request to create a real-world evidence study."""

    title: str
    study_type: RWEStudyType
    description: str = ""
    data_source: str = ""
    sample_size: int = 0
    study_period_start: Optional[DateType] = None
    study_period_end: Optional[DateType] = None
    primary_endpoint: str = ""
    matching_method: Optional[MatchingMethod] = None
    covariates: list[str] = Field(default_factory=list)


class RWEStudyListResponse(BaseModel):
    """Paginated list of RWE studies."""

    items: list[RWEStudy]
    total: int


class ComparabilityCreateRequest(BaseModel):
    """Request to create an RWE-RCT comparability assessment."""

    rwe_study_id: str
    rct_reference: str
    endpoint_comparison: str = ""
    rwe_effect_size: float = 0.0
    rct_effect_size: float = 0.0
    assessment_notes: str = ""


class BiomarkerMetrics(BaseModel):
    """Aggregate metrics across biomarker discovery pipeline."""

    total_biomarkers: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_role: dict[str, int] = Field(default_factory=dict)
    avg_sensitivity: Optional[float] = None
    avg_specificity: Optional[float] = None
    avg_auc_roc: Optional[float] = None
    total_associations: int = 0
    total_panels: int = 0
    total_patient_values: int = 0


class RWEMetrics(BaseModel):
    """Aggregate metrics across RWE studies."""

    total_studies: int = 0
    by_study_type: dict[str, int] = Field(default_factory=dict)
    by_matching_method: dict[str, int] = Field(default_factory=dict)
    avg_sample_size: float = 0.0
    avg_effect_size: Optional[float] = None
    total_comparability_assessments: int = 0
    avg_agreement_score: Optional[float] = None
    completed_studies: int = 0


class BiomarkerStratificationResult(BaseModel):
    """Result of stratifying patients by a biomarker value."""

    biomarker_id: str
    biomarker_name: str
    threshold: float
    above_threshold: list[str] = Field(default_factory=list)
    below_threshold: list[str] = Field(default_factory=list)
    above_count: int = 0
    below_count: int = 0
    above_mean: Optional[float] = None
    below_mean: Optional[float] = None


class EnrichmentResult(BaseModel):
    """Result of biomarker enrichment analysis for trial success prediction."""

    biomarker_id: str
    biomarker_name: str
    enrichment_score: float = 0.0
    predictive_value: float = 0.0
    recommended_threshold: Optional[float] = None
    sample_size: int = 0
    p_value: Optional[float] = None
