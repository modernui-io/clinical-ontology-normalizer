"""Pydantic schemas for Data Safety Monitoring Board (DSMB) Service (CLINICAL-3).

Manages DSMB operations: board composition, scheduled/ad-hoc/emergency meetings,
interim analyses with group-sequential stopping rules (O'Brien-Fleming, Pocock,
Lan-DeMets alpha spending), event adjudication workflows, blinded/unblinded
safety report generation, and charter governance.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DSMBRole(str, Enum):
    """Role of a DSMB member."""

    CHAIR = "CHAIR"
    BIOSTATISTICIAN = "BIOSTATISTICIAN"
    CLINICIAN = "CLINICIAN"
    ETHICIST = "ETHICIST"
    PATIENT_ADVOCATE = "PATIENT_ADVOCATE"


class MeetingType(str, Enum):
    """Type of DSMB meeting."""

    SCHEDULED = "SCHEDULED"
    AD_HOC = "AD_HOC"
    EMERGENCY = "EMERGENCY"


class ReviewOutcome(str, Enum):
    """Outcome of a DSMB review."""

    CONTINUE_UNCHANGED = "CONTINUE_UNCHANGED"
    CONTINUE_WITH_MODIFICATIONS = "CONTINUE_WITH_MODIFICATIONS"
    SUSPEND_ENROLLMENT = "SUSPEND_ENROLLMENT"
    TERMINATE_EARLY = "TERMINATE_EARLY"
    REQUEST_ADDITIONAL_DATA = "REQUEST_ADDITIONAL_DATA"


class StoppingRule(str, Enum):
    """Type of statistical stopping rule."""

    EFFICACY_BOUNDARY = "EFFICACY_BOUNDARY"
    FUTILITY_BOUNDARY = "FUTILITY_BOUNDARY"
    SAFETY_BOUNDARY = "SAFETY_BOUNDARY"
    HARM_BOUNDARY = "HARM_BOUNDARY"


class InterimAnalysisType(str, Enum):
    """Type of interim analysis."""

    SAFETY_ONLY = "SAFETY_ONLY"
    EFFICACY_FUTILITY = "EFFICACY_FUTILITY"
    COMBINED = "COMBINED"
    SAMPLE_SIZE_REESTIMATION = "SAMPLE_SIZE_REESTIMATION"


class ReportAccessLevel(str, Enum):
    """Access level for safety reports."""

    BLINDED = "BLINDED"
    UNBLINDED = "UNBLINDED"
    SUMMARY_ONLY = "SUMMARY_ONLY"


class EventAdjudicationStatus(str, Enum):
    """Status of an event adjudication."""

    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ADJUDICATED = "ADJUDICATED"
    APPEALED = "APPEALED"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class DSMBMember(BaseModel):
    """A member of the Data Safety Monitoring Board."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique member identifier")
    name: str = Field(..., description="Full name of the member")
    role: DSMBRole = Field(..., description="Role on the DSMB")
    institution: str = Field(..., description="Affiliated institution")
    specialty: str = Field(..., description="Medical or scientific specialty")
    email: str = Field(..., description="Contact email")
    conflict_of_interest_declared: bool = Field(
        default=False, description="Whether a COI has been declared"
    )
    coi_details: str | None = Field(None, description="Details of the conflict of interest")
    term_start: datetime = Field(..., description="Start date of the DSMB term")
    term_end: datetime = Field(..., description="End date of the DSMB term")
    active: bool = Field(default=True, description="Whether the member is currently active")


