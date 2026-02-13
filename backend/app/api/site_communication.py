"""Site Communication API endpoints (SCM-MGT).

Provides comprehensive site communication operations: communication logs,
newsletter distributions, site query threads, site broadcast alerts, and
communication metrics.

Endpoints:
    GET    /site-communication/communication-logs                          - List communication logs
    GET    /site-communication/communication-logs/{log_id}                 - Get single log
    POST   /site-communication/communication-logs                          - Create log
    PUT    /site-communication/communication-logs/{log_id}                 - Update log
    DELETE /site-communication/communication-logs/{log_id}                 - Delete log
    GET    /site-communication/newsletter-distributions                    - List newsletters
    GET    /site-communication/newsletter-distributions/{newsletter_id}    - Get single newsletter
    POST   /site-communication/newsletter-distributions                    - Create newsletter
    PUT    /site-communication/newsletter-distributions/{newsletter_id}    - Update newsletter
    DELETE /site-communication/newsletter-distributions/{newsletter_id}    - Delete newsletter
    GET    /site-communication/site-query-threads                          - List query threads
    GET    /site-communication/site-query-threads/{query_id}               - Get single query thread
    POST   /site-communication/site-query-threads                          - Create query thread
    PUT    /site-communication/site-query-threads/{query_id}               - Update query thread
    DELETE /site-communication/site-query-threads/{query_id}               - Delete query thread
    GET    /site-communication/site-broadcast-alerts                       - List broadcast alerts
    GET    /site-communication/site-broadcast-alerts/{alert_id}            - Get single alert
    POST   /site-communication/site-broadcast-alerts                       - Create alert
    PUT    /site-communication/site-broadcast-alerts/{alert_id}            - Update alert
    DELETE /site-communication/site-broadcast-alerts/{alert_id}            - Delete alert
    GET    /site-communication/metrics                                     - Communication metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_communication import (
    AlertLevel,
    CommunicationChannel,
    CommunicationLog,
    CommunicationLogCreate,
    CommunicationLogListResponse,
    CommunicationLogUpdate,
    CommunicationPriority,
    DistributionStatus,
    NewsletterDistribution,
    NewsletterDistributionCreate,
    NewsletterDistributionListResponse,
    NewsletterDistributionUpdate,
    QueryStatus,
    SiteBroadcastAlert,
    SiteBroadcastAlertCreate,
    SiteBroadcastAlertListResponse,
    SiteBroadcastAlertUpdate,
    SiteCommunicationMetrics,
    SiteQueryThread,
    SiteQueryThreadCreate,
    SiteQueryThreadListResponse,
    SiteQueryThreadUpdate,
)
from app.services.site_communication_service import get_site_communication_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-communication",
    tags=["Site Communication"],
)


# ---------------------------------------------------------------------------
# Communication Logs
# ---------------------------------------------------------------------------


@router.get(
    "/communication-logs",
    response_model=CommunicationLogListResponse,
    summary="List communication logs",
    description="Retrieve communication logs with optional filtering by trial, channel, priority, and site.",
)
async def list_communication_logs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    communication_channel: Optional[CommunicationChannel] = Query(
        None, description="Filter by communication channel"
    ),
    communication_priority: Optional[CommunicationPriority] = Query(
        None, description="Filter by communication priority"
    ),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> CommunicationLogListResponse:
    svc = get_site_communication_service()
    items = svc.list_communication_logs(
        trial_id=trial_id,
        communication_channel=communication_channel,
        communication_priority=communication_priority,
        site_id=site_id,
    )
    return CommunicationLogListResponse(items=items, total=len(items))


@router.get(
    "/communication-logs/{log_id}",
    response_model=CommunicationLog,
    summary="Get a communication log",
)
async def get_communication_log(log_id: str) -> CommunicationLog:
    svc = get_site_communication_service()
    record = svc.get_communication_log(log_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Communication log '{log_id}' not found")
    return record


@router.post(
    "/communication-logs",
    response_model=CommunicationLog,
    status_code=201,
    summary="Create a communication log",
)
async def create_communication_log(payload: CommunicationLogCreate) -> CommunicationLog:
    svc = get_site_communication_service()
    return svc.create_communication_log(payload)


@router.put(
    "/communication-logs/{log_id}",
    response_model=CommunicationLog,
    summary="Update a communication log",
)
async def update_communication_log(
    log_id: str, payload: CommunicationLogUpdate
) -> CommunicationLog:
    svc = get_site_communication_service()
    updated = svc.update_communication_log(log_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Communication log '{log_id}' not found")
    return updated


@router.delete(
    "/communication-logs/{log_id}",
    status_code=204,
    summary="Delete a communication log",
)
async def delete_communication_log(log_id: str) -> None:
    svc = get_site_communication_service()
    deleted = svc.delete_communication_log(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Communication log '{log_id}' not found")


# ---------------------------------------------------------------------------
# Newsletter Distributions
# ---------------------------------------------------------------------------


@router.get(
    "/newsletter-distributions",
    response_model=NewsletterDistributionListResponse,
    summary="List newsletter distributions",
    description="Retrieve newsletter distributions with optional filtering by trial and status.",
)
async def list_newsletter_distributions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    distribution_status: Optional[DistributionStatus] = Query(
        None, description="Filter by distribution status"
    ),
) -> NewsletterDistributionListResponse:
    svc = get_site_communication_service()
    items = svc.list_newsletter_distributions(
        trial_id=trial_id, distribution_status=distribution_status
    )
    return NewsletterDistributionListResponse(items=items, total=len(items))


@router.get(
    "/newsletter-distributions/{newsletter_id}",
    response_model=NewsletterDistribution,
    summary="Get a newsletter distribution",
)
async def get_newsletter_distribution(newsletter_id: str) -> NewsletterDistribution:
    svc = get_site_communication_service()
    record = svc.get_newsletter_distribution(newsletter_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Newsletter distribution '{newsletter_id}' not found"
        )
    return record


@router.post(
    "/newsletter-distributions",
    response_model=NewsletterDistribution,
    status_code=201,
    summary="Create a newsletter distribution",
)
async def create_newsletter_distribution(
    payload: NewsletterDistributionCreate,
) -> NewsletterDistribution:
    svc = get_site_communication_service()
    return svc.create_newsletter_distribution(payload)


@router.put(
    "/newsletter-distributions/{newsletter_id}",
    response_model=NewsletterDistribution,
    summary="Update a newsletter distribution",
)
async def update_newsletter_distribution(
    newsletter_id: str, payload: NewsletterDistributionUpdate
) -> NewsletterDistribution:
    svc = get_site_communication_service()
    updated = svc.update_newsletter_distribution(newsletter_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Newsletter distribution '{newsletter_id}' not found"
        )
    return updated


@router.delete(
    "/newsletter-distributions/{newsletter_id}",
    status_code=204,
    summary="Delete a newsletter distribution",
)
async def delete_newsletter_distribution(newsletter_id: str) -> None:
    svc = get_site_communication_service()
    deleted = svc.delete_newsletter_distribution(newsletter_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Newsletter distribution '{newsletter_id}' not found"
        )


# ---------------------------------------------------------------------------
# Site Query Threads
# ---------------------------------------------------------------------------


@router.get(
    "/site-query-threads",
    response_model=SiteQueryThreadListResponse,
    summary="List site query threads",
    description="Retrieve site query threads with optional filtering by trial, status, and site.",
)
async def list_site_query_threads(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    query_status: Optional[QueryStatus] = Query(None, description="Filter by query status"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> SiteQueryThreadListResponse:
    svc = get_site_communication_service()
    items = svc.list_site_query_threads(
        trial_id=trial_id, query_status=query_status, site_id=site_id
    )
    return SiteQueryThreadListResponse(items=items, total=len(items))


@router.get(
    "/site-query-threads/{query_id}",
    response_model=SiteQueryThread,
    summary="Get a site query thread",
)
async def get_site_query_thread(query_id: str) -> SiteQueryThread:
    svc = get_site_communication_service()
    record = svc.get_site_query_thread(query_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Site query thread '{query_id}' not found"
        )
    return record


@router.post(
    "/site-query-threads",
    response_model=SiteQueryThread,
    status_code=201,
    summary="Create a site query thread",
)
async def create_site_query_thread(payload: SiteQueryThreadCreate) -> SiteQueryThread:
    svc = get_site_communication_service()
    return svc.create_site_query_thread(payload)


@router.put(
    "/site-query-threads/{query_id}",
    response_model=SiteQueryThread,
    summary="Update a site query thread",
)
async def update_site_query_thread(
    query_id: str, payload: SiteQueryThreadUpdate
) -> SiteQueryThread:
    svc = get_site_communication_service()
    updated = svc.update_site_query_thread(query_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Site query thread '{query_id}' not found"
        )
    return updated


@router.delete(
    "/site-query-threads/{query_id}",
    status_code=204,
    summary="Delete a site query thread",
)
async def delete_site_query_thread(query_id: str) -> None:
    svc = get_site_communication_service()
    deleted = svc.delete_site_query_thread(query_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Site query thread '{query_id}' not found"
        )


# ---------------------------------------------------------------------------
# Site Broadcast Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/site-broadcast-alerts",
    response_model=SiteBroadcastAlertListResponse,
    summary="List site broadcast alerts",
    description="Retrieve site broadcast alerts with optional filtering by trial and alert level.",
)
async def list_site_broadcast_alerts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    alert_level: Optional[AlertLevel] = Query(None, description="Filter by alert level"),
) -> SiteBroadcastAlertListResponse:
    svc = get_site_communication_service()
    items = svc.list_site_broadcast_alerts(trial_id=trial_id, alert_level=alert_level)
    return SiteBroadcastAlertListResponse(items=items, total=len(items))


@router.get(
    "/site-broadcast-alerts/{alert_id}",
    response_model=SiteBroadcastAlert,
    summary="Get a site broadcast alert",
)
async def get_site_broadcast_alert(alert_id: str) -> SiteBroadcastAlert:
    svc = get_site_communication_service()
    record = svc.get_site_broadcast_alert(alert_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Site broadcast alert '{alert_id}' not found"
        )
    return record


@router.post(
    "/site-broadcast-alerts",
    response_model=SiteBroadcastAlert,
    status_code=201,
    summary="Create a site broadcast alert",
)
async def create_site_broadcast_alert(
    payload: SiteBroadcastAlertCreate,
) -> SiteBroadcastAlert:
    svc = get_site_communication_service()
    return svc.create_site_broadcast_alert(payload)


@router.put(
    "/site-broadcast-alerts/{alert_id}",
    response_model=SiteBroadcastAlert,
    summary="Update a site broadcast alert",
)
async def update_site_broadcast_alert(
    alert_id: str, payload: SiteBroadcastAlertUpdate
) -> SiteBroadcastAlert:
    svc = get_site_communication_service()
    updated = svc.update_site_broadcast_alert(alert_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Site broadcast alert '{alert_id}' not found"
        )
    return updated


@router.delete(
    "/site-broadcast-alerts/{alert_id}",
    status_code=204,
    summary="Delete a site broadcast alert",
)
async def delete_site_broadcast_alert(alert_id: str) -> None:
    svc = get_site_communication_service()
    deleted = svc.delete_site_broadcast_alert(alert_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Site broadcast alert '{alert_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SiteCommunicationMetrics,
    summary="Get site communication metrics",
    description="Aggregated metrics across all site communication operations.",
)
async def get_metrics() -> SiteCommunicationMetrics:
    svc = get_site_communication_service()
    return svc.get_metrics()
