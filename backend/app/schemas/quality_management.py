"""Pydantic schemas for Quality Management (CAPA & Qualification).

VP-Quality-2: IQ/OQ/PQ Qualification Documentation and CAPA system.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# CAPA Enumerations
# ---------------------------------------------------------------------------


class CAPAType(str, Enum):
    """Type of CAPA action."""

    CORRECTIVE = "CORRECTIVE"
    PREVENTIVE = "PREVENTIVE"


class CAPASource(str, Enum):
    """Source that triggered the CAPA."""

    AUDIT = "AUDIT"
    INCIDENT = "INCIDENT"
    DEVIATION = "DEVIATION"
    COMPLAINT = "COMPLAINT"


class CAPASeverity(str, Enum):
    """Severity classification of CAPA."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class CAPAStatus(str, Enum):
    """CAPA lifecycle status."""

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ACTION_PLANNED = "ACTION_PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFICATION = "VERIFICATION"
    CLOSED = "CLOSED"


class RootCauseCategory(str, Enum):
    """Root cause analysis categories."""

    PROCESS = "PROCESS"
    TECHNOLOGY = "TECHNOLOGY"
    HUMAN_ERROR = "HUMAN_ERROR"
    DESIGN = "DESIGN"
    EXTERNAL = "EXTERNAL"


class QualificationType(str, Enum):
    """Qualification protocol type."""

    IQ = "IQ"
    OQ = "OQ"
    PQ = "PQ"


class CheckStatus(str, Enum):
    """Status of a single qualification check."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


# ---------------------------------------------------------------------------
# CAPA Schemas
# ---------------------------------------------------------------------------


class CAPACreate(BaseModel):
    """Request schema for creating a new CAPA."""

    title: str = Field(..., min_length=1, max_length=500, description="CAPA title")
    description: str = Field(..., min_length=1, description="Detailed description of the issue")
    capa_type: CAPAType = Field(..., description="Corrective or Preventive")
    source: CAPASource = Field(..., description="Source that triggered the CAPA")
    severity: CAPASeverity = Field(..., description="Severity classification")
    root_cause_category: RootCauseCategory | None = Field(
        default=None, description="Root cause analysis category"
    )
    root_cause: str | None = Field(default=None, description="Root cause description")
    corrective_action: str | None = Field(default=None, description="Planned corrective action")
    preventive_action: str | None = Field(default=None, description="Planned preventive action")
    assigned_to: str | None = Field(default=None, description="Person assigned to resolve")
    due_date: datetime | None = Field(default=None, description="Target resolution date")


class CAPAUpdate(BaseModel):
    """Request schema for updating a CAPA."""

    title: str | None = Field(default=None, max_length=500, description="Updated title")
    description: str | None = Field(default=None, description="Updated description")
    status: CAPAStatus | None = Field(default=None, description="New status (state transition)")
    severity: CAPASeverity | None = Field(default=None, description="Updated severity")
    root_cause_category: RootCauseCategory | None = Field(
        default=None, description="Root cause category"
    )
    root_cause: str | None = Field(default=None, description="Root cause description")
    corrective_action: str | None = Field(default=None, description="Corrective action taken")
    preventive_action: str | None = Field(default=None, description="Preventive action planned")
    assigned_to: str | None = Field(default=None, description="Updated assignee")
    due_date: datetime | None = Field(default=None, description="Updated due date")
    effectiveness_check_date: datetime | None = Field(
        default=None, description="Date to check effectiveness"
    )


class CAPAResponse(BaseModel):
    """Full CAPA record response."""

    id: str
    title: str
    description: str
    capa_type: CAPAType
    source: CAPASource
    severity: CAPASeverity
    status: CAPAStatus
    root_cause_category: RootCauseCategory | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    assigned_to: str | None = None
    due_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    effectiveness_check_date: datetime | None = None
    recurrence_count: int = 0

    model_config = {"from_attributes": True}


class CAPAMetrics(BaseModel):
    """CAPA dashboard metrics."""

    total_capas: int = Field(description="Total CAPA count")
    open_capas: int = Field(description="Open (non-closed) CAPAs")
    by_severity: dict[str, int] = Field(description="Count by severity level")
    by_status: dict[str, int] = Field(description="Count by status")
    by_type: dict[str, int] = Field(description="Count by CAPA type")
    overdue_count: int = Field(description="CAPAs past their due date")
    avg_days_to_close: float = Field(description="Average days from open to close")
    recurrence_rate: float = Field(
        description="Percentage of closed CAPAs with recurrence"
    )


class CAPAListResponse(BaseModel):
    """Paginated list of CAPAs."""

    capas: list[CAPAResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Qualification Schemas
# ---------------------------------------------------------------------------


class QualificationCheck(BaseModel):
    """Result of a single qualification check."""

    check_id: str = Field(description="Unique check identifier (e.g., IQ-TC-001)")
    name: str = Field(description="Human-readable check name")
    category: QualificationType = Field(description="IQ, OQ, or PQ")
    status: CheckStatus = Field(description="PASS, FAIL, or SKIP")
    details: str = Field(default="", description="Additional details or error message")
    duration_ms: float = Field(default=0.0, description="Check execution time in milliseconds")


class QualificationSummary(BaseModel):
    """Summary statistics for a qualification run."""

    total_checks: int
    passed: int
    failed: int
    skipped: int
    pass_rate: float = Field(description="Percentage of passed checks (0-100)")
    total_duration_ms: float = Field(description="Total execution time")
    qualification_type: QualificationType
    overall_result: str = Field(description="PASS if all checks pass, FAIL otherwise")


class QualificationReport(BaseModel):
    """Full qualification report from a test run."""

    id: str = Field(description="Report unique identifier")
    qualification_type: QualificationType
    summary: QualificationSummary
    checks: list[QualificationCheck]
    executed_at: datetime
    executed_by: str = Field(default="system", description="Who initiated the run")
    environment: str = Field(default="unknown", description="Environment tested")


class QualificationRunRequest(BaseModel):
    """Request to execute a qualification suite."""

    qualification_type: QualificationType = Field(
        ..., description="Which qualification suite to run (IQ, OQ, or PQ)"
    )
    executed_by: str = Field(
        default="system", description="Identifier of the person initiating the run"
    )


class QualificationReportListResponse(BaseModel):
    """List of qualification reports."""

    reports: list[QualificationReport]
    total: int
