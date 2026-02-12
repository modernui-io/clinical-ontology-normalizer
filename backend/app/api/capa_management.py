"""CAPA (Corrective and Preventive Action) Management API endpoints.

Provides comprehensive CAPA lifecycle management: record creation and tracking,
root cause investigation, action plan submission, implementation oversight,
effectiveness verification, action item management, and CAPA metrics.

Endpoints:
    GET    /capa-management/                          - List CAPAs
    GET    /capa-management/{capa_id}                 - Get single CAPA
    POST   /capa-management/                          - Create CAPA
    PUT    /capa-management/{capa_id}                 - Update CAPA
    DELETE /capa-management/{capa_id}                 - Delete CAPA
    POST   /capa-management/{capa_id}/investigate     - Start investigation
    POST   /capa-management/{capa_id}/action-plan     - Submit action plan
    POST   /capa-management/{capa_id}/implement       - Begin implementation
    POST   /capa-management/{capa_id}/verify          - Verify effectiveness
    POST   /capa-management/{capa_id}/close           - Close CAPA
    GET    /capa-management/{capa_id}/actions          - List actions for CAPA
    POST   /capa-management/{capa_id}/actions          - Create action
    PUT    /capa-management/actions/{action_id}        - Update action
    GET    /capa-management/metrics                    - Get CAPA metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.capa_management import (
    CapaAction,
    CapaActionCreate,
    CapaActionListResponse,
    CapaActionUpdate,
    CapaCreate,
    CapaListResponse,
    CapaMetrics,
    CapaPriority,
    CapaRecord,
    CapaSource,
    CapaStatus,
    CapaUpdate,
)
from app.services.capa_management_service import get_capa_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/capa-management",
    tags=["CAPA Management"],
)


# ---------------------------------------------------------------------------
# Metrics (registered first to avoid route conflicts with {capa_id})
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CapaMetrics,
    summary="Get CAPA metrics",
    description="Aggregated CAPA management metrics across all sites and trials.",
)
async def get_metrics() -> CapaMetrics:
    svc = get_capa_management_service()
    return svc.get_metrics()


# ---------------------------------------------------------------------------
# CAPA CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=CapaListResponse,
    summary="List CAPAs",
    description="Retrieve CAPAs with optional filtering by trial, site, status, priority, and source.",
)
async def list_capas(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[CapaStatus] = Query(None, description="Filter by status"),
    priority: Optional[CapaPriority] = Query(None, description="Filter by priority"),
    source: Optional[CapaSource] = Query(None, description="Filter by source"),
) -> CapaListResponse:
    svc = get_capa_management_service()
    items = svc.list_capas(
        trial_id=trial_id,
        site_id=site_id,
        status=status,
        priority=priority,
        source=source,
    )
    return CapaListResponse(items=items, total=len(items))


@router.get(
    "/{capa_id}",
    response_model=CapaRecord,
    summary="Get a CAPA record",
)
async def get_capa(capa_id: str) -> CapaRecord:
    svc = get_capa_management_service()
    capa = svc.get_capa(capa_id)
    if capa is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return capa


@router.post(
    "/",
    response_model=CapaRecord,
    status_code=201,
    summary="Create a CAPA record",
)
async def create_capa(payload: CapaCreate) -> CapaRecord:
    svc = get_capa_management_service()
    return svc.create_capa(payload)


@router.put(
    "/{capa_id}",
    response_model=CapaRecord,
    summary="Update a CAPA record",
)
async def update_capa(capa_id: str, payload: CapaUpdate) -> CapaRecord:
    svc = get_capa_management_service()
    updated = svc.update_capa(capa_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return updated


@router.delete(
    "/{capa_id}",
    status_code=204,
    summary="Delete a CAPA record",
)
async def delete_capa(capa_id: str) -> None:
    svc = get_capa_management_service()
    deleted = svc.delete_capa(capa_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")


# ---------------------------------------------------------------------------
# Status Transitions
# ---------------------------------------------------------------------------


@router.post(
    "/{capa_id}/investigate",
    response_model=CapaRecord,
    summary="Start CAPA investigation",
    description="Transition CAPA from 'open' to 'investigation' status.",
)
async def start_investigation(capa_id: str) -> CapaRecord:
    svc = get_capa_management_service()
    try:
        result = svc.start_investigation(capa_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return result


@router.post(
    "/{capa_id}/action-plan",
    response_model=CapaRecord,
    summary="Submit CAPA action plan",
    description="Transition CAPA from 'investigation' to 'action_plan' status.",
)
async def submit_action_plan(capa_id: str) -> CapaRecord:
    svc = get_capa_management_service()
    try:
        result = svc.submit_action_plan(capa_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return result


@router.post(
    "/{capa_id}/implement",
    response_model=CapaRecord,
    summary="Begin CAPA implementation",
    description="Transition CAPA from 'action_plan' to 'implementation' status.",
)
async def begin_implementation(capa_id: str) -> CapaRecord:
    svc = get_capa_management_service()
    try:
        result = svc.begin_implementation(capa_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return result


@router.post(
    "/{capa_id}/verify",
    response_model=CapaRecord,
    summary="Verify CAPA effectiveness",
    description="Transition CAPA from 'implementation' to 'verification' status.",
)
async def verify_effectiveness(capa_id: str) -> CapaRecord:
    svc = get_capa_management_service()
    try:
        result = svc.verify_effectiveness(capa_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return result


@router.post(
    "/{capa_id}/close",
    response_model=CapaRecord,
    summary="Close CAPA",
    description="Transition CAPA from 'verification' to 'closed' status. Sets effectiveness_verified to True.",
)
async def close_capa_record(capa_id: str) -> CapaRecord:
    svc = get_capa_management_service()
    try:
        result = svc.close_capa(capa_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return result


# ---------------------------------------------------------------------------
# CAPA Actions
# ---------------------------------------------------------------------------


@router.get(
    "/{capa_id}/actions",
    response_model=CapaActionListResponse,
    summary="List actions for a CAPA",
    description="Retrieve all action items associated with a CAPA record.",
)
async def list_actions(capa_id: str) -> CapaActionListResponse:
    svc = get_capa_management_service()
    capa = svc.get_capa(capa_id)
    if capa is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    items = svc.list_actions(capa_id)
    return CapaActionListResponse(items=items, total=len(items))


@router.post(
    "/{capa_id}/actions",
    response_model=CapaAction,
    status_code=201,
    summary="Create a CAPA action",
    description="Create a new action item for a CAPA record.",
)
async def create_action(capa_id: str, payload: CapaActionCreate) -> CapaAction:
    svc = get_capa_management_service()
    action = svc.create_action(capa_id, payload)
    if action is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return action


@router.put(
    "/actions/{action_id}",
    response_model=CapaAction,
    summary="Update a CAPA action",
    description="Update an existing CAPA action item.",
)
async def update_action(action_id: str, payload: CapaActionUpdate) -> CapaAction:
    svc = get_capa_management_service()
    updated = svc.update_action(action_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")
    return updated
