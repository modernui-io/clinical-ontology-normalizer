"""Pydantic schemas for Medical Monitor Dashboard.

Provides medical monitors with tools for safety signal review, benefit-risk
assessments, medical queries, patient case reviews, safety trend analysis,
monitor notes, and operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SignalStatus(str, Enum):
    """Lifecycle status of a safety signal."""

    DETECTED = "detected"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    ESCALATED = "escalated"
    CLOSED = "closed"


class RiskLevel(str, Enum):
    """Risk level classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ReviewPriority(str, Enum):
    """Priority level for reviews and queries."""

    ROUTINE = "routine"
    ELEVATED = "elevated"
    URGENT = "urgent"
    CRITICAL = "critical"


class QueryCategory(str, Enum):
    """Category of a medical query."""

    SAFETY = "safety"
    EFFICACY = "efficacy"
    ELIGIBILITY = "eligibility"
    PROTOCOL_COMPLIANCE = "protocol_compliance"
    DATA_CLARIFICATION = "data_clarification"


class AssessmentOutcome(str, Enum):
    """Overall outcome of a benefit-risk assessment."""

    FAVORABLE = "favorable"
    NEUTRAL = "neutral"
    UNFAVORABLE = "unfavorable"
    INSUFFICIENT_DATA = "insufficient_data"


class CaseReviewStatus(str, Enum):
    """Lifecycle status of a patient case review."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


class QueryStatus(str, Enum):
    """Lifecycle status of a medical query."""

    OPEN = "open"
    ASSIGNED = "assigned"
    RESPONDED = "responded"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TrendDirection(str, Enum):
    """Direction of a safety trend."""

    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


class NoteCategory(str, Enum):
    """Category for medical monitor notes."""

    SAFETY_REVIEW = "safety_review"
    BENEFIT_RISK = "benefit_risk"
    MEDICAL_QUERY = "medical_query"
    CASE_REVIEW = "case_review"
    GENERAL = "general"


class NoteVisibility(str, Enum):
    """Visibility level for notes."""

    PRIVATE = "private"
    TEAM = "team"
    SPONSOR = "sponsor"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SafetySignal(BaseModel):
    """A detected safety signal requiring medical monitor review."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique safety signal identifier")
    trial_id: str = Field(..., description="Trial identifier")
    signal_name: str = Field(..., description="Name of the safety signal")
    signal_type: str = Field(..., description="Type of signal (e.g., AE cluster, lab abnormality, mortality)")
    detected_date: datetime = Field(..., description="Date the signal was detected")
    source: str = Field(..., description="Source of signal detection (e.g., SMC review, automated detection)")
    description: str = Field(..., description="Detailed description of the safety signal")
    affected_patients_count: int = Field(ge=0, description="Number of patients affected")
    incidence_rate: float = Field(ge=0.0, description="Observed incidence rate per 100 patients")
    expected_rate: float = Field(ge=0.0, description="Expected background rate per 100 patients")
    risk_level: RiskLevel = Field(..., description="Assessed risk level")
    status: SignalStatus = Field(default=SignalStatus.DETECTED, description="Signal lifecycle status")
    assigned_to: str | None = Field(None, description="Medical monitor assigned for review")
    reviewed_date: datetime | None = Field(None, description="Date signal was reviewed")
    assessment_notes: str | None = Field(None, description="Notes from the medical monitor's assessment")
    action_taken: str | None = Field(None, description="Action taken in response to the signal")


