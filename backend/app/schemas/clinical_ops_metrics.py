"""Pydantic schemas for Clinical Operations Metrics Dashboard.

Provides comprehensive operational KPIs, performance tracking, trend analysis,
benchmarking, and executive reporting across the clinical trial portfolio.
Covers enrollment, quality, timeline, budget, safety, compliance, site
performance, and data management metrics with portfolio-level scorecards,
industry benchmarking, operational alerts, and executive report generation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MetricCategory(str, Enum):
    """Category of operational KPI."""

    ENROLLMENT = "enrollment"
    QUALITY = "quality"
    TIMELINE = "timeline"
    BUDGET = "budget"
    SAFETY = "safety"
    COMPLIANCE = "compliance"
    SITE_PERFORMANCE = "site_performance"
    DATA_MANAGEMENT = "data_management"


class TrendDirection(str, Enum):
    """Direction of a KPI trend over time."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"


class ReportPeriod(str, Enum):
    """Reporting period granularity."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class BenchmarkSource(str, Enum):
    """Source for benchmarking data."""

    INTERNAL = "internal"
    INDUSTRY = "industry"
    SPONSOR_TARGET = "sponsor_target"


class AlertSeverity(str, Enum):
    """Severity of an operational alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class KPIStatus(str, Enum):
    """Status of a KPI relative to target."""

    ON_TARGET = "on_target"
    AT_RISK = "at_risk"
    OFF_TARGET = "off_target"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class OperationalKPI(BaseModel):
    """A single operational KPI measurement for a trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique KPI identifier")
    trial_id: str = Field(..., description="Trial identifier")
    category: MetricCategory = Field(..., description="KPI category")
    metric_name: str = Field(..., description="Name of the metric")
    current_value: float = Field(..., description="Current metric value")
    target_value: float = Field(..., description="Target metric value")
    unit: str = Field(..., description="Unit of measurement (e.g., %, days, count)")
    trend_direction: TrendDirection = Field(..., description="Trend direction over recent periods")
    period_start: datetime = Field(..., description="Start of the measurement period")
    period_end: datetime = Field(..., description="End of the measurement period")
    calculated_date: datetime = Field(..., description="When this KPI was last calculated")
    variance_pct: float = Field(..., description="Variance from target as a percentage")
    status: KPIStatus = Field(..., description="KPI status relative to target")


class PerformanceTrend(BaseModel):
    """A single data point in a KPI performance trend over time."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique trend data point identifier")
    kpi_id: str = Field(..., description="Associated KPI identifier")
    period_start: datetime = Field(..., description="Start of the period")
    period_end: datetime = Field(..., description="End of the period")
    value: float = Field(..., description="Metric value for this period")
    target: float = Field(..., description="Target value for this period")
    variance_pct: float = Field(..., description="Variance from target as a percentage")
    notes: str | None = Field(None, description="Optional notes for this period")


