"""Enrollment Forecasting Engine API endpoints (CMO-10).

Provides enrollment forecasting, Monte Carlo simulation, scenario analysis,
site-level enrollment rates, milestone tracking, trend detection, risk
assessment, and aggregate metrics for clinical trial enrollment.

Endpoints:
    GET  /enrollment-forecasting/forecasts                              - List all forecasts
    GET  /enrollment-forecasting/forecasts/{trial_id}                   - Get single forecast
    POST /enrollment-forecasting/forecasts/{trial_id}/generate          - Regenerate forecast
    GET  /enrollment-forecasting/forecasts/{trial_id}/monte-carlo       - Monte Carlo results
    GET  /enrollment-forecasting/forecasts/{trial_id}/scenarios         - Scenario analysis
    GET  /enrollment-forecasting/forecasts/{trial_id}/sites             - Site-level rates
    GET  /enrollment-forecasting/forecasts/{trial_id}/milestones        - List milestones
    POST /enrollment-forecasting/forecasts/{trial_id}/milestones        - Add milestone
    PUT  /enrollment-forecasting/forecasts/{trial_id}/milestones/{id}   - Update milestone
    GET  /enrollment-forecasting/forecasts/{trial_id}/trend             - Trend analysis
    GET  /enrollment-forecasting/forecasts/{trial_id}/risk              - Risk assessment
    GET  /enrollment-forecasting/forecasts/{trial_id}/data-points       - List data points
    POST /enrollment-forecasting/forecasts/{trial_id}/data-points       - Add data point
    GET  /enrollment-forecasting/metrics                                - Aggregate metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.enrollment_forecasting import (
    DataPointCreateRequest,
    EnrollmentDataPoint,
    EnrollmentMilestone,
    ForecastListResponse,
    ForecastMetrics,
    ForecastMethod,
    ForecastRequest,
    ForecastResult,
    MilestoneCreateRequest,
    MilestoneUpdateRequest,
    MonteCarloResult,
    RiskAssessment,
    ScenarioResult,
    SiteEnrollmentRate,
    TrendAnalysis,
    TrialForecast,
)
from app.services.enrollment_forecasting_service import get_enrollment_forecasting_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/enrollment-forecasting",
    tags=["Enrollment Forecasting"],
)


# ---------------------------------------------------------------------------
# Forecast CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts",
    response_model=ForecastListResponse,
    summary="List all trial forecasts",
    description="Retrieve enrollment forecasts for all monitored clinical trials.",
)
async def list_forecasts() -> ForecastListResponse:
    """List all trial forecasts."""
    svc = get_enrollment_forecasting_service()
    items = svc.list_forecasts()
    return ForecastListResponse(items=items, total=len(items))


@router.get(
    "/forecasts/{trial_id}",
    response_model=TrialForecast,
    summary="Get trial forecast",
    description="Retrieve the enrollment forecast for a specific trial.",
)
async def get_forecast(trial_id: str) -> TrialForecast:
    """Get forecast for a specific trial."""
    svc = get_enrollment_forecasting_service()
    forecast = svc.get_forecast(trial_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return forecast


@router.post(
    "/forecasts/{trial_id}/generate",
    response_model=ForecastResult,
    summary="Generate forecast",
    description="Generate or regenerate an enrollment forecast for a trial using the specified method.",
)
async def generate_forecast(
    trial_id: str,
    request: Optional[ForecastRequest] = None,
) -> ForecastResult:
    """Generate or regenerate a forecast for a trial."""
    svc = get_enrollment_forecasting_service()
    result = svc.generate_forecast(trial_id, request)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return result


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/monte-carlo",
    response_model=MonteCarloResult,
    summary="Run Monte Carlo simulation",
    description="Run a Monte Carlo simulation to project enrollment completion timelines with percentile distributions.",
)
async def run_monte_carlo(
    trial_id: str,
    simulations: int = Query(1000, ge=100, le=10000, description="Number of simulations to run"),
) -> MonteCarloResult:
    """Run Monte Carlo simulation for enrollment timeline."""
    svc = get_enrollment_forecasting_service()
    result = svc.run_monte_carlo(trial_id, n_simulations=simulations)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return result


# ---------------------------------------------------------------------------
# Scenario analysis
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/scenarios",
    response_model=list[ScenarioResult],
    summary="Get scenario analysis",
    description="Get optimistic, base-case, and pessimistic enrollment scenarios for a trial.",
)
async def get_scenarios(trial_id: str) -> list[ScenarioResult]:
    """Get scenario analysis for a trial."""
    svc = get_enrollment_forecasting_service()
    scenarios = svc.get_scenarios(trial_id)
    if scenarios is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return scenarios


# ---------------------------------------------------------------------------
# Site-level rates
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/sites",
    response_model=list[SiteEnrollmentRate],
    summary="Get site enrollment rates",
    description="Get enrollment rates and capacity metrics for all sites in a trial.",
)
async def get_site_rates(trial_id: str) -> list[SiteEnrollmentRate]:
    """Get site-level enrollment rates for a trial."""
    svc = get_enrollment_forecasting_service()
    rates = svc.get_site_rates(trial_id)
    if rates is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return rates


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/milestones",
    response_model=list[EnrollmentMilestone],
    summary="List milestones",
    description="List all enrollment milestones for a trial.",
)
async def list_milestones(trial_id: str) -> list[EnrollmentMilestone]:
    """List milestones for a trial."""
    svc = get_enrollment_forecasting_service()
    milestones = svc.get_milestones(trial_id)
    if milestones is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return milestones


@router.post(
    "/forecasts/{trial_id}/milestones",
    response_model=EnrollmentMilestone,
    status_code=201,
    summary="Add milestone",
    description="Add a new enrollment milestone to a trial forecast.",
)
async def add_milestone(
    trial_id: str,
    request: MilestoneCreateRequest,
) -> EnrollmentMilestone:
    """Add a new milestone to a trial forecast."""
    svc = get_enrollment_forecasting_service()
    milestone = svc.add_milestone(trial_id, request)
    if milestone is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return milestone


@router.put(
    "/forecasts/{trial_id}/milestones/{milestone_id}",
    response_model=EnrollmentMilestone,
    summary="Update milestone",
    description="Update an enrollment milestone's actual data and status.",
)
async def update_milestone(
    trial_id: str,
    milestone_id: str,
    request: MilestoneUpdateRequest,
) -> EnrollmentMilestone:
    """Update a milestone's actual data and status."""
    svc = get_enrollment_forecasting_service()
    milestone = svc.update_milestone(trial_id, milestone_id, request)
    if milestone is None:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone not found: {milestone_id} for trial {trial_id}",
        )
    return milestone


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/trend",
    response_model=TrendAnalysis,
    summary="Detect enrollment trend",
    description="Detect enrollment velocity trend by comparing recent vs prior enrollment periods.",
)
async def detect_trend(trial_id: str) -> TrendAnalysis:
    """Detect enrollment trend for a trial."""
    svc = get_enrollment_forecasting_service()
    trend = svc.detect_trend(trial_id)
    if trend is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return trend


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/risk",
    response_model=RiskAssessment,
    summary="Assess enrollment risk",
    description="Compute a composite enrollment risk score with factor-level analysis and recommendations.",
)
async def assess_risk(trial_id: str) -> RiskAssessment:
    """Assess enrollment risk for a trial."""
    svc = get_enrollment_forecasting_service()
    assessment = svc.assess_risk(trial_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return assessment


# ---------------------------------------------------------------------------
# Data points
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts/{trial_id}/data-points",
    response_model=list[EnrollmentDataPoint],
    summary="List enrollment data points",
    description="List all historical enrollment data points for a trial.",
)
async def list_data_points(trial_id: str) -> list[EnrollmentDataPoint]:
    """List enrollment data points for a trial."""
    svc = get_enrollment_forecasting_service()
    points = svc.get_data_points(trial_id)
    if points is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return points


@router.post(
    "/forecasts/{trial_id}/data-points",
    response_model=EnrollmentDataPoint,
    status_code=201,
    summary="Add enrollment data point",
    description="Add a new enrollment data point to a trial's historical data.",
)
async def add_data_point(
    trial_id: str,
    request: DataPointCreateRequest,
) -> EnrollmentDataPoint:
    """Add a new enrollment data point to a trial."""
    svc = get_enrollment_forecasting_service()
    dp = svc.add_data_point(trial_id, request)
    if dp is None:
        raise HTTPException(status_code=404, detail=f"Trial forecast not found: {trial_id}")
    return dp


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ForecastMetrics,
    summary="Get aggregate forecast metrics",
    description="Get aggregate enrollment metrics across all monitored trials.",
)
async def get_metrics() -> ForecastMetrics:
    """Get aggregate metrics across all trial forecasts."""
    svc = get_enrollment_forecasting_service()
    return svc.get_metrics()
