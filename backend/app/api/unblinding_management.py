"""Unblinding Management API endpoints (CLINICAL-UBM).

Provides comprehensive unblinding management operations: request lifecycle
(create, approve, deny, execute, cancel), policy CRUD per trial, and
operational metrics/dashboard.

Endpoints:
    GET    /unblinding-management/requests                          - List unblinding requests
    GET    /unblinding-management/requests/{request_id}             - Get single request
    POST   /unblinding-management/requests                          - Create unblinding request
    PUT    /unblinding-management/requests/{request_id}             - Update request
    POST   /unblinding-management/requests/{request_id}/approve     - Approve request
    POST   /unblinding-management/requests/{request_id}/deny        - Deny request
    POST   /unblinding-management/requests/{request_id}/execute     - Execute unblinding
    POST   /unblinding-management/requests/{request_id}/cancel      - Cancel request
    GET    /unblinding-management/policies                          - List unblinding policies
    GET    /unblinding-management/policies/{policy_id}              - Get single policy
    POST   /unblinding-management/policies                          - Create policy
    PUT    /unblinding-management/policies/{policy_id}              - Update policy
    GET    /unblinding-management/metrics                           - Unblinding metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.unblinding_management import (
    ApprovalAuthority,
    UnblindingMetrics,
    UnblindingPolicy,
    UnblindingPolicyCreate,
    UnblindingPolicyListResponse,
    UnblindingPolicyUpdate,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestListResponse,
    UnblindingRequestUpdate,
    UnblindingStatus,
    UnblindingType,
)
from app.services.unblinding_management_service import (
    get_unblinding_management_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/unblinding-management",
    tags=["Unblinding Management"],
)


# ---------------------------------------------------------------------------
# Action payloads
# ---------------------------------------------------------------------------


class ApprovePayload(BaseModel):
    """Payload for approving an unblinding request."""

    approved_by: str = Field(..., description="Name of the approver")
    approval_authority: ApprovalAuthority = Field(
        ..., description="Authority level of the approver"
    )


class DenyPayload(BaseModel):
    """Payload for denying an unblinding request."""

    denied_by: str = Field(..., description="Name of the person denying the request")
    denial_reason: str = Field(..., description="Reason for denial")


class ExecutePayload(BaseModel):
    """Payload for executing an approved unblinding."""

    executed_by: str = Field(..., description="Name of the person executing the unblinding")
    treatment_assignment: str = Field(
        ..., description="The revealed treatment assignment"
    )


class CancelPayload(BaseModel):
    """Payload for cancelling an unblinding request."""

    cancelled_by: str = Field(..., description="Name of the person cancelling the request")
    cancellation_reason: str = Field(..., description="Reason for cancellation")


# ---------------------------------------------------------------------------
# Unblinding Requests
# ---------------------------------------------------------------------------


@router.get(
    "/requests",
    response_model=UnblindingRequestListResponse,
    summary="List unblinding requests",
    description="Retrieve unblinding requests with optional filtering by trial, site, status, and type.",
)
async def list_requests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[UnblindingStatus] = Query(None, description="Filter by status"),
    unblinding_type: Optional[UnblindingType] = Query(
        None, description="Filter by unblinding type"
    ),
) -> UnblindingRequestListResponse:
    svc = get_unblinding_management_service()
    items = svc.list_requests(
        trial_id=trial_id,
        site_id=site_id,
        status=status,
        unblinding_type=unblinding_type,
    )
    return UnblindingRequestListResponse(items=items, total=len(items))


@router.get(
    "/requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Get an unblinding request",
)
async def get_request(request_id: str) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    req = svc.get_request(request_id)
    if req is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return req


@router.post(
    "/requests",
    response_model=UnblindingRequest,
    status_code=201,
    summary="Create an unblinding request",
)
async def create_request(payload: UnblindingRequestCreate) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    return svc.create_request(payload)


@router.put(
    "/requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Update an unblinding request",
)
async def update_request(
    request_id: str, payload: UnblindingRequestUpdate
) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    updated = svc.update_request(request_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return updated


@router.post(
    "/requests/{request_id}/approve",
    response_model=UnblindingRequest,
    summary="Approve an unblinding request",
    description="Approve a pending unblinding request. Only requests in 'requested' status can be approved.",
)
async def approve_request(
    request_id: str, payload: ApprovePayload
) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    try:
        result = svc.approve_request(
            request_id,
            approved_by=payload.approved_by,
            approval_authority=payload.approval_authority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return result


@router.post(
    "/requests/{request_id}/deny",
    response_model=UnblindingRequest,
    summary="Deny an unblinding request",
    description="Deny a pending unblinding request. Only requests in 'requested' status can be denied.",
)
async def deny_request(request_id: str, payload: DenyPayload) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    try:
        result = svc.deny_request(
            request_id,
            denied_by=payload.denied_by,
            denial_reason=payload.denial_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return result


@router.post(
    "/requests/{request_id}/execute",
    response_model=UnblindingRequest,
    summary="Execute an approved unblinding",
    description="Execute an approved unblinding request, revealing the treatment assignment. "
    "Only requests in 'approved' status can be executed.",
)
async def execute_request(
    request_id: str, payload: ExecutePayload
) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    try:
        result = svc.execute_request(
            request_id,
            executed_by=payload.executed_by,
            treatment_assignment=payload.treatment_assignment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return result


@router.post(
    "/requests/{request_id}/cancel",
    response_model=UnblindingRequest,
    summary="Cancel an unblinding request",
    description="Cancel an unblinding request. Only requests in 'requested' or 'approved' status can be cancelled.",
)
async def cancel_request(
    request_id: str, payload: CancelPayload
) -> UnblindingRequest:
    svc = get_unblinding_management_service()
    try:
        result = svc.cancel_request(
            request_id,
            cancelled_by=payload.cancelled_by,
            cancellation_reason=payload.cancellation_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return result


# ---------------------------------------------------------------------------
# Unblinding Policies
# ---------------------------------------------------------------------------


@router.get(
    "/policies",
    response_model=UnblindingPolicyListResponse,
    summary="List unblinding policies",
    description="Retrieve unblinding policies with optional filtering by trial.",
)
async def list_policies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> UnblindingPolicyListResponse:
    svc = get_unblinding_management_service()
    items = svc.list_policies(trial_id=trial_id)
    return UnblindingPolicyListResponse(items=items, total=len(items))


@router.get(
    "/policies/{policy_id}",
    response_model=UnblindingPolicy,
    summary="Get an unblinding policy",
)
async def get_policy(policy_id: str) -> UnblindingPolicy:
    svc = get_unblinding_management_service()
    policy = svc.get_policy(policy_id)
    if policy is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding policy '{policy_id}' not found"
        )
    return policy


@router.post(
    "/policies",
    response_model=UnblindingPolicy,
    status_code=201,
    summary="Create an unblinding policy",
)
async def create_policy(payload: UnblindingPolicyCreate) -> UnblindingPolicy:
    svc = get_unblinding_management_service()
    return svc.create_policy(payload)


@router.put(
    "/policies/{policy_id}",
    response_model=UnblindingPolicy,
    summary="Update an unblinding policy",
)
async def update_policy(
    policy_id: str, payload: UnblindingPolicyUpdate
) -> UnblindingPolicy:
    svc = get_unblinding_management_service()
    updated = svc.update_policy(policy_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding policy '{policy_id}' not found"
        )
    return updated


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=UnblindingMetrics,
    summary="Get unblinding management metrics",
    description="Aggregated unblinding management metrics across all trials.",
)
async def get_metrics() -> UnblindingMetrics:
    svc = get_unblinding_management_service()
    return svc.get_metrics()
