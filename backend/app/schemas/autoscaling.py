"""Pydantic schemas for Auto-Scaling Policies and Event-Driven Scaling (DEVOPS-3).

Defines schemas for scaling policies, scaling targets, scaling decisions,
scaling history events, KEDA ScaledObject specs, and predictive scaling.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ScalingPolicyType(str, Enum):
    """Type of scaling policy trigger."""

    CPU_THRESHOLD = "cpu_threshold"
    MEMORY_THRESHOLD = "memory_threshold"
    REQUEST_RATE = "request_rate"
    QUEUE_DEPTH = "queue_depth"
    SCHEDULE = "schedule"
    CUSTOM_METRIC = "custom_metric"


class ScalingDirection(str, Enum):
    """Direction of a scaling action."""

    UP = "up"
    DOWN = "down"
    NONE = "none"


class ScalingTargetName(str, Enum):
    """Supported scaling target services."""

    BACKEND_API = "backend_api"
    FHIR_WORKER = "fhir_worker"
    NLP_WORKER = "nlp_worker"
    SCREENING_WORKER = "screening_worker"


class PolicyStatus(str, Enum):
    """Whether a scaling policy is active or disabled."""

    ACTIVE = "active"
    DISABLED = "disabled"


class TrendDirection(str, Enum):
    """Detected metric trend direction."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


# ---------------------------------------------------------------------------
# Scaling Target
# ---------------------------------------------------------------------------


class ScalingTargetConfig(BaseModel):
    """Configuration for a scaling target (service)."""

    name: ScalingTargetName = Field(..., description="Target service name")
    min_replicas: int = Field(..., ge=1, description="Minimum replica count")
    max_replicas: int = Field(..., ge=1, description="Maximum replica count")
    default_replicas: int = Field(..., ge=1, description="Default replica count")
    current_replicas: int = Field(..., ge=0, description="Current replica count")
    description: str = Field(default="", description="Human-readable description")


class ScalingTargetStatus(BaseModel):
    """Current status of a scaling target."""

    name: ScalingTargetName = Field(..., description="Target service name")
    current_replicas: int = Field(..., ge=0, description="Current replica count")
    min_replicas: int = Field(..., ge=1, description="Minimum replica count")
    max_replicas: int = Field(..., ge=1, description="Maximum replica count")
    desired_replicas: int = Field(..., ge=0, description="Desired replica count")
    last_scale_time: datetime | None = Field(None, description="When last scaling occurred")
    active_policies: int = Field(default=0, ge=0, description="Number of active policies")


class ScalingTargetsResponse(BaseModel):
    """Response listing all scaling targets."""

    targets: list[ScalingTargetStatus] = Field(default_factory=list)
    timestamp: datetime = Field(..., description="When this snapshot was taken")


# ---------------------------------------------------------------------------
# Schedule Config
# ---------------------------------------------------------------------------


class ScheduleConfig(BaseModel):
    """Schedule configuration for time-based scaling."""

    days_of_week: list[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4],
        description="Days of week (0=Monday, 6=Sunday)",
    )
    start_hour: int = Field(default=8, ge=0, le=23, description="Start hour (24h format)")
    end_hour: int = Field(default=18, ge=0, le=23, description="End hour (24h format)")
    timezone: str = Field(default="US/Eastern", description="Timezone for schedule")


# ---------------------------------------------------------------------------
# Scaling Policy
# ---------------------------------------------------------------------------


class ScalingPolicyBase(BaseModel):
    """Base fields for a scaling policy."""

    name: str = Field(..., min_length=1, max_length=128, description="Policy name")
    description: str = Field(default="", description="Human-readable description")
    policy_type: ScalingPolicyType = Field(..., description="Type of scaling trigger")
    target: ScalingTargetName = Field(..., description="Target service to scale")
    threshold: float = Field(default=70.0, ge=0, description="Threshold value to trigger scaling")
    min_replicas: int | None = Field(None, ge=1, description="Override minimum replicas")
    max_replicas: int | None = Field(None, ge=1, description="Override maximum replicas")
    desired_replicas: int | None = Field(
        None, ge=1, description="Desired replicas (for schedule policies)"
    )
    cooldown_seconds: int = Field(
        default=300, ge=0, description="Cooldown period after scale-up (seconds)"
    )
    stabilization_seconds: int = Field(
        default=600, ge=0, description="Stabilization period before scale-down (seconds)"
    )
    scale_up_step: int = Field(default=2, ge=1, description="Replicas to add per scale-up")
    scale_down_step: int = Field(default=1, ge=1, description="Replicas to remove per scale-down")
    schedule: ScheduleConfig | None = Field(None, description="Schedule config for schedule policies")
    metric_name: str | None = Field(None, description="Custom metric name (for custom_metric type)")
    status: PolicyStatus = Field(default=PolicyStatus.ACTIVE, description="Policy status")


class ScalingPolicyCreate(ScalingPolicyBase):
    """Schema for creating a new scaling policy."""

    pass