class DSMBMeeting(BaseModel):
    """Record of a DSMB meeting."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique meeting identifier")
    trial_id: str = Field(..., description="Trial discussed in the meeting")
    meeting_type: MeetingType = Field(..., description="Type of meeting")
    meeting_date: datetime = Field(..., description="Date and time of the meeting")
    attendees: list[str] = Field(default_factory=list, description="List of member IDs in attendance")
    agenda: list[str] = Field(default_factory=list, description="Agenda items")
    minutes_summary: str | None = Field(None, description="Summary of meeting minutes")
    outcome: ReviewOutcome | None = Field(None, description="Review outcome decision")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations from the board")
    action_items: list[str] = Field(default_factory=list, description="Action items arising from the meeting")
    next_meeting_date: datetime | None = Field(None, description="Scheduled date for the next meeting")
    created_at: datetime = Field(..., description="Record creation timestamp")


class StoppingBoundary(BaseModel):
    """A stopping boundary evaluated during interim analysis."""

    model_config = ConfigDict(from_attributes=True)

    rule_type: StoppingRule = Field(..., description="Type of stopping rule")
    boundary_value: float = Field(..., description="Critical value for the boundary")
    alpha_spent: float = Field(ge=0.0, le=1.0, description="Cumulative alpha spent at this look")
    information_fraction: float = Field(ge=0.0, le=1.0, description="Fraction of total information")
    crossed: bool = Field(default=False, description="Whether the boundary was crossed")
    method: str = Field(..., description="Statistical method used (e.g., OBF, Pocock, Lan-DeMets)")


class InterimAnalysis(BaseModel):
    """Record of an interim analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique analysis identifier")
    trial_id: str = Field(..., description="Trial being analyzed")
    analysis_type: InterimAnalysisType = Field(..., description="Type of interim analysis")
    analysis_date: datetime = Field(..., description="Date the analysis was performed")
    planned_sample_size: int = Field(ge=0, description="Planned total sample size")
    actual_sample_size: int = Field(ge=0, description="Actual sample size at this look")
    information_fraction: float = Field(ge=0.0, le=1.0, description="Information fraction at this look")
    stopping_rules_evaluated: list[StoppingBoundary] = Field(
        default_factory=list, description="Stopping rules evaluated"
    )
    boundaries_crossed: list[str] = Field(
        default_factory=list, description="Names of boundaries that were crossed"
    )
    recommendation: ReviewOutcome = Field(..., description="Analysis recommendation")
    report_access_level: ReportAccessLevel = Field(
        default=ReportAccessLevel.UNBLINDED, description="Access level of the report"
    )
    performed_by: str = Field(..., description="Analyst who performed the analysis")
    reviewed_at: datetime | None = Field(None, description="When the DSMB reviewed this analysis")
    created_at: datetime = Field(..., description="Record creation timestamp")


class EventAdjudication(BaseModel):
    """Record of an event adjudication by the DSMB."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique adjudication identifier")
    trial_id: str = Field(..., description="Trial the event belongs to")
    patient_id: str = Field(..., description="Patient who experienced the event")
    event_type: str = Field(..., description="Type of clinical event")
    event_date: datetime = Field(..., description="Date the event occurred")
    submitted_by: str = Field(..., description="Investigator who submitted the event")
    adjudicator: str | None = Field(None, description="DSMB member adjudicating the event")
    status: EventAdjudicationStatus = Field(
        default=EventAdjudicationStatus.PENDING, description="Current adjudication status"
    )
    original_classification: str = Field(..., description="Original event classification by site")
    adjudicated_classification: str | None = Field(
        None, description="Classification after adjudication"
    )
    rationale: str | None = Field(None, description="Rationale for the adjudication decision")
    adjudicated_at: datetime | None = Field(None, description="Date of adjudication decision")
    created_at: datetime = Field(..., description="Record creation timestamp")


class SafetyReport(BaseModel):
    """Aggregated safety report for DSMB review."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique report identifier")
    trial_id: str = Field(..., description="Trial the report covers")
    report_date: datetime = Field(..., description="Date the report was generated")
    report_type: str = Field(..., description="Type of safety report (e.g., periodic, ad-hoc)")
    total_enrolled: int = Field(ge=0, description="Total subjects enrolled")
    total_events: int = Field(ge=0, description="Total adverse events recorded")
    serious_events: int = Field(ge=0, description="Number of serious adverse events")
    fatal_events: int = Field(ge=0, description="Number of fatal events")
    event_rates_by_arm: dict[str, float] = Field(
        default_factory=dict, description="Event rates per treatment arm"
    )
    safety_signals: list[str] = Field(
        default_factory=list, description="Identified safety signals"
    )
    generated_by: str = Field(..., description="Person or system that generated the report")
    access_level: ReportAccessLevel = Field(
        default=ReportAccessLevel.BLINDED, description="Access level for this report"
    )


