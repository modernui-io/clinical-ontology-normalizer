"""IMP Supply Chain Management API endpoints (CLINICAL-6).

Provides comprehensive supply chain operations: drug product CRUD, inventory
management, shipment tracking, temperature excursion reporting, kit assignment
and reconciliation, supply forecasting, lot traceability, and metrics dashboard.

Endpoints:
    GET    /supply-chain/drug-products                           - List drug products
    GET    /supply-chain/drug-products/{product_id}              - Get single drug product
    POST   /supply-chain/drug-products                           - Create drug product
    PUT    /supply-chain/drug-products/{product_id}              - Update drug product
    DELETE /supply-chain/drug-products/{product_id}              - Delete drug product
    GET    /supply-chain/inventory                               - List inventory items
    GET    /supply-chain/inventory/{item_id}                     - Get single inventory item
    POST   /supply-chain/inventory                               - Create inventory item
    PUT    /supply-chain/inventory/{item_id}                     - Update inventory item
    DELETE /supply-chain/inventory/{item_id}                     - Delete inventory item
    GET    /supply-chain/shipments                               - List shipments
    GET    /supply-chain/shipments/{shipment_id}                 - Get single shipment
    POST   /supply-chain/shipments                               - Create shipment
    PUT    /supply-chain/shipments/{shipment_id}                 - Update shipment
    POST   /supply-chain/shipments/{shipment_id}/deliver         - Mark shipment delivered
    DELETE /supply-chain/shipments/{shipment_id}                 - Delete shipment
    GET    /supply-chain/excursions                              - List temperature excursions
    GET    /supply-chain/excursions/{excursion_id}               - Get single excursion
    POST   /supply-chain/shipments/{shipment_id}/excursions      - Report temperature excursion
    GET    /supply-chain/shipments/{shipment_id}/temperature-compliance - Check temperature compliance
    POST   /supply-chain/kits                                    - Assign kit to patient
    GET    /supply-chain/kits                                    - List kit assignments
    GET    /supply-chain/kits/{kit_id}                           - Get single kit assignment
    POST   /supply-chain/kits/{kit_id}/return                   - Record kit return
    GET    /supply-chain/kits/reconciliation                     - Kit reconciliation report
    GET    /supply-chain/lots/{lot_number}/trace                 - Lot traceability
    GET    /supply-chain/forecast                                - Supply forecast
    GET    /supply-chain/expiring                                - Expiring inventory items
    GET    /supply-chain/metrics                                 - Supply chain dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.supply_chain import (
    DrugProduct,
    DrugProductCreate,
    DrugProductListResponse,
    DrugProductUpdate,
    ExpiringItemsResponse,
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryListResponse,
    KitAssignRequest,
    KitAssignment,
    KitAssignmentListResponse,
    KitReconciliation,
    KitType,
    LotTrace,
    Shipment,
    ShipmentCreate,
    ShipmentListResponse,
    ShipmentStatus,
    ShipmentUpdate,
    SupplyForecastResponse,
    SupplyMetrics,
    SupplyStatus,
    TemperatureExcursion,
    TemperatureExcursionListResponse,
    TemperatureExcursionReport,
    TemperatureExcursionSeverity,
    TemperatureReading,
)
from app.services.supply_chain_service import get_supply_chain_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/supply-chain",
    tags=["Supply Chain"],
)


# ---------------------------------------------------------------------------
# Drug Product CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/drug-products",
    response_model=DrugProductListResponse,
    summary="List drug products",
    description="Retrieve all investigational medicinal products tracked in the supply chain.",
)
async def list_drug_products() -> DrugProductListResponse:
    svc = get_supply_chain_service()
    items = svc.list_drug_products()
    return DrugProductListResponse(items=items, total=len(items))


@router.get(
    "/drug-products/{product_id}",
    response_model=DrugProduct,
    summary="Get a drug product",
)
async def get_drug_product(product_id: str) -> DrugProduct:
    svc = get_supply_chain_service()
    try:
        return svc.get_drug_product(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Drug product '{product_id}' not found")


@router.post(
    "/drug-products",
    response_model=DrugProduct,
    status_code=201,
    summary="Create a drug product",
)
async def create_drug_product(payload: DrugProductCreate) -> DrugProduct:
    svc = get_supply_chain_service()
    return svc.create_drug_product(payload)


@router.put(
    "/drug-products/{product_id}",
    response_model=DrugProduct,
    summary="Update a drug product",
)
async def update_drug_product(product_id: str, payload: DrugProductUpdate) -> DrugProduct:
    svc = get_supply_chain_service()
    try:
        return svc.update_drug_product(product_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Drug product '{product_id}' not found")


@router.delete(
    "/drug-products/{product_id}",
    status_code=204,
    summary="Delete a drug product",
)
async def delete_drug_product(product_id: str) -> None:
    svc = get_supply_chain_service()
    try:
        svc.delete_drug_product(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Drug product '{product_id}' not found")


# ---------------------------------------------------------------------------
# Inventory CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/inventory",
    response_model=InventoryListResponse,
    summary="List inventory items",
    description="Retrieve inventory items with optional filtering by site, drug product, and status.",
)
async def list_inventory(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    drug_product_id: Optional[str] = Query(None, description="Filter by drug product ID"),
    status: Optional[SupplyStatus] = Query(None, description="Filter by inventory status"),
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> InventoryListResponse:
    svc = get_supply_chain_service()
    items, total = svc.list_inventory(
        site_id=site_id,
        drug_product_id=drug_product_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return InventoryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/inventory/{item_id}",
    response_model=InventoryItem,
    summary="Get an inventory item",
)
async def get_inventory_item(item_id: str) -> InventoryItem:
    svc = get_supply_chain_service()
    try:
        return svc.get_inventory_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Inventory item '{item_id}' not found")


@router.post(
    "/inventory",
    response_model=InventoryItem,
    status_code=201,
    summary="Create an inventory item",
)
async def create_inventory_item(payload: InventoryItemCreate) -> InventoryItem:
    svc = get_supply_chain_service()
    return svc.create_inventory_item(payload)


@router.put(
    "/inventory/{item_id}",
    response_model=InventoryItem,
    summary="Update an inventory item",
)
async def update_inventory_item(item_id: str, payload: InventoryItemUpdate) -> InventoryItem:
    svc = get_supply_chain_service()
    try:
        return svc.update_inventory_item(item_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Inventory item '{item_id}' not found")


@router.delete(
    "/inventory/{item_id}",
    status_code=204,
    summary="Delete an inventory item",
)
async def delete_inventory_item(item_id: str) -> None:
    svc = get_supply_chain_service()
    try:
        svc.delete_inventory_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Inventory item '{item_id}' not found")


# ---------------------------------------------------------------------------
# Shipment CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/shipments",
    response_model=ShipmentListResponse,
    summary="List shipments",
    description="Retrieve shipments with optional filtering by status and drug product.",
)
async def list_shipments(
    status: Optional[ShipmentStatus] = Query(None, description="Filter by shipment status"),
    drug_product_id: Optional[str] = Query(None, description="Filter by drug product ID"),
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ShipmentListResponse:
    svc = get_supply_chain_service()
    items, total = svc.list_shipments(
        status=status,
        drug_product_id=drug_product_id,
        limit=limit,
        offset=offset,
    )
    return ShipmentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/shipments/{shipment_id}",
    response_model=Shipment,
    summary="Get a shipment",
)
async def get_shipment(shipment_id: str) -> Shipment:
    svc = get_supply_chain_service()
    try:
        return svc.get_shipment(shipment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


@router.post(
    "/shipments",
    response_model=Shipment,
    status_code=201,
    summary="Create a shipment",
)
async def create_shipment(payload: ShipmentCreate) -> Shipment:
    svc = get_supply_chain_service()
    return svc.create_shipment(payload)


@router.put(
    "/shipments/{shipment_id}",
    response_model=Shipment,
    summary="Update a shipment",
)
async def update_shipment(shipment_id: str, payload: ShipmentUpdate) -> Shipment:
    svc = get_supply_chain_service()
    try:
        return svc.update_shipment(shipment_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


@router.post(
    "/shipments/{shipment_id}/deliver",
    response_model=Shipment,
    summary="Mark shipment as delivered",
    description="Transition a shipment to delivered status. Only valid for pending or in_transit shipments.",
)
async def deliver_shipment(shipment_id: str) -> Shipment:
    svc = get_supply_chain_service()
    try:
        return svc.deliver_shipment(shipment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/shipments/{shipment_id}",
    status_code=204,
    summary="Delete a shipment",
)
async def delete_shipment(shipment_id: str) -> None:
    svc = get_supply_chain_service()
    try:
        svc.delete_shipment(shipment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


# ---------------------------------------------------------------------------
# Temperature Excursion Management
# ---------------------------------------------------------------------------


@router.get(
    "/excursions",
    response_model=TemperatureExcursionListResponse,
    summary="List temperature excursions",
    description="Retrieve temperature excursions with optional filtering by severity and time window.",
)
async def list_temperature_excursions(
    severity: Optional[TemperatureExcursionSeverity] = Query(
        None, description="Filter by excursion severity"
    ),
    days: Optional[int] = Query(None, ge=1, description="Filter excursions within last N days"),
) -> TemperatureExcursionListResponse:
    svc = get_supply_chain_service()
    items = svc.list_temperature_excursions(severity=severity, days=days)
    return TemperatureExcursionListResponse(items=items, total=len(items))


@router.get(
    "/excursions/{excursion_id}",
    response_model=TemperatureExcursion,
    summary="Get a temperature excursion",
)
async def get_temperature_excursion(excursion_id: str) -> TemperatureExcursion:
    svc = get_supply_chain_service()
    try:
        return svc.get_temperature_excursion(excursion_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Temperature excursion '{excursion_id}' not found"
        )


@router.post(
    "/shipments/{shipment_id}/excursions",
    response_model=TemperatureExcursion,
    status_code=201,
    summary="Report a temperature excursion for a shipment",
    description="Report a temperature excursion event during shipment transit.",
)
async def report_temperature_excursion(
    shipment_id: str, payload: TemperatureExcursionReport
) -> TemperatureExcursion:
    svc = get_supply_chain_service()
    try:
        return svc.report_temperature_excursion(shipment_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


@router.get(
    "/shipments/{shipment_id}/temperature-compliance",
    response_model=list[TemperatureReading],
    summary="Check temperature compliance for a shipment",
    description="Return temperature readings that are out of the acceptable range for the shipped drug product.",
)
async def check_temperature_compliance(shipment_id: str) -> list[TemperatureReading]:
    svc = get_supply_chain_service()
    try:
        return svc.check_temperature_compliance(shipment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


# ---------------------------------------------------------------------------
# Kit Assignment Management
# ---------------------------------------------------------------------------


@router.get(
    "/kits/reconciliation",
    response_model=KitReconciliation,
    summary="Get kit reconciliation report",
    description="Generate a kit reconciliation report with breakdowns by kit type and site.",
)
async def get_kit_reconciliation(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> KitReconciliation:
    svc = get_supply_chain_service()
    return svc.get_kit_reconciliation(site_id=site_id)


@router.get(
    "/kits",
    response_model=KitAssignmentListResponse,
    summary="List kit assignments",
    description="Retrieve kit assignments with optional filtering by site, kit type, and patient.",
)
async def list_kit_assignments(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    kit_type: Optional[KitType] = Query(None, description="Filter by kit type"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> KitAssignmentListResponse:
    svc = get_supply_chain_service()
    items = svc.list_kit_assignments(site_id=site_id, kit_type=kit_type, patient_id=patient_id)
    return KitAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/kits/{kit_id}",
    response_model=KitAssignment,
    summary="Get a kit assignment",
)
async def get_kit_assignment(kit_id: str) -> KitAssignment:
    svc = get_supply_chain_service()
    try:
        return svc.get_kit_assignment(kit_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Kit assignment '{kit_id}' not found")


@router.post(
    "/kits",
    response_model=KitAssignment,
    status_code=201,
    summary="Assign a kit to a patient",
)
async def assign_kit(payload: KitAssignRequest) -> KitAssignment:
    svc = get_supply_chain_service()
    return svc.assign_kit(payload)


@router.post(
    "/kits/{kit_id}/return",
    response_model=KitAssignment,
    summary="Record kit return",
    description="Record that a kit has been returned by the patient.",
)
async def return_kit(kit_id: str) -> KitAssignment:
    svc = get_supply_chain_service()
    try:
        return svc.return_kit(kit_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Kit assignment '{kit_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Lot Traceability
# ---------------------------------------------------------------------------


@router.get(
    "/lots/{lot_number}/trace",
    response_model=LotTrace,
    summary="Trace a lot number",
    description="Trace all usage of a specific lot number across inventory, shipments, "
    "patient exposures, and temperature excursions.",
)
async def trace_lot(lot_number: str) -> LotTrace:
    svc = get_supply_chain_service()
    try:
        return svc.trace_lot(lot_number)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Lot number '{lot_number}' not found")


# ---------------------------------------------------------------------------
# Supply Forecasting & Expiry
# ---------------------------------------------------------------------------


@router.get(
    "/forecast",
    response_model=SupplyForecastResponse,
    summary="Get supply forecast",
    description="Generate supply forecasts based on historical consumption rates. "
    "Identifies sites at risk of running out of stock.",
)
async def get_supply_forecast(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    drug_product_id: Optional[str] = Query(None, description="Filter by drug product ID"),
) -> SupplyForecastResponse:
    svc = get_supply_chain_service()
    return svc.get_supply_forecast(site_id=site_id, drug_product_id=drug_product_id)


@router.get(
    "/expiring",
    response_model=ExpiringItemsResponse,
    summary="Get expiring inventory items",
    description="Retrieve inventory items expiring within a specified time window.",
)
async def get_expiring_items(
    days: int = Query(90, ge=1, le=730, description="Days until expiry threshold"),
) -> ExpiringItemsResponse:
    svc = get_supply_chain_service()
    return svc.get_expiring_items(days=days)


# ---------------------------------------------------------------------------
# Metrics Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SupplyMetrics,
    summary="Get supply chain dashboard metrics",
    description="Aggregated supply chain metrics including inventory levels, "
    "active shipments, temperature excursions, and forecasting summaries.",
)
async def get_metrics() -> SupplyMetrics:
    svc = get_supply_chain_service()
    return svc.get_metrics()
