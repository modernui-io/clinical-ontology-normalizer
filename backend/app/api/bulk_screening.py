"""Bulk Screening API endpoints.

Screens batches of patients against multiple clinical trials in a single
request.  Designed for site-level screening (e.g., "screen 5,000 patients
from a site against all Regeneron trials").

Endpoints:
    POST /api/v1/trials/bulk-screen                - Bulk screen patients against trials
    POST /api/v1/trials/dual-enrollment-candidates - Find cross-trial eligible patients
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, PermissionChecker
from app.schemas.trial import (
    BulkScreeningRequest,
    BulkScreeningResponse,
    DualEnrollmentRequest,
    DualEnrollmentResponse,
)
from app.services.bulk_screening_service import get_bulk_screening_service
from app.services.dual_enrollment_service import get_dual_enrollment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trials", tags=["Clinical Trials"])


@router.post(
    "/bulk-screen",
    response_model=BulkScreeningResponse,
    summary="Bulk screen patients against multiple trials",
    description=(
        "Screen a batch of patients against one or more clinical trials. "
        "Returns ranked results grouped by trial with match scores and "
        "aggregate statistics. Designed for site-level screening workflows "
        "(e.g., screen all patients from a site against a sponsor's trials). "
        "Maximum 10,000 patients x 100 trials per request."
    ),
)
async def bulk_screen_patients(
    request: Request,
    body: BulkScreeningRequest,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.SCREEN_PATIENTS])),
) -> BulkScreeningResponse:
    """Bulk screen patients against multiple clinical trials."""
    service = get_bulk_screening_service()

    try:
        result = await service.bulk_screen(body, session=session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.info(
        "Bulk screening API: %d patients x %d trials, "
        "%d eligible (%.1f%% pass rate) in %.0fms",
        result.summary.total_patients,
        result.summary.total_trials,
        result.summary.total_eligible,
        result.summary.overall_pass_rate,
        result.summary.screening_duration_ms,
    )

    return result


@router.post(
    "/dual-enrollment-candidates",
    response_model=DualEnrollmentResponse,
    summary="Find cross-trial eligible patients",
    description=(
        "Detect patients currently enrolled in one trial who also qualify for "
        "other active trials. Returns patients grouped with their current "
        "enrollment(s) and additional trial matches with scores. "
        "Optionally filter to find candidates for a specific trial."
    ),
)
async def find_dual_enrollment_candidates(
    request: Request,
    body: DualEnrollmentRequest | None = None,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.SCREEN_PATIENTS])),
) -> DualEnrollmentResponse:
    """Find patients enrolled in one trial who qualify for others."""
    if body is None:
        body = DualEnrollmentRequest()

    service = get_dual_enrollment_service()
    result = await service.find_dual_enrollment_candidates(body, session=session)

    logger.info(
        "Dual enrollment API: checked %d patients across %d trials, "
        "found %d with %d additional matches in %.0fms",
        result.summary.total_enrolled_patients_checked,
        result.summary.trials_checked,
        result.summary.total_patients_with_additional_matches,
        result.summary.total_additional_matches,
        result.summary.screening_duration_ms,
    )

    return result
