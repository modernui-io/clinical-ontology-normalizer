"""Pydantic schemas for A/B Testing / Experiment framework.

VP-DS-3: A/B Testing Framework for clinical trial patient recruitment.

Defines schemas for experiment lifecycle management, variant assignment,
outcome tracking, and statistical analysis results.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExperimentStatus(str, Enum):
    """Experiment lifecycle states."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MetricType(str, Enum):
    """Type of metric being measured."""

    CONTINUOUS = "continuous"  # e.g., screening score, time
    BINARY = "binary"  # e.g., pass/fail


# ---------------------------------------------------------------------------
# Variant Definition
# ---------------------------------------------------------------------------


class VariantDefinition(BaseModel):
    """Definition of an experiment variant (arm)."""

    name: str = Field(..., description="Variant name (e.g., 'control', 'treatment')")
    weight: float = Field(
        ...,
        gt=0,
        le=100,
        description="Assignment weight as percentage (e.g., 50.0 for 50%)",
    )


# ---------------------------------------------------------------------------
# Experiment CRUD Schemas
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    """Schema for creating a new experiment."""

    name: str = Field(..., min_length=1, max_length=200, description="Experiment name")
    description: str | None = Field(None, description="Experiment description")
    hypothesis: str | None = Field(None, description="Hypothesis being tested")
    variants: list[VariantDefinition] = Field(
        ...,
        min_length=2,
        description="List of variants with weights (must sum to 100)",
    )
    metric: str = Field(
        ...,
        description="Primary metric to measure (e.g., screening_pass_rate, time_to_eligible)",
    )
    metric_type: MetricType = Field(
        default=MetricType.CONTINUOUS,
        description="Whether the metric is continuous or binary",
    )
    target_sample_size: int = Field(
        default=100,
        ge=10,
        description="Minimum observations per variant for statistical validity",
    )
    start_date: datetime | None = Field(None, description="Scheduled start date")
    end_date: datetime | None = Field(None, description="Scheduled end date")


class ExperimentResponse(BaseModel):
    """Full experiment response."""

    id: str
    name: str
    description: str | None = None
    hypothesis: str | None = None
    status: ExperimentStatus
    variants: list[VariantDefinition]
    metric: str
    metric_type: MetricType
    target_sample_size: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    total_assignments: int = 0
    total_outcomes: int = 0


class ExperimentListResponse(BaseModel):
    """Paginated experiment list response."""

    experiments: list[ExperimentResponse]
    total: int


# ---------------------------------------------------------------------------
# Assignment & Outcome
# ---------------------------------------------------------------------------


class AssignmentRequest(BaseModel):
    """Request to assign a patient to a variant."""

    patient_id: str = Field(..., description="Patient identifier")


class AssignmentResponse(BaseModel):
    """Variant assignment response."""

    experiment_id: str
    patient_id: str
    variant: str
    bucket: int = Field(description="Hash bucket (0-99) used for assignment")


class OutcomeRecord(BaseModel):
    """Record an outcome event for an experiment."""

    patient_id: str = Field(..., description="Patient identifier")
    metric_name: str = Field(..., description="Metric name (must match experiment metric)")
    value: float = Field(..., description="Metric value (0/1 for binary, any float for continuous)")


# ---------------------------------------------------------------------------
# Statistical Results
# ---------------------------------------------------------------------------


class VariantStats(BaseModel):
    """Statistics for a single variant."""

    name: str
    count: int = 0
    mean: float = 0.0
    std_dev: float = 0.0
    min_value: float | None = None
    max_value: float | None = None


class StatisticalResult(BaseModel):
    """Result of statistical comparison between variants."""

    variant_a: VariantStats
    variant_b: VariantStats
    test_type: str = Field(description="Type of test: t-test or z-test")
    test_statistic: float
    p_value: float
    significant: bool = Field(description="Whether p < 0.05")
    effect_size: float = Field(description="Cohen's d for continuous, h for binary")
    effect_size_interpretation: str = Field(description="small/medium/large")
    confidence_interval_lower: float
    confidence_interval_upper: float
    confidence_level: float = 0.95


class SequentialTestResult(BaseModel):
    """Result of sequential testing with O'Brien-Fleming spending function."""

    current_look: int = Field(description="Which interim look this is (1-indexed)")
    total_planned_looks: int
    nominal_alpha: float = Field(description="Overall type I error rate")
    adjusted_alpha: float = Field(description="Alpha boundary for this look")
    observed_p_value: float
    can_stop_early: bool = Field(
        description="Whether the result crosses the spending boundary"
    )
    cumulative_information_fraction: float = Field(
        description="Fraction of total planned sample collected"
    )


class PowerAnalysis(BaseModel):
    """Power analysis result."""

    current_sample_per_variant: int
    target_sample_per_variant: int
    estimated_power: float = Field(description="Estimated statistical power (0-1)")
    is_adequately_powered: bool = Field(
        description="Whether power >= 0.80"
    )
    minimum_detectable_effect: float = Field(
        description="Smallest effect size detectable with current sample"
    )
    samples_needed_for_80_power: int = Field(
        description="Sample size per variant needed for 80% power"
    )


class ExperimentResults(BaseModel):
    """Complete experiment results."""

    experiment_id: str
    experiment_name: str
    status: ExperimentStatus
    variant_stats: list[VariantStats]
    pairwise_comparisons: list[StatisticalResult]
    sequential_test: SequentialTestResult | None = None
    power_analysis: PowerAnalysis | None = None
    recommendation: str = Field(
        description="Human-readable recommendation based on results"
    )


# ---------------------------------------------------------------------------
# Experiment Templates
# ---------------------------------------------------------------------------


class ExperimentTemplate(BaseModel):
    """Pre-defined experiment template."""

    template_id: str
    name: str
    description: str
    hypothesis: str
    metric: str
    metric_type: MetricType
    default_variants: list[VariantDefinition]
    target_sample_size: int


class TemplateListResponse(BaseModel):
    """List of available experiment templates."""

    templates: list[ExperimentTemplate]
