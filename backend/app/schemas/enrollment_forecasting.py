"""Pydantic schemas for Enrollment Forecasting Engine (CMO-10).

Pharma-grade enrollment forecasting system that predicts clinical trial
enrollment timelines using historical data, Monte Carlo simulations,
scenario analysis, and site-level enrollment rate tracking.
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ForecastMethod(str, Enum):
    """Statistical method used to generate enrollment forecast."""

    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    EXPONENTIAL_SMOOTHING = "EXPONENTIAL_SMOOTHING"
    MONTE_CARLO = "MONTE_CARLO"
    POISSON_PROCESS = "POISSON_PROCESS"
    BAYESIAN = "BAYESIAN"
    WEIGHTED_MOVING_AVERAGE = "WEIGHTED_MOVING_AVERAGE"


class EnrollmentTrend(str, Enum):
    """Current enrollment velocity trend classification."""

    ACCELERATING = "ACCELERATING"
    STEADY = "STEADY"
    DECELERATING = "DECELERATING"
    STALLED = "STALLED"
    NOT_STARTED = "NOT_STARTED"


class RiskFactor(str, Enum):
    """Risk factor that may affect enrollment timeline."""

    SLOW_SCREENING = "SLOW_SCREENING"
    HIGH_SCREEN_FAILURE = "HIGH_SCREEN_FAILURE"
    SITE_CAPACITY = "SITE_CAPACITY"
    SEASONAL_EFFECT = "SEASONAL_EFFECT"
    COMPETITION = "COMPETITION"
    PROTOCOL_AMENDMENT = "PROTOCOL_AMENDMENT"
    REGULATORY_DELAY = "REGULATORY_DELAY"


class ScenarioType(str, Enum):
    """Scenario type for enrollment projection analysis."""

    OPTIMISTIC = "OPTIMISTIC"
    BASE_CASE = "BASE_CASE"
    PESSIMISTIC = "PESSIMISTIC"
    CUSTOM = "CUSTOM"


class ConfidenceLevel(str, Enum):
    """Confidence level of a forecast prediction."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class MilestoneStatus(str, Enum):
    """Status of an enrollment milestone."""

    PENDING = "PENDING"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    MISSED = "MISSED"
    ACHIEVED = "ACHIEVED"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class EnrollmentDataPoint(BaseModel):
    """A single enrollment data point for a trial at a point in time."""

    model_config = ConfigDict(from_attributes=True)

    date: DateType = Field(..., description="Date of the data point")
    cumulative_enrolled: int = Field(..., ge=0, description="Total enrolled to date")
    new_enrolled: int = Field(0, ge=0, description="Newly enrolled on this date")
    screened: int = Field(0, ge=0, description="Number screened on this date")
    screen_failures: int = Field(0, ge=0, description="Screen failures on this date")
    dropouts: int = Field(0, ge=0, description="Dropouts on this date")
    site_id: Optional[str] = Field(None, description="Site ID if site-level data")


