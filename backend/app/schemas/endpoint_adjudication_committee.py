"""Pydantic schemas for Endpoint Adjudication Committee (EAC-MGMT).

Manages endpoint adjudication committee operations: committee member
management, case review tracking, adjudication outcomes, charter
management, and blinding compliance with committee metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MemberRole(str, Enum):
    CHAIR = "chair"
    VOTING_MEMBER = "voting_member"
    ALTERNATE = "alternate"
    NON_VOTING_ADVISOR = "non_voting_advisor"
    STATISTICIAN = "statistician"
    COORDINATOR = "coordinator"


class CaseStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"
    ADJUDICATED = "adjudicated"
    DEFERRED = "deferred"
    RETURNED_FOR_INFO = "returned_for_info"
    CLOSED = "closed"


class AdjudicationOutcome(str, Enum):
    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"
    INDETERMINATE = "indeterminate"
    RECLASSIFIED = "reclassified"
    SPLIT_DECISION = "split_decision"


class CharterStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    AMENDED = "amended"
    SUPERSEDED = "superseded"


class BlindingStatus(str, Enum):
    MAINTAINED = "maintained"
    POTENTIAL_BREACH = "potential_breach"
    CONFIRMED_BREACH = "confirmed_breach"
    NOT_APPLICABLE = "not_applicable"
    UNDER_INVESTIGATION = "under_investigation"


class CommitteeMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    member_name: str
    role: MemberRole
    specialty: str
    institution: str
    is_active: bool = True
    appointment_date: datetime
    term_end_date: datetime | None = None
    conflict_of_interest_declared: bool = True
    coi_details: str | None = None
    training_completed: bool = False
    training_date: datetime | None = None
    cases_reviewed: int = Field(ge=0, default=0)
    agreement_rate_pct: float = Field(ge=0, le=100, default=0.0)
    appointed_by: str
    notes: str | None = None
    created_at: datetime


class CaseReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    case_number: str
    subject_id: str
    event_type: str
    event_date: datetime
    status: CaseStatus = CaseStatus.PENDING_REVIEW
    assigned_reviewers: list[str] = Field(default_factory=list)
    review_deadline: datetime | None = None
    source_documents_received: bool = False
    documents_adequate: bool = False
    additional_info_requested: bool = False
    meeting_id: str | None = None
    review_round: int = Field(ge=1, default=1)
    submitted_by: str
    notes: str | None = None
    created_at: datetime


class AdjudicationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    case_id: str
    outcome: AdjudicationOutcome
    adjudication_date: datetime
    original_classification: str
    final_classification: str
    votes_for: int = Field(ge=0, default=0)
    votes_against: int = Field(ge=0, default=0)
    votes_abstain: int = Field(ge=0, default=0)
    unanimous: bool = False
    dissenting_opinions: list[str] = Field(default_factory=list)
    rationale: str
    supporting_evidence: list[str] = Field(default_factory=list)
    reviewed_by_chair: bool = False
    finalized: bool = False
    adjudicated_by: str
    notes: str | None = None
    created_at: datetime


class CharterRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    version: str
    status: CharterStatus = CharterStatus.DRAFT
    effective_date: datetime | None = None
    review_date: datetime | None = None
    endpoint_definitions: list[str] = Field(default_factory=list)
    adjudication_criteria: list[str] = Field(default_factory=list)
    quorum_requirement: int = Field(ge=0, default=3)
    voting_threshold_pct: float = Field(ge=0, le=100, default=66.7)
    blinding_procedures: str | None = None
    document_requirements: list[str] = Field(default_factory=list)
    authored_by: str
    approved_by: str | None = None
    approval_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class BlindingCompliance(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    assessment_date: datetime
    blinding_status: BlindingStatus = BlindingStatus.MAINTAINED
    case_id: str | None = None
    member_id: str | None = None
    breach_type: str | None = None
    breach_description: str | None = None
    breach_source: str | None = None
    impact_assessment: str | None = None
    corrective_action: str | None = None
    reported_to_sponsor: bool = False
    reported_to_irb: bool = False
    resolution_date: datetime | None = None
    assessed_by: str
    notes: str | None = None
    created_at: datetime


class CommitteeMemberCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    member_name: str
    role: MemberRole
    specialty: str
    institution: str
    appointed_by: str


class CommitteeMemberUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    training_completed: bool | None = None
    conflict_of_interest_declared: bool | None = None
    role: MemberRole | None = None
    notes: str | None = None


class CaseReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    case_number: str
    subject_id: str
    event_type: str
    event_date: datetime
    submitted_by: str
    assigned_reviewers: list[str] = Field(default_factory=list)


class CaseReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: CaseStatus | None = None
    documents_adequate: bool | None = None
    additional_info_requested: bool | None = None
    review_round: int | None = None
    notes: str | None = None


class AdjudicationResultCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    case_id: str
    outcome: AdjudicationOutcome
    original_classification: str
    final_classification: str
    rationale: str
    adjudicated_by: str


class AdjudicationResultUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    finalized: bool | None = None
    reviewed_by_chair: bool | None = None
    votes_for: int | None = None
    votes_against: int | None = None
    notes: str | None = None


class CharterRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    version: str
    authored_by: str
    quorum_requirement: int = Field(ge=0, default=3)
    endpoint_definitions: list[str] = Field(default_factory=list)


class CharterRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: CharterStatus | None = None
    approved_by: str | None = None
    blinding_procedures: str | None = None
    voting_threshold_pct: float | None = None
    notes: str | None = None


class BlindingComplianceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    assessed_by: str
    blinding_status: BlindingStatus = BlindingStatus.MAINTAINED
    case_id: str | None = None
    member_id: str | None = None


class BlindingComplianceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    blinding_status: BlindingStatus | None = None
    corrective_action: str | None = None
    reported_to_sponsor: bool | None = None
    impact_assessment: str | None = None
    notes: str | None = None


class CommitteeMemberListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CommitteeMember] = Field(default_factory=list)
    total: int = Field(ge=0)


class CaseReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CaseReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdjudicationResultListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AdjudicationResult] = Field(default_factory=list)
    total: int = Field(ge=0)


class CharterRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CharterRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class BlindingComplianceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[BlindingCompliance] = Field(default_factory=list)
    total: int = Field(ge=0)


class EndpointAdjudicationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_members: int = Field(ge=0)
    active_members: int = Field(ge=0)
    members_by_role: dict[str, int] = Field(default_factory=dict)
    total_cases: int = Field(ge=0)
    cases_by_status: dict[str, int] = Field(default_factory=dict)
    total_adjudications: int = Field(ge=0)
    adjudications_by_outcome: dict[str, int] = Field(default_factory=dict)
    unanimous_decisions: int = Field(ge=0)
    total_charters: int = Field(ge=0)
    charters_by_status: dict[str, int] = Field(default_factory=dict)
    total_blinding_records: int = Field(ge=0)
    blinding_by_status: dict[str, int] = Field(default_factory=dict)
    confirmed_breaches: int = Field(ge=0)
