"""Pydantic schemas for Defect Tracking & Test Environment Management.

QA-3: Pharma-grade defect tracking and test environment management system
providing documented defect resolution for regulatory audits. Includes SLA
enforcement, forward-only state machine, duplicate linking, MTTR metrics,
and test environment health monitoring.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Defect Enumerations
# ---------------------------------------------------------------------------


class DefectSeverity(str, Enum):
    """Defect severity classification (drives SLA deadlines)."""

    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    TRIVIAL = "TRIVIAL"


class DefectPriority(str, Enum):
    """Defect priority for scheduling."""

    P0_IMMEDIATE = "P0_IMMEDIATE"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"
    P4_BACKLOG = "P4_BACKLOG"


class DefectStatus(str, Enum):
    """Defect lifecycle status (forward-only state machine, with REOPEN)."""

    NEW = "NEW"
    TRIAGED = "TRIAGED"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    WONT_FIX = "WONT_FIX"
    DUPLICATE = "DUPLICATE"


class DefectCategory(str, Enum):
    """Classification category for root-cause analysis."""

    FUNCTIONAL = "FUNCTIONAL"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    COMPLIANCE = "COMPLIANCE"
    UI_UX = "UI_UX"
    INTEGRATION = "INTEGRATION"
    REGRESSION = "REGRESSION"


class EnvironmentType(str, Enum):
    """Test environment type."""

    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    QA = "QA"
    UAT = "UAT"
    PRE_PRODUCTION = "PRE_PRODUCTION"
    PRODUCTION = "PRODUCTION"


class EnvironmentStatus(str, Enum):
    """Test environment lifecycle status."""

    PROVISIONING = "PROVISIONING"
    READY = "READY"
    IN_USE = "IN_USE"
    MAINTENANCE = "MAINTENANCE"
    DECOMMISSIONED = "DECOMMISSIONED"


# ---------------------------------------------------------------------------
# SLA Rules (hours by severity)
# ---------------------------------------------------------------------------

SLA_HOURS: dict[DefectSeverity, float] = {
    DefectSeverity.BLOCKER: 4.0,
    DefectSeverity.CRITICAL: 24.0,
    DefectSeverity.MAJOR: 72.0,
    DefectSeverity.MINOR: 168.0,
    DefectSeverity.TRIVIAL: 720.0,
}


# ---------------------------------------------------------------------------
# Valid Status Transitions (forward-only + CLOSED -> REOPENED)
# ---------------------------------------------------------------------------

VALID_STATUS_TRANSITIONS: dict[DefectStatus, list[DefectStatus]] = {
    DefectStatus.NEW: [DefectStatus.TRIAGED, DefectStatus.DUPLICATE, DefectStatus.WONT_FIX],
    DefectStatus.TRIAGED: [DefectStatus.IN_PROGRESS, DefectStatus.WONT_FIX, DefectStatus.DUPLICATE],
    DefectStatus.IN_PROGRESS: [DefectStatus.IN_REVIEW, DefectStatus.WONT_FIX],
    DefectStatus.IN_REVIEW: [DefectStatus.VERIFIED, DefectStatus.IN_PROGRESS],
    DefectStatus.VERIFIED: [DefectStatus.CLOSED],
    DefectStatus.CLOSED: [DefectStatus.REOPENED],
    DefectStatus.REOPENED: [DefectStatus.IN_PROGRESS, DefectStatus.WONT_FIX],
    DefectStatus.WONT_FIX: [],  # Terminal
    DefectStatus.DUPLICATE: [],  # Terminal
}


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class HealthCheck(BaseModel):
    """Health check result for a test environment component."""

    name: str = Field(..., description="Component name (e.g., 'database', 'api')")
    status: str = Field(..., description="Health status: 'healthy', 'degraded', 'unhealthy'")
    last_checked: datetime = Field(..., description="When this check was last performed")
    response_time_ms: float = Field(..., description="Response time in milliseconds")


class DefectComment(BaseModel):
    """A comment on a defect record."""

    id: str = Field(..., description="Unique comment identifier")
    defect_id: str = Field(..., description="Associated defect ID")
    author: str = Field(..., description="Comment author")
    content: str = Field(..., description="Comment text")
    created_at: datetime = Field(..., description="When the comment was created")


class DefectTransition(BaseModel):
    """Audit record for a defect status transition."""

    id: str = Field(..., description="Unique transition identifier")
    defect_id: str = Field(..., description="Associated defect ID")
    from_status: DefectStatus = Field(..., description="Previous status")
    to_status: DefectStatus = Field(..., description="New status")
    transitioned_by: str = Field(..., description="Who performed the transition")
    timestamp: datetime = Field(..., description="When the transition occurred")
    reason: str | None = Field(None, description="Reason for the transition")


class DefectRecord(BaseModel):
    """A tracked software defect with full audit trail."""

    id: str = Field(..., description="Unique defect identifier")
    title: str = Field(..., description="Short defect title")
    description: str = Field(..., description="Detailed defect description")
    severity: DefectSeverity = Field(..., description="Defect severity level")
    priority: DefectPriority = Field(..., description="Scheduling priority")
    status: DefectStatus = Field(DefectStatus.NEW, description="Current lifecycle status")
    category: DefectCategory = Field(..., description="Defect classification category")
    component: str = Field(..., description="Affected system component")
    reported_by: str = Field(..., description="Who reported the defect")
    assigned_to: str | None = Field(None, description="Currently assigned engineer")
    created_at: datetime = Field(..., description="When the defect was created")
    updated_at: datetime = Field(..., description="When the defect was last updated")
    resolved_at: datetime | None = Field(None, description="When the defect was resolved")
    resolution_notes: str | None = Field(None, description="Resolution details")
    steps_to_reproduce: str | None = Field(None, description="Steps to reproduce the defect")
    expected_behavior: str | None = Field(None, description="Expected correct behavior")
    actual_behavior: str | None = Field(None, description="Observed incorrect behavior")
    environment: str | None = Field(None, description="Environment where defect was found")
    build_version: str | None = Field(None, description="Build version with the defect")
    linked_defects: list[str] = Field(default_factory=list, description="IDs of linked/duplicate defects")
    tags: list[str] = Field(default_factory=list, description="Classification tags")
    sla_deadline: datetime | None = Field(None, description="SLA resolution deadline")


class TestEnvironment(BaseModel):
    """A managed test environment with health monitoring."""

    id: str = Field(..., description="Unique environment identifier")
    name: str = Field(..., description="Human-readable environment name")
    env_type: EnvironmentType = Field(..., description="Environment type")
    status: EnvironmentStatus = Field(..., description="Current lifecycle status")
    description: str | None = Field(None, description="Environment description")
    url: str | None = Field(None, description="Access URL for the environment")
    created_at: datetime = Field(..., description="When the environment was provisioned")
    last_refreshed: datetime | None = Field(None, description="Last data refresh timestamp")
    data_snapshot_date: datetime | None = Field(None, description="Date of data snapshot loaded")
    owner: str = Field(..., description="Environment owner / point of contact")
    components: list[str] = Field(default_factory=list, description="Deployed components")
    health_checks: list[HealthCheck] = Field(default_factory=list, description="Latest health check results")


class DefectMetrics(BaseModel):
    """Aggregate defect metrics for dashboards and audits."""

    total: int = Field(..., description="Total defect count")
    by_severity: dict[str, int] = Field(default_factory=dict, description="Count by severity")
    by_status: dict[str, int] = Field(default_factory=dict, description="Count by status")
    by_category: dict[str, int] = Field(default_factory=dict, description="Count by category")
    mttr_hours: float = Field(..., description="Mean time to resolve (hours)")
    sla_compliance_rate: float = Field(..., description="Percentage of defects resolved within SLA")
    reopen_rate: float = Field(..., description="Percentage of defects reopened after closure")
    aging_buckets: dict[str, int] = Field(
        default_factory=dict,
        description="Open defects by age: '0-24h', '24-72h', '72h-1w', '1w+'",
    )


class TrendDataPoint(BaseModel):
    """A single data point in a trend series."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    opened: int = Field(0, description="Defects opened on this date")
    closed: int = Field(0, description="Defects closed on this date")