class SiteEnrollmentRate(BaseModel):
    """Enrollment rate and capacity metrics for a single trial site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Unique site identifier")
    site_name: str = Field(..., description="Human-readable site name")
    enrollment_rate_per_month: float = Field(..., ge=0, description="Avg patients enrolled per month")
    screen_failure_rate: float = Field(..., ge=0, le=1.0, description="Proportion of screened patients who fail")
    capacity_remaining: int = Field(..., ge=0, description="Remaining enrollment capacity at site")
    projected_completion: Optional[DateType] = Field(None, description="Projected date site reaches capacity")
    active: bool = Field(True, description="Whether site is actively enrolling")
    months_active: float = Field(0, ge=0, description="Months since site activation")


class ScenarioResult(BaseModel):
    """Projected outcome under a specific enrollment scenario."""

    model_config = ConfigDict(from_attributes=True)

    scenario_type: ScenarioType = Field(..., description="Type of scenario")
    projected_completion_date: DateType = Field(..., description="Projected enrollment completion date")
    enrollment_rate: float = Field(..., ge=0, description="Assumed enrollment rate per month")
    probability: float = Field(..., ge=0, le=1.0, description="Probability of this scenario")
    assumptions: list[str] = Field(default_factory=list, description="Key assumptions for this scenario")


class MonteCarloResult(BaseModel):
    """Results from a Monte Carlo simulation of enrollment timelines."""

    model_config = ConfigDict(from_attributes=True)

    simulations_run: int = Field(..., ge=1, description="Number of simulations executed")
    p10_date: DateType = Field(..., description="10th percentile completion date")
    p25_date: DateType = Field(..., description="25th percentile completion date")
    p50_date: DateType = Field(..., description="50th percentile (median) completion date")
    p75_date: DateType = Field(..., description="75th percentile completion date")
    p90_date: DateType = Field(..., description="90th percentile completion date")
    mean_days_to_target: float = Field(..., ge=0, description="Mean days to reach target enrollment")
    std_dev_days: float = Field(..., ge=0, description="Standard deviation of days to target")
    histogram_buckets: list[dict] = Field(
        default_factory=list,
        description="Histogram buckets with 'range_start', 'range_end', 'count' keys",
    )


class ForecastResult(BaseModel):
    """Enrollment forecast result from a specific method."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    method: ForecastMethod = Field(..., description="Forecast method used")
    target_enrollment: int = Field(..., ge=1, description="Target enrollment count")
    current_enrollment: int = Field(..., ge=0, description="Current enrollment count")
    projected_completion_date: DateType = Field(..., description="Projected completion date")
    confidence_interval_lower: DateType = Field(..., description="Lower bound of confidence interval")
    confidence_interval_upper: DateType = Field(..., description="Upper bound of confidence interval")
    confidence_level: ConfidenceLevel = Field(..., description="Forecast confidence level")
    days_to_target: int = Field(..., ge=0, description="Estimated days to reach target")
    enrollment_rate_per_month: float = Field(..., ge=0, description="Current enrollment rate per month")
    data_points_used: int = Field(..., ge=0, description="Number of historical data points used")
    risk_factors: list[RiskFactor] = Field(default_factory=list, description="Identified risk factors")
    scenarios: list[ScenarioResult] = Field(default_factory=list, description="Scenario analysis results")


class EnrollmentMilestone(BaseModel):
    """Enrollment milestone with target and actual tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique milestone identifier")
    trial_id: str = Field(..., description="Trial identifier")
    milestone_name: str = Field(..., description="Milestone description")
    target_count: int = Field(..., ge=0, description="Target enrollment count")
    target_date: DateType = Field(..., description="Target date for milestone")
    actual_count: Optional[int] = Field(None, ge=0, description="Actual enrollment count at target date")
    actual_date: Optional[DateType] = Field(None, description="Actual date milestone was reached")
    status: MilestoneStatus = Field(MilestoneStatus.PENDING, description="Milestone status")
    variance_days: Optional[int] = Field(None, description="Days ahead (+) or behind (-) schedule")


class TrialForecast(BaseModel):
    """Complete enrollment forecast for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique forecast identifier")
    trial_id: str = Field(..., description="Trial identifier")
    trial_name: str = Field(..., description="Human-readable trial name")
    target_enrollment: int = Field(..., ge=1, description="Target enrollment count")
    current_enrollment: int = Field(..., ge=0, description="Current enrollment count")
    start_date: DateType = Field(..., description="Trial enrollment start date")
    target_date: DateType = Field(..., description="Target enrollment completion date")
    forecast_method: ForecastMethod = Field(..., description="Primary forecast method")
    forecast_result: Optional[ForecastResult] = Field(None, description="Latest forecast result")
    monte_carlo: Optional[MonteCarloResult] = Field(None, description="Monte Carlo simulation results")
    milestones: list[EnrollmentMilestone] = Field(default_factory=list, description="Enrollment milestones")
    site_rates: list[SiteEnrollmentRate] = Field(default_factory=list, description="Site-level enrollment rates")
    trend: EnrollmentTrend = Field(EnrollmentTrend.NOT_STARTED, description="Current enrollment trend")
    risk_score: float = Field(0.0, ge=0, le=100.0, description="Composite risk score (0-100)")
    created_at: datetime = Field(..., description="Forecast creation timestamp")
    updated_at: datetime = Field(..., description="Forecast last update timestamp")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ForecastRequest(BaseModel):
    """Request to generate or regenerate a forecast for a trial."""

    model_config = ConfigDict(from_attributes=True)

    method: ForecastMethod = Field(
        ForecastMethod.MONTE_CARLO,
        description="Forecast method to use",
    )
    simulations: int = Field(1000, ge=100, le=10000, description="Number of Monte Carlo simulations")
    include_scenarios: bool = Field(True, description="Include scenario analysis")


