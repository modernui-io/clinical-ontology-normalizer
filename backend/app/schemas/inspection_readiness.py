"""Pydantic schemas for Inspection Readiness module.

Manages regulatory inspection preparation including mock inspections, inspection
checklists, document readiness, CAPA tracking, inspector observations, and
readiness scoring for FDA/EMA/PMDA inspections.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InspectionType(str, Enum):
    """Type of regulatory inspection."""

    FDA_ROUTINE = "fda_routine"
    FDA_FOR_CAUSE = "fda_for_cause"
    FDA_PRE_APPROVAL = "fda_pre_approval"
    EMA_GCP = "ema_gcp"
    EMA_GMP = "ema_gmp"
    PMDA = "pmda"
    HEALTH_CANADA = "health_canada"
    MHRA = "mhra"
    MOCK = "mock"
    INTERNAL_AUDIT = "internal_audit"


class ReadinessStatus(str, Enum):
    """Overall readiness status for an assessment."""

    NOT_ASSESSED = "not_assessed"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    NEEDS_ATTENTION = "needs_attention"
    CRITICAL_GAPS = "critical_gaps"


class ChecklistCategory(str, Enum):
    """Category for readiness checklist items."""

    DOCUMENTATION = "documentation"
    FACILITIES = "facilities"
    PERSONNEL = "personnel"
    SYSTEMS = "systems"
    PROCESSES = "processes"
    TRAINING = "training"
    QUALITY = "quality"


class FindingSeverity(str, Enum):
    """Severity classification for inspection findings."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"


class CAPAStatus(str, Enum):
    """Lifecycle status of a CAPA (Corrective and Preventive Action)."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    CLOSED = "closed"
    OVERDUE = "overdue"


class InspectionOutcome(str, Enum):
    """Outcome of a completed inspection."""

    NO_ACTION_INDICATED = "no_action_indicated"
    VOLUNTARY_ACTION_INDICATED = "voluntary_action_indicated"
    OFFICIAL_ACTION_INDICATED = "official_action_indicated"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"


class InspectionEventStatus(str, Enum):
    """Status of an inspection event."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class ChecklistItemStatus(str, Enum):
    """Status of an individual checklist item."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_REMEDIATION = "needs_remediation"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class InspectionEvent(BaseModel):
    """A scheduled or completed regulatory inspection event."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique inspection event identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site being inspected")
    inspection_type: InspectionType = Field(..., description="Type of regulatory inspection")
    scheduled_date: datetime = Field(..., description="Scheduled date for the inspection")
    actual_date: datetime | None = Field(None, description="Actual date the inspection occurred")
    inspector_name: str = Field(..., description="Lead inspector name")
    inspector_agency: str = Field(..., description="Regulatory agency conducting the inspection")
    status: InspectionEventStatus = Field(
        default=InspectionEventStatus.SCHEDULED, description="Current status of the inspection"
    )
    outcome: InspectionOutcome = Field(
        default=InspectionOutcome.PENDING, description="Outcome of the inspection"
    )
    duration_days: int = Field(default=1, ge=1, description="Duration of the inspection in days")
    scope: str = Field(default="", description="Scope of the inspection")
    findings_count: int = Field(default=0, ge=0, description="Number of findings from this inspection")
    observations: str | None = Field(None, description="General observations from the inspection")
    created_at: datetime = Field(..., description="Record creation timestamp")


class CategoryScore(BaseModel):
    """Score for a single readiness category."""

    model_config = ConfigDict(from_attributes=True)

    category: ChecklistCategory = Field(..., description="Checklist category")
    score: float = Field(ge=0.0, le=100.0, description="Score for this category (0-100)")
    items_total: int = Field(default=0, ge=0, description="Total checklist items in this category")
    items_complete: int = Field(default=0, ge=0, description="Completed items in this category")


class ReadinessAssessment(BaseModel):
    """A readiness assessment for a trial site before an inspection."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assessment identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site being assessed")
    assessment_date: datetime = Field(..., description="Date the assessment was conducted")
    assessed_by: str = Field(..., description="Name of the person conducting the assessment")
    overall_score: float = Field(
        ge=0.0, le=100.0, description="Overall readiness score (0-100)"
    )
    overall_status: ReadinessStatus = Field(..., description="Overall readiness status")
    category_scores: list[CategoryScore] = Field(
        default_factory=list, description="Scores broken down by category"
    )
    gaps_identified: int = Field(default=0, ge=0, description="Number of gaps identified")
    action_items_count: int = Field(default=0, ge=0, description="Number of action items generated")
    next_assessment_date: datetime | None = Field(
        None, description="Recommended date for next assessment"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class ReadinessChecklist(BaseModel):
    """An individual checklist item within a readiness assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique checklist item identifier")
    assessment_id: str = Field(..., description="Associated assessment identifier")
    category: ChecklistCategory = Field(..., description="Category of the checklist item")
    item_description: str = Field(..., description="Description of the checklist item")
    required: bool = Field(default=True, description="Whether this item is required for readiness")
    status: ChecklistItemStatus = Field(
        default=ChecklistItemStatus.NOT_STARTED, description="Current status of the item"
    )
    evidence_reference: str | None = Field(
        None, description="Reference to evidence document supporting completion"
    )
    notes: str | None = Field(None, description="Additional notes for this item")
    verified_by: str | None = Field(None, description="Name of person who verified this item")
    verified_date: datetime | None = Field(None, description="Date the item was verified")