class DSMBCharter(BaseModel):
    """DSMB charter defining operational rules and procedures."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique charter identifier")
    trial_id: str = Field(..., description="Trial this charter governs")
    version: str = Field(..., description="Charter version")
    approved_date: datetime = Field(..., description="Date the charter was approved")
    review_frequency_weeks: int = Field(
        ge=1, description="How often the DSMB meets to review data (in weeks)"
    )
    stopping_rules: list[str] = Field(
        default_factory=list, description="Stopping rules defined in the charter"
    )
    reporting_requirements: list[str] = Field(
        default_factory=list, description="Required reports and their schedule"
    )
    access_policies: list[str] = Field(
        default_factory=list, description="Data access policies"
    )
    approved_by: list[str] = Field(
        default_factory=list, description="Member IDs who approved the charter"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class DSMBMemberCreate(BaseModel):
    """Request to create a new DSMB member."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Full name")
    role: DSMBRole = Field(..., description="Role on the DSMB")
    institution: str = Field(..., description="Affiliated institution")
    specialty: str = Field(..., description="Specialty")
    email: str = Field(..., description="Contact email")
    conflict_of_interest_declared: bool = Field(default=False, description="COI declared")
    coi_details: str | None = Field(None, description="COI details")
    term_start: datetime = Field(..., description="Term start date")
    term_end: datetime = Field(..., description="Term end date")


class DSMBMemberUpdate(BaseModel):
    """Request to update an existing DSMB member."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Full name")
    role: DSMBRole | None = Field(None, description="Role on the DSMB")
    institution: str | None = Field(None, description="Institution")
    specialty: str | None = Field(None, description="Specialty")
    email: str | None = Field(None, description="Contact email")
    conflict_of_interest_declared: bool | None = Field(None, description="COI declared")
    coi_details: str | None = Field(None, description="COI details")
    active: bool | None = Field(None, description="Active status")


class DSMBMeetingCreate(BaseModel):
    """Request to schedule a DSMB meeting."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    meeting_type: MeetingType = Field(..., description="Meeting type")
    meeting_date: datetime = Field(..., description="Meeting date")
    attendees: list[str] = Field(default_factory=list, description="Attendee member IDs")
    agenda: list[str] = Field(default_factory=list, description="Agenda items")


class DSMBMeetingUpdate(BaseModel):
    """Request to update meeting details (e.g., add minutes, outcome)."""

    model_config = ConfigDict(from_attributes=True)

    minutes_summary: str | None = Field(None, description="Minutes summary")
    outcome: ReviewOutcome | None = Field(None, description="Review outcome")
    recommendations: list[str] | None = Field(None, description="Recommendations")
    action_items: list[str] | None = Field(None, description="Action items")
    next_meeting_date: datetime | None = Field(None, description="Next meeting date")
    attendees: list[str] | None = Field(None, description="Updated attendees")


class InterimAnalysisCreate(BaseModel):
    """Request to create a new interim analysis."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    analysis_type: InterimAnalysisType = Field(..., description="Type of analysis")
    planned_sample_size: int = Field(ge=1, description="Planned total sample size")
    actual_sample_size: int = Field(ge=1, description="Actual sample size at this look")
    performed_by: str = Field(..., description="Analyst name")
    method: str = Field(
        default="OBF", description="Stopping boundary method (OBF, Pocock, Lan-DeMets)"
    )
    overall_alpha: float = Field(
        default=0.05, ge=0.001, le=0.5, description="Overall significance level"
    )
    number_of_looks: int = Field(
        default=3, ge=1, le=10, description="Total planned number of interim looks"
    )
    current_look: int = Field(
        default=1, ge=1, description="Current look number"
    )


class EventAdjudicationCreate(BaseModel):
    """Request to submit an event for adjudication."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    patient_id: str = Field(..., description="Patient ID")
    event_type: str = Field(..., description="Type of event")
    event_date: datetime = Field(..., description="Date of event")
    submitted_by: str = Field(..., description="Submitting investigator")
    original_classification: str = Field(..., description="Original classification")


