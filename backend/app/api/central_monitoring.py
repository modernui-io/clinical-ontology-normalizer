"""Central Monitoring Management API endpoints (CTR-MON).

Provides comprehensive central monitoring operations: remote monitoring visits,
KRI signal detection, site risk indicators, monitoring action items,
centralized review activities, and central monitoring operational metrics.

Endpoints:
    GET    /central-monitoring/monitoring-visits                     - List monitoring visits
    GET    /central-monitoring/monitoring-visits/{visit_id}          - Get single visit
    POST   /central-monitoring/monitoring-visits                     - Create visit
    PUT    /central-monitoring/monitoring-visits/{visit_id}          - Update visit
    DELETE /central-monitoring/monitoring-visits/{visit_id}          - Delete visit

    GET    /central-monitoring/kri-signals                           - List KRI signals
    GET    /central-monitoring/kri-signals/{signal_id}               - Get single signal
    POST   /central-monitoring/kri-signals                           - Create signal
    PUT    /central-monitoring/kri-signals/{signal_id}               - Update signal
    DELETE /central-monitoring/kri-signals/{signal_id}               - Delete signal

    GET    /central-monitoring/site-risk-indicators                  - List site risk indicators
    GET    /central-monitoring/site-risk-indicators/{indicator_id}   - Get single indicator
    POST   /central-monitoring/site-risk-indicators                  - Create indicator
    PUT    /central-monitoring/site-risk-indicators/{indicator_id}   - Update indicator
    DELETE /central-monitoring/site-risk-indicators/{indicator_id}   - Delete indicator

    GET    /central-monitoring/monitoring-actions                    - List monitoring actions
    GET    /central-monitoring/monitoring-actions/{action_id}        - Get single action
    POST   /central-monitoring/monitoring-actions                    - Create action
    PUT    /central-monitoring/monitoring-actions/{action_id}        - Update action
    DELETE /central-monitoring/monitoring-actions/{action_id}        - Delete action

    GET    /central-monitoring/central-reviews                       - List central reviews
    GET    /central-monitoring/central-reviews/{review_id}           - Get single review
    POST   /central-monitoring/central-reviews                       - Create review
    PUT    /central-monitoring/central-reviews/{review_id}           - Update review
    DELETE /central-monitoring/central-reviews/{review_id}           - Delete review

    GET    /central-monitoring/metrics                               - Central monitoring metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.central_monitoring import (
    CentralMonitoringMetrics,
    CentralReview,
    CentralReviewCreate,
    CentralReviewListResponse,
    CentralReviewUpdate,
    KRISignal,
    KRISignalCreate,
    KRISignalListResponse,
    KRISignalUpdate,
    MonitoringAction,
    MonitoringActionCreate,
    MonitoringActionListResponse,
    MonitoringActionUpdate,
    MonitoringVisit,
    MonitoringVisitCreate,
    MonitoringVisitListResponse,
    MonitoringVisitUpdate,
    SiteRiskIndicator,
    SiteRiskIndicatorCreate,
    SiteRiskIndicatorListResponse,
    SiteRiskIndicatorUpdate,
)
from app.services.central_monitoring_service import get_central_monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/central-monitoring",
    tags=["Central Monitoring"],
)


# ---------------------------------------------------------------------------
# Monitoring Visits
# ---------------------------------------------------------------------------


@router.get(
    "/monitoring-visits",
    response_model=MonitoringVisitListResponse,
    summary="List monitoring visits",
    description="Retrieve monitoring visits with optional filtering by trial ID.",
)
async def list_monitoring_visits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> MonitoringVisitListResponse:
    svc = get_central_monitoring_service()
    items = svc.list_monitoring_visits(trial_id=trial_id)
    return MonitoringVisitListResponse(items=items, total=len(items))


@router.get(
    "/monitoring-visits/{visit_id}",
    response_model=MonitoringVisit,
    summary="Get a monitoring visit",
)
async def get_monitoring_visit(visit_id: str) -> MonitoringVisit:
    svc = get_central_monitoring_service()
    visit = svc.get_monitoring_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"Monitoring visit '{visit_id}' not found")
    return visit


@router.post(
    "/monitoring-visits",
    response_model=MonitoringVisit,
    status_code=201,
    summary="Create a monitoring visit",
)
async def create_monitoring_visit(payload: MonitoringVisitCreate) -> MonitoringVisit:
    svc = get_central_monitoring_service()
    return svc.create_monitoring_visit(payload)


@router.put(
    "/monitoring-visits/{visit_id}",
    response_model=MonitoringVisit,
    summary="Update a monitoring visit",
)
async def update_monitoring_visit(
    visit_id: str, payload: MonitoringVisitUpdate
) -> MonitoringVisit:
    svc = get_central_monitoring_service()
    updated = svc.update_monitoring_visit(visit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Monitoring visit '{visit_id}' not found")
    return updated


@router.delete(
    "/monitoring-visits/{visit_id}",
    status_code=204,
    summary="Delete a monitoring visit",
)
async def delete_monitoring_visit(visit_id: str) -> None:
    svc = get_central_monitoring_service()
    deleted = svc.delete_monitoring_visit(visit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Monitoring visit '{visit_id}' not found")


# ---------------------------------------------------------------------------
# KRI Signals
# ---------------------------------------------------------------------------


@router.get(
    "/kri-signals",
    response_model=KRISignalListResponse,
    summary="List KRI signals",
    description="Retrieve KRI signals with optional filtering by trial ID.",
)
async def list_kri_signals(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> KRISignalListResponse:
    svc = get_central_monitoring_service()
    items = svc.list_kri_signals(trial_id=trial_id)
    return KRISignalListResponse(items=items, total=len(items))


@router.get(
    "/kri-signals/{signal_id}",
    response_model=KRISignal,
    summary="Get a KRI signal",
)
async def get_kri_signal(signal_id: str) -> KRISignal:
    svc = get_central_monitoring_service()
    signal = svc.get_kri_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"KRI signal '{signal_id}' not found")
    return signal


@router.post(
    "/kri-signals",
    response_model=KRISignal,
    status_code=201,
    summary="Create a KRI signal",
)
async def create_kri_signal(payload: KRISignalCreate) -> KRISignal:
    svc = get_central_monitoring_service()
    return svc.create_kri_signal(payload)


@router.put(
    "/kri-signals/{signal_id}",
    response_model=KRISignal,
    summary="Update a KRI signal",
)
async def update_kri_signal(signal_id: str, payload: KRISignalUpdate) -> KRISignal:
    svc = get_central_monitoring_service()
    updated = svc.update_kri_signal(signal_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"KRI signal '{signal_id}' not found")
    return updated


@router.delete(
    "/kri-signals/{signal_id}",
    status_code=204,
    summary="Delete a KRI signal",
)
async def delete_kri_signal(signal_id: str) -> None:
    svc = get_central_monitoring_service()
    deleted = svc.delete_kri_signal(signal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"KRI signal '{signal_id}' not found")


# ---------------------------------------------------------------------------
# Site Risk Indicators
# ---------------------------------------------------------------------------


@router.get(
    "/site-risk-indicators",
    response_model=SiteRiskIndicatorListResponse,
    summary="List site risk indicators",
    description="Retrieve site risk indicators with optional filtering by trial ID.",
)
async def list_site_risk_indicators(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SiteRiskIndicatorListResponse:
    svc = get_central_monitoring_service()
    items = svc.list_site_risk_indicators(trial_id=trial_id)
    return SiteRiskIndicatorListResponse(items=items, total=len(items))


@router.get(
    "/site-risk-indicators/{indicator_id}",
    response_model=SiteRiskIndicator,
    summary="Get a site risk indicator",
)
async def get_site_risk_indicator(indicator_id: str) -> SiteRiskIndicator:
    svc = get_central_monitoring_service()
    indicator = svc.get_site_risk_indicator(indicator_id)
    if indicator is None:
        raise HTTPException(
            status_code=404, detail=f"Site risk indicator '{indicator_id}' not found"
        )
    return indicator


@router.post(
    "/site-risk-indicators",
    response_model=SiteRiskIndicator,
    status_code=201,
    summary="Create a site risk indicator",
)
async def create_site_risk_indicator(
    payload: SiteRiskIndicatorCreate,
) -> SiteRiskIndicator:
    svc = get_central_monitoring_service()
    return svc.create_site_risk_indicator(payload)


@router.put(
    "/site-risk-indicators/{indicator_id}",
    response_model=SiteRiskIndicator,
    summary="Update a site risk indicator",
)
async def update_site_risk_indicator(
    indicator_id: str, payload: SiteRiskIndicatorUpdate
) -> SiteRiskIndicator:
    svc = get_central_monitoring_service()
    updated = svc.update_site_risk_indicator(indicator_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Site risk indicator '{indicator_id}' not found"
        )
    return updated


@router.delete(
    "/site-risk-indicators/{indicator_id}",
    status_code=204,
    summary="Delete a site risk indicator",
)
async def delete_site_risk_indicator(indicator_id: str) -> None:
    svc = get_central_monitoring_service()
    deleted = svc.delete_site_risk_indicator(indicator_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Site risk indicator '{indicator_id}' not found"
        )


# ---------------------------------------------------------------------------
# Monitoring Actions
# ---------------------------------------------------------------------------


@router.get(
    "/monitoring-actions",
    response_model=MonitoringActionListResponse,
    summary="List monitoring actions",
    description="Retrieve monitoring actions with optional filtering by trial ID.",
)
async def list_monitoring_actions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> MonitoringActionListResponse:
    svc = get_central_monitoring_service()
    items = svc.list_monitoring_actions(trial_id=trial_id)
    return MonitoringActionListResponse(items=items, total=len(items))


@router.get(
    "/monitoring-actions/{action_id}",
    response_model=MonitoringAction,
    summary="Get a monitoring action",
)
async def get_monitoring_action(action_id: str) -> MonitoringAction:
    svc = get_central_monitoring_service()
    action = svc.get_monitoring_action(action_id)
    if action is None:
        raise HTTPException(
            status_code=404, detail=f"Monitoring action '{action_id}' not found"
        )
    return action


@router.post(
    "/monitoring-actions",
    response_model=MonitoringAction,
    status_code=201,
    summary="Create a monitoring action",
)
async def create_monitoring_action(payload: MonitoringActionCreate) -> MonitoringAction:
    svc = get_central_monitoring_service()
    return svc.create_monitoring_action(payload)


@router.put(
    "/monitoring-actions/{action_id}",
    response_model=MonitoringAction,
    summary="Update a monitoring action",
)
async def update_monitoring_action(
    action_id: str, payload: MonitoringActionUpdate
) -> MonitoringAction:
    svc = get_central_monitoring_service()
    updated = svc.update_monitoring_action(action_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Monitoring action '{action_id}' not found"
        )
    return updated


@router.delete(
    "/monitoring-actions/{action_id}",
    status_code=204,
    summary="Delete a monitoring action",
)
async def delete_monitoring_action(action_id: str) -> None:
    svc = get_central_monitoring_service()
    deleted = svc.delete_monitoring_action(action_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Monitoring action '{action_id}' not found"
        )


# ---------------------------------------------------------------------------
# Central Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/central-reviews",
    response_model=CentralReviewListResponse,
    summary="List central reviews",
    description="Retrieve central reviews with optional filtering by trial ID.",
)
async def list_central_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CentralReviewListResponse:
    svc = get_central_monitoring_service()
    items = svc.list_central_reviews(trial_id=trial_id)
    return CentralReviewListResponse(items=items, total=len(items))


@router.get(
    "/central-reviews/{review_id}",
    response_model=CentralReview,
    summary="Get a central review",
)
async def get_central_review(review_id: str) -> CentralReview:
    svc = get_central_monitoring_service()
    review = svc.get_central_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Central review '{review_id}' not found")
    return review


@router.post(
    "/central-reviews",
    response_model=CentralReview,
    status_code=201,
    summary="Create a central review",
)
async def create_central_review(payload: CentralReviewCreate) -> CentralReview:
    svc = get_central_monitoring_service()
    return svc.create_central_review(payload)


@router.put(
    "/central-reviews/{review_id}",
    response_model=CentralReview,
    summary="Update a central review",
)
async def update_central_review(
    review_id: str, payload: CentralReviewUpdate
) -> CentralReview:
    svc = get_central_monitoring_service()
    updated = svc.update_central_review(review_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Central review '{review_id}' not found")
    return updated


@router.delete(
    "/central-reviews/{review_id}",
    status_code=204,
    summary="Delete a central review",
)
async def delete_central_review(review_id: str) -> None:
    svc = get_central_monitoring_service()
    deleted = svc.delete_central_review(review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Central review '{review_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CentralMonitoringMetrics,
    summary="Get central monitoring metrics",
    description="Aggregated central monitoring operational metrics across all trials and sites.",
)
async def get_metrics() -> CentralMonitoringMetrics:
    svc = get_central_monitoring_service()
    return svc.get_metrics()
