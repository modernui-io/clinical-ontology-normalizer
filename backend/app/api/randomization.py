"""Randomization & Blinding API endpoints (CLINICAL-1).

Provides full lifecycle management for clinical trial randomization schemes,
patient randomization, blinding enforcement, unblinding workflow, balance
checking, audit trail, and metrics.

Endpoints:
    GET    /randomization/schemes                          - List schemes
    GET    /randomization/schemes/metrics                  - Aggregated metrics
    POST   /randomization/schemes                          - Create scheme
    GET    /randomization/schemes/{scheme_id}               - Get scheme
    PUT    /randomization/schemes/{scheme_id}               - Update scheme
    DELETE /randomization/schemes/{scheme_id}               - Delete scheme (DRAFT only)
    POST   /randomization/schemes/{scheme_id}/validate      - Validate scheme
    POST   /randomization/schemes/{scheme_id}/activate      - Activate scheme
    POST   /randomization/schemes/{scheme_id}/lock          - Lock scheme
    POST   /randomization/schemes/{scheme_id}/complete      - Complete scheme
    POST   /randomization/schemes/{scheme_id}/randomize     - Randomize patient
    GET    /randomization/schemes/{scheme_id}/balance       - Balance check
    GET    /randomization/schemes/{scheme_id}/list          - Pre-generated list
    GET    /randomization/assignments                       - List assignments (unblinded)
    GET    /randomization/assignments/blinded               - List assignments (blinded)
    GET    /randomization/assignments/{assignment_id}       - Get assignment (unblinded)
    GET    /randomization/assignments/{assignment_id}/blinded - Get assignment (blinded)
    GET    /randomization/assignments/patient/{scheme_id}/{patient_id} - Lookup by patient
    POST   /randomization/unblinding/request               - Request unblinding
    GET    /randomization/unblinding/requests               - List requests
    GET    /randomization/unblinding/requests/{request_id}  - Get request
    POST   /randomization/unblinding/requests/{request_id}/approve - Approve/reject
    GET    /randomization/audit                             - Audit trail
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.randomization import (
    AllocationRatio,
    AssignmentListResponse,
    AuditListResponse,
    BalanceReport,
    BlindedAssignment,
    BlindedAssignmentListResponse,
    BlindingLevel,
    RandomizationAssignment,
    RandomizationAuditEntry,
    RandomizationMetrics,
    RandomizationMethod,
    RandomizationScheme,
    RandomizationStatus,
    RandomizePatientRequest,
    SchemeCreate,
    SchemeListResponse,
    SchemeUpdate,
    UnblindingApproval,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestListResponse,
)
from app.services.randomization_service import get_randomization_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/randomization",
    tags=["Randomization & Blinding"],
)


# ---------------------------------------------------------------------------
# Scheme CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/schemes",
    response_model=SchemeListResponse,
    summary="List randomization schemes",
    description="Retrieve randomization schemes with optional filtering.",
)
async def list_schemes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[RandomizationStatus] = Query(None, description="Filter by status"),
    method: Optional[RandomizationMethod] = Query(None, description="Filter by method"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> SchemeListResponse:
    """List randomization schemes."""
    svc = get_randomization_service()
    items, total = svc.list_schemes(
        trial_id=trial_id, status=status, method=method, limit=limit, offset=offset,
    )
    return SchemeListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/schemes/metrics",
    response_model=RandomizationMetrics,
    summary="Randomization metrics",
    description="Aggregated metrics across all randomization schemes.",
)
async def get_metrics() -> RandomizationMetrics:
    """Get aggregated randomization metrics."""
    svc = get_randomization_service()
    return svc.get_metrics()


@router.post(
    "/schemes",
    response_model=RandomizationScheme,
    status_code=201,
    summary="Create randomization scheme",
    description="Create a new randomization scheme for a clinical trial.",
)
async def create_scheme(req: SchemeCreate) -> RandomizationScheme:
    """Create a new randomization scheme."""
    svc = get_randomization_service()
    return svc.create_scheme(req)


@router.get(
    "/schemes/{scheme_id}",
    response_model=RandomizationScheme,
    summary="Get randomization scheme",
    description="Retrieve a single randomization scheme by ID.",
)
async def get_scheme(scheme_id: str) -> RandomizationScheme:
    """Get a scheme by ID."""
    svc = get_randomization_service()
    scheme = svc.get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return scheme


@router.put(
    "/schemes/{scheme_id}",
    response_model=RandomizationScheme,
    summary="Update randomization scheme",
    description="Update a scheme (only DRAFT or VALIDATED status).",
)
async def update_scheme(scheme_id: str, req: SchemeUpdate) -> RandomizationScheme:
    """Update a scheme."""
    svc = get_randomization_service()
    try:
        scheme = svc.update_scheme(scheme_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return scheme


@router.delete(
    "/schemes/{scheme_id}",
    status_code=204,
    summary="Delete randomization scheme",
    description="Delete a scheme (only DRAFT status).",
)
async def delete_scheme(scheme_id: str) -> None:
    """Delete a DRAFT scheme."""
    svc = get_randomization_service()
    try:
        deleted = svc.delete_scheme(scheme_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")


# ---------------------------------------------------------------------------
# Scheme lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/schemes/{scheme_id}/validate",
    response_model=RandomizationScheme,
    summary="Validate scheme",
    description="Validate a DRAFT scheme for correctness.",
)
async def validate_scheme(
    scheme_id: str,
    validated_by: str = Query("system", description="Validator identity"),
) -> RandomizationScheme:
    """Validate a scheme."""
    svc = get_randomization_service()
    try:
        scheme = svc.validate_scheme(scheme_id, validated_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return scheme


@router.post(
    "/schemes/{scheme_id}/activate",
    response_model=RandomizationScheme,
    summary="Activate scheme",
    description="Activate a VALIDATED scheme to allow randomizations.",
)
async def activate_scheme(scheme_id: str) -> RandomizationScheme:
    """Activate a scheme."""
    svc = get_randomization_service()
    try:
        scheme = svc.activate_scheme(scheme_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return scheme


@router.post(
    "/schemes/{scheme_id}/lock",
    response_model=RandomizationScheme,
    summary="Lock scheme",
    description="Lock an ACTIVE scheme (no more randomizations).",
)
async def lock_scheme(
    scheme_id: str,
    locked_by: str = Query("system", description="User locking the scheme"),
) -> RandomizationScheme:
    """Lock a scheme."""
    svc = get_randomization_service()
    try:
        scheme = svc.lock_scheme(scheme_id, locked_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return scheme


@router.post(
    "/schemes/{scheme_id}/complete",
    response_model=RandomizationScheme,
    summary="Complete scheme",
    description="Mark an ACTIVE or LOCKED scheme as COMPLETED.",
)
async def complete_scheme(scheme_id: str) -> RandomizationScheme:
    """Complete a scheme."""
    svc = get_randomization_service()
    try:
        scheme = svc.complete_scheme(scheme_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return scheme


# ---------------------------------------------------------------------------
# Randomization
# ---------------------------------------------------------------------------


@router.post(
    "/schemes/{scheme_id}/randomize",
    response_model=RandomizationAssignment,
    status_code=201,
    summary="Randomize patient",
    description="Randomize a patient to a treatment arm within a scheme.",
)
async def randomize_patient(
    scheme_id: str, req: RandomizePatientRequest
) -> RandomizationAssignment:
    """Randomize a patient."""
    svc = get_randomization_service()
    try:
        return svc.randomize_patient(scheme_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Balance & randomization list
# ---------------------------------------------------------------------------


@router.get(
    "/schemes/{scheme_id}/balance",
    response_model=BalanceReport,
    summary="Check randomization balance",
    description="Check balance across stratification factors for a scheme.",
)
async def check_balance(scheme_id: str) -> BalanceReport:
    """Check scheme balance."""
    svc = get_randomization_service()
    report = svc.check_balance(scheme_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
    return report


@router.get(
    "/schemes/{scheme_id}/list",
    response_model=list[dict[str, Any]],
    summary="Generate randomization list",
    description="Generate a pre-computed randomization list for a scheme.",
)
async def generate_list(
    scheme_id: str,
    count: int = Query(50, ge=1, le=1000, description="Number of entries"),
) -> list[dict[str, Any]]:
    """Generate randomization list."""
    svc = get_randomization_service()
    try:
        return svc.generate_randomization_list(scheme_id, count)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Assignment lookup
# ---------------------------------------------------------------------------


@router.get(
    "/assignments",
    response_model=AssignmentListResponse,
    summary="List assignments (unblinded)",
    description="List randomization assignments with full arm details. Restricted to unblinded roles.",
)
async def list_assignments(
    scheme_id: Optional[str] = Query(None, description="Filter by scheme ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    arm_id: Optional[str] = Query(None, description="Filter by arm ID"),
    is_unblinded: Optional[bool] = Query(None, description="Filter by unblinding status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> AssignmentListResponse:
    """List assignments (unblinded view)."""
    svc = get_randomization_service()
    items, total = svc.list_assignments(
        scheme_id=scheme_id,
        patient_id=patient_id,
        arm_id=arm_id,
        is_unblinded=is_unblinded,
        limit=limit,
        offset=offset,
    )
    return AssignmentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/assignments/blinded",
    response_model=BlindedAssignmentListResponse,
    summary="List assignments (blinded)",
    description="List assignments with arm details hidden. Safe for blinded personnel.",
)
async def list_blinded_assignments(
    scheme_id: Optional[str] = Query(None, description="Filter by scheme ID"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> BlindedAssignmentListResponse:
    """List assignments (blinded view)."""
    svc = get_randomization_service()
    items, total = svc.list_blinded_assignments(
        scheme_id=scheme_id, limit=limit, offset=offset,
    )
    return BlindedAssignmentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/assignments/{assignment_id}",
    response_model=RandomizationAssignment,
    summary="Get assignment (unblinded)",
    description="Retrieve full assignment details including arm. Restricted to unblinded roles.",
)
async def get_assignment(assignment_id: str) -> RandomizationAssignment:
    """Get an assignment (unblinded)."""
    svc = get_randomization_service()
    assignment = svc.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} not found")
    return assignment


@router.get(
    "/assignments/{assignment_id}/blinded",
    response_model=BlindedAssignment,
    summary="Get assignment (blinded)",
    description="Retrieve blinded assignment view (no arm info).",
)
async def get_blinded_assignment(assignment_id: str) -> BlindedAssignment:
    """Get an assignment (blinded view)."""
    svc = get_randomization_service()
    blinded = svc.get_blinded_assignment(assignment_id)
    if not blinded:
        raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} not found")
    return blinded


@router.get(
    "/assignments/patient/{scheme_id}/{patient_id}",
    response_model=RandomizationAssignment,
    summary="Lookup patient assignment",
    description="Look up a patient's assignment within a scheme.",
)
async def get_patient_assignment(scheme_id: str, patient_id: str) -> RandomizationAssignment:
    """Look up a patient's assignment."""
    svc = get_randomization_service()
    assignment = svc.get_patient_assignment(scheme_id, patient_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment found for patient {patient_id} in scheme {scheme_id}",
        )
    return assignment


