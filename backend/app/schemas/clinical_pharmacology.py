"""Pydantic schemas for Clinical Pharmacology Operations (CLIN-PHARM).

Manages PK/PD study definitions, pharmacokinetic sampling schedules,
bioanalytical sample tracking, dose escalation decisions, exposure-response
analyses, drug-drug interaction assessments, and pharmacology metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StudyType(str, Enum):
    PK_SINGLE_DOSE = "pk_single_dose"
    PK_MULTIPLE_DOSE = "pk_multiple_dose"
    PK_PD = "pk_pd"
    DOSE_ESCALATION = "dose_escalation"
    DOSE_FINDING = "dose_finding"
    BIOEQUIVALENCE = "bioequivalence"
    DDI = "drug_drug_interaction"
    FOOD_EFFECT = "food_effect"
    SPECIAL_POPULATION = "special_population"


class SampleMatrix(str, Enum):
    PLASMA = "plasma"
    SERUM = "serum"
    URINE = "urine"
    CSF = "csf"
    TISSUE = "tissue"
    SALIVA = "saliva"
    WHOLE_BLOOD = "whole_blood"


class SampleStatus(str, Enum):
    SCHEDULED = "scheduled"
    COLLECTED = "collected"
    IN_TRANSIT = "in_transit"
    RECEIVED_AT_LAB = "received_at_lab"
    ANALYZED = "analyzed"
    FAILED_QC = "failed_qc"
    REPORTED = "reported"


class EscalationDecision(str, Enum):
    ESCALATE = "escalate"
    MAINTAIN = "maintain"
    DE_ESCALATE = "de_escalate"
    HALT = "halt"
    EXPAND_COHORT = "expand_cohort"


class AnalysisStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    UNDER_REVIEW = "under_review"
    FINALIZED = "finalized"


class DDIRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CONTRAINDICATED = "contraindicated"


class PKStudy(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    study_type: StudyType
    title: str
    description: str
    target_analyte: str
    matrix: SampleMatrix
    dose_levels: list[str] = Field(default_factory=list)
    total_subjects: int = Field(ge=0, default=0)
    sampling_timepoints: list[str] = Field(default_factory=list)
    bioanalytical_method: str
    lloq: float | None = None
    uloq: float | None = None
    status: AnalysisStatus = AnalysisStatus.PLANNED
    principal_investigator: str
    start_date: datetime | None = None
    completion_date: datetime | None = None
    created_at: datetime


class PKSample(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    subject_id: str
    timepoint: str
    nominal_time_hours: float
    actual_time_hours: float | None = None
    matrix: SampleMatrix
    status: SampleStatus = SampleStatus.SCHEDULED
    concentration: float | None = None
    concentration_unit: str = "ng/mL"
    collection_date: datetime | None = None
    analysis_date: datetime | None = None
    qc_passed: bool | None = None
    notes: str | None = None


class DoseEscalation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    cohort_number: int = Field(ge=1)
    dose_level: str
    subjects_enrolled: int = Field(ge=0, default=0)
    subjects_evaluable: int = Field(ge=0, default=0)
    dlts_observed: int = Field(ge=0, default=0)
    dlt_descriptions: list[str] = Field(default_factory=list)
    decision: EscalationDecision | None = None
    decision_date: datetime | None = None
    decision_rationale: str | None = None
    pk_summary: str | None = None
    safety_summary: str | None = None
    decided_by: str | None = None


class ExposureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    analysis_type: str
    endpoint: str
    model_type: str
    pk_parameter: str
    correlation_coefficient: float | None = None
    p_value: float | None = None
    ec50: float | None = None
    emax: float | None = None
    therapeutic_window_low: float | None = None
    therapeutic_window_high: float | None = None
    status: AnalysisStatus = AnalysisStatus.PLANNED
    analyst: str
    analysis_date: datetime | None = None
    report_reference: str | None = None


class DDIAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    perpetrator_drug: str
    victim_drug: str
    interaction_mechanism: str
    in_vitro_result: str | None = None
    clinical_result: str | None = None
    auc_ratio: float | None = None
    cmax_ratio: float | None = None
    risk_classification: DDIRisk = DDIRisk.LOW
    recommendation: str
    assessed_by: str
    assessment_date: datetime
    references: list[str] = Field(default_factory=list)


class PKStudyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    study_type: StudyType
    title: str
    description: str
    target_analyte: str
    matrix: SampleMatrix
    dose_levels: list[str] = Field(default_factory=list)
    total_subjects: int = Field(ge=0, default=0)
    sampling_timepoints: list[str] = Field(default_factory=list)
    bioanalytical_method: str
    lloq: float | None = None
    uloq: float | None = None
    principal_investigator: str


class PKStudyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    status: AnalysisStatus | None = None
    total_subjects: int | None = None
    start_date: datetime | None = None
    completion_date: datetime | None = None


class PKSampleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: str
    subject_id: str
    timepoint: str
    nominal_time_hours: float
    matrix: SampleMatrix


class PKSampleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SampleStatus | None = None
    actual_time_hours: float | None = None
    concentration: float | None = None
    qc_passed: bool | None = None
    notes: str | None = None


class DoseEscalationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: str
    cohort_number: int = Field(ge=1)
    dose_level: str
    subjects_enrolled: int = Field(ge=0, default=0)


class DoseEscalationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subjects_evaluable: int | None = None
    dlts_observed: int | None = None
    dlt_descriptions: list[str] | None = None
    decision: EscalationDecision | None = None
    decision_rationale: str | None = None
    pk_summary: str | None = None
    safety_summary: str | None = None
    decided_by: str | None = None


class ExposureResponseCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: str
    analysis_type: str
    endpoint: str
    model_type: str
    pk_parameter: str
    analyst: str


class ExposureResponseUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AnalysisStatus | None = None
    correlation_coefficient: float | None = None
    p_value: float | None = None
    ec50: float | None = None
    emax: float | None = None
    therapeutic_window_low: float | None = None
    therapeutic_window_high: float | None = None
    report_reference: str | None = None


class DDIAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    perpetrator_drug: str
    victim_drug: str
    interaction_mechanism: str
    risk_classification: DDIRisk = DDIRisk.LOW
    recommendation: str
    assessed_by: str
    references: list[str] = Field(default_factory=list)


class DDIAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    in_vitro_result: str | None = None
    clinical_result: str | None = None
    auc_ratio: float | None = None
    cmax_ratio: float | None = None
    risk_classification: DDIRisk | None = None
    recommendation: str | None = None


class PKStudyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PKStudy] = Field(default_factory=list)
    total: int = Field(ge=0)


class PKSampleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PKSample] = Field(default_factory=list)
    total: int = Field(ge=0)


class DoseEscalationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DoseEscalation] = Field(default_factory=list)
    total: int = Field(ge=0)


class ExposureResponseListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ExposureResponse] = Field(default_factory=list)
    total: int = Field(ge=0)


class DDIAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DDIAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalPharmacologyMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_studies: int = Field(ge=0)
    studies_by_type: dict[str, int] = Field(default_factory=dict)
    studies_by_status: dict[str, int] = Field(default_factory=dict)
    total_samples: int = Field(ge=0)
    samples_by_status: dict[str, int] = Field(default_factory=dict)
    samples_analyzed: int = Field(ge=0)
    samples_failed_qc: int = Field(ge=0)
    total_escalations: int = Field(ge=0)
    escalations_by_decision: dict[str, int] = Field(default_factory=dict)
    total_exposure_analyses: int = Field(ge=0)
    total_ddi_assessments: int = Field(ge=0)
    ddi_by_risk: dict[str, int] = Field(default_factory=dict)
    avg_sample_analysis_rate: float = Field(ge=0, le=100)