class TrialScorecard(BaseModel):
    """Composite scorecard for a clinical trial across multiple dimensions."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique scorecard identifier")
    trial_id: str = Field(..., description="Trial identifier")
    trial_name: str = Field(..., description="Trial display name")
    phase: str = Field(..., description="Trial phase (e.g., Phase I, Phase II, Phase III)")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    overall_score: float = Field(ge=0.0, le=100.0, description="Overall composite score (0-100)")
    enrollment_score: float = Field(ge=0.0, le=100.0, description="Enrollment dimension score (0-100)")
    quality_score: float = Field(ge=0.0, le=100.0, description="Quality dimension score (0-100)")
    timeline_score: float = Field(ge=0.0, le=100.0, description="Timeline dimension score (0-100)")
    budget_score: float = Field(ge=0.0, le=100.0, description="Budget dimension score (0-100)")
    safety_score: float = Field(ge=0.0, le=100.0, description="Safety dimension score (0-100)")
    compliance_score: float = Field(ge=0.0, le=100.0, description="Compliance dimension score (0-100)")
    last_updated: datetime = Field(..., description="When the scorecard was last updated")
    risk_flags: list[str] = Field(default_factory=list, description="Active risk flags for this trial")


class PortfolioSummary(BaseModel):
    """High-level summary of the entire clinical trial portfolio."""

    model_config = ConfigDict(from_attributes=True)

    total_trials: int = Field(ge=0, description="Total number of trials in the portfolio")
    trials_by_phase: dict[str, int] = Field(
        default_factory=dict, description="Count of trials by phase"
    )
    total_sites: int = Field(ge=0, description="Total active sites across all trials")
    total_patients: int = Field(ge=0, description="Total enrolled patients")
    overall_enrollment_rate: float = Field(
        ge=0.0, description="Portfolio-wide enrollment rate (patients per site per month)"
    )
    budget_utilization_pct: float = Field(
        ge=0.0, le=200.0, description="Budget utilization percentage across portfolio"
    )
    avg_data_quality_score: float = Field(
        ge=0.0, le=100.0, description="Average data quality score across all trials"
    )
    critical_alerts_count: int = Field(ge=0, description="Number of active critical alerts")
    trials_on_track_pct: float = Field(
        ge=0.0, le=100.0, description="Percentage of trials on track against timeline"
    )


class Benchmark(BaseModel):
    """Benchmark comparison for a metric against internal, industry, and sponsor targets."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique benchmark identifier")
    category: MetricCategory = Field(..., description="Metric category")
    metric_name: str = Field(..., description="Name of the benchmarked metric")
    internal_value: float = Field(..., description="Internal (actual) value")
    industry_value: float = Field(..., description="Industry average value")
    sponsor_target: float = Field(..., description="Sponsor target value")
    percentile_rank: float = Field(
        ge=0.0, le=100.0, description="Percentile rank vs. industry (0-100)"
    )
    comparison_period: str = Field(..., description="Period of comparison (e.g., Q4 2025)")
    source: BenchmarkSource = Field(..., description="Primary benchmark source")


class OperationalAlert(BaseModel):
    """An operational alert triggered by a metric threshold breach."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique alert identifier")
    trial_id: str = Field(..., description="Trial that triggered the alert")
    category: MetricCategory = Field(..., description="Metric category of the alert")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    message: str = Field(..., description="Human-readable alert message")
    metric_value: float = Field(..., description="Metric value that triggered the alert")
    threshold_value: float = Field(..., description="Threshold value that was breached")
    created_date: datetime = Field(..., description="When the alert was created")
    acknowledged: bool = Field(default=False, description="Whether the alert has been acknowledged")
    acknowledged_by: str | None = Field(None, description="User who acknowledged the alert")
    resolved_date: datetime | None = Field(None, description="When the alert was resolved")


class ExecutiveReport(BaseModel):
    """A generated executive report for a reporting period."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique report identifier")
    report_period: ReportPeriod = Field(..., description="Reporting period granularity")
    period_start: datetime = Field(..., description="Start of the reporting period")
    period_end: datetime = Field(..., description="End of the reporting period")
    generated_date: datetime = Field(..., description="When the report was generated")
    generated_by: str = Field(..., description="User or system that generated the report")
    portfolio_summary: PortfolioSummary = Field(..., description="Portfolio summary snapshot")
    key_achievements: list[str] = Field(
        default_factory=list, description="Notable achievements during the period"
    )
    key_risks: list[str] = Field(
        default_factory=list, description="Key risks identified during the period"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Action recommendations for the next period"
    )


