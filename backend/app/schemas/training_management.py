"""Pydantic schemas for Training & Competency Management (CLINICAL-13).

Manages training operations: course definitions, training assignments with
completion tracking, competency assessments, training matrix by role,
certification management with expiry tracking, and training metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TrainingType(str, Enum):
    """Type of training course."""

    GCP_ICH = "gcp_ich"
    PROTOCOL_SPECIFIC = "protocol_specific"
    SYSTEM = "system"
    SOP = "sop"
    REGULATORY = "regulatory"
    SAFETY_REPORTING = "safety_reporting"
    DATA_ENTRY = "data_entry"
    DEVICE = "device"


class CompletionStatus(str, Enum):
    """Completion status of a training assignment."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    WAIVED = "waived"


class CertificationType(str, Enum):
    """Type of professional certification."""

    GCP = "gcp"
    IATA_DANGEROUS_GOODS = "iata_dangerous_goods"
    HUMAN_SUBJECTS = "human_subjects"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    CPR_FIRST_AID = "cpr_first_aid"


class CompetencyLevel(str, Enum):
    """Competency proficiency level."""

    NOVICE = "novice"
    COMPETENT = "competent"
    PROFICIENT = "proficient"
    EXPERT = "expert"


class AssessmentResult(str, Enum):
    """Result of a competency assessment."""

    PASS = "pass"
    FAIL = "fail"
    REMEDIATION_REQUIRED = "remediation_required"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class TrainingCourse(BaseModel):
    """Definition of a training course."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique course identifier")
    title: str = Field(..., description="Course title")
    training_type: TrainingType = Field(..., description="Type of training")
    description: str = Field(..., description="Detailed course description")
    duration_hours: float = Field(..., ge=0.0, description="Duration in hours")
    passing_score: float = Field(..., ge=0.0, le=100.0, description="Minimum passing score (%)")
    version: str = Field(..., description="Course version")
    effective_date: datetime = Field(..., description="Date course became effective")
    expiry_months: int = Field(..., ge=0, description="Months until certification expires (0=never)")
    required_for_roles: list[str] = Field(default_factory=list, description="Roles that require this course")
    content_modules: list[str] = Field(default_factory=list, description="List of module titles")


class TrainingAssignment(BaseModel):
    """A training assignment linking a user to a course."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assignment identifier")
    course_id: str = Field(..., description="Associated course ID")
    user_id: str = Field(..., description="Assigned user ID")
    user_name: str = Field(..., description="User display name")
    role: str = Field(..., description="User role at time of assignment")
    site_id: str = Field(..., description="Site identifier")
    assigned_date: datetime = Field(..., description="Date assignment was created")
    due_date: datetime = Field(..., description="Completion deadline")
    completion_date: datetime | None = Field(None, description="Date training was completed")
    status: CompletionStatus = Field(
        default=CompletionStatus.NOT_STARTED, description="Assignment status"
    )
    score: float | None = Field(None, ge=0.0, le=100.0, description="Score achieved (%)")
    attempts: int = Field(default=0, ge=0, description="Number of attempts")
    certificate_id: str | None = Field(None, description="Issued certificate ID")


class CompetencyAssessment(BaseModel):
    """A competency assessment record for a user."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assessment identifier")
    user_id: str = Field(..., description="Assessed user ID")
    skill_area: str = Field(..., description="Skill area assessed")
    current_level: CompetencyLevel = Field(..., description="Current competency level")
    assessed_date: datetime = Field(..., description="Date of assessment")
    assessor: str = Field(..., description="Name of assessor")
    next_assessment_date: datetime = Field(..., description="Next scheduled assessment date")
    evidence: list[str] = Field(default_factory=list, description="Evidence supporting the assessment")


class TrainingMatrix(BaseModel):
    """Training matrix entry for a role."""

    model_config = ConfigDict(from_attributes=True)

    role: str = Field(..., description="Role name")
    required_courses: list[str] = Field(default_factory=list, description="Required course IDs")
    optional_courses: list[str] = Field(default_factory=list, description="Optional course IDs")
    compliance_rate: float = Field(ge=0.0, le=100.0, description="Current compliance rate (%)")


class TrainingMetrics(BaseModel):
    """Aggregated training & competency metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_courses: int = Field(ge=0, description="Total training courses defined")
    total_assignments: int = Field(ge=0, description="Total training assignments")
    completion_rate: float = Field(ge=0.0, le=100.0, description="Overall completion rate (%)")
    overdue_count: int = Field(ge=0, description="Number of overdue assignments")
    avg_score: float = Field(ge=0.0, le=100.0, description="Average score across completed assignments")
    certifications_expiring_30d: int = Field(
        ge=0, description="Certifications expiring within 30 days"
    )
    compliance_by_role: dict[str, float] = Field(
        default_factory=dict, description="Compliance rate by role"
    )
    compliance_by_site: dict[str, float] = Field(
        default_factory=dict, description="Compliance rate by site"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class TrainingCourseCreate(BaseModel):
    """Request to create a training course."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="Course title")
    training_type: TrainingType = Field(..., description="Training type")
    description: str = Field(..., description="Course description")
    duration_hours: float = Field(..., ge=0.0, description="Duration in hours")
    passing_score: float = Field(default=80.0, ge=0.0, le=100.0, description="Passing score")
    version: str = Field(default="1.0", description="Course version")
    expiry_months: int = Field(default=24, ge=0, description="Months until expiry")
    required_for_roles: list[str] = Field(default_factory=list, description="Required for roles")
    content_modules: list[str] = Field(default_factory=list, description="Content modules")


class TrainingCourseUpdate(BaseModel):
    """Request to update a training course."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Course title")
    description: str | None = Field(None, description="Description")
    duration_hours: float | None = Field(None, ge=0.0, description="Duration")
    passing_score: float | None = Field(None, ge=0.0, le=100.0, description="Passing score")
    version: str | None = Field(None, description="Version")
    expiry_months: int | None = Field(None, ge=0, description="Expiry months")
    required_for_roles: list[str] | None = Field(None, description="Required for roles")
    content_modules: list[str] | None = Field(None, description="Content modules")


