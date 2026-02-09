"""Pydantic schemas for Electronic Patient-Reported Outcomes (ePRO) & Questionnaire Management (CLINICAL-9).

Manages validated PRO instruments (EQ-5D-5L, EORTC QLQ-C30, DLQI, NEI-VFQ-25,
PRO-CTCAE, WPAI), patient assignments, questionnaire responses with scoring,
compliance monitoring, MCID detection, and trend analysis.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QuestionType(str, Enum):
    """Type of question in a PRO instrument."""

    LIKERT = "likert"
    VISUAL_ANALOG_SCALE = "visual_analog_scale"
    NUMERIC_RATING = "numeric_rating"
    MULTIPLE_CHOICE = "multiple_choice"
    FREE_TEXT = "free_text"
    YES_NO = "yes_no"
    DATE = "date"


class InstrumentCategory(str, Enum):
    """Category of a PRO instrument."""

    QUALITY_OF_LIFE = "quality_of_life"
    SYMPTOM_SEVERITY = "symptom_severity"
    FUNCTIONAL_STATUS = "functional_status"
    SATISFACTION = "satisfaction"
    SAFETY = "safety"
    ADHERENCE = "adherence"


class ComplianceStatus(str, Enum):
    """Compliance status for a questionnaire response."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    WINDOW_MISSED = "window_missed"
    NOT_DUE = "not_due"


class ResponseWindow(str, Enum):
    """Frequency / response window for scheduled questionnaires."""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    VISIT_BASED = "visit_based"
    EVENT_TRIGGERED = "event_triggered"


class PRO_CTCAE_Grade(int, Enum):
    """PRO-CTCAE severity grade (0-4)."""

    ABSENT = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3
    VERY_SEVERE = 4


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class Question(BaseModel):
    """A single question within a PRO instrument."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique question identifier")
    instrument_id: str = Field(..., description="Parent instrument ID")
    text: str = Field(..., description="Question text")
    type: QuestionType = Field(..., description="Type of question")
    required: bool = Field(default=True, description="Whether the question is required")
    options: list[str] | None = Field(None, description="Options for multiple-choice questions")
    min_value: float | None = Field(None, description="Minimum value for numeric/VAS scales")
    max_value: float | None = Field(None, description="Maximum value for numeric/VAS scales")
    anchors: dict[str, str] | None = Field(
        None, description="Anchor labels for VAS/NRS (e.g. {'0': 'No pain', '100': 'Worst pain'})"
    )


class Instrument(BaseModel):
    """A validated PRO instrument definition."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique instrument identifier")
    name: str = Field(..., description="Full instrument name")
    abbreviation: str = Field(..., description="Short abbreviation (e.g. EQ-5D-5L)")
    category: InstrumentCategory = Field(..., description="Instrument category")
    description: str = Field(..., description="Description of the instrument")
    version: str = Field(default="1.0", description="Instrument version")
    copyright_holder: str | None = Field(None, description="Copyright holder")
    questions: list[Question] = Field(default_factory=list, description="List of questions")
    scoring_algorithm: str | None = Field(None, description="Description of the scoring algorithm")
    min_score: float | None = Field(None, description="Minimum possible total score")
    max_score: float | None = Field(None, description="Maximum possible total score")
    mcid: float | None = Field(
        None, description="Minimum Clinically Important Difference"
    )
    validated_languages: list[str] = Field(
        default_factory=lambda: ["en"], description="Languages with validated translations"
    )


class ScheduleTemplate(BaseModel):
    """Schedule template defining when questionnaires should be administered."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique schedule template identifier")
    trial_id: str = Field(..., description="Trial this schedule applies to")
    instrument_id: str = Field(..., description="Instrument to administer")
    frequency: ResponseWindow = Field(..., description="Administration frequency")
    window_before_days: int = Field(
        default=2, ge=0, description="Days before scheduled date the window opens"
    )
    window_after_days: int = Field(
        default=3, ge=0, description="Days after scheduled date the window closes"
    )
    start_visit: str | None = Field(None, description="Visit at which administration starts")
    end_visit: str | None = Field(None, description="Visit at which administration ends")


class PatientAssignment(BaseModel):
    """Assignment of a PRO instrument to a specific patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assignment identifier")
    patient_id: str = Field(..., description="Assigned patient ID")
    trial_id: str = Field(..., description="Trial ID")
    instrument_id: str = Field(..., description="Assigned instrument ID")
    schedule_template_id: str | None = Field(None, description="Linked schedule template ID")
    active: bool = Field(default=True, description="Whether the assignment is active")
    assigned_at: datetime = Field(..., description="When the assignment was created")
    language: str = Field(default="en", description="Language version assigned")


