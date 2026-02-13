"""Emergency Unblinding API endpoints (EMRG-UBL).

Provides comprehensive emergency unblinding operations: unblinding requests,
approval workflows, unblinding notifications, audit log entries, and
unblinding metrics.

Endpoints:
    GET    /emergency-unblinding/requests                          - List unblinding requests
    GET    /emergency-unblinding/requests/{request_id}             - Get single request
    POST   /emergency-unblinding/requests                          - Create request
    PUT    /emergency-unblinding/requests/{request_id}             - Update request
    DELETE /emergency-unblinding/requests/{request_id}             - Delete request
    GET    /emergency-unblinding/approvals                         - List approvals
    GET    /emergency-unblinding/approvals/{approval_id}           - Get single approval
    POST   /emergency-unblinding/approvals                         - Create approval
    PUT    /emergency-unblinding/approvals/{approval_id}           - Update approval
    DELETE /emergency-unblinding/approvals/{approval_id}           - Delete approval
    GET    /emergency-unblinding/notifications                     - List notifications
    GET    /emergency-unblinding/notifications/{notification_id}   - Get single notification
    POST   /emergency-unblinding/notifications                     - Create notification
    PUT    /emergency-unblinding/notifications/{notification_id}   - Update notification
    DELETE /emergency-unblinding/notifications/{notification_id}   - Delete notification
    GET    /emergency-unblinding/audit-logs                        - List audit logs
    GET    /emergency-unblinding/audit-logs/{log_id}               - Get single audit log
    POST   /emergency-unblinding/audit-logs                        - Create audit log
    PUT    /emergency-unblinding/audit-logs/{log_id}               - Update audit log
    DELETE /emergency-unblinding/audit-logs/{log_id}               - Delete audit log
    GET    /emergency-unblinding/metrics                           - Unblinding metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.emergency_unblinding import (
    ApprovalDecision,
    AuditAction,
    EmergencyUnblindingMetrics,
    NotificationChannel,
    RequestStatus,
    UnblindingApproval,
    UnblindingApprovalCreate,
    UnblindingApprovalListResponse,
    UnblindingApprovalUpdate,
    UnblindingAuditLog,
    UnblindingAuditLogCreate,
    UnblindingAuditLogListResponse,
    UnblindingAuditLogUpdate,
    UnblindingNotification,
    UnblindingNotificationCreate,
    UnblindingNotificationListResponse,
    UnblindingNotificationUpdate,
    UnblindingReason,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestListResponse,
    UnblindingRequestUpdate,
)
from app.services.emergency_unblinding_service import get_emergency_unblinding_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/emergency-unblinding",
    tags=["Emergency Unblinding"],
)


# ---------------------------------------------------------------------------
# Unblinding Requests
# ---------------------------------------------------------------------------


@router.get(
    "/requests",
    response_model=UnblindingRequestListResponse,
    summary="List unblinding requests",
    description="Retrieve unblinding requests with optional filtering by trial, reason, and status.",
)
async def list_requests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    unblinding_reason: Optional[UnblindingReason] = Query(None, description="Filter by unblinding reason"),
    request_status: Optional[RequestStatus] = Query(None, description="Filter by request status"),
) -> UnblindingRequestListResponse:
    svc = get_emergency_unblinding_service()
    items = svc.list_requests(
        trial_id=trial_id, unblinding_reason=unblinding_reason, request_status=request_status
    )
    return UnblindingRequestListResponse(items=items, total=len(items))


@router.get(
    "/requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Get an unblinding request",
)
async def get_request(request_id: str) -> UnblindingRequest:
    svc = get_emergency_unblinding_service()
    record = svc.get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unblinding request '{request_id}' not found")
    return record


@router.post(
    "/requests",
    response_model=UnblindingRequest,
    status_code=201,
    summary="Create an unblinding request",
)
async def create_request(payload: UnblindingRequestCreate) -> UnblindingRequest:
    svc = get_emergency_unblinding_service()
    return svc.create_request(payload)


@router.put(
    "/requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Update an unblinding request",
)
async def update_request(
    request_id: str, payload: UnblindingRequestUpdate
) -> UnblindingRequest:
    svc = get_emergency_unblinding_service()
    updated = svc.update_request(request_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Unblinding request '{request_id}' not found")
    return updated


@router.delete(
    "/requests/{request_id}",
    status_code=204,
    summary="Delete an unblinding request",
)
async def delete_request(request_id: str) -> None:
    svc = get_emergency_unblinding_service()
    deleted = svc.delete_request(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unblinding request '{request_id}' not found")


# ---------------------------------------------------------------------------
# Unblinding Approvals
# ---------------------------------------------------------------------------


@router.get(
    "/approvals",
    response_model=UnblindingApprovalListResponse,
    summary="List unblinding approvals",
    description="Retrieve unblinding approvals with optional filtering by trial, decision, and request.",
)
async def list_approvals(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    approval_decision: Optional[ApprovalDecision] = Query(None, description="Filter by approval decision"),
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
) -> UnblindingApprovalListResponse:
    svc = get_emergency_unblinding_service()
    items = svc.list_approvals(
        trial_id=trial_id, approval_decision=approval_decision, request_id=request_id
    )
    return UnblindingApprovalListResponse(items=items, total=len(items))


@router.get(
    "/approvals/{approval_id}",
    response_model=UnblindingApproval,
    summary="Get an unblinding approval",
)
async def get_approval(approval_id: str) -> UnblindingApproval:
    svc = get_emergency_unblinding_service()
    record = svc.get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unblinding approval '{approval_id}' not found")
    return record


@router.post(
    "/approvals",
    response_model=UnblindingApproval,
    status_code=201,
    summary="Create an unblinding approval",
)
async def create_approval(payload: UnblindingApprovalCreate) -> UnblindingApproval:
    svc = get_emergency_unblinding_service()
    return svc.create_approval(payload)


@router.put(
    "/approvals/{approval_id}",
    response_model=UnblindingApproval,
    summary="Update an unblinding approval",
)
async def update_approval(
    approval_id: str, payload: UnblindingApprovalUpdate
) -> UnblindingApproval:
    svc = get_emergency_unblinding_service()
    updated = svc.update_approval(approval_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Unblinding approval '{approval_id}' not found")
    return updated


@router.delete(
    "/approvals/{approval_id}",
    status_code=204,
    summary="Delete an unblinding approval",
)
async def delete_approval(approval_id: str) -> None:
    svc = get_emergency_unblinding_service()
    deleted = svc.delete_approval(approval_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unblinding approval '{approval_id}' not found")


# ---------------------------------------------------------------------------
# Unblinding Notifications
# ---------------------------------------------------------------------------


@router.get(
    "/notifications",
    response_model=UnblindingNotificationListResponse,
    summary="List unblinding notifications",
    description="Retrieve unblinding notifications with optional filtering by trial, channel, and acknowledgment.",
)
async def list_notifications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    notification_channel: Optional[NotificationChannel] = Query(None, description="Filter by notification channel"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
) -> UnblindingNotificationListResponse:
    svc = get_emergency_unblinding_service()
    items = svc.list_notifications(
        trial_id=trial_id, notification_channel=notification_channel, acknowledged=acknowledged
    )
    return UnblindingNotificationListResponse(items=items, total=len(items))


@router.get(
    "/notifications/{notification_id}",
    response_model=UnblindingNotification,
    summary="Get an unblinding notification",
)
async def get_notification(notification_id: str) -> UnblindingNotification:
    svc = get_emergency_unblinding_service()
    record = svc.get_notification(notification_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding notification '{notification_id}' not found"
        )
    return record


@router.post(
    "/notifications",
    response_model=UnblindingNotification,
    status_code=201,
    summary="Create an unblinding notification",
)
async def create_notification(payload: UnblindingNotificationCreate) -> UnblindingNotification:
    svc = get_emergency_unblinding_service()
    return svc.create_notification(payload)


@router.put(
    "/notifications/{notification_id}",
    response_model=UnblindingNotification,
    summary="Update an unblinding notification",
)
async def update_notification(
    notification_id: str, payload: UnblindingNotificationUpdate
) -> UnblindingNotification:
    svc = get_emergency_unblinding_service()
    updated = svc.update_notification(notification_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding notification '{notification_id}' not found"
        )
    return updated


@router.delete(
    "/notifications/{notification_id}",
    status_code=204,
    summary="Delete an unblinding notification",
)
async def delete_notification(notification_id: str) -> None:
    svc = get_emergency_unblinding_service()
    deleted = svc.delete_notification(notification_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Unblinding notification '{notification_id}' not found"
        )


# ---------------------------------------------------------------------------
# Unblinding Audit Logs
# ---------------------------------------------------------------------------


@router.get(
    "/audit-logs",
    response_model=UnblindingAuditLogListResponse,
    summary="List unblinding audit logs",
    description="Retrieve unblinding audit logs with optional filtering by trial, action, and request.",
)
async def list_audit_logs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    audit_action: Optional[AuditAction] = Query(None, description="Filter by audit action"),
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
) -> UnblindingAuditLogListResponse:
    svc = get_emergency_unblinding_service()
    items = svc.list_audit_logs(
        trial_id=trial_id, audit_action=audit_action, request_id=request_id
    )
    return UnblindingAuditLogListResponse(items=items, total=len(items))


@router.get(
    "/audit-logs/{log_id}",
    response_model=UnblindingAuditLog,
    summary="Get an unblinding audit log",
)
async def get_audit_log(log_id: str) -> UnblindingAuditLog:
    svc = get_emergency_unblinding_service()
    record = svc.get_audit_log(log_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unblinding audit log '{log_id}' not found")
    return record


@router.post(
    "/audit-logs",
    response_model=UnblindingAuditLog,
    status_code=201,
    summary="Create an unblinding audit log",
)
async def create_audit_log(payload: UnblindingAuditLogCreate) -> UnblindingAuditLog:
    svc = get_emergency_unblinding_service()
    return svc.create_audit_log(payload)


@router.put(
    "/audit-logs/{log_id}",
    response_model=UnblindingAuditLog,
    summary="Update an unblinding audit log",
)
async def update_audit_log(
    log_id: str, payload: UnblindingAuditLogUpdate
) -> UnblindingAuditLog:
    svc = get_emergency_unblinding_service()
    updated = svc.update_audit_log(log_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Unblinding audit log '{log_id}' not found")
    return updated


@router.delete(
    "/audit-logs/{log_id}",
    status_code=204,
    summary="Delete an unblinding audit log",
)
async def delete_audit_log(log_id: str) -> None:
    svc = get_emergency_unblinding_service()
    deleted = svc.delete_audit_log(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unblinding audit log '{log_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=EmergencyUnblindingMetrics,
    summary="Get emergency unblinding metrics",
    description="Aggregated metrics across all emergency unblinding operations.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> EmergencyUnblindingMetrics:
    svc = get_emergency_unblinding_service()
    return svc.get_metrics(trial_id=trial_id)
