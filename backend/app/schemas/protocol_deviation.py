"""Pydantic schemas for Protocol Deviation Tracking (CMO-7).

Tracks and manages clinical protocol deviations across trial sites,
including severity classification, notification tracking, CAPA linkage,
and regulatory compliance metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeviationType(str, Enum):
    """Classification of protocol deviation types."""

    INCLUSION_CRITERIA = "INCLUSION_CRITERIA"
    EXCLUSION_CRITERIA = "EXCLUSION_CRITERIA"
    INFORMED_CONSENT = "INFORMED_CONSENT"
    VISIT_WINDOW = "VISIT_WINDOW"
    PROHIBITED_MEDICATION = "PROHIBITED_MEDICATION"
    PROCEDURE_ERROR = "PROCEDURE_ERROR"
    RANDOMIZATION_ERROR = "RANDOMIZATION_ERROR"
    DOSING_ERROR = "DOSING_ERROR"
    SAFETY_REPORTING = "SAFETY_REPORTING"
    DATA_COLLECTION = "DATA_COLLECTION"


class DeviationSeverity(str, Enum):
    """Severity level of a protocol deviation."""

    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class DeviationStatus(str, Enum):
    """Status of a protocol deviation through its lifecycle."""

    REPORTED = "REPORTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    CAPA_REQUIRED = "CAPA_REQUIRED"
    CAPA_IN_PROGRESS = "CAPA_IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# Core record
# ---------------------------------------------------------------------------


class DeviationRecord(BaseModel):
    """A single protocol deviation record with full audit trail."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique deviation identifier")
    trial_id: str = Field(..., description="Trial the deviation belongs to")
    patient_id: str | None = Field(None, description="Patient involved (may be de-identified)")
    site_id: str = Field(..., description="Site where the deviation occurred")
    deviation_type: DeviationType = Field(..., description="Classification of the deviation")
    severity: DeviationSeverity = Field(..., description="Severity level")
    status: DeviationStatus = Field(
        default=DeviationStatus.REPORTED, description="Current lifecycle status"
    )
    title: str = Field(..., description="Short title summarising the deviation")
    description: str = Field(..., description="Detailed description of the deviation")
    date_occurred: datetime = Field(..., description="When the deviation occurred")
    date_reported: datetime = Field(..., description="When the deviation was reported")
    reported_by: str = Field(..., description="Person who reported the deviation")
    reviewer: str | None = Field(None, description="Assigned reviewer")
    root_cause: str | None = Field(None, description="Root cause analysis")
    impact_assessment: str | None = Field(None, description="Assessment of deviation impact")
    capa_id: str | None = Field(None, description="Linked CAPA record identifier")
    irb_notification_required: bool = Field(
        default=False, description="Whether IRB notification is required"
    )
    sponsor_notification_required: bool = Field(
        default=False, description="Whether sponsor notification is required"
    )
    irb_notified_date: datetime | None = Field(
        None, description="Date IRB was notified"
    )
    sponsor_notified_date: datetime | None = Field(
        None, description="Date sponsor was notified"
    )
    resolution_notes: str | None = Field(None, description="Notes on how the deviation was resolved")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")
    closed_at: datetime | None = Field(None, description="When the deviation was closed")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class DeviationCreate(BaseModel):
    """Request payload for creating a new deviation."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial the deviation belongs to")
    patient_id: str | None = Field(None, description="Patient involved (may be de-identified)")
    site_id: str = Field(..., description="Site where the deviation occurred")
    deviation_type: DeviationType = Field(..., description="Classification of the deviation")
    severity: DeviationSeverity = Field(..., description="Severity level")
    title: str = Field(..., description="Short title summarising the deviation")
    description: str = Field(..., description="Detailed description of the deviation")
    date_occurred: datetime = Field(..., description="When the deviation occurred")
    reported_by: str = Field(..., description="Person who reported the deviation")


class DeviationUpdate(BaseModel):
    """Request payload for updating an existing deviation."""

    model_config = ConfigDict(from_attributes=True)

    status: DeviationStatus | None = Field(None, description="New status")
    severity: DeviationSeverity | None = Field(None, description="Updated severity")
    reviewer: str | None = Field(None, description="Assigned reviewer")
    root_cause: str | None = Field(None, description="Root cause analysis")
    resolution_notes: str | None = Field(None, description="Resolution notes")


class DeviationListResponse(BaseModel):
    """Paginated list of deviation records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DeviationRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
    limit: int = Field(ge=1, description="Page size")
    offset: int = Field(ge=0, description="Page offset")


class CAPALinkRequest(BaseModel):
    """Request to link a deviation to a CAPA record."""

    capa_id: str = Field(..., description="CAPA record identifier to link")


class NotificationRequest(BaseModel):
    """Request to record a notification date."""

    notified_date: datetime = Field(..., description="Date the notification was sent")


class ImpactAssessmentRequest(BaseModel):
    """Request to record an impact assessment."""

    impact_text: str = Field(..., description="Impact assessment text")


# ---------------------------------------------------------------------------
# Metrics & Trends
# ---------------------------------------------------------------------------


class DeviationTrend(BaseModel):
    """Monthly deviation trend data point."""

    model_config = ConfigDict(from_attributes=True)

    month: str = Field(..., description="Month in YYYY-MM format")
    count: int = Field(ge=0, description="Total deviations in this month")
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Count per severity level"
    )


class DeviationMetrics(BaseModel):
    """Aggregated protocol deviation metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_deviations: int = Field(ge=0, description="Total deviation count")
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Count per deviation type"
    )
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Count per severity level"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="Count per status"
    )
    by_trial: dict[str, int] = Field(
        default_factory=dict, description="Count per trial"
    )
    mean_time_to_resolution_days: float | None = Field(
        None, description="Average days from report to resolution"
    )
    capa_linkage_rate: float = Field(
        ge=0.0, le=1.0, default=0.0,
        description="Fraction of deviations linked to a CAPA",
    )
    irb_notification_compliance_rate: float = Field(
        ge=0.0, le=1.0, default=0.0,
        description="Fraction of IRB-required deviations that were notified on time",
    )
    sponsor_notification_compliance_rate: float = Field(
        ge=0.0, le=1.0, default=0.0,
        description="Fraction of sponsor-required deviations that were notified on time",
    )
    trends: list[DeviationTrend] = Field(
        default_factory=list, description="Monthly trend data"
    )