class BenefitRiskAssessment(BaseModel):
    """A benefit-risk assessment for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assessment identifier")
    trial_id: str = Field(..., description="Trial identifier")
    assessment_date: datetime = Field(..., description="Date of assessment")
    assessor: str = Field(..., description="Name of the assessor")
    overall_outcome: AssessmentOutcome = Field(..., description="Overall benefit-risk outcome")
    benefit_score: float = Field(ge=0.0, le=100.0, description="Benefit score (0-100)")
    risk_score: float = Field(ge=0.0, le=100.0, description="Risk score (0-100)")
    benefit_summary: str = Field(..., description="Summary of observed benefits")
    risk_summary: str = Field(..., description="Summary of observed risks")
    data_cutoff_date: datetime = Field(..., description="Data cutoff date for the assessment")
    enrollment_at_assessment: int = Field(ge=0, description="Total enrollment at time of assessment")
    next_review_date: datetime | None = Field(None, description="Scheduled date for next review")
    recommendations: str | None = Field(None, description="Recommendations from the assessment")
    supporting_data: dict | None = Field(None, description="Supporting data references")


class MedicalQuery(BaseModel):
    """A medical query raised during clinical trial monitoring."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique query identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str | None = Field(None, description="Patient identifier, if applicable")
    category: QueryCategory = Field(..., description="Query category")
    priority: ReviewPriority = Field(default=ReviewPriority.ROUTINE, description="Query priority")
    subject: str = Field(..., description="Query subject line")
    query_text: str = Field(..., description="Full query text")
    raised_by: str = Field(..., description="Person who raised the query")
    raised_date: datetime = Field(..., description="Date the query was raised")
    assigned_to: str | None = Field(None, description="Medical monitor assigned to respond")
    response_text: str | None = Field(None, description="Response from the medical monitor")
    responded_date: datetime | None = Field(None, description="Date of response")
    status: QueryStatus = Field(default=QueryStatus.OPEN, description="Query lifecycle status")
    resolution_date: datetime | None = Field(None, description="Date the query was resolved")
    follow_up_required: bool = Field(default=False, description="Whether follow-up is required")


class PatientCaseReview(BaseModel):
    """A patient case review by the medical monitor."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique case review identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str = Field(..., description="Patient identifier")
    review_reason: str = Field(..., description="Reason for the case review")
    priority: ReviewPriority = Field(default=ReviewPriority.ROUTINE, description="Review priority")
    status: CaseReviewStatus = Field(default=CaseReviewStatus.PENDING, description="Case review status")
    reviewer: str | None = Field(None, description="Assigned reviewer")
    review_date: datetime | None = Field(None, description="Date review was conducted")
    clinical_summary: str | None = Field(None, description="Clinical summary of the patient case")
    findings: str | None = Field(None, description="Key findings from the review")
    recommendations: str | None = Field(None, description="Recommendations from the review")
    action_items: list[str] | None = Field(None, description="Action items from the review")
    follow_up_date: datetime | None = Field(None, description="Scheduled follow-up date")


class SafetyTrend(BaseModel):
    """A safety trend analysis for a specific event type."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique trend identifier")
    trial_id: str = Field(..., description="Trial identifier")
    event_type: str = Field(..., description="Type of adverse event being tracked")
    period_start: datetime = Field(..., description="Start of analysis period")
    period_end: datetime = Field(..., description="End of analysis period")
    event_count: int = Field(ge=0, description="Number of events in this period")
    rate_per_100_patients: float = Field(ge=0.0, description="Event rate per 100 patients")
    previous_period_rate: float | None = Field(None, description="Rate in the previous period")
    trend_direction: TrendDirection = Field(..., description="Direction of the trend")
    statistical_significance: bool = Field(
        default=False, description="Whether the trend is statistically significant"
    )
    notes: str | None = Field(None, description="Additional notes on the trend")


