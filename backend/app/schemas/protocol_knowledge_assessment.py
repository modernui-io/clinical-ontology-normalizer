"""Pydantic schemas for Protocol Knowledge Assessment (PKA-ASM).

Manages protocol knowledge assessment operations: assessment questionnaires,
assessment responses, competency records, remediation plans, and assessment
metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class QuestionnaireStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    UNDER_REVIEW = "under_review"
    PILOT = "pilot"
    ARCHIVED = "archived"


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    SCENARIO_BASED = "scenario_based"
    FILL_IN_BLANK = "fill_in_blank"
    MATCHING = "matching"


class CompetencyLevel(str, Enum):
    EXPERT = "expert"
    PROFICIENT = "proficient"
    COMPETENT = "competent"
    DEVELOPING = "developing"
    NOVICE = "novice"
    NOT_ASSESSED = "not_assessed"


class RemediationStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    WAIVED = "waived"
    REASSESSED = "reassessed"


class AssessmentResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL_PASS = "conditional_pass"
    INCOMPLETE = "incomplete"
    VOIDED = "voided"
    PENDING_REVIEW = "pending_review"


# --- Main entities ---

class AssessmentQuestionnaire(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    questionnaire_title: str
    version: str
    questionnaire_status: QuestionnaireStatus = QuestionnaireStatus.DRAFT
    total_questions: int = Field(ge=0, default=0)
    passing_score_pct: float = Field(ge=0, le=100, default=80.0)
    time_limit_minutes: int = Field(ge=0, default=60)
    max_attempts: int = Field(ge=1, default=3)
    protocol_version: str | None = None
    target_roles: str | None = None
    authored_by: str
    approved_by: str | None = None
    effective_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    questionnaire_id: str
    respondent_name: str
    respondent_role: str
    site_id: str
    attempt_number: int = Field(ge=1, default=1)
    assessment_result: AssessmentResult = AssessmentResult.PENDING_REVIEW
    score_pct: float = Field(ge=0, le=100, default=0.0)
    questions_answered: int = Field(ge=0, default=0)
    correct_answers: int = Field(ge=0, default=0)
    time_taken_minutes: int = Field(ge=0, default=0)
    started_at: datetime
    completed_at: datetime | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class CompetencyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    staff_name: str
    staff_role: str
    site_id: str
    competency_level: CompetencyLevel = CompetencyLevel.NOT_ASSESSED
    latest_assessment_id: str | None = None
    latest_score_pct: float = Field(ge=0, le=100, default=0.0)
    assessments_completed: int = Field(ge=0, default=0)
    last_assessment_date: datetime | None = None
    next_reassessment_date: datetime | None = None
    certification_valid: bool = False
    certification_expiry: datetime | None = None
    approved_for_delegation: bool = False
    notes: str | None = None
    created_at: datetime


class RemediationPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    staff_name: str
    site_id: str
    assessment_response_id: str | None = None
    remediation_status: RemediationStatus = RemediationStatus.ASSIGNED
    knowledge_gaps: str
    remediation_activities: str
    assigned_by: str
    due_date: datetime
    completed_date: datetime | None = None
    reassessment_required: bool = True
    reassessment_date: datetime | None = None
    reassessment_score_pct: float | None = None
    mentor_assigned: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class AssessmentQuestionnaireCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    questionnaire_title: str
    version: str
    authored_by: str
    total_questions: int = Field(ge=0, default=0)
    passing_score_pct: float = Field(ge=0, le=100, default=80.0)


class AssessmentQuestionnaireUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    questionnaire_status: QuestionnaireStatus | None = None
    approved_by: str | None = None
    effective_date: datetime | None = None
    time_limit_minutes: int | None = None
    target_roles: str | None = None
    notes: str | None = None


class AssessmentResponseCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    questionnaire_id: str
    respondent_name: str
    respondent_role: str
    site_id: str
    started_at: datetime
    attempt_number: int = Field(ge=1, default=1)


class AssessmentResponseUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    assessment_result: AssessmentResult | None = None
    score_pct: float | None = None
    questions_answered: int | None = None
    correct_answers: int | None = None
    completed_at: datetime | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class CompetencyRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    staff_name: str
    staff_role: str
    site_id: str


class CompetencyRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competency_level: CompetencyLevel | None = None
    latest_score_pct: float | None = None
    certification_valid: bool | None = None
    certification_expiry: datetime | None = None
    approved_for_delegation: bool | None = None
    next_reassessment_date: datetime | None = None
    notes: str | None = None


class RemediationPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    staff_name: str
    site_id: str
    knowledge_gaps: str
    remediation_activities: str
    assigned_by: str
    due_date: datetime
    assessment_response_id: str | None = None


class RemediationPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    remediation_status: RemediationStatus | None = None
    completed_date: datetime | None = None
    reassessment_date: datetime | None = None
    reassessment_score_pct: float | None = None
    mentor_assigned: str | None = None
    notes: str | None = None


# --- List responses ---

class AssessmentQuestionnaireListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AssessmentQuestionnaire] = Field(default_factory=list)
    total: int = Field(ge=0)


class AssessmentResponseListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AssessmentResponse] = Field(default_factory=list)
    total: int = Field(ge=0)


class CompetencyRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CompetencyRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class RemediationPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RemediationPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class ProtocolKnowledgeMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_questionnaires: int = Field(ge=0)
    questionnaires_by_status: dict[str, int] = Field(default_factory=dict)
    total_responses: int = Field(ge=0)
    responses_by_result: dict[str, int] = Field(default_factory=dict)
    average_score_pct: float = Field(ge=0)
    pass_rate: float = Field(ge=0)
    total_competency_records: int = Field(ge=0)
    records_by_level: dict[str, int] = Field(default_factory=dict)
    certification_rate: float = Field(ge=0)
    total_remediation_plans: int = Field(ge=0)
    plans_by_status: dict[str, int] = Field(default_factory=dict)
    remediation_completion_rate: float = Field(ge=0)
