"""Clinical Operations Analytics API endpoints (CLIN-OPS-ANLY).

Provides comprehensive clinical operations analytics: enrollment velocity
tracking, site performance scorecards, protocol deviation trending,
resource utilization analysis, and milestone achievement with metrics.

Endpoints:
    GET    /clinical-operations-analytics/enrollment-velocities                     - List enrollment velocities
    GET    /clinical-operations-analytics/enrollment-velocities/{velocity_id}       - Get single velocity
    POST   /clinical-operations-analytics/enrollment-velocities                     - Create velocity
    PUT    /clinical-operations-analytics/enrollment-velocities/{velocity_id}       - Update velocity
    DELETE /clinical-operations-analytics/enrollment-velocities/{velocity_id}       - Delete velocity
    GET    /clinical-operations-analytics/site-performance-scorecards               - List scorecards
    GET    /clinical-operations-analytics/site-performance-scorecards/{id}          - Get single scorecard
    POST   /clinical-operations-analytics/site-performance-scorecards               - Create scorecard
    PUT    /clinical-operations-analytics/site-performance-scorecards/{id}          - Update scorecard
    DELETE /clinical-operations-analytics/site-performance-scorecards/{id}          - Delete scorecard
    GET    /clinical-operations-analytics/protocol-deviation-trends                 - List deviation trends
    GET    /clinical-operations-analytics/protocol-deviation-trends/{id}            - Get single trend
    POST   /clinical-operations-analytics/protocol-deviation-trends                 - Create trend
    PUT    /clinical-operations-analytics/protocol-deviation-trends/{id}            - Update trend
    DELETE /clinical-operations-analytics/protocol-deviation-trends/{id}            - Delete trend
    GET    /clinical-operations-analytics/resource-utilizations                     - List utilizations
    GET    /clinical-operations-analytics/resource-utilizations/{id}                - Get single utilization
    POST   /clinical-operations-analytics/resource-utilizations                     - Create utilization
    PUT    /clinical-operations-analytics/resource-utilizations/{id}                - Update utilization
    DELETE /clinical-operations-analytics/resource-utilizations/{id}                - Delete utilization
    GET    /clinical-operations-analytics/milestone-achievements                    - List milestones
    GET    /clinical-operations-analytics/milestone-achievements/{id}               - Get single milestone
    POST   /clinical-operations-analytics/milestone-achievements                    - Create milestone
    PUT    /clinical-operations-analytics/milestone-achievements/{id}               - Update milestone
    DELETE /clinical-operations-analytics/milestone-achievements/{id}               - Delete milestone
    GET    /clinical-operations-analytics/metrics                                   - Operations analytics metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_operations_analytics import (
    ClinicalOperationsAnalyticsMetrics,
    DeviationCategory,
    EnrollmentVelocity,
    EnrollmentVelocityCreate,
    EnrollmentVelocityListResponse,
    EnrollmentVelocityUpdate,
    MilestoneAchievement,
    MilestoneAchievementCreate,
    MilestoneAchievementListResponse,
    MilestoneAchievementUpdate,
    MilestoneCategory,
    PerformanceTier,
    ProtocolDeviationTrend,
    ProtocolDeviationTrendCreate,
    ProtocolDeviationTrendListResponse,
    ProtocolDeviationTrendUpdate,
    ResourceType,
    ResourceUtilization,
    ResourceUtilizationCreate,
    ResourceUtilizationListResponse,
    ResourceUtilizationUpdate,
    SitePerformanceScorecard,
    SitePerformanceScorecardCreate,
    SitePerformanceScorecardListResponse,
    SitePerformanceScorecardUpdate,
    VelocityTrend,
)
from app.services.clinical_operations_analytics_service import (
    get_clinical_operations_analytics_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-operations-analytics",
    tags=["Clinical Operations Analytics"],
)


# ---------------------------------------------------------------------------
# Enrollment Velocities
# ---------------------------------------------------------------------------


@router.get(
    "/enrollment-velocities",
    response_model=EnrollmentVelocityListResponse,
    summary="List enrollment velocities",
    description="Retrieve enrollment velocities with optional filtering by trial and velocity trend.",
)
async def list_enrollment_velocities(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    velocity_trend: Optional[VelocityTrend] = Query(None, description="Filter by velocity trend"),
) -> EnrollmentVelocityListResponse:
    svc = get_clinical_operations_analytics_service()
    items = svc.list_enrollment_velocities(
        trial_id=trial_id, velocity_trend=velocity_trend
    )
    return EnrollmentVelocityListResponse(items=items, total=len(items))


@router.get(
    "/enrollment-velocities/{velocity_id}",
    response_model=EnrollmentVelocity,
    summary="Get an enrollment velocity",
)
async def get_enrollment_velocity(velocity_id: str) -> EnrollmentVelocity:
    svc = get_clinical_operations_analytics_service()
    velocity = svc.get_enrollment_velocity(velocity_id)
    if velocity is None:
        raise HTTPException(
            status_code=404, detail=f"Enrollment velocity '{velocity_id}' not found"
        )
    return velocity


@router.post(
    "/enrollment-velocities",
    response_model=EnrollmentVelocity,
    status_code=201,
    summary="Create an enrollment velocity",
)
async def create_enrollment_velocity(payload: EnrollmentVelocityCreate) -> EnrollmentVelocity:
    svc = get_clinical_operations_analytics_service()
    return svc.create_enrollment_velocity(payload)


@router.put(
    "/enrollment-velocities/{velocity_id}",
    response_model=EnrollmentVelocity,
    summary="Update an enrollment velocity",
)
async def update_enrollment_velocity(
    velocity_id: str, payload: EnrollmentVelocityUpdate
) -> EnrollmentVelocity:
    svc = get_clinical_operations_analytics_service()
    updated = svc.update_enrollment_velocity(velocity_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Enrollment velocity '{velocity_id}' not found"
        )
    return updated


@router.delete(
    "/enrollment-velocities/{velocity_id}",
    status_code=204,
    summary="Delete an enrollment velocity",
)
async def delete_enrollment_velocity(velocity_id: str) -> None:
    svc = get_clinical_operations_analytics_service()
    deleted = svc.delete_enrollment_velocity(velocity_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Enrollment velocity '{velocity_id}' not found"
        )


# ---------------------------------------------------------------------------
# Site Performance Scorecards
# ---------------------------------------------------------------------------


@router.get(
    "/site-performance-scorecards",
    response_model=SitePerformanceScorecardListResponse,
    summary="List site performance scorecards",
    description="Retrieve site performance scorecards with optional filtering by trial and performance tier.",
)
async def list_site_performance_scorecards(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    performance_tier: Optional[PerformanceTier] = Query(
        None, description="Filter by performance tier"
    ),
) -> SitePerformanceScorecardListResponse:
    svc = get_clinical_operations_analytics_service()
    items = svc.list_site_performance_scorecards(
        trial_id=trial_id, performance_tier=performance_tier
    )
    return SitePerformanceScorecardListResponse(items=items, total=len(items))


@router.get(
    "/site-performance-scorecards/{scorecard_id}",
    response_model=SitePerformanceScorecard,
    summary="Get a site performance scorecard",
)
async def get_site_performance_scorecard(scorecard_id: str) -> SitePerformanceScorecard:
    svc = get_clinical_operations_analytics_service()
    scorecard = svc.get_site_performance_scorecard(scorecard_id)
    if scorecard is None:
        raise HTTPException(
            status_code=404,
            detail=f"Site performance scorecard '{scorecard_id}' not found",
        )
    return scorecard


@router.post(
    "/site-performance-scorecards",
    response_model=SitePerformanceScorecard,
    status_code=201,
    summary="Create a site performance scorecard",
)
async def create_site_performance_scorecard(
    payload: SitePerformanceScorecardCreate,
) -> SitePerformanceScorecard:
    svc = get_clinical_operations_analytics_service()
    return svc.create_site_performance_scorecard(payload)


@router.put(
    "/site-performance-scorecards/{scorecard_id}",
    response_model=SitePerformanceScorecard,
    summary="Update a site performance scorecard",
)
async def update_site_performance_scorecard(
    scorecard_id: str, payload: SitePerformanceScorecardUpdate
) -> SitePerformanceScorecard:
    svc = get_clinical_operations_analytics_service()
    updated = svc.update_site_performance_scorecard(scorecard_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Site performance scorecard '{scorecard_id}' not found",
        )
    return updated


@router.delete(
    "/site-performance-scorecards/{scorecard_id}",
    status_code=204,
    summary="Delete a site performance scorecard",
)
async def delete_site_performance_scorecard(scorecard_id: str) -> None:
    svc = get_clinical_operations_analytics_service()
    deleted = svc.delete_site_performance_scorecard(scorecard_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Site performance scorecard '{scorecard_id}' not found",
        )


# ---------------------------------------------------------------------------
# Protocol Deviation Trends
# ---------------------------------------------------------------------------


@router.get(
    "/protocol-deviation-trends",
    response_model=ProtocolDeviationTrendListResponse,
    summary="List protocol deviation trends",
    description="Retrieve protocol deviation trends with optional filtering by trial and deviation category.",
)
async def list_protocol_deviation_trends(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    deviation_category: Optional[DeviationCategory] = Query(
        None, description="Filter by deviation category"
    ),
) -> ProtocolDeviationTrendListResponse:
    svc = get_clinical_operations_analytics_service()
    items = svc.list_protocol_deviation_trends(
        trial_id=trial_id, deviation_category=deviation_category
    )
    return ProtocolDeviationTrendListResponse(items=items, total=len(items))


@router.get(
    "/protocol-deviation-trends/{trend_id}",
    response_model=ProtocolDeviationTrend,
    summary="Get a protocol deviation trend",
)
async def get_protocol_deviation_trend(trend_id: str) -> ProtocolDeviationTrend:
    svc = get_clinical_operations_analytics_service()
    trend = svc.get_protocol_deviation_trend(trend_id)
    if trend is None:
        raise HTTPException(
            status_code=404,
            detail=f"Protocol deviation trend '{trend_id}' not found",
        )
    return trend


@router.post(
    "/protocol-deviation-trends",
    response_model=ProtocolDeviationTrend,
    status_code=201,
    summary="Create a protocol deviation trend",
)
async def create_protocol_deviation_trend(
    payload: ProtocolDeviationTrendCreate,
) -> ProtocolDeviationTrend:
    svc = get_clinical_operations_analytics_service()
    return svc.create_protocol_deviation_trend(payload)


@router.put(
    "/protocol-deviation-trends/{trend_id}",
    response_model=ProtocolDeviationTrend,
    summary="Update a protocol deviation trend",
)
async def update_protocol_deviation_trend(
    trend_id: str, payload: ProtocolDeviationTrendUpdate
) -> ProtocolDeviationTrend:
    svc = get_clinical_operations_analytics_service()
    updated = svc.update_protocol_deviation_trend(trend_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Protocol deviation trend '{trend_id}' not found",
        )
    return updated


@router.delete(
    "/protocol-deviation-trends/{trend_id}",
    status_code=204,
    summary="Delete a protocol deviation trend",
)
async def delete_protocol_deviation_trend(trend_id: str) -> None:
    svc = get_clinical_operations_analytics_service()
    deleted = svc.delete_protocol_deviation_trend(trend_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Protocol deviation trend '{trend_id}' not found",
        )


# ---------------------------------------------------------------------------
# Resource Utilizations
# ---------------------------------------------------------------------------


@router.get(
    "/resource-utilizations",
    response_model=ResourceUtilizationListResponse,
    summary="List resource utilizations",
    description="Retrieve resource utilizations with optional filtering by trial and resource type.",
)
async def list_resource_utilizations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    resource_type: Optional[ResourceType] = Query(
        None, description="Filter by resource type"
    ),
) -> ResourceUtilizationListResponse:
    svc = get_clinical_operations_analytics_service()
    items = svc.list_resource_utilizations(
        trial_id=trial_id, resource_type=resource_type
    )
    return ResourceUtilizationListResponse(items=items, total=len(items))


@router.get(
    "/resource-utilizations/{utilization_id}",
    response_model=ResourceUtilization,
    summary="Get a resource utilization",
)
async def get_resource_utilization(utilization_id: str) -> ResourceUtilization:
    svc = get_clinical_operations_analytics_service()
    utilization = svc.get_resource_utilization(utilization_id)
    if utilization is None:
        raise HTTPException(
            status_code=404,
            detail=f"Resource utilization '{utilization_id}' not found",
        )
    return utilization


@router.post(
    "/resource-utilizations",
    response_model=ResourceUtilization,
    status_code=201,
    summary="Create a resource utilization",
)
async def create_resource_utilization(
    payload: ResourceUtilizationCreate,
) -> ResourceUtilization:
    svc = get_clinical_operations_analytics_service()
    return svc.create_resource_utilization(payload)


@router.put(
    "/resource-utilizations/{utilization_id}",
    response_model=ResourceUtilization,
    summary="Update a resource utilization",
)
async def update_resource_utilization(
    utilization_id: str, payload: ResourceUtilizationUpdate
) -> ResourceUtilization:
    svc = get_clinical_operations_analytics_service()
    updated = svc.update_resource_utilization(utilization_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Resource utilization '{utilization_id}' not found",
        )
    return updated


@router.delete(
    "/resource-utilizations/{utilization_id}",
    status_code=204,
    summary="Delete a resource utilization",
)
async def delete_resource_utilization(utilization_id: str) -> None:
    svc = get_clinical_operations_analytics_service()
    deleted = svc.delete_resource_utilization(utilization_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Resource utilization '{utilization_id}' not found",
        )


# ---------------------------------------------------------------------------
# Milestone Achievements
# ---------------------------------------------------------------------------


@router.get(
    "/milestone-achievements",
    response_model=MilestoneAchievementListResponse,
    summary="List milestone achievements",
    description="Retrieve milestone achievements with optional filtering by trial and milestone category.",
)
async def list_milestone_achievements(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    milestone_category: Optional[MilestoneCategory] = Query(
        None, description="Filter by milestone category"
    ),
) -> MilestoneAchievementListResponse:
    svc = get_clinical_operations_analytics_service()
    items = svc.list_milestone_achievements(
        trial_id=trial_id, milestone_category=milestone_category
    )
    return MilestoneAchievementListResponse(items=items, total=len(items))


@router.get(
    "/milestone-achievements/{milestone_id}",
    response_model=MilestoneAchievement,
    summary="Get a milestone achievement",
)
async def get_milestone_achievement(milestone_id: str) -> MilestoneAchievement:
    svc = get_clinical_operations_analytics_service()
    milestone = svc.get_milestone_achievement(milestone_id)
    if milestone is None:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone achievement '{milestone_id}' not found",
        )
    return milestone


@router.post(
    "/milestone-achievements",
    response_model=MilestoneAchievement,
    status_code=201,
    summary="Create a milestone achievement",
)
async def create_milestone_achievement(
    payload: MilestoneAchievementCreate,
) -> MilestoneAchievement:
    svc = get_clinical_operations_analytics_service()
    return svc.create_milestone_achievement(payload)


@router.put(
    "/milestone-achievements/{milestone_id}",
    response_model=MilestoneAchievement,
    summary="Update a milestone achievement",
)
async def update_milestone_achievement(
    milestone_id: str, payload: MilestoneAchievementUpdate
) -> MilestoneAchievement:
    svc = get_clinical_operations_analytics_service()
    updated = svc.update_milestone_achievement(milestone_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone achievement '{milestone_id}' not found",
        )
    return updated


@router.delete(
    "/milestone-achievements/{milestone_id}",
    status_code=204,
    summary="Delete a milestone achievement",
)
async def delete_milestone_achievement(milestone_id: str) -> None:
    svc = get_clinical_operations_analytics_service()
    deleted = svc.delete_milestone_achievement(milestone_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone achievement '{milestone_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalOperationsAnalyticsMetrics,
    summary="Get clinical operations analytics metrics",
    description="Returns aggregated metrics across all clinical operations analytics data.",
)
async def get_metrics() -> ClinicalOperationsAnalyticsMetrics:
    svc = get_clinical_operations_analytics_service()
    return svc.get_metrics()
