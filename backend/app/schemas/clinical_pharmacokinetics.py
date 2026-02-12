"""Pydantic schemas for Clinical Pharmacokinetics (CLIN-PK).

Manages clinical PK operations: PK study management, concentration
data tracking, compartmental modeling, drug interaction analysis,
and exposure-response assessment with PK metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PKStudyType(str, Enum):
    SINGLE_DOSE = "single_dose"
    MULTIPLE_DOSE = "multiple_dose"
    FOOD_EFFECT = "food_effect"
    DRUG_INTERACTION = "drug_interaction"
    SPECIAL_POPULATION = "special_population"
    POPULATION_PK = "population_pk"


class PKStudyStatus(str, Enum):
    PLANNED = "planned"
    SAMPLE_COLLECTION = "sample_collection"
    BIOANALYSIS = "bioanalysis"
    DATA_ANALYSIS = "data_analysis"
    REPORT_WRITING = "report_writing"
    COMPLETED = "completed"


class ModelType(str, Enum):
    ONE_COMPARTMENT = "one_compartment"
    TWO_COMPARTMENT = "two_compartment"
    THREE_COMPARTMENT = "three_compartment"
    NONCOMPARTMENTAL = "noncompartmental"
    POPULATION_MIXED_EFFECTS = "population_mixed_effects"
    PBPK = "pbpk"


class InteractionType(str, Enum):
    INHIBITOR = "inhibitor"
    INDUCER = "inducer"
    SUBSTRATE = "substrate"
    COMBINED = "combined"
    TRANSPORTER = "transporter"


class InteractionSeverity(str, Enum):
    NO_INTERACTION = "no_interaction"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CONTRAINDICATED = "contraindicated"


class PKStudy(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_name: str
    study_type: PKStudyType
    status: PKStudyStatus = PKStudyStatus.PLANNED
    drug_name: str
    dose: str
    route: str = "oral"
    subjects_planned: int = Field(ge=0, default=0)
    subjects_enrolled: int = Field(ge=0, default=0)
    sampling_timepoints: list[str] = Field(default_factory=list)
    total_samples_planned: int = Field(ge=0, default=0)
    total_samples_collected: int = Field(ge=0, default=0)
    bioanalytical_method: str | None = None
    lloq: float | None = None
    uloq: float | None = None
    start_date: datetime | None = None
    completion_date: datetime | None = None
    principal_investigator: str
    notes: str | None = None
    created_at: datetime


class ConcentrationData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str
    subject_id: str
    period: int = Field(ge=1, default=1)
    timepoint_hours: float
    nominal_time_hours: float
    concentration: float | None = None
    unit: str = "ng/mL"
    below_lloq: bool = False
    sample_quality: str = "acceptable"
    matrix: str = "plasma"
    assay_date: datetime | None = None
    reanalysis: bool = False
    flag: str | None = None
    analyzed_by: str
    notes: str | None = None
    created_at: datetime


class CompartmentalModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str
    model_name: str
    model_type: ModelType
    software: str = "NONMEM"
    objective_function_value: float | None = None
    aic: float | None = None
    bic: float | None = None
    parameters: list[dict] = Field(default_factory=list)
    covariates_tested: list[str] = Field(default_factory=list)
    significant_covariates: list[str] = Field(default_factory=list)
    goodness_of_fit_adequate: bool = False
    vpc_adequate: bool = False
    bootstrap_runs: int = Field(ge=0, default=0)
    model_qualified: bool = False
    modeler: str
    reviewer: str | None = None
    notes: str | None = None
    created_at: datetime


class DrugInteraction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str | None = None
    perpetrator_drug: str
    victim_drug: str
    interaction_type: InteractionType
    severity: InteractionSeverity = InteractionSeverity.NO_INTERACTION
    mechanism: str | None = None
    enzyme_involved: str | None = None
    auc_ratio: float | None = None
    cmax_ratio: float | None = None
    clinical_significance: str | None = None
    dose_adjustment_needed: bool = False
    recommended_adjustment: str | None = None
    in_vitro_data: bool = False
    in_vivo_data: bool = False
    assessed_by: str
    assessment_date: datetime
    notes: str | None = None
    created_at: datetime


class ExposureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_id: str | None = None
    analysis_name: str
    exposure_metric: str
    response_endpoint: str
    relationship_type: str = "linear"
    model_type: str = "logistic_regression"
    subjects_analyzed: int = Field(ge=0, default=0)
    significant_relationship: bool = False
    p_value: float | None = None
    r_squared: float | None = None
    ec50: float | None = None
    emax: float | None = None
    therapeutic_window_lower: float | None = None
    therapeutic_window_upper: float | None = None
    dose_recommendation: str | None = None
    analyzed_by: str
    analysis_date: datetime
    notes: str | None = None
    created_at: datetime


class PKStudyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_name: str
    study_type: PKStudyType
    drug_name: str
    dose: str
    principal_investigator: str
    subjects_planned: int = Field(ge=0, default=0)


class PKStudyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PKStudyStatus | None = None
    subjects_enrolled: int | None = None
    total_samples_collected: int | None = None
    bioanalytical_method: str | None = None
    notes: str | None = None


class ConcentrationDataCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_id: str
    subject_id: str
    timepoint_hours: float
    nominal_time_hours: float
    analyzed_by: str
    concentration: float | None = None
    unit: str = "ng/mL"


class ConcentrationDataUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    concentration: float | None = None
    below_lloq: bool | None = None
    sample_quality: str | None = None
    flag: str | None = None
    notes: str | None = None


class CompartmentalModelCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_id: str
    model_name: str
    model_type: ModelType
    modeler: str
    software: str = "NONMEM"


class CompartmentalModelUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    model_qualified: bool | None = None
    goodness_of_fit_adequate: bool | None = None
    vpc_adequate: bool | None = None
    reviewer: str | None = None
    notes: str | None = None


class DrugInteractionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    perpetrator_drug: str
    victim_drug: str
    interaction_type: InteractionType
    assessed_by: str
    study_id: str | None = None
    severity: InteractionSeverity = InteractionSeverity.NO_INTERACTION


class DrugInteractionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity: InteractionSeverity | None = None
    dose_adjustment_needed: bool | None = None
    recommended_adjustment: str | None = None
    auc_ratio: float | None = None
    notes: str | None = None


class ExposureResponseCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_name: str
    exposure_metric: str
    response_endpoint: str
    analyzed_by: str
    study_id: str | None = None
    subjects_analyzed: int = Field(ge=0, default=0)


class ExposureResponseUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    significant_relationship: bool | None = None
    dose_recommendation: str | None = None
    r_squared: float | None = None
    ec50: float | None = None
    notes: str | None = None


class PKStudyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PKStudy] = Field(default_factory=list)
    total: int = Field(ge=0)


class ConcentrationDataListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ConcentrationData] = Field(default_factory=list)
    total: int = Field(ge=0)


class CompartmentalModelListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CompartmentalModel] = Field(default_factory=list)
    total: int = Field(ge=0)


class DrugInteractionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DrugInteraction] = Field(default_factory=list)
    total: int = Field(ge=0)


class ExposureResponseListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ExposureResponse] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalPharmacokineticsMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_pk_studies: int = Field(ge=0)
    studies_by_type: dict[str, int] = Field(default_factory=dict)
    studies_by_status: dict[str, int] = Field(default_factory=dict)
    total_concentration_records: int = Field(ge=0)
    below_lloq_pct: float = Field(ge=0)
    total_models: int = Field(ge=0)
    models_by_type: dict[str, int] = Field(default_factory=dict)
    qualified_models: int = Field(ge=0)
    total_interactions: int = Field(ge=0)
    interactions_by_severity: dict[str, int] = Field(default_factory=dict)
    dose_adjustments_needed: int = Field(ge=0)
    total_exposure_response: int = Field(ge=0)
    significant_relationships: int = Field(ge=0)