class TrainingAssignmentCreate(BaseModel):
    """Request to create a training assignment."""

    model_config = ConfigDict(from_attributes=True)

    course_id: str = Field(..., description="Course ID")
    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")
    role: str = Field(..., description="User role")
    site_id: str = Field(..., description="Site ID")
    due_date: datetime = Field(..., description="Completion deadline")


class TrainingAssignmentUpdate(BaseModel):
    """Request to update a training assignment."""

    model_config = ConfigDict(from_attributes=True)

    status: CompletionStatus | None = Field(None, description="Status")
    score: float | None = Field(None, ge=0.0, le=100.0, description="Score")
    due_date: datetime | None = Field(None, description="Due date")


class TrainingAssignmentComplete(BaseModel):
    """Request to complete a training assignment."""

    model_config = ConfigDict(from_attributes=True)

    score: float = Field(..., ge=0.0, le=100.0, description="Score achieved")
    completion_date: datetime | None = Field(None, description="Completion date (defaults to now)")


class CompetencyAssessmentCreate(BaseModel):
    """Request to create a competency assessment."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="User ID")
    skill_area: str = Field(..., description="Skill area")
    current_level: CompetencyLevel = Field(..., description="Competency level")
    assessor: str = Field(..., description="Assessor name")
    next_assessment_date: datetime = Field(..., description="Next assessment date")
    evidence: list[str] = Field(default_factory=list, description="Evidence")


class CompetencyAssessmentUpdate(BaseModel):
    """Request to update a competency assessment."""

    model_config = ConfigDict(from_attributes=True)

    current_level: CompetencyLevel | None = Field(None, description="Level")
    assessor: str | None = Field(None, description="Assessor")
    next_assessment_date: datetime | None = Field(None, description="Next assessment date")
    evidence: list[str] | None = Field(None, description="Evidence")


class AutoAssignRequest(BaseModel):
    """Request to auto-assign training based on role/matrix."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")
    role: str = Field(..., description="User role")
    site_id: str = Field(..., description="Site ID")


class AutoAssignResponse(BaseModel):
    """Response from auto-assignment."""

    model_config = ConfigDict(from_attributes=True)

    assignments_created: int = Field(ge=0, description="Number of assignments created")
    assignments: list[TrainingAssignment] = Field(default_factory=list, description="Created assignments")


class CompetencyGapAnalysis(BaseModel):
    """Competency gap analysis for a user or role."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="User role")
    gaps: list[str] = Field(default_factory=list, description="Identified competency gaps")
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended training courses"
    )
    overall_competency_score: float = Field(
        ge=0.0, le=100.0, description="Overall competency score (%)"
    )


class CertificationExpiryAlert(BaseModel):
    """Alert for an expiring certification."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: str = Field(..., description="Assignment ID")
    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")
    course_id: str = Field(..., description="Course ID")
    course_title: str = Field(..., description="Course title")
    completion_date: datetime = Field(..., description="Original completion date")
    expiry_date: datetime = Field(..., description="Certification expiry date")
    days_until_expiry: int = Field(..., description="Days until certification expires")


class RecertificationReminder(BaseModel):
    """Re-certification reminder for an expiring training."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")
    course_id: str = Field(..., description="Course ID")
    course_title: str = Field(..., description="Course title")
    expiry_date: datetime = Field(..., description="Certification expiry date")
    days_until_expiry: int = Field(..., description="Days remaining")
    priority: str = Field(..., description="Priority level (urgent/warning/info)")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class TrainingCourseListResponse(BaseModel):
    """List of training courses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrainingCourse] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TrainingAssignmentListResponse(BaseModel):
    """List of training assignments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrainingAssignment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CompetencyAssessmentListResponse(BaseModel):
    """List of competency assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CompetencyAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TrainingMatrixListResponse(BaseModel):
    """List of training matrix entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrainingMatrix] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CertificationExpiryListResponse(BaseModel):
    """List of certification expiry alerts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CertificationExpiryAlert] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RecertificationReminderListResponse(BaseModel):
    """List of re-certification reminders."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RecertificationReminder] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
