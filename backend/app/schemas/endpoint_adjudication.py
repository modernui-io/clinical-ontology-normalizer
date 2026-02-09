"""Pydantic schemas for Clinical Endpoint Adjudication Committee (CEAC) Management (CLINICAL-20).

Manages endpoint adjudication operations: committee definitions, member management,
adjudication event tracking with dual-reviewer workflow, reviewer assessments with
confidence levels, consensus tracking, inter-rater agreement (Cohen's kappa),
committee meetings, blinded review workflow, and adjudication metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EndpointType(str, Enum):
    """Type of clinical endpoint being adjudicated."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPLORATORY = "exploratory"
    SAFETY = "safety"
    COMPOSITE = "composite"


class AdjudicationStatus(str, Enum):
    """Status of an adjudication event."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    ADJUDICATED = "adjudicated"
    APPEALED = "appealed"
    FINAL = "final"


class AdjudicatorRole(str, Enum):
    """Role of a committee member."""

    CHAIR = "chair"
    PRIMARY_REVIEWER = "primary_reviewer"
    SECONDARY_REVIEWER = "secondary_reviewer"
    TIEBREAKER = "tiebreaker"


class EventClassification(str, Enum):
    """Classification outcome for an adjudication event."""

    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"
    INDETERMINATE = "indeterminate"
    MISSING_DATA = "missing_data"


class BlindingStatus(str, Enum):
    """Blinding status for the adjudication committee."""

    BLINDED = "blinded"
    PARTIALLY_UNBLINDED = "partially_unblinded"
    UNBLINDED = "unblinded"


class ConfidenceLevel(str, Enum):
    """Confidence level for a reviewer assessment."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CommitteeMember(BaseModel):
    """A member of an adjudication committee."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique member identifier")
    name: str = Field(..., description="Full name of the member")
    specialty: str = Field(..., description="Medical specialty")
    institution: str = Field(..., description="Affiliated institution")
    role: AdjudicatorRole = Field(..., description="Role on the committee")
    conflict_of_interest_disclosed: bool = Field(
        default=False, description="Whether COI has been disclosed"
    )
    training_completed: bool = Field(
        default=False, description="Whether adjudication training is completed"
    )


class AdjudicationCommittee(BaseModel):
    """An endpoint adjudication committee for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique committee identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    name: str = Field(..., description="Committee name")
    charter_version: str = Field(..., description="Committee charter version")
    members: list[CommitteeMember] = Field(
        default_factory=list, description="Committee members"
    )
    blinding_status: BlindingStatus = Field(
        default=BlindingStatus.BLINDED, description="Blinding status of the committee"
    )
    meeting_frequency: str = Field(
        default="monthly", description="Frequency of committee meetings"
    )


class AdjudicationEvent(BaseModel):
    """A clinical event submitted for adjudication."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique event identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    patient_id: str = Field(..., description="Patient identifier")
    event_type: EndpointType = Field(..., description="Type of endpoint event")
    event_date: datetime = Field(..., description="Date the event occurred")
    reported_by_site: str = Field(..., description="Site that reported the event")
    source_documents: list[str] = Field(
        default_factory=list, description="List of source document references"
    )
    status: AdjudicationStatus = Field(
        default=AdjudicationStatus.PENDING, description="Current adjudication status"
    )
    assigned_reviewers: list[str] = Field(
        default_factory=list, description="IDs of assigned reviewers"
    )
    classification: EventClassification | None = Field(
        None, description="Final classification after adjudication"
    )
    classification_date: datetime | None = Field(
        None, description="Date of classification"
    )
    consensus_required: bool = Field(
        default=False, description="Whether consensus meeting is required"
    )


class ReviewerAssessment(BaseModel):
    """An individual reviewer's assessment of an adjudication event."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assessment identifier")
    event_id: str = Field(..., description="Associated adjudication event ID")
    reviewer_id: str = Field(..., description="Reviewer member ID")
    classification: EventClassification = Field(
        ..., description="Reviewer's classification"
    )
    confidence_level: ConfidenceLevel = Field(
        ..., description="Confidence level of the classification"
    )
    rationale: str = Field(..., description="Rationale for the classification")
    reviewed_date: datetime = Field(..., description="Date the review was completed")