class MilestoneCreateRequest(BaseModel):
    """Request to create a new enrollment milestone."""

    model_config = ConfigDict(from_attributes=True)

    milestone_name: str = Field(..., min_length=1, max_length=200, description="Milestone description")
    target_count: int = Field(..., ge=1, description="Target enrollment count")
    target_date: DateType = Field(..., description="Target date for milestone")


class MilestoneUpdateRequest(BaseModel):
    """Request to update an enrollment milestone."""

    model_config = ConfigDict(from_attributes=True)

    actual_count: Optional[int] = Field(None, ge=0, description="Actual enrollment count")
    actual_date: Optional[DateType] = Field(None, description="Actual date milestone reached")
    status: Optional[MilestoneStatus] = Field(None, description="Updated milestone status")


class DataPointCreateRequest(BaseModel):
    """Request to add a new enrollment data point."""

    model_config = ConfigDict(from_attributes=True)

    date: DateType = Field(..., description="Date of the data point")
    new_enrolled: int = Field(..., ge=0, description="Newly enrolled patients")
    screened: int = Field(0, ge=0, description="Number screened")
    screen_failures: int = Field(0, ge=0, description="Number of screen failures")
    dropouts: int = Field(0, ge=0, description="Number of dropouts")
    site_id: Optional[str] = Field(None, description="Site ID for site-level data")


class ForecastListResponse(BaseModel):
    """Response containing a list of trial forecasts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrialForecast] = Field(..., description="List of trial forecasts")
    total: int = Field(..., ge=0, description="Total number of forecasts")


class TrendAnalysis(BaseModel):
    """Enrollment trend analysis result."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    trend: EnrollmentTrend = Field(..., description="Current trend classification")
    current_rate: float = Field(..., ge=0, description="Current enrollment rate (last 30 days)")
    prior_rate: float = Field(..., ge=0, description="Prior enrollment rate (30-60 days ago)")
    rate_change_pct: float = Field(..., description="Percentage change in rate")
    description: str = Field(..., description="Human-readable trend description")


class RiskAssessment(BaseModel):
    """Enrollment risk assessment for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    risk_score: float = Field(..., ge=0, le=100.0, description="Composite risk score (0-100)")
    risk_factors: list[dict] = Field(
        default_factory=list,
        description="List of risk factors with 'factor', 'severity', 'description' keys",
    )
    overall_risk: str = Field(..., description="Overall risk level: LOW, MEDIUM, HIGH, CRITICAL")
    recommendations: list[str] = Field(default_factory=list, description="Risk mitigation recommendations")


class ForecastMetrics(BaseModel):
    """Aggregate metrics across all trial forecasts."""

    model_config = ConfigDict(from_attributes=True)

    total_trials: int = Field(..., ge=0, description="Total number of trials being forecasted")
    total_target_enrollment: int = Field(..., ge=0, description="Sum of all target enrollments")
    total_current_enrollment: int = Field(..., ge=0, description="Sum of all current enrollments")
    overall_enrollment_pct: float = Field(..., ge=0, le=100.0, description="Overall enrollment percentage")
    trials_on_track: int = Field(..., ge=0, description="Number of trials on track")
    trials_at_risk: int = Field(..., ge=0, description="Number of trials at risk")
    trials_behind: int = Field(..., ge=0, description="Number of trials behind schedule")
    avg_risk_score: float = Field(..., ge=0, le=100.0, description="Average risk score across trials")
    avg_enrollment_rate: float = Field(..., ge=0, description="Average enrollment rate per month")
    total_sites: int = Field(..., ge=0, description="Total number of enrollment sites")
    avg_screen_failure_rate: float = Field(..., ge=0, le=1.0, description="Average screen failure rate")