class Answer(BaseModel):
    """A single answer within a questionnaire response."""

    model_config = ConfigDict(from_attributes=True)

    question_id: str = Field(..., description="Question being answered")
    value: float | None = Field(None, description="Numeric value of the answer")
    text_value: str | None = Field(None, description="Free-text value of the answer")
    timestamp: datetime | None = Field(None, description="When the answer was recorded")


class QuestionnaireResponse(BaseModel):
    """A completed or in-progress questionnaire response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique response identifier")
    assignment_id: str = Field(..., description="Parent assignment ID")
    patient_id: str = Field(..., description="Patient who responded")
    instrument_id: str = Field(..., description="Instrument that was administered")
    started_at: datetime = Field(..., description="When the patient started the questionnaire")
    completed_at: datetime | None = Field(None, description="When the questionnaire was completed")
    answers: list[Answer] = Field(default_factory=list, description="List of answers")
    total_score: float | None = Field(None, description="Computed total score")
    compliance_status: ComplianceStatus = Field(
        default=ComplianceStatus.COMPLIANT, description="Compliance status"
    )
    window_start: datetime | None = Field(None, description="Start of the response window")
    window_end: datetime | None = Field(None, description="End of the response window")
    language: str = Field(default="en", description="Language version used")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class InstrumentCreate(BaseModel):
    """Request payload for creating a new instrument."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Full instrument name")
    abbreviation: str = Field(..., description="Short abbreviation")
    category: InstrumentCategory = Field(..., description="Instrument category")
    description: str = Field(..., description="Description")
    version: str = Field(default="1.0", description="Version")
    copyright_holder: str | None = Field(None, description="Copyright holder")
    scoring_algorithm: str | None = Field(None, description="Scoring algorithm description")
    min_score: float | None = Field(None, description="Minimum possible score")
    max_score: float | None = Field(None, description="Maximum possible score")
    mcid: float | None = Field(None, description="MCID threshold")
    validated_languages: list[str] = Field(
        default_factory=lambda: ["en"], description="Validated languages"
    )


class InstrumentUpdate(BaseModel):
    """Request payload for updating an existing instrument."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Updated name")
    description: str | None = Field(None, description="Updated description")
    version: str | None = Field(None, description="Updated version")
    scoring_algorithm: str | None = Field(None, description="Updated scoring algorithm")
    mcid: float | None = Field(None, description="Updated MCID")
    validated_languages: list[str] | None = Field(None, description="Updated languages")


class InstrumentListResponse(BaseModel):
    """Paginated list of instruments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Instrument] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ScheduleCreate(BaseModel):
    """Request payload for creating a schedule template."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    instrument_id: str = Field(..., description="Instrument ID")
    frequency: ResponseWindow = Field(..., description="Administration frequency")
    window_before_days: int = Field(default=2, ge=0, description="Window before days")
    window_after_days: int = Field(default=3, ge=0, description="Window after days")
    start_visit: str | None = Field(None, description="Start visit")
    end_visit: str | None = Field(None, description="End visit")


class ScheduleListResponse(BaseModel):
    """List of schedule templates."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ScheduleTemplate] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total schedules")


class AssignmentCreate(BaseModel):
    """Request payload for assigning an instrument to a patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    trial_id: str = Field(..., description="Trial ID")
    instrument_id: str = Field(..., description="Instrument ID")
    schedule_template_id: str | None = Field(None, description="Schedule template ID")
    language: str = Field(default="en", description="Language version")


class AssignmentListResponse(BaseModel):
    """List of patient assignments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientAssignment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total assignments")


class ResponseSubmit(BaseModel):
    """Request payload for submitting a questionnaire response."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: str = Field(..., description="Assignment ID")
    answers: list[Answer] = Field(..., description="List of answers")
    language: str = Field(default="en", description="Language version used")


class ResponseListResponse(BaseModel):
    """Paginated list of questionnaire responses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[QuestionnaireResponse] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ScoredResponse(BaseModel):
    """A scored questionnaire response with domain breakdown."""

    model_config = ConfigDict(from_attributes=True)

    response_id: str = Field(..., description="Response ID")
    instrument_id: str = Field(..., description="Instrument ID")
    instrument_name: str = Field(..., description="Instrument name")
    total_score: float | None = Field(None, description="Total score")
    domain_scores: dict[str, float] = Field(
        default_factory=dict, description="Scores per domain/subscale"
    )
    percentile: float | None = Field(None, description="Score percentile vs normative data")
    interpretation: str | None = Field(None, description="Clinical interpretation")


