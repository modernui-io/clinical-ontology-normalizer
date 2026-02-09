"""Veeva Vault CDMS Integration API Endpoints.

Endpoints for integrating with Veeva Vault Clinical Data Management Suite:
    - Connection testing
    - Study listing and import
    - Screening result push
    - Enrollment status sync
    - Integration status dashboard

All endpoints work in demo mode when Vault credentials are not configured.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.veeva_vault import (
    VeevaConnectionTestResponse,
    VeevaCriterionMapping,
    VeevaEnrollmentStatusUpdate,
    VeevaEnrollmentSyncResponse,
    VeevaIntegrationStatus,
    VeevaScreeningPushRequest,
    VeevaScreeningPushResponse,
    VeevaScreeningPushResult,
    VeevaStudyImportRequest,
    VeevaStudyImportResponse,
    VeevaStudyListResponse,
    VeevaStudySummary,
    VeevaSubject,
    VeevaSubjectListResponse,
)
from app.services.veeva_vault_service import (
    VeevaVaultError,
    VeevaVaultService,
    get_veeva_vault_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/veeva-vault", tags=["Veeva Vault CDMS Integration"])


# ==============================================================================
# Connection
# ==============================================================================


@router.post(
    "/connection/test",
    response_model=VeevaConnectionTestResponse,
    summary="Test Vault connectivity",
    description="Verify connectivity to the configured Veeva Vault CDMS instance.",
)
async def test_connection() -> VeevaConnectionTestResponse:
    """Test connection to Veeva Vault CDMS."""
    service = get_veeva_vault_service()
    try:
        result = await service.test_connection()
        return VeevaConnectionTestResponse(**result)
    except Exception as e:
        logger.error("Vault connection test failed: %s", e)
        return VeevaConnectionTestResponse(
            connected=False,
            error=str(e),
            demo_mode=service.demo_mode,
        )


# ==============================================================================
# Studies
# ==============================================================================


@router.get(
    "/studies",
    response_model=VeevaStudyListResponse,
    summary="List Vault studies",
    description="List available studies from the Veeva Vault CDMS instance.",
)
async def list_studies() -> VeevaStudyListResponse:
    """List all accessible studies in Vault CDMS."""
    service = get_veeva_vault_service()
    try:
        studies_data = await service.list_studies()
        studies = [VeevaStudySummary(**s) for s in studies_data]
        return VeevaStudyListResponse(
            studies=studies,
            total_count=len(studies),
            demo_mode=service.demo_mode,
        )
    except VeevaVaultError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list Vault studies: {e}",
        ) from e


@router.post(
    "/studies/{study_name}/import",
    response_model=VeevaStudyImportResponse,
    summary="Import study from Vault",
    description="Import a study definition from Vault CDMS and create a trial record with eligibility criteria.",
)
async def import_study(
    study_name: str,
    request: VeevaStudyImportRequest | None = None,
) -> VeevaStudyImportResponse:
    """Import study definition from Vault CDMS."""
    service = get_veeva_vault_service()

    try:
        result = await service.import_study(study_name)

        criteria = [
            VeevaCriterionMapping(**c) for c in result.get("criteria", [])
        ]

        return VeevaStudyImportResponse(
            trial_id=result.get("trial_id"),
            study_name=result["study_name"],
            study_title=result.get("study_title", ""),
            criteria_count=result["criteria_count"],
            criteria=criteria,
            forms_count=result.get("forms_count", 0),
            mapping_summary=result.get("mapping_summary", {}),
            demo_mode=result.get("demo_mode", service.demo_mode),
        )
    except VeevaVaultError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to import study {study_name}: {e}",
        ) from e


@router.get(
    "/studies/{study_name}/subjects",
    response_model=VeevaSubjectListResponse,
    summary="List study subjects",
    description="List subjects in a Vault CDMS study.",
)
async def list_study_subjects(
    study_name: str,
) -> VeevaSubjectListResponse:
    """Get subjects for a study in Vault CDMS."""
    service = get_veeva_vault_service()
    try:
        subjects_data = await service.list_subjects(study_name)
        subjects = [VeevaSubject(**s) for s in subjects_data]
        return VeevaSubjectListResponse(
            subjects=subjects,
            total_count=len(subjects),
            demo_mode=service.demo_mode,
        )
    except VeevaVaultError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list subjects for {study_name}: {e}",
        ) from e


# ==============================================================================
# Screening
# ==============================================================================


@router.post(
    "/screening/push",
    response_model=VeevaScreeningPushResponse,
    summary="Push screening results to Vault",
    description="Push patient screening results to Vault CDMS as clinical data.",
)
async def push_screening_results(
    request: VeevaScreeningPushRequest,
) -> VeevaScreeningPushResponse:
    """Push screening results for one or more patients to Vault CDMS."""
    service = get_veeva_vault_service()
    results: list[VeevaScreeningPushResult] = []
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
            results.append(VeevaScreeningPushResult(
                patient_id=patient_id,
                success=success,
                vault_subject_id=result.get("vault_subject_id"),
                error=result.get("error"),
            ))
            if success:
                pushed += 1
            else:
                failed += 1
        except VeevaVaultError as e:
            results.append(VeevaScreeningPushResult(
                patient_id=patient_id,
                success=False,
                error=str(e),
            ))
            failed += 1

    return VeevaScreeningPushResponse(
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
    response_model=VeevaEnrollmentSyncResponse,
    summary="Sync enrollment status",
    description="Sync enrollment status updates from Vault CDMS for a trial.",
)
async def sync_enrollment(
    trial_id: str = "",
) -> VeevaEnrollmentSyncResponse:
    """Sync enrollment status from Vault CDMS."""
    service = get_veeva_vault_service()
    try:
        result = await service.sync_enrollment_status(trial_id)
        updates = [
            VeevaEnrollmentStatusUpdate(**u) for u in result.get("status_updates", [])
        ]
        return VeevaEnrollmentSyncResponse(
            synced_count=result.get("synced_count", 0),
            status_updates=updates,
            demo_mode=result.get("demo_mode", service.demo_mode),
        )
    except VeevaVaultError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync enrollment: {e}",
        ) from e


# ==============================================================================
# Integration Status
# ==============================================================================


@router.get(
    "/status",
    response_model=VeevaIntegrationStatus,
    summary="Integration status",
    description="Get Veeva Vault CDMS integration status and configuration summary.",
)
async def get_integration_status() -> VeevaIntegrationStatus:
    """Get current Vault CDMS integration status."""
    service = get_veeva_vault_service()
    return VeevaIntegrationStatus(
        configured=not service.demo_mode,
        demo_mode=service.demo_mode,
        vault_url=service._vault_url if not service.demo_mode else None,
        last_sync=None,
        studies_imported=0,
        screenings_pushed=0,
        active_syncs=0,
    )
