"""Threat Intelligence & DLP API endpoints.

CISO-13: Threat intelligence feed management, IOC tracking, DLP policy
enforcement, violation monitoring, and security awareness training for the
clinical trial patient recruitment platform.

Endpoints:
    # Threat Indicators
    GET    /threat-intelligence/indicators                  - List indicators
    GET    /threat-intelligence/indicators/search           - Search by IOC value
    GET    /threat-intelligence/indicators/{id}             - Get indicator
    POST   /threat-intelligence/indicators                  - Create indicator
    PUT    /threat-intelligence/indicators/{id}             - Update indicator
    DELETE /threat-intelligence/indicators/{id}             - Delete indicator

    # Threat Feeds
    GET    /threat-intelligence/feeds                       - List feeds
    GET    /threat-intelligence/feeds/{id}                  - Get feed
    POST   /threat-intelligence/feeds                       - Create feed
    PUT    /threat-intelligence/feeds/{id}                  - Update feed
    DELETE /threat-intelligence/feeds/{id}                  - Delete feed

    # Threat Alerts
    GET    /threat-intelligence/alerts                      - List alerts
    GET    /threat-intelligence/alerts/{id}                 - Get alert
    POST   /threat-intelligence/alerts                      - Create alert
    POST   /threat-intelligence/alerts/{id}/acknowledge     - Acknowledge alert
    POST   /threat-intelligence/alerts/{id}/mitigate        - Mitigate alert

    # DLP Policies
    GET    /threat-intelligence/dlp/policies                - List DLP policies
    GET    /threat-intelligence/dlp/policies/{id}           - Get DLP policy
    POST   /threat-intelligence/dlp/policies                - Create DLP policy
    PUT    /threat-intelligence/dlp/policies/{id}           - Update DLP policy
    DELETE /threat-intelligence/dlp/policies/{id}           - Delete DLP policy
    POST   /threat-intelligence/dlp/policies/{id}/enable    - Enable policy
    POST   /threat-intelligence/dlp/policies/{id}/disable   - Disable policy

    # DLP Violations
    GET    /threat-intelligence/dlp/violations              - List violations
    GET    /threat-intelligence/dlp/violations/{id}         - Get violation
    POST   /threat-intelligence/dlp/violations/{id}/resolve - Resolve violation

    # Security Awareness Training
    GET    /threat-intelligence/training                    - List trainings
    GET    /threat-intelligence/training/{id}               - Get training
    POST   /threat-intelligence/training                    - Create training
    PUT    /threat-intelligence/training/{id}               - Update training

    # Metrics
    GET    /threat-intelligence/metrics/threats              - Threat metrics
    GET    /threat-intelligence/metrics/dlp                  - DLP metrics
    GET    /threat-intelligence/metrics/training             - Training compliance
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.threat_intelligence import (
    DLPAction,
    DLPChannel,
    DLPMetrics,
    DLPPolicy,
    DLPPolicyCreate,
    DLPPolicyListResponse,
    DLPPolicyType,
    DLPPolicyUpdate,
    DLPViolation,
    DLPViolationListResponse,
    DLPViolationResolve,
    IOCType,
    SecurityAwarenessTraining,
    ThreatAlert,
    ThreatAlertCreate,
    ThreatAlertListResponse,
    ThreatCategory,
    ThreatFeed,
    ThreatFeedCreate,
    ThreatFeedUpdate,
    ThreatIndicator,
    ThreatIndicatorCreate,
    ThreatIndicatorListResponse,
    ThreatIndicatorUpdate,
    ThreatMetrics,
    ThreatSeverity,
    ThreatStatus,
    TrainingComplianceRate,
    TrainingListResponse,
)
from app.services.threat_intelligence_service import (
    get_threat_intelligence_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/threat-intelligence",
    tags=["Threat Intelligence"],
)


# ---------------------------------------------------------------------------
# Threat Indicators
# ---------------------------------------------------------------------------


@router.get(
    "/indicators",
    response_model=ThreatIndicatorListResponse,
    summary="List threat indicators",
    description="Returns threat indicators with optional filtering by IOC type, category, severity, and status.",
)
async def list_indicators(
    ioc_type: Optional[IOCType] = Query(default=None, description="Filter by IOC type"),
    threat_category: Optional[ThreatCategory] = Query(default=None, description="Filter by threat category"),
    severity: Optional[ThreatSeverity] = Query(default=None, description="Filter by severity"),
    indicator_status: Optional[ThreatStatus] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> ThreatIndicatorListResponse:
    service = get_threat_intelligence_service()
    items, total = service.list_indicators(
        ioc_type=ioc_type,
        threat_category=threat_category,
        severity=severity,
        status=indicator_status,
        limit=limit,
        offset=offset,
    )
    return ThreatIndicatorListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/indicators/search",
    response_model=list[ThreatIndicator],
    summary="Search indicators by IOC value",
    description="Search for indicators matching a given IOC value (substring match).",
)
async def search_indicators(
    value: str = Query(..., min_length=1, description="IOC value to search"),
) -> list[ThreatIndicator]:
    service = get_threat_intelligence_service()
    return service.search_indicator_by_value(value)


@router.get(
    "/indicators/{indicator_id}",
    response_model=ThreatIndicator,
    summary="Get threat indicator",
    description="Retrieve a single threat indicator by ID.",
)
async def get_indicator(indicator_id: str) -> ThreatIndicator:
    service = get_threat_intelligence_service()
    indicator = service.get_indicator(indicator_id)
    if indicator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {indicator_id} not found",
        )
    return indicator


@router.post(
    "/indicators",
    response_model=ThreatIndicator,
    status_code=status.HTTP_201_CREATED,
    summary="Create threat indicator",
    description="Create a new indicator of compromise.",
)
async def create_indicator(body: ThreatIndicatorCreate) -> ThreatIndicator:
    service = get_threat_intelligence_service()
    return service.create_indicator(
        ioc_type=body.ioc_type,
        value=body.value,
        threat_category=body.threat_category,
        severity=body.severity,
        description=body.description,
        source=body.source,
        confidence_score=body.confidence_score,
        related_campaigns=body.related_campaigns,
        mitre_techniques=body.mitre_techniques,
    )


@router.put(
    "/indicators/{indicator_id}",
    response_model=ThreatIndicator,
    summary="Update threat indicator",
    description="Update an existing threat indicator.",
)
async def update_indicator(
    indicator_id: str,
    body: ThreatIndicatorUpdate,
) -> ThreatIndicator:
    service = get_threat_intelligence_service()
    updated = service.update_indicator(
        indicator_id,
        severity=body.severity,
        description=body.description,
        confidence_score=body.confidence_score,
        status=body.status,
        related_campaigns=body.related_campaigns,
        mitre_techniques=body.mitre_techniques,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {indicator_id} not found",
        )
    return updated


@router.delete(
    "/indicators/{indicator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete threat indicator",
    description="Delete a threat indicator.",
)
async def delete_indicator(indicator_id: str) -> None:
    service = get_threat_intelligence_service()
    if not service.delete_indicator(indicator_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {indicator_id} not found",
        )


# ---------------------------------------------------------------------------
# Threat Feeds
# ---------------------------------------------------------------------------


@router.get(
    "/feeds",
    response_model=list[ThreatFeed],
    summary="List threat feeds",
    description="List all configured threat intelligence feeds.",
)
async def list_feeds() -> list[ThreatFeed]:
    service = get_threat_intelligence_service()
    return service.list_feeds()


@router.get(
    "/feeds/{feed_id}",
    response_model=ThreatFeed,
    summary="Get threat feed",
    description="Retrieve a single threat feed by ID.",
)
async def get_feed(feed_id: str) -> ThreatFeed:
    service = get_threat_intelligence_service()
    feed = service.get_feed(feed_id)
    if feed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feed {feed_id} not found",
        )
    return feed


@router.post(
    "/feeds",
    response_model=ThreatFeed,
    status_code=status.HTTP_201_CREATED,
    summary="Create threat feed",
    description="Add a new threat intelligence feed.",
)
async def create_feed(body: ThreatFeedCreate) -> ThreatFeed:
    service = get_threat_intelligence_service()
    return service.create_feed(
        name=body.name,
        provider=body.provider,
        url=body.url,
        feed_type=body.feed_type,
        update_frequency_hours=body.update_frequency_hours,
        enabled=body.enabled,
    )


@router.put(
    "/feeds/{feed_id}",
    response_model=ThreatFeed,
    summary="Update threat feed",
    description="Update a threat feed configuration.",
)
async def update_feed(feed_id: str, body: ThreatFeedUpdate) -> ThreatFeed:
    service = get_threat_intelligence_service()
    updated = service.update_feed(
        feed_id,
        name=body.name,
        url=body.url,
        update_frequency_hours=body.update_frequency_hours,
        enabled=body.enabled,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feed {feed_id} not found",
        )
    return updated


@router.delete(
    "/feeds/{feed_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete threat feed",
    description="Delete a threat intelligence feed.",
)
async def delete_feed(feed_id: str) -> None:
    service = get_threat_intelligence_service()
    if not service.delete_feed(feed_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feed {feed_id} not found",
        )


# ---------------------------------------------------------------------------
# Threat Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=ThreatAlertListResponse,
    summary="List threat alerts",
    description="List threat alerts with optional filtering.",
)
async def list_alerts(
    severity: Optional[ThreatSeverity] = Query(default=None, description="Filter by severity"),
    category: Optional[ThreatCategory] = Query(default=None, description="Filter by category"),
    acknowledged: Optional[bool] = Query(default=None, description="Filter by acknowledged status"),
) -> ThreatAlertListResponse:
    service = get_threat_intelligence_service()
    items = service.list_alerts(
        severity=severity,
        category=category,
        acknowledged=acknowledged,
    )
    return ThreatAlertListResponse(items=items, total=len(items))


@router.get(
    "/alerts/{alert_id}",
    response_model=ThreatAlert,
    summary="Get threat alert",
    description="Retrieve a single threat alert by ID.",
)
async def get_alert(alert_id: str) -> ThreatAlert:
    service = get_threat_intelligence_service()
    alert = service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )
    return alert


@router.post(
    "/alerts",
    response_model=ThreatAlert,
    status_code=status.HTTP_201_CREATED,
    summary="Create threat alert",
    description="Create a new threat alert.",
)
async def create_alert(body: ThreatAlertCreate) -> ThreatAlert:
    service = get_threat_intelligence_service()
    return service.create_alert(
        title=body.title,
        description=body.description,
        severity=body.severity,
        category=body.category,
        indicators=body.indicators,
        affected_systems=body.affected_systems,
        detection_method=body.detection_method,
    )


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=ThreatAlert,
    summary="Acknowledge alert",
    description="Mark a threat alert as acknowledged.",
)
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., description="User acknowledging the alert"),
) -> ThreatAlert:
    service = get_threat_intelligence_service()
    result = service.acknowledge_alert(alert_id, acknowledged_by)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )
    return result


@router.post(
    "/alerts/{alert_id}/mitigate",
    response_model=ThreatAlert,
    summary="Mitigate alert",
    description="Mark a threat alert as mitigated.",
)
async def mitigate_alert(alert_id: str) -> ThreatAlert:
    service = get_threat_intelligence_service()
    result = service.mitigate_alert(alert_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )
    return result


# ---------------------------------------------------------------------------
# DLP Policies
# ---------------------------------------------------------------------------


@router.get(
    "/dlp/policies",
    response_model=DLPPolicyListResponse,
    summary="List DLP policies",
    description="List data loss prevention policies with optional filtering.",
)
async def list_dlp_policies(
    policy_type: Optional[DLPPolicyType] = Query(default=None, description="Filter by policy type"),
    enabled: Optional[bool] = Query(default=None, description="Filter by enabled status"),
) -> DLPPolicyListResponse:
    service = get_threat_intelligence_service()
    items = service.list_dlp_policies(policy_type=policy_type, enabled=enabled)
    return DLPPolicyListResponse(items=items, total=len(items))


@router.get(
    "/dlp/policies/{policy_id}",
    response_model=DLPPolicy,
    summary="Get DLP policy",
    description="Retrieve a single DLP policy by ID.",
)
async def get_dlp_policy(policy_id: str) -> DLPPolicy:
    service = get_threat_intelligence_service()
    policy = service.get_dlp_policy(policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLP policy {policy_id} not found",
        )
    return policy


@router.post(
    "/dlp/policies",
    response_model=DLPPolicy,
    status_code=status.HTTP_201_CREATED,
    summary="Create DLP policy",
    description="Create a new data loss prevention policy.",
)
async def create_dlp_policy(body: DLPPolicyCreate) -> DLPPolicy:
    service = get_threat_intelligence_service()
    return service.create_dlp_policy(
        name=body.name,
        policy_type=body.policy_type,
        description=body.description,
        channels=body.channels,
        action=body.action,
        enabled=body.enabled,
        patterns=body.patterns,
        sensitivity_threshold=body.sensitivity_threshold,
        exceptions=body.exceptions,
    )


@router.put(
    "/dlp/policies/{policy_id}",
    response_model=DLPPolicy,
    summary="Update DLP policy",
    description="Update an existing DLP policy.",
)
async def update_dlp_policy(
    policy_id: str,
    body: DLPPolicyUpdate,
) -> DLPPolicy:
    service = get_threat_intelligence_service()
    updated = service.update_dlp_policy(
        policy_id,
        name=body.name,
        description=body.description,
        channels=body.channels,
        action=body.action,
        enabled=body.enabled,
        patterns=body.patterns,
        sensitivity_threshold=body.sensitivity_threshold,
        exceptions=body.exceptions,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLP policy {policy_id} not found",
        )
    return updated


@router.delete(
    "/dlp/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete DLP policy",
    description="Delete a DLP policy.",
)
async def delete_dlp_policy(policy_id: str) -> None:
    service = get_threat_intelligence_service()
    if not service.delete_dlp_policy(policy_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLP policy {policy_id} not found",
        )


@router.post(
    "/dlp/policies/{policy_id}/enable",
    response_model=DLPPolicy,
    summary="Enable DLP policy",
    description="Enable a DLP policy.",
)
async def enable_dlp_policy(policy_id: str) -> DLPPolicy:
    service = get_threat_intelligence_service()
    result = service.enable_dlp_policy(policy_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLP policy {policy_id} not found",
        )
    return result


@router.post(
    "/dlp/policies/{policy_id}/disable",
    response_model=DLPPolicy,
    summary="Disable DLP policy",
    description="Disable a DLP policy.",
)
async def disable_dlp_policy(policy_id: str) -> DLPPolicy:
    service = get_threat_intelligence_service()
    result = service.disable_dlp_policy(policy_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLP policy {policy_id} not found",
        )
    return result


# ---------------------------------------------------------------------------
# DLP Violations
# ---------------------------------------------------------------------------


@router.get(
    "/dlp/violations",
    response_model=DLPViolationListResponse,
    summary="List DLP violations",
    description="List DLP violations with optional filtering.",
)
async def list_violations(
    policy_id: Optional[str] = Query(default=None, description="Filter by policy ID"),
    channel: Optional[DLPChannel] = Query(default=None, description="Filter by channel"),
    resolved: Optional[bool] = Query(default=None, description="Filter by resolved status"),
    limit: int = Query(default=100, ge=1, le=1000, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> DLPViolationListResponse:
    service = get_threat_intelligence_service()
    items, total = service.list_violations(
        policy_id=policy_id,
        channel=channel,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )
    return DLPViolationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/dlp/violations/{violation_id}",
    response_model=DLPViolation,
    summary="Get DLP violation",
    description="Retrieve a single DLP violation by ID.",
)
async def get_violation(violation_id: str) -> DLPViolation:
    service = get_threat_intelligence_service()
    violation = service.get_violation(violation_id)
    if violation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation {violation_id} not found",
        )
    return violation


@router.post(
    "/dlp/violations/{violation_id}/resolve",
    response_model=DLPViolation,
    summary="Resolve DLP violation",
    description="Mark a DLP violation as resolved with resolution notes.",
)
async def resolve_violation(
    violation_id: str,
    body: DLPViolationResolve,
) -> DLPViolation:
    service = get_threat_intelligence_service()
    result = service.resolve_violation(
        violation_id,
        resolution_notes=body.resolution_notes,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation {violation_id} not found",
        )
    return result


# ---------------------------------------------------------------------------
# Security Awareness Training
# ---------------------------------------------------------------------------


@router.get(
    "/training",
    response_model=TrainingListResponse,
    summary="List security trainings",
    description="List all security awareness training programs.",
)
async def list_trainings() -> TrainingListResponse:
    service = get_threat_intelligence_service()
    items = service.list_trainings()
    return TrainingListResponse(items=items, total=len(items))


@router.get(
    "/training/{training_id}",
    response_model=SecurityAwarenessTraining,
    summary="Get training",
    description="Retrieve a single training program by ID.",
)
async def get_training(training_id: str) -> SecurityAwarenessTraining:
    service = get_threat_intelligence_service()
    training = service.get_training(training_id)
    if training is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training {training_id} not found",
        )
    return training


@router.post(
    "/training",
    response_model=SecurityAwarenessTraining,
    status_code=status.HTTP_201_CREATED,
    summary="Create training",
    description="Create a new security awareness training program.",
)
async def create_training(
    name: str = Query(..., description="Training name"),
    training_type: str = Query(..., description="Training type"),
    description: str = Query(default="", description="Description"),
) -> SecurityAwarenessTraining:
    service = get_threat_intelligence_service()
    return service.create_training(
        name=name,
        training_type=training_type,
        description=description,
    )


@router.put(
    "/training/{training_id}",
    response_model=SecurityAwarenessTraining,
    summary="Update training",
    description="Update training progress metrics.",
)
async def update_training(
    training_id: str,
    total_completed: Optional[int] = Query(default=None, ge=0, description="Updated completed count"),
    pass_rate: Optional[float] = Query(default=None, ge=0.0, le=100.0, description="Updated pass rate"),
    phishing_simulation_click_rate: Optional[float] = Query(
        default=None, ge=0.0, le=100.0, description="Updated phishing click rate"
    ),
) -> SecurityAwarenessTraining:
    service = get_threat_intelligence_service()
    result = service.update_training(
        training_id,
        total_completed=total_completed,
        pass_rate=pass_rate,
        phishing_simulation_click_rate=phishing_simulation_click_rate,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training {training_id} not found",
        )
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/threats",
    response_model=ThreatMetrics,
    summary="Threat intelligence metrics",
    description="Aggregated threat intelligence metrics including indicators by category/severity, active threats, and MITRE coverage.",
)
async def get_threat_metrics() -> ThreatMetrics:
    service = get_threat_intelligence_service()
    return service.get_threat_metrics()


@router.get(
    "/metrics/dlp",
    response_model=DLPMetrics,
    summary="DLP metrics",
    description="Aggregated DLP metrics including violations by channel/policy type and action breakdown.",
)
async def get_dlp_metrics() -> DLPMetrics:
    service = get_threat_intelligence_service()
    return service.get_dlp_metrics()


@router.get(
    "/metrics/training",
    response_model=TrainingComplianceRate,
    summary="Training compliance metrics",
    description="Security awareness training compliance rates and statistics.",
)
async def get_training_compliance() -> TrainingComplianceRate:
    service = get_threat_intelligence_service()
    return service.get_training_compliance()
