"""Biospecimen & Biobank Management API endpoints (CLINICAL-17).

Provides comprehensive biobank operations: specimen collection registration,
aliquot tracking with chain of custody, biorepository management with capacity
monitoring, consent scope validation, quality scoring, specimen genealogy,
shipment manifests, and biobank operational metrics.

Endpoints:
    GET    /biobank/specimens                                   - List specimens
    GET    /biobank/specimens/{specimen_id}                     - Get single specimen
    POST   /biobank/specimens                                   - Register specimen
    PUT    /biobank/specimens/{specimen_id}                     - Update specimen
    DELETE /biobank/specimens/{specimen_id}                     - Delete specimen
    GET    /biobank/specimens/{specimen_id}/genealogy           - Specimen genealogy
    GET    /biobank/aliquots                                    - List aliquots
    GET    /biobank/aliquots/{aliquot_id}                       - Get single aliquot
    POST   /biobank/aliquots                                    - Create aliquot
    PUT    /biobank/aliquots/{aliquot_id}                       - Update aliquot
    POST   /biobank/aliquots/{aliquot_id}/reserve               - Reserve aliquot
    POST   /biobank/aliquots/{aliquot_id}/freeze-thaw           - Record freeze-thaw
    GET    /biobank/repositories                                - List repositories
    GET    /biobank/repositories/{repository_id}                - Get single repository
    POST   /biobank/repositories                                - Create repository
    PUT    /biobank/repositories/{repository_id}                - Update repository
    DELETE /biobank/repositories/{repository_id}                - Delete repository
    GET    /biobank/storage-alerts                               - Get storage capacity alerts
    GET    /biobank/consents                                    - List consent records
    GET    /biobank/consents/{consent_id}                       - Get single consent
    POST   /biobank/consents                                    - Create consent record
    POST   /biobank/consents/{consent_id}/withdraw              - Withdraw consent
    POST   /biobank/consents/validate                           - Validate consent scopes
    GET    /biobank/shipments                                   - List shipments
    GET    /biobank/shipments/{shipment_id}                     - Get single shipment
    POST   /biobank/shipments                                   - Create shipment
    POST   /biobank/shipments/{shipment_id}/receive             - Receive shipment
    GET    /biobank/metrics                                     - Biobank dashboard metrics
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.biobank_management import (
    Aliquot,
    AliquotCreate,
    AliquotListResponse,
    AliquotReserve,
    AliquotStatus,
    AliquotUpdate,
    BiobankMetrics,
    Biorepository,
    BiorepositoryCreate,
    BiorepositoryListResponse,
    BiorepositoryType,
    BiorepositoryUpdate,
    BiospecimenCollection,
    ConsentCreate,
    ConsentListResponse,
    ConsentRecord,
    ConsentScope,
    ConsentWithdraw,
    ShipmentCreate,
    ShipmentListResponse,
    ShipmentManifest,
    ShipmentReceive,
    SpecimenCreate,
    SpecimenGenealogy,
    SpecimenListResponse,
    SpecimenType,
    SpecimenUpdate,
    StorageCapacityAlert,
    StorageType,
)
from app.services.biobank_management_service import get_biobank_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/biobank",
    tags=["Biobank Management"],
)


# ---------------------------------------------------------------------------
# Specimen Management
# ---------------------------------------------------------------------------


@router.get(
    "/specimens",
    response_model=SpecimenListResponse,
    summary="List biospecimen collections",
    description="Retrieve specimens with optional filtering by patient, trial, site, and specimen type.",
)
async def list_specimens(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    specimen_type: Optional[SpecimenType] = Query(None, description="Filter by specimen type"),
) -> SpecimenListResponse:
    svc = get_biobank_service()
    items = svc.list_specimens(
        patient_id=patient_id, trial_id=trial_id,
        site_id=site_id, specimen_type=specimen_type,
    )
    return SpecimenListResponse(items=items, total=len(items))


@router.get(
    "/specimens/{specimen_id}",
    response_model=BiospecimenCollection,
    summary="Get a biospecimen collection",
)
async def get_specimen(specimen_id: str) -> BiospecimenCollection:
    svc = get_biobank_service()
    specimen = svc.get_specimen(specimen_id)
    if specimen is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return specimen


@router.post(
    "/specimens",
    response_model=BiospecimenCollection,
    status_code=201,
    summary="Register a biospecimen collection",
)
async def create_specimen(payload: SpecimenCreate) -> BiospecimenCollection:
    svc = get_biobank_service()
    return svc.create_specimen(payload)


@router.put(
    "/specimens/{specimen_id}",
    response_model=BiospecimenCollection,
    summary="Update a specimen record",
)
async def update_specimen(
    specimen_id: str, payload: SpecimenUpdate
) -> BiospecimenCollection:
    svc = get_biobank_service()
    updated = svc.update_specimen(specimen_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return updated


@router.delete(
    "/specimens/{specimen_id}",
    status_code=204,
    summary="Delete a specimen record",
)
async def delete_specimen(specimen_id: str) -> None:
    svc = get_biobank_service()
    deleted = svc.delete_specimen(specimen_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")


@router.get(
    "/specimens/{specimen_id}/genealogy",
    response_model=SpecimenGenealogy,
    summary="Get specimen genealogy",
    description="Retrieve the genealogy tree for a specimen showing aliquots and child specimens.",
)
async def get_specimen_genealogy(specimen_id: str) -> SpecimenGenealogy:
    svc = get_biobank_service()
    genealogy = svc.get_specimen_genealogy(specimen_id)
    if genealogy is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return genealogy


# ---------------------------------------------------------------------------
# Aliquot Management
# ---------------------------------------------------------------------------


@router.get(
    "/aliquots",
    response_model=AliquotListResponse,
    summary="List aliquots",
    description="Retrieve aliquots with optional filtering by specimen, status, storage type.",
)
async def list_aliquots(
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
    status: Optional[AliquotStatus] = Query(None, description="Filter by status"),
    storage_type: Optional[StorageType] = Query(None, description="Filter by storage type"),
) -> AliquotListResponse:
    svc = get_biobank_service()
    items = svc.list_aliquots(
        specimen_id=specimen_id, status=status, storage_type=storage_type,
    )
    return AliquotListResponse(items=items, total=len(items))


@router.get(
    "/aliquots/{aliquot_id}",
    response_model=Aliquot,
    summary="Get an aliquot",
)
async def get_aliquot(aliquot_id: str) -> Aliquot:
    svc = get_biobank_service()
    aliquot = svc.get_aliquot(aliquot_id)
    if aliquot is None:
        raise HTTPException(status_code=404, detail=f"Aliquot '{aliquot_id}' not found")
    return aliquot


@router.post(
    "/aliquots",
    response_model=Aliquot,
    status_code=201,
    summary="Create an aliquot from a specimen",
)
async def create_aliquot(payload: AliquotCreate) -> Aliquot:
    svc = get_biobank_service()
    try:
        return svc.create_aliquot(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/aliquots/{aliquot_id}",
    response_model=Aliquot,
    summary="Update an aliquot",
)
async def update_aliquot(aliquot_id: str, payload: AliquotUpdate) -> Aliquot:
    svc = get_biobank_service()
    updated = svc.update_aliquot(aliquot_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Aliquot '{aliquot_id}' not found")
    return updated


@router.post(
    "/aliquots/{aliquot_id}/reserve",
    response_model=Aliquot,
    summary="Reserve an aliquot",
    description="Reserve an aliquot for use after validating consent scopes.",
)
async def reserve_aliquot(aliquot_id: str, payload: AliquotReserve) -> Aliquot:
    svc = get_biobank_service()
    try:
        result = svc.reserve_aliquot(aliquot_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aliquot '{aliquot_id}' not found")
    return result


@router.post(
    "/aliquots/{aliquot_id}/freeze-thaw",
    response_model=Aliquot,
    summary="Record a freeze-thaw cycle",
    description="Record a freeze-thaw cycle for an aliquot. Automatically recalculates quality score.",
)
async def record_freeze_thaw(aliquot_id: str) -> Aliquot:
    svc = get_biobank_service()
    result = svc.record_freeze_thaw(aliquot_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aliquot '{aliquot_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Biorepository Management
# ---------------------------------------------------------------------------


@router.get(
    "/repositories",
    response_model=BiorepositoryListResponse,
    summary="List biorepositories",
    description="Retrieve biorepositories with optional filtering by type.",
)
async def list_repositories(
    repo_type: Optional[BiorepositoryType] = Query(None, alias="type", description="Filter by repository type"),
) -> BiorepositoryListResponse:
    svc = get_biobank_service()
    items = svc.list_repositories(repo_type=repo_type)
    return BiorepositoryListResponse(items=items, total=len(items))


@router.get(
    "/repositories/{repository_id}",
    response_model=Biorepository,
    summary="Get a biorepository",
)
async def get_repository(repository_id: str) -> Biorepository:
    svc = get_biobank_service()
    repo = svc.get_repository(repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")
    return repo


@router.post(
    "/repositories",
    response_model=Biorepository,
    status_code=201,
    summary="Register a biorepository",
)
async def create_repository(payload: BiorepositoryCreate) -> Biorepository:
    svc = get_biobank_service()
    return svc.create_repository(payload)


@router.put(
    "/repositories/{repository_id}",
    response_model=Biorepository,
    summary="Update a biorepository",
)
async def update_repository(
    repository_id: str, payload: BiorepositoryUpdate
) -> Biorepository:
    svc = get_biobank_service()
    updated = svc.update_repository(repository_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")
    return updated


@router.delete(
    "/repositories/{repository_id}",
    status_code=204,
    summary="Delete a biorepository",
)
async def delete_repository(repository_id: str) -> None:
    svc = get_biobank_service()
    deleted = svc.delete_repository(repository_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")


@router.get(
    "/storage-alerts",
    response_model=list[StorageCapacityAlert],
    summary="Get storage capacity alerts",
    description="Retrieve alerts for biorepositories at 80%+ utilization.",
)
async def get_storage_alerts() -> list[StorageCapacityAlert]:
    svc = get_biobank_service()
    return svc.get_storage_alerts()


# ---------------------------------------------------------------------------
# Consent Management
# ---------------------------------------------------------------------------


@router.get(
    "/consents",
    response_model=ConsentListResponse,
    summary="List consent records",
    description="Retrieve consent records with optional filtering by patient, specimen, and active status.",
)
async def list_consents(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
    active_only: Optional[bool] = Query(False, description="Only return active (non-withdrawn) consents"),
) -> ConsentListResponse:
    svc = get_biobank_service()
    items = svc.list_consents(
        patient_id=patient_id, specimen_id=specimen_id, active_only=active_only or False,
    )
    return ConsentListResponse(items=items, total=len(items))


@router.get(
    "/consents/{consent_id}",
    response_model=ConsentRecord,
    summary="Get a consent record",
)
async def get_consent(consent_id: str) -> ConsentRecord:
    svc = get_biobank_service()
    consent = svc.get_consent(consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return consent


@router.post(
    "/consents",
    response_model=ConsentRecord,
    status_code=201,
    summary="Create a consent record",
)
async def create_consent(payload: ConsentCreate) -> ConsentRecord:
    svc = get_biobank_service()
    return svc.create_consent(payload)


@router.post(
    "/consents/{consent_id}/withdraw",
    response_model=ConsentRecord,
    summary="Withdraw consent",
    description="Withdraw a consent record. Withdrawn consents cannot be used for specimen release.",
)
async def withdraw_consent(
    consent_id: str, payload: ConsentWithdraw
) -> ConsentRecord:
    svc = get_biobank_service()
    try:
        result = svc.withdraw_consent(consent_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return result


@router.post(
    "/consents/validate",
    response_model=dict[str, Any],
    summary="Validate consent scopes",
    description="Check whether a patient has the required consent scopes for a specimen.",
)
async def validate_consent_scopes(
    patient_id: str = Query(..., description="Patient ID"),
    specimen_id: str = Query(..., description="Specimen ID"),
    required_scopes: list[ConsentScope] = Query(..., description="Required consent scopes"),
) -> dict[str, Any]:
    svc = get_biobank_service()
    return svc.validate_consent_scopes(patient_id, specimen_id, required_scopes)


# ---------------------------------------------------------------------------
# Shipment Management
# ---------------------------------------------------------------------------


@router.get(
    "/shipments",
    response_model=ShipmentListResponse,
    summary="List shipment manifests",
    description="Retrieve shipment manifests with optional in-transit filter.",
)
async def list_shipments(
    in_transit_only: Optional[bool] = Query(False, description="Only return in-transit shipments"),
) -> ShipmentListResponse:
    svc = get_biobank_service()
    items = svc.list_shipments(in_transit_only=in_transit_only or False)
    return ShipmentListResponse(items=items, total=len(items))


@router.get(
    "/shipments/{shipment_id}",
    response_model=ShipmentManifest,
    summary="Get a shipment manifest",
)
async def get_shipment(shipment_id: str) -> ShipmentManifest:
    svc = get_biobank_service()
    shipment = svc.get_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return shipment


@router.post(
    "/shipments",
    response_model=ShipmentManifest,
    status_code=201,
    summary="Create a shipment manifest",
    description="Create a shipment and mark aliquots as shipped.",
)
async def create_shipment(payload: ShipmentCreate) -> ShipmentManifest:
    svc = get_biobank_service()
    try:
        return svc.create_shipment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/shipments/{shipment_id}/receive",
    response_model=ShipmentManifest,
    summary="Receive a shipment",
    description="Mark a shipment as received with condition assessment and temperature log.",
)
async def receive_shipment(
    shipment_id: str, payload: ShipmentReceive
) -> ShipmentManifest:
    svc = get_biobank_service()
    try:
        result = svc.receive_shipment(shipment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Metrics & Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=BiobankMetrics,
    summary="Get biobank dashboard metrics",
    description="Aggregated biobank operational metrics including storage utilization, quality scores, and consent withdrawal rates.",
)
async def get_metrics() -> BiobankMetrics:
    svc = get_biobank_service()
    return svc.get_metrics()