# ---------------------------------------------------------------------------
# Unblinding workflow
# ---------------------------------------------------------------------------


@router.post(
    "/unblinding/request",
    response_model=UnblindingRequest,
    status_code=201,
    summary="Request unblinding",
    description="Submit a request to unblind a patient's treatment assignment.",
)
async def create_unblinding_request(req: UnblindingRequestCreate) -> UnblindingRequest:
    """Create an unblinding request."""
    svc = get_randomization_service()
    try:
        return svc.create_unblinding_request(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/unblinding/requests",
    response_model=UnblindingRequestListResponse,
    summary="List unblinding requests",
    description="List unblinding requests with optional filters.",
)
async def list_unblinding_requests(
    scheme_id: Optional[str] = Query(None, description="Filter by scheme ID"),
    pending_only: bool = Query(False, description="Only pending requests"),
) -> UnblindingRequestListResponse:
    """List unblinding requests."""
    svc = get_randomization_service()
    items = svc.list_unblinding_requests(scheme_id=scheme_id, pending_only=pending_only)
    return UnblindingRequestListResponse(items=items, total=len(items))


@router.get(
    "/unblinding/requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Get unblinding request",
    description="Retrieve a single unblinding request by ID.",
)
async def get_unblinding_request(request_id: str) -> UnblindingRequest:
    """Get an unblinding request."""
    svc = get_randomization_service()
    req = svc.get_unblinding_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail=f"Unblinding request {request_id} not found")
    return req


@router.post(
    "/unblinding/requests/{request_id}/approve",
    response_model=UnblindingRequest,
    summary="Approve or reject unblinding",
    description="Approve or reject a pending unblinding request.",
)
async def approve_unblinding(
    request_id: str, approval: UnblindingApproval
) -> UnblindingRequest:
    """Approve or reject unblinding."""
    svc = get_randomization_service()
    try:
        req = svc.approve_unblinding(request_id, approval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not req:
        raise HTTPException(status_code=404, detail=f"Unblinding request {request_id} not found")
    return req


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@router.get(
    "/audit",
    response_model=AuditListResponse,
    summary="Audit trail",
    description="Retrieve randomization audit trail entries.",
)
async def get_audit_trail(
    scheme_id: Optional[str] = Query(None, description="Filter by scheme ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> AuditListResponse:
    """Get audit trail."""
    svc = get_randomization_service()
    items, total = svc.get_audit_trail(
        scheme_id=scheme_id, action=action, limit=limit, offset=offset,
    )
    return AuditListResponse(items=items, total=total)