class MedicalMonitorNote(BaseModel):
    """A note created by the medical monitor."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique note identifier")
    trial_id: str = Field(..., description="Trial identifier")
    author: str = Field(..., description="Note author")
    note_date: datetime = Field(..., description="Date of the note")
    category: NoteCategory = Field(default=NoteCategory.GENERAL, description="Note category")
    subject: str = Field(..., description="Note subject line")
    content: str = Field(..., description="Note content")
    referenced_patients: list[str] | None = Field(
        None, description="Patient IDs referenced in this note"
    )
    referenced_signals: list[str] | None = Field(
        None, description="Safety signal IDs referenced in this note"
    )
    visibility: NoteVisibility = Field(
        default=NoteVisibility.TEAM, description="Note visibility level"
    )


# ---------------------------------------------------------------------------
# Create / Update models
# ---------------------------------------------------------------------------


class SafetySignalCreate(BaseModel):
    """Request to create a new safety signal."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    signal_name: str = Field(..., description="Signal name")
    signal_type: str = Field(..., description="Signal type")
    detected_date: datetime = Field(..., description="Detection date")
    source: str = Field(..., description="Detection source")
    description: str = Field(..., description="Signal description")
    affected_patients_count: int = Field(ge=0, description="Affected patients count")
    incidence_rate: float = Field(ge=0.0, description="Incidence rate")
    expected_rate: float = Field(ge=0.0, description="Expected rate")
    risk_level: RiskLevel = Field(..., description="Risk level")
    assigned_to: str | None = Field(None, description="Assigned medical monitor")


class SafetySignalUpdate(BaseModel):
    """Request to update a safety signal."""

    model_config = ConfigDict(from_attributes=True)

    signal_name: str | None = Field(None, description="Signal name")
    description: str | None = Field(None, description="Description")
    risk_level: RiskLevel | None = Field(None, description="Risk level")
    status: SignalStatus | None = Field(None, description="Status")
    assigned_to: str | None = Field(None, description="Assigned medical monitor")
    assessment_notes: str | None = Field(None, description="Assessment notes")
    action_taken: str | None = Field(None, description="Action taken")


class SignalEscalation(BaseModel):
    """Request to escalate a safety signal."""

    model_config = ConfigDict(from_attributes=True)

    reason: str = Field(..., description="Reason for escalation")
    escalated_to: str = Field(..., description="Person or committee escalated to")
    recommended_action: str | None = Field(None, description="Recommended action")


class BenefitRiskAssessmentCreate(BaseModel):
    """Request to create a benefit-risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    assessor: str = Field(..., description="Assessor name")
    overall_outcome: AssessmentOutcome = Field(..., description="Overall outcome")
    benefit_score: float = Field(ge=0.0, le=100.0, description="Benefit score")
    risk_score: float = Field(ge=0.0, le=100.0, description="Risk score")
    benefit_summary: str = Field(..., description="Benefit summary")
    risk_summary: str = Field(..., description="Risk summary")
    data_cutoff_date: datetime = Field(..., description="Data cutoff date")
    enrollment_at_assessment: int = Field(ge=0, description="Enrollment count")
    next_review_date: datetime | None = Field(None, description="Next review date")
    recommendations: str | None = Field(None, description="Recommendations")
    supporting_data: dict | None = Field(None, description="Supporting data")


class BenefitRiskAssessmentUpdate(BaseModel):
    """Request to update a benefit-risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    overall_outcome: AssessmentOutcome | None = Field(None, description="Overall outcome")
    benefit_score: float | None = Field(None, ge=0.0, le=100.0, description="Benefit score")
    risk_score: float | None = Field(None, ge=0.0, le=100.0, description="Risk score")
    benefit_summary: str | None = Field(None, description="Benefit summary")
    risk_summary: str | None = Field(None, description="Risk summary")
    next_review_date: datetime | None = Field(None, description="Next review date")
    recommendations: str | None = Field(None, description="Recommendations")
    supporting_data: dict | None = Field(None, description="Supporting data")


