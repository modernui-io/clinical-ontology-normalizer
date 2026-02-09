"""Medidata Rave EDC Integration API Endpoints.

Endpoints for integrating with Medidata Rave Electronic Data Capture:
    - Connection testing
    - Study listing and import
    - Screening result push
    - Enrollment status sync
    - Integration status dashboard

All endpoints work in demo mode when Rave credentials are not configured.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.schemas.medidata_rave import (
    RaveConnectionTestResponse,
    RaveEnrollmentSyncResponse,
    RaveIntegrationStatus,
    RaveScreeningPushRequest,
    RaveScreeningPushResponse,
    RaveStudyImportRequest,
    RaveStudyImportResponse,
    RaveStudyListResponse,
    RaveStudySummary,
    RaveSubjectListResponse,
    RaveSubject,
    ScreeningPushResult,
    EnrollmentStatusUpdate,
    RaveCriterionMapping,
)
from app.services.medidata_rave_service import (
    MedidataRaveError,
    MedidataRaveService,
    get_medidata_rave_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medidata-rave", tags=["Medidata Rave Integration"])


# ==============================================================================
# Connection
# ==============================================================================


@router.post(
    "/connection/test",
    response_model=RaveConnectionTestResponse,
    summary="Test Rave connectivity",
    description="Verify connectivity to the configured Medidata Rave instance.",
)
async def test_connection() -> RaveConnectionTestResponse:
    """Test connection to Medidata Rave Web Services."""
    service = get_medidata_rave_service()
    try:
        result = await service.test_connection()
        return RaveConnectionTestResponse(**result)
    except Exception as e:
        logger.error("Rave connection test failed: %s", e)
        return RaveConnectionTestResponse(
            connected=False,
            error=str(e),
            demo_mode=service.demo_mode,
        )


# ==============================================================================
# Studies
# ==============================================================================


@router.get(
    "/studies",
    response_model=RaveStudyListResponse,
    summary="List Rave studies",
    description="List available studies from the Medidata Rave instance.",
)
async def list_studies() -> RaveStudyListResponse:
    """List all accessible studies in Rave."""
    service = get_medidata_rave_service()
    try:
        studies_data = await service.list_studies()
        studies = [RaveStudySummary(**s) for s in studies_data]
        return RaveStudyListResponse(
            studies=studies,
            total_count=len(studies),
            demo_mode=service.demo_mode,
        )
    except MedidataRaveError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list Rave studies: {e}",
        ) from e


@router.post(
    "/studies/{study_oid}/import",
    response_model=RaveStudyImportResponse,
    summary="Import study from Rave",
    description="Import a study definition from Rave and create a trial record with eligibility criteria.",
)
async def import_study(
    study_oid: str,
    request: RaveStudyImportRequest | None = None,
) -> RaveStudyImportResponse:
    """Import study definition from Rave via CDISC ODM."""
    service = get_medidata_rave_service()
    environment = request.environment.value if request else "Prod"

    try:
        result = await service.import_study(study_oid, environment)

        criteria = [
            RaveCriterionMapping(**c) for c in result.get("criteria", [])
        ]

        return RaveStudyImportResponse(
            trial_id=result.get("trial_id"),
            study_oid=result["study_oid"],
            study_name=result["study_name"],
            criteria_count=result["criteria_count"],
            criteria=criteria,
            forms_count=result.get("forms_count", 0),
            mapping_summary=result.get("mapping_summary", {}),
            demo_mode=result.get("demo_mode", service.demo_mode),
        )
    except MedidataRaveError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to import study {study_oid}: {e}",
        ) from e


@router.get(
    "/studies/{study_oid}/subjects",
    response_model=RaveSubjectListResponse,
    summary="List study subjects",
    description="List subjects enrolled in a Rave study.",
)
async def list_study_subjects(
    study_oid: str,
    environment: str = "Prod",
) -> RaveSubjectListResponse:
    """Get subjects for a study in Rave."""
    service = get_medidata_rave_service()
    try:
        subjects_data = await service.get_study_subjects(study_oid, environment)
        subjects = [RaveSubject(**s) for s in subjects_data]
        return RaveSubjectListResponse(
            subjects=subjects,
            total_count=len(subjects),
            demo_mode=service.demo_mode,
        )
    except MedidataRaveError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list subjects for {study_oid}: {e}",
        ) from e


# ==============================================================================
# Screening
# ==============================================================================


@router.post(
    "/screening/push",
    response_model=RaveScreeningPushResponse,
    summary="Push screening results to Rave",
    description="Push patient screening results to Rave as clinical data.",
)
async def push_screening_results(
    request: RaveScreeningPushRequest,
) -> RaveScreeningPushResponse:
    """Push screening results for one or more patients to Rave."""
    service = get_medidata_rave_service()
    results: list[ScreeningPushResult] = []
    pushed = 0
    failed = 0

    for patient_id in request.patient_ids:
        try:
            result = await service.push_screening_result(
                trial_id=request.trial_id,
                patient_id=patient_id,
                eligibility_result={"criteria_results": []},
            )
            success = result.get("success", False)
            results.append(ScreeningPushResult(
                patient_id=patient_id,
                success=success,
                rave_subject_key=result.get("rave_subject_key"),
                error=result.get("error"),
            ))
            if success:
                pushed += 1
            else:
                failed += 1
        except MedidataRaveError as e:
            results.append(ScreeningPushResult(
                patient_id=patient_id,
                success=False,
                error=str(e),
            ))
            failed += 1

    return RaveScreeningPushResponse(
        pushed_count=pushed,
        failed_count=failed,
        results=results,
        demo_mode=service.demo_mode,
    )


# ==============================================================================
# Enrollment
# ==============================================================================


@router.post(
    "/enrollment/sync",
    response_model=RaveEnrollmentSyncResponse,
    summary="Sync enrollment status",
    description="Sync enrollment status updates from Rave for a trial.",
)
async def sync_enrollment(
    trial_id: str = "",
) -> RaveEnrollmentSyncResponse:
    """Sync enrollment status from Rave."""
    service = get_medidata_rave_service()
    try:
        result = await service.sync_enrollment_status(trial_id)
        updates = [
            EnrollmentStatusUpdate(**u) for u in result.get("status_updates", [])
        ]
        return RaveEnrollmentSyncResponse(
            synced_count=result.get("synced_count", 0),
            status_updates=updates,
            demo_mode=result.get("demo_mode", service.demo_mode),
        )
    except MedidataRaveError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync enrollment: {e}",
        ) from e


# ==============================================================================
# Integration Status
# ==============================================================================


@router.get(
    "/status",
    response_model=RaveIntegrationStatus,
    summary="Integration status",
    description="Get Medidata Rave integration status and configuration summary.",
)
async def get_integration_status() -> RaveIntegrationStatus:
    """Get current Rave integration status."""
    service = get_medidata_rave_service()
    return RaveIntegrationStatus(
        configured=not service.demo_mode,
        demo_mode=service.demo_mode,
        base_url=service._base_url if not service.demo_mode else None,
        last_sync=None,
        studies_imported=0,
        screenings_pushed=0,
        active_syncs=0,
    )
