"""Schemas for Model Evaluation Framework.

Provides structured types for tracking and comparing ML model performance
across NLP extraction, OMOP mapping, assertion classification, and trial matching.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Types of ML models tracked by the evaluation framework."""

    NLP_EXTRACTION = "nlp_extraction"
    OMOP_MAPPING = "omop_mapping"
    ASSERTION_CLASSIFIER = "assertion_classifier"
    TRIAL_MATCHING = "trial_matching"


class ModelInfo(BaseModel):
    """Metadata for a registered model."""

    name: str = Field(..., min_length=1, max_length=255, description="Model name")
    version: str = Field(..., min_length=1, max_length=64, description="Model version")
    model_type: ModelType = Field(..., description="Type of ML model")
    description: str = Field(default="", description="Human-readable description")
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Registration timestamp",
    )


class EvaluationRun(BaseModel):
    """A single evaluation run capturing metrics for a model version."""

    id: str = Field(..., description="Unique evaluation run identifier")
    model_name: str = Field(..., description="Name of the evaluated model")
    model_version: str = Field(..., description="Version of the evaluated model")
    dataset_name: str = Field(..., description="Name of the evaluation dataset")
    metrics: dict[str, float] = Field(
        ..., description="Evaluation metrics (e.g., precision, recall, f1)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional run metadata"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Evaluation timestamp",
    )


class MetricComparison(BaseModel):
    """Comparison of a single metric between two model versions."""

    metric: str = Field(..., description="Metric name")
    value_a: float = Field(..., description="Value for version A")
    value_b: float = Field(..., description="Value for version B")
    diff: float = Field(..., description="Absolute difference (B - A)")
    diff_pct: float = Field(..., description="Percentage change from A to B")
    improved: bool = Field(..., description="Whether version B improved over A")


class ComparisonResult(BaseModel):
    """Result of comparing two model versions."""

    model_name: str = Field(..., description="Model name")
    version_a: str = Field(..., description="Baseline version")
    version_b: str = Field(..., description="Comparison version")
    metric_comparisons: list[MetricComparison] = Field(
        ..., description="Per-metric comparisons"
    )


class RegressionCheck(BaseModel):
    """Result of checking whether the latest version regressed on a metric."""

    model_name: str = Field(..., description="Model name")
    metric: str = Field(..., description="Metric being checked")
    current_value: float = Field(..., description="Current (latest) metric value")
    previous_value: float = Field(..., description="Previous metric value")
    threshold: float = Field(..., description="Acceptable degradation threshold")
    is_regression: bool = Field(
        ..., description="True if current is worse than previous beyond threshold"
    )


# --- Request schemas for API endpoints ---


class RegisterModelRequest(BaseModel):
    """Request body for registering a model."""

    name: str = Field(..., min_length=1, max_length=255, description="Model name")
    version: str = Field(..., min_length=1, max_length=64, description="Model version")
    model_type: ModelType = Field(..., description="Type of ML model")
    description: str = Field(default="", description="Human-readable description")


class RecordEvaluationRequest(BaseModel):
    """Request body for recording an evaluation run."""

    model_name: str = Field(..., description="Name of the evaluated model")
    model_version: str = Field(..., description="Version of the evaluated model")
    dataset_name: str = Field(..., description="Name of the evaluation dataset")
    metrics: dict[str, float] = Field(..., description="Evaluation metrics")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional run metadata"
    )


class ModelListResponse(BaseModel):
    """Response for listing registered models."""

    total: int = Field(..., description="Total number of models")
    models: list[ModelInfo] = Field(..., description="List of registered models")
