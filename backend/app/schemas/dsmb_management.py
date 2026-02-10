"""Pydantic schemas for DSMB (Data Safety Monitoring Board) Management.

Manages DSMB operations: charter management, member tracking, meeting lifecycle,
safety reviews with interim analysis data, DSMB recommendations with voting records,
unblinding request workflow, quorum validation, and DSMB operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MeetingType(str, Enum):
    """Type of DSMB meeting."""

    ORGANIZATIONAL = "organizational"
    SCHEDULED_REVIEW = "scheduled_review"
    AD_HOC = "ad_hoc"
    EMERGENCY = "emergency"
    FINAL = "final"


class MeetingStatus(str, Enum):
    """Status of a DSMB meeting."""

    PLANNED = "planned"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RecommendationType(str, Enum):
    """Type of DSMB recommendation."""

    CONTINUE_UNCHANGED = "continue_unchanged"
    CONTINUE_WITH_MODIFICATIONS = "continue_with_modifications"
    PAUSE_ENROLLMENT = "pause_enrollment"
    STOP_FOR_EFFICACY = "stop_for_efficacy"
    STOP_FOR_FUTILITY = "stop_for_futility"
    STOP_FOR_SAFETY = "stop_for_safety"
    REQUEST_ADDITIONAL_DATA = "request_additional_data"


class VoteOutcome(str, Enum):
    """Outcome of a DSMB vote."""

    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    SPLIT = "split"
    DEFERRED = "deferred"


class MemberRole(str, Enum):
    """Role of a DSMB member."""

    CHAIR = "chair"
    STATISTICIAN = "statistician"
    CLINICIAN = "clinician"
    ETHICIST = "ethicist"
    PATIENT_ADVOCATE = "patient_advocate"


class UnblindingScope(str, Enum):
    """Scope of an unblinding request."""

    INDIVIDUAL_PATIENT = "individual_patient"
    TREATMENT_ARM = "treatment_arm"
    FULL_STUDY = "full_study"
    INTERIM_ANALYSIS = "interim_analysis"


class UnblindingStatus(str, Enum):
    """Status of an unblinding request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class DSMBCharter(BaseModel):
    """DSMB charter defining governance, procedures, and membership criteria."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique charter identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    version: str = Field(..., description="Charter version (e.g., 1.0, 2.1)")
    effective_date: datetime = Field(..., description="Date the charter becomes effective")
    approved_date: datetime | None = Field(None, description="Date the charter was approved")
    approved_by: str | None = Field(None, description="Name of person who approved the charter")
    review_frequency: str = Field(
        ..., description="Frequency of scheduled reviews (e.g., quarterly, semi-annual)"
    )
    stopping_rules: str = Field(
        ..., description="Pre-defined statistical stopping rules for the trial"
    )
    unblinding_procedures: str = Field(
        ..., description="Procedures governing unblinding of treatment assignments"
    )
    membership_criteria: str = Field(
        ..., description="Criteria for DSMB membership selection"
    )
    conflict_of_interest_policy: str = Field(
        ..., description="Policy governing conflicts of interest for DSMB members"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class DSMBMember(BaseModel):
    """A member of a Data Safety Monitoring Board."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique member identifier")
    charter_id: str = Field(..., description="Associated charter identifier")
    name: str = Field(..., description="Full name of the DSMB member")
    role: MemberRole = Field(..., description="Role on the DSMB")
    institution: str = Field(..., description="Member's affiliated institution")
    specialty: str = Field(..., description="Medical or scientific specialty")
    email: str = Field(..., description="Contact email address")
    term_start: datetime = Field(..., description="Start date of DSMB term")
    term_end: datetime = Field(..., description="End date of DSMB term")
    active: bool = Field(default=True, description="Whether the member is currently active")
    conflict_declarations: list[str] = Field(
        default_factory=list, description="Declared conflicts of interest"
    )


