"""Pydantic schemas for Site Feasibility Management (SITE-FEAS).

Manages site feasibility operations: site assessments, investigator
qualification, patient pool analysis, capability evaluations, feasibility
surveys, and site feasibility operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AssessmentStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class FeasibilityResult(str, Enum):
    HIGHLY_FEASIBLE = "highly_feasible"
    FEASIBLE = "feasible"
    CONDITIONALLY_FEASIBLE = "conditionally_feasible"
    NOT_FEASIBLE = "not_feasible"
    PENDING = "pending"


class QualificationStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    QUALIFIED = "qualified"
    CONDITIONALLY_QUALIFIED = "conditionally_qualified"
    NOT_QUALIFIED = "not_qualified"
    DEFERRED = "deferred"


class CapabilityArea(str, Enum):
    LABORATORY = "laboratory"
    PHARMACY = "pharmacy"
    IMAGING = "imaging"
    REGULATORY = "regulatory"
    STAFF = "staff"
    FACILITIES = "facilities"
    IT_SYSTEMS = "it_systems"
    PATIENT_ACCESS = "patient_access"


class SiteAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    site_name: str
    country: str
    region: str | None = None
    assessment_date: datetime
    status: AssessmentStatus = AssessmentStatus.PLANNED
    result: FeasibilityResult = FeasibilityResult.PENDING
    overall_score: float = Field(ge=0, le=100, default=0.0)
    enrollment_potential: int = Field(ge=0, default=0)
    competitive_trials: int = Field(ge=0, default=0)
    estimated_activation_weeks: int = Field(ge=0, default=0)
    irb_type: str | None = None
    previous_trial_experience: int = Field(ge=0, default=0)
    therapeutic_area_experience: bool = False
    assessor: str
    comments: str | None = None
    created_at: datetime


class InvestigatorQualification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    investigator_name: str
    medical_license_number: str | None = None
    specialty: str
    years_experience: int = Field(ge=0, default=0)
    gcp_certified: bool = False
    gcp_expiry_date: datetime | None = None
    cv_on_file: bool = False
    financial_disclosure_complete: bool = False
    previous_studies_count: int = Field(ge=0, default=0)
    enrollment_track_record: float | None = None
    qualification_status: QualificationStatus = QualificationStatus.PENDING_REVIEW
    debarment_checked: bool = False
    sanctions_checked: bool = False
    reviewed_by: str | None = None
    review_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class PatientPoolAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    analysis_date: datetime
    indication: str
    estimated_prevalence: int = Field(ge=0, default=0)
    estimated_eligible: int = Field(ge=0, default=0)
    screen_failure_rate_pct: float = Field(ge=0, le=100, default=30.0)
    expected_enrollment: int = Field(ge=0, default=0)
    enrollment_rate_per_month: float = Field(ge=0, default=0.0)
    data_source: str = "medical_records"
    competing_study_impact_pct: float = Field(ge=0, le=100, default=0.0)
    seasonal_variation: bool = False
    referral_network_available: bool = False
    patient_database_size: int = Field(ge=0, default=0)
    analyst: str
    methodology_notes: str | None = None
    created_at: datetime


class CapabilityEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    capability_area: CapabilityArea
    evaluation_date: datetime
    score: float = Field(ge=0, le=100, default=0.0)
    meets_requirements: bool = False
    gap_description: str | None = None
    remediation_plan: str | None = None
    remediation_timeline_weeks: int | None = None
    equipment_available: bool = True
    staff_trained: bool = True
    certification_current: bool = True
    evaluator: str
    notes: str | None = None
    created_at: datetime


class FeasibilitySurvey(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    survey_name: str
    sent_date: datetime
    response_date: datetime | None = None
    respondent: str | None = None
    total_questions: int = Field(ge=0, default=0)
    answered_questions: int = Field(ge=0, default=0)
    interest_level: str | None = None
    estimated_enrollment: int | None = None
    timeline_acceptable: bool | None = None
    budget_acceptable: bool | None = None
    additional_comments: str | None = None
    follow_up_required: bool = False
    created_at: datetime


class SiteAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    site_name: str
    country: str
    assessor: str
    region: str | None = None
    enrollment_potential: int = Field(ge=0, default=0)


class SiteAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AssessmentStatus | None = None
    result: FeasibilityResult | None = None
    overall_score: float | None = None
    comments: str | None = None


class InvestigatorQualificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    investigator_name: str
    specialty: str
    years_experience: int = Field(ge=0, default=0)
    gcp_certified: bool = False


class InvestigatorQualificationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    qualification_status: QualificationStatus | None = None
    reviewed_by: str | None = None
    cv_on_file: bool | None = None
    financial_disclosure_complete: bool | None = None


class PatientPoolAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    indication: str
    analyst: str
    estimated_prevalence: int = Field(ge=0, default=0)
    estimated_eligible: int = Field(ge=0, default=0)


class PatientPoolAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    expected_enrollment: int | None = None
    enrollment_rate_per_month: float | None = None
    competing_study_impact_pct: float | None = None
    methodology_notes: str | None = None


class CapabilityEvaluationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    capability_area: CapabilityArea
    evaluator: str
    score: float = Field(ge=0, le=100, default=0.0)
    meets_requirements: bool = False


class CapabilityEvaluationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    score: float | None = None
    meets_requirements: bool | None = None
    gap_description: str | None = None
    remediation_plan: str | None = None


class FeasibilitySurveyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    survey_name: str
    total_questions: int = Field(ge=0, default=0)


class FeasibilitySurveyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    respondent: str | None = None
    interest_level: str | None = None
    estimated_enrollment: int | None = None
    follow_up_required: bool | None = None


class SiteAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class InvestigatorQualificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InvestigatorQualification] = Field(default_factory=list)
    total: int = Field(ge=0)


class PatientPoolAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PatientPoolAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class CapabilityEvaluationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CapabilityEvaluation] = Field(default_factory=list)
    total: int = Field(ge=0)


class FeasibilitySurveyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FeasibilitySurvey] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteFeasibilityMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_assessments: int = Field(ge=0)
    assessments_by_status: dict[str, int] = Field(default_factory=dict)
    assessments_by_result: dict[str, int] = Field(default_factory=dict)
    avg_feasibility_score: float = Field(ge=0)
    total_investigators: int = Field(ge=0)
    investigators_by_status: dict[str, int] = Field(default_factory=dict)
    qualified_investigators: int = Field(ge=0)
    total_pool_analyses: int = Field(ge=0)
    total_estimated_eligible: int = Field(ge=0)
    total_evaluations: int = Field(ge=0)
    evaluations_by_area: dict[str, int] = Field(default_factory=dict)
    capabilities_meeting_requirements: int = Field(ge=0)
    total_surveys: int = Field(ge=0)
    surveys_responded: int = Field(ge=0)