class InspectionFinding(BaseModel):
    """A finding recorded during or after an inspection."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique finding identifier")
    inspection_id: str = Field(..., description="Associated inspection event identifier")
    finding_number: str = Field(..., description="Finding reference number (e.g., F-001)")
    severity: FindingSeverity = Field(..., description="Severity classification of the finding")
    category: ChecklistCategory = Field(..., description="Category the finding relates to")
    description: str = Field(..., description="Detailed description of the finding")
    root_cause: str | None = Field(None, description="Identified root cause of the finding")
    regulatory_reference: str | None = Field(
        None, description="Regulatory reference (e.g., 21 CFR 11, ICH E6(R2))"
    )
    response_due_date: datetime = Field(..., description="Due date for response to the finding")
    response_submitted: bool = Field(
        default=False, description="Whether a response has been submitted"
    )
    response_accepted: bool = Field(
        default=False, description="Whether the response was accepted by the inspector"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class CAPA(BaseModel):
    """Corrective and Preventive Action linked to an inspection finding."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique CAPA identifier")
    finding_id: str = Field(..., description="Associated finding identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Associated site identifier")
    description: str = Field(..., description="Description of the CAPA")
    root_cause_analysis: str = Field(..., description="Root cause analysis summary")
    corrective_action: str = Field(..., description="Corrective action to address the finding")
    preventive_action: str = Field(..., description="Preventive action to avoid recurrence")
    assigned_to: str = Field(..., description="Person responsible for the CAPA")
    due_date: datetime = Field(..., description="CAPA due date")
    completed_date: datetime | None = Field(None, description="Date the CAPA was completed")
    verified_by: str | None = Field(None, description="Person who verified CAPA effectiveness")
    verification_date: datetime | None = Field(
        None, description="Date the CAPA effectiveness was verified"
    )
    status: CAPAStatus = Field(default=CAPAStatus.OPEN, description="Current CAPA status")
    effectiveness_check: bool = Field(
        default=False, description="Whether effectiveness check has been performed"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class InspectionMetrics(BaseModel):
    """Aggregated inspection readiness metrics for dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_inspections: int = Field(ge=0, description="Total inspection events")
    inspections_by_type: dict[str, int] = Field(
        default_factory=dict, description="Inspection counts by type"
    )
    inspections_by_status: dict[str, int] = Field(
        default_factory=dict, description="Inspection counts by status"
    )
    total_assessments: int = Field(ge=0, description="Total readiness assessments")
    average_readiness_score: float = Field(
        ge=0.0, description="Average readiness score across assessments"
    )
    assessments_by_status: dict[str, int] = Field(
        default_factory=dict, description="Assessment counts by readiness status"
    )
    total_checklist_items: int = Field(ge=0, description="Total checklist items across all assessments")
    checklist_completion_rate: float = Field(
        ge=0.0, le=100.0, description="Percentage of checklist items completed"
    )
    total_findings: int = Field(ge=0, description="Total inspection findings")
    findings_by_severity: dict[str, int] = Field(
        default_factory=dict, description="Finding counts by severity"
    )
    total_capas: int = Field(ge=0, description="Total CAPAs")
    capas_by_status: dict[str, int] = Field(
        default_factory=dict, description="CAPA counts by status"
    )
    overdue_capas: int = Field(ge=0, description="Number of overdue CAPAs")
    open_capas: int = Field(ge=0, description="Number of open/in-progress CAPAs")
    sites_ready: int = Field(ge=0, description="Number of sites assessed as ready")
    sites_with_critical_gaps: int = Field(
        ge=0, description="Number of sites with critical gaps"
    )


# ---------------------------------------------------------------------------
# Create / Update models
# ---------------------------------------------------------------------------


class InspectionEventCreate(BaseModel):
    """Request to create a new inspection event."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    inspection_type: InspectionType = Field(..., description="Type of inspection")
    scheduled_date: datetime = Field(..., description="Scheduled date")
    inspector_name: str = Field(..., description="Lead inspector name")
    inspector_agency: str = Field(..., description="Regulatory agency")
    duration_days: int = Field(default=1, ge=1, description="Duration in days")
    scope: str = Field(default="", description="Scope of the inspection")


class InspectionEventUpdate(BaseModel):
    """Request to update an inspection event."""

    model_config = ConfigDict(from_attributes=True)

    inspection_type: InspectionType | None = Field(None, description="Type of inspection")
    scheduled_date: datetime | None = Field(None, description="Scheduled date")
    actual_date: datetime | None = Field(None, description="Actual date")
    inspector_name: str | None = Field(None, description="Inspector name")
    inspector_agency: str | None = Field(None, description="Agency")
    status: InspectionEventStatus | None = Field(None, description="Status")
    outcome: InspectionOutcome | None = Field(None, description="Outcome")
    duration_days: int | None = Field(None, ge=1, description="Duration")
    scope: str | None = Field(None, description="Scope")
    observations: str | None = Field(None, description="Observations")


class ReadinessAssessmentCreate(BaseModel):
    """Request to create a readiness assessment."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    assessed_by: str = Field(..., description="Assessor name")


class ReadinessAssessmentUpdate(BaseModel):
    """Request to update a readiness assessment."""

    model_config = ConfigDict(from_attributes=True)

    overall_score: float | None = Field(None, ge=0.0, le=100.0, description="Overall score")
    overall_status: ReadinessStatus | None = Field(None, description="Overall status")
    next_assessment_date: datetime | None = Field(None, description="Next assessment date")


class ReadinessChecklistCreate(BaseModel):
    """Request to create a checklist item."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: str = Field(..., description="Assessment identifier")
    category: ChecklistCategory = Field(..., description="Category")
    item_description: str = Field(..., description="Description")
    required: bool = Field(default=True, description="Whether required")


class ReadinessChecklistUpdate(BaseModel):
    """Request to update a checklist item."""

    model_config = ConfigDict(from_attributes=True)

    status: ChecklistItemStatus | None = Field(None, description="Status")
    evidence_reference: str | None = Field(None, description="Evidence reference")
    notes: str | None = Field(None, description="Notes")
    verified_by: str | None = Field(None, description="Verified by")
    verified_date: datetime | None = Field(None, description="Verified date")


class InspectionFindingCreate(BaseModel):
    """Request to create an inspection finding."""

    model_config = ConfigDict(from_attributes=True)

    inspection_id: str = Field(..., description="Inspection event identifier")
    severity: FindingSeverity = Field(..., description="Severity")
    category: ChecklistCategory = Field(..., description="Category")
    description: str = Field(..., description="Description")
    root_cause: str | None = Field(None, description="Root cause")
    regulatory_reference: str | None = Field(None, description="Regulatory reference")
    response_due_date: datetime = Field(..., description="Response due date")


class InspectionFindingUpdate(BaseModel):
    """Request to update an inspection finding."""

    model_config = ConfigDict(from_attributes=True)

    severity: FindingSeverity | None = Field(None, description="Severity")
    category: ChecklistCategory | None = Field(None, description="Category")
    description: str | None = Field(None, description="Description")
    root_cause: str | None = Field(None, description="Root cause")
    regulatory_reference: str | None = Field(None, description="Regulatory reference")
    response_due_date: datetime | None = Field(None, description="Response due date")
    response_submitted: bool | None = Field(None, description="Response submitted")
    response_accepted: bool | None = Field(None, description="Response accepted")


class CAPACreate(BaseModel):
    """Request to create a CAPA."""

    model_config = ConfigDict(from_attributes=True)

    finding_id: str = Field(..., description="Finding identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    description: str = Field(..., description="Description")
    root_cause_analysis: str = Field(..., description="Root cause analysis")
    corrective_action: str = Field(..., description="Corrective action")
    preventive_action: str = Field(..., description="Preventive action")
    assigned_to: str = Field(..., description="Assigned to")
    due_date: datetime = Field(..., description="Due date")


class CAPAUpdate(BaseModel):
    """Request to update a CAPA."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = Field(None, description="Description")
    corrective_action: str | None = Field(None, description="Corrective action")
    preventive_action: str | None = Field(None, description="Preventive action")
    assigned_to: str | None = Field(None, description="Assigned to")
    due_date: datetime | None = Field(None, description="Due date")
    completed_date: datetime | None = Field(None, description="Completed date")
    verified_by: str | None = Field(None, description="Verified by")
    verification_date: datetime | None = Field(None, description="Verification date")
    status: CAPAStatus | None = Field(None, description="Status")
    effectiveness_check: bool | None = Field(None, description="Effectiveness check performed")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class InspectionEventListResponse(BaseModel):
    """List of inspection events."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InspectionEvent] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ReadinessAssessmentListResponse(BaseModel):
    """List of readiness assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReadinessAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ReadinessChecklistListResponse(BaseModel):
    """List of readiness checklist items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReadinessChecklist] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InspectionFindingListResponse(BaseModel):
    """List of inspection findings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InspectionFinding] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CAPAListResponse(BaseModel):
    """List of CAPAs."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CAPA] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