class MedicalQueryCreate(BaseModel):
    """Request to create a medical query."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str | None = Field(None, description="Patient identifier")
    category: QueryCategory = Field(..., description="Query category")
    priority: ReviewPriority = Field(default=ReviewPriority.ROUTINE, description="Priority")
    subject: str = Field(..., description="Query subject")
    query_text: str = Field(..., description="Query text")
    raised_by: str = Field(..., description="Person raising the query")


class MedicalQueryUpdate(BaseModel):
    """Request to update a medical query."""

    model_config = ConfigDict(from_attributes=True)

    category: QueryCategory | None = Field(None, description="Category")
    priority: ReviewPriority | None = Field(None, description="Priority")
    assigned_to: str | None = Field(None, description="Assigned medical monitor")
    status: QueryStatus | None = Field(None, description="Status")
    follow_up_required: bool | None = Field(None, description="Follow-up required")


class MedicalQueryResponse(BaseModel):
    """Request to respond to a medical query."""

    model_config = ConfigDict(from_attributes=True)

    response_text: str = Field(..., description="Response text from medical monitor")
    follow_up_required: bool = Field(default=False, description="Whether follow-up is required")


class PatientCaseReviewCreate(BaseModel):
    """Request to create a patient case review."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str = Field(..., description="Patient identifier")
    review_reason: str = Field(..., description="Reason for review")
    priority: ReviewPriority = Field(default=ReviewPriority.ROUTINE, description="Priority")
    reviewer: str | None = Field(None, description="Assigned reviewer")


class PatientCaseReviewUpdate(BaseModel):
    """Request to update a patient case review."""

    model_config = ConfigDict(from_attributes=True)

    priority: ReviewPriority | None = Field(None, description="Priority")
    status: CaseReviewStatus | None = Field(None, description="Status")
    reviewer: str | None = Field(None, description="Reviewer")
    clinical_summary: str | None = Field(None, description="Clinical summary")
    findings: str | None = Field(None, description="Findings")
    recommendations: str | None = Field(None, description="Recommendations")
    action_items: list[str] | None = Field(None, description="Action items")
    follow_up_date: datetime | None = Field(None, description="Follow-up date")


class CaseReviewCompletion(BaseModel):
    """Request to complete a patient case review."""

    model_config = ConfigDict(from_attributes=True)

    clinical_summary: str = Field(..., description="Clinical summary")
    findings: str = Field(..., description="Key findings")
    recommendations: str = Field(..., description="Recommendations")
    action_items: list[str] | None = Field(None, description="Action items")
    follow_up_date: datetime | None = Field(None, description="Follow-up date")


class MedicalMonitorNoteCreate(BaseModel):
    """Request to create a medical monitor note."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    author: str = Field(..., description="Note author")
    category: NoteCategory = Field(default=NoteCategory.GENERAL, description="Note category")
    subject: str = Field(..., description="Note subject")
    content: str = Field(..., description="Note content")
    referenced_patients: list[str] | None = Field(None, description="Referenced patient IDs")
    referenced_signals: list[str] | None = Field(None, description="Referenced signal IDs")
    visibility: NoteVisibility = Field(default=NoteVisibility.TEAM, description="Visibility")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SafetySignalListResponse(BaseModel):
    """List of safety signals."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetySignal] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class BenefitRiskAssessmentListResponse(BaseModel):
    """List of benefit-risk assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BenefitRiskAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MedicalQueryListResponse(BaseModel):
    """List of medical queries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MedicalQuery] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PatientCaseReviewListResponse(BaseModel):
    """List of patient case reviews."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientCaseReview] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SafetyTrendListResponse(BaseModel):
    """List of safety trends."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetyTrend] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MedicalMonitorNoteListResponse(BaseModel):
    """List of medical monitor notes."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MedicalMonitorNote] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class MedicalMonitorMetrics(BaseModel):
    """Aggregated medical monitor operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    open_signals: int = Field(ge=0, description="Number of open safety signals")
    pending_reviews: int = Field(ge=0, description="Number of pending case reviews")
    overdue_queries: int = Field(ge=0, description="Number of overdue medical queries")
    avg_query_resolution_days: float = Field(
        ge=0.0, description="Average query resolution time in days"
    )
    assessments_due: int = Field(ge=0, description="Number of assessments due within 30 days")
    critical_cases: int = Field(ge=0, description="Number of critical priority cases")
    active_trends: int = Field(ge=0, description="Number of active increasing trends")
