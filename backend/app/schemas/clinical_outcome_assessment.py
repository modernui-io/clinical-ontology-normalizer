"""Pydantic schemas for Clinical Outcome Assessment Management (COA-MGT).

Manages clinical outcome assessments: patient-reported outcomes (PROs),
clinician-reported outcomes (ClinROs), observer-reported outcomes (ObsROs),
performance outcomes (PerfOs), assessment instrument validation, and COA
operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class COAType(str, Enum):
    PRO = "patient_reported_outcome"
    CLINRO = "clinician_reported_outcome"
    OBSRO = "observer_reported_outcome"
    PERFO = "performance_outcome"


class InstrumentStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    VALIDATED = "validated"
    REGULATORY_QUALIFIED = "regulatory_qualified"
    DEPRECATED = "deprecated"


class AssessmentFrequency(str, Enum):
    SCREENING = "screening"
    BASELINE = "baseline"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    END_OF_TREATMENT = "end_of_treatment"
    FOLLOW_UP = "follow_up"


class CompletionStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    MISSED = "missed"
    NOT_APPLICABLE = "not_applicable"


class ValidationLevel(str, Enum):
    CONTENT_VALIDITY = "content_validity"
    CONSTRUCT_VALIDITY = "construct_validity"
    CRITERION_VALIDITY = "criterion_validity"
    RELIABILITY = "reliability"
    RESPONSIVENESS = "responsiveness"
    FULL_PSYCHOMETRIC = "full_psychometric"


class COAInstrument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    instrument_name: str
    coa_type: COAType
    description: str
    version: str
    domains: list[str] = Field(default_factory=list)
    total_items: int = Field(ge=0, default=0)
    scoring_algorithm: str | None = None
    score_range_min: float | None = None
    score_range_max: float | None = None
    mcid: float | None = None
    recall_period: str | None = None
    administration_mode: str = "electronic"
    language: str = "en"
    status: InstrumentStatus = InstrumentStatus.DRAFT
    license_holder: str | None = None
    regulatory_reference: str | None = None
    created_by: str
    created_at: datetime


class COAAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    instrument_id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit: str
    frequency: AssessmentFrequency
    scheduled_date: datetime
    completed_date: datetime | None = None
    completion_status: CompletionStatus = CompletionStatus.SCHEDULED
    total_score: float | None = None
    domain_scores: dict[str, float] = Field(default_factory=dict)
    completion_time_minutes: int | None = None
    missing_items: int = Field(ge=0, default=0)
    data_quality_flag: str | None = None
    administered_by: str | None = None
    created_at: datetime


class InstrumentValidation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    instrument_id: str
    validation_level: ValidationLevel
    study_name: str
    sample_size: int = Field(ge=0, default=0)
    population: str
    cronbach_alpha: float | None = None
    test_retest_icc: float | None = None
    convergent_correlation: float | None = None
    known_groups_p_value: float | None = None
    responsiveness_es: float | None = None
    mcid_estimate: float | None = None
    mcid_method: str | None = None
    conclusion: str | None = None
    validated_by: str
    validation_date: datetime
    publication_reference: str | None = None
    created_at: datetime


class TranslationAdaptation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    instrument_id: str
    target_language: str
    target_country: str
    translation_method: str
    forward_translators: int = Field(ge=0, default=0)
    back_translators: int = Field(ge=0, default=0)
    cognitive_interviews: int = Field(ge=0, default=0)
    harmonized: bool = False
    status: str = "in_progress"
    completed_date: datetime | None = None
    certified_by: str | None = None
    created_at: datetime


class COAComplianceReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    instrument_id: str
    reporting_period_start: datetime
    reporting_period_end: datetime
    total_expected: int = Field(ge=0, default=0)
    total_completed: int = Field(ge=0, default=0)
    total_missed: int = Field(ge=0, default=0)
    compliance_pct: float = Field(ge=0, le=100, default=0)
    by_site: dict[str, float] = Field(default_factory=dict)
    by_visit: dict[str, float] = Field(default_factory=dict)
    average_completion_time_min: float | None = None
    data_quality_issues: int = Field(ge=0, default=0)
    generated_by: str
    generated_date: datetime


class COAInstrumentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    instrument_name: str
    coa_type: COAType
    description: str
    version: str
    created_by: str
    domains: list[str] = Field(default_factory=list)
    total_items: int = Field(ge=0, default=0)
    recall_period: str | None = None


class COAInstrumentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: InstrumentStatus | None = None
    scoring_algorithm: str | None = None
    score_range_min: float | None = None
    score_range_max: float | None = None
    mcid: float | None = None
    regulatory_reference: str | None = None


class COAAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instrument_id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit: str
    frequency: AssessmentFrequency
    scheduled_date: datetime


class COAAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    completion_status: CompletionStatus | None = None
    total_score: float | None = None
    domain_scores: dict[str, float] | None = None
    missing_items: int | None = None
    data_quality_flag: str | None = None


class InstrumentValidationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instrument_id: str
    validation_level: ValidationLevel
    study_name: str
    population: str
    validated_by: str
    sample_size: int = Field(ge=0, default=0)


class InstrumentValidationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cronbach_alpha: float | None = None
    test_retest_icc: float | None = None
    mcid_estimate: float | None = None
    conclusion: str | None = None
    publication_reference: str | None = None


class TranslationAdaptationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instrument_id: str
    target_language: str
    target_country: str
    translation_method: str


class TranslationAdaptationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    harmonized: bool | None = None
    cognitive_interviews: int | None = None
    certified_by: str | None = None


class COAComplianceReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    instrument_id: str
    reporting_period_start: datetime
    reporting_period_end: datetime
    generated_by: str


class COAComplianceReportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_expected: int | None = None
    total_completed: int | None = None
    total_missed: int | None = None
    compliance_pct: float | None = None


class COAInstrumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[COAInstrument] = Field(default_factory=list)
    total: int = Field(ge=0)


class COAAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[COAAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class InstrumentValidationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InstrumentValidation] = Field(default_factory=list)
    total: int = Field(ge=0)


class TranslationAdaptationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TranslationAdaptation] = Field(default_factory=list)
    total: int = Field(ge=0)


class COAComplianceReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[COAComplianceReport] = Field(default_factory=list)
    total: int = Field(ge=0)


class COAMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_instruments: int = Field(ge=0)
    instruments_by_type: dict[str, int] = Field(default_factory=dict)
    instruments_by_status: dict[str, int] = Field(default_factory=dict)
    total_assessments: int = Field(ge=0)
    assessments_by_status: dict[str, int] = Field(default_factory=dict)
    overall_compliance_pct: float = Field(ge=0, le=100)
    total_validations: int = Field(ge=0)
    validations_by_level: dict[str, int] = Field(default_factory=dict)
    total_translations: int = Field(ge=0)
    translations_completed: int = Field(ge=0)
    total_compliance_reports: int = Field(ge=0)
    avg_data_quality_issues: float = Field(ge=0)
