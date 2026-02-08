"""Data Governance API endpoints.

CLO-2: Data Use Agreements and Right-to-Deletion for the clinical trial
patient recruitment platform.

Endpoints:
    DUA:
        POST /governance/dua                     - Create DUA
        GET  /governance/dua                     - List DUAs (with status filter)
        GET  /governance/dua/{id}                - DUA detail
        PUT  /governance/dua/{id}                - Update DUA (state transitions, amendments)
        POST /governance/dua/check-access        - Check if access is covered by active DUA
        GET  /governance/dua/expiring            - DUAs expiring soon
        GET  /governance/dua/templates/{type}     - Get DUA template

    Deletion:
        POST /governance/deletion-requests              - Submit deletion request
        GET  /governance/deletion-requests              - List deletion requests
        GET  /governance/deletion-requests/{id}         - Deletion request detail
        POST /governance/deletion-requests/{id}/execute - Execute approved deletion
        GET  /governance/deletion-requests/{id}/certificate - Get deletion certificate

    Access Log:
        POST /governance/access-log              - Record data access
        GET  /governance/access-log              - Query access logs
        GET  /governance/access-log/suspicious   - Uncovered accesses
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.data_governance import (
    AccessLogCreate,
    AccessLogEntry,
    AccessLogQuery,
    DataCategory,
    DeletionCertificate,
    DeletionRequestCreate,
    DeletionRequestResponse,
    DeletionStatus,
    DUAComplianceCheck,
    DUAComplianceResult,
    DUACreate,
    DUAResponse,
    DUAStatus,
    DUATemplate,
    DUAType,
    DUAUpdate,
    SuspiciousAccessReport,
)
from app.services.data_use_agreement_service import get_dua_service
from app.services.deletion_service import get_deletion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/governance", tags=["Data Governance"])


# ==============================================================================
# DUA Endpoints
# ==============================================================================


@router.post(
    "/dua",
    response_model=DUAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Data Use Agreement",
    description=(
        "Create a new Data Use Agreement in DRAFT status. "
        "DUA must progress through PENDING_REVIEW before being activated."
    ),
)
async def create_dua(request: DUACreate) -> DUAResponse:
    """Create a new DUA."""
    svc = get_dua_service()
    return svc.create_dua(request)


@router.get(
    "/dua/expiring",
    response_model=list[DUAResponse],
    summary="List expiring DUAs",
    description="List active DUAs expiring within the specified number of days.",
)
async def get_expiring_duas(
    within_days: int = Query(default=30, ge=1, le=365, description="Days to look ahead"),
) -> list[DUAResponse]:
    """Get DUAs expiring soon."""
    svc = get_dua_service()
    return svc.get_expiring_duas(within_days=within_days)


@router.get(
    "/dua/templates/{dua_type}",
    response_model=DUATemplate,
    summary="Get DUA template",
    description="Get the pre-populated DUA template for a specific type.",
)
async def get_dua_template(dua_type: DUAType) -> DUATemplate:
    """Get a DUA template by type."""
    svc = get_dua_service()
    try:
        return svc.get_template(dua_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/dua",
    response_model=list[DUAResponse],
    summary="List Data Use Agreements",
    description="List all DUAs with optional status filter.",
)
async def list_duas(
    status_filter: Optional[DUAStatus] = Query(default=None, alias="status", description="Filter by status"),
) -> list[DUAResponse]:
    """List DUAs."""
    svc = get_dua_service()
    return svc.list_duas(status_filter=status_filter)


@router.get(
    "/dua/{dua_id}",
    response_model=DUAResponse,
    summary="Get DUA detail",
    description="Get a specific Data Use Agreement by ID.",
)
async def get_dua(dua_id: str) -> DUAResponse:
    """Get DUA by ID."""
    svc = get_dua_service()
    dua = svc.get_dua(dua_id)
    if dua is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DUA {dua_id} not found",
        )
    return dua


@router.put(
    "/dua/{dua_id}",
    response_model=DUAResponse,
    summary="Update DUA",
    description=(
        "Update a DUA including state transitions and amendments. "
        "For active DUAs, substantive changes require an amendment reason."
    ),
)
async def update_dua(dua_id: str, update: DUAUpdate) -> DUAResponse:
    """Update a DUA."""
    svc = get_dua_service()
    try:
        return svc.update_dua(dua_id, update)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/dua/check-access",
    response_model=DUAComplianceResult,
    summary="Check DUA compliance",
    description="Check if a data access request is covered by an active DUA.",
)
async def check_dua_compliance(check: DUAComplianceCheck) -> DUAComplianceResult:
    """Check if access is covered by active DUA."""
    svc = get_dua_service()
    return svc.check_compliance(check)


# ==============================================================================
# Deletion Endpoints
# ==============================================================================


@router.post(
    "/deletion-requests",
    response_model=DeletionRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit deletion request",
    description=(
        "Submit a right-to-deletion request for a patient's data. "
        "The request goes through validation before execution."
    ),
)
async def create_deletion_request(
    request: DeletionRequestCreate,
) -> DeletionRequestResponse:
    """Submit a new deletion request."""
    svc = get_deletion_service()
    return svc.create_request(request)


@router.get(
    "/deletion-requests",
    response_model=list[DeletionRequestResponse],
    summary="List deletion requests",
    description="List all deletion requests with optional status filter.",
)
async def list_deletion_requests(
    status_filter: Optional[DeletionStatus] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    patient_id: Optional[str] = Query(default=None, description="Filter by patient ID"),
) -> list[DeletionRequestResponse]:
    """List deletion requests."""
    svc = get_deletion_service()
    return svc.list_requests(status_filter=status_filter, patient_id=patient_id)


@router.get(
    "/deletion-requests/{request_id}",
    response_model=DeletionRequestResponse,
    summary="Get deletion request detail",
    description="Get a specific deletion request by ID with full audit trail.",
)
async def get_deletion_request(request_id: str) -> DeletionRequestResponse:
    """Get deletion request by ID."""
    svc = get_deletion_service()
    req = svc.get_request(request_id)
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deletion request {request_id} not found",
        )
    return req


@router.post(
    "/deletion-requests/{request_id}/execute",
    response_model=DeletionRequestResponse,
    summary="Execute deletion",
    description=(
        "Execute an approved deletion request. Deletes patient data across "
        "all relevant stores while retaining audit logs (with PHI redacted)."
    ),
)
async def execute_deletion(
    request_id: str,
    executor: str = Query(default="system", description="Who is executing the deletion"),
) -> DeletionRequestResponse:
    """Execute an approved deletion request."""
    svc = get_deletion_service()
    try:
        return svc.execute_deletion(request_id, executor=executor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/deletion-requests/{request_id}/certificate",
    response_model=DeletionCertificate,
    summary="Get deletion certificate",
    description="Get a certificate confirming what data was deleted.",
)
async def get_deletion_certificate(request_id: str) -> DeletionCertificate:
    """Get deletion certificate for a completed request."""
    svc = get_deletion_service()
    try:
        return svc.get_deletion_certificate(request_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# ==============================================================================
# Access Log Endpoints
# ==============================================================================


@router.post(
    "/access-log",
    response_model=AccessLogEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Record data access",
    description="Record a data access event for audit purposes.",
)
async def record_access(request: AccessLogCreate) -> AccessLogEntry:
    """Record a data access event."""
    svc = get_dua_service()
    return svc.record_access(request)


@router.get(
    "/access-log",
    response_model=list[AccessLogEntry],
    summary="Query access logs",
    description="Query data access logs with filters.",
)
async def query_access_log(
    user_id: Optional[str] = Query(default=None, description="Filter by user"),
    patient_id: Optional[str] = Query(default=None, description="Filter by patient"),
    data_category: Optional[DataCategory] = Query(default=None, description="Filter by category"),
    dua_id: Optional[str] = Query(default=None, description="Filter by DUA"),
) -> list[AccessLogEntry]:
    """Query access logs."""
    svc = get_dua_service()
    query = AccessLogQuery(
        user_id=user_id,
        patient_id=patient_id,
        data_category=data_category,
        dua_id=dua_id,
    )
    return svc.query_access_log(query)


@router.get(
    "/access-log/suspicious",
    response_model=SuspiciousAccessReport,
    summary="Suspicious access report",
    description="Find data accesses not covered by any active DUA.",
)
async def get_suspicious_accesses() -> SuspiciousAccessReport:
    """Get suspicious (uncovered) data accesses."""
    svc = get_dua_service()
    return svc.get_suspicious_accesses()
