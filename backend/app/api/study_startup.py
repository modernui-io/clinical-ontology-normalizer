"""Study Startup & Feasibility Assessment API endpoints (CLINICAL-15).

Provides comprehensive study startup operations: site feasibility assessments
with weighted scoring, site ranking, country feasibility evaluation, country
optimization, startup timeline tracking with critical path analysis, protocol
feasibility assessment, bottleneck analysis, screen failure prediction,
and startup operational metrics.

Endpoints:
    GET    /study-startup/sites                                     - List site feasibilities
    GET    /study-startup/sites/{assessment_id}                     - Get site feasibility
    POST   /study-startup/sites                                     - Create site feasibility
    PUT    /study-startup/sites/{assessment_id}                     - Update site feasibility
    DELETE /study-startup/sites/{assessment_id}                     - Delete site feasibility
    GET    /study-startup/sites/rankings                            - Get site rankings
    GET    /study-startup/countries                                 - List country feasibilities
    GET    /study-startup/countries/{assessment_id}                 - Get country feasibility
    POST   /study-startup/countries                                 - Create country feasibility
    PUT    /study-startup/countries/{assessment_id}                 - Update country feasibility
    DELETE /study-startup/countries/{assessment_id}                 - Delete country feasibility
    GET    /study-startup/countries/optimization                    - Country optimization
    GET    /study-startup/timelines                                 - List startup timelines
    GET    /study-startup/timelines/{timeline_id}                   - Get startup timeline
    POST   /study-startup/timelines                                 - Create startup timeline
    PUT    /study-startup/timelines/{timeline_id}                   - Update startup timeline
    DELETE /study-startup/timelines/{timeline_id}                   - Delete startup timeline
    GET    /study-startup/timelines/critical-path                   - Critical path analysis
    GET    /study-startup/protocols                                 - List protocol feasibilities
    GET    /study-startup/protocols/{assessment_id}                 - Get protocol feasibility
    POST   /study-startup/protocols                                 - Create protocol feasibility
    GET    /study-startup/protocols/{trial_id}/screen-failure       - Screen failure prediction
    GET    /study-startup/bottleneck-analysis                       - Bottleneck analysis
    GET    /study-startup/metrics                                   - Startup metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.study_startup import (
    BottleneckAnalysis,
    CountryFeasibility,
    CountryFeasibilityCreate,
    CountryFeasibilityListResponse,
    CountryFeasibilityUpdate,
    CountryOptimization,
    CriticalPath,
    FeasibilityStatus,
    ProtocolFeasibility,
    ProtocolFeasibilityCreate,
    ProtocolFeasibilityListResponse,
    ScreenFailurePrediction,
    SiteFeasibility,
    SiteFeasibilityCreate,
    SiteFeasibilityListResponse,
    SiteFeasibilityUpdate,
    SiteRanking,
    StartupMetrics,
    StartupPhase,
    StartupTimeline,
    StartupTimelineCreate,
    StartupTimelineListResponse,
    StartupTimelineUpdate,
)
from app.services.study_startup_service import get_study_startup_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/study-startup",
    tags=["Study Startup & Feasibility"],
)


# ---------------------------------------------------------------------------
# Site Feasibility
# ---------------------------------------------------------------------------


@router.get(
    "/sites/rankings",
    response_model=list[SiteRanking],
    summary="Get site feasibility rankings",
    description="Rank sites by weighted composite feasibility score with detailed breakdown.",
)
async def get_site_rankings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> list[SiteRanking]:
    svc = get_study_startup_service()
    return svc.get_site_rankings(trial_id=trial_id)


@router.get(
    "/sites",
    response_model=SiteFeasibilityListResponse,
    summary="List site feasibility assessments",
    description="Retrieve site feasibility assessments with optional filtering by trial, status, and region.",
)
async def list_site_feasibilities(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[FeasibilityStatus] = Query(None, description="Filter by feasibility status"),
    region: Optional[str] = Query(None, description="Filter by geographic region"),
) -> SiteFeasibilityListResponse:
    svc = get_study_startup_service()
    items = svc.list_site_feasibilities(trial_id=trial_id, status=status, region=region)
    return SiteFeasibilityListResponse(items=items, total=len(items))


@router.get(
    "/sites/{assessment_id}",
    response_model=SiteFeasibility,
    summary="Get a site feasibility assessment",
)
async def get_site_feasibility(assessment_id: str) -> SiteFeasibility:
    svc = get_study_startup_service()
    result = svc.get_site_feasibility(assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site feasibility '{assessment_id}' not found")
    return result


@router.post(
    "/sites",
    response_model=SiteFeasibility,
    status_code=201,
    summary="Create a site feasibility assessment",
    description="Create a new site feasibility assessment. Composite score is automatically calculated using weighted scoring.",
)
async def create_site_feasibility(payload: SiteFeasibilityCreate) -> SiteFeasibility:
    svc = get_study_startup_service()
    return svc.create_site_feasibility(payload)


@router.put(
    "/sites/{assessment_id}",
    response_model=SiteFeasibility,
    summary="Update a site feasibility assessment",
    description="Update a site feasibility assessment. Composite score is recalculated if scoring inputs change.",
)
async def update_site_feasibility(
    assessment_id: str, payload: SiteFeasibilityUpdate
) -> SiteFeasibility:
    svc = get_study_startup_service()
    updated = svc.update_site_feasibility(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Site feasibility '{assessment_id}' not found")
    return updated


@router.delete(
    "/sites/{assessment_id}",
    status_code=204,
    summary="Delete a site feasibility assessment",
)
async def delete_site_feasibility(assessment_id: str) -> None:
    svc = get_study_startup_service()
    deleted = svc.delete_site_feasibility(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Site feasibility '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Country Feasibility
# ---------------------------------------------------------------------------


@router.get(
    "/countries/optimization",
    response_model=list[CountryOptimization],
    summary="Get country optimization recommendations",
    description="Optimize country selection based on cost vs timeline vs patient pool trade-offs.",
)
async def get_country_optimization(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> list[CountryOptimization]:
    svc = get_study_startup_service()
    return svc.get_country_optimization(trial_id=trial_id)


@router.get(
    "/countries",
    response_model=CountryFeasibilityListResponse,
    summary="List country feasibility assessments",
    description="Retrieve country feasibility assessments with optional filtering by trial.",
)
async def list_country_feasibilities(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CountryFeasibilityListResponse:
    svc = get_study_startup_service()
    items = svc.list_country_feasibilities(trial_id=trial_id)
    return CountryFeasibilityListResponse(items=items, total=len(items))


@router.get(
    "/countries/{assessment_id}",
    response_model=CountryFeasibility,
    summary="Get a country feasibility assessment",
)
async def get_country_feasibility(assessment_id: str) -> CountryFeasibility:
    svc = get_study_startup_service()
    result = svc.get_country_feasibility(assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Country feasibility '{assessment_id}' not found")
    return result


@router.post(
    "/countries",
    response_model=CountryFeasibility,
    status_code=201,
    summary="Create a country feasibility assessment",
)
async def create_country_feasibility(
    payload: CountryFeasibilityCreate,
) -> CountryFeasibility:
    svc = get_study_startup_service()
    return svc.create_country_feasibility(payload)


@router.put(
    "/countries/{assessment_id}",
    response_model=CountryFeasibility,
    summary="Update a country feasibility assessment",
)
async def update_country_feasibility(
    assessment_id: str, payload: CountryFeasibilityUpdate
) -> CountryFeasibility:
    svc = get_study_startup_service()
    updated = svc.update_country_feasibility(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Country feasibility '{assessment_id}' not found")
    return updated


@router.delete(
    "/countries/{assessment_id}",
    status_code=204,
    summary="Delete a country feasibility assessment",
)
async def delete_country_feasibility(assessment_id: str) -> None:
    svc = get_study_startup_service()
    deleted = svc.delete_country_feasibility(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Country feasibility '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Startup Timelines
# ---------------------------------------------------------------------------


@router.get(
    "/timelines/critical-path",
    response_model=list[CriticalPath],
    summary="Get critical path analysis",
    description="Compute critical path analysis for each site's startup, identifying delays and bottlenecks.",
)
async def get_critical_path(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> list[CriticalPath]:
    svc = get_study_startup_service()
    return svc.get_critical_path(trial_id=trial_id)


@router.get(
    "/timelines",
    response_model=StartupTimelineListResponse,
    summary="List startup timelines",
    description="Retrieve startup timeline entries with optional filtering by trial, site, and phase.",
)
async def list_startup_timelines(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    phase: Optional[StartupPhase] = Query(None, description="Filter by startup phase"),
) -> StartupTimelineListResponse:
    svc = get_study_startup_service()
    items = svc.list_startup_timelines(trial_id=trial_id, site_id=site_id, phase=phase)
    return StartupTimelineListResponse(items=items, total=len(items))


@router.get(
    "/timelines/{timeline_id}",
    response_model=StartupTimeline,
    summary="Get a startup timeline entry",
)
async def get_startup_timeline(timeline_id: str) -> StartupTimeline:
    svc = get_study_startup_service()
    result = svc.get_startup_timeline(timeline_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Startup timeline '{timeline_id}' not found")
    return result


@router.post(
    "/timelines",
    response_model=StartupTimeline,
    status_code=201,
    summary="Create a startup timeline entry",
)
async def create_startup_timeline(payload: StartupTimelineCreate) -> StartupTimeline:
    svc = get_study_startup_service()
    return svc.create_startup_timeline(payload)


@router.put(
    "/timelines/{timeline_id}",
    response_model=StartupTimeline,
    summary="Update a startup timeline entry",
    description="Update timeline entry including actual dates, blockers, and milestone notes.",
)
async def update_startup_timeline(
    timeline_id: str, payload: StartupTimelineUpdate
) -> StartupTimeline:
    svc = get_study_startup_service()
    updated = svc.update_startup_timeline(timeline_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Startup timeline '{timeline_id}' not found")
    return updated


@router.delete(
    "/timelines/{timeline_id}",
    status_code=204,
    summary="Delete a startup timeline entry",
)
async def delete_startup_timeline(timeline_id: str) -> None:
    svc = get_study_startup_service()
    deleted = svc.delete_startup_timeline(timeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Startup timeline '{timeline_id}' not found")


# ---------------------------------------------------------------------------
# Protocol Feasibility
# ---------------------------------------------------------------------------


@router.get(
    "/protocols",
    response_model=ProtocolFeasibilityListResponse,
    summary="List protocol feasibility assessments",
    description="Retrieve protocol feasibility assessments with optional filtering by trial.",
)
async def list_protocol_feasibilities(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ProtocolFeasibilityListResponse:
    svc = get_study_startup_service()
    items = svc.list_protocol_feasibilities(trial_id=trial_id)
    return ProtocolFeasibilityListResponse(items=items, total=len(items))


@router.get(
    "/protocols/{assessment_id}",
    response_model=ProtocolFeasibility,
    summary="Get a protocol feasibility assessment",
)
async def get_protocol_feasibility(assessment_id: str) -> ProtocolFeasibility:
    svc = get_study_startup_service()
    result = svc.get_protocol_feasibility(assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Protocol feasibility '{assessment_id}' not found")
    return result


@router.post(
    "/protocols",
    response_model=ProtocolFeasibility,
    status_code=201,
    summary="Create a protocol feasibility assessment",
)
async def create_protocol_feasibility(
    payload: ProtocolFeasibilityCreate,
) -> ProtocolFeasibility:
    svc = get_study_startup_service()
    return svc.create_protocol_feasibility(payload)


@router.get(
    "/protocols/{trial_id}/screen-failure",
    response_model=ScreenFailurePrediction,
    summary="Predict screen failure rate",
    description="Predict screen failure rate based on protocol criteria complexity and visit schedule.",
)
async def predict_screen_failure(trial_id: str) -> ScreenFailurePrediction:
    svc = get_study_startup_service()
    result = svc.predict_screen_failure_rate(trial_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No protocol feasibility found for trial '{trial_id}'",
        )
    return result


# ---------------------------------------------------------------------------
# Bottleneck Analysis & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/bottleneck-analysis",
    response_model=list[BottleneckAnalysis],
    summary="Get bottleneck analysis",
    description="Analyze which startup phases cause the most delays across all sites.",
)
async def get_bottleneck_analysis() -> list[BottleneckAnalysis]:
    svc = get_study_startup_service()
    return svc.get_bottleneck_analysis()


@router.get(
    "/metrics",
    response_model=StartupMetrics,
    summary="Get study startup metrics",
    description="Aggregated study startup operational metrics across all trials and sites.",
)
async def get_metrics() -> StartupMetrics:
    svc = get_study_startup_service()
    return svc.get_metrics()