class ScalingPolicyUpdate(BaseModel):
    """Schema for updating a scaling policy."""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    threshold: float | None = Field(None, ge=0)
    min_replicas: int | None = Field(None, ge=1)
    max_replicas: int | None = Field(None, ge=1)
    desired_replicas: int | None = Field(None, ge=1)
    cooldown_seconds: int | None = Field(None, ge=0)
    stabilization_seconds: int | None = Field(None, ge=0)
    scale_up_step: int | None = Field(None, ge=1)
    scale_down_step: int | None = Field(None, ge=1)
    schedule: ScheduleConfig | None = None
    metric_name: str | None = None
    status: PolicyStatus | None = None


class ScalingPolicy(ScalingPolicyBase):
    """Full scaling policy with server-assigned fields."""

    id: str = Field(..., description="Unique policy identifier")
    created_at: datetime = Field(..., description="When the policy was created")
    updated_at: datetime = Field(..., description="When the policy was last updated")
    last_triggered: datetime | None = Field(None, description="When policy last triggered a scaling action")
    trigger_count: int = Field(default=0, ge=0, description="Number of times this policy has triggered")


class ScalingPoliciesResponse(BaseModel):
    """Response listing scaling policies."""

    policies: list[ScalingPolicy] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Scaling Decision
# ---------------------------------------------------------------------------


class ScalingDecision(BaseModel):
    """Result of evaluating scaling policies against current metrics."""

    target: ScalingTargetName = Field(..., description="Target service")
    direction: ScalingDirection = Field(..., description="Scaling direction")
    current_replicas: int = Field(..., ge=0, description="Current replica count")
    desired_replicas: int = Field(..., ge=0, description="Desired replica count")
    reason: str = Field(default="", description="Human-readable reason for the decision")
    triggered_policies: list[str] = Field(
        default_factory=list, description="Policy IDs that triggered this decision"
    )
    metric_values: dict[str, float] = Field(
        default_factory=dict, description="Current metric values considered"
    )
    cooldown_active: bool = Field(
        default=False, description="Whether cooldown is preventing this action"
    )
    timestamp: datetime = Field(..., description="When decision was made")


class ScalingEvaluationRequest(BaseModel):
    """Request to evaluate scaling for specific metrics."""

    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Current metric values, e.g. {'cpu_percent': 85, 'queue_depth': 120}",
    )
    target: ScalingTargetName | None = Field(
        None, description="Evaluate only for a specific target (optional)"
    )


class ScalingEvaluationResponse(BaseModel):
    """Response from scaling evaluation."""

    decisions: list[ScalingDecision] = Field(default_factory=list)
    evaluated_policies: int = Field(default=0, ge=0)
    timestamp: datetime = Field(..., description="When evaluation was performed")


# ---------------------------------------------------------------------------
# Scaling History
# ---------------------------------------------------------------------------


class ScalingEvent(BaseModel):
    """Record of a scaling event."""

    id: str = Field(..., description="Unique event identifier")
    target: ScalingTargetName = Field(..., description="Target service that was scaled")
    direction: ScalingDirection = Field(..., description="Scaling direction")
    from_replicas: int = Field(..., ge=0, description="Previous replica count")
    to_replicas: int = Field(..., ge=0, description="New replica count")
    reason: str = Field(default="", description="Why scaling occurred")
    policy_id: str | None = Field(None, description="Policy that triggered the event")
    policy_name: str | None = Field(None, description="Name of the triggering policy")
    metric_value: float | None = Field(None, description="Metric value at the time")
    threshold: float | None = Field(None, description="Threshold that was crossed")
    timestamp: datetime = Field(..., description="When the scaling event occurred")


class ScalingHistoryResponse(BaseModel):
    """Response listing scaling history events."""

    events: list[ScalingEvent] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# KEDA ScaledObject Spec
# ---------------------------------------------------------------------------


class KEDAScaledObjectSpec(BaseModel):
    """KEDA ScaledObject YAML specification."""

    target: ScalingTargetName = Field(..., description="Target service")
    yaml_content: str = Field(..., description="Generated KEDA ScaledObject YAML")
    api_version: str = Field(default="keda.sh/v1alpha1", description="KEDA API version")
    kind: str = Field(default="ScaledObject", description="Kubernetes resource kind")
    metadata: dict[str, Any] = Field(default_factory=dict, description="KEDA metadata")


# ---------------------------------------------------------------------------
# Predictive Scaling
# ---------------------------------------------------------------------------


class MetricTrend(BaseModel):
    """Detected trend in a metric's history."""

    metric_name: str = Field(..., description="Name of the metric")
    direction: TrendDirection = Field(..., description="Trend direction")
    slope: float = Field(default=0.0, description="Slope of the trend line")
    confidence: float = Field(default=0.0, ge=0, le=1, description="Confidence in the trend (0-1)")
    data_points: int = Field(default=0, ge=0, description="Number of data points analyzed")
    predicted_value: float | None = Field(
        None, description="Predicted value at next interval"
    )
    recommendation: str = Field(default="", description="Scaling recommendation based on trend")


class PredictiveScalingReport(BaseModel):
    """Predictive scaling analysis report."""

    target: ScalingTargetName = Field(..., description="Target service")
    trends: list[MetricTrend] = Field(default_factory=list)
    should_prescale: bool = Field(default=False, description="Whether proactive scaling is recommended")
    recommended_replicas: int | None = Field(None, description="Recommended replica count")
    analysis_window_minutes: int = Field(default=30, description="Minutes of history analyzed")
    timestamp: datetime = Field(..., description="When analysis was performed")
