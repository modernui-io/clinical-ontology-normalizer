"""Schemas for Drift Detection Service.

Provides structured types for monitoring model and data drift
in clinical trial patient screening pipelines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DriftSeverity(str, Enum):
    """Severity level of detected drift."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class DriftRecommendation(str, Enum):
    """Recommended action based on drift analysis."""

    STABLE = "stable"
    MONITOR = "monitor"
    RETRAIN = "retrain"


class MonitorType(str, Enum):
    """Type of drift monitor."""

    CATEGORICAL = "categorical"
    CONTINUOUS = "continuous"
    RATE = "rate"


# ---------------------------------------------------------------------------
# Baseline schemas
# ---------------------------------------------------------------------------


class BaselineCreate(BaseModel):
    """Request body for capturing a new baseline snapshot."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Human-readable baseline name"
    )
    feature_distributions: dict[str, list[float]] = Field(
        ...,
        description="Feature name -> histogram bin counts (distribution snapshot)",
    )
    sample_count: int = Field(
        ..., ge=1, description="Number of samples in this baseline"
    )


class BaselineResponse(BaseModel):
    """Response schema for a stored baseline."""

    id: str = Field(..., description="Unique baseline identifier")
    name: str = Field(..., description="Baseline name")
    created_at: datetime = Field(..., description="Creation timestamp")
    feature_distributions: dict[str, list[float]] = Field(
        ..., description="Feature distributions"
    )
    sample_count: int = Field(..., description="Sample count")


class BaselineListResponse(BaseModel):
    """Response for listing baselines."""

    total: int = Field(..., description="Total number of baselines")
    baselines: list[BaselineResponse] = Field(..., description="List of baselines")


# ---------------------------------------------------------------------------
# Drift analysis schemas
# ---------------------------------------------------------------------------


class FeatureDrift(BaseModel):
    """Drift analysis result for a single feature."""

    feature: str = Field(..., description="Feature name")
    psi: float = Field(..., description="Population Stability Index")
    severity: DriftSeverity = Field(..., description="Drift severity classification")
    p_value: float | None = Field(
        None, description="KS or chi-squared test p-value (if applicable)"
    )
    test_used: str = Field(
        default="psi", description="Statistical test used (psi, ks, chi_squared)"
    )


class DriftAnalysisRequest(BaseModel):
    """Request body for running drift analysis."""

    baseline_id: str = Field(..., description="Baseline to compare against")
    current_distributions: dict[str, list[float]] = Field(
        ..., description="Current feature distributions to analyze"
    )
    current_sample_count: int = Field(
        default=0, ge=0, description="Number of samples in current data"
    )


class DriftAnalysis(BaseModel):
    """Result of a drift analysis against a baseline."""

    baseline_id: str = Field(..., description="Baseline used for comparison")
    baseline_name: str = Field(..., description="Name of the baseline")
    overall_drift_score: float = Field(
        ..., description="Aggregated drift score across all features"
    )
    overall_severity: DriftSeverity = Field(..., description="Overall drift severity")
    feature_drifts: list[FeatureDrift] = Field(
        ..., description="Per-feature drift results"
    )
    recommendation: DriftRecommendation = Field(
        ..., description="Recommended action"
    )
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analysis timestamp",
    )


# ---------------------------------------------------------------------------
# Drift report schemas
# ---------------------------------------------------------------------------


class DriftReport(BaseModel):
    """Aggregated drift report with actionable recommendations."""

    report_id: str = Field(..., description="Unique report identifier")
    generated_at: datetime = Field(..., description="Report generation timestamp")
    overall_drift_score: float = Field(..., description="Overall drift score")
    overall_severity: DriftSeverity = Field(..., description="Overall severity")
    recommendation: DriftRecommendation = Field(..., description="Recommended action")
    feature_drifts: list[FeatureDrift] = Field(
        ..., description="Per-feature drift breakdown"
    )
    model_accuracy_current: float | None = Field(
        None, description="Current model accuracy (if available)"
    )
    model_accuracy_baseline: float | None = Field(
        None, description="Baseline model accuracy (if available)"
    )
    top_drifting_features: list[str] = Field(
        default_factory=list,
        description="Features with highest drift, sorted by PSI descending",
    )
    summary: str = Field(default="", description="Human-readable summary")


# ---------------------------------------------------------------------------
# Monitor schemas
# ---------------------------------------------------------------------------


class MonitorStatus(BaseModel):
    """Status of a drift monitor."""

    name: str = Field(..., description="Monitor name")
    monitor_type: MonitorType = Field(..., description="Type of monitor")
    description: str = Field(default="", description="Monitor description")
    is_active: bool = Field(default=True, description="Whether the monitor is active")
    last_value: float | None = Field(None, description="Last recorded value")
    data_points: int = Field(default=0, description="Number of recorded data points")
    drift_severity: DriftSeverity = Field(
        default=DriftSeverity.NONE, description="Current drift severity"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Monitor creation timestamp",
    )


class MonitorListResponse(BaseModel):
    """Response for listing monitors."""

    total: int = Field(..., description="Total number of monitors")
    monitors: list[MonitorStatus] = Field(..., description="List of monitors")


# ---------------------------------------------------------------------------
# Data recording schemas
# ---------------------------------------------------------------------------


class DataPointRecord(BaseModel):
    """Request body for recording a new data point."""

    monitor_name: str = Field(..., description="Name of the monitor to record to")
    value: float = Field(..., description="Numeric value to record")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    timestamp: datetime | None = Field(
        None, description="Override timestamp (defaults to now)"
    )


class DataPointResponse(BaseModel):
    """Response after recording a data point."""

    monitor_name: str = Field(..., description="Monitor name")
    value: float = Field(..., description="Recorded value")
    timestamp: datetime = Field(..., description="Recording timestamp")
    total_points: int = Field(..., description="Total data points for this monitor")


# ---------------------------------------------------------------------------
# Drift history schemas
# ---------------------------------------------------------------------------


class DriftHistoryEntry(BaseModel):
    """A single entry in the drift score history."""

    timestamp: datetime = Field(..., description="Timestamp")
    drift_score: float = Field(..., description="Drift score at this time")
    severity: DriftSeverity = Field(..., description="Severity at this time")


class DriftHistory(BaseModel):
    """Drift score over time."""

    monitor_name: str | None = Field(
        None, description="Monitor name (if scoped to a monitor)"
    )
    entries: list[DriftHistoryEntry] = Field(
        ..., description="Drift score history entries"
    )
    total: int = Field(..., description="Total number of entries")
