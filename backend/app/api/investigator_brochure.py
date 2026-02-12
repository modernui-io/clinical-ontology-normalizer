"""Investigator Brochure Management API endpoints (IB-MGMT).

Provides comprehensive investigator brochure management operations: IB version
tracking, safety update records, distribution management, revision history,
and acknowledgment records with compliance metrics.

Endpoints:
    GET    /investigator-brochure/ib-versions                            - List IB versions
    GET    /investigator-brochure/ib-versions/{version_id}               - Get single version
    POST   /investigator-brochure/ib-versions                            - Create version
    PUT    /investigator-brochure/ib-versions/{version_id}               - Update version
    DELETE /investigator-brochure/ib-versions/{version_id}               - Delete version
    GET    /investigator-brochure/safety-updates                         - List safety updates
    GET    /investigator-brochure/safety-updates/{update_id}             - Get single update
    POST   /investigator-brochure/safety-updates                         - Create update
    PUT    /investigator-brochure/safety-updates/{update_id}             - Update update
    DELETE /investigator-brochure/safety-updates/{update_id}             - Delete update
    GET    /investigator-brochure/distribution-records                   - List distributions
    GET    /investigator-brochure/distribution-records/{record_id}       - Get single distribution
    POST   /investigator-brochure/distribution-records                   - Create distribution
    PUT    /investigator-brochure/distribution-records/{record_id}       - Update distribution
    DELETE /investigator-brochure/distribution-records/{record_id}       - Delete distribution
    GET    /investigator-brochure/revision-histories                     - List revisions
    GET    /investigator-brochure/revision-histories/{revision_id}       - Get single revision
    POST   /investigator-brochure/revision-histories                     - Create revision
    PUT    /investigator-brochure/revision-histories/{revision_id}       - Update revision
    DELETE /investigator-brochure/revision-histories/{revision_id}       - Delete revision
    GET    /investigator-brochure/acknowledgment-records                 - List acknowledgments
    GET    /investigator-brochure/acknowledgment-records/{record_id}     - Get single acknowledgment
    POST   /investigator-brochure/acknowledgment-records                 - Create acknowledgment
    PUT    /investigator-brochure/acknowledgment-records/{record_id}     - Update acknowledgment
    DELETE /investigator-brochure/acknowledgment-records/{record_id}     - Delete acknowledgment
    GET    /investigator-brochure/metrics                                - IB metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.investigator_brochure import (
    AcknowledgmentRecord,
    AcknowledgmentRecordCreate,
    AcknowledgmentRecordListResponse,
    AcknowledgmentRecordUpdate,
    AcknowledgmentStatus,
    DistributionMethod,
    DistributionRecord,
    DistributionRecordCreate,
    DistributionRecordListResponse,
    DistributionRecordUpdate,
    IBStatus,
    IBVersion,
    IBVersionCreate,
    IBVersionListResponse,
    IBVersionUpdate,
    InvestigatorBrochureMetrics,
    RevisionHistory,
    RevisionHistoryCreate,
    RevisionHistoryListResponse,
    RevisionHistoryUpdate,
    RevisionScope,
    SafetyUpdate,
    SafetyUpdateCreate,
    SafetyUpdateListResponse,
    SafetyUpdateUpdate,
    UpdateType,
)
from app.services.investigator_brochure_service import get_investigator_brochure_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/investigator-brochure",
    tags=["Investigator Brochure"],
)


# ---------------------------------------------------------------------------
# IB Versions
# ---------------------------------------------------------------------------


@router.get(
    "/ib-versions",
    response_model=IBVersionListResponse,
    summary="List IB versions",
    description="Retrieve IB versions with optional filtering by trial and status.",
)
async def list_ib_versions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[IBStatus] = Query(None, description="Filter by IB status"),
) -> IBVersionListResponse:
    svc = get_investigator_brochure_service()
    items = svc.list_ib_versions(trial_id=trial_id, status=status)
    return IBVersionListResponse(items=items, total=len(items))


@router.get(
    "/ib-versions/{version_id}",
    response_model=IBVersion,
    summary="Get an IB version",
)
async def get_ib_version(version_id: str) -> IBVersion:
    svc = get_investigator_brochure_service()
    version = svc.get_ib_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"IB version '{version_id}' not found")
    return version


@router.post(
    "/ib-versions",
    response_model=IBVersion,
    status_code=201,
    summary="Create an IB version",
)
async def create_ib_version(payload: IBVersionCreate) -> IBVersion:
    svc = get_investigator_brochure_service()
    return svc.create_ib_version(payload)


@router.put(
    "/ib-versions/{version_id}",
    response_model=IBVersion,
    summary="Update an IB version",
)
async def update_ib_version(
    version_id: str, payload: IBVersionUpdate
) -> IBVersion:
    svc = get_investigator_brochure_service()
    updated = svc.update_ib_version(version_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"IB version '{version_id}' not found")
    return updated


@router.delete(
    "/ib-versions/{version_id}",
    status_code=204,
    summary="Delete an IB version",
)
async def delete_ib_version(version_id: str) -> None:
    svc = get_investigator_brochure_service()
    deleted = svc.delete_ib_version(version_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"IB version '{version_id}' not found")


# ---------------------------------------------------------------------------
# Safety Updates
# ---------------------------------------------------------------------------


@router.get(
    "/safety-updates",
    response_model=SafetyUpdateListResponse,
    summary="List safety updates",
    description="Retrieve safety updates with optional filtering by trial and update type.",
)
async def list_safety_updates(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    update_type: Optional[UpdateType] = Query(None, description="Filter by update type"),
) -> SafetyUpdateListResponse:
    svc = get_investigator_brochure_service()
    items = svc.list_safety_updates(trial_id=trial_id, update_type=update_type)
    return SafetyUpdateListResponse(items=items, total=len(items))


@router.get(
    "/safety-updates/{update_id}",
    response_model=SafetyUpdate,
    summary="Get a safety update",
)
async def get_safety_update(update_id: str) -> SafetyUpdate:
    svc = get_investigator_brochure_service()
    update = svc.get_safety_update(update_id)
    if update is None:
        raise HTTPException(status_code=404, detail=f"Safety update '{update_id}' not found")
    return update


@router.post(
    "/safety-updates",
    response_model=SafetyUpdate,
    status_code=201,
    summary="Create a safety update",
)
async def create_safety_update(payload: SafetyUpdateCreate) -> SafetyUpdate:
    svc = get_investigator_brochure_service()
    return svc.create_safety_update(payload)


@router.put(
    "/safety-updates/{update_id}",
    response_model=SafetyUpdate,
    summary="Update a safety update",
)
async def update_safety_update(
    update_id: str, payload: SafetyUpdateUpdate
) -> SafetyUpdate:
    svc = get_investigator_brochure_service()
    updated = svc.update_safety_update(update_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Safety update '{update_id}' not found")
    return updated


@router.delete(
    "/safety-updates/{update_id}",
    status_code=204,
    summary="Delete a safety update",
)
async def delete_safety_update(update_id: str) -> None:
    svc = get_investigator_brochure_service()
    deleted = svc.delete_safety_update(update_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Safety update '{update_id}' not found")


# ---------------------------------------------------------------------------
# Distribution Records
# ---------------------------------------------------------------------------


@router.get(
    "/distribution-records",
    response_model=DistributionRecordListResponse,
    summary="List distribution records",
    description="Retrieve distribution records with optional filtering by trial and method.",
)
async def list_distribution_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    distribution_method: Optional[DistributionMethod] = Query(
        None, description="Filter by distribution method"
    ),
) -> DistributionRecordListResponse:
    svc = get_investigator_brochure_service()
    items = svc.list_distribution_records(
        trial_id=trial_id, distribution_method=distribution_method
    )
    return DistributionRecordListResponse(items=items, total=len(items))


@router.get(
    "/distribution-records/{record_id}",
    response_model=DistributionRecord,
    summary="Get a distribution record",
)
async def get_distribution_record(record_id: str) -> DistributionRecord:
    svc = get_investigator_brochure_service()
    record = svc.get_distribution_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Distribution record '{record_id}' not found"
        )
    return record


@router.post(
    "/distribution-records",
    response_model=DistributionRecord,
    status_code=201,
    summary="Create a distribution record",
)
async def create_distribution_record(payload: DistributionRecordCreate) -> DistributionRecord:
    svc = get_investigator_brochure_service()
    return svc.create_distribution_record(payload)


@router.put(
    "/distribution-records/{record_id}",
    response_model=DistributionRecord,
    summary="Update a distribution record",
)
async def update_distribution_record(
    record_id: str, payload: DistributionRecordUpdate
) -> DistributionRecord:
    svc = get_investigator_brochure_service()
    updated = svc.update_distribution_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Distribution record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/distribution-records/{record_id}",
    status_code=204,
    summary="Delete a distribution record",
)
async def delete_distribution_record(record_id: str) -> None:
    svc = get_investigator_brochure_service()
    deleted = svc.delete_distribution_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Distribution record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Revision Histories
# ---------------------------------------------------------------------------


@router.get(
    "/revision-histories",
    response_model=RevisionHistoryListResponse,
    summary="List revision histories",
    description="Retrieve revision histories with optional filtering by trial and scope.",
)
async def list_revision_histories(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    revision_scope: Optional[RevisionScope] = Query(None, description="Filter by revision scope"),
) -> RevisionHistoryListResponse:
    svc = get_investigator_brochure_service()
    items = svc.list_revision_histories(trial_id=trial_id, revision_scope=revision_scope)
    return RevisionHistoryListResponse(items=items, total=len(items))


@router.get(
    "/revision-histories/{revision_id}",
    response_model=RevisionHistory,
    summary="Get a revision history entry",
)
async def get_revision_history(revision_id: str) -> RevisionHistory:
    svc = get_investigator_brochure_service()
    revision = svc.get_revision_history(revision_id)
    if revision is None:
        raise HTTPException(
            status_code=404, detail=f"Revision history '{revision_id}' not found"
        )
    return revision


@router.post(
    "/revision-histories",
    response_model=RevisionHistory,
    status_code=201,
    summary="Create a revision history entry",
)
async def create_revision_history(payload: RevisionHistoryCreate) -> RevisionHistory:
    svc = get_investigator_brochure_service()
    return svc.create_revision_history(payload)


@router.put(
    "/revision-histories/{revision_id}",
    response_model=RevisionHistory,
    summary="Update a revision history entry",
)
async def update_revision_history(
    revision_id: str, payload: RevisionHistoryUpdate
) -> RevisionHistory:
    svc = get_investigator_brochure_service()
    updated = svc.update_revision_history(revision_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Revision history '{revision_id}' not found"
        )
    return updated


@router.delete(
    "/revision-histories/{revision_id}",
    status_code=204,
    summary="Delete a revision history entry",
)
async def delete_revision_history(revision_id: str) -> None:
    svc = get_investigator_brochure_service()
    deleted = svc.delete_revision_history(revision_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Revision history '{revision_id}' not found"
        )


# ---------------------------------------------------------------------------
# Acknowledgment Records
# ---------------------------------------------------------------------------


@router.get(
    "/acknowledgment-records",
    response_model=AcknowledgmentRecordListResponse,
    summary="List acknowledgment records",
    description="Retrieve acknowledgment records with optional filtering by trial and status.",
)
async def list_acknowledgment_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AcknowledgmentStatus] = Query(None, description="Filter by status"),
) -> AcknowledgmentRecordListResponse:
    svc = get_investigator_brochure_service()
    items = svc.list_acknowledgment_records(trial_id=trial_id, status=status)
    return AcknowledgmentRecordListResponse(items=items, total=len(items))


@router.get(
    "/acknowledgment-records/{record_id}",
    response_model=AcknowledgmentRecord,
    summary="Get an acknowledgment record",
)
async def get_acknowledgment_record(record_id: str) -> AcknowledgmentRecord:
    svc = get_investigator_brochure_service()
    record = svc.get_acknowledgment_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Acknowledgment record '{record_id}' not found"
        )
    return record


@router.post(
    "/acknowledgment-records",
    response_model=AcknowledgmentRecord,
    status_code=201,
    summary="Create an acknowledgment record",
)
async def create_acknowledgment_record(
    payload: AcknowledgmentRecordCreate,
) -> AcknowledgmentRecord:
    svc = get_investigator_brochure_service()
    return svc.create_acknowledgment_record(payload)


@router.put(
    "/acknowledgment-records/{record_id}",
    response_model=AcknowledgmentRecord,
    summary="Update an acknowledgment record",
)
async def update_acknowledgment_record(
    record_id: str, payload: AcknowledgmentRecordUpdate
) -> AcknowledgmentRecord:
    svc = get_investigator_brochure_service()
    updated = svc.update_acknowledgment_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Acknowledgment record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/acknowledgment-records/{record_id}",
    status_code=204,
    summary="Delete an acknowledgment record",
)
async def delete_acknowledgment_record(record_id: str) -> None:
    svc = get_investigator_brochure_service()
    deleted = svc.delete_acknowledgment_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Acknowledgment record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InvestigatorBrochureMetrics,
    summary="Get investigator brochure metrics",
    description="Aggregated metrics across all investigator brochure operations.",
)
async def get_metrics() -> InvestigatorBrochureMetrics:
    svc = get_investigator_brochure_service()
    return svc.get_metrics()
