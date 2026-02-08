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
    GET  /api/v1/trials/{id}/matches/{patient_id}/explanation - Per-match explainability
    POST /api/v1/trials/{id}/enroll  - Enroll a patient
    PUT  /api/v1/trials/{id}/enrollments/{patient_id} - Update enrollment
    GET  /api/v1/trials/{id}/enrollments - List enrollments
    POST /api/v1/trials/{id}/patients/{patient_id}/flag-fn - Flag false negative (CMO-6)
    GET  /api/v1/trials/{id}/fn-report - FN monitoring report (CMO-6)
    GET  /api/v1/trials/{id}/dashboard - Enrollment dashboard
    GET  /api/v1/trials/stats        - Service statistics
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
from app.schemas.fn_monitoring import FNFlagCreate, FNFlag, FNReport
from app.services.fn_monitoring_service import get_fn_monitoring_service
from app.services.match_explanation_service import MatchExplanationService
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
    session: AsyncSession = Depends(get_db),
) -> TrialListResponse:
    """List all clinical trials."""
    service = get_trial_service()
    trials, total = await service.list_trials(
        status=status,
        sponsor=sponsor,
        therapeutic_area=therapeutic_area,
        search=search,
        limit=limit,
        offset=offset,
        session=session,
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
async def get_trial_stats(session: AsyncSession = Depends(get_db)) -> dict:
    """Get trial service statistics."""
    service = get_trial_service()
    return await service.get_stats(session=session)


@router.get(
    "/{trial_id}",
    response_model=TrialResponse,
    summary="Get trial details",
    description="Get full details of a clinical trial including criteria and enrollment status.",
)
async def get_trial(trial_id: str, session: AsyncSession = Depends(get_db)) -> TrialResponse:
    """Get a trial by ID."""
    service = get_trial_service()
    trial = await service.get_trial(trial_id, session=session)
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
    session: AsyncSession = Depends(get_db),
) -> ScreeningResponse:
    """Screen patients against trial eligibility criteria."""
    service = get_trial_service()
    result = await service.screen_patients(trial_id, request, session=session)
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
    session: AsyncSession = Depends(get_db),
) -> PatientEligibility:
    """Check if a specific patient is eligible for a trial."""
    service = get_trial_service()
    result = await service.check_patient_eligibility(
        trial_id, patient_id, session=session
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return result


# ==============================================================================
# Per-Match Explainability (VP-Product-2)
# ==============================================================================


@router.get(
    "/{trial_id}/matches/{patient_id}/explanation",
    response_model=PatientEligibility,
    summary="Get per-match explainability for a patient-trial pair",
    description=(
        "Returns eligibility results enriched with per-criterion evidence summaries, "
        "source document references, and confidence explanations. "
        "Pharma RFP Tier 2 requirement."
    ),
)
async def get_match_explanation(
    trial_id: str,
    patient_id: str,
    session: AsyncSession = Depends(get_db),
) -> PatientEligibility:
    """Get per-match explainability for a patient-trial pair.

    Runs eligibility check and enriches each criterion result with:
    - evidence_summary: Plain-language explanation of why the criterion passed/failed
    - source_documents: Document IDs where the evidence was found
    - confidence_explanation: Why this confidence level was assigned
    """
    trial_service = get_trial_service()
    eligibility = await trial_service.check_patient_eligibility(
        trial_id, patient_id, session=session
    )
    if not eligibility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )

    explanation_service = MatchExplanationService()
    enriched = await explanation_service.enrich_eligibility(eligibility, session)
    return enriched


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
    session: AsyncSession = Depends(get_db),
) -> EnrollmentResponse:
    """Enroll a patient in a trial."""
    service = get_trial_service()
    result = await service.enroll_patient(trial_id, create, session=session)
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
# False Negative Monitoring (CMO-6)
# ==============================================================================


@router.post(
    "/{trial_id}/patients/{patient_id}/flag-fn",
    response_model=FNFlag,
    status_code=status.HTTP_201_CREATED,
    summary="Flag a potential false negative",
    description=(
        "A clinician flags a patient as potentially eligible despite the system "
        "marking them ineligible. This is a monitoring action -- it does NOT "
        "change the screening result. CMO-6: False Negative Monitoring."
    ),
)
async def flag_false_negative(
    trial_id: str,
    patient_id: str,
    body: FNFlagCreate,
    session: AsyncSession = Depends(get_db),
) -> FNFlag:
    """Flag a patient as a potential false negative for a trial."""
    # Verify trial exists
    trial_service = get_trial_service()
    trial = await trial_service.get_trial(trial_id, session=session)
    if not trial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )

    fn_service = get_fn_monitoring_service()
    flag = fn_service.flag_potential_false_negative(
        trial_id=trial_id,
        patient_id=patient_id,
        reason=body.reason,
        flagged_by=body.flagged_by,
    )
    logger.info(
        "FN flag created: trial=%s patient=%s by=%s",
        trial_id, patient_id, body.flagged_by,
    )
    return flag


@router.get(
    "/{trial_id}/fn-report",
    response_model=FNReport,
    summary="Get false negative monitoring report",
    description=(
        "Aggregated report of screening outcomes and potential false negatives "
        "for a trial. Includes FN rate, top miss reasons, and data completeness "
        "gaps. CMO-6: False Negative Monitoring."
    ),
)
async def get_fn_report(
    trial_id: str,
    session: AsyncSession = Depends(get_db),
) -> FNReport:
    """Get the false-negative monitoring report for a trial."""
    # Verify trial exists
    trial_service = get_trial_service()
    trial = await trial_service.get_trial(trial_id, session=session)
    if not trial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )

    fn_service = get_fn_monitoring_service()
    return fn_service.get_fn_report(trial_id)


# ==============================================================================
# Dashboard
# ==============================================================================


@router.get(
    "/{trial_id}/dashboard",
    response_model=TrialDashboard,
    summary="Get trial enrollment dashboard",
    description="Get enrollment progress and status breakdown for a trial.",
)
async def get_trial_dashboard(trial_id: str, session: AsyncSession = Depends(get_db)) -> TrialDashboard:
    """Get enrollment dashboard for a trial."""
    service = get_trial_service()
    result = await service.get_dashboard(trial_id, session=session)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return result
