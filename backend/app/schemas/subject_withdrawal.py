"""Pydantic schemas for Subject Withdrawal Management (SWD-MGT).

Manages subject withdrawal operations: withdrawal requests, withdrawal
assessments, follow-up tracking, data disposition records, and withdrawal
metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class WithdrawalReason(str, Enum):
    ADVERSE_EVENT = "adverse_event"
    LACK_OF_EFFICACY = "lack_of_efficacy"
    PROTOCOL_VIOLATION = "protocol_violation"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    LOST_TO_FOLLOW_UP = "lost_to_follow_up"
    INVESTIGATOR_DECISION = "investigator_decision"


class WithdrawalStatus(str, Enum):
    INITIATED = "initiated"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    RESCINDED = "rescinded"
    PENDING_DOCUMENTATION = "pending_documentation"


class AssessmentType(str, Enum):
    SAFETY_ASSESSMENT = "safety_assessment"
    EFFICACY_ASSESSMENT = "efficacy_assessment"
    PROTOCOL_REVIEW = "protocol_review"
    CONSENT_REVIEW = "consent_review"
    MEDICAL_EVALUATION = "medical_evaluation"
    COMPREHENSIVE = "comprehensive"


class FollowUpOutcome(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    REFUSED = "refused"
    UNABLE_TO_CONTACT = "unable_to_contact"
    DECEASED = "deceased"
    ONGOING = "ongoing"


class DataDisposition(str, Enum):
    INCLUDE_ALL = "include_all"
    INCLUDE_PARTIAL = "include_partial"
    EXCLUDE_POST_WITHDRAWAL = "exclude_post_withdrawal"
    EXCLUDE_ALL = "exclude_all"
    PER_PROTOCOL_ANALYSIS = "per_protocol_analysis"
    SENSITIVITY_ANALYSIS = "sensitivity_analysis"


# --- Main entities ---

class WithdrawalRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    withdrawal_reason: WithdrawalReason
    withdrawal_status: WithdrawalStatus = WithdrawalStatus.INITIATED
    request_date: datetime
    effective_date: datetime | None = None
    last_dose_date: datetime | None = None
    last_visit_date: datetime | None = None
    initiated_by: str
    investigator_name: str
    subject_consents_to_follow_up: bool = False
    subject_consents_to_data_use: bool = True
    irb_notification_date: datetime | None = None
    sponsor_notification_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class WithdrawalAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    withdrawal_request_id: str
    assessment_type: AssessmentType
    assessment_date: datetime
    assessor_name: str
    assessor_role: str
    clinical_findings: str
    safety_concerns_identified: bool = False
    ongoing_aes: int = Field(ge=0, default=0)
    unresolved_saes: int = Field(ge=0, default=0)
    medication_washout_required: bool = False
    washout_period_days: int = Field(ge=0, default=0)
    recommendations: str | None = None
    notes: str | None = None
    created_at: datetime


class WithdrawalFollowUp(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    withdrawal_request_id: str
    subject_id: str
    follow_up_outcome: FollowUpOutcome = FollowUpOutcome.ONGOING
    visit_number: int = Field(ge=1, default=1)
    scheduled_date: datetime
    actual_date: datetime | None = None
    contact_method: str | None = None
    contact_attempts: int = Field(ge=0, default=0)
    safety_data_collected: bool = False
    survival_status_confirmed: bool = False
    performed_by: str
    notes: str | None = None
    created_at: datetime


class DataDispositionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    withdrawal_request_id: str
    subject_id: str
    data_disposition: DataDisposition = DataDisposition.INCLUDE_ALL
    analysis_population: str
    data_cutoff_date: datetime | None = None
    visits_included: int = Field(ge=0, default=0)
    visits_excluded: int = Field(ge=0, default=0)
    rationale: str
    statistician_name: str
    approved_by: str | None = None
    approval_date: datetime | None = None
    regulatory_impact: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class WithdrawalRequestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    withdrawal_reason: WithdrawalReason
    initiated_by: str
    investigator_name: str
    request_date: datetime


class WithdrawalRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    withdrawal_status: WithdrawalStatus | None = None
    effective_date: datetime | None = None
    last_dose_date: datetime | None = None
    subject_consents_to_follow_up: bool | None = None
    subject_consents_to_data_use: bool | None = None
    irb_notification_date: datetime | None = None
    notes: str | None = None


class WithdrawalAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    withdrawal_request_id: str
    assessment_type: AssessmentType
    assessment_date: datetime
    assessor_name: str
    assessor_role: str
    clinical_findings: str


class WithdrawalAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    safety_concerns_identified: bool | None = None
    ongoing_aes: int | None = None
    unresolved_saes: int | None = None
    medication_washout_required: bool | None = None
    recommendations: str | None = None
    notes: str | None = None


class WithdrawalFollowUpCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    withdrawal_request_id: str
    subject_id: str
    scheduled_date: datetime
    performed_by: str
    visit_number: int = Field(ge=1, default=1)


class WithdrawalFollowUpUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    follow_up_outcome: FollowUpOutcome | None = None
    actual_date: datetime | None = None
    contact_attempts: int | None = None
    safety_data_collected: bool | None = None
    survival_status_confirmed: bool | None = None
    notes: str | None = None


class DataDispositionRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    withdrawal_request_id: str
    subject_id: str
    analysis_population: str
    rationale: str
    statistician_name: str
    data_disposition: DataDisposition = DataDisposition.INCLUDE_ALL


class DataDispositionRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data_cutoff_date: datetime | None = None
    visits_included: int | None = None
    visits_excluded: int | None = None
    approved_by: str | None = None
    approval_date: datetime | None = None
    regulatory_impact: str | None = None
    notes: str | None = None


# --- List responses ---

class WithdrawalRequestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[WithdrawalRequest] = Field(default_factory=list)
    total: int = Field(ge=0)


class WithdrawalAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[WithdrawalAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class WithdrawalFollowUpListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[WithdrawalFollowUp] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataDispositionRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataDispositionRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class SubjectWithdrawalMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_withdrawals: int = Field(ge=0)
    withdrawals_by_reason: dict[str, int] = Field(default_factory=dict)
    withdrawals_by_status: dict[str, int] = Field(default_factory=dict)
    withdrawal_rate: float = Field(ge=0)
    total_assessments: int = Field(ge=0)
    assessments_by_type: dict[str, int] = Field(default_factory=dict)
    safety_concern_rate: float = Field(ge=0)
    total_follow_ups: int = Field(ge=0)
    follow_ups_by_outcome: dict[str, int] = Field(default_factory=dict)
    follow_up_completion_rate: float = Field(ge=0)
    total_disposition_records: int = Field(ge=0)
    dispositions_by_type: dict[str, int] = Field(default_factory=dict)
