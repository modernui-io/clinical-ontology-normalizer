"""Clinical Trials API endpoints.

Endpoints for managing clinical trials, screening patients against
eligibility criteria, and tracking enrollment.

Endpoints:
    GET  /api/v1/trials              - List trials
    POST /api/v1/trials              - Create a trial
    GET  /api/v1/trials/{id}         - Get trial details
    PUT  /api/v1/trials/{id}         - Update a trial
    DELETE /api/v1/trials/{id}       - Delete a trial
    POST /api/v1/trials/{id}/screen  - Screen patients for eligibility
    GET  /api/v1/trials/{id}/check/{patient_id} - Check single patient eligibility
    POST /api/v1/trials/{id}/enroll  - Enroll a patient
    PUT  /api/v1/trials/{id}/enrollments/{patient_id} - Update enrollment
    GET  /api/v1/trials/{id}/enrollments - List enrollments
    GET  /api/v1/trials/{id}/dashboard - Enrollment dashboard
    GET  /api/v1/trials/stats        - Service statistics
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.models.trial import EnrollmentStatus, TrialStatus
from app.schemas.trial import (
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentUpdate,
    PatientEligibility,
    ScreeningRequest,
    ScreeningResponse,
    TrialCreate,
    TrialDashboard,
    TrialResponse,
    TrialSummary,
    TrialUpdate,
)
from app.services.trial_eligibility_service import get_trial_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trials", tags=["Clinical Trials"])


# ==============================================================================
# Response wrappers
# ==============================================================================


class TrialListResponse(BaseModel):
    """Paginated trial list response."""
    trials: list[TrialSummary]
    total: int
    offset: int
    limit: int


class EnrollmentListResponse(BaseModel):
    """Paginated enrollment list response."""
    enrollments: list[EnrollmentResponse]
    total: int
    offset: int
    limit: int


# ==============================================================================
# Trial CRUD
# ==============================================================================


@router.get(
    "",
    response_model=TrialListResponse,
    summary="List clinical trials",
    description="Get a paginated list of clinical trials with optional filtering.",
)
async def list_trials(
    status: TrialStatus | None = Query(None, description="Filter by trial status"),
    sponsor: str | None = Query(None, description="Filter by sponsor name"),
    therapeutic_area: str | None = Query(None, description="Filter by therapeutic area"),
    search: str | None = Query(None, description="Search in name, description, NCT number"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> TrialListResponse:
    """List all clinical trials."""
    service = get_trial_service()
    trials, total = service.list_trials(
        status=status,
        sponsor=sponsor,
        therapeutic_area=therapeutic_area,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TrialListResponse(trials=trials, total=total, offset=offset, limit=limit)


@router.post(
    "",
    response_model=TrialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a clinical trial",
    description="Create a new clinical trial with inclusion/exclusion criteria.",
)
async def create_trial(create: TrialCreate) -> TrialResponse:
    """Create a new clinical trial."""
    service = get_trial_service()
    trial = service.create_trial(create)
    logger.info(f"Created trial via API: {trial.id}")
    return trial


@router.get(
    "/stats",
    summary="Get trial service statistics",
    description="Get aggregate statistics across all trials.",
)
async def get_trial_stats() -> dict:
    """Get trial service statistics."""
    service = get_trial_service()
    return service.get_stats()


@router.get(
    "/{trial_id}",
    response_model=TrialResponse,
    summary="Get trial details",
    description="Get full details of a clinical trial including criteria and enrollment status.",
)
async def get_trial(trial_id: str) -> TrialResponse:
    """Get a trial by ID."""
    service = get_trial_service()
    trial = service.get_trial(trial_id)
    if not trial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return trial


@router.put(
    "/{trial_id}",
    response_model=TrialResponse,
    summary="Update a clinical trial",
    description="Update trial metadata or eligibility criteria.",
)
async def update_trial(trial_id: str, update: TrialUpdate) -> TrialResponse:
    """Update an existing trial."""
    service = get_trial_service()
    trial = service.update_trial(trial_id, update)
    if not trial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return trial


@router.delete(
    "/{trial_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a clinical trial",
)
async def delete_trial(trial_id: str) -> None:
    """Delete a trial."""
    service = get_trial_service()
    if not service.delete_trial(trial_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )


# ==============================================================================
# Patient Screening
# ==============================================================================


@router.post(
    "/{trial_id}/screen",
    response_model=ScreeningResponse,
    summary="Screen patients for trial eligibility",
    description="Execute eligibility criteria against patient population and return matching candidates.",
)
async def screen_patients(
    trial_id: str,
    request: ScreeningRequest | None = None,
) -> ScreeningResponse:
    """Screen patients against trial eligibility criteria."""
    service = get_trial_service()
    result = service.screen_patients(trial_id, request)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return result


@router.get(
    "/{trial_id}/check/{patient_id}",
    response_model=PatientEligibility,
    summary="Check patient eligibility",
    description="Check a single patient's eligibility for a specific trial.",
)
async def check_patient_eligibility(
    trial_id: str,
    patient_id: str,
) -> PatientEligibility:
    """Check if a specific patient is eligible for a trial."""
    service = get_trial_service()
    result = service.check_patient_eligibility(trial_id, patient_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return result


# ==============================================================================
# Enrollment Management
# ==============================================================================


@router.post(
    "/{trial_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll a patient in a trial",
    description="Add a patient to the trial enrollment pipeline.",
)
async def enroll_patient(
    trial_id: str,
    create: EnrollmentCreate,
) -> EnrollmentResponse:
    """Enroll a patient in a trial."""
    service = get_trial_service()
    result = service.enroll_patient(trial_id, create)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return result


@router.put(
    "/{trial_id}/enrollments/{patient_id}",
    response_model=EnrollmentResponse,
    summary="Update enrollment status",
    description="Update a patient's enrollment status in a trial.",
)
async def update_enrollment(
    trial_id: str,
    patient_id: str,
    update: EnrollmentUpdate,
) -> EnrollmentResponse:
    """Update a patient's enrollment."""
    service = get_trial_service()
    result = service.update_enrollment(trial_id, patient_id, update)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrollment not found for patient {patient_id} in trial {trial_id}",
        )
    return result


@router.get(
    "/{trial_id}/enrollments",
    response_model=EnrollmentListResponse,
    summary="List trial enrollments",
    description="Get paginated list of patient enrollments for a trial.",
)
async def list_enrollments(
    trial_id: str,
    status: EnrollmentStatus | None = Query(None, description="Filter by enrollment status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> EnrollmentListResponse:
    """List enrollments for a trial."""
    service = get_trial_service()
    enrollments, total = service.get_enrollments(
        trial_id, status=status, limit=limit, offset=offset
    )
    return EnrollmentListResponse(
        enrollments=enrollments, total=total, offset=offset, limit=limit
    )


# ==============================================================================
# Dashboard
# ==============================================================================


@router.get(
    "/{trial_id}/dashboard",
    response_model=TrialDashboard,
    summary="Get trial enrollment dashboard",
    description="Get enrollment progress and status breakdown for a trial.",
)
async def get_trial_dashboard(trial_id: str) -> TrialDashboard:
    """Get enrollment dashboard for a trial."""
    service = get_trial_service()
    result = service.get_dashboard(trial_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return result
