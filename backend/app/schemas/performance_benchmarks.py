"""Schemas for Performance Benchmarking & SLA Management (CTO-9).

Provides structured types for tracking API latency benchmarks,
SLA definitions, compliance monitoring, trend analysis, and
regression detection across a pharma-regulated clinical trial
patient recruitment platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BenchmarkCategory(str, Enum):
    """Category of performance benchmark."""

    API_LATENCY = "api_latency"
    DATABASE_QUERY = "database_query"
    NLP_PIPELINE = "nlp_pipeline"
    FHIR_IMPORT = "fhir_import"
    TRIAL_SCREENING = "trial_screening"
    KG_QUERY = "kg_query"
    DOCUMENT_PROCESSING = "document_processing"
    BULK_EXPORT = "bulk_export"


class SLATier(str, Enum):
    """SLA tier with target p99 latency ceiling.

    PLATINUM: p99 < 100ms  (real-time interactive)
    GOLD:     p99 < 500ms  (sub-second UX)
    SILVER:   p99 < 2s     (tolerable latency)
    BRONZE:   p99 < 10s    (batch-acceptable)
    """

    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


class Environment(str, Enum):
    """Deployment environment."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class TrendDirection(str, Enum):
    """Direction of a performance trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


# ---------------------------------------------------------------------------
# Benchmark result
# ---------------------------------------------------------------------------


class BenchmarkResult(BaseModel):
    """A single benchmark measurement."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique benchmark result ID")
    category: BenchmarkCategory = Field(..., description="Benchmark category")
    operation_name: str = Field(..., description="Operation being measured")
    p50_ms: float = Field(..., ge=0, description="50th percentile latency (ms)")
    p95_ms: float = Field(..., ge=0, description="95th percentile latency (ms)")
    p99_ms: float = Field(..., ge=0, description="99th percentile latency (ms)")
    max_ms: float = Field(..., ge=0, description="Maximum observed latency (ms)")
    min_ms: float = Field(..., ge=0, description="Minimum observed latency (ms)")
    mean_ms: float = Field(..., ge=0, description="Mean latency (ms)")
    std_dev_ms: float = Field(..., ge=0, description="Standard deviation (ms)")
    throughput_rps: float = Field(..., ge=0, description="Throughput (requests/sec)")
    sample_count: int = Field(..., ge=1, description="Number of samples")
    measured_at: datetime = Field(..., description="When the measurement was taken")
    environment: Environment = Field(..., description="Deployment environment")
    version: str = Field(..., description="Application version")


class BenchmarkResultCreate(BaseModel):
    """Request body for recording a benchmark result."""

    model_config = ConfigDict(from_attributes=True)

    category: BenchmarkCategory = Field(..., description="Benchmark category")
    operation_name: str = Field(
        ..., min_length=1, max_length=255, description="Operation being measured"
    )
    p50_ms: float = Field(..., ge=0)
    p95_ms: float = Field(..., ge=0)
    p99_ms: float = Field(..., ge=0)
    max_ms: float = Field(..., ge=0)
    min_ms: float = Field(..., ge=0)
    mean_ms: float = Field(..., ge=0)
    std_dev_ms: float = Field(0.0, ge=0)
    throughput_rps: float = Field(0.0, ge=0)
    sample_count: int = Field(1, ge=1)
    environment: Environment = Field(Environment.DEV)
    version: str = Field("1.0.0")


class BenchmarkListResponse(BaseModel):
    """Paginated list of benchmark results."""

    total: int = Field(..., description="Total results matching filter")
    results: list[BenchmarkResult] = Field(..., description="Benchmark results")


# ---------------------------------------------------------------------------
# SLA definition
# ---------------------------------------------------------------------------