class DashboardMetrics(BaseModel):
    """Aggregated dashboard metrics for the operations metrics UI."""

    model_config = ConfigDict(from_attributes=True)

    portfolio_summary: PortfolioSummary = Field(..., description="Portfolio-level summary")
    total_kpis: int = Field(ge=0, description="Total KPIs tracked")
    kpis_on_target: int = Field(ge=0, description="Number of KPIs on target")
    kpis_at_risk: int = Field(ge=0, description="Number of KPIs at risk")
    kpis_off_target: int = Field(ge=0, description="Number of KPIs off target")
    active_alerts: int = Field(ge=0, description="Number of unresolved alerts")
    critical_alerts: int = Field(ge=0, description="Number of critical alerts")
    total_scorecards: int = Field(ge=0, description="Number of trial scorecards")
    avg_overall_score: float = Field(
        ge=0.0, le=100.0, description="Average overall trial score"
    )
    total_benchmarks: int = Field(ge=0, description="Number of benchmark comparisons")
    top_risks: list[str] = Field(
        default_factory=list, description="Top risk items across the portfolio"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class OperationalKPICreate(BaseModel):
    """Request to create a new operational KPI."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    category: MetricCategory = Field(..., description="KPI category")
    metric_name: str = Field(..., description="Metric name")
    current_value: float = Field(..., description="Current value")
    target_value: float = Field(..., description="Target value")
    unit: str = Field(..., description="Unit of measurement")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")


class OperationalKPIUpdate(BaseModel):
    """Request to update an operational KPI."""

    model_config = ConfigDict(from_attributes=True)

    current_value: float | None = Field(None, description="Updated current value")
    target_value: float | None = Field(None, description="Updated target value")
    metric_name: str | None = Field(None, description="Updated metric name")
    unit: str | None = Field(None, description="Updated unit")
    period_start: datetime | None = Field(None, description="Updated period start")
    period_end: datetime | None = Field(None, description="Updated period end")


class PerformanceTrendCreate(BaseModel):
    """Request to create a performance trend data point."""

    model_config = ConfigDict(from_attributes=True)

    kpi_id: str = Field(..., description="Associated KPI identifier")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    value: float = Field(..., description="Metric value")
    target: float = Field(..., description="Target value")
    notes: str | None = Field(None, description="Optional notes")


class TrialScorecardCreate(BaseModel):
    """Request to create a trial scorecard."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    trial_name: str = Field(..., description="Trial name")
    phase: str = Field(..., description="Trial phase")
    therapeutic_area: str = Field(..., description="Therapeutic area")


class BenchmarkCreate(BaseModel):
    """Request to create a benchmark comparison."""

    model_config = ConfigDict(from_attributes=True)

    category: MetricCategory = Field(..., description="Metric category")
    metric_name: str = Field(..., description="Metric name")
    internal_value: float = Field(..., description="Internal value")
    industry_value: float = Field(..., description="Industry average")
    sponsor_target: float = Field(..., description="Sponsor target")
    comparison_period: str = Field(..., description="Comparison period")
    source: BenchmarkSource = Field(..., description="Primary benchmark source")


class BenchmarkUpdate(BaseModel):
    """Request to update a benchmark comparison."""

    model_config = ConfigDict(from_attributes=True)

    internal_value: float | None = Field(None, description="Updated internal value")
    industry_value: float | None = Field(None, description="Updated industry value")
    sponsor_target: float | None = Field(None, description="Updated sponsor target")
    comparison_period: str | None = Field(None, description="Updated comparison period")
    source: BenchmarkSource | None = Field(None, description="Updated source")


class AlertAcknowledge(BaseModel):
    """Request to acknowledge an operational alert."""

    model_config = ConfigDict(from_attributes=True)

    acknowledged_by: str = Field(..., description="User acknowledging the alert")


class AlertResolve(BaseModel):
    """Request to resolve an operational alert."""

    model_config = ConfigDict(from_attributes=True)

    resolved_by: str = Field(..., description="User resolving the alert")
    notes: str | None = Field(None, description="Resolution notes")


class OperationalAlertCreate(BaseModel):
    """Request to create an operational alert."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    category: MetricCategory = Field(..., description="Metric category")
    severity: AlertSeverity = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    metric_value: float = Field(..., description="Metric value that triggered the alert")
    threshold_value: float = Field(..., description="Threshold value breached")


class ExecutiveReportGenerate(BaseModel):
    """Request to generate an executive report."""

    model_config = ConfigDict(from_attributes=True)

    report_period: ReportPeriod = Field(..., description="Report period granularity")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    generated_by: str = Field(default="system", description="Who is generating the report")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class OperationalKPIListResponse(BaseModel):
    """List of operational KPIs."""

    model_config = ConfigDict(from_attributes=True)

    items: list[OperationalKPI] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PerformanceTrendListResponse(BaseModel):
    """List of performance trend data points."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PerformanceTrend] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TrialScorecardListResponse(BaseModel):
    """List of trial scorecards."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrialScorecard] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class BenchmarkListResponse(BaseModel):
    """List of benchmark comparisons."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Benchmark] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class OperationalAlertListResponse(BaseModel):
    """List of operational alerts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[OperationalAlert] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ExecutiveReportListResponse(BaseModel):
    """List of executive reports."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ExecutiveReport] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
