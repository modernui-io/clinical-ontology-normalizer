"""Pydantic schemas for Observability Stack (DEVOPS-2).

Defines schemas for distributed tracing, Prometheus-compatible metrics,
alert rules, and dashboard aggregation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SpanStatus(str, Enum):
    """Status of a tracing span."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class MetricType(str, Enum):
    """Prometheus-style metric type."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class AlertSeverity(str, Enum):
    """Severity level for an alert rule."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCondition(str, Enum):
    """Comparison operator for alert thresholds."""

    GT = "gt"
    LT = "lt"
    EQ = "eq"


class AlertStatus(str, Enum):
    """State machine for alert lifecycle."""

    OK = "ok"
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"


# ---------------------------------------------------------------------------
# Tracing schemas
# ---------------------------------------------------------------------------


class SpanSchema(BaseModel):
    """A single span within a distributed trace."""

    trace_id: str = Field(..., description="Globally unique trace identifier")
    span_id: str = Field(..., description="Unique span identifier within trace")
    parent_span_id: str | None = Field(None, description="Parent span ID (None for root)")
    operation_name: str = Field(..., description="Name of the operation being traced")
    service_name: str = Field(default="clinical-ontology", description="Service that produced this span")
    start_time: datetime = Field(..., description="When the span started")
    end_time: datetime | None = Field(None, description="When the span ended (None if in-flight)")
    duration_ms: float | None = Field(None, ge=0, description="Duration in milliseconds")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Span outcome")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Key-value attributes")
    events: list[dict[str, Any]] = Field(default_factory=list, description="Timestamped events within span")


class TraceSchema(BaseModel):
    """A complete distributed trace (collection of spans)."""

    trace_id: str = Field(..., description="Globally unique trace identifier")
    root_span: SpanSchema | None = Field(None, description="Root span of the trace")
    spans: list[SpanSchema] = Field(default_factory=list, description="All spans in this trace")
    service_name: str = Field(default="clinical-ontology", description="Primary service")
    duration_ms: float | None = Field(None, ge=0, description="Total trace duration")
    span_count: int = Field(default=0, ge=0, description="Number of spans")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Overall trace status")


# ---------------------------------------------------------------------------
# Metrics schemas
# ---------------------------------------------------------------------------


class MetricLabelSet(BaseModel):
    """A unique combination of label values for a metric."""

    labels: dict[str, str] = Field(default_factory=dict, description="Label key-value pairs")
    value: float = Field(default=0.0, description="Current metric value")


class HistogramBucket(BaseModel):
    """A single histogram bucket."""

    le: float = Field(..., description="Upper bound (less-than-or-equal)")
    count: int = Field(default=0, ge=0, description="Cumulative count")


class HistogramData(BaseModel):
    """Full histogram state."""

    labels: dict[str, str] = Field(default_factory=dict, description="Label key-value pairs")
    buckets: list[HistogramBucket] = Field(default_factory=list, description="Cumulative buckets")
    count: int = Field(default=0, ge=0, description="Total observation count")
    sum: float = Field(default=0.0, description="Sum of observed values")


class MetricSchema(BaseModel):
    """A single metric definition and its current values."""

    name: str = Field(..., description="Metric name (e.g., screening_requests_total)")
    metric_type: MetricType = Field(..., description="Counter, gauge, or histogram")
    help_text: str = Field(default="", description="Description of the metric")
    label_names: list[str] = Field(default_factory=list, description="Declared label names")
    values: list[MetricLabelSet] = Field(
        default_factory=list,
        description="Current values per label set (for counter/gauge)",
    )
    histograms: list[HistogramData] = Field(
        default_factory=list,
        description="Histogram data per label set (for histogram type)",
    )


# ---------------------------------------------------------------------------
# Alert schemas
# ---------------------------------------------------------------------------


class AlertRuleSchema(BaseModel):
    """Definition of an alert rule."""

    name: str = Field(..., description="Unique alert rule name")
    metric_name: str = Field(..., description="Metric to evaluate")
    condition: AlertCondition = Field(..., description="Comparison operator")
    threshold: float = Field(..., description="Threshold value")
    duration_seconds: float = Field(
        default=0,
        ge=0,
        description="How long condition must hold before firing",
    )
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING, description="Alert severity")
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Label filter for the metric (empty = aggregate)",
    )
    description: str = Field(default="", description="Human-readable description")


class AlertStateSchema(BaseModel):
    """Current state of an alert."""

    rule_name: str = Field(..., description="Name of the alert rule")
    status: AlertStatus = Field(default=AlertStatus.OK, description="Current alert state")
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING)
    current_value: float | None = Field(None, description="Most recent metric value")
    threshold: float = Field(..., description="Threshold that triggers the alert")
    condition: AlertCondition = Field(..., description="Comparison operator")
    pending_since: datetime | None = Field(None, description="When the alert entered PENDING")
    firing_since: datetime | None = Field(None, description="When the alert started FIRING")
    resolved_at: datetime | None = Field(None, description="When the alert was RESOLVED")
    description: str = Field(default="")
    history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Timestamped state transition history",
    )


# ---------------------------------------------------------------------------
# Dashboard / Response schemas
# ---------------------------------------------------------------------------


class ServiceHealth(BaseModel):
    """Health summary for a single service component."""

    name: str = Field(..., description="Component name")
    status: str = Field(default="healthy", description="healthy / degraded / unhealthy")
    latency_p50_ms: float | None = Field(None, ge=0, description="p50 latency")
    latency_p99_ms: float | None = Field(None, ge=0, description="p99 latency")
    request_rate: float | None = Field(None, ge=0, description="Requests per second")
    error_rate: float | None = Field(None, ge=0.0, le=1.0, description="Error fraction")
    details: dict[str, Any] = Field(default_factory=dict)


class DashboardResponse(BaseModel):
    """Aggregated system health dashboard."""

    timestamp: datetime = Field(..., description="When this snapshot was generated")
    overall_status: str = Field(default="healthy", description="Overall system status")
    services: list[ServiceHealth] = Field(default_factory=list)
    active_alerts: int = Field(default=0, ge=0)
    total_traces_24h: int = Field(default=0, ge=0)
    error_rate_24h: float | None = Field(None, ge=0.0, le=1.0)
    key_metrics: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    """Response wrapper for metrics endpoint."""

    timestamp: datetime = Field(..., description="When metrics were collected")
    metrics: list[MetricSchema] = Field(default_factory=list)
    total: int = Field(default=0, ge=0, description="Total number of metrics")


class TracesResponse(BaseModel):
    """Response wrapper for traces endpoint."""

    traces: list[TraceSchema] = Field(default_factory=list)
    total: int = Field(default=0, ge=0, description="Total number of traces returned")
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)


class AlertsResponse(BaseModel):
    """Response wrapper for alerts endpoint."""

    timestamp: datetime = Field(..., description="When alerts were evaluated")
    alerts: list[AlertStateSchema] = Field(default_factory=list)
    firing_count: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)
    ok_count: int = Field(default=0, ge=0)
