"""Operational Dashboard & SLA Management schemas (COO-5).

Pydantic v2 models for the operational dashboard: SLA definitions
and measurements, system health, trial operations summaries,
automated processes, alerts, and the unified dashboard response.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SLACategory(str, Enum):
    """Categories of SLA metrics tracked by the platform."""

    API_UPTIME = "api_uptime"
    NLP_TURNAROUND = "nlp_turnaround"
    DATA_FRESHNESS = "data_freshness"
    SCREENING_ACCURACY = "screening_accuracy"
    RESPONSE_TIME = "response_time"
    COMPLIANCE_REPORTING = "compliance_reporting"


class SLAStatus(str, Enum):
    """Current status of an SLA relative to its target."""

    MEETING = "meeting"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    NOT_MEASURED = "not_measured"


class OperationalStatus(str, Enum):
    """Overall operational health of a service or the platform."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    IMPAIRED = "impaired"
    DOWN = "down"


class AlertSeverity(str, Enum):
    """Severity level for an operational alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ProcessStatus(str, Enum):
    """Execution status of an automated process."""

    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class SLADefinition(BaseModel):
    """An SLA definition with its current status and breach history."""

    id: str
    name: str
    category: SLACategory
    target_value: float = Field(..., description="Target threshold (e.g. 99.9 for uptime %)")
    unit: str = Field(..., description="Unit of measurement (%, seconds, hours, etc.)")
    measurement_period_hours: int = Field(24, description="How often this SLA is measured")
    current_value: float | None = Field(None, description="Most recent measured value")
    status: SLAStatus = SLAStatus.NOT_MEASURED
    breach_count_30d: int = Field(0, description="Number of breaches in the last 30 days")
    last_measured: datetime | None = None
    client_id: str | None = Field(None, description="Client this SLA belongs to, if any")
    penalty_amount: float | None = Field(None, description="Financial penalty per breach ($)")


class SLAMeasurement(BaseModel):
    """A single SLA measurement point."""

    id: str
    sla_id: str
    value: float
    measured_at: datetime
    meets_target: bool


class OperationalMetric(BaseModel):
    """A single operational KPI with trend data."""

    name: str
    value: float
    unit: str
    trend: str = Field("stable", description="up, down, or stable")
    previous_value: float | None = None
    change_percent: float | None = None


class TrialOperationsSummary(BaseModel):
    """High-level operational summary for one clinical trial."""

    trial_id: str
    trial_name: str
    status: str = "active"
    patients_screened: int = 0
    patients_enrolled: int = 0
    enrollment_rate_per_week: float = 0.0
    site_count: int = 0
    active_sites: int = 0
    screen_failure_rate: float = 0.0


class SystemHealthStatus(BaseModel):
    """Health snapshot of a single platform service."""

    service_name: str
    status: OperationalStatus = OperationalStatus.HEALTHY
    uptime_percent_30d: float = 100.0
    last_incident: datetime | None = None
    response_time_p99_ms: float = 0.0
    error_rate_percent: float = 0.0


class AutomatedProcess(BaseModel):
    """An automated/scheduled process tracked by the platform."""

    id: str
    name: str
    process_type: str = "batch"
    status: ProcessStatus = ProcessStatus.SCHEDULED
    schedule_cron: str | None = None
    last_run: datetime | None = None
    next_run: datetime | None = None
    success_rate_30d: float = 100.0
    avg_duration_seconds: float = 0.0
    last_error: str | None = None


class OperationalAlert(BaseModel):
    """An operational alert or notification."""

    id: str
    severity: AlertSeverity = AlertSeverity.INFO
    title: str
    message: str
    source: str = "system"
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None


class SLASummary(BaseModel):
    """Aggregated SLA summary for the dashboard."""

    total_slas: int = 0
    meeting: int = 0
    at_risk: int = 0
    breached: int = 0
    not_measured: int = 0
    overall_compliance_rate: float = 0.0


class OperationalDashboard(BaseModel):
    """Full operational dashboard payload."""

    timestamp: datetime
    overall_status: OperationalStatus = OperationalStatus.HEALTHY
    active_trials: int = 0
    total_patients_pipeline: int = 0
    total_sites: int = 0
    system_health: list[SystemHealthStatus] = []
    trial_summaries: list[TrialOperationsSummary] = []
    sla_summary: SLASummary = Field(default_factory=SLASummary)
    automated_processes: list[AutomatedProcess] = []
    alerts: list[OperationalAlert] = []
    key_metrics: list[OperationalMetric] = []


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SLACreateRequest(BaseModel):
    """Request body to create a new SLA definition."""

    name: str
    category: SLACategory
    target_value: float
    unit: str
    measurement_period_hours: int = 24
    client_id: str | None = None
    penalty_amount: float | None = None


class SLAUpdateRequest(BaseModel):
    """Request body to update an existing SLA definition."""

    name: str | None = None
    target_value: float | None = None
    unit: str | None = None
    measurement_period_hours: int | None = None
    client_id: str | None = None
    penalty_amount: float | None = None


class SLAListResponse(BaseModel):
    """Paginated list of SLA definitions."""

    items: list[SLADefinition] = []
    total: int = 0


class SLAMeasurementCreateRequest(BaseModel):
    """Request body to record an SLA measurement."""

    sla_id: str
    value: float
    measured_at: datetime | None = None


class ProcessCreateRequest(BaseModel):
    """Request body to create an automated process."""

    name: str
    process_type: str = "batch"
    schedule_cron: str | None = None
    status: ProcessStatus = ProcessStatus.SCHEDULED


class ProcessUpdateRequest(BaseModel):
    """Request body to update an automated process."""

    name: str | None = None
    status: ProcessStatus | None = None
    schedule_cron: str | None = None
    last_error: str | None = None


class ProcessListResponse(BaseModel):
    """List of automated processes."""

    items: list[AutomatedProcess] = []
    total: int = 0


class AlertCreateRequest(BaseModel):
    """Request body to create an operational alert."""

    severity: AlertSeverity = AlertSeverity.INFO
    title: str
    message: str
    source: str = "system"


class AlertListResponse(BaseModel):
    """List of operational alerts."""

    items: list[OperationalAlert] = []
    total: int = 0


class DashboardResponse(BaseModel):
    """Wrapper for the full dashboard response."""

    dashboard: OperationalDashboard


class SLAComplianceTrend(BaseModel):
    """Historical SLA compliance for a single period."""

    period: str
    compliance_rate: float
    measurements_count: int
    breaches: int


class CapacityAssessment(BaseModel):
    """Operational capacity assessment."""

    overall_capacity_percent: float = Field(
        ..., description="How much capacity is currently utilized"
    )
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    storage_utilization: float = 0.0
    active_connections: int = 0
    max_connections: int = 1000
    recommendation: str = "normal"