class EventAdjudicationUpdate(BaseModel):
    """Request to update an event adjudication (assign, adjudicate, appeal)."""

    model_config = ConfigDict(from_attributes=True)

    adjudicator: str | None = Field(None, description="Assigned adjudicator")
    status: EventAdjudicationStatus | None = Field(None, description="New status")
    adjudicated_classification: str | None = Field(None, description="Adjudicated classification")
    rationale: str | None = Field(None, description="Rationale for decision")


class SafetyReportCreate(BaseModel):
    """Request to generate a safety report."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    report_type: str = Field(default="periodic", description="Report type")
    generated_by: str = Field(..., description="Person or system generating the report")
    access_level: ReportAccessLevel = Field(
        default=ReportAccessLevel.BLINDED, description="Report access level"
    )


class DSMBCharterCreate(BaseModel):
    """Request to create a DSMB charter."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    version: str = Field(..., description="Charter version")
    review_frequency_weeks: int = Field(ge=1, description="Review frequency in weeks")
    stopping_rules: list[str] = Field(default_factory=list, description="Stopping rules")
    reporting_requirements: list[str] = Field(
        default_factory=list, description="Reporting requirements"
    )
    access_policies: list[str] = Field(default_factory=list, description="Access policies")
    approved_by: list[str] = Field(default_factory=list, description="Approving member IDs")


class DSMBCharterUpdate(BaseModel):
    """Request to update a DSMB charter."""

    model_config = ConfigDict(from_attributes=True)

    version: str | None = Field(None, description="New version")
    review_frequency_weeks: int | None = Field(None, description="Updated review frequency")
    stopping_rules: list[str] | None = Field(None, description="Updated stopping rules")
    reporting_requirements: list[str] | None = Field(None, description="Updated requirements")
    access_policies: list[str] | None = Field(None, description="Updated access policies")
    approved_by: list[str] | None = Field(None, description="Updated approvers")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class DSMBMemberListResponse(BaseModel):
    """Paginated list of DSMB members."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBMember] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DSMBMeetingListResponse(BaseModel):
    """Paginated list of DSMB meetings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBMeeting] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InterimAnalysisListResponse(BaseModel):
    """List of interim analyses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InterimAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EventAdjudicationListResponse(BaseModel):
    """List of event adjudications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[EventAdjudication] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SafetyReportListResponse(BaseModel):
    """List of safety reports."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetyReport] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DSMBCharterListResponse(BaseModel):
    """List of DSMB charters."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DSMBCharter] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class DSMBMetrics(BaseModel):
    """Aggregated DSMB operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_members: int = Field(ge=0, description="Total DSMB members")
    active_members: int = Field(ge=0, description="Active members")
    total_meetings: int = Field(ge=0, description="Total meetings held")
    meetings_by_type: dict[str, int] = Field(
        default_factory=dict, description="Meeting counts by type"
    )
    total_interim_analyses: int = Field(ge=0, description="Total interim analyses performed")
    boundaries_crossed_count: int = Field(
        ge=0, description="Total number of boundary crossings across analyses"
    )
    total_adjudications: int = Field(ge=0, description="Total event adjudications")
    adjudications_by_status: dict[str, int] = Field(
        default_factory=dict, description="Adjudication counts by status"
    )
    pending_adjudications: int = Field(ge=0, description="Adjudications pending review")
    overdue_adjudications: int = Field(ge=0, description="Adjudications overdue (>30 days pending)")
    total_safety_reports: int = Field(ge=0, description="Total safety reports generated")
    total_charters: int = Field(ge=0, description="Total charters on file")
    upcoming_meetings: int = Field(ge=0, description="Meetings scheduled in the next 30 days")
    trials_with_active_monitoring: int = Field(
        ge=0, description="Number of distinct trials under active DSMB monitoring"
    )