class ComplianceReport(BaseModel):
    """Compliance report for a patient on a specific instrument."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    instrument_id: str = Field(..., description="Instrument ID")
    instrument_name: str = Field(..., description="Instrument name")
    total_expected: int = Field(ge=0, description="Total expected responses")
    total_completed: int = Field(ge=0, description="Total completed responses")
    compliance_rate: float = Field(ge=0.0, le=1.0, description="Compliance rate (0-1)")
    missed_windows: int = Field(ge=0, description="Number of missed response windows")
    late_submissions: int = Field(ge=0, description="Number of late submissions")
    consecutive_misses: int = Field(ge=0, description="Current consecutive misses")
    alert: bool = Field(default=False, description="Whether compliance alert is triggered")


class TrialComplianceReport(BaseModel):
    """Trial-level compliance summary."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    total_patients: int = Field(ge=0, description="Total patients with assignments")
    overall_compliance_rate: float = Field(ge=0.0, le=1.0, description="Overall compliance rate")
    by_instrument: dict[str, float] = Field(
        default_factory=dict, description="Compliance rate per instrument"
    )
    patients_at_risk: int = Field(ge=0, description="Patients with 2+ consecutive misses")
    total_overdue: int = Field(ge=0, description="Total overdue responses")


class ReminderItem(BaseModel):
    """A reminder for an upcoming or overdue questionnaire."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: str = Field(..., description="Assignment ID")
    patient_id: str = Field(..., description="Patient ID")
    instrument_id: str = Field(..., description="Instrument ID")
    instrument_name: str = Field(..., description="Instrument name")
    due_date: datetime = Field(..., description="Due date")
    window_end: datetime = Field(..., description="End of response window")
    status: str = Field(..., description="upcoming or overdue")
    days_until_due: int = Field(..., description="Days until due (negative = overdue)")


class ReminderListResponse(BaseModel):
    """List of reminders."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReminderItem] = Field(default_factory=list)
    total_upcoming: int = Field(ge=0, description="Total upcoming reminders")
    total_overdue: int = Field(ge=0, description="Total overdue reminders")


class ScoreTrendPoint(BaseModel):
    """A single point in a score trend over time."""

    model_config = ConfigDict(from_attributes=True)

    response_id: str = Field(..., description="Response ID")
    date: datetime = Field(..., description="Response date")
    score: float = Field(..., description="Score at this point")
    mcid_change: float | None = Field(None, description="Change from baseline in MCID units")


class PatientScoreTrend(BaseModel):
    """Score trend for a patient on a specific instrument."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    instrument_id: str = Field(..., description="Instrument ID")
    instrument_name: str = Field(..., description="Instrument name")
    baseline_score: float | None = Field(None, description="Baseline score")
    current_score: float | None = Field(None, description="Most recent score")
    change_from_baseline: float | None = Field(None, description="Change from baseline")
    mcid_exceeded: bool = Field(default=False, description="Whether MCID has been exceeded")
    trend_direction: str = Field(default="stable", description="improving, worsening, or stable")
    data_points: list[ScoreTrendPoint] = Field(
        default_factory=list, description="Score data points over time"
    )


class MCIDAlert(BaseModel):
    """Alert when a patient's score change exceeds the MCID."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    instrument_id: str = Field(..., description="Instrument ID")
    instrument_name: str = Field(..., description="Instrument name")
    baseline_score: float = Field(..., description="Baseline score")
    current_score: float = Field(..., description="Current score")
    change: float = Field(..., description="Score change")
    mcid_threshold: float = Field(..., description="MCID threshold")
    direction: str = Field(..., description="improvement or deterioration")
    detected_at: datetime = Field(..., description="When the change was detected")


class MCIDAlertListResponse(BaseModel):
    """List of MCID alerts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MCIDAlert] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total MCID alerts")


class EPROMetrics(BaseModel):
    """ePRO dashboard metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_instruments: int = Field(ge=0, description="Total registered instruments")
    total_assignments: int = Field(ge=0, description="Total patient assignments")
    active_patients: int = Field(ge=0, description="Number of patients with active assignments")
    avg_compliance_rate: float = Field(
        ge=0.0, le=1.0, description="Average compliance rate across all patients"
    )
    completion_rate_7d: float = Field(
        ge=0.0, le=1.0, description="Completion rate in the last 7 days"
    )
    overdue_count: int = Field(ge=0, description="Number of overdue questionnaires")
    instruments_by_category: dict[str, int] = Field(
        default_factory=dict, description="Instrument count by category"
    )
    total_responses: int = Field(ge=0, description="Total submitted responses")
    mcid_alerts_active: int = Field(ge=0, description="Number of active MCID alerts")