class DefectTrend(BaseModel):
    """Trend analysis of defect activity over time."""

    period_days: int = Field(..., description="Number of days in the trend period")
    data_points: list[TrendDataPoint] = Field(default_factory=list, description="Daily data points")
    total_opened: int = Field(0, description="Total defects opened in period")
    total_closed: int = Field(0, description="Total defects closed in period")
    net_change: int = Field(0, description="Net change (opened - closed)")


class SLABreachRecord(BaseModel):
    """A defect that has breached or is about to breach SLA."""

    defect_id: str = Field(..., description="Defect identifier")
    title: str = Field(..., description="Defect title")
    severity: DefectSeverity = Field(..., description="Defect severity")
    sla_deadline: datetime = Field(..., description="SLA deadline")
    hours_overdue: float = Field(..., description="Hours past SLA (negative = still within SLA)")
    status: DefectStatus = Field(..., description="Current defect status")
    assigned_to: str | None = Field(None, description="Assigned engineer")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class DefectCreateRequest(BaseModel):
    """Request to create a new defect."""

    title: str = Field(..., min_length=1, max_length=200, description="Defect title")
    description: str = Field(..., min_length=1, description="Defect description")
    severity: DefectSeverity = Field(..., description="Severity level")
    priority: DefectPriority = Field(DefectPriority.P2_MEDIUM, description="Priority level")
    category: DefectCategory = Field(..., description="Defect category")
    component: str = Field(..., min_length=1, description="Affected component")
    reported_by: str = Field(..., min_length=1, description="Reporter")
    assigned_to: str | None = Field(None, description="Assignee")
    steps_to_reproduce: str | None = Field(None, description="Reproduction steps")
    expected_behavior: str | None = Field(None, description="Expected behavior")
    actual_behavior: str | None = Field(None, description="Actual behavior")
    environment: str | None = Field(None, description="Environment")
    build_version: str | None = Field(None, description="Build version")
    tags: list[str] = Field(default_factory=list, description="Tags")


