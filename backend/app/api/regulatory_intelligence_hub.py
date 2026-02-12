"""Regulatory Intelligence Hub API endpoints (REG-INTEL).

Provides comprehensive regulatory intelligence operations: landscape monitoring,
guideline tracking, authority communication records, impact assessments,
and compliance alert management with intelligence metrics.

Endpoints:
    GET    /regulatory-intelligence-hub/landscape-monitors                         - List landscape monitors
    GET    /regulatory-intelligence-hub/landscape-monitors/{monitor_id}            - Get single monitor
    POST   /regulatory-intelligence-hub/landscape-monitors                         - Create monitor
    PUT    /regulatory-intelligence-hub/landscape-monitors/{monitor_id}            - Update monitor
    DELETE /regulatory-intelligence-hub/landscape-monitors/{monitor_id}            - Delete monitor
    GET    /regulatory-intelligence-hub/guideline-trackers                         - List guideline trackers
    GET    /regulatory-intelligence-hub/guideline-trackers/{tracker_id}            - Get single tracker
    POST   /regulatory-intelligence-hub/guideline-trackers                         - Create tracker
    PUT    /regulatory-intelligence-hub/guideline-trackers/{tracker_id}            - Update tracker
    DELETE /regulatory-intelligence-hub/guideline-trackers/{tracker_id}            - Delete tracker
    GET    /regulatory-intelligence-hub/authority-communications                   - List communications
    GET    /regulatory-intelligence-hub/authority-communications/{id}              - Get single communication
    POST   /regulatory-intelligence-hub/authority-communications                   - Create communication
    PUT    /regulatory-intelligence-hub/authority-communications/{id}              - Update communication
    DELETE /regulatory-intelligence-hub/authority-communications/{id}              - Delete communication
    GET    /regulatory-intelligence-hub/impact-assessments                         - List assessments
    GET    /regulatory-intelligence-hub/impact-assessments/{id}                    - Get single assessment
    POST   /regulatory-intelligence-hub/impact-assessments                         - Create assessment
    PUT    /regulatory-intelligence-hub/impact-assessments/{id}                    - Update assessment
    DELETE /regulatory-intelligence-hub/impact-assessments/{id}                    - Delete assessment
    GET    /regulatory-intelligence-hub/compliance-alerts                          - List alerts
    GET    /regulatory-intelligence-hub/compliance-alerts/{id}                     - Get single alert
    POST   /regulatory-intelligence-hub/compliance-alerts                          - Create alert
    PUT    /regulatory-intelligence-hub/compliance-alerts/{id}                     - Update alert
    DELETE /regulatory-intelligence-hub/compliance-alerts/{id}                     - Delete alert
    GET    /regulatory-intelligence-hub/metrics                                    - Intelligence metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.regulatory_intelligence_hub import (
    AlertSeverity,
    AuthorityCommunication,
    AuthorityCommunicationCreate,
    AuthorityCommunicationListResponse,
    AuthorityCommunicationUpdate,
    CommunicationType,
    ComplianceAlert,
    ComplianceAlertCreate,
    ComplianceAlertListResponse,
    ComplianceAlertUpdate,
    GuidelineTracker,
    GuidelineTrackerCreate,
    GuidelineTrackerListResponse,
    GuidelineTrackerUpdate,
    ImpactAssessment,
    ImpactAssessmentCreate,
    ImpactAssessmentListResponse,
    ImpactAssessmentUpdate,
    ImpactLevel,
    IntelligenceType,
    LandscapeMonitor,
    LandscapeMonitorCreate,
    LandscapeMonitorListResponse,
    LandscapeMonitorUpdate,
    RegionScope,
    RegulatoryIntelligenceMetrics,
)
from app.services.regulatory_intelligence_hub_service import (
    get_regulatory_intelligence_hub_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/regulatory-intelligence-hub",
    tags=["Regulatory Intelligence Hub"],
)


# ---------------------------------------------------------------------------
# Landscape Monitors
# ---------------------------------------------------------------------------


@router.get(
    "/landscape-monitors",
    response_model=LandscapeMonitorListResponse,
    summary="List landscape monitors",
    description="Retrieve landscape monitors with optional filtering by trial, intelligence type, region, and impact level.",
)
async def list_landscape_monitors(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    intelligence_type: Optional[IntelligenceType] = Query(None, description="Filter by intelligence type"),
    region: Optional[RegionScope] = Query(None, description="Filter by region"),
    impact_level: Optional[ImpactLevel] = Query(None, description="Filter by impact level"),
) -> LandscapeMonitorListResponse:
    svc = get_regulatory_intelligence_hub_service()
    items = svc.list_landscape_monitors(
        trial_id=trial_id,
        intelligence_type=intelligence_type,
        region=region,
        impact_level=impact_level,
    )
    return LandscapeMonitorListResponse(items=items, total=len(items))


@router.get(
    "/landscape-monitors/{monitor_id}",
    response_model=LandscapeMonitor,
    summary="Get a landscape monitor",
)
async def get_landscape_monitor(monitor_id: str) -> LandscapeMonitor:
    svc = get_regulatory_intelligence_hub_service()
    monitor = svc.get_landscape_monitor(monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail=f"Landscape monitor '{monitor_id}' not found")
    return monitor


@router.post(
    "/landscape-monitors",
    response_model=LandscapeMonitor,
    status_code=201,
    summary="Create a landscape monitor",
)
async def create_landscape_monitor(payload: LandscapeMonitorCreate) -> LandscapeMonitor:
    svc = get_regulatory_intelligence_hub_service()
    return svc.create_landscape_monitor(payload)


@router.put(
    "/landscape-monitors/{monitor_id}",
    response_model=LandscapeMonitor,
    summary="Update a landscape monitor",
)
async def update_landscape_monitor(
    monitor_id: str, payload: LandscapeMonitorUpdate
) -> LandscapeMonitor:
    svc = get_regulatory_intelligence_hub_service()
    updated = svc.update_landscape_monitor(monitor_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Landscape monitor '{monitor_id}' not found")
    return updated


@router.delete(
    "/landscape-monitors/{monitor_id}",
    status_code=204,
    summary="Delete a landscape monitor",
)
async def delete_landscape_monitor(monitor_id: str) -> None:
    svc = get_regulatory_intelligence_hub_service()
    deleted = svc.delete_landscape_monitor(monitor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Landscape monitor '{monitor_id}' not found")


# ---------------------------------------------------------------------------
# Guideline Trackers
# ---------------------------------------------------------------------------


@router.get(
    "/guideline-trackers",
    response_model=GuidelineTrackerListResponse,
    summary="List guideline trackers",
    description="Retrieve guideline trackers with optional filtering by trial, region, and compliance gap status.",
)
async def list_guideline_trackers(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    region: Optional[RegionScope] = Query(None, description="Filter by region"),
    compliance_gap_identified: Optional[bool] = Query(None, description="Filter by compliance gap status"),
) -> GuidelineTrackerListResponse:
    svc = get_regulatory_intelligence_hub_service()
    items = svc.list_guideline_trackers(
        trial_id=trial_id, region=region, compliance_gap_identified=compliance_gap_identified
    )
    return GuidelineTrackerListResponse(items=items, total=len(items))


@router.get(
    "/guideline-trackers/{tracker_id}",
    response_model=GuidelineTracker,
    summary="Get a guideline tracker",
)
async def get_guideline_tracker(tracker_id: str) -> GuidelineTracker:
    svc = get_regulatory_intelligence_hub_service()
    tracker = svc.get_guideline_tracker(tracker_id)
    if tracker is None:
        raise HTTPException(
            status_code=404, detail=f"Guideline tracker '{tracker_id}' not found"
        )
    return tracker


@router.post(
    "/guideline-trackers",
    response_model=GuidelineTracker,
    status_code=201,
    summary="Create a guideline tracker",
)
async def create_guideline_tracker(payload: GuidelineTrackerCreate) -> GuidelineTracker:
    svc = get_regulatory_intelligence_hub_service()
    return svc.create_guideline_tracker(payload)


@router.put(
    "/guideline-trackers/{tracker_id}",
    response_model=GuidelineTracker,
    summary="Update a guideline tracker",
)
async def update_guideline_tracker(
    tracker_id: str, payload: GuidelineTrackerUpdate
) -> GuidelineTracker:
    svc = get_regulatory_intelligence_hub_service()
    updated = svc.update_guideline_tracker(tracker_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Guideline tracker '{tracker_id}' not found"
        )
    return updated


@router.delete(
    "/guideline-trackers/{tracker_id}",
    status_code=204,
    summary="Delete a guideline tracker",
)
async def delete_guideline_tracker(tracker_id: str) -> None:
    svc = get_regulatory_intelligence_hub_service()
    deleted = svc.delete_guideline_tracker(tracker_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Guideline tracker '{tracker_id}' not found"
        )


# ---------------------------------------------------------------------------
# Authority Communications
# ---------------------------------------------------------------------------


@router.get(
    "/authority-communications",
    response_model=AuthorityCommunicationListResponse,
    summary="List authority communications",
    description="Retrieve authority communications with optional filtering by trial, communication type, and region.",
)
async def list_authority_communications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    communication_type: Optional[CommunicationType] = Query(None, description="Filter by communication type"),
    region: Optional[RegionScope] = Query(None, description="Filter by region"),
) -> AuthorityCommunicationListResponse:
    svc = get_regulatory_intelligence_hub_service()
    items = svc.list_authority_communications(
        trial_id=trial_id, communication_type=communication_type, region=region
    )
    return AuthorityCommunicationListResponse(items=items, total=len(items))


@router.get(
    "/authority-communications/{communication_id}",
    response_model=AuthorityCommunication,
    summary="Get an authority communication",
)
async def get_authority_communication(communication_id: str) -> AuthorityCommunication:
    svc = get_regulatory_intelligence_hub_service()
    comm = svc.get_authority_communication(communication_id)
    if comm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Authority communication '{communication_id}' not found",
        )
    return comm


@router.post(
    "/authority-communications",
    response_model=AuthorityCommunication,
    status_code=201,
    summary="Create an authority communication",
)
async def create_authority_communication(
    payload: AuthorityCommunicationCreate,
) -> AuthorityCommunication:
    svc = get_regulatory_intelligence_hub_service()
    return svc.create_authority_communication(payload)


@router.put(
    "/authority-communications/{communication_id}",
    response_model=AuthorityCommunication,
    summary="Update an authority communication",
)
async def update_authority_communication(
    communication_id: str, payload: AuthorityCommunicationUpdate
) -> AuthorityCommunication:
    svc = get_regulatory_intelligence_hub_service()
    updated = svc.update_authority_communication(communication_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Authority communication '{communication_id}' not found",
        )
    return updated


@router.delete(
    "/authority-communications/{communication_id}",
    status_code=204,
    summary="Delete an authority communication",
)
async def delete_authority_communication(communication_id: str) -> None:
    svc = get_regulatory_intelligence_hub_service()
    deleted = svc.delete_authority_communication(communication_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Authority communication '{communication_id}' not found",
        )


# ---------------------------------------------------------------------------
# Impact Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/impact-assessments",
    response_model=ImpactAssessmentListResponse,
    summary="List impact assessments",
    description="Retrieve impact assessments with optional filtering by trial and impact level.",
)
async def list_impact_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    impact_level: Optional[ImpactLevel] = Query(None, description="Filter by impact level"),
) -> ImpactAssessmentListResponse:
    svc = get_regulatory_intelligence_hub_service()
    items = svc.list_impact_assessments(trial_id=trial_id, impact_level=impact_level)
    return ImpactAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/impact-assessments/{assessment_id}",
    response_model=ImpactAssessment,
    summary="Get an impact assessment",
)
async def get_impact_assessment(assessment_id: str) -> ImpactAssessment:
    svc = get_regulatory_intelligence_hub_service()
    assessment = svc.get_impact_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Impact assessment '{assessment_id}' not found",
        )
    return assessment


@router.post(
    "/impact-assessments",
    response_model=ImpactAssessment,
    status_code=201,
    summary="Create an impact assessment",
)
async def create_impact_assessment(payload: ImpactAssessmentCreate) -> ImpactAssessment:
    svc = get_regulatory_intelligence_hub_service()
    return svc.create_impact_assessment(payload)


@router.put(
    "/impact-assessments/{assessment_id}",
    response_model=ImpactAssessment,
    summary="Update an impact assessment",
)
async def update_impact_assessment(
    assessment_id: str, payload: ImpactAssessmentUpdate
) -> ImpactAssessment:
    svc = get_regulatory_intelligence_hub_service()
    updated = svc.update_impact_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Impact assessment '{assessment_id}' not found",
        )
    return updated


@router.delete(
    "/impact-assessments/{assessment_id}",
    status_code=204,
    summary="Delete an impact assessment",
)
async def delete_impact_assessment(assessment_id: str) -> None:
    svc = get_regulatory_intelligence_hub_service()
    deleted = svc.delete_impact_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Impact assessment '{assessment_id}' not found",
        )


# ---------------------------------------------------------------------------
# Compliance Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/compliance-alerts",
    response_model=ComplianceAlertListResponse,
    summary="List compliance alerts",
    description="Retrieve compliance alerts with optional filtering by trial, severity, region, and resolved status.",
)
async def list_compliance_alerts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    region: Optional[RegionScope] = Query(None, description="Filter by region"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
) -> ComplianceAlertListResponse:
    svc = get_regulatory_intelligence_hub_service()
    items = svc.list_compliance_alerts(
        trial_id=trial_id, severity=severity, region=region, resolved=resolved
    )
    return ComplianceAlertListResponse(items=items, total=len(items))


@router.get(
    "/compliance-alerts/{alert_id}",
    response_model=ComplianceAlert,
    summary="Get a compliance alert",
)
async def get_compliance_alert(alert_id: str) -> ComplianceAlert:
    svc = get_regulatory_intelligence_hub_service()
    alert = svc.get_compliance_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=404, detail=f"Compliance alert '{alert_id}' not found"
        )
    return alert


@router.post(
    "/compliance-alerts",
    response_model=ComplianceAlert,
    status_code=201,
    summary="Create a compliance alert",
)
async def create_compliance_alert(payload: ComplianceAlertCreate) -> ComplianceAlert:
    svc = get_regulatory_intelligence_hub_service()
    return svc.create_compliance_alert(payload)


@router.put(
    "/compliance-alerts/{alert_id}",
    response_model=ComplianceAlert,
    summary="Update a compliance alert",
)
async def update_compliance_alert(
    alert_id: str, payload: ComplianceAlertUpdate
) -> ComplianceAlert:
    svc = get_regulatory_intelligence_hub_service()
    updated = svc.update_compliance_alert(alert_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Compliance alert '{alert_id}' not found"
        )
    return updated


@router.delete(
    "/compliance-alerts/{alert_id}",
    status_code=204,
    summary="Delete a compliance alert",
)
async def delete_compliance_alert(alert_id: str) -> None:
    svc = get_regulatory_intelligence_hub_service()
    deleted = svc.delete_compliance_alert(alert_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Compliance alert '{alert_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RegulatoryIntelligenceMetrics,
    summary="Get regulatory intelligence metrics",
    description="Aggregated metrics across all regulatory intelligence operations.",
)
async def get_metrics() -> RegulatoryIntelligenceMetrics:
    svc = get_regulatory_intelligence_hub_service()
    return svc.get_metrics()
