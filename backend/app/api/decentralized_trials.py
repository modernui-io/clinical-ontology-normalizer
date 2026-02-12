"""Decentralized Trial Operations (DCT-OPS) API endpoints.

Provides comprehensive DCT management: remote visit scheduling, wearable
device management, telemedicine session tracking, eSource data capture,
and decentralized trial operational metrics.

Endpoints:
    GET    /decentralized-trials/visits                           - List remote visits
    GET    /decentralized-trials/visits/{visit_id}                - Get single visit
    POST   /decentralized-trials/visits                           - Create remote visit
    PUT    /decentralized-trials/visits/{visit_id}                - Update remote visit
    DELETE /decentralized-trials/visits/{visit_id}                - Delete remote visit
    GET    /decentralized-trials/devices                          - List wearable devices
    GET    /decentralized-trials/devices/{device_id}              - Get single device
    POST   /decentralized-trials/devices                          - Create wearable device
    PUT    /decentralized-trials/devices/{device_id}              - Update wearable device
    DELETE /decentralized-trials/devices/{device_id}              - Delete wearable device
    GET    /decentralized-trials/sessions                         - List telemedicine sessions
    GET    /decentralized-trials/sessions/{session_id}            - Get single session
    POST   /decentralized-trials/sessions                         - Create telemedicine session
    PUT    /decentralized-trials/sessions/{session_id}            - Update telemedicine session
    DELETE /decentralized-trials/sessions/{session_id}            - Delete telemedicine session
    GET    /decentralized-trials/esource                          - List eSource captures
    GET    /decentralized-trials/esource/{esource_id}             - Get single eSource capture
    POST   /decentralized-trials/esource                          - Create eSource capture
    PUT    /decentralized-trials/esource/{esource_id}             - Update eSource capture
    DELETE /decentralized-trials/esource/{esource_id}             - Delete eSource capture
    GET    /decentralized-trials/metrics                          - DCT dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.decentralized_trials import (
    DataQuality,
    DecentralizedTrialMetrics,
    DeviceStatus,
    DeviceType,
    ESourceCapture,
    ESourceCaptureCreate,
    ESourceCaptureListResponse,
    ESourceCaptureUpdate,
    RemoteVisit,
    RemoteVisitCreate,
    RemoteVisitListResponse,
    RemoteVisitUpdate,
    SessionPlatform,
    TelemedicineSession,
    TelemedicineSessionCreate,
    TelemedicineSessionListResponse,
    TelemedicineSessionUpdate,
    VisitStatus,
    VisitType,
    WearableDevice,
    WearableDeviceCreate,
    WearableDeviceListResponse,
    WearableDeviceUpdate,
)
from app.services.decentralized_trials_service import get_decentralized_trials_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/decentralized-trials",
    tags=["Decentralized Trials"],
)


# ---------------------------------------------------------------------------
# Remote Visits
# ---------------------------------------------------------------------------


@router.get(
    "/visits",
    response_model=RemoteVisitListResponse,
    summary="List remote visits",
    description="Retrieve remote visits with optional filtering by trial, visit type, status, and subject.",
)
async def list_visits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    visit_type: Optional[VisitType] = Query(None, description="Filter by visit type"),
    status: Optional[VisitStatus] = Query(None, description="Filter by status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> RemoteVisitListResponse:
    svc = get_decentralized_trials_service()
    items = svc.list_visits(
        trial_id=trial_id, visit_type=visit_type, status=status, subject_id=subject_id
    )
    return RemoteVisitListResponse(items=items, total=len(items))


@router.get(
    "/visits/{visit_id}",
    response_model=RemoteVisit,
    summary="Get a remote visit",
)
async def get_visit(visit_id: str) -> RemoteVisit:
    svc = get_decentralized_trials_service()
    visit = svc.get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return visit


@router.post(
    "/visits",
    response_model=RemoteVisit,
    status_code=201,
    summary="Create a remote visit",
)
async def create_visit(payload: RemoteVisitCreate) -> RemoteVisit:
    svc = get_decentralized_trials_service()
    return svc.create_visit(payload)


@router.put(
    "/visits/{visit_id}",
    response_model=RemoteVisit,
    summary="Update a remote visit",
)
async def update_visit(visit_id: str, payload: RemoteVisitUpdate) -> RemoteVisit:
    svc = get_decentralized_trials_service()
    updated = svc.update_visit(visit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return updated


@router.delete(
    "/visits/{visit_id}",
    status_code=204,
    summary="Delete a remote visit",
)
async def delete_visit(visit_id: str) -> None:
    svc = get_decentralized_trials_service()
    deleted = svc.delete_visit(visit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")


# ---------------------------------------------------------------------------
# Wearable Devices
# ---------------------------------------------------------------------------


@router.get(
    "/devices",
    response_model=WearableDeviceListResponse,
    summary="List wearable devices",
    description="Retrieve wearable devices with optional filtering by trial, device type, status, and subject.",
)
async def list_devices(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    device_type: Optional[DeviceType] = Query(None, description="Filter by device type"),
    device_status: Optional[DeviceStatus] = Query(None, description="Filter by device status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> WearableDeviceListResponse:
    svc = get_decentralized_trials_service()
    items = svc.list_devices(
        trial_id=trial_id, device_type=device_type, device_status=device_status, subject_id=subject_id
    )
    return WearableDeviceListResponse(items=items, total=len(items))


@router.get(
    "/devices/{device_id}",
    response_model=WearableDevice,
    summary="Get a wearable device",
)
async def get_device(device_id: str) -> WearableDevice:
    svc = get_decentralized_trials_service()
    device = svc.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return device


@router.post(
    "/devices",
    response_model=WearableDevice,
    status_code=201,
    summary="Create a wearable device",
)
async def create_device(payload: WearableDeviceCreate) -> WearableDevice:
    svc = get_decentralized_trials_service()
    return svc.create_device(payload)


@router.put(
    "/devices/{device_id}",
    response_model=WearableDevice,
    summary="Update a wearable device",
)
async def update_device(device_id: str, payload: WearableDeviceUpdate) -> WearableDevice:
    svc = get_decentralized_trials_service()
    updated = svc.update_device(device_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return updated


@router.delete(
    "/devices/{device_id}",
    status_code=204,
    summary="Delete a wearable device",
)
async def delete_device(device_id: str) -> None:
    svc = get_decentralized_trials_service()
    deleted = svc.delete_device(device_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")


# ---------------------------------------------------------------------------
# Telemedicine Sessions
# ---------------------------------------------------------------------------


@router.get(
    "/sessions",
    response_model=TelemedicineSessionListResponse,
    summary="List telemedicine sessions",
    description="Retrieve telemedicine sessions with optional filtering by trial, platform, status, and subject.",
)
async def list_sessions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    platform: Optional[SessionPlatform] = Query(None, description="Filter by platform"),
    status: Optional[VisitStatus] = Query(None, description="Filter by status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> TelemedicineSessionListResponse:
    svc = get_decentralized_trials_service()
    items = svc.list_sessions(
        trial_id=trial_id, platform=platform, status=status, subject_id=subject_id
    )
    return TelemedicineSessionListResponse(items=items, total=len(items))


@router.get(
    "/sessions/{session_id}",
    response_model=TelemedicineSession,
    summary="Get a telemedicine session",
)
async def get_session(session_id: str) -> TelemedicineSession:
    svc = get_decentralized_trials_service()
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


@router.post(
    "/sessions",
    response_model=TelemedicineSession,
    status_code=201,
    summary="Create a telemedicine session",
)
async def create_session(payload: TelemedicineSessionCreate) -> TelemedicineSession:
    svc = get_decentralized_trials_service()
    return svc.create_session(payload)


@router.put(
    "/sessions/{session_id}",
    response_model=TelemedicineSession,
    summary="Update a telemedicine session",
)
async def update_session(session_id: str, payload: TelemedicineSessionUpdate) -> TelemedicineSession:
    svc = get_decentralized_trials_service()
    updated = svc.update_session(session_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return updated


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Delete a telemedicine session",
)
async def delete_session(session_id: str) -> None:
    svc = get_decentralized_trials_service()
    deleted = svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")


# ---------------------------------------------------------------------------
# eSource Captures
# ---------------------------------------------------------------------------


@router.get(
    "/esource",
    response_model=ESourceCaptureListResponse,
    summary="List eSource captures",
    description="Retrieve eSource captures with optional filtering by trial, subject, data type, and quality.",
)
async def list_esource(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    data_type: Optional[str] = Query(None, description="Filter by data type"),
    data_quality: Optional[DataQuality] = Query(None, description="Filter by data quality"),
) -> ESourceCaptureListResponse:
    svc = get_decentralized_trials_service()
    items = svc.list_esource(
        trial_id=trial_id, subject_id=subject_id, data_type=data_type, data_quality=data_quality
    )
    return ESourceCaptureListResponse(items=items, total=len(items))


@router.get(
    "/esource/{esource_id}",
    response_model=ESourceCapture,
    summary="Get an eSource capture",
)
async def get_esource(esource_id: str) -> ESourceCapture:
    svc = get_decentralized_trials_service()
    capture = svc.get_esource(esource_id)
    if capture is None:
        raise HTTPException(status_code=404, detail=f"eSource capture '{esource_id}' not found")
    return capture


@router.post(
    "/esource",
    response_model=ESourceCapture,
    status_code=201,
    summary="Create an eSource capture",
)
async def create_esource(payload: ESourceCaptureCreate) -> ESourceCapture:
    svc = get_decentralized_trials_service()
    return svc.create_esource(payload)


@router.put(
    "/esource/{esource_id}",
    response_model=ESourceCapture,
    summary="Update an eSource capture",
)
async def update_esource(esource_id: str, payload: ESourceCaptureUpdate) -> ESourceCapture:
    svc = get_decentralized_trials_service()
    updated = svc.update_esource(esource_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"eSource capture '{esource_id}' not found")
    return updated


@router.delete(
    "/esource/{esource_id}",
    status_code=204,
    summary="Delete an eSource capture",
)
async def delete_esource(esource_id: str) -> None:
    svc = get_decentralized_trials_service()
    deleted = svc.delete_esource(esource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"eSource capture '{esource_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DecentralizedTrialMetrics,
    summary="Get DCT dashboard metrics",
    description="Aggregated decentralized trial operational metrics across all entities.",
)
async def get_metrics() -> DecentralizedTrialMetrics:
    svc = get_decentralized_trials_service()
    return svc.get_metrics()
