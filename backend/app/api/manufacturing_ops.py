"""Manufacturing Operations & Batch Record API endpoints (MFG-OPS).

Provides comprehensive GMP manufacturing operations: batch record lifecycle,
equipment qualification tracking, environmental monitoring, process validation,
deviation management with CAPA, batch release checklists, and operational metrics.

Endpoints:
    GET    /manufacturing-ops/batches                                  - List batch records
    GET    /manufacturing-ops/batches/{batch_id}                       - Get single batch
    POST   /manufacturing-ops/batches                                  - Create batch record
    PUT    /manufacturing-ops/batches/{batch_id}                       - Update batch record
    DELETE /manufacturing-ops/batches/{batch_id}                       - Delete batch record
    POST   /manufacturing-ops/batches/{batch_id}/start                 - Start batch manufacturing
    POST   /manufacturing-ops/batches/{batch_id}/complete              - Complete batch
    POST   /manufacturing-ops/batches/{batch_id}/release               - Release batch

    GET    /manufacturing-ops/equipment                                - List equipment
    GET    /manufacturing-ops/equipment/{equipment_id}                 - Get single equipment
    POST   /manufacturing-ops/equipment                                - Create equipment
    PUT    /manufacturing-ops/equipment/{equipment_id}                 - Update equipment
    DELETE /manufacturing-ops/equipment/{equipment_id}                 - Delete equipment

    GET    /manufacturing-ops/environmental-monitoring                 - List env monitoring
    GET    /manufacturing-ops/environmental-monitoring/{record_id}     - Get single record
    POST   /manufacturing-ops/environmental-monitoring                 - Log env monitoring

    GET    /manufacturing-ops/validations                              - List validations
    GET    /manufacturing-ops/validations/{validation_id}              - Get single validation
    POST   /manufacturing-ops/validations                              - Create validation
    PUT    /manufacturing-ops/validations/{validation_id}              - Update validation
    DELETE /manufacturing-ops/validations/{validation_id}              - Delete validation
    POST   /manufacturing-ops/validations/{validation_id}/pass         - Mark validation passed

    GET    /manufacturing-ops/deviations                               - List deviations
    GET    /manufacturing-ops/deviations/{deviation_id}                - Get single deviation
    POST   /manufacturing-ops/deviations                               - Record deviation
    PUT    /manufacturing-ops/deviations/{deviation_id}                - Update deviation
    DELETE /manufacturing-ops/deviations/{deviation_id}                - Delete deviation

    GET    /manufacturing-ops/checklists                               - List checklists
    GET    /manufacturing-ops/checklists/{item_id}                     - Get checklist item
    POST   /manufacturing-ops/checklists                               - Create checklist item
    PUT    /manufacturing-ops/checklists/{item_id}                     - Update checklist item
    DELETE /manufacturing-ops/checklists/{item_id}                     - Delete checklist item

    GET    /manufacturing-ops/metrics                                  - Manufacturing metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.manufacturing_ops import (
    BatchRecord,
    BatchRecordCreate,
    BatchRecordListResponse,
    BatchRecordUpdate,
    BatchReleaseChecklist,
    BatchReleaseRequest,
    BatchStatus,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    ChecklistListResponse,
    DeviationCreate,
    DeviationListResponse,
    DeviationStatus,
    DeviationType,
    DeviationUpdate,
    EnvironmentalMonitoring,
    EnvironmentalMonitoringCreate,
    EnvironmentalMonitoringListResponse,
    EnvironmentalZone,
    Equipment,
    EquipmentCreate,
    EquipmentListResponse,
    EquipmentStatus,
    EquipmentUpdate,
    ManufacturingDeviation,
    ManufacturingMetrics,
    MonitoringResult,
    ProcessValidation,
    ProcessValidationCreate,
    ProcessValidationListResponse,
    ProcessValidationUpdate,
    ValidationStatus,
)
from app.services.manufacturing_ops_service import get_manufacturing_ops_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/manufacturing-ops",
    tags=["Manufacturing Operations"],
)


# ---------------------------------------------------------------------------
# Batch Record Management
# ---------------------------------------------------------------------------


@router.get(
    "/batches",
    response_model=BatchRecordListResponse,
    summary="List batch records",
    description="Retrieve batch records with optional filtering by status, manufacturing site, and product name.",
)
async def list_batches(
    status: Optional[BatchStatus] = Query(None, description="Filter by batch status"),
    manufacturing_site: Optional[str] = Query(None, description="Filter by manufacturing site (partial match)"),
    product_name: Optional[str] = Query(None, description="Filter by product name (partial match)"),
) -> BatchRecordListResponse:
    svc = get_manufacturing_ops_service()
    items = svc.list_batches(status=status, manufacturing_site=manufacturing_site, product_name=product_name)
    return BatchRecordListResponse(items=items, total=len(items))


@router.get(
    "/batches/{batch_id}",
    response_model=BatchRecord,
    summary="Get a batch record",
)
async def get_batch(batch_id: str) -> BatchRecord:
    svc = get_manufacturing_ops_service()
    batch = svc.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return batch


@router.post(
    "/batches",
    response_model=BatchRecord,
    status_code=201,
    summary="Create a batch record",
)
async def create_batch(payload: BatchRecordCreate) -> BatchRecord:
    svc = get_manufacturing_ops_service()
    return svc.create_batch(payload)


@router.put(
    "/batches/{batch_id}",
    response_model=BatchRecord,
    summary="Update a batch record",
)
async def update_batch(batch_id: str, payload: BatchRecordUpdate) -> BatchRecord:
    svc = get_manufacturing_ops_service()
    updated = svc.update_batch(batch_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return updated


@router.delete(
    "/batches/{batch_id}",
    status_code=204,
    summary="Delete a batch record",
)
async def delete_batch(batch_id: str) -> None:
    svc = get_manufacturing_ops_service()
    deleted = svc.delete_batch(batch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.post(
    "/batches/{batch_id}/start",
    response_model=BatchRecord,
    summary="Start batch manufacturing",
    description="Transition a planned batch to in_progress and record start timestamp.",
)
async def start_batch(batch_id: str) -> BatchRecord:
    svc = get_manufacturing_ops_service()
    try:
        result = svc.start_batch(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return result


@router.post(
    "/batches/{batch_id}/complete",
    response_model=BatchRecord,
    summary="Complete batch manufacturing",
    description="Mark an in-progress batch as completed with actual yield data.",
)
async def complete_batch(
    batch_id: str,
    yield_actual: float = Query(..., gt=0, description="Actual yield quantity"),
) -> BatchRecord:
    svc = get_manufacturing_ops_service()
    try:
        result = svc.complete_batch(batch_id, yield_actual=yield_actual)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return result


@router.post(
    "/batches/{batch_id}/release",
    response_model=BatchRecord,
    summary="Release a batch",
    description="Release a completed batch after verifying all required checklist items and no open critical deviations.",
)
async def release_batch(batch_id: str, payload: BatchReleaseRequest) -> BatchRecord:
    svc = get_manufacturing_ops_service()
    try:
        result = svc.release_batch(batch_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Equipment Management
# ---------------------------------------------------------------------------


@router.get(
    "/equipment",
    response_model=EquipmentListResponse,
    summary="List equipment",
    description="Retrieve equipment records with optional filtering by status, type, and assigned area.",
)
async def list_equipment(
    status: Optional[EquipmentStatus] = Query(None, description="Filter by equipment status"),
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type (partial match)"),
    assigned_area: Optional[str] = Query(None, description="Filter by assigned area (partial match)"),
) -> EquipmentListResponse:
    svc = get_manufacturing_ops_service()
    items = svc.list_equipment(status=status, equipment_type=equipment_type, assigned_area=assigned_area)
    return EquipmentListResponse(items=items, total=len(items))


@router.get(
    "/equipment/{equipment_id}",
    response_model=Equipment,
    summary="Get an equipment record",
)
async def get_equipment(equipment_id: str) -> Equipment:
    svc = get_manufacturing_ops_service()
    eq = svc.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment '{equipment_id}' not found")
    return eq


@router.post(
    "/equipment",
    response_model=Equipment,
    status_code=201,
    summary="Create an equipment record",
)
async def create_equipment(payload: EquipmentCreate) -> Equipment:
    svc = get_manufacturing_ops_service()
    return svc.create_equipment(payload)


@router.put(
    "/equipment/{equipment_id}",
    response_model=Equipment,
    summary="Update an equipment record",
)
async def update_equipment(equipment_id: str, payload: EquipmentUpdate) -> Equipment:
    svc = get_manufacturing_ops_service()
    updated = svc.update_equipment(equipment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Equipment '{equipment_id}' not found")
    return updated


@router.delete(
    "/equipment/{equipment_id}",
    status_code=204,
    summary="Delete an equipment record",
)
async def delete_equipment(equipment_id: str) -> None:
    svc = get_manufacturing_ops_service()
    deleted = svc.delete_equipment(equipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Equipment '{equipment_id}' not found")


# ---------------------------------------------------------------------------
# Environmental Monitoring
# ---------------------------------------------------------------------------


@router.get(
    "/environmental-monitoring",
    response_model=EnvironmentalMonitoringListResponse,
    summary="List environmental monitoring records",
    description="Retrieve environmental monitoring records with optional filtering by zone, result, and room.",
)
async def list_environmental_monitoring(
    zone: Optional[EnvironmentalZone] = Query(None, description="Filter by cleanroom zone"),
    result: Optional[MonitoringResult] = Query(None, description="Filter by monitoring result"),
    room_name: Optional[str] = Query(None, description="Filter by room name (partial match)"),
) -> EnvironmentalMonitoringListResponse:
    svc = get_manufacturing_ops_service()
    items = svc.list_environmental_monitoring(zone=zone, result=result, room_name=room_name)
    return EnvironmentalMonitoringListResponse(items=items, total=len(items))


@router.get(
    "/environmental-monitoring/{record_id}",
    response_model=EnvironmentalMonitoring,
    summary="Get an environmental monitoring record",
)
async def get_environmental_monitoring(record_id: str) -> EnvironmentalMonitoring:
    svc = get_manufacturing_ops_service()
    record = svc.get_environmental_monitoring(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Environmental monitoring record '{record_id}' not found")
    return record


@router.post(
    "/environmental-monitoring",
    response_model=EnvironmentalMonitoring,
    status_code=201,
    summary="Log environmental monitoring event",
    description="Record a new environmental monitoring measurement with automatic result evaluation based on zone limits.",
)
async def log_environmental_monitoring(
    payload: EnvironmentalMonitoringCreate,
) -> EnvironmentalMonitoring:
    svc = get_manufacturing_ops_service()
    return svc.log_environmental_monitoring(payload)


# ---------------------------------------------------------------------------
# Process Validation
# ---------------------------------------------------------------------------


@router.get(
    "/validations",
    response_model=ProcessValidationListResponse,
    summary="List process validations",
    description="Retrieve process validation records with optional filtering by status and product name.",
)
async def list_validations(
    status: Optional[ValidationStatus] = Query(None, description="Filter by validation status"),
    product_name: Optional[str] = Query(None, description="Filter by product name (partial match)"),
) -> ProcessValidationListResponse:
    svc = get_manufacturing_ops_service()
    items = svc.list_validations(status=status, product_name=product_name)
    return ProcessValidationListResponse(items=items, total=len(items))


@router.get(
    "/validations/{validation_id}",
    response_model=ProcessValidation,
    summary="Get a process validation record",
)
async def get_validation(validation_id: str) -> ProcessValidation:
    svc = get_manufacturing_ops_service()
    validation = svc.get_validation(validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return validation


@router.post(
    "/validations",
    response_model=ProcessValidation,
    status_code=201,
    summary="Create a process validation",
)
async def create_validation(payload: ProcessValidationCreate) -> ProcessValidation:
    svc = get_manufacturing_ops_service()
    return svc.create_validation(payload)


@router.put(
    "/validations/{validation_id}",
    response_model=ProcessValidation,
    summary="Update a process validation",
)
async def update_validation(validation_id: str, payload: ProcessValidationUpdate) -> ProcessValidation:
    svc = get_manufacturing_ops_service()
    updated = svc.update_validation(validation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return updated


@router.delete(
    "/validations/{validation_id}",
    status_code=204,
    summary="Delete a process validation",
)
async def delete_validation(validation_id: str) -> None:
    svc = get_manufacturing_ops_service()
    deleted = svc.delete_validation(validation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")


@router.post(
    "/validations/{validation_id}/pass",
    response_model=ProcessValidation,
    summary="Mark validation as passed",
    description="Mark an in-progress validation as passed if required batches are complete.",
)
async def validate_process(validation_id: str) -> ProcessValidation:
    svc = get_manufacturing_ops_service()
    try:
        result = svc.validate_process(validation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Deviation Management
# ---------------------------------------------------------------------------


@router.get(
    "/deviations",
    response_model=DeviationListResponse,
    summary="List manufacturing deviations",
    description="Retrieve manufacturing deviations with optional filtering by type, status, and batch.",
)
async def list_deviations(
    deviation_type: Optional[DeviationType] = Query(None, description="Filter by deviation type"),
    status: Optional[DeviationStatus] = Query(None, description="Filter by deviation status"),
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
) -> DeviationListResponse:
    svc = get_manufacturing_ops_service()
    items = svc.list_deviations(deviation_type=deviation_type, status=status, batch_id=batch_id)
    return DeviationListResponse(items=items, total=len(items))


@router.get(
    "/deviations/{deviation_id}",
    response_model=ManufacturingDeviation,
    summary="Get a manufacturing deviation",
)
async def get_deviation(deviation_id: str) -> ManufacturingDeviation:
    svc = get_manufacturing_ops_service()
    deviation = svc.get_deviation(deviation_id)
    if deviation is None:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")
    return deviation


@router.post(
    "/deviations",
    response_model=ManufacturingDeviation,
    status_code=201,
    summary="Record a manufacturing deviation",
    description="Record a new manufacturing deviation. Critical deviations linked to a batch will automatically quarantine that batch.",
)
async def record_deviation(payload: DeviationCreate) -> ManufacturingDeviation:
    svc = get_manufacturing_ops_service()
    return svc.record_deviation(payload)


@router.put(
    "/deviations/{deviation_id}",
    response_model=ManufacturingDeviation,
    summary="Update a manufacturing deviation",
    description="Update deviation details including root cause, corrective/preventive actions, and status.",
)
async def update_deviation(deviation_id: str, payload: DeviationUpdate) -> ManufacturingDeviation:
    svc = get_manufacturing_ops_service()
    updated = svc.update_deviation(deviation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")
    return updated


@router.delete(
    "/deviations/{deviation_id}",
    status_code=204,
    summary="Delete a manufacturing deviation",
)
async def delete_deviation(deviation_id: str) -> None:
    svc = get_manufacturing_ops_service()
    deleted = svc.delete_deviation(deviation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Deviation '{deviation_id}' not found")


# ---------------------------------------------------------------------------
# Batch Release Checklists
# ---------------------------------------------------------------------------


@router.get(
    "/checklists",
    response_model=ChecklistListResponse,
    summary="List batch release checklist items",
    description="Retrieve batch release checklist items with optional filtering by batch and checked status.",
)
async def list_checklists(
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    checked: Optional[bool] = Query(None, description="Filter by checked status"),
) -> ChecklistListResponse:
    svc = get_manufacturing_ops_service()
    items = svc.list_checklists(batch_id=batch_id, checked=checked)
    return ChecklistListResponse(items=items, total=len(items))


@router.get(
    "/checklists/{item_id}",
    response_model=BatchReleaseChecklist,
    summary="Get a checklist item",
)
async def get_checklist_item(item_id: str) -> BatchReleaseChecklist:
    svc = get_manufacturing_ops_service()
    item = svc.get_checklist_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Checklist item '{item_id}' not found")
    return item


@router.post(
    "/checklists",
    response_model=BatchReleaseChecklist,
    status_code=201,
    summary="Create a checklist item",
)
async def create_checklist_item(payload: ChecklistItemCreate) -> BatchReleaseChecklist:
    svc = get_manufacturing_ops_service()
    return svc.create_checklist_item(payload)


@router.put(
    "/checklists/{item_id}",
    response_model=BatchReleaseChecklist,
    summary="Update a checklist item",
    description="Update checklist item details, including marking it as checked.",
)
async def update_checklist_item(item_id: str, payload: ChecklistItemUpdate) -> BatchReleaseChecklist:
    svc = get_manufacturing_ops_service()
    updated = svc.update_checklist_item(item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Checklist item '{item_id}' not found")
    return updated


@router.delete(
    "/checklists/{item_id}",
    status_code=204,
    summary="Delete a checklist item",
)
async def delete_checklist_item(item_id: str) -> None:
    svc = get_manufacturing_ops_service()
    deleted = svc.delete_checklist_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Checklist item '{item_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ManufacturingMetrics,
    summary="Get manufacturing operations metrics",
    description="Aggregated manufacturing operations metrics including batch statistics, equipment status, "
                "environmental excursions, validation progress, and deviation summary.",
)
async def get_metrics() -> ManufacturingMetrics:
    svc = get_manufacturing_ops_service()
    return svc.get_metrics()
