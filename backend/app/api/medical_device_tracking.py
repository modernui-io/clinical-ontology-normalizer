"""Medical Device Tracking API endpoints (MDT-TRK).

Provides comprehensive medical device tracking operations: device registrations,
device deployment records, maintenance logs, device incident reports, and device
tracking metrics.

Endpoints:
    GET    /medical-device-tracking/device-registrations                        - List device registrations
    GET    /medical-device-tracking/device-registrations/{registration_id}      - Get single registration
    POST   /medical-device-tracking/device-registrations                        - Create registration
    PUT    /medical-device-tracking/device-registrations/{registration_id}      - Update registration
    DELETE /medical-device-tracking/device-registrations/{registration_id}      - Delete registration
    GET    /medical-device-tracking/device-deployments                          - List device deployments
    GET    /medical-device-tracking/device-deployments/{deployment_id}          - Get single deployment
    POST   /medical-device-tracking/device-deployments                          - Create deployment
    PUT    /medical-device-tracking/device-deployments/{deployment_id}          - Update deployment
    DELETE /medical-device-tracking/device-deployments/{deployment_id}          - Delete deployment
    GET    /medical-device-tracking/maintenance-logs                            - List maintenance logs
    GET    /medical-device-tracking/maintenance-logs/{maintenance_id}           - Get single log
    POST   /medical-device-tracking/maintenance-logs                            - Create log
    PUT    /medical-device-tracking/maintenance-logs/{maintenance_id}           - Update log
    DELETE /medical-device-tracking/maintenance-logs/{maintenance_id}           - Delete log
    GET    /medical-device-tracking/device-incidents                            - List incident reports
    GET    /medical-device-tracking/device-incidents/{incident_id}              - Get single incident
    POST   /medical-device-tracking/device-incidents                            - Create incident
    PUT    /medical-device-tracking/device-incidents/{incident_id}              - Update incident
    DELETE /medical-device-tracking/device-incidents/{incident_id}              - Delete incident
    GET    /medical-device-tracking/metrics                                     - Device tracking metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_device_tracking import (
    DeploymentStatus,
    DeviceClassification,
    DeviceDeployment,
    DeviceDeploymentCreate,
    DeviceDeploymentListResponse,
    DeviceDeploymentUpdate,
    DeviceIncidentReport,
    DeviceIncidentReportCreate,
    DeviceIncidentReportListResponse,
    DeviceIncidentReportUpdate,
    DeviceRegistration,
    DeviceRegistrationCreate,
    DeviceRegistrationListResponse,
    DeviceRegistrationUpdate,
    IncidentSeverity,
    MaintenanceLog,
    MaintenanceLogCreate,
    MaintenanceLogListResponse,
    MaintenanceLogUpdate,
    MaintenanceResult,
    MaintenanceType,
    MedicalDeviceTrackingMetrics,
)
from app.services.medical_device_tracking_service import get_medical_device_tracking_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-device-tracking",
    tags=["Medical Device Tracking"],
)


# ---------------------------------------------------------------------------
# Device Registrations
# ---------------------------------------------------------------------------


@router.get(
    "/device-registrations",
    response_model=DeviceRegistrationListResponse,
    summary="List device registrations",
    description="Retrieve device registrations with optional filtering by trial and device classification.",
)
async def list_device_registrations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    device_classification: Optional[DeviceClassification] = Query(None, description="Filter by device classification"),
) -> DeviceRegistrationListResponse:
    svc = get_medical_device_tracking_service()
    items = svc.list_device_registrations(
        trial_id=trial_id, device_classification=device_classification
    )
    return DeviceRegistrationListResponse(items=items, total=len(items))


@router.get(
    "/device-registrations/{registration_id}",
    response_model=DeviceRegistration,
    summary="Get a device registration",
)
async def get_device_registration(registration_id: str) -> DeviceRegistration:
    svc = get_medical_device_tracking_service()
    record = svc.get_device_registration(registration_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Device registration '{registration_id}' not found")
    return record


@router.post(
    "/device-registrations",
    response_model=DeviceRegistration,
    status_code=201,
    summary="Create a device registration",
)
async def create_device_registration(payload: DeviceRegistrationCreate) -> DeviceRegistration:
    svc = get_medical_device_tracking_service()
    return svc.create_device_registration(payload)


@router.put(
    "/device-registrations/{registration_id}",
    response_model=DeviceRegistration,
    summary="Update a device registration",
)
async def update_device_registration(
    registration_id: str, payload: DeviceRegistrationUpdate
) -> DeviceRegistration:
    svc = get_medical_device_tracking_service()
    updated = svc.update_device_registration(registration_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Device registration '{registration_id}' not found")
    return updated


@router.delete(
    "/device-registrations/{registration_id}",
    status_code=204,
    summary="Delete a device registration",
)
async def delete_device_registration(registration_id: str) -> None:
    svc = get_medical_device_tracking_service()
    deleted = svc.delete_device_registration(registration_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Device registration '{registration_id}' not found")


# ---------------------------------------------------------------------------
# Device Deployments
# ---------------------------------------------------------------------------


@router.get(
    "/device-deployments",
    response_model=DeviceDeploymentListResponse,
    summary="List device deployments",
    description="Retrieve device deployments with optional filtering by trial, status, and site.",
)
async def list_device_deployments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    deployment_status: Optional[DeploymentStatus] = Query(None, description="Filter by deployment status"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> DeviceDeploymentListResponse:
    svc = get_medical_device_tracking_service()
    items = svc.list_device_deployments(
        trial_id=trial_id, deployment_status=deployment_status, site_id=site_id
    )
    return DeviceDeploymentListResponse(items=items, total=len(items))


@router.get(
    "/device-deployments/{deployment_id}",
    response_model=DeviceDeployment,
    summary="Get a device deployment",
)
async def get_device_deployment(deployment_id: str) -> DeviceDeployment:
    svc = get_medical_device_tracking_service()
    record = svc.get_device_deployment(deployment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Device deployment '{deployment_id}' not found")
    return record


@router.post(
    "/device-deployments",
    response_model=DeviceDeployment,
    status_code=201,
    summary="Create a device deployment",
)
async def create_device_deployment(payload: DeviceDeploymentCreate) -> DeviceDeployment:
    svc = get_medical_device_tracking_service()
    return svc.create_device_deployment(payload)


@router.put(
    "/device-deployments/{deployment_id}",
    response_model=DeviceDeployment,
    summary="Update a device deployment",
)
async def update_device_deployment(
    deployment_id: str, payload: DeviceDeploymentUpdate
) -> DeviceDeployment:
    svc = get_medical_device_tracking_service()
    updated = svc.update_device_deployment(deployment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Device deployment '{deployment_id}' not found")
    return updated


@router.delete(
    "/device-deployments/{deployment_id}",
    status_code=204,
    summary="Delete a device deployment",
)
async def delete_device_deployment(deployment_id: str) -> None:
    svc = get_medical_device_tracking_service()
    deleted = svc.delete_device_deployment(deployment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Device deployment '{deployment_id}' not found")


# ---------------------------------------------------------------------------
# Maintenance Logs
# ---------------------------------------------------------------------------


@router.get(
    "/maintenance-logs",
    response_model=MaintenanceLogListResponse,
    summary="List maintenance logs",
    description="Retrieve maintenance logs with optional filtering by trial, type, and result.",
)
async def list_maintenance_logs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    maintenance_type: Optional[MaintenanceType] = Query(None, description="Filter by maintenance type"),
    maintenance_result: Optional[MaintenanceResult] = Query(None, description="Filter by maintenance result"),
) -> MaintenanceLogListResponse:
    svc = get_medical_device_tracking_service()
    items = svc.list_maintenance_logs(
        trial_id=trial_id, maintenance_type=maintenance_type, maintenance_result=maintenance_result
    )
    return MaintenanceLogListResponse(items=items, total=len(items))


@router.get(
    "/maintenance-logs/{maintenance_id}",
    response_model=MaintenanceLog,
    summary="Get a maintenance log",
)
async def get_maintenance_log(maintenance_id: str) -> MaintenanceLog:
    svc = get_medical_device_tracking_service()
    record = svc.get_maintenance_log(maintenance_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Maintenance log '{maintenance_id}' not found")
    return record


@router.post(
    "/maintenance-logs",
    response_model=MaintenanceLog,
    status_code=201,
    summary="Create a maintenance log",
)
async def create_maintenance_log(payload: MaintenanceLogCreate) -> MaintenanceLog:
    svc = get_medical_device_tracking_service()
    return svc.create_maintenance_log(payload)


@router.put(
    "/maintenance-logs/{maintenance_id}",
    response_model=MaintenanceLog,
    summary="Update a maintenance log",
)
async def update_maintenance_log(
    maintenance_id: str, payload: MaintenanceLogUpdate
) -> MaintenanceLog:
    svc = get_medical_device_tracking_service()
    updated = svc.update_maintenance_log(maintenance_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Maintenance log '{maintenance_id}' not found")
    return updated


@router.delete(
    "/maintenance-logs/{maintenance_id}",
    status_code=204,
    summary="Delete a maintenance log",
)
async def delete_maintenance_log(maintenance_id: str) -> None:
    svc = get_medical_device_tracking_service()
    deleted = svc.delete_maintenance_log(maintenance_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Maintenance log '{maintenance_id}' not found")


# ---------------------------------------------------------------------------
# Device Incident Reports
# ---------------------------------------------------------------------------


@router.get(
    "/device-incidents",
    response_model=DeviceIncidentReportListResponse,
    summary="List device incident reports",
    description="Retrieve device incident reports with optional filtering by trial, severity, and site.",
)
async def list_device_incidents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    incident_severity: Optional[IncidentSeverity] = Query(None, description="Filter by incident severity"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> DeviceIncidentReportListResponse:
    svc = get_medical_device_tracking_service()
    items = svc.list_device_incident_reports(
        trial_id=trial_id, incident_severity=incident_severity, site_id=site_id
    )
    return DeviceIncidentReportListResponse(items=items, total=len(items))


@router.get(
    "/device-incidents/{incident_id}",
    response_model=DeviceIncidentReport,
    summary="Get a device incident report",
)
async def get_device_incident(incident_id: str) -> DeviceIncidentReport:
    svc = get_medical_device_tracking_service()
    record = svc.get_device_incident_report(incident_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Device incident report '{incident_id}' not found")
    return record


@router.post(
    "/device-incidents",
    response_model=DeviceIncidentReport,
    status_code=201,
    summary="Create a device incident report",
)
async def create_device_incident(payload: DeviceIncidentReportCreate) -> DeviceIncidentReport:
    svc = get_medical_device_tracking_service()
    return svc.create_device_incident_report(payload)


@router.put(
    "/device-incidents/{incident_id}",
    response_model=DeviceIncidentReport,
    summary="Update a device incident report",
)
async def update_device_incident(
    incident_id: str, payload: DeviceIncidentReportUpdate
) -> DeviceIncidentReport:
    svc = get_medical_device_tracking_service()
    updated = svc.update_device_incident_report(incident_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Device incident report '{incident_id}' not found")
    return updated


@router.delete(
    "/device-incidents/{incident_id}",
    status_code=204,
    summary="Delete a device incident report",
)
async def delete_device_incident(incident_id: str) -> None:
    svc = get_medical_device_tracking_service()
    deleted = svc.delete_device_incident_report(incident_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Device incident report '{incident_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MedicalDeviceTrackingMetrics,
    summary="Get medical device tracking metrics",
    description="Aggregated metrics across all medical device tracking operations.",
)
async def get_metrics() -> MedicalDeviceTrackingMetrics:
    svc = get_medical_device_tracking_service()
    return svc.get_metrics()
