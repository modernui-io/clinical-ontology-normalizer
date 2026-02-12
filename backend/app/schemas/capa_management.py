"""Pydantic schemas for Corrective and Preventive Action (CAPA) Management.

Manages CAPA lifecycle operations: CAPA record creation and tracking, root cause
analysis, action plan management, implementation oversight, effectiveness
verification, and CAPA metrics aggregation across clinical trial sites.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CapaType(str, Enum):
    """Type of CAPA: corrective (address existing issue) or preventive (prevent recurrence)."""

    CORRECTIVE = "corrective"
    PREVENTIVE = "preventive"


class CapaStatus(str, Enum):
    """Lifecycle status of a CAPA record."""

    OPEN = "open"
    INVESTIGATION = "investigation"
    ACTION_PLAN = "action_plan"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"
    CLOSED = "closed"


class CapaPriority(str, Enum):
    """Priority classification for a CAPA."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class CapaSource(str, Enum):
    """Source that originated the CAPA."""

    AUDIT_FINDING = "audit_finding"
    DEVIATION = "deviation"
    COMPLAINT = "complaint"
    INSPECTION = "inspection"
    SELF_IDENTIFIED = "self_identified"
    TREND_ANALYSIS = "trend_analysis"


class CapaActionStatus(str, Enum):
    """Status of an individual CAPA action item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CapaActionType(str, Enum):
    """Type of corrective/preventive action."""

    CORRECTIVE = "corrective"
    PREVENTIVE = "preventive"
    CONTAINMENT = "containment"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CapaRecord(BaseModel):
    """A Corrective and Preventive Action record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique CAPA identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Associated site identifier")
    capa_number: str = Field(..., description="Human-readable CAPA number (e.g., CAPA-2026-001)")
    capa_type: CapaType = Field(..., description="Type of CAPA (corrective or preventive)")
    status: CapaStatus = Field(default=CapaStatus.OPEN, description="Current lifecycle status")
    priority: CapaPriority = Field(..., description="Priority classification")
    source: CapaSource = Field(..., description="Source that originated the CAPA")
    title: str = Field(..., description="Brief title describing the CAPA")
    description: str = Field(..., description="Detailed description of the issue")
    root_cause_analysis: str | None = Field(
        None, description="Root cause analysis findings"
    )
    identified_date: datetime = Field(..., description="Date the issue was identified")
    due_date: datetime = Field(..., description="Target completion date")
    closed_date: datetime | None = Field(None, description="Date the CAPA was closed")
    assigned_to: str = Field(..., description="Person or team responsible for the CAPA")
    department: str = Field(..., description="Department responsible for the CAPA")
    related_deviation_ids: list[str] = Field(
        default_factory=list, description="IDs of related protocol deviations"
    )
    related_audit_ids: list[str] = Field(
        default_factory=list, description="IDs of related audit findings"
    )
    effectiveness_check_date: datetime | None = Field(
        None, description="Scheduled date for effectiveness verification"
    )
    effectiveness_verified: bool = Field(
        default=False, description="Whether effectiveness has been verified"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class CapaAction(BaseModel):
    """An individual action item within a CAPA."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique action identifier")
    capa_id: str = Field(..., description="Parent CAPA identifier")
    action_description: str = Field(..., description="Description of the action to be taken")
    action_type: CapaActionType = Field(..., description="Type of action")
    assigned_to: str = Field(..., description="Person responsible for this action")
    due_date: datetime = Field(..., description="Target completion date for this action")
    completed_date: datetime | None = Field(None, description="Actual completion date")
    status: CapaActionStatus = Field(
        default=CapaActionStatus.PENDING, description="Action status"
    )
    evidence_description: str | None = Field(
        None, description="Description of evidence supporting completion"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class CapaMetrics(BaseModel):
    """Aggregated CAPA management metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_capas: int = Field(ge=0, description="Total CAPA records")
    open_capas: int = Field(ge=0, description="Number of open CAPAs (not closed)")
    closed_capas: int = Field(ge=0, description="Number of closed CAPAs")
    overdue_capas: int = Field(ge=0, description="CAPAs past their due date and not closed")
    capas_by_status: dict[str, int] = Field(
        default_factory=dict, description="CAPA counts by status"
    )
    capas_by_priority: dict[str, int] = Field(
        default_factory=dict, description="CAPA counts by priority"
    )
    capas_by_source: dict[str, int] = Field(
        default_factory=dict, description="CAPA counts by source"
    )
    avg_days_to_close: float = Field(
        ge=0.0, description="Average number of days from open to close"
    )
    effectiveness_verified_count: int = Field(
        ge=0, description="Number of CAPAs with verified effectiveness"
    )
    total_actions: int = Field(ge=0, description="Total action items across all CAPAs")
    completed_actions: int = Field(ge=0, description="Number of completed action items")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class CapaCreate(BaseModel):
    """Request to create a new CAPA record."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    capa_type: CapaType = Field(..., description="Type of CAPA")
    priority: CapaPriority = Field(..., description="Priority classification")
    source: CapaSource = Field(..., description="Source of the CAPA")
    title: str = Field(..., description="Brief title")
    description: str = Field(..., description="Detailed description")
    due_date: datetime = Field(..., description="Target completion date")
    assigned_to: str = Field(..., description="Responsible person or team")
    department: str = Field(..., description="Responsible department")
    related_deviation_ids: list[str] = Field(
        default_factory=list, description="Related deviation IDs"
    )
    related_audit_ids: list[str] = Field(
        default_factory=list, description="Related audit finding IDs"
    )


class CapaUpdate(BaseModel):
    """Request to update an existing CAPA record."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Brief title")
    description: str | None = Field(None, description="Detailed description")
    priority: CapaPriority | None = Field(None, description="Priority classification")
    due_date: datetime | None = Field(None, description="Target completion date")
    assigned_to: str | None = Field(None, description="Responsible person or team")
    department: str | None = Field(None, description="Responsible department")
    root_cause_analysis: str | None = Field(None, description="Root cause analysis findings")
    related_deviation_ids: list[str] | None = Field(None, description="Related deviation IDs")
    related_audit_ids: list[str] | None = Field(None, description="Related audit finding IDs")
    effectiveness_check_date: datetime | None = Field(
        None, description="Scheduled effectiveness check date"
    )


class CapaActionCreate(BaseModel):
    """Request to create a CAPA action item."""

    model_config = ConfigDict(from_attributes=True)

    action_description: str = Field(..., description="Description of the action")
    action_type: CapaActionType = Field(..., description="Type of action")
    assigned_to: str = Field(..., description="Responsible person")
    due_date: datetime = Field(..., description="Target completion date")
    evidence_description: str | None = Field(None, description="Expected evidence")


class CapaActionUpdate(BaseModel):
    """Request to update a CAPA action item."""

    model_config = ConfigDict(from_attributes=True)

    action_description: str | None = Field(None, description="Description of the action")
    action_type: CapaActionType | None = Field(None, description="Type of action")
    assigned_to: str | None = Field(None, description="Responsible person")
    due_date: datetime | None = Field(None, description="Target completion date")
    status: CapaActionStatus | None = Field(None, description="Action status")
    evidence_description: str | None = Field(None, description="Evidence description")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class CapaListResponse(BaseModel):
    """List of CAPA records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CapaRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CapaActionListResponse(BaseModel):
    """List of CAPA action items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CapaAction] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
