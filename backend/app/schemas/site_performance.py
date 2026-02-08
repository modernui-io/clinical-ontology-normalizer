"""Pydantic schemas for Clinical Site Performance Analytics (CMO-8).

Tracks clinical trial site performance, benchmarking, scoring, and
recommendations to optimise multi-site trial operations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SiteStatus(str, Enum):
    """Operational status of a clinical trial site."""

    ACTIVE = "active"
    ENROLLING = "enrolling"
    PAUSED = "paused"
    CLOSED = "closed"
    PENDING_ACTIVATION = "pending_activation"


class RecommendationType(str, Enum):
    """Types of site-level recommendations."""

    INCREASE_CAPACITY = "increase_capacity"
    TRAINING_NEEDED = "training_needed"
    PAUSE_ENROLLMENT = "pause_enrollment"
    EXPAND_TRIALS = "expand_trials"
    CLOSE = "close"


class Quartile(str, Enum):
    """Performance quartile buckets."""

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


# ---------------------------------------------------------------------------
# Core site record
# ---------------------------------------------------------------------------

class ClinicalSite(BaseModel):
    """A clinical trial site with key performance indicators."""

    id: str = Field(..., description="Unique site identifier")
    name: str = Field(..., description="Site display name")
    institution: str = Field(..., description="Parent institution / hospital")
    location: dict = Field(
        ...,
        description="Site location with city, state, country keys",
    )
    pi_name: str = Field(..., description="Principal investigator name")
    status: SiteStatus = Field(..., description="Current operational status")
    activated_date: str | None = Field(None, description="ISO date when site was activated")
    trials: list[str] = Field(default_factory=list, description="List of associated trial IDs")
    total_screened: int = Field(0, ge=0, description="Total patients screened")
    total_enrolled: int = Field(0, ge=0, description="Total patients enrolled")
    screen_failure_rate: float = Field(0.0, ge=0.0, le=1.0, description="Fraction failing screening")
    enrollment_rate_per_month: float = Field(0.0, ge=0.0, description="Avg patients enrolled per month")
    avg_time_to_first_patient_days: float | None = Field(
        None, ge=0.0, description="Average days from activation to first patient enrolled",
    )
    avg_query_resolution_days: float | None = Field(
        None, ge=0.0, description="Average days to resolve data queries",
    )
    protocol_deviation_count: int = Field(0, ge=0, description="Total protocol deviations reported")
    created_at: str = Field(..., description="ISO datetime when the record was created")


# ---------------------------------------------------------------------------
# Performance scoring
# ---------------------------------------------------------------------------

class SitePerformanceScore(BaseModel):
    """Composite performance score for a single site."""

    site_id: str = Field(..., description="Site identifier")
    enrollment_score: float = Field(..., ge=0.0, le=100.0, description="Enrollment efficiency score")
    quality_score: float = Field(..., ge=0.0, le=100.0, description="Data quality score")
    timeliness_score: float = Field(..., ge=0.0, le=100.0, description="Timeliness / speed score")
    compliance_score: float = Field(..., ge=0.0, le=100.0, description="Protocol compliance score")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Weighted overall score")
    rank: int = Field(..., ge=1, description="Rank among all scored sites")
    quartile: Quartile = Field(..., description="Performance quartile")
    calculated_at: str = Field(..., description="ISO datetime of calculation")


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

class SiteBenchmark(BaseModel):
    """Benchmark comparison for a single metric against the cohort."""

    metric_name: str = Field(..., description="Name of the metric being benchmarked")
    p25: float = Field(..., description="25th percentile value")
    p50: float = Field(..., description="50th percentile (median)")
    p75: float = Field(..., description="75th percentile value")
    p90: float = Field(..., description="90th percentile value")
    site_value: float = Field(..., description="Value for the target site")
    percentile_rank: float = Field(
        ..., ge=0.0, le=100.0, description="Site's percentile rank for this metric",
    )


# ---------------------------------------------------------------------------
# Head-to-head comparison
# ---------------------------------------------------------------------------

class MetricComparison(BaseModel):
    """Single metric comparison between two sites."""

    metric: str = Field(..., description="Metric name")
    site_a_value: float = Field(..., description="Value for site A")
    site_b_value: float = Field(..., description="Value for site B")
    difference: float = Field(..., description="site_a_value - site_b_value")
    better: str = Field(..., description="Which site is better: 'a', 'b', or 'tie'")


class SiteComparison(BaseModel):
    """Head-to-head comparison of two sites."""

    site_a_id: str = Field(..., description="First site identifier")
    site_b_id: str = Field(..., description="Second site identifier")
    metrics_comparison: list[MetricComparison] = Field(
        default_factory=list, description="Per-metric comparison results",
    )


# ---------------------------------------------------------------------------
# Aggregate program metrics
# ---------------------------------------------------------------------------

class SiteMetrics(BaseModel):
    """Program-wide aggregate site metrics."""

    total_sites: int = Field(ge=0, description="Total number of sites")
    active_sites: int = Field(ge=0, description="Number of active/enrolling sites")
    avg_enrollment_rate: float = Field(ge=0.0, description="Average enrollment rate across sites")
    avg_screen_failure_rate: float = Field(
        ge=0.0, le=1.0, description="Average screen failure rate",
    )
    top_performers: list[str] = Field(
        default_factory=list, description="Site IDs of top performing sites",
    )
    underperformers: list[str] = Field(
        default_factory=list, description="Site IDs of underperforming sites",
    )
    by_country: dict[str, int] = Field(
        default_factory=dict, description="Site count by country",
    )
    total_enrolled_all_sites: int = Field(ge=0, description="Sum of enrolled patients across all sites")


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class SiteRecommendation(BaseModel):
    """Auto-generated recommendation for a site."""

    site_id: str = Field(..., description="Target site identifier")
    recommendation_type: RecommendationType = Field(..., description="Category of recommendation")
    rationale: str = Field(..., description="Human-readable explanation")
    priority: str = Field(..., description="Priority level: high, medium, low")


# ---------------------------------------------------------------------------
# Enrollment trend
# ---------------------------------------------------------------------------

class MonthlyEnrollment(BaseModel):
    """Enrollment count for a single month."""

    month: str = Field(..., description="Month label (YYYY-MM)")
    enrolled: int = Field(ge=0, description="Patients enrolled that month")
    screened: int = Field(ge=0, description="Patients screened that month")


# ---------------------------------------------------------------------------
# Request / Response wrappers
# ---------------------------------------------------------------------------

class SiteListResponse(BaseModel):
    """Paginated list of clinical sites."""

    sites: list[ClinicalSite] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteScoresResponse(BaseModel):
    """All site performance scores."""

    scores: list[SitePerformanceScore] = Field(default_factory=list)
    calculated_at: str = Field(..., description="ISO datetime")


class SiteBenchmarksResponse(BaseModel):
    """Benchmark results for a site."""

    site_id: str
    benchmarks: list[SiteBenchmark] = Field(default_factory=list)


class SiteRecommendationsResponse(BaseModel):
    """Recommendations for a site."""

    site_id: str
    recommendations: list[SiteRecommendation] = Field(default_factory=list)


class EnrollmentTrendResponse(BaseModel):
    """Monthly enrollment trend for a site."""

    site_id: str
    months: list[MonthlyEnrollment] = Field(default_factory=list)


class UnderperformersResponse(BaseModel):
    """Sites performing below threshold."""

    threshold: float
    sites: list[ClinicalSite] = Field(default_factory=list)
    total: int = Field(ge=0)
