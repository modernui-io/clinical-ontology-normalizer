"""Operational Dashboard & SLA Management API endpoints (COO-5).

Provides a unified operational dashboard, SLA management, system health
monitoring, trial operations summaries, automated process tracking,
alert management, key metrics, compliance trending, and capacity assessment.

Endpoints:
    GET    /operational-dashboard/                                - Full dashboard
    GET    /operational-dashboard/stats                           - Service stats

    SLA Management:
    GET    /operational-dashboard/slas                             - List SLAs
    POST   /operational-dashboard/slas                             - Create SLA
    GET    /operational-dashboard/slas/{sla_id}                    - Get SLA
    PUT    /operational-dashboard/slas/{sla_id}                    - Update SLA
    DELETE /operational-dashboard/slas/{sla_id}                    - Delete SLA
    GET    /operational-dashboard/slas/{sla_id}/measurements       - SLA measurements
    POST   /operational-dashboard/slas/{sla_id}/measurements       - Record measurement
    GET    /operational-dashboard/slas/{sla_id}/trend              - SLA compliance trend
    GET    /operational-dashboard/slas/breaches                    - Breached SLAs

    System Health:
    GET    /operational-dashboard/health                           - All service health
    GET    /operational-dashboard/health/{service_name}            - Service health
    PUT    /operational-dashboard/health/{service_name}            - Update service status

    Trial Operations:
    GET    /operational-dashboard/trials                           - Trial summaries
    GET    /operational-dashboard/trials/{trial_id}                - Trial summary

    Automated Processes:
    GET    /operational-dashboard/processes                        - List processes
    POST   /operational-dashboard/processes                        - Create process
    GET    /operational-dashboard/processes/{process_id}            - Get process
    PUT    /operational-dashboard/processes/{process_id}            - Update process
    POST   /operational-dashboard/processes/{process_id}/trigger    - Trigger process
    DELETE /operational-dashboard/processes/{process_id}            - Delete process

    Alerts:
    GET    /operational-dashboard/alerts                           - List alerts
    POST   /operational-dashboard/alerts                           - Create alert
    GET    /operational-dashboard/alerts/{alert_id}                - Get alert
    POST   /operational-dashboard/alerts/{alert_id}/acknowledge    - Acknowledge alert
    DELETE /operational-dashboard/alerts/{alert_id}                - Delete alert

    Analytics:
    GET    /operational-dashboard/metrics                          - Key metrics
    GET    /operational-dashboard/capacity                         - Capacity assessment
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.operational_dashboard import (
    AlertCreateRequest,
    AlertSeverity,
    AutomatedProcess,
    CapacityAssessment,
    DashboardResponse,
    OperationalAlert,
    OperationalMetric,
    OperationalStatus,
    ProcessCreateRequest,
    ProcessListResponse,
    ProcessStatus,
    ProcessUpdateRequest,
    SLACategory,
    SLAComplianceTrend,
    SLACreateRequest,
    SLADefinition,
    SLAListResponse,
    SLAMeasurement,
    SLAMeasurementCreateRequest,
    SLAUpdateRequest,
    SystemHealthStatus,
    TrialOperationsSummary,
)
from app.services.operational_dashboard_service import (
    get_operational_dashboard_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/operational-dashboard",
    tags=["Operational Dashboard"],
)


# ---------------------------------------------------------------------------
# Full Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=DashboardResponse,
    summary="Full operational dashboard",
    description="Unified dashboard with SLA status, system health, trial operations, processes, alerts, and key metrics.",
)
async def get_dashboard() -> DashboardResponse:
    """Return the full operational dashboard snapshot."""
    svc = get_operational_dashboard_service()
    return svc.get_full_dashboard()


@router.get(
    "/stats",
    response_model=dict,
    summary="Service stats",
    description="Internal service statistics: counts of SLAs, measurements, trials, processes, and alerts.",
)
async def get_stats() -> dict:
    """Return service stats."""
    svc = get_operational_dashboard_service()
    return svc.get_stats()


# ---------------------------------------------------------------------------
# SLA Management
# ---------------------------------------------------------------------------


@router.get(
    "/slas",
    response_model=SLAListResponse,
    summary="List SLA definitions",
    description="List all SLA definitions, optionally filtered by category.",
)
async def list_slas(
    category: SLACategory | None = Query(None, description="Filter by SLA category"),
) -> SLAListResponse:
    """List SLA definitions."""
    svc = get_operational_dashboard_service()
    return svc.list_slas(category=category)


@router.post(
    "/slas",
    response_model=SLADefinition,
    status_code=201,
    summary="Create SLA definition",
    description="Create a new SLA definition with target value and measurement parameters.",
)
async def create_sla(body: SLACreateRequest) -> SLADefinition:
    """Create a new SLA definition."""
    svc = get_operational_dashboard_service()
    return svc.create_sla(body)


@router.get(
    "/slas/breaches",
    response_model=list[SLADefinition],
    summary="Breached SLAs",
    description="Return all SLAs currently in breached status.",
)
async def get_breached_slas() -> list[SLADefinition]:
    """Return breached SLAs."""
    svc = get_operational_dashboard_service()
    return svc.detect_breaches()


@router.get(
    "/slas/{sla_id}",
    response_model=SLADefinition,
    summary="Get SLA definition",
    description="Return a single SLA definition by ID.",
)
async def get_sla(sla_id: str) -> SLADefinition:
    """Return an SLA definition by ID."""
    svc = get_operational_dashboard_service()
    sla = svc.get_sla(sla_id)
    if not sla:
        raise HTTPException(status_code=404, detail=f"SLA not found: {sla_id}")
    return sla


@router.put(
    "/slas/{sla_id}",
    response_model=SLADefinition,
    summary="Update SLA definition",
    description="Update an existing SLA definition's parameters.",
)
async def update_sla(sla_id: str, body: SLAUpdateRequest) -> SLADefinition:
    """Update an SLA definition."""
    svc = get_operational_dashboard_service()
    sla = svc.update_sla(sla_id, body)
    if not sla:
        raise HTTPException(status_code=404, detail=f"SLA not found: {sla_id}")
    return sla


@router.delete(
    "/slas/{sla_id}",
    status_code=204,
    summary="Delete SLA definition",
    description="Delete an SLA definition and its associated measurements.",
)
async def delete_sla(sla_id: str) -> None:
    """Delete an SLA definition."""
    svc = get_operational_dashboard_service()
    deleted = svc.delete_sla(sla_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SLA not found: {sla_id}")


@router.get(
    "/slas/{sla_id}/measurements",
    response_model=list[SLAMeasurement],
    summary="SLA measurements",
    description="Return measurement history for an SLA, newest first.",
)
async def get_sla_measurements(
    sla_id: str,
    limit: int = Query(50, ge=1, le=500, description="Max measurements to return"),
) -> list[SLAMeasurement]:
    """Return measurements for an SLA."""
    svc = get_operational_dashboard_service()
    if not svc.get_sla(sla_id):
        raise HTTPException(status_code=404, detail=f"SLA not found: {sla_id}")
    return svc.get_measurements(sla_id, limit=limit)


@router.post(
    "/slas/{sla_id}/measurements",
    response_model=SLAMeasurement,
    status_code=201,
    summary="Record SLA measurement",
    description="Record a new measurement value for an SLA. Triggers breach detection.",
)
async def record_measurement(
    sla_id: str, body: SLAMeasurementCreateRequest
) -> SLAMeasurement:
    """Record an SLA measurement."""
    # Ensure the path parameter matches the body
    body.sla_id = sla_id
    svc = get_operational_dashboard_service()
    measurement = svc.record_measurement(body)
    if not measurement:
        raise HTTPException(status_code=404, detail=f"SLA not found: {sla_id}")
    return measurement


@router.get(
    "/slas/{sla_id}/trend",
    response_model=list[SLAComplianceTrend],
    summary="SLA compliance trend",
    description="Historical compliance trend for an SLA, grouped by daily periods.",
)
async def get_sla_trend(
    sla_id: str,
    periods: int = Query(7, ge=1, le=90, description="Number of days to include"),
) -> list[SLAComplianceTrend]:
    """Return compliance trend for an SLA."""
    svc = get_operational_dashboard_service()
    if not svc.get_sla(sla_id):
        raise HTTPException(status_code=404, detail=f"SLA not found: {sla_id}")
    return svc.get_sla_compliance_trend(sla_id, periods=periods)


# ---------------------------------------------------------------------------
# System Health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=list[SystemHealthStatus],
    summary="System health overview",
    description="Return health status for all monitored platform services.",
)
async def get_system_health() -> list[SystemHealthStatus]:
    """Return system health for all services."""
    svc = get_operational_dashboard_service()
    return svc.get_system_health()


@router.get(
    "/health/{service_name}",
    response_model=SystemHealthStatus,
    summary="Service health",
    description="Return health status for a specific platform service.",
)
async def get_service_health(service_name: str) -> SystemHealthStatus:
    """Return health for a specific service."""
    svc = get_operational_dashboard_service()
    health = svc.get_service_health(service_name)
    if not health:
        raise HTTPException(
            status_code=404, detail=f"Service not found: {service_name}"
        )
    return health


@router.put(
    "/health/{service_name}",
    response_model=SystemHealthStatus,
    summary="Update service status",
    description="Update the operational status of a specific platform service.",
)
async def update_service_health(
    service_name: str,
    status: OperationalStatus = Query(..., description="New operational status"),
) -> SystemHealthStatus:
    """Update a service's operational status."""
    svc = get_operational_dashboard_service()
    health = svc.update_service_health(service_name, status)
    if not health:
        raise HTTPException(
            status_code=404, detail=f"Service not found: {service_name}"
        )
    return health


