"""IP Accountability (Investigational Product Accountability) API endpoints.

Provides comprehensive IP accountability operations: shipment receipt and tracking,
inventory management with kit-level tracking, dispensing to patients with witness
documentation, product returns with condition assessment, temperature excursion
logging and resolution, accountability log maintenance, site-level reconciliation,
and IP operational metrics.

Endpoints:
    GET    /ip-accountability/shipments                                   - List shipments
    POST   /ip-accountability/shipments                                   - Create shipment
    GET    /ip-accountability/shipments/{shipment_id}                     - Get single shipment
    PUT    /ip-accountability/shipments/{shipment_id}                     - Update shipment
    GET    /ip-accountability/inventory                                   - List inventory items
    POST   /ip-accountability/inventory                                   - Create inventory item
    GET    /ip-accountability/inventory/{item_id}                         - Get inventory item
    PUT    /ip-accountability/inventory/{item_id}                         - Update inventory item
    GET    /ip-accountability/inventory/site/{site_id}                    - Get site inventory
    POST   /ip-accountability/dispensing                                  - Record dispensing
    GET    /ip-accountability/dispensing                                  - List dispensing records
    POST   /ip-accountability/returns                                    - Record return
    GET    /ip-accountability/returns                                    - List return records
    POST   /ip-accountability/temperature-excursions                     - Log temp excursion
    GET    /ip-accountability/temperature-excursions                     - List excursions
    GET    /ip-accountability/temperature-excursions/{excursion_id}      - Get excursion
    POST   /ip-accountability/temperature-excursions/{excursion_id}/resolve - Resolve excursion
    GET    /ip-accountability/accountability-logs                        - List logs
    POST   /ip-accountability/accountability-logs                        - Create log
    GET    /ip-accountability/accountability-logs/{log_id}               - Get single log
    POST   /ip-accountability/reconciliation                             - Perform reconciliation
    GET    /ip-accountability/reconciliation                             - List reconciliations
    GET    /ip-accountability/metrics                                    - IP metrics dashboard
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.ip_accountability import (
    AccountabilityLog,
    AccountabilityLogCreate,
    AccountabilityLogListResponse,
    DispensingRecord,
    DispensingRecordCreate,
    DispensingRecordListResponse,
    IPInventoryItem,
    IPInventoryItemCreate,
    IPInventoryItemListResponse,
    IPInventoryItemUpdate,
    IPMetrics,
    IPReconciliation,
    IPReconciliationCreate,
    IPReconciliationListResponse,
    IPShipment,
    IPShipmentCreate,
    IPShipmentListResponse,
    IPShipmentUpdate,
    IPStatus,
    ReconciliationStatus,
    ReturnRecord,
    ReturnRecordCreate,
    ReturnRecordListResponse,
    TemperatureExcursion,
    TemperatureExcursionCreate,
    TemperatureExcursionListResponse,
    TemperatureExcursionResolve,
    TemperatureExcursionSeverity,
)
from app.services.ip_accountability_service import get_ip_accountability_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ip-accountability",
    tags=["IP Accountability"],
)


# ---------------------------------------------------------------------------
# Shipment Management
# ---------------------------------------------------------------------------


@router.get(
    "/shipments",
    response_model=IPShipmentListResponse,
    summary="List IP shipments",
    description="Retrieve IP shipments with optional filtering by site, trial, and status.",
)
async def list_shipments(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[IPStatus] = Query(None, description="Filter by status"),
) -> IPShipmentListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_shipments(site_id=site_id, trial_id=trial_id, status=status)
    return IPShipmentListResponse(items=items, total=len(items))


@router.post(
    "/shipments",
    response_model=IPShipment,
    status_code=201,
    summary="Create an IP shipment",
    description="Record a new investigational product shipment to a clinical trial site.",
)
async def create_shipment(payload: IPShipmentCreate) -> IPShipment:
    svc = get_ip_accountability_service()
    return svc.create_shipment(payload)


@router.get(
    "/shipments/{shipment_id}",
    response_model=IPShipment,
    summary="Get an IP shipment",
)
async def get_shipment(shipment_id: str) -> IPShipment:
    svc = get_ip_accountability_service()
    shipment = svc.get_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return shipment


@router.put(
    "/shipments/{shipment_id}",
    response_model=IPShipment,
    summary="Update an IP shipment",
    description="Update shipment details such as receipt confirmation and status.",
)
async def update_shipment(shipment_id: str, payload: IPShipmentUpdate) -> IPShipment:
    svc = get_ip_accountability_service()
    updated = svc.update_shipment(shipment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Inventory Management
# ---------------------------------------------------------------------------


@router.get(
    "/inventory",
    response_model=IPInventoryItemListResponse,
    summary="List inventory items",
    description="Retrieve IP inventory items with optional filtering by site, status, and shipment.",
)
async def list_inventory(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[IPStatus] = Query(None, description="Filter by status"),
    shipment_id: Optional[str] = Query(None, description="Filter by shipment ID"),
) -> IPInventoryItemListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_inventory(site_id=site_id, status=status, shipment_id=shipment_id)
    return IPInventoryItemListResponse(items=items, total=len(items))


@router.post(
    "/inventory",
    response_model=IPInventoryItem,
    status_code=201,
    summary="Create an inventory item",
    description="Add a new investigational product unit to site inventory.",
)
async def create_inventory_item(payload: IPInventoryItemCreate) -> IPInventoryItem:
    svc = get_ip_accountability_service()
    return svc.create_inventory_item(payload)


@router.get(
    "/inventory/site/{site_id}",
    response_model=IPInventoryItemListResponse,
    summary="Get site inventory",
    description="Retrieve all inventory items for a specific clinical trial site.",
)
async def get_site_inventory(site_id: str) -> IPInventoryItemListResponse:
    svc = get_ip_accountability_service()
    items = svc.get_site_inventory(site_id)
    return IPInventoryItemListResponse(items=items, total=len(items))


@router.get(
    "/inventory/{item_id}",
    response_model=IPInventoryItem,
    summary="Get an inventory item",
)
async def get_inventory_item(item_id: str) -> IPInventoryItem:
    svc = get_ip_accountability_service()
    item = svc.get_inventory_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Inventory item '{item_id}' not found")
    return item


@router.put(
    "/inventory/{item_id}",
    response_model=IPInventoryItem,
    summary="Update an inventory item",
    description="Update inventory item details such as status and quantity.",
)
async def update_inventory_item(item_id: str, payload: IPInventoryItemUpdate) -> IPInventoryItem:
    svc = get_ip_accountability_service()
    updated = svc.update_inventory_item(item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Inventory item '{item_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Dispensing
# ---------------------------------------------------------------------------


@router.post(
    "/dispensing",
    response_model=DispensingRecord,
    status_code=201,
    summary="Record a dispensing event",
    description="Record dispensing of investigational product to a patient. Validates inventory availability and updates item status.",
)
async def record_dispensing(payload: DispensingRecordCreate) -> DispensingRecord:
    svc = get_ip_accountability_service()
    try:
        return svc.record_dispensing(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/dispensing",
    response_model=DispensingRecordListResponse,
    summary="List dispensing records",
    description="Retrieve dispensing records with optional filtering by site and patient.",
)
async def list_dispensing_records(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> DispensingRecordListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_dispensing_records(site_id=site_id, patient_id=patient_id)
    return DispensingRecordListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------


@router.post(
    "/returns",
    response_model=ReturnRecord,
    status_code=201,
    summary="Record a product return",
    description="Record return of investigational product from a patient. Updates inventory item status.",
)
async def record_return(payload: ReturnRecordCreate) -> ReturnRecord:
    svc = get_ip_accountability_service()
    try:
        return svc.record_return(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/returns",
    response_model=ReturnRecordListResponse,
    summary="List return records",
    description="Retrieve return records with optional filtering by site and patient.",
)
async def list_return_records(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> ReturnRecordListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_return_records(site_id=site_id, patient_id=patient_id)
    return ReturnRecordListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Temperature Excursions
# ---------------------------------------------------------------------------


@router.post(
    "/temperature-excursions",
    response_model=TemperatureExcursion,
    status_code=201,
    summary="Log a temperature excursion",
    description="Log a temperature excursion event for stored investigational product.",
)
async def log_temperature_excursion(payload: TemperatureExcursionCreate) -> TemperatureExcursion:
    svc = get_ip_accountability_service()
    return svc.log_temperature_excursion(payload)


@router.get(
    "/temperature-excursions",
    response_model=TemperatureExcursionListResponse,
    summary="List temperature excursions",
    description="Retrieve temperature excursion events with optional filtering by site, severity, and resolution status.",
)
async def list_temperature_excursions(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    severity: Optional[TemperatureExcursionSeverity] = Query(None, description="Filter by severity"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
) -> TemperatureExcursionListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_temperature_excursions(site_id=site_id, severity=severity, resolved=resolved)
    return TemperatureExcursionListResponse(items=items, total=len(items))


@router.get(
    "/temperature-excursions/{excursion_id}",
    response_model=TemperatureExcursion,
    summary="Get a temperature excursion",
)
async def get_temperature_excursion(excursion_id: str) -> TemperatureExcursion:
    svc = get_ip_accountability_service()
    excursion = svc.get_temperature_excursion(excursion_id)
    if excursion is None:
        raise HTTPException(status_code=404, detail=f"Temperature excursion '{excursion_id}' not found")
    return excursion


@router.post(
    "/temperature-excursions/{excursion_id}/resolve",
    response_model=TemperatureExcursion,
    summary="Resolve a temperature excursion",
    description="Resolve a temperature excursion event with resolution notes and impact assessment.",
)
async def resolve_temperature_excursion(
    excursion_id: str, payload: TemperatureExcursionResolve
) -> TemperatureExcursion:
    svc = get_ip_accountability_service()
    try:
        result = svc.resolve_temperature_excursion(excursion_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Temperature excursion '{excursion_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Accountability Logs
# ---------------------------------------------------------------------------


@router.get(
    "/accountability-logs",
    response_model=AccountabilityLogListResponse,
    summary="List accountability logs",
    description="Retrieve accountability log entries with optional filtering by site, trial, and reconciliation status.",
)
async def list_accountability_logs(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    reconciliation_status: Optional[ReconciliationStatus] = Query(
        None, description="Filter by reconciliation status"
    ),
) -> AccountabilityLogListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_accountability_logs(
        site_id=site_id, trial_id=trial_id, reconciliation_status=reconciliation_status
    )
    return AccountabilityLogListResponse(items=items, total=len(items))


@router.post(
    "/accountability-logs",
    response_model=AccountabilityLog,
    status_code=201,
    summary="Create an accountability log",
    description="Create a new accountability log entry for IP balance tracking at a site.",
)
async def create_accountability_log(payload: AccountabilityLogCreate) -> AccountabilityLog:
    svc = get_ip_accountability_service()
    return svc.create_accountability_log(payload)


@router.get(
    "/accountability-logs/{log_id}",
    response_model=AccountabilityLog,
    summary="Get an accountability log",
)
async def get_accountability_log(log_id: str) -> AccountabilityLog:
    svc = get_ip_accountability_service()
    log = svc.get_accountability_log(log_id)
    if log is None:
        raise HTTPException(status_code=404, detail=f"Accountability log '{log_id}' not found")
    return log


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


@router.post(
    "/reconciliation",
    response_model=IPReconciliation,
    status_code=201,
    summary="Perform IP reconciliation",
    description="Perform an IP reconciliation at a site. Automatically detects discrepancies between expected and actual quantities.",
)
async def perform_reconciliation(payload: IPReconciliationCreate) -> IPReconciliation:
    svc = get_ip_accountability_service()
    return svc.perform_reconciliation(payload)


@router.get(
    "/reconciliation",
    response_model=IPReconciliationListResponse,
    summary="List reconciliation records",
    description="Retrieve IP reconciliation records with optional filtering by site, trial, and status.",
)
async def list_reconciliations(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ReconciliationStatus] = Query(None, description="Filter by status"),
) -> IPReconciliationListResponse:
    svc = get_ip_accountability_service()
    items = svc.list_reconciliations(site_id=site_id, trial_id=trial_id, status=status)
    return IPReconciliationListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=IPMetrics,
    summary="Get IP accountability metrics",
    description="Aggregated IP accountability operational metrics across all sites.",
)
async def get_metrics() -> IPMetrics:
    svc = get_ip_accountability_service()
    return svc.get_metrics()