class DefectUpdateRequest(BaseModel):
    """Request to update defect fields (not status - use transition endpoint)."""

    title: str | None = Field(None, max_length=200, description="Updated title")
    description: str | None = Field(None, description="Updated description")
    priority: DefectPriority | None = Field(None, description="Updated priority")
    category: DefectCategory | None = Field(None, description="Updated category")
    component: str | None = Field(None, description="Updated component")
    assigned_to: str | None = Field(None, description="Updated assignee")
    steps_to_reproduce: str | None = Field(None, description="Updated reproduction steps")
    expected_behavior: str | None = Field(None, description="Updated expected behavior")
    actual_behavior: str | None = Field(None, description="Updated actual behavior")
    resolution_notes: str | None = Field(None, description="Resolution notes")
    tags: list[str] | None = Field(None, description="Updated tags")


class DefectTransitionRequest(BaseModel):
    """Request to transition a defect to a new status."""

    to_status: DefectStatus = Field(..., description="Target status")
    transitioned_by: str = Field(..., min_length=1, description="Who is performing the transition")
    reason: str | None = Field(None, description="Reason for transition")


class DefectCommentCreateRequest(BaseModel):
    """Request to add a comment to a defect."""

    author: str = Field(..., min_length=1, description="Comment author")
    content: str = Field(..., min_length=1, description="Comment content")


class DefectLinkRequest(BaseModel):
    """Request to link a defect as duplicate."""

    duplicate_of: str = Field(..., min_length=1, description="ID of the original defect")
    linked_by: str = Field(..., min_length=1, description="Who created the link")


class DefectListResponse(BaseModel):
    """Paginated list of defects."""

    defects: list[DefectRecord] = Field(default_factory=list)
    total: int = Field(0)
    limit: int = Field(50)
    offset: int = Field(0)


class DefectCommentListResponse(BaseModel):
    """List of comments for a defect."""

    comments: list[DefectComment] = Field(default_factory=list)
    total: int = Field(0)


class DefectTransitionListResponse(BaseModel):
    """List of transitions for a defect."""

    transitions: list[DefectTransition] = Field(default_factory=list)
    total: int = Field(0)


class SLABreachResponse(BaseModel):
    """List of SLA breaches / at-risk defects."""

    breaches: list[SLABreachRecord] = Field(default_factory=list)
    total: int = Field(0)
    breached_count: int = Field(0, description="Number actually breached")
    at_risk_count: int = Field(0, description="Number within 20% of deadline")


class TestEnvironmentCreateRequest(BaseModel):
    """Request to create a new test environment."""

    name: str = Field(..., min_length=1, max_length=100, description="Environment name")
    env_type: EnvironmentType = Field(..., description="Environment type")
    description: str | None = Field(None, description="Description")
    url: str | None = Field(None, description="Access URL")
    owner: str = Field(..., min_length=1, description="Owner")
    components: list[str] = Field(default_factory=list, description="Deployed components")


class TestEnvironmentUpdateRequest(BaseModel):
    """Request to update a test environment."""

    name: str | None = Field(None, max_length=100, description="Updated name")
    status: EnvironmentStatus | None = Field(None, description="Updated status")
    description: str | None = Field(None, description="Updated description")
    url: str | None = Field(None, description="Updated URL")
    owner: str | None = Field(None, description="Updated owner")
    components: list[str] | None = Field(None, description="Updated components")


class HealthCheckUpdateRequest(BaseModel):
    """Request to update health checks for an environment."""

    health_checks: list[HealthCheck] = Field(..., description="Updated health check results")


class TestEnvironmentListResponse(BaseModel):
    """List of test environments."""

    environments: list[TestEnvironment] = Field(default_factory=list)
    total: int = Field(0)