class DSMBMeeting(BaseModel):
    """A DSMB meeting record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique meeting identifier")
    charter_id: str = Field(..., description="Associated charter identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    meeting_type: MeetingType = Field(..., description="Type of DSMB meeting")
    meeting_number: int = Field(..., ge=1, description="Sequential meeting number")
    scheduled_date: datetime = Field(..., description="Scheduled date of the meeting")
    actual_date: datetime | None = Field(None, description="Actual date the meeting occurred")
    status: MeetingStatus = Field(
        default=MeetingStatus.PLANNED, description="Current meeting status"
    )
    location: str = Field(..., description="Meeting location or virtual platform")
    agenda: str | None = Field(None, description="Meeting agenda")
    quorum_required: int = Field(..., ge=1, description="Minimum members required for quorum")
    quorum_met: bool | None = Field(None, description="Whether quorum was met at the meeting")
    attendees: list[str] = Field(
        default_factory=list, description="List of member IDs who attended"
    )
    open_session_minutes: str | None = Field(
        None, description="Minutes from the open session (sponsor present)"
    )
    closed_session_minutes: str | None = Field(
        None, description="Minutes from the closed session (DSMB only)"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class SafetyReview(BaseModel):
    """Safety review data presented at a DSMB meeting."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique safety review identifier")
    meeting_id: str = Field(..., description="Associated meeting identifier")
    data_cutoff_date: datetime = Field(
        ..., description="Data cutoff date for the review"
    )
    enrollment_at_review: int = Field(
        ..., ge=0, description="Total enrollment at time of review"
    )
    ae_summary: str = Field(
        ..., description="Summary of adverse events since last review"
    )
    sae_summary: str = Field(
        ..., description="Summary of serious adverse events since last review"
    )
    mortality_summary: str = Field(
        ..., description="Summary of mortality data"
    )
    efficacy_summary: str | None = Field(
        None, description="Summary of efficacy data (if available at interim)"
    )
    dmc_statistician_report: str | None = Field(
        None, description="Report from the DMC statistician"
    )
    independent_statistician_report: str | None = Field(
        None, description="Report from the independent statistician"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class DSMBRecommendation(BaseModel):
    """A recommendation made by the DSMB following a meeting."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique recommendation identifier")
    meeting_id: str = Field(..., description="Associated meeting identifier")
    recommendation_type: RecommendationType = Field(
        ..., description="Type of recommendation"
    )
    rationale: str = Field(..., description="Rationale for the recommendation")
    conditions: str | None = Field(
        None, description="Conditions attached to the recommendation"
    )
    vote_outcome: VoteOutcome = Field(..., description="Outcome of the vote")
    votes_for: int = Field(..., ge=0, description="Number of votes in favor")
    votes_against: int = Field(..., ge=0, description="Number of votes against")
    votes_abstain: int = Field(default=0, ge=0, description="Number of abstentions")
    communicated_to_sponsor: bool = Field(
        default=False, description="Whether recommendation was communicated to sponsor"
    )
    communicated_date: datetime | None = Field(
        None, description="Date recommendation was communicated to sponsor"
    )
    sponsor_response: str | None = Field(
        None, description="Sponsor's response to the recommendation"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class UnblindingRequest(BaseModel):
    """A request for unblinding treatment assignments."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique unblinding request identifier")
    meeting_id: str | None = Field(None, description="Associated meeting identifier (if any)")
    trial_id: str = Field(..., description="Associated trial identifier")
    requested_by: str = Field(..., description="Name of person requesting unblinding")
    request_date: datetime = Field(..., description="Date the request was submitted")
    justification: str = Field(..., description="Justification for the unblinding request")
    scope: UnblindingScope = Field(..., description="Scope of the unblinding")
    status: UnblindingStatus = Field(
        default=UnblindingStatus.PENDING, description="Current status of the request"
    )
    approved: bool | None = Field(None, description="Whether the request was approved")
    approved_by: str | None = Field(None, description="Name of person who approved/denied")
    approval_date: datetime | None = Field(None, description="Date of approval/denial decision")
    unblinding_date: datetime | None = Field(
        None, description="Date unblinding was performed"
    )
    results_summary: str | None = Field(
        None, description="Summary of unblinded results"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class DSMBCharterCreate(BaseModel):
    """Request to create a new DSMB charter."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    version: str = Field(..., description="Charter version")
    effective_date: datetime = Field(..., description="Effective date")
    review_frequency: str = Field(..., description="Review frequency")
    stopping_rules: str = Field(..., description="Stopping rules")
    unblinding_procedures: str = Field(..., description="Unblinding procedures")
    membership_criteria: str = Field(..., description="Membership criteria")
    conflict_of_interest_policy: str = Field(..., description="COI policy")


class DSMBCharterUpdate(BaseModel):
    """Request to update a DSMB charter."""

    model_config = ConfigDict(from_attributes=True)

    version: str | None = Field(None, description="Charter version")
    effective_date: datetime | None = Field(None, description="Effective date")
    approved_date: datetime | None = Field(None, description="Approved date")
    approved_by: str | None = Field(None, description="Approved by")
    review_frequency: str | None = Field(None, description="Review frequency")
    stopping_rules: str | None = Field(None, description="Stopping rules")
    unblinding_procedures: str | None = Field(None, description="Unblinding procedures")
    membership_criteria: str | None = Field(None, description="Membership criteria")
    conflict_of_interest_policy: str | None = Field(None, description="COI policy")


class DSMBMemberCreate(BaseModel):
    """Request to create a new DSMB member."""

    model_config = ConfigDict(from_attributes=True)

    charter_id: str = Field(..., description="Charter identifier")
    name: str = Field(..., description="Full name")
    role: MemberRole = Field(..., description="Role on DSMB")
    institution: str = Field(..., description="Institution")
    specialty: str = Field(..., description="Specialty")
    email: str = Field(..., description="Email address")
    term_start: datetime = Field(..., description="Term start date")
    term_end: datetime = Field(..., description="Term end date")
    conflict_declarations: list[str] = Field(
        default_factory=list, description="Conflict declarations"
    )


class DSMBMemberUpdate(BaseModel):
    """Request to update a DSMB member."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Full name")
    role: MemberRole | None = Field(None, description="Role on DSMB")
    institution: str | None = Field(None, description="Institution")
    specialty: str | None = Field(None, description="Specialty")
    email: str | None = Field(None, description="Email")
    term_end: datetime | None = Field(None, description="Term end date")
    active: bool | None = Field(None, description="Active status")
    conflict_declarations: list[str] | None = Field(None, description="Conflict declarations")