class AdjudicationMeeting(BaseModel):
    """A committee meeting to review adjudication events."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique meeting identifier")
    committee_id: str = Field(..., description="Associated committee ID")
    meeting_date: datetime = Field(..., description="Date of the meeting")
    events_reviewed: list[str] = Field(
        default_factory=list, description="IDs of events reviewed"
    )
    events_adjudicated: int = Field(
        default=0, ge=0, description="Number of events adjudicated at the meeting"
    )
    disagreements_resolved: int = Field(
        default=0, ge=0, description="Number of disagreements resolved"
    )
    minutes_summary: str = Field(
        default="", description="Summary of meeting minutes"
    )


class AdjudicationMetrics(BaseModel):
    """Aggregated adjudication operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_events: int = Field(ge=0, description="Total adjudication events")
    events_by_status: dict[str, int] = Field(
        default_factory=dict, description="Event counts by status"
    )
    events_by_classification: dict[str, int] = Field(
        default_factory=dict, description="Event counts by classification"
    )
    inter_rater_agreement_kappa: float = Field(
        default=0.0, description="Cohen's kappa for inter-rater agreement"
    )
    avg_adjudication_days: float = Field(
        default=0.0, ge=0.0, description="Average days from event to adjudication"
    )
    disagreement_rate: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of events with reviewer disagreement"
    )
    events_pending: int = Field(ge=0, description="Number of events pending adjudication")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class CommitteeCreate(BaseModel):
    """Request to create an adjudication committee."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    name: str = Field(..., description="Committee name")
    charter_version: str = Field(..., description="Charter version")
    blinding_status: BlindingStatus = Field(
        default=BlindingStatus.BLINDED, description="Blinding status"
    )
    meeting_frequency: str = Field(
        default="monthly", description="Meeting frequency"
    )


class CommitteeUpdate(BaseModel):
    """Request to update an adjudication committee."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Committee name")
    charter_version: str | None = Field(None, description="Charter version")
    blinding_status: BlindingStatus | None = Field(None, description="Blinding status")
    meeting_frequency: str | None = Field(None, description="Meeting frequency")


class MemberCreate(BaseModel):
    """Request to add a member to a committee."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Full name")
    specialty: str = Field(..., description="Medical specialty")
    institution: str = Field(..., description="Institution")
    role: AdjudicatorRole = Field(..., description="Role")
    conflict_of_interest_disclosed: bool = Field(
        default=False, description="COI disclosed"
    )
    training_completed: bool = Field(
        default=False, description="Training completed"
    )


class MemberUpdate(BaseModel):
    """Request to update a committee member."""

    model_config = ConfigDict(from_attributes=True)

    role: AdjudicatorRole | None = Field(None, description="Role")
    conflict_of_interest_disclosed: bool | None = Field(None, description="COI disclosed")
    training_completed: bool | None = Field(None, description="Training completed")


class EventCreate(BaseModel):
    """Request to submit an adjudication event."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    patient_id: str = Field(..., description="Patient identifier")
    event_type: EndpointType = Field(..., description="Endpoint type")
    event_date: datetime = Field(..., description="Event date")
    reported_by_site: str = Field(..., description="Reporting site")
    source_documents: list[str] = Field(
        default_factory=list, description="Source document references"
    )


class EventUpdate(BaseModel):
    """Request to update an adjudication event."""

    model_config = ConfigDict(from_attributes=True)

    status: AdjudicationStatus | None = Field(None, description="Status")
    classification: EventClassification | None = Field(None, description="Classification")
    consensus_required: bool | None = Field(None, description="Consensus required")


class AssessmentCreate(BaseModel):
    """Request to submit a reviewer assessment."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(..., description="Event ID")
    reviewer_id: str = Field(..., description="Reviewer member ID")
    classification: EventClassification = Field(..., description="Classification")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence level")
    rationale: str = Field(..., description="Rationale")


class MeetingCreate(BaseModel):
    """Request to create a committee meeting."""

    model_config = ConfigDict(from_attributes=True)

    committee_id: str = Field(..., description="Committee ID")
    meeting_date: datetime = Field(..., description="Meeting date")
    events_reviewed: list[str] = Field(
        default_factory=list, description="Event IDs reviewed"
    )
    events_adjudicated: int = Field(default=0, ge=0, description="Events adjudicated")
    disagreements_resolved: int = Field(default=0, ge=0, description="Disagreements resolved")
    minutes_summary: str = Field(default="", description="Minutes summary")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class CommitteeListResponse(BaseModel):
    """List of adjudication committees."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AdjudicationCommittee] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EventListResponse(BaseModel):
    """List of adjudication events."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AdjudicationEvent] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class AssessmentListResponse(BaseModel):
    """List of reviewer assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReviewerAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MeetingListResponse(BaseModel):
    """List of adjudication meetings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AdjudicationMeeting] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MemberListResponse(BaseModel):
    """List of committee members."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CommitteeMember] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