# ---------------------------------------------------------------------------
# Trial Operations
# ---------------------------------------------------------------------------


@router.get(
    "/trials",
    response_model=list[TrialOperationsSummary],
    summary="Trial operations summaries",
    description="Return operational summaries for all active clinical trials.",
)
async def get_trial_summaries() -> list[TrialOperationsSummary]:
    """Return trial operations summaries."""
    svc = get_operational_dashboard_service()
    return svc.get_trial_summaries()


@router.get(
    "/trials/{trial_id}",
    response_model=TrialOperationsSummary,
    summary="Trial operations summary",
    description="Return operational summary for a specific clinical trial.",
)
async def get_trial_summary(trial_id: str) -> TrialOperationsSummary:
    """Return a trial operations summary."""
    svc = get_operational_dashboard_service()
    summary = svc.get_trial_summary(trial_id)
    if not summary:
        raise HTTPException(
            status_code=404, detail=f"Trial not found: {trial_id}"
        )
    return summary


# ---------------------------------------------------------------------------
# Automated Processes
# ---------------------------------------------------------------------------


@router.get(
    "/processes",
    response_model=ProcessListResponse,
    summary="List automated processes",
    description="List all automated processes, optionally filtered by status.",
)
async def list_processes(
    status: ProcessStatus | None = Query(None, description="Filter by process status"),
) -> ProcessListResponse:
    """List automated processes."""
    svc = get_operational_dashboard_service()
    return svc.list_processes(status=status)


