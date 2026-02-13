"""Specimen Management API endpoints (SPEC-MGT).

Provides comprehensive specimen management operations: collection tracking,
storage inventory, chain of custody records, shipping logistics, and specimen
quality control with specimen metrics.

Endpoints:
    GET    /specimen-management/collection-records                       - List collection records
    GET    /specimen-management/collection-records/{record_id}           - Get single record
    POST   /specimen-management/collection-records                       - Create record
    PUT    /specimen-management/collection-records/{record_id}           - Update record
    DELETE /specimen-management/collection-records/{record_id}           - Delete record
    GET    /specimen-management/storage-inventory                        - List storage inventory
    GET    /specimen-management/storage-inventory/{inventory_id}         - Get single inventory
    POST   /specimen-management/storage-inventory                        - Create inventory
    PUT    /specimen-management/storage-inventory/{inventory_id}         - Update inventory
    DELETE /specimen-management/storage-inventory/{inventory_id}         - Delete inventory
    GET    /specimen-management/chain-of-custody                         - List custody records
    GET    /specimen-management/chain-of-custody/{custody_id}            - Get single custody
    POST   /specimen-management/chain-of-custody                         - Create custody
    PUT    /specimen-management/chain-of-custody/{custody_id}            - Update custody
    DELETE /specimen-management/chain-of-custody/{custody_id}            - Delete custody
    GET    /specimen-management/shipping-logistics                       - List shipments
    GET    /specimen-management/shipping-logistics/{shipping_id}         - Get single shipment
    POST   /specimen-management/shipping-logistics                       - Create shipment
    PUT    /specimen-management/shipping-logistics/{shipping_id}         - Update shipment
    DELETE /specimen-management/shipping-logistics/{shipping_id}         - Delete shipment
    GET    /specimen-management/specimen-qc                              - List QC records
    GET    /specimen-management/specimen-qc/{qc_id}                      - Get single QC
    POST   /specimen-management/specimen-qc                              - Create QC
    PUT    /specimen-management/specimen-qc/{qc_id}                      - Update QC
    DELETE /specimen-management/specimen-qc/{qc_id}                      - Delete QC
    GET    /specimen-management/metrics                                  - Specimen metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.specimen_management import (
    ChainOfCustody,
    ChainOfCustodyCreate,
    ChainOfCustodyListResponse,
    ChainOfCustodyUpdate,
    CollectionRecord,
    CollectionRecordCreate,
    CollectionRecordListResponse,
    CollectionRecordUpdate,
    CollectionStatus,
    QCResult,
    ShippingLogistic,
    ShippingLogisticCreate,
    ShippingLogisticListResponse,
    ShippingLogisticUpdate,
    ShippingStatus,
    SpecimenManagementMetrics,
    SpecimenQC,
    SpecimenQCCreate,
    SpecimenQCListResponse,
    SpecimenQCUpdate,
    SpecimenType,
    StorageCondition,
    StorageInventory,
    StorageInventoryCreate,
    StorageInventoryListResponse,
    StorageInventoryUpdate,
)
from app.services.specimen_management_service import get_specimen_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/specimen-management",
    tags=["Specimen Management"],
)


# ---------------------------------------------------------------------------
# Collection Records
# ---------------------------------------------------------------------------


@router.get(
    "/collection-records",
    response_model=CollectionRecordListResponse,
    summary="List collection records",
    description="Retrieve collection records with optional filtering by trial, specimen type, and status.",
)
async def list_collection_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    specimen_type: Optional[SpecimenType] = Query(None, description="Filter by specimen type"),
    collection_status: Optional[CollectionStatus] = Query(None, description="Filter by collection status"),
) -> CollectionRecordListResponse:
    svc = get_specimen_management_service()
    items = svc.list_collection_records(
        trial_id=trial_id, specimen_type=specimen_type, collection_status=collection_status
    )
    return CollectionRecordListResponse(items=items, total=len(items))


@router.get(
    "/collection-records/{record_id}",
    response_model=CollectionRecord,
    summary="Get a collection record",
)
async def get_collection_record(record_id: str) -> CollectionRecord:
    svc = get_specimen_management_service()
    record = svc.get_collection_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Collection record '{record_id}' not found")
    return record


@router.post(
    "/collection-records",
    response_model=CollectionRecord,
    status_code=201,
    summary="Create a collection record",
)
async def create_collection_record(payload: CollectionRecordCreate) -> CollectionRecord:
    svc = get_specimen_management_service()
    return svc.create_collection_record(payload)


@router.put(
    "/collection-records/{record_id}",
    response_model=CollectionRecord,
    summary="Update a collection record",
)
async def update_collection_record(
    record_id: str, payload: CollectionRecordUpdate
) -> CollectionRecord:
    svc = get_specimen_management_service()
    updated = svc.update_collection_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Collection record '{record_id}' not found")
    return updated


@router.delete(
    "/collection-records/{record_id}",
    status_code=204,
    summary="Delete a collection record",
)
async def delete_collection_record(record_id: str) -> None:
    svc = get_specimen_management_service()
    deleted = svc.delete_collection_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Collection record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Storage Inventory
# ---------------------------------------------------------------------------


@router.get(
    "/storage-inventory",
    response_model=StorageInventoryListResponse,
    summary="List storage inventory",
    description="Retrieve storage inventory with optional filtering by trial, condition, and availability.",
)
async def list_storage_inventory(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    storage_condition: Optional[StorageCondition] = Query(None, description="Filter by storage condition"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
) -> StorageInventoryListResponse:
    svc = get_specimen_management_service()
    items = svc.list_storage_inventory(
        trial_id=trial_id, storage_condition=storage_condition, is_available=is_available
    )
    return StorageInventoryListResponse(items=items, total=len(items))


@router.get(
    "/storage-inventory/{inventory_id}",
    response_model=StorageInventory,
    summary="Get a storage inventory record",
)
async def get_storage_inventory(inventory_id: str) -> StorageInventory:
    svc = get_specimen_management_service()
    record = svc.get_storage_inventory(inventory_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Storage inventory '{inventory_id}' not found"
        )
    return record


@router.post(
    "/storage-inventory",
    response_model=StorageInventory,
    status_code=201,
    summary="Create a storage inventory record",
)
async def create_storage_inventory(payload: StorageInventoryCreate) -> StorageInventory:
    svc = get_specimen_management_service()
    return svc.create_storage_inventory(payload)


@router.put(
    "/storage-inventory/{inventory_id}",
    response_model=StorageInventory,
    summary="Update a storage inventory record",
)
async def update_storage_inventory(
    inventory_id: str, payload: StorageInventoryUpdate
) -> StorageInventory:
    svc = get_specimen_management_service()
    updated = svc.update_storage_inventory(inventory_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Storage inventory '{inventory_id}' not found"
        )
    return updated


@router.delete(
    "/storage-inventory/{inventory_id}",
    status_code=204,
    summary="Delete a storage inventory record",
)
async def delete_storage_inventory(inventory_id: str) -> None:
    svc = get_specimen_management_service()
    deleted = svc.delete_storage_inventory(inventory_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Storage inventory '{inventory_id}' not found"
        )


# ---------------------------------------------------------------------------
# Chain of Custody
# ---------------------------------------------------------------------------


@router.get(
    "/chain-of-custody",
    response_model=ChainOfCustodyListResponse,
    summary="List chain of custody records",
    description="Retrieve chain of custody records with optional filtering by trial and specimen.",
)
async def list_chain_of_custody(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
) -> ChainOfCustodyListResponse:
    svc = get_specimen_management_service()
    items = svc.list_chain_of_custody(trial_id=trial_id, specimen_id=specimen_id)
    return ChainOfCustodyListResponse(items=items, total=len(items))


@router.get(
    "/chain-of-custody/{custody_id}",
    response_model=ChainOfCustody,
    summary="Get a chain of custody record",
)
async def get_chain_of_custody(custody_id: str) -> ChainOfCustody:
    svc = get_specimen_management_service()
    record = svc.get_chain_of_custody(custody_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Chain of custody '{custody_id}' not found"
        )
    return record


@router.post(
    "/chain-of-custody",
    response_model=ChainOfCustody,
    status_code=201,
    summary="Create a chain of custody record",
)
async def create_chain_of_custody(payload: ChainOfCustodyCreate) -> ChainOfCustody:
    svc = get_specimen_management_service()
    return svc.create_chain_of_custody(payload)


@router.put(
    "/chain-of-custody/{custody_id}",
    response_model=ChainOfCustody,
    summary="Update a chain of custody record",
)
async def update_chain_of_custody(
    custody_id: str, payload: ChainOfCustodyUpdate
) -> ChainOfCustody:
    svc = get_specimen_management_service()
    updated = svc.update_chain_of_custody(custody_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Chain of custody '{custody_id}' not found"
        )
    return updated


@router.delete(
    "/chain-of-custody/{custody_id}",
    status_code=204,
    summary="Delete a chain of custody record",
)
async def delete_chain_of_custody(custody_id: str) -> None:
    svc = get_specimen_management_service()
    deleted = svc.delete_chain_of_custody(custody_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Chain of custody '{custody_id}' not found"
        )


# ---------------------------------------------------------------------------
# Shipping Logistics
# ---------------------------------------------------------------------------


@router.get(
    "/shipping-logistics",
    response_model=ShippingLogisticListResponse,
    summary="List shipping logistics",
    description="Retrieve shipping logistics with optional filtering by trial and status.",
)
async def list_shipping_logistics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    shipping_status: Optional[ShippingStatus] = Query(None, description="Filter by shipping status"),
) -> ShippingLogisticListResponse:
    svc = get_specimen_management_service()
    items = svc.list_shipping_logistics(trial_id=trial_id, shipping_status=shipping_status)
    return ShippingLogisticListResponse(items=items, total=len(items))


@router.get(
    "/shipping-logistics/{shipping_id}",
    response_model=ShippingLogistic,
    summary="Get a shipping logistic record",
)
async def get_shipping_logistic(shipping_id: str) -> ShippingLogistic:
    svc = get_specimen_management_service()
    record = svc.get_shipping_logistic(shipping_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Shipping logistic '{shipping_id}' not found"
        )
    return record


@router.post(
    "/shipping-logistics",
    response_model=ShippingLogistic,
    status_code=201,
    summary="Create a shipping logistic record",
)
async def create_shipping_logistic(payload: ShippingLogisticCreate) -> ShippingLogistic:
    svc = get_specimen_management_service()
    return svc.create_shipping_logistic(payload)


@router.put(
    "/shipping-logistics/{shipping_id}",
    response_model=ShippingLogistic,
    summary="Update a shipping logistic record",
)
async def update_shipping_logistic(
    shipping_id: str, payload: ShippingLogisticUpdate
) -> ShippingLogistic:
    svc = get_specimen_management_service()
    updated = svc.update_shipping_logistic(shipping_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Shipping logistic '{shipping_id}' not found"
        )
    return updated


@router.delete(
    "/shipping-logistics/{shipping_id}",
    status_code=204,
    summary="Delete a shipping logistic record",
)
async def delete_shipping_logistic(shipping_id: str) -> None:
    svc = get_specimen_management_service()
    deleted = svc.delete_shipping_logistic(shipping_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Shipping logistic '{shipping_id}' not found"
        )


# ---------------------------------------------------------------------------
# Specimen QC
# ---------------------------------------------------------------------------


@router.get(
    "/specimen-qc",
    response_model=SpecimenQCListResponse,
    summary="List specimen QC records",
    description="Retrieve specimen QC records with optional filtering by trial, specimen, and result.",
)
async def list_specimen_qc(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
    qc_result: Optional[QCResult] = Query(None, description="Filter by QC result"),
) -> SpecimenQCListResponse:
    svc = get_specimen_management_service()
    items = svc.list_specimen_qc(trial_id=trial_id, specimen_id=specimen_id, qc_result=qc_result)
    return SpecimenQCListResponse(items=items, total=len(items))


@router.get(
    "/specimen-qc/{qc_id}",
    response_model=SpecimenQC,
    summary="Get a specimen QC record",
)
async def get_specimen_qc(qc_id: str) -> SpecimenQC:
    svc = get_specimen_management_service()
    record = svc.get_specimen_qc(qc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Specimen QC '{qc_id}' not found")
    return record


@router.post(
    "/specimen-qc",
    response_model=SpecimenQC,
    status_code=201,
    summary="Create a specimen QC record",
)
async def create_specimen_qc(payload: SpecimenQCCreate) -> SpecimenQC:
    svc = get_specimen_management_service()
    return svc.create_specimen_qc(payload)


@router.put(
    "/specimen-qc/{qc_id}",
    response_model=SpecimenQC,
    summary="Update a specimen QC record",
)
async def update_specimen_qc(qc_id: str, payload: SpecimenQCUpdate) -> SpecimenQC:
    svc = get_specimen_management_service()
    updated = svc.update_specimen_qc(qc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Specimen QC '{qc_id}' not found")
    return updated


@router.delete(
    "/specimen-qc/{qc_id}",
    status_code=204,
    summary="Delete a specimen QC record",
)
async def delete_specimen_qc(qc_id: str) -> None:
    svc = get_specimen_management_service()
    deleted = svc.delete_specimen_qc(qc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Specimen QC '{qc_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SpecimenManagementMetrics,
    summary="Get specimen management metrics",
    description="Aggregated metrics across all specimen management operations.",
)
async def get_metrics() -> SpecimenManagementMetrics:
    svc = get_specimen_management_service()
    return svc.get_metrics()
