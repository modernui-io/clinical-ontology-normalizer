"""User Analytics & Feature Flag Management API endpoints (VP-Product-9).

Provides event tracking, session management, feature flag CRUD with
rollout strategy evaluation, funnel analysis, retention cohort analysis,
and product health metrics for the clinical trial recruitment platform.

Endpoints:
    POST /user-analytics/events                         - Track event
    GET  /user-analytics/events                         - List with filters
    GET  /user-analytics/events/count                   - Event counts by category
    GET  /user-analytics/sessions                       - List sessions
    GET  /user-analytics/sessions/{session_id}          - Session detail
    POST /user-analytics/sessions                       - Create session
    PUT  /user-analytics/sessions/{session_id}/end      - End session
    GET  /user-analytics/feature-flags                  - List flags
    POST /user-analytics/feature-flags                  - Create flag
    GET  /user-analytics/feature-flags/{flag_id}        - Get flag
    PUT  /user-analytics/feature-flags/{flag_id}        - Update flag
    DELETE /user-analytics/feature-flags/{flag_id}      - Archive flag
    POST /user-analytics/feature-flags/{flag_id}/evaluate  - Evaluate for user
    GET  /user-analytics/funnels                        - Funnel analysis
    GET  /user-analytics/retention                      - Retention cohorts
    GET  /user-analytics/metrics                        - Product health
    GET  /user-analytics/top-events                     - Top events
    GET  /user-analytics/top-pages                      - Top pages
    GET  /user-analytics/event-rate                     - Event rate
    GET  /user-analytics/segments                       - User segments
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.user_analytics import (
    AnalyticsEvent,
    EventCategory,
    EventCreateRequest,
    EventListResponse,
    FeatureFlag,
    FeatureFlagCreateRequest,
    FeatureFlagUpdateRequest,
    FlagEvaluation,
    FlagEvaluateRequest,
    FlagListResponse,
    FlagStatus,
    FunnelAnalysis,
    FunnelRequest,
    FunnelStage,
    ProductHealthReport,
    RetentionCohort,
    RetentionPeriod,
    RetentionRequest,
    SessionCreateRequest,
    UserAnalyticsMetrics,
    UserSession,
)
from app.services.user_analytics_service import get_user_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/user-analytics",
    tags=["User Analytics"],
)


# ---------------------------------------------------------------------------
# Event tracking
# ---------------------------------------------------------------------------


@router.post(
    "/events",
    response_model=AnalyticsEvent,
    summary="Track analytics event",
    description="Record a user analytics event for tracking and analysis.",
)
async def track_event(request: EventCreateRequest) -> AnalyticsEvent:
    """Track a new analytics event."""
    svc = get_user_analytics_service()
    return svc.track_event(request)


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="List analytics events",
    description="Retrieve analytics events with optional filtering by user, category, date range, and event name.",
)
async def list_events(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    category: Optional[EventCategory] = Query(None, description="Filter by event category"),
    event_name: Optional[str] = Query(None, description="Filter by event name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> EventListResponse:
    """List events with filtering and pagination."""
    svc = get_user_analytics_service()
    items, total = svc.list_events(
        user_id=user_id,
        category=category,
        event_name=event_name,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/events/count",
    response_model=dict[str, int],
    summary="Event counts by category",
    description="Return the number of events grouped by category.",
)
async def count_events() -> dict[str, int]:
    """Count events by category."""
    svc = get_user_analytics_service()
    return svc.count_events_by_category()


# ---------------------------------------------------------------------------
# Session tracking
# ---------------------------------------------------------------------------


@router.get(
    "/sessions",
    summary="List sessions",
    description="Retrieve user sessions with optional filtering by user.",
)
async def list_sessions(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> dict[str, Any]:
    """List sessions with filtering and pagination."""
    svc = get_user_analytics_service()
    items, total = svc.list_sessions(user_id=user_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/sessions/{session_id}",
    response_model=UserSession,
    summary="Get session detail",
    description="Retrieve details of a specific session.",
)
async def get_session(session_id: str) -> UserSession:
    """Get session detail."""
    svc = get_user_analytics_service()
    try:
        return svc.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.post(
    "/sessions",
    response_model=UserSession,
    summary="Create session",
    description="Create a new user session.",
)
async def create_session(request: SessionCreateRequest) -> UserSession:
    """Create a new session."""
    svc = get_user_analytics_service()
    return svc.create_session(
        user_id=request.user_id,
        device_type=request.device_type,
        browser=request.browser,
    )


@router.put(
    "/sessions/{session_id}/end",
    response_model=UserSession,
    summary="End session",
    description="Mark a session as ended.",
)
async def end_session(session_id: str) -> UserSession:
    """End an active session."""
    svc = get_user_analytics_service()
    try:
        return svc.end_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


@router.get(
    "/feature-flags",
    response_model=FlagListResponse,
    summary="List feature flags",
    description="Retrieve all feature flags, optionally filtered by status.",
)
async def list_flags(
    status: Optional[FlagStatus] = Query(None, description="Filter by status"),
) -> FlagListResponse:
    """List feature flags."""
    svc = get_user_analytics_service()
    items = svc.list_flags(status=status)
    return FlagListResponse(items=items, total=len(items))


@router.post(
    "/feature-flags",
    response_model=FeatureFlag,
    summary="Create feature flag",
    description="Create a new feature flag with rollout configuration.",
)
async def create_flag(request: FeatureFlagCreateRequest) -> FeatureFlag:
    """Create a new feature flag."""
    svc = get_user_analytics_service()
    return svc.create_flag(request)


@router.get(
    "/feature-flags/{flag_id}",
    response_model=FeatureFlag,
    summary="Get feature flag",
    description="Retrieve details of a specific feature flag.",
)
async def get_flag(flag_id: str) -> FeatureFlag:
    """Get feature flag detail."""
    svc = get_user_analytics_service()
    try:
        return svc.get_flag(flag_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Feature flag {flag_id} not found")


@router.put(
    "/feature-flags/{flag_id}",
    response_model=FeatureFlag,
    summary="Update feature flag",
    description="Update an existing feature flag.",
)
async def update_flag(flag_id: str, request: FeatureFlagUpdateRequest) -> FeatureFlag:
    """Update feature flag."""
    svc = get_user_analytics_service()
    try:
        return svc.update_flag(flag_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Feature flag {flag_id} not found")


@router.delete(
    "/feature-flags/{flag_id}",
    response_model=FeatureFlag,
    summary="Archive feature flag",
    description="Archive a feature flag (soft delete).",
)
async def archive_flag(flag_id: str) -> FeatureFlag:
    """Archive a feature flag."""
    svc = get_user_analytics_service()
    try:
        return svc.archive_flag(flag_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Feature flag {flag_id} not found")


@router.post(
    "/feature-flags/{flag_id}/evaluate",
    response_model=FlagEvaluation,
    summary="Evaluate feature flag",
    description="Evaluate a feature flag for a specific user based on rollout strategy.",
)
async def evaluate_flag(flag_id: str, request: FlagEvaluateRequest) -> FlagEvaluation:
    """Evaluate a feature flag for a user."""
    svc = get_user_analytics_service()
    try:
        return svc.evaluate_flag(flag_id, request.user_id, request.role)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Feature flag {flag_id} not found")


# ---------------------------------------------------------------------------
# Analytics & Reporting
# ---------------------------------------------------------------------------


@router.get(
    "/funnels",
    response_model=FunnelAnalysis,
    summary="Funnel analysis",
    description="Compute funnel conversion analysis across screening stages.",
)
async def get_funnel(
    funnel_name: str = Query("trial_screening", description="Funnel name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> FunnelAnalysis:
    """Get funnel analysis."""
    svc = get_user_analytics_service()
    return svc.analyze_funnel(
        funnel_name=funnel_name,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/retention",
    response_model=list[RetentionCohort],
    summary="Retention cohorts",
    description="Compute retention cohort analysis over configurable periods.",
)
async def get_retention(
    period: RetentionPeriod = Query(RetentionPeriod.WEEKLY, description="Retention period"),
    num_cohorts: int = Query(4, ge=1, le=12, description="Number of cohorts"),
    num_periods: int = Query(6, ge=1, le=24, description="Periods per cohort"),
) -> list[RetentionCohort]:
    """Get retention cohort analysis."""
    svc = get_user_analytics_service()
    return svc.analyze_retention(
        period=period,
        num_cohorts=num_cohorts,
        num_periods=num_periods,
    )


@router.get(
    "/metrics",
    response_model=ProductHealthReport,
    summary="Product health metrics",
    description="Generate a comprehensive product health report with DAU/WAU/MAU, session metrics, and feature adoption.",
)
async def get_product_health() -> ProductHealthReport:
    """Get product health metrics."""
    svc = get_user_analytics_service()
    return svc.get_product_health()


@router.get(
    "/top-events",
    response_model=list[dict[str, Any]],
    summary="Top events",
    description="Return the most frequent events ranked by count.",
)
async def get_top_events(
    limit: int = Query(10, ge=1, le=50, description="Number of events to return"),
) -> list[dict[str, Any]]:
    """Get top events by count."""
    svc = get_user_analytics_service()
    return svc.get_top_events(limit=limit)


@router.get(
    "/top-pages",
    response_model=list[dict[str, Any]],
    summary="Top pages",
    description="Return the most viewed pages ranked by view count.",
)
async def get_top_pages(
    limit: int = Query(10, ge=1, le=50, description="Number of pages to return"),
) -> list[dict[str, Any]]:
    """Get top pages by views."""
    svc = get_user_analytics_service()
    return svc.get_top_pages(limit=limit)


@router.get(
    "/event-rate",
    summary="Event rate",
    description="Calculate the event rate (events per minute) over a given time window.",
)
async def get_event_rate(
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
) -> dict[str, Any]:
    """Get event rate over a time window."""
    svc = get_user_analytics_service()
    rate = svc.get_event_rate(window_minutes=window_minutes)
    return {"window_minutes": window_minutes, "events_per_minute": rate}


@router.get(
    "/segments",
    summary="User segments",
    description="Segment users by behavior patterns (power, regular, casual, inactive).",
)
async def get_segments() -> dict[str, list[str]]:
    """Get user segments by behavior."""
    svc = get_user_analytics_service()
    return svc.get_user_segments()
