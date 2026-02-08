"""Vendor Risk Management API endpoints.

COO-3: Vendor Risk Management for the clinical trial patient recruitment
platform. Exposes vendor CRUD, risk assessments, certification tracking,
and portfolio metrics.

Endpoints:
    GET  /vendor-management/vendors                  - List vendors with filters
    GET  /vendor-management/vendors/metrics           - Portfolio metrics
    GET  /vendor-management/vendors/{id}              - Vendor detail
    POST /vendor-management/vendors                   - Create vendor
    PUT  /vendor-management/vendors/{id}              - Update vendor
    POST /vendor-management/vendors/{id}/suspend      - Suspend vendor
    POST /vendor-management/vendors/{id}/reactivate   - Reactivate vendor
    POST /vendor-management/vendors/{id}/assess       - Conduct assessment
    GET  /vendor-management/vendors/{id}/assessments  - Assessment history
    GET  /vendor-management/certifications/expiring   - Expiring certifications
    GET  /vendor-management/contracts/renewals        - Upcoming contract renewals
    GET  /vendor-management/data-access/phi           - Vendors with PHI access
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.vendor_management import (
    AssessmentListResponse,
    AssessmentRequest,
    CertificationAlert,
    ContractRenewal,
    DataAccessLevel,
    RiskLevel,
    VendorCategory,
    VendorCreate,
    VendorListResponse,
    VendorMetrics,
    VendorRecord,
    VendorRiskAssessment,
    VendorStatus,
    VendorUpdate,
)
from app.services.vendor_management_service import get_vendor_management_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vendor-management", tags=["Vendor Management"])


# ---------------------------------------------------------------------------
# Vendor CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/vendors",
    response_model=VendorListResponse,
    summary="List vendors",
    description=(
        "List all vendors with optional filtering by category, risk level, "
        "and status. Supports pagination via limit and offset."
    ),
)
async def list_vendors(
    category: Optional[VendorCategory] = Query(
        default=None, description="Filter by vendor category"
    ),
    risk_level: Optional[RiskLevel] = Query(
        default=None, description="Filter by risk level"
    ),
    vendor_status: Optional[VendorStatus] = Query(
        default=None,
        alias="status",
        description="Filter by vendor status",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> VendorListResponse:
    """List vendors with optional filters."""
    service = get_vendor_management_service()
    vendors, total = service.list_vendors(
        category=category,
        risk_level=risk_level,
        status=vendor_status,
        limit=limit,
        offset=offset,
    )
    return VendorListResponse(
        items=vendors, total=total, limit=limit, offset=offset
    )


@router.get(
    "/vendors/metrics",
    response_model=VendorMetrics,
    summary="Get vendor portfolio metrics",
    description=(
        "Returns aggregated metrics across the entire vendor portfolio "
        "including counts by category, risk level, spend, and alerts."
    ),
)
async def get_vendor_metrics() -> VendorMetrics:
    """Get aggregated vendor portfolio metrics."""
    service = get_vendor_management_service()
    return service.get_metrics()


@router.get(
    "/vendors/{vendor_id}",
    response_model=VendorRecord,
    summary="Get vendor detail",
    description="Returns detailed information about a specific vendor.",
)
async def get_vendor(vendor_id: str) -> VendorRecord:
    """Get a single vendor by ID."""
    service = get_vendor_management_service()
    vendor = service.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    return vendor


@router.post(
    "/vendors",
    response_model=VendorRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor",
    description="Create a new vendor record in the registry.",
)
async def create_vendor(request: VendorCreate) -> VendorRecord:
    """Create a new vendor."""
    service = get_vendor_management_service()
    return service.create_vendor(request)


@router.put(
    "/vendors/{vendor_id}",
    response_model=VendorRecord,
    summary="Update vendor",
    description="Update an existing vendor record.",
)
async def update_vendor(
    vendor_id: str, request: VendorUpdate
) -> VendorRecord:
    """Update a vendor."""
    service = get_vendor_management_service()
    updated = service.update_vendor(vendor_id, request)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    return updated


# ---------------------------------------------------------------------------
# Vendor Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/vendors/{vendor_id}/suspend",
    response_model=VendorRecord,
    summary="Suspend vendor",
    description="Suspend a vendor with a reason. Cannot suspend already-suspended or terminated vendors.",
)
async def suspend_vendor(
    vendor_id: str,
    reason: str = Query(..., description="Reason for suspension"),
) -> VendorRecord:
    """Suspend a vendor."""
    service = get_vendor_management_service()
    try:
        result = service.suspend_vendor(vendor_id, reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    return result


@router.post(
    "/vendors/{vendor_id}/reactivate",
    response_model=VendorRecord,
    summary="Reactivate vendor",
    description="Reactivate a previously suspended vendor.",
)
async def reactivate_vendor(vendor_id: str) -> VendorRecord:
    """Reactivate a suspended vendor."""
    service = get_vendor_management_service()
    try:
        result = service.reactivate_vendor(vendor_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    return result


# ---------------------------------------------------------------------------
# Risk Assessments
# ---------------------------------------------------------------------------


@router.post(
    "/vendors/{vendor_id}/assess",
    response_model=VendorRiskAssessment,
    status_code=status.HTTP_201_CREATED,
    summary="Conduct risk assessment",
    description=(
        "Conduct a risk assessment on a vendor. Scores are provided on a 0-10 "
        "scale and combined into a weighted overall score (0-100). The vendor's "
        "risk level is automatically updated based on the score."
    ),
)
async def conduct_assessment(
    vendor_id: str, request: AssessmentRequest
) -> VendorRiskAssessment:
    """Conduct a risk assessment on a vendor."""
    service = get_vendor_management_service()
    try:
        result = service.conduct_assessment(vendor_id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    return result


@router.get(
    "/vendors/{vendor_id}/assessments",
    response_model=AssessmentListResponse,
    summary="Get assessment history",
    description="Returns all risk assessments conducted on a vendor.",
)
async def get_assessments(vendor_id: str) -> AssessmentListResponse:
    """Get assessment history for a vendor."""
    service = get_vendor_management_service()
    assessments = service.get_assessments(vendor_id)
    if assessments is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    return AssessmentListResponse(
        items=assessments, total=len(assessments), vendor_id=vendor_id
    )


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------


@router.get(
    "/certifications/expiring",
    response_model=list[CertificationAlert],
    summary="Get expiring certifications",
    description=(
        "Returns a list of vendor certifications that are expired or "
        "expiring within 90 days."
    ),
)
async def get_expiring_certifications() -> list[CertificationAlert]:
    """Get expiring certifications."""
    service = get_vendor_management_service()
    return service.check_certifications()


# ---------------------------------------------------------------------------
# Contract Renewals
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/renewals",
    response_model=list[ContractRenewal],
    summary="Get upcoming contract renewals",
    description="Returns vendors with contracts expiring within the specified number of days.",
)
async def get_contract_renewals(
    days: int = Query(
        default=90, ge=1, le=365, description="Look-ahead days"
    ),
) -> list[ContractRenewal]:
    """Get upcoming contract renewals."""
    service = get_vendor_management_service()
    return service.get_contract_renewals(days_ahead=days)


# ---------------------------------------------------------------------------
# Data Access
# ---------------------------------------------------------------------------


@router.get(
    "/data-access/phi",
    response_model=list[VendorRecord],
    summary="Get vendors with PHI access",
    description=(
        "Returns all vendors that have PHI (Protected Health Information) "
        "data access. Critical for HIPAA compliance tracking."
    ),
)
async def get_phi_vendors() -> list[VendorRecord]:
    """Get all vendors with PHI access."""
    service = get_vendor_management_service()
    return service.get_vendors_by_data_access(DataAccessLevel.PHI)
