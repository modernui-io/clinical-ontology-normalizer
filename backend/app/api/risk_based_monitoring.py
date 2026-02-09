"""Risk-Based Monitoring (RBM) & Central Monitoring API endpoints (CLINICAL-7).

Provides comprehensive RBM operations: KRI definitions & management, site risk
scoring with weighted KRI aggregation, KRI data point submission & trending,
monitoring plan lifecycle, finding management with CAPA linkage, central
monitoring alerts, auto-escalation, and RBM operational metrics.

Endpoints:
    GET    /risk-based-monitoring/kris                                 - List KRIs
    GET    /risk-based-monitoring/kris/{kri_id}                        - Get single KRI
    POST   /risk-based-monitoring/kris                                 - Create KRI
    PUT    /risk-based-monitoring/kris/{kri_id}                        - Update KRI
    DELETE /risk-based-monitoring/kris/{kri_id}                        - Delete KRI
    GET    /risk-based-monitoring/sites/risk-scores                    - All site risk scores
    GET    /risk-based-monitoring/sites/{site_id}/risk-profile         - Detailed risk profile
    POST   /risk-based-monitoring/sites/{site_id}/recalculate-risk     - Recalculate site risk
    GET    /risk-based-monitoring/sites/{site_id}/kri-trends           - KRI trends over time
    POST   /risk-based-monitoring/kri-data                             - Submit KRI data points
    GET    /risk-based-monitoring/alerts                               - List alerts
    GET    /risk-based-monitoring/alerts/{alert_id}                    - Get single alert
    POST   /risk-based-monitoring/alerts/{alert_id}/resolve            - Resolve alert
    GET    /risk-based-monitoring/plans                                - List monitoring plans
    GET    /risk-based-monitoring/plans/{plan_id}                      - Get single plan
    POST   /risk-based-monitoring/plans                                - Create monitoring plan
    PUT    /risk-based-monitoring/plans/{plan_id}                      - Update monitoring plan
    DELETE /risk-based-monitoring/plans/{plan_id}                      - Delete monitoring plan
    POST   /risk-based-monitoring/plans/{plan_id}/complete             - Complete visit with findings
    GET    /risk-based-monitoring/findings                             - List findings
    GET    /risk-based-monitoring/findings/{finding_id}                - Get single finding
    PUT    /risk-based-monitoring/findings/{finding_id}                - Update finding
    GET    /risk-based-monitoring/findings/overdue                     - Overdue findings
    GET    /risk-based-monitoring/metrics                              - RBM dashboard metrics
    GET    /risk-based-monitoring/monitoring-schedule                  - Recommended monitoring schedule
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.risk_based_monitoring import (
    AlertResolve,
    CentralMonitoringAlert,
    CentralMonitoringAlertListResponse,
    FindingCategory,
    FindingStatus,
    FindingUpdate,
    KRICategory,
    KRICreate,
    KRIDataPoint,
    KRIDataPointCreate,
    KRIDataPointListResponse,
    KRIListResponse,
    KRIUpdate,
    KeyRiskIndicator,
    MonitoringFinding,
    MonitoringFindingListResponse,
    MonitoringPlan,
    MonitoringPlanCreate,
    MonitoringPlanListResponse,
    MonitoringPlanStatus,
    MonitoringPlanUpdate,
    MonitoringScheduleRecommendation,
    MonitoringVisitComplete,
    MonitoringVisitType,
    RBMMetrics,
    RiskLevel,
    SiteRiskScore,
    SiteRiskScoreListResponse,
)
from app.services.risk_based_monitoring_service import get_rbm_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/risk-based-monitoring",
    tags=["Risk-Based Monitoring"],
)


# ---------------------------------------------------------------------------
# KRI Management
# ---------------------------------------------------------------------------


@router.get(
    "/kris",
    response_model=KRIListResponse,
    summary="List Key Risk Indicators",
    description="Retrieve KRIs with optional filtering by category and active status.",
)
async def list_kris(
    category: Optional[KRICategory] = Query(None, description="Filter by KRI category"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> KRIListResponse:
    svc = get_rbm_service()
    items = svc.list_kris(category=category, active=active)
    return KRIListResponse(items=items, total=len(items))


@router.get(
    "/kris/{kri_id}",
    response_model=KeyRiskIndicator,
    summary="Get a Key Risk Indicator",
)
async def get_kri(kri_id: str) -> KeyRiskIndicator:
    svc = get_rbm_service()
    kri = svc.get_kri(kri_id)
    if kri is None:
        raise HTTPException(status_code=404, detail=f"KRI '{kri_id}' not found")
    return kri


@router.post(
    "/kris",
    response_model=KeyRiskIndicator,
    status_code=201,
    summary="Create a Key Risk Indicator",
)
async def create_kri(payload: KRICreate) -> KeyRiskIndicator:
    svc = get_rbm_service()
    return svc.create_kri(payload)


@router.put(
    "/kris/{kri_id}",
    response_model=KeyRiskIndicator,
    summary="Update a Key Risk Indicator",
)
async def update_kri(kri_id: str, payload: KRIUpdate) -> KeyRiskIndicator:
    svc = get_rbm_service()
    updated = svc.update_kri(kri_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"KRI '{kri_id}' not found")
    return updated


@router.delete(
    "/kris/{kri_id}",
    status_code=204,
    summary="Delete a Key Risk Indicator",
)
async def delete_kri(kri_id: str) -> None:
    svc = get_rbm_service()
    deleted = svc.delete_kri(kri_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"KRI '{kri_id}' not found")


# ---------------------------------------------------------------------------
# Site Risk Scoring
# ---------------------------------------------------------------------------


@router.get(
    "/sites/risk-scores",
    response_model=SiteRiskScoreListResponse,
    summary="Get all site risk scores",
    description="Retrieve risk scores for all monitored sites, optionally filtered by risk level.",
)
async def list_site_risk_scores(
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
) -> SiteRiskScoreListResponse:
    svc = get_rbm_service()
    items = svc.list_site_risk_scores(risk_level=risk_level)
    return SiteRiskScoreListResponse(items=items, total=len(items))


@router.get(
    "/sites/{site_id}/risk-profile",
    response_model=SiteRiskScore,
    summary="Get detailed site risk profile",
    description="Retrieve a comprehensive risk profile for a specific site including per-KRI scores.",
)
async def get_site_risk_profile(site_id: str) -> SiteRiskScore:
    svc = get_rbm_service()
    profile = svc.get_site_risk_profile(site_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return profile


@router.post(
    "/sites/{site_id}/recalculate-risk",
    response_model=SiteRiskScore,
    summary="Recalculate site risk score",
    description="Recalculate the risk score for a site based on latest KRI data with weighted aggregation and auto-escalation.",
)
async def recalculate_site_risk(site_id: str) -> SiteRiskScore:
    svc = get_rbm_service()
    result = svc.recalculate_site_risk(site_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


@router.get(
    "/sites/{site_id}/kri-trends",
    response_model=KRIDataPointListResponse,
    summary="Get KRI trends for a site",
    description="Retrieve historical KRI data points for a site to visualize trends over time.",
)
async def get_kri_trends(
    site_id: str,
    kri_id: Optional[str] = Query(None, description="Filter by specific KRI"),
) -> KRIDataPointListResponse:
    svc = get_rbm_service()
    items = svc.get_kri_trends(site_id, kri_id=kri_id)
    return KRIDataPointListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# KRI Data Submission
# ---------------------------------------------------------------------------


@router.post(
    "/kri-data",
    response_model=KRIDataPoint,
    status_code=201,
    summary="Submit KRI data point",
    description="Submit a KRI measurement for a site. Automatically evaluates thresholds and triggers alerts.",
)
async def submit_kri_data(payload: KRIDataPointCreate) -> KRIDataPoint:
    svc = get_rbm_service()
    try:
        return svc.submit_kri_data(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Central Monitoring Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=CentralMonitoringAlertListResponse,
    summary="List central monitoring alerts",
    description="Retrieve central monitoring alerts with optional filtering by site and resolution status.",
)
async def list_alerts(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
) -> CentralMonitoringAlertListResponse:
    svc = get_rbm_service()
    items = svc.list_alerts(site_id=site_id, resolved=resolved)
    return CentralMonitoringAlertListResponse(items=items, total=len(items))


@router.get(
    "/alerts/{alert_id}",
    response_model=CentralMonitoringAlert,
    summary="Get a central monitoring alert",
)
async def get_alert(alert_id: str) -> CentralMonitoringAlert:
    svc = get_rbm_service()
    alert = svc.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return alert


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=CentralMonitoringAlert,
    summary="Resolve a central monitoring alert",
    description="Resolve an alert by specifying the action taken.",
)
async def resolve_alert(alert_id: str, payload: AlertResolve) -> CentralMonitoringAlert:
    svc = get_rbm_service()
    try:
        result = svc.resolve_alert(alert_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Monitoring Plans
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    response_model=MonitoringPlanListResponse,
    summary="List monitoring plans",
    description="Retrieve monitoring plans with optional filtering by site, trial, status, and visit type.",
)
async def list_monitoring_plans(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[MonitoringPlanStatus] = Query(None, description="Filter by status"),
    visit_type: Optional[MonitoringVisitType] = Query(None, description="Filter by visit type"),
) -> MonitoringPlanListResponse:
    svc = get_rbm_service()
    items = svc.list_monitoring_plans(
        site_id=site_id, trial_id=trial_id, status=status, visit_type=visit_type
    )
    return MonitoringPlanListResponse(items=items, total=len(items))


@router.get(
    "/plans/{plan_id}",
    response_model=MonitoringPlan,
    summary="Get a monitoring plan",
)
async def get_monitoring_plan(plan_id: str) -> MonitoringPlan:
    svc = get_rbm_service()
    plan = svc.get_monitoring_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Monitoring plan '{plan_id}' not found")
    return plan


@router.post(
    "/plans",
    response_model=MonitoringPlan,
    status_code=201,
    summary="Create a monitoring plan",
)
async def create_monitoring_plan(payload: MonitoringPlanCreate) -> MonitoringPlan:
    svc = get_rbm_service()
    return svc.create_monitoring_plan(payload)


@router.put(
    "/plans/{plan_id}",
    response_model=MonitoringPlan,
    summary="Update a monitoring plan",
)
async def update_monitoring_plan(plan_id: str, payload: MonitoringPlanUpdate) -> MonitoringPlan:
    svc = get_rbm_service()
    updated = svc.update_monitoring_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Monitoring plan '{plan_id}' not found")
    return updated


@router.delete(
    "/plans/{plan_id}",
    status_code=204,
    summary="Delete a monitoring plan",
)
async def delete_monitoring_plan(plan_id: str) -> None:
    svc = get_rbm_service()
    deleted = svc.delete_monitoring_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Monitoring plan '{plan_id}' not found")


@router.post(
    "/plans/{plan_id}/complete",
    response_model=MonitoringPlan,
    summary="Complete a monitoring visit",
    description="Mark a monitoring visit as completed and optionally attach findings.",
)
async def complete_monitoring_visit(
    plan_id: str, payload: MonitoringVisitComplete
) -> MonitoringPlan:
    svc = get_rbm_service()
    try:
        result = svc.complete_monitoring_visit(plan_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Monitoring plan '{plan_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Monitoring Findings
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=MonitoringFindingListResponse,
    summary="List monitoring findings",
    description="Retrieve monitoring findings with optional filtering by site, plan, category, and status.",
)
async def list_findings(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    category: Optional[FindingCategory] = Query(None, description="Filter by category"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status"),
) -> MonitoringFindingListResponse:
    svc = get_rbm_service()
    items = svc.list_findings(
        site_id=site_id, plan_id=plan_id, category=category, status=status
    )
    return MonitoringFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/overdue",
    response_model=MonitoringFindingListResponse,
    summary="Get overdue findings",
    description="Retrieve findings that are past their response due date and not yet resolved.",
)
async def get_overdue_findings() -> MonitoringFindingListResponse:
    svc = get_rbm_service()
    items = svc.get_overdue_findings()
    return MonitoringFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=MonitoringFinding,
    summary="Get a monitoring finding",
)
async def get_finding(finding_id: str) -> MonitoringFinding:
    svc = get_rbm_service()
    finding = svc.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return finding


@router.put(
    "/findings/{finding_id}",
    response_model=MonitoringFinding,
    summary="Update a monitoring finding",
    description="Update finding details including status, category, and resolution.",
)
async def update_finding(finding_id: str, payload: FindingUpdate) -> MonitoringFinding:
    svc = get_rbm_service()
    updated = svc.update_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Metrics & Schedule
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RBMMetrics,
    summary="Get RBM dashboard metrics",
    description="Aggregated risk-based monitoring metrics across all sites.",
)
async def get_metrics() -> RBMMetrics:
    svc = get_rbm_service()
    return svc.get_metrics()


@router.get(
    "/monitoring-schedule",
    response_model=list[MonitoringScheduleRecommendation],
    summary="Get recommended monitoring schedule",
    description="Generate a recommended monitoring schedule based on site risk levels. "
                "Critical sites get weekly visits, high risk monthly, medium/low quarterly.",
)
async def get_monitoring_schedule() -> list[MonitoringScheduleRecommendation]:
    svc = get_rbm_service()
    return svc.get_monitoring_schedule()