class SLADefinition(BaseModel):
    """Defines an SLA target for a specific operation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique SLA ID")
    category: BenchmarkCategory = Field(..., description="Benchmark category")
    operation_name: str = Field(..., description="Target operation")
    tier: SLATier = Field(..., description="SLA tier")
    target_p50_ms: float = Field(..., ge=0, description="Target p50 (ms)")
    target_p95_ms: float = Field(..., ge=0, description="Target p95 (ms)")
    target_p99_ms: float = Field(..., ge=0, description="Target p99 (ms)")
    target_throughput_rps: float = Field(0.0, ge=0, description="Target throughput")
    measurement_window_hours: int = Field(
        24, ge=1, description="Measurement window in hours"
    )
    breach_threshold_pct: float = Field(
        5.0,
        ge=0,
        le=100,
        description="Percentage of consecutive breaches before alerting",
    )


class SLADefinitionCreate(BaseModel):
    """Request body for creating an SLA definition."""

    model_config = ConfigDict(from_attributes=True)

    category: BenchmarkCategory
    operation_name: str = Field(..., min_length=1, max_length=255)
    tier: SLATier
    target_p50_ms: float = Field(..., ge=0)
    target_p95_ms: float = Field(..., ge=0)
    target_p99_ms: float = Field(..., ge=0)
    target_throughput_rps: float = Field(0.0, ge=0)
    measurement_window_hours: int = Field(24, ge=1)
    breach_threshold_pct: float = Field(5.0, ge=0, le=100)


class SLADefinitionUpdate(BaseModel):
    """Request body for updating an SLA definition."""

    model_config = ConfigDict(from_attributes=True)

    tier: SLATier | None = None
    target_p50_ms: float | None = Field(None, ge=0)
    target_p95_ms: float | None = Field(None, ge=0)
    target_p99_ms: float | None = Field(None, ge=0)
    target_throughput_rps: float | None = Field(None, ge=0)
    measurement_window_hours: int | None = Field(None, ge=1)
    breach_threshold_pct: float | None = Field(None, ge=0, le=100)


class SLAListResponse(BaseModel):
    """List of SLA definitions."""

    total: int = Field(..., description="Total SLAs")
    slas: list[SLADefinition] = Field(..., description="SLA definitions")


# ---------------------------------------------------------------------------
# SLA compliance status
# ---------------------------------------------------------------------------


class SLAStatus(BaseModel):
    """Current compliance status for a single SLA."""

    model_config = ConfigDict(from_attributes=True)

    sla_id: str = Field(..., description="SLA definition ID")
    operation_name: str = Field(..., description="Operation name")
    category: BenchmarkCategory = Field(..., description="Category")
    tier: SLATier = Field(..., description="SLA tier")
    current_p50: float = Field(..., description="Current measured p50 (ms)")
    current_p95: float = Field(..., description="Current measured p95 (ms)")
    current_p99: float = Field(..., description="Current measured p99 (ms)")
    current_throughput: float = Field(..., description="Current throughput (rps)")
    p50_met: bool = Field(..., description="p50 target met")
    p95_met: bool = Field(..., description="p95 target met")
    p99_met: bool = Field(..., description="p99 target met")
    throughput_met: bool = Field(..., description="Throughput target met")
    overall_compliance: bool = Field(..., description="All targets met")
    compliance_pct_30d: float = Field(
        ..., ge=0, le=100, description="30-day compliance percentage"
    )
    last_breach: datetime | None = Field(None, description="Last breach timestamp")
    breach_count_30d: int = Field(0, ge=0, description="Breaches in last 30 days")


class SLAComplianceSummary(BaseModel):
    """Batch compliance check results."""

    total_slas: int
    compliant: int
    non_compliant: int
    compliance_rate: float = Field(..., ge=0, le=100)
    statuses: list[SLAStatus]


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------


class TrendDataPoint(BaseModel):
    """Single data point in a performance trend."""

    timestamp: datetime
    p50: float
    p95: float
    p99: float
    throughput: float


class PerformanceTrend(BaseModel):
    """Performance trend for an operation over time."""

    model_config = ConfigDict(from_attributes=True)

    category: BenchmarkCategory
    operation_name: str
    data_points: list[TrendDataPoint] = Field(
        default_factory=list, description="Historical data points"
    )
    trend_direction: TrendDirection = Field(
        TrendDirection.STABLE, description="Overall trend direction"
    )
    regression_detected: bool = Field(
        False, description="Whether a regression was detected"
    )


class RegressionAlert(BaseModel):
    """A detected performance regression."""

    category: BenchmarkCategory
    operation_name: str
    previous_p99: float
    current_p99: float
    change_pct: float
    detected_at: datetime


class RegressionReport(BaseModel):
    """Report of all detected regressions."""

    total_operations_scanned: int
    regressions_found: int
    alerts: list[RegressionAlert]


# ---------------------------------------------------------------------------
# Benchmark suites
# ---------------------------------------------------------------------------


class BenchmarkSuiteEntry(BaseModel):
    """A single benchmark entry in a suite."""

    category: BenchmarkCategory
    operation_name: str


class BenchmarkSuite(BaseModel):
    """A named collection of benchmarks to run together."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Suite ID")
    name: str = Field(..., description="Suite name")
    description: str = Field("", description="Suite description")
    benchmarks: list[BenchmarkSuiteEntry] = Field(
        default_factory=list, description="Benchmarks in this suite"
    )
    last_run: datetime | None = Field(None, description="Last run timestamp")
    schedule_cron: str | None = Field(None, description="Cron schedule expression")


class BenchmarkSuiteCreate(BaseModel):
    """Request body for creating a benchmark suite."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("")
    benchmarks: list[BenchmarkSuiteEntry] = Field(default_factory=list)
    schedule_cron: str | None = None


class BenchmarkSuiteRunResult(BaseModel):
    """Result of running a benchmark suite."""

    suite_id: str
    suite_name: str
    started_at: datetime
    completed_at: datetime
    results: list[BenchmarkResult]


class BenchmarkSuiteListResponse(BaseModel):
    """List of benchmark suites."""

    total: int
    suites: list[BenchmarkSuite]


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


class VersionComparisonEntry(BaseModel):
    """Comparison of a single operation between two versions."""

    operation_name: str
    category: BenchmarkCategory
    version_a_p99: float
    version_b_p99: float
    version_a_p50: float
    version_b_p50: float
    delta_p99_ms: float
    delta_p99_pct: float
    improved: bool


class VersionComparison(BaseModel):
    """Comparison of performance between two application versions."""

    version_a: str
    version_b: str
    total_operations: int
    improved: int
    degraded: int
    unchanged: int
    entries: list[VersionComparisonEntry]


# ---------------------------------------------------------------------------
# Aggregate program metrics
# ---------------------------------------------------------------------------


class OperationSummary(BaseModel):
    """Summary of a single operation's performance."""

    operation_name: str
    category: BenchmarkCategory
    latest_p99: float


class PerformanceMetrics(BaseModel):
    """Program-wide performance metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_slas: int = Field(0, description="Total SLA definitions")
    sla_compliance_rate: float = Field(
        0.0, ge=0, le=100, description="Overall SLA compliance percentage"
    )
    total_benchmarks: int = Field(0, description="Total benchmark results recorded")
    categories_covered: int = Field(0, description="Number of distinct categories")
    mean_p99_across_all: float = Field(0.0, description="Mean p99 across all operations")
    degraded_operations: list[OperationSummary] = Field(
        default_factory=list, description="Operations with detected regressions"
    )
    top_performers: list[OperationSummary] = Field(
        default_factory=list, description="Best-performing operations"
    )
    worst_performers: list[OperationSummary] = Field(
        default_factory=list, description="Worst-performing operations"
    )
