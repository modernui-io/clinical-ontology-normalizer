"""Pydantic schemas for Clinical Event Adjudication (CEA-ADJ).

Manages clinical event adjudication operations: event submissions, adjudicator
assignments, adjudication decisions, consensus reviews, and adjudication
metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EventCategory(str, Enum):
    CARDIOVASCULAR = "cardiovascular"
    NEUROLOGICAL = "neurological"
    HEPATIC = "hepatic"
    RENAL = "renal"
    DEATH = "death"
    OTHER_SERIOUS = "other_serious"


class EventStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ADJUDICATED = "adjudicated"
    APPEALED = "appealed"
    FINAL = "final"
    WITHDRAWN = "withdrawn"


class AdjudicatorRole(str, Enum):
    PRIMARY_REVIEWER = "primary_reviewer"
    SECONDARY_REVIEWER = "secondary_reviewer"
    TIE_BREAKER = "tie_breaker"
    CHAIR = "chair"
    SPECIALIST = "specialist"
    ALTERNATE = "alternate"


class AdjudicationDecision(str, Enum):
    CONFIRMED = "confirmed"
    RECLASSIFIED = "reclassified"
    NOT_AN_EVENT = "not_an_event"
    INSUFFICIENT_DATA = "insufficient_data"
    DEFERRED = "deferred"
    SPLIT_DECISION = "split_decision"


class ConsensusOutcome(str, Enum):
    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    TIE_BROKEN = "tie_broken"
    ESCALATED = "escalated"
    PENDING = "pending"
    NO_CONSENSUS = "no_consensus"


# --- Main entities ---

class EventSubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    event_category: EventCategory
    event_status: EventStatus = EventStatus.SUBMITTED
    event_date: datetime
    event_description: str
    source_documents_count: int = Field(ge=0, default=0)
    submitted_by: str
    submission_date: datetime
    blinded: bool = True
    priority_review: bool = False
    target_turnaround_days: int = Field(ge=0, default=14)
    notes: str | None = None
    created_at: datetime


class AdjudicatorAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    event_submission_id: str
    adjudicator_name: str
    adjudicator_role: AdjudicatorRole
    specialty: str
    assigned_date: datetime
    due_date: datetime
    completed_date: datetime | None = None
    conflict_of_interest_declared: bool = False
    conflict_details: str | None = None
    review_time_hours: float = Field(ge=0, default=0.0)
    is_active: bool = True
    notes: str | None = None
    created_at: datetime


class AdjudicationDecisionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    event_submission_id: str
    assignment_id: str
    adjudication_decision: AdjudicationDecision = AdjudicationDecision.DEFERRED
    original_classification: str
    adjudicated_classification: str | None = None
    confidence_level: float = Field(ge=0, le=100, default=0.0)
    rationale: str
    additional_data_requested: bool = False
    decision_date: datetime
    notes: str | None = None
    created_at: datetime


class ConsensusReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    event_submission_id: str
    consensus_outcome: ConsensusOutcome = ConsensusOutcome.PENDING
    reviewers_count: int = Field(ge=0, default=0)
    agreeing_count: int = Field(ge=0, default=0)
    disagreeing_count: int = Field(ge=0, default=0)
    final_classification: str | None = None
    meeting_date: datetime | None = None
    chair_name: str | None = None
    discussion_summary: str | None = None
    escalation_reason: str | None = None
    finalized_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class EventSubmissionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    event_category: EventCategory
    event_date: datetime
    event_description: str
    submitted_by: str
    submission_date: datetime


class EventSubmissionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_status: EventStatus | None = None
    source_documents_count: int | None = None
    priority_review: bool | None = None
    notes: str | None = None


class AdjudicatorAssignmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    event_submission_id: str
    adjudicator_name: str
    adjudicator_role: AdjudicatorRole
    specialty: str
    assigned_date: datetime
    due_date: datetime


class AdjudicatorAssignmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    completed_date: datetime | None = None
    conflict_of_interest_declared: bool | None = None
    conflict_details: str | None = None
    review_time_hours: float | None = None
    is_active: bool | None = None
    notes: str | None = None


class AdjudicationDecisionRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    event_submission_id: str
    assignment_id: str
    original_classification: str
    rationale: str
    decision_date: datetime
    adjudication_decision: AdjudicationDecision = AdjudicationDecision.DEFERRED


class AdjudicationDecisionRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    adjudicated_classification: str | None = None
    confidence_level: float | None = None
    additional_data_requested: bool | None = None
    notes: str | None = None


class ConsensusReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    event_submission_id: str
    reviewers_count: int = Field(ge=0, default=0)
    chair_name: str | None = None


class ConsensusReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    consensus_outcome: ConsensusOutcome | None = None
    agreeing_count: int | None = None
    disagreeing_count: int | None = None
    final_classification: str | None = None
    meeting_date: datetime | None = None
    discussion_summary: str | None = None
    finalized_date: datetime | None = None
    notes: str | None = None


# --- List responses ---

class EventSubmissionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EventSubmission] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdjudicatorAssignmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AdjudicatorAssignment] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdjudicationDecisionRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AdjudicationDecisionRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class ConsensusReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ConsensusReview] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class ClinicalEventAdjudicationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_submissions: int = Field(ge=0)
    submissions_by_category: dict[str, int] = Field(default_factory=dict)
    submissions_by_status: dict[str, int] = Field(default_factory=dict)
    total_assignments: int = Field(ge=0)
    assignments_by_role: dict[str, int] = Field(default_factory=dict)
    total_decisions: int = Field(ge=0)
    decisions_by_outcome: dict[str, int] = Field(default_factory=dict)
    avg_confidence_level: float = Field(ge=0)
    total_consensus_reviews: int = Field(ge=0)
    consensus_by_outcome: dict[str, int] = Field(default_factory=dict)
    consensus_rate: float = Field(ge=0)