@router.post(
    "/processes",
    response_model=AutomatedProcess,
    status_code=201,
    summary="Create automated process",
    description="Register a new automated process with optional cron schedule.",
)
async def create_process(body: ProcessCreateRequest) -> AutomatedProcess:
    """Create a new automated process."""
    svc = get_operational_dashboard_service()
    return svc.create_process(body)


@router.get(
    "/processes/{process_id}",
    response_model=AutomatedProcess,
    summary="Get automated process",
    description="Return details for a specific automated process.",
)
async def get_process(process_id: str) -> AutomatedProcess:
    """Return an automated process by ID."""
    svc = get_operational_dashboard_service()
    proc = svc.get_process(process_id)
    if not proc:
        raise HTTPException(
            status_code=404, detail=f"Process not found: {process_id}"
        )
    return proc


@router.put(
    "/processes/{process_id}",
    response_model=AutomatedProcess,
    summary="Update automated process",
    description="Update parameters of an existing automated process.",
)
async def update_process(
    process_id: str, body: ProcessUpdateRequest
) -> AutomatedProcess:
    """Update an automated process."""
    svc = get_operational_dashboard_service()
    proc = svc.update_process(process_id, body)
    if not proc:
        raise HTTPException(
            status_code=404, detail=f"Process not found: {process_id}"
        )
    return proc


