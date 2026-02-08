"""Referral Network API endpoints.

VP-Product-5: Site referral network and trial enrollment workflow.

Endpoints:
    POST /api/v1/referrals                                    - Create referral
    GET  /api/v1/referrals                                    - List referrals
    GET  /api/v1/referrals/analytics                          - Network analytics
    GET  /api/v1/referrals/{referral_id}                      - Referral detail
    PUT  /api/v1/referrals/{referral_id}                      - Update referral
    POST /api/v1/referrals/suggest-sites                      - Site suggestions
    GET  /api/v1/referrals/enrollment/{patient_id}/{trial_id} - Enrollment status
    POST /api/v1/referrals/enrollment/{patient_id}/{trial_id}/advance - Advance enrollment
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.schemas.referral_network import (
    EnrollmentAdvanceRequest,
    EnrollmentAdvanceResponse,
    EnrollmentTracking,
    NetworkAnalytics,
    ReferralCreate,
    ReferralListResponse,
    ReferralResponse,
    ReferralStatus,
    ReferralUpdate,
    SiteSuggestionRequest,
    SiteSuggestionResponse,
)
from app.services.referral_service import get_referral_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/referrals", tags=["Referral Network"])


# ==============================================================================
# Referral CRUD
# ==============================================================================


@router.post(
    "",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a referral",
    description="Create a new patient referral from one site to another for a trial.",
)
async def create_referral(
    request: Request,
    create: ReferralCreate,
) -> ReferralResponse:
    """Create a new referral."""
    service = get_referral_service()
    return service.create_referral(create)


@router.get(
    "",
    response_model=ReferralListResponse,
    summary="List referrals",
    description="List referrals with optional filters by trial, site, status, or patient.",
)
async def list_referrals(
    request: Request,
    trial_id: str | None = Query(None, description="Filter by trial ID"),
    site_id: str | None = Query(None, description="Filter by site ID (source or destination)"),
    status_filter: ReferralStatus | None = Query(
        None, alias="status", description="Filter by referral status"
    ),
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
) -> ReferralListResponse:
    """List referrals with filters."""
    service = get_referral_service()
    referrals, total = service.list_referrals(
        trial_id=trial_id,
        site_id=site_id,
        status=status_filter,
        patient_id=patient_id,
        offset=offset,
        limit=limit,
    )
    return ReferralListResponse(
        referrals=referrals,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/analytics",
    response_model=NetworkAnalytics,
    summary="Network analytics",
    description="Get referral network analytics including volume, acceptance rates, and conversion metrics.",
)
async def get_analytics(
    request: Request,
    trial_id: str | None = Query(None, description="Filter analytics by trial ID"),
    site_id: str | None = Query(None, description="Filter analytics by site ID"),
) -> NetworkAnalytics:
    """Get referral network analytics."""
    service = get_referral_service()
    return service.get_analytics(trial_id=trial_id, site_id=site_id)


@router.get(
    "/{referral_id}",
    response_model=ReferralResponse,
    summary="Get referral detail",
    description="Get full details of a specific referral.",
)
async def get_referral(
    referral_id: str,
    request: Request,
) -> ReferralResponse:
    """Get a referral by ID."""
    service = get_referral_service()
    referral = service.get_referral(referral_id)
    if referral is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found",
        )
    return referral


@router.put(
    "/{referral_id}",
    response_model=ReferralResponse,
    summary="Update referral",
    description="Update a referral's status, priority, or other fields.",
)
async def update_referral(
    referral_id: str,
    request: Request,
    update: ReferralUpdate,
) -> ReferralResponse:
    """Update a referral."""
    service = get_referral_service()
    try:
        result = service.update_referral(referral_id, update)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found",
        )
    return result


# ==============================================================================
# Site suggestions
# ==============================================================================


@router.post(
    "/suggest-sites",
    response_model=SiteSuggestionResponse,
    summary="Suggest sites for a patient/trial",
    description=(
        "Get ranked site suggestions based on geographic proximity, "
        "site capacity, performance, and specialty match."
    ),
)
async def suggest_sites(
    request: Request,
    suggestion_request: SiteSuggestionRequest,
) -> SiteSuggestionResponse:
    """Get site suggestions for a patient/trial combination."""
    service = get_referral_service()
    return service.suggest_sites(suggestion_request)


# ==============================================================================
# Enrollment workflow
# ==============================================================================


@router.get(
    "/enrollment/{patient_id}/{trial_id}",
    response_model=EnrollmentTracking,
    summary="Get enrollment status",
    description="Get the enrollment tracking status for a patient/trial pair.",
)
async def get_enrollment(
    patient_id: str,
    trial_id: str,
    request: Request,
) -> EnrollmentTracking:
    """Get enrollment tracking for a patient/trial pair."""
    service = get_referral_service()
    tracking = service.get_enrollment(patient_id, trial_id)
    if tracking is None:
        # Auto-create enrollment tracking if not found
        tracking = service.create_enrollment(patient_id, trial_id)
    return tracking


@router.post(
    "/enrollment/{patient_id}/{trial_id}/advance",
    response_model=EnrollmentAdvanceResponse,
    summary="Advance enrollment stage",
    description="Advance a patient's enrollment to the next workflow stage.",
)
async def advance_enrollment(
    patient_id: str,
    trial_id: str,
    request: Request,
    advance_request: EnrollmentAdvanceRequest | None = None,
) -> EnrollmentAdvanceResponse:
    """Advance enrollment to the next stage."""
    service = get_referral_service()

    # Ensure enrollment exists
    tracking = service.get_enrollment(patient_id, trial_id)
    if tracking is None:
        service.create_enrollment(patient_id, trial_id)

    notes = advance_request.notes if advance_request else None

    try:
        result = service.advance_enrollment(patient_id, trial_id, notes=notes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrollment not found for patient {patient_id} / trial {trial_id}",
        )
    return result
