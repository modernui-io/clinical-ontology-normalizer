"""Change Control and Configuration Management API endpoints (VP-Quality-4).

Provides endpoints for formal change request lifecycle management,
approval workflows, configuration baselines, and drift detection.

Endpoints:
    POST   /api/v1/quality/changes              - Create change request
    GET    /api/v1/quality/changes               - List with filters
    GET    /api/v1/quality/changes/metrics        - Change metrics
    GET    /api/v1/quality/changes/{id}           - Detail
    PUT    /api/v1/quality/changes/{id}           - Update (status transitions)
    POST   /api/v1/quality/changes/{id}/approve   - Approve change
    POST   /api/v1/quality/changes/{id}/reject    - Reject change
    POST   /api/v1/quality/config/baseline        - Capture configuration baseline
    GET    /api/v1/quality/config/baselines        - List baselines
    GET    /api/v1/quality/config/drift            - Detect configuration drift
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.change_control import (
    ApprovalRequest,
    BaselineCaptureRequest,
    BaselineListResponse,
    ChangeMetrics,
    ChangeRequestCreate,
    ChangeRequestListResponse,
    ChangeRequestResponse,
    ChangeRequestUpdate,
    ChangeStatus,
    ChangeType,
    ConfigurationBaseline,
    DriftReport,
    RejectionRequest,
    RiskLevel,
)
from app.services.change_control_service import get_change_control_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quality", tags=["Change Control & Configuration Management"])


# ============================================================================
# Helper functions
# ============================================================================


def _change_to_response(change) -> ChangeRequestResponse:
    """Convert a ChangeRecord to a ChangeRequestResponse."""
    return ChangeRequestResponse(
        id=change.id,
        title=change.title,
        description=change.description,
        change_type=change.change_type,
        risk_level=change.risk_level,
        requester=change.requester,
        assigned_to=change.assigned_to,
        status=change.status,
        impact_assessment=change.impact_assessment,
        rollback_plan=change.rollback_plan,
        testing_requirements=change.testing_requirements,
        approval_chain=change.approval_chain,
        required_approvals=change.required_approvals,
        current_approvals=change.current_approvals,
        scheduled_date=change.scheduled_date,
        created_at=change.created_at,
        updated_at=change.updated_at,
        deployed_at=change.deployed_at,
        closed_at=change.closed_at,
        rolled_back_at=change.rolled_back_at,
    )


# ============================================================================
# Change Request Endpoints
# ============================================================================


@router.get(
    "/changes/metrics",
    response_model=ChangeMetrics,
    summary="Get change metrics",
    description="Get aggregated change control metrics including counts by risk level, status, and deployment stats.",
)
async def get_change_metrics() -> ChangeMetrics:
    """Get change control dashboard metrics."""
    service = get_change_control_service()
    return service.get_metrics()


@router.get(
    "/changes",
    response_model=ChangeRequestListResponse,
    summary="List change requests",
    description="List change requests with optional filtering by status, risk level, type, and requester.",
)
async def list_changes(
    change_status: ChangeStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    risk_level: RiskLevel | None = Query(
        default=None, description="Filter by risk level"
    ),
    change_type: ChangeType | None = Query(
        default=None, alias="type", description="Filter by change type"
    ),
    requester: str | None = Query(
        default=None, description="Filter by requester"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> ChangeRequestListResponse:
    """List change requests with optional filters."""
    service = get_change_control_service()
    changes, total = service.list_change_requests(
        status=change_status,
        risk_level=risk_level,
        change_type=change_type,
        requester=requester,
        limit=limit,
        offset=offset,
    )
    return ChangeRequestListResponse(
        changes=[_change_to_response(c) for c in changes],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/changes/{change_id}",
    response_model=ChangeRequestResponse,
    summary="Get change request detail",
    description="Get full details of a specific change request.",
)
async def get_change(change_id: str) -> ChangeRequestResponse:
    """Get a specific change request by ID."""
    service = get_change_control_service()
    change = service.get_change_request(change_id)
    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {change_id}",
        )
    return _change_to_response(change)


@router.post(
    "/changes",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a change request",
    description="Create a new formal change request with risk assessment.",
)
async def create_change(request: ChangeRequestCreate) -> ChangeRequestResponse:
    """Create a new change request."""
    service = get_change_control_service()
    change = service.create_change_request(
        title=request.title,
        description=request.description,
        change_type=request.change_type,
        risk_level=request.risk_level,
        requester=request.requester,
        assigned_to=request.assigned_to,
        impact_assessment=request.impact_assessment,
        rollback_plan=request.rollback_plan,
        testing_requirements=request.testing_requirements,
        scheduled_date=request.scheduled_date,
    )
    logger.info("Change request created via API: %s", change.id)
    return _change_to_response(change)


@router.put(
    "/changes/{change_id}",
    response_model=ChangeRequestResponse,
    summary="Update a change request",
    description="Update change request fields including status transitions.",
)
async def update_change(
    change_id: str, request: ChangeRequestUpdate
) -> ChangeRequestResponse:
    """Update an existing change request."""
    service = get_change_control_service()
    try:
        change = service.update_change_request(
            change_id=change_id,
            title=request.title,
            description=request.description,
            status=request.status,
            risk_level=request.risk_level,
            assigned_to=request.assigned_to,
            impact_assessment=request.impact_assessment,
            rollback_plan=request.rollback_plan,
            testing_requirements=request.testing_requirements,
            scheduled_date=request.scheduled_date,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return _change_to_response(change)


@router.post(
    "/changes/{change_id}/approve",
    response_model=ChangeRequestResponse,
    summary="Approve a change request",
    description="Add an approval to a change request. Auto-transitions to APPROVED when all required approvals are received.",
)
async def approve_change(
    change_id: str, request: ApprovalRequest
) -> ChangeRequestResponse:
    """Approve a change request."""
    service = get_change_control_service()
    try:
        change = service.approve_change(
            change_id=change_id,
            approver=request.approver,
            role=request.role,
            comment=request.comment,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return _change_to_response(change)


@router.post(
    "/changes/{change_id}/reject",
    response_model=ChangeRequestResponse,
    summary="Reject a change request",
    description="Reject a change request with a reason.",
)
async def reject_change(
    change_id: str, request: RejectionRequest
) -> ChangeRequestResponse:
    """Reject a change request."""
    service = get_change_control_service()
    try:
        change = service.reject_change(
            change_id=change_id,
            approver=request.approver,
            role=request.role,
            reason=request.reason,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return _change_to_response(change)


# ============================================================================
# Configuration Management Endpoints
# ============================================================================


@router.post(
    "/config/baseline",
    response_model=ConfigurationBaseline,
    status_code=status.HTTP_201_CREATED,
    summary="Capture configuration baseline",
    description="Capture a snapshot of the current configuration as a baseline.",
)
async def capture_baseline(
    request: BaselineCaptureRequest,
) -> ConfigurationBaseline:
    """Capture a configuration baseline."""
    service = get_change_control_service()
    baseline = service.capture_baseline(
        name=request.name,
        description=request.description,
        captured_by=request.captured_by,
        environment=request.environment,
    )
    logger.info("Configuration baseline captured via API: %s", baseline.id)
    return baseline


@router.get(
    "/config/baselines",
    response_model=BaselineListResponse,
    summary="List configuration baselines",
    description="List all configuration baselines.",
)
async def list_baselines() -> BaselineListResponse:
    """List all configuration baselines."""
    service = get_change_control_service()
    baselines = service.list_baselines()
    return BaselineListResponse(
        baselines=baselines,
        total=len(baselines),
    )


@router.get(
    "/config/drift",
    response_model=DriftReport,
    summary="Detect configuration drift",
    description="Compare current configuration against a baseline to detect drift.",
)
async def detect_drift(
    baseline_id: str | None = Query(
        default=None,
        description="Baseline ID to compare against. Uses most recent if not specified.",
    ),
) -> DriftReport:
    """Detect configuration drift from a baseline."""
    service = get_change_control_service()
    try:
        report = service.detect_drift(baseline_id=baseline_id)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return report