@router.post(
    "/processes/{process_id}/trigger",
    response_model=AutomatedProcess,
    summary="Trigger process execution",
    description="Trigger immediate execution of an automated process.",
)
async def trigger_process(process_id: str) -> AutomatedProcess:
    """Trigger a process for immediate execution."""
    svc = get_operational_dashboard_service()
    proc = svc.trigger_process(process_id)
    if not proc:
        raise HTTPException(
            status_code=404, detail=f"Process not found: {process_id}"
        )
    return proc


@router.delete(
    "/processes/{process_id}",
    status_code=204,
    summary="Delete automated process",
    description="Delete an automated process registration.",
)
async def delete_process(process_id: str) -> None:
    """Delete an automated process."""
    svc = get_operational_dashboard_service()
    deleted = svc.delete_process(process_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Process not found: {process_id}"
        )


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=list[OperationalAlert],
    summary="List operational alerts",
    description="List alerts, optionally filtered by severity and/or acknowledgment status.",
)
async def list_alerts(
    severity: AlertSeverity | None = Query(None, description="Filter by severity"),
    acknowledged: bool | None = Query(None, description="Filter by acknowledgment"),
    limit: int = Query(50, ge=1, le=200, description="Max alerts to return"),
) -> list[OperationalAlert]:
    """List operational alerts."""
    svc = get_operational_dashboard_service()
    return svc.list_alerts(severity=severity, acknowledged=acknowledged, limit=limit)


@router.post(
    "/alerts",
    response_model=OperationalAlert,
    status_code=201,
    summary="Create operational alert",
    description="Create a new operational alert with specified severity.",
)
async def create_alert(body: AlertCreateRequest) -> OperationalAlert:
    """Create a new alert."""
    svc = get_operational_dashboard_service()
    return svc.create_alert(body)


@router.get(
    "/alerts/{alert_id}",
    response_model=OperationalAlert,
    summary="Get operational alert",
    description="Return a single operational alert by ID.",
)
async def get_alert(alert_id: str) -> OperationalAlert:
    """Return an alert by ID."""
    svc = get_operational_dashboard_service()
    alert = svc.get_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=404, detail=f"Alert not found: {alert_id}"
        )
    return alert


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=OperationalAlert,
    summary="Acknowledge alert",
    description="Mark an alert as acknowledged.",
)
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query("system", description="Who acknowledged the alert"),
) -> OperationalAlert:
    """Acknowledge an alert."""
    svc = get_operational_dashboard_service()
    alert = svc.acknowledge_alert(alert_id, acknowledged_by=acknowledged_by)
    if not alert:
        raise HTTPException(
            status_code=404, detail=f"Alert not found: {alert_id}"
        )
    return alert


@router.delete(
    "/alerts/{alert_id}",
    status_code=204,
    summary="Delete alert",
    description="Delete an operational alert.",
)
async def delete_alert(alert_id: str) -> None:
    """Delete an alert."""
    svc = get_operational_dashboard_service()
    deleted = svc.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Alert not found: {alert_id}"
        )


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=list[OperationalMetric],
    summary="Key operational metrics",
    description="High-level operational KPIs: cost per patient, time to match, enrollment velocity, conversion rate, site utilization.",
)
async def get_key_metrics() -> list[OperationalMetric]:
    """Return key operational metrics."""
    svc = get_operational_dashboard_service()
    return svc.get_key_metrics()


@router.get(
    "/capacity",
    response_model=CapacityAssessment,
    summary="Capacity assessment",
    description="Current operational capacity utilization across compute, memory, storage, and connections.",
)
async def get_capacity() -> CapacityAssessment:
    """Return capacity assessment."""
    svc = get_operational_dashboard_service()
    return svc.get_capacity_assessment()
