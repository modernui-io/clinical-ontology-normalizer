"""Companion Diagnostics (CDx) Management API endpoints (CDx-MGMT).

Provides comprehensive CDx lifecycle operations: CDx registration and tracking,
biomarker-drug pairing, analytical/clinical validation studies, regulatory pathway
management, assay performance metrics, concordance analysis, and portfolio metrics.

Endpoints:
    GET    /companion-diagnostics/cdx                               - List companion diagnostics
    GET    /companion-diagnostics/cdx/{cdx_id}                      - Get single CDx
    POST   /companion-diagnostics/cdx                               - Create CDx
    PUT    /companion-diagnostics/cdx/{cdx_id}                      - Update CDx
    DELETE /companion-diagnostics/cdx/{cdx_id}                      - Delete CDx
    GET    /companion-diagnostics/studies                            - List validation studies
    GET    /companion-diagnostics/studies/{study_id}                 - Get single study
    POST   /companion-diagnostics/cdx/{cdx_id}/studies              - Create study for CDx
    PUT    /companion-diagnostics/studies/{study_id}                 - Update study
    DELETE /companion-diagnostics/studies/{study_id}                 - Delete study
    GET    /companion-diagnostics/metrics                            - Portfolio metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.companion_diagnostics import (
    BiomarkerType,
    CdxCreate,
    CdxListResponse,
    CdxMetrics,
    CdxStatus,
    CdxType,
    CdxUpdate,
    CdxValidationStudy,
    CdxValidationStudyCreate,
    CdxValidationStudyListResponse,
    CdxValidationStudyUpdate,
    CompanionDiagnostic,
    ValidationStudyStatus,
    ValidationStudyType,
)
from app.services.companion_diagnostics_service import (
    get_companion_diagnostics_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/companion-diagnostics",
    tags=["Companion Diagnostics"],
)


# ---------------------------------------------------------------------------
# CDx Management
# ---------------------------------------------------------------------------


@router.get(
    "/cdx",
    response_model=CdxListResponse,
    summary="List companion diagnostics",
    description="Retrieve companion diagnostics with optional filtering.",
)
async def list_cdx(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CdxStatus] = Query(None, description="Filter by lifecycle status"),
    cdx_type: Optional[CdxType] = Query(None, description="Filter by technology type"),
    biomarker_type: Optional[BiomarkerType] = Query(None, description="Filter by biomarker type"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
) -> CdxListResponse:
    svc = get_companion_diagnostics_service()
    items = svc.list_cdx(
        trial_id=trial_id,
        status=status,
        cdx_type=cdx_type,
        biomarker_type=biomarker_type,
        therapeutic_area=therapeutic_area,
    )
    return CdxListResponse(items=items, total=len(items))


@router.get(
    "/cdx/{cdx_id}",
    response_model=CompanionDiagnostic,
    summary="Get a companion diagnostic",
)
async def get_cdx(cdx_id: str) -> CompanionDiagnostic:
    svc = get_companion_diagnostics_service()
    cdx = svc.get_cdx(cdx_id)
    if cdx is None:
        raise HTTPException(status_code=404, detail=f"CDx '{cdx_id}' not found")
    return cdx


@router.post(
    "/cdx",
    response_model=CompanionDiagnostic,
    status_code=201,
    summary="Create a companion diagnostic",
)
async def create_cdx(payload: CdxCreate) -> CompanionDiagnostic:
    svc = get_companion_diagnostics_service()
    return svc.create_cdx(payload)


@router.put(
    "/cdx/{cdx_id}",
    response_model=CompanionDiagnostic,
    summary="Update a companion diagnostic",
)
async def update_cdx(cdx_id: str, payload: CdxUpdate) -> CompanionDiagnostic:
    svc = get_companion_diagnostics_service()
    updated = svc.update_cdx(cdx_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CDx '{cdx_id}' not found")
    return updated


@router.delete(
    "/cdx/{cdx_id}",
    status_code=204,
    summary="Delete a companion diagnostic",
)
async def delete_cdx(cdx_id: str) -> None:
    svc = get_companion_diagnostics_service()
    if not svc.delete_cdx(cdx_id):
        raise HTTPException(status_code=404, detail=f"CDx '{cdx_id}' not found")


# ---------------------------------------------------------------------------
# Validation Study Management
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=CdxValidationStudyListResponse,
    summary="List validation studies",
    description="Retrieve validation studies with optional filtering.",
)
async def list_studies(
    cdx_id: Optional[str] = Query(None, description="Filter by CDx ID"),
    study_type: Optional[ValidationStudyType] = Query(None, description="Filter by study type"),
    status: Optional[ValidationStudyStatus] = Query(None, description="Filter by study status"),
) -> CdxValidationStudyListResponse:
    svc = get_companion_diagnostics_service()
    items = svc.list_studies(
        cdx_id=cdx_id,
        study_type=study_type,
        status=status,
    )
    return CdxValidationStudyListResponse(items=items, total=len(items))


@router.get(
    "/studies/{study_id}",
    response_model=CdxValidationStudy,
    summary="Get a validation study",
)
async def get_study(study_id: str) -> CdxValidationStudy:
    svc = get_companion_diagnostics_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return study


@router.post(
    "/cdx/{cdx_id}/studies",
    response_model=CdxValidationStudy,
    status_code=201,
    summary="Create a validation study for a CDx",
)
async def create_study(
    cdx_id: str,
    payload: CdxValidationStudyCreate,
) -> CdxValidationStudy:
    svc = get_companion_diagnostics_service()
    study = svc.create_study(cdx_id, payload)
    if study is None:
        raise HTTPException(status_code=404, detail=f"CDx '{cdx_id}' not found")
    return study


@router.put(
    "/studies/{study_id}",
    response_model=CdxValidationStudy,
    summary="Update a validation study",
)
async def update_study(
    study_id: str, payload: CdxValidationStudyUpdate
) -> CdxValidationStudy:
    svc = get_companion_diagnostics_service()
    updated = svc.update_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return updated


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete a validation study",
)
async def delete_study(study_id: str) -> None:
    svc = get_companion_diagnostics_service()
    if not svc.delete_study(study_id):
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CdxMetrics,
    summary="CDx portfolio metrics",
    description="Aggregated companion diagnostics portfolio metrics with optional trial filter.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CdxMetrics:
    svc = get_companion_diagnostics_service()
    return svc.get_metrics(trial_id=trial_id)