class DSMBMeetingCreate(BaseModel):
    """Request to schedule a DSMB meeting."""

    model_config = ConfigDict(from_attributes=True)

    charter_id: str = Field(..., description="Charter identifier")
    trial_id: str = Field(..., description="Trial identifier")
    meeting_type: MeetingType = Field(..., description="Meeting type")
    meeting_number: int = Field(..., ge=1, description="Sequential meeting number")
    scheduled_date: datetime = Field(..., description="Scheduled date")
    location: str = Field(..., description="Location or virtual platform")
    agenda: str | None = Field(None, description="Meeting agenda")
    quorum_required: int = Field(..., ge=1, description="Quorum required")


class DSMBMeetingUpdate(BaseModel):
    """Request to update a DSMB meeting."""

    model_config = ConfigDict(from_attributes=True)

    meeting_type: MeetingType | None = Field(None, description="Meeting type")
    scheduled_date: datetime | None = Field(None, description="Scheduled date")
    actual_date: datetime | None = Field(None, description="Actual date")
    status: MeetingStatus | None = Field(None, description="Meeting status")
    location: str | None = Field(None, description="Location")
    agenda: str | None = Field(None, description="Agenda")
    quorum_met: bool | None = Field(None, description="Quorum met")
    attendees: list[str] | None = Field(None, description="Attendee member IDs")
    open_session_minutes: str | None = Field(None, description="Open session minutes")
    closed_session_minutes: str | None = Field(None, description="Closed session minutes")


class SafetyReviewCreate(BaseModel):
    """Request to create a safety review for a meeting."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str = Field(..., description="Meeting identifier")
    data_cutoff_date: datetime = Field(..., description="Data cutoff date")
    enrollment_at_review: int = Field(..., ge=0, description="Enrollment at review")
    ae_summary: str = Field(..., description="AE summary")
    sae_summary: str = Field(..., description="SAE summary")
    mortality_summary: str = Field(..., description="Mortality summary")
    efficacy_summary: str | None = Field(None, description="Efficacy summary")
    dmc_statistician_report: str | None = Field(None, description="DMC statistician report")
    independent_statistician_report: str | None = Field(
        None, description="Independent statistician report"
    )


class SafetyReviewUpdate(BaseModel):
    """Request to update a safety review."""

    model_config = ConfigDict(from_attributes=True)

    data_cutoff_date: datetime | None = Field(None, description="Data cutoff date")
    enrollment_at_review: int | None = Field(None, ge=0, description="Enrollment")
    ae_summary: str | None = Field(None, description="AE summary")
    sae_summary: str | None = Field(None, description="SAE summary")
    mortality_summary: str | None = Field(None, description="Mortality summary")
    efficacy_summary: str | None = Field(None, description="Efficacy summary")
    dmc_statistician_report: str | None = Field(None, description="DMC statistician report")
    independent_statistician_report: str | None = Field(
        None, description="Independent statistician report"
    )


class DSMBRecommendationCreate(BaseModel):
    """Request to record a DSMB recommendation."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str = Field(..., description="Meeting identifier")
    recommendation_type: RecommendationType = Field(..., description="Recommendation type")
    rationale: str = Field(..., description="Rationale")
    conditions: str | None = Field(None, description="Conditions")
    vote_outcome: VoteOutcome = Field(..., description="Vote outcome")
    votes_for: int = Field(..., ge=0, description="Votes for")
    votes_against: int = Field(..., ge=0, description="Votes against")
    votes_abstain: int = Field(default=0, ge=0, description="Abstentions")


