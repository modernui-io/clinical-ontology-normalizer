"""Clinical Supply Forecasting API endpoints (SUPPLY-FCST).

Provides comprehensive clinical supply forecasting operations: demand forecast
management, supply plan lifecycle, inventory projection tracking, expiry risk
monitoring, depot allocation planning, and supply forecasting metrics.

Endpoints:
    GET    /clinical-supply-forecast/demand-forecasts                     - List demand forecasts
    GET    /clinical-supply-forecast/demand-forecasts/{forecast_id}       - Get single demand forecast
    POST   /clinical-supply-forecast/demand-forecasts                     - Create demand forecast
    PUT    /clinical-supply-forecast/demand-forecasts/{forecast_id}       - Update demand forecast
    DELETE /clinical-supply-forecast/demand-forecasts/{forecast_id}       - Delete demand forecast
    GET    /clinical-supply-forecast/supply-plans                         - List supply plans
    GET    /clinical-supply-forecast/supply-plans/{plan_id}               - Get single supply plan
    POST   /clinical-supply-forecast/supply-plans                         - Create supply plan
    PUT    /clinical-supply-forecast/supply-plans/{plan_id}               - Update supply plan
    DELETE /clinical-supply-forecast/supply-plans/{plan_id}               - Delete supply plan
    GET    /clinical-supply-forecast/inventory-projections                - List inventory projections
    GET    /clinical-supply-forecast/inventory-projections/{projection_id} - Get single projection
    POST   /clinical-supply-forecast/inventory-projections                - Create inventory projection
    PUT    /clinical-supply-forecast/inventory-projections/{projection_id} - Update projection
    DELETE /clinical-supply-forecast/inventory-projections/{projection_id} - Delete projection
    GET    /clinical-supply-forecast/expiry-risks                         - List expiry risks
    GET    /clinical-supply-forecast/expiry-risks/{expiry_risk_id}        - Get single expiry risk
    POST   /clinical-supply-forecast/expiry-risks                         - Create expiry risk
    PUT    /clinical-supply-forecast/expiry-risks/{expiry_risk_id}        - Update expiry risk
    DELETE /clinical-supply-forecast/expiry-risks/{expiry_risk_id}        - Delete expiry risk
    GET    /clinical-supply-forecast/depot-allocations                    - List depot allocations
    GET    /clinical-supply-forecast/depot-allocations/{allocation_id}    - Get single allocation
    POST   /clinical-supply-forecast/depot-allocations                    - Create depot allocation
    PUT    /clinical-supply-forecast/depot-allocations/{allocation_id}    - Update depot allocation
    DELETE /clinical-supply-forecast/depot-allocations/{allocation_id}    - Delete depot allocation
    GET    /clinical-supply-forecast/metrics                              - Supply forecast metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_supply_forecast import (
    ClinicalSupplyForecastMetrics,
    DemandForecast,
    DemandForecastCreate,
    DemandForecastListResponse,
    DemandForecastUpdate,
    DepotAllocation,
    DepotAllocationCreate,
    DepotAllocationListResponse,
    DepotAllocationUpdate,
    ExpiryRisk,
    ExpiryRiskCreate,
    ExpiryRiskListResponse,
    ExpiryRiskUpdate,
    ForecastStatus,
    ForecastType,
    InventoryProjection,
    InventoryProjectionCreate,
    InventoryProjectionListResponse,
    InventoryProjectionUpdate,
    SupplyPlan,
    SupplyPlanCreate,
    SupplyPlanListResponse,
    SupplyPlanUpdate,
    SupplyRisk,
)
from app.services.clinical_supply_forecast_service import (
    get_clinical_supply_forecast_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-supply-forecast",
    tags=["Clinical Supply Forecast"],
)


# ---------------------------------------------------------------------------
# Demand Forecasts
# ---------------------------------------------------------------------------


@router.get(
    "/demand-forecasts",
    response_model=DemandForecastListResponse,
    summary="List demand forecasts",
    description="Retrieve demand forecasts with optional filtering by trial, type, and status.",
)
async def list_demand_forecasts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    forecast_type: Optional[ForecastType] = Query(None, description="Filter by forecast type"),
    status: Optional[ForecastStatus] = Query(None, description="Filter by status"),
) -> DemandForecastListResponse:
    svc = get_clinical_supply_forecast_service()
    items = svc.list_demand_forecasts(
        trial_id=trial_id, forecast_type=forecast_type, status=status
    )
    return DemandForecastListResponse(items=items, total=len(items))


@router.get(
    "/demand-forecasts/{forecast_id}",
    response_model=DemandForecast,
    summary="Get a demand forecast",
)
async def get_demand_forecast(forecast_id: str) -> DemandForecast:
    svc = get_clinical_supply_forecast_service()
    forecast = svc.get_demand_forecast(forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail=f"Demand forecast '{forecast_id}' not found")
    return forecast


@router.post(
    "/demand-forecasts",
    response_model=DemandForecast,
    status_code=201,
    summary="Create a demand forecast",
)
async def create_demand_forecast(payload: DemandForecastCreate) -> DemandForecast:
    svc = get_clinical_supply_forecast_service()
    return svc.create_demand_forecast(payload)


@router.put(
    "/demand-forecasts/{forecast_id}",
    response_model=DemandForecast,
    summary="Update a demand forecast",
)
async def update_demand_forecast(
    forecast_id: str, payload: DemandForecastUpdate
) -> DemandForecast:
    svc = get_clinical_supply_forecast_service()
    updated = svc.update_demand_forecast(forecast_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Demand forecast '{forecast_id}' not found")
    return updated


@router.delete(
    "/demand-forecasts/{forecast_id}",
    status_code=204,
    summary="Delete a demand forecast",
)
async def delete_demand_forecast(forecast_id: str) -> None:
    svc = get_clinical_supply_forecast_service()
    deleted = svc.delete_demand_forecast(forecast_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Demand forecast '{forecast_id}' not found")


# ---------------------------------------------------------------------------
# Supply Plans
# ---------------------------------------------------------------------------


@router.get(
    "/supply-plans",
    response_model=SupplyPlanListResponse,
    summary="List supply plans",
    description="Retrieve supply plans with optional filtering by trial, status, and risk level.",
)
async def list_supply_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ForecastStatus] = Query(None, description="Filter by status"),
    risk_level: Optional[SupplyRisk] = Query(None, description="Filter by risk level"),
) -> SupplyPlanListResponse:
    svc = get_clinical_supply_forecast_service()
    items = svc.list_supply_plans(trial_id=trial_id, status=status, risk_level=risk_level)
    return SupplyPlanListResponse(items=items, total=len(items))


@router.get(
    "/supply-plans/{plan_id}",
    response_model=SupplyPlan,
    summary="Get a supply plan",
)
async def get_supply_plan(plan_id: str) -> SupplyPlan:
    svc = get_clinical_supply_forecast_service()
    plan = svc.get_supply_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Supply plan '{plan_id}' not found")
    return plan


@router.post(
    "/supply-plans",
    response_model=SupplyPlan,
    status_code=201,
    summary="Create a supply plan",
)
async def create_supply_plan(payload: SupplyPlanCreate) -> SupplyPlan:
    svc = get_clinical_supply_forecast_service()
    return svc.create_supply_plan(payload)


@router.put(
    "/supply-plans/{plan_id}",
    response_model=SupplyPlan,
    summary="Update a supply plan",
)
async def update_supply_plan(plan_id: str, payload: SupplyPlanUpdate) -> SupplyPlan:
    svc = get_clinical_supply_forecast_service()
    updated = svc.update_supply_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Supply plan '{plan_id}' not found")
    return updated


@router.delete(
    "/supply-plans/{plan_id}",
    status_code=204,
    summary="Delete a supply plan",
)
async def delete_supply_plan(plan_id: str) -> None:
    svc = get_clinical_supply_forecast_service()
    deleted = svc.delete_supply_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Supply plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Inventory Projections
# ---------------------------------------------------------------------------


@router.get(
    "/inventory-projections",
    response_model=InventoryProjectionListResponse,
    summary="List inventory projections",
    description="Retrieve inventory projections with optional filtering by trial, site, and stockout risk.",
)
async def list_inventory_projections(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    stockout_risk: Optional[SupplyRisk] = Query(None, description="Filter by stockout risk level"),
) -> InventoryProjectionListResponse:
    svc = get_clinical_supply_forecast_service()
    items = svc.list_inventory_projections(
        trial_id=trial_id, site_id=site_id, stockout_risk=stockout_risk
    )
    return InventoryProjectionListResponse(items=items, total=len(items))


@router.get(
    "/inventory-projections/{projection_id}",
    response_model=InventoryProjection,
    summary="Get an inventory projection",
)
async def get_inventory_projection(projection_id: str) -> InventoryProjection:
    svc = get_clinical_supply_forecast_service()
    projection = svc.get_inventory_projection(projection_id)
    if projection is None:
        raise HTTPException(
            status_code=404, detail=f"Inventory projection '{projection_id}' not found"
        )
    return projection


@router.post(
    "/inventory-projections",
    response_model=InventoryProjection,
    status_code=201,
    summary="Create an inventory projection",
)
async def create_inventory_projection(
    payload: InventoryProjectionCreate,
) -> InventoryProjection:
    svc = get_clinical_supply_forecast_service()
    return svc.create_inventory_projection(payload)


@router.put(
    "/inventory-projections/{projection_id}",
    response_model=InventoryProjection,
    summary="Update an inventory projection",
)
async def update_inventory_projection(
    projection_id: str, payload: InventoryProjectionUpdate
) -> InventoryProjection:
    svc = get_clinical_supply_forecast_service()
    updated = svc.update_inventory_projection(projection_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Inventory projection '{projection_id}' not found"
        )
    return updated


@router.delete(
    "/inventory-projections/{projection_id}",
    status_code=204,
    summary="Delete an inventory projection",
)
async def delete_inventory_projection(projection_id: str) -> None:
    svc = get_clinical_supply_forecast_service()
    deleted = svc.delete_inventory_projection(projection_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Inventory projection '{projection_id}' not found"
        )


# ---------------------------------------------------------------------------
# Expiry Risks
# ---------------------------------------------------------------------------


@router.get(
    "/expiry-risks",
    response_model=ExpiryRiskListResponse,
    summary="List expiry risks",
    description="Retrieve expiry risks with optional filtering by trial, risk level, and resolved status.",
)
async def list_expiry_risks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    risk_level: Optional[SupplyRisk] = Query(None, description="Filter by risk level"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
) -> ExpiryRiskListResponse:
    svc = get_clinical_supply_forecast_service()
    items = svc.list_expiry_risks(trial_id=trial_id, risk_level=risk_level, resolved=resolved)
    return ExpiryRiskListResponse(items=items, total=len(items))


@router.get(
    "/expiry-risks/{expiry_risk_id}",
    response_model=ExpiryRisk,
    summary="Get an expiry risk",
)
async def get_expiry_risk(expiry_risk_id: str) -> ExpiryRisk:
    svc = get_clinical_supply_forecast_service()
    risk = svc.get_expiry_risk(expiry_risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail=f"Expiry risk '{expiry_risk_id}' not found")
    return risk


@router.post(
    "/expiry-risks",
    response_model=ExpiryRisk,
    status_code=201,
    summary="Create an expiry risk",
)
async def create_expiry_risk(payload: ExpiryRiskCreate) -> ExpiryRisk:
    svc = get_clinical_supply_forecast_service()
    return svc.create_expiry_risk(payload)


@router.put(
    "/expiry-risks/{expiry_risk_id}",
    response_model=ExpiryRisk,
    summary="Update an expiry risk",
)
async def update_expiry_risk(
    expiry_risk_id: str, payload: ExpiryRiskUpdate
) -> ExpiryRisk:
    svc = get_clinical_supply_forecast_service()
    updated = svc.update_expiry_risk(expiry_risk_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Expiry risk '{expiry_risk_id}' not found")
    return updated


@router.delete(
    "/expiry-risks/{expiry_risk_id}",
    status_code=204,
    summary="Delete an expiry risk",
)
async def delete_expiry_risk(expiry_risk_id: str) -> None:
    svc = get_clinical_supply_forecast_service()
    deleted = svc.delete_expiry_risk(expiry_risk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Expiry risk '{expiry_risk_id}' not found")


# ---------------------------------------------------------------------------
# Depot Allocations
# ---------------------------------------------------------------------------


@router.get(
    "/depot-allocations",
    response_model=DepotAllocationListResponse,
    summary="List depot allocations",
    description="Retrieve depot allocations with optional filtering by trial, region, and active status.",
)
async def list_depot_allocations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    region: Optional[str] = Query(None, description="Filter by region"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> DepotAllocationListResponse:
    svc = get_clinical_supply_forecast_service()
    items = svc.list_depot_allocations(trial_id=trial_id, region=region, is_active=is_active)
    return DepotAllocationListResponse(items=items, total=len(items))


@router.get(
    "/depot-allocations/{allocation_id}",
    response_model=DepotAllocation,
    summary="Get a depot allocation",
)
async def get_depot_allocation(allocation_id: str) -> DepotAllocation:
    svc = get_clinical_supply_forecast_service()
    allocation = svc.get_depot_allocation(allocation_id)
    if allocation is None:
        raise HTTPException(
            status_code=404, detail=f"Depot allocation '{allocation_id}' not found"
        )
    return allocation


@router.post(
    "/depot-allocations",
    response_model=DepotAllocation,
    status_code=201,
    summary="Create a depot allocation",
)
async def create_depot_allocation(payload: DepotAllocationCreate) -> DepotAllocation:
    svc = get_clinical_supply_forecast_service()
    return svc.create_depot_allocation(payload)


@router.put(
    "/depot-allocations/{allocation_id}",
    response_model=DepotAllocation,
    summary="Update a depot allocation",
)
async def update_depot_allocation(
    allocation_id: str, payload: DepotAllocationUpdate
) -> DepotAllocation:
    svc = get_clinical_supply_forecast_service()
    updated = svc.update_depot_allocation(allocation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Depot allocation '{allocation_id}' not found"
        )
    return updated


@router.delete(
    "/depot-allocations/{allocation_id}",
    status_code=204,
    summary="Delete a depot allocation",
)
async def delete_depot_allocation(allocation_id: str) -> None:
    svc = get_clinical_supply_forecast_service()
    deleted = svc.delete_depot_allocation(allocation_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Depot allocation '{allocation_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalSupplyForecastMetrics,
    summary="Get clinical supply forecast metrics",
    description="Aggregated clinical supply forecasting metrics across all entities.",
)
async def get_metrics() -> ClinicalSupplyForecastMetrics:
    svc = get_clinical_supply_forecast_service()
    return svc.get_metrics()