class DSMBRecommendationUpdate(BaseModel):
    """Request to update a DSMB recommendation."""

    model_config = ConfigDict(from_attributes=True)

    recommendation_type: RecommendationType | None = Field(None, description="Recommendation type")
    rationale: str | None = Field(None, description="Rationale")
    conditions: str | None = Field(None, description="Conditions")
    communicated_to_sponsor: bool | None = Field(None, description="Communicated to sponsor")
    communicated_date: datetime | None = Field(None, description="Communicated date")
    sponsor_response: str | None = Field(None, description="Sponsor response")


class UnblindingRequestCreate(BaseModel):
    """Request to create an unblinding request."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str | None = Field(None, description="Meeting identifier")
    trial_id: str = Field(..., description="Trial identifier")
    requested_by: str = Field(..., description="Requested by")
    justification: str = Field(..., description="Justification")
    scope: UnblindingScope = Field(..., description="Unblinding scope")


class UnblindingRequestUpdate(BaseModel):
    """Request to update an unblinding request."""

    model_config = ConfigDict(from_attributes=True)

    status: UnblindingStatus | None = Field(None, description="Status")
    approved: bool | None = Field(None, description="Approved")
    approved_by: str | None = Field(None, description="Approved by")
    approval_date: datetime | None = Field(None, description="Approval date")
    unblinding_date: datetime | None = Field(None, description="Unblinding date")
    results_summary: str | None = Field(None, description="Results summary")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class DSMBCharterListResponse(BaseModel):
    """List of DSMB charters."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBCharter] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DSMBMemberListResponse(BaseModel):
    """List of DSMB members."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBMember] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DSMBMeetingListResponse(BaseModel):
    """List of DSMB meetings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBMeeting] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SafetyReviewListResponse(BaseModel):
    """List of safety reviews."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetyReview] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DSMBRecommendationListResponse(BaseModel):
    """List of DSMB recommendations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBRecommendation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class UnblindingRequestListResponse(BaseModel):
    """List of unblinding requests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UnblindingRequest] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Quorum check response
# ---------------------------------------------------------------------------


class QuorumCheckResult(BaseModel):
    """Result of a quorum check for a DSMB meeting."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str = Field(..., description="Meeting identifier")
    quorum_required: int = Field(..., ge=1, description="Minimum members for quorum")
    attendees_count: int = Field(..., ge=0, description="Number of attendees present")
    quorum_met: bool = Field(..., description="Whether quorum requirement is satisfied")
    missing_roles: list[str] = Field(
        default_factory=list,
        description="Required roles not represented among attendees",
    )


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class DSMBMetrics(BaseModel):
    """Aggregated DSMB operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_charters: int = Field(ge=0, description="Total DSMB charters")
    total_members: int = Field(ge=0, description="Total DSMB members across all charters")
    active_members: int = Field(ge=0, description="Currently active DSMB members")
    total_meetings: int = Field(ge=0, description="Total meetings (all statuses)")
    completed_meetings: int = Field(ge=0, description="Completed meetings")
    planned_meetings: int = Field(ge=0, description="Planned/scheduled meetings")
    total_safety_reviews: int = Field(ge=0, description="Total safety reviews conducted")
    total_recommendations: int = Field(ge=0, description="Total recommendations made")
    recommendations_by_type: dict[str, int] = Field(
        default_factory=dict, description="Recommendation counts by type"
    )
    total_unblinding_requests: int = Field(ge=0, description="Total unblinding requests")
    pending_unblinding_requests: int = Field(
        ge=0, description="Pending unblinding requests"
    )
    recommendations_communicated: int = Field(
        ge=0, description="Recommendations communicated to sponsor"
    )
    meetings_with_quorum: int = Field(
        ge=0, description="Completed meetings where quorum was met"
    )
