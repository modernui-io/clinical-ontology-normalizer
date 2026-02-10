"""Clinical Supply Forecasting API endpoints (CLINICAL-8).

Provides comprehensive drug supply forecasting operations: supply forecast
lifecycle management, demand projection modeling, supply plan ordering,
inventory snapshot tracking, resupply alert management, supply risk assessment,
site inventory status aggregation, and operational metrics.

Endpoints:
    GET    /supply-forecasting/forecasts                                  - List forecasts
    GET    /supply-forecasting/forecasts/{forecast_id}                    - Get single forecast
    POST   /supply-forecasting/forecasts                                  - Create forecast
    PUT    /supply-forecasting/forecasts/{forecast_id}                    - Update forecast
    DELETE /supply-forecasting/forecasts/{forecast_id}                    - Delete forecast
    POST   /supply-forecasting/forecasts/{forecast_id}/generate           - Generate/recalculate forecast
    GET    /supply-forecasting/demand-projections                         - List demand projections
    GET    /supply-forecasting/demand-projections/{projection_id}         - Get single projection
    POST   /supply-forecasting/demand-projections                         - Create projection
    DELETE /supply-forecasting/demand-projections/{projection_id}         - Delete projection
    GET    /supply-forecasting/supply-plans                               - List supply plans
    GET    /supply-forecasting/supply-plans/{plan_id}                     - Get single plan
    POST   /supply-forecasting/supply-plans                               - Create supply plan
    PUT    /supply-forecasting/supply-plans/{plan_id}                     - Update supply plan
    DELETE /supply-forecasting/supply-plans/{plan_id}                     - Delete supply plan
    GET    /supply-forecasting/inventory-snapshots                        - List snapshots
    GET    /supply-forecasting/inventory-snapshots/{snapshot_id}          - Get single snapshot
    DELETE /supply-forecasting/inventory-snapshots/{snapshot_id}          - Delete snapshot
    GET    /supply-forecasting/resupply-alerts                            - List resupply alerts
    GET    /supply-forecasting/resupply-alerts/{alert_id}                 - Get single alert
    POST   /supply-forecasting/resupply-alerts/{alert_id}/acknowledge     - Acknowledge alert
    POST   /supply-forecasting/resupply-alerts/trigger                    - Trigger manual resupply
    GET    /supply-forecasting/risk-assessments                           - List risk assessments
    GET    /supply-forecasting/risk-assessments/{assessment_id}           - Get single assessment
    POST   /supply-forecasting/risk-assessments                           - Create assessment
    PUT    /supply-forecasting/risk-assessments/{assessment_id}           - Update assessment
    DELETE /supply-forecasting/risk-assessments/{assessment_id}           - Delete assessment
    GET    /supply-forecasting/forecasts/{forecast_id}/risks              - Assess forecast risks
    GET    /supply-forecasting/sites/{site_id}/inventory-status           - Site inventory status
    GET    /supply-forecasting/metrics                                    - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.supply_forecasting import (
    DemandProjection,
    DemandProjectionCreate,
    DemandProjectionListResponse,
    DemandScenario,
    ForecastStatus,
    InventorySnapshot,
    InventorySnapshotListResponse,
    ResupplyAlert,
    ResupplyAlertAcknowledge,
    ResupplyAlertListResponse,
    ResupplyTriggerType,
    RiskAssessmentStatus,
    SiteInventoryStatus,
    SupplyForecast,
    SupplyForecastCreate,
    SupplyForecastingMetrics,
    SupplyForecastListResponse,
    SupplyForecastUpdate,
    SupplyPlan,
    SupplyPlanCreate,
    SupplyPlanListResponse,
    SupplyPlanStatus,
    SupplyPlanUpdate,
    SupplyRiskAssessment,
    SupplyRiskAssessmentCreate,
    SupplyRiskAssessmentListResponse,
    SupplyRiskAssessmentUpdate,
)
from app.services.supply_forecasting_service import get_supply_forecasting_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/supply-forecasting",
    tags=["Supply Forecasting"],
)


# ---------------------------------------------------------------------------
# Supply Forecast Management
# ---------------------------------------------------------------------------


@router.get(
    "/forecasts",
    response_model=SupplyForecastListResponse,
    summary="List supply forecasts",
    description="Retrieve supply forecasts with optional filtering by trial, status, and scenario.",
)
async def list_forecasts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ForecastStatus] = Query(None, description="Filter by forecast status"),
    scenario: Optional[DemandScenario] = Query(None, description="Filter by demand scenario"),
) -> SupplyForecastListResponse:
    svc = get_supply_forecasting_service()
    items = svc.list_forecasts(trial_id=trial_id, status=status, scenario=scenario)
    return SupplyForecastListResponse(items=items, total=len(items))


@router.get(
    "/forecasts/{forecast_id}",
    response_model=SupplyForecast,
    summary="Get a supply forecast",
)
async def get_forecast(forecast_id: str) -> SupplyForecast:
    svc = get_supply_forecasting_service()
    forecast = svc.get_forecast(forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail=f"Forecast '{forecast_id}' not found")
    return forecast


@router.post(
    "/forecasts",
    response_model=SupplyForecast,
    status_code=201,
    summary="Create a supply forecast",
)
async def create_forecast(payload: SupplyForecastCreate) -> SupplyForecast:
    svc = get_supply_forecasting_service()
    return svc.create_forecast(payload)


@router.put(
    "/forecasts/{forecast_id}",
    response_model=SupplyForecast,
    summary="Update a supply forecast",
)
async def update_forecast(forecast_id: str, payload: SupplyForecastUpdate) -> SupplyForecast:
    svc = get_supply_forecasting_service()
    updated = svc.update_forecast(forecast_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Forecast '{forecast_id}' not found")
    return updated


@router.delete(
    "/forecasts/{forecast_id}",
    status_code=204,
    summary="Delete a supply forecast",
)
async def delete_forecast(forecast_id: str) -> None:
    svc = get_supply_forecasting_service()
    deleted = svc.delete_forecast(forecast_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Forecast '{forecast_id}' not found")


@router.post(
    "/forecasts/{forecast_id}/generate",
    response_model=SupplyForecast,
    summary="Generate/recalculate a supply forecast",
    description="Aggregate demand projections and supply plans to compute projected "
                "demand, supply, months of supply, and risk level.",
)
async def generate_forecast(forecast_id: str) -> SupplyForecast:
    svc = get_supply_forecasting_service()
    result = svc.generate_forecast(forecast_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Forecast '{forecast_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Demand Projections
# ---------------------------------------------------------------------------


@router.get(
    "/demand-projections",
    response_model=DemandProjectionListResponse,
    summary="List demand projections",
    description="Retrieve demand projections with optional filtering by forecast.",
)
async def list_demand_projections(
    forecast_id: Optional[str] = Query(None, description="Filter by forecast ID"),
) -> DemandProjectionListResponse:
    svc = get_supply_forecasting_service()
    items = svc.list_demand_projections(forecast_id=forecast_id)
    return DemandProjectionListResponse(items=items, total=len(items))


@router.get(
    "/demand-projections/{projection_id}",
    response_model=DemandProjection,
    summary="Get a demand projection",
)
async def get_demand_projection(projection_id: str) -> DemandProjection:
    svc = get_supply_forecasting_service()
    projection = svc.get_demand_projection(projection_id)
    if projection is None:
        raise HTTPException(status_code=404, detail=f"Demand projection '{projection_id}' not found")
    return projection


@router.post(
    "/demand-projections",
    response_model=DemandProjection,
    status_code=201,
    summary="Create a demand projection",
    description="Create a demand projection for a forecast period. "
                "Automatically computes total doses and units required.",
)
async def create_demand_projection(payload: DemandProjectionCreate) -> DemandProjection:
    svc = get_supply_forecasting_service()
    result = svc.create_demand_projection(payload)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Forecast '{payload.forecast_id}' not found",
        )
    return result


@router.delete(
    "/demand-projections/{projection_id}",
    status_code=204,
    summary="Delete a demand projection",
)
async def delete_demand_projection(projection_id: str) -> None:
    svc = get_supply_forecasting_service()
    deleted = svc.delete_demand_projection(projection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Demand projection '{projection_id}' not found")


# ---------------------------------------------------------------------------
# Supply Plans
# ---------------------------------------------------------------------------


@router.get(
    "/supply-plans",
    response_model=SupplyPlanListResponse,
    summary="List supply plans",
    description="Retrieve supply plan orders with optional filtering by forecast and status.",
)
async def list_supply_plans(
    forecast_id: Optional[str] = Query(None, description="Filter by forecast ID"),
    status: Optional[SupplyPlanStatus] = Query(None, description="Filter by order status"),
) -> SupplyPlanListResponse:
    svc = get_supply_forecasting_service()
    items = svc.list_supply_plans(forecast_id=forecast_id, status=status)
    return SupplyPlanListResponse(items=items, total=len(items))


@router.get(
    "/supply-plans/{plan_id}",
    response_model=SupplyPlan,
    summary="Get a supply plan",
)
async def get_supply_plan(plan_id: str) -> SupplyPlan:
    svc = get_supply_forecasting_service()
    plan = svc.get_supply_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Supply plan '{plan_id}' not found")
    return plan


@router.post(
    "/supply-plans",
    response_model=SupplyPlan,
    status_code=201,
    summary="Create a supply plan order",
)
async def create_supply_plan(payload: SupplyPlanCreate) -> SupplyPlan:
    svc = get_supply_forecasting_service()
    result = svc.create_supply_plan(payload)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Forecast '{payload.forecast_id}' not found",
        )
    return result


@router.put(
    "/supply-plans/{plan_id}",
    response_model=SupplyPlan,
    summary="Update a supply plan order",
)
async def update_supply_plan(plan_id: str, payload: SupplyPlanUpdate) -> SupplyPlan:
    svc = get_supply_forecasting_service()
    updated = svc.update_supply_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Supply plan '{plan_id}' not found")
    return updated


@router.delete(
    "/supply-plans/{plan_id}",
    status_code=204,
    summary="Delete a supply plan order",
)
async def delete_supply_plan(plan_id: str) -> None:
    svc = get_supply_forecasting_service()
    deleted = svc.delete_supply_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Supply plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Inventory Snapshots
# ---------------------------------------------------------------------------


@router.get(
    "/inventory-snapshots",
    response_model=InventorySnapshotListResponse,
    summary="List inventory snapshots",
    description="Retrieve inventory snapshots with optional filtering by trial, site, and product.",
)
async def list_inventory_snapshots(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> InventorySnapshotListResponse:
    svc = get_supply_forecasting_service()
    items = svc.list_inventory_snapshots(
        trial_id=trial_id, site_id=site_id, product_name=product_name
    )
    return InventorySnapshotListResponse(items=items, total=len(items))


@router.get(
    "/inventory-snapshots/{snapshot_id}",
    response_model=InventorySnapshot,
    summary="Get an inventory snapshot",
)
async def get_inventory_snapshot(snapshot_id: str) -> InventorySnapshot:
    svc = get_supply_forecasting_service()
    snapshot = svc.get_inventory_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Inventory snapshot '{snapshot_id}' not found")
    return snapshot


@router.delete(
    "/inventory-snapshots/{snapshot_id}",
    status_code=204,
    summary="Delete an inventory snapshot",
)
async def delete_inventory_snapshot(snapshot_id: str) -> None:
    svc = get_supply_forecasting_service()
    deleted = svc.delete_inventory_snapshot(snapshot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Inventory snapshot '{snapshot_id}' not found")


# ---------------------------------------------------------------------------
# Resupply Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/resupply-alerts",
    response_model=ResupplyAlertListResponse,
    summary="List resupply alerts",
    description="Retrieve resupply alerts with optional filtering by trial, site, and acknowledgment status.",
)
async def list_resupply_alerts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
) -> ResupplyAlertListResponse:
    svc = get_supply_forecasting_service()
    items = svc.list_resupply_alerts(
        trial_id=trial_id, site_id=site_id, acknowledged=acknowledged
    )
    return ResupplyAlertListResponse(items=items, total=len(items))


@router.get(
    "/resupply-alerts/{alert_id}",
    response_model=ResupplyAlert,
    summary="Get a resupply alert",
)
async def get_resupply_alert(alert_id: str) -> ResupplyAlert:
    svc = get_supply_forecasting_service()
    alert = svc.get_resupply_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Resupply alert '{alert_id}' not found")
    return alert


@router.post(
    "/resupply-alerts/{alert_id}/acknowledge",
    response_model=ResupplyAlert,
    summary="Acknowledge a resupply alert",
)
async def acknowledge_resupply_alert(
    alert_id: str, payload: ResupplyAlertAcknowledge
) -> ResupplyAlert:
    svc = get_supply_forecasting_service()
    try:
        result = svc.acknowledge_resupply_alert(alert_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Resupply alert '{alert_id}' not found")
    return result


@router.post(
    "/resupply-alerts/trigger",
    response_model=ResupplyAlert,
    status_code=201,
    summary="Trigger a manual resupply alert",
    description="Create a resupply alert for a specific trial, site, and product.",
)
async def trigger_resupply(
    trial_id: str = Query(..., description="Trial ID"),
    site_id: str = Query(..., description="Site ID"),
    product_name: str = Query(..., description="Product name"),
    current_level: int = Query(..., ge=0, description="Current inventory level"),
    threshold_level: int = Query(..., ge=0, description="Threshold level"),
    recommended_quantity: int = Query(..., ge=1, description="Recommended resupply quantity"),
    trigger_type: ResupplyTriggerType = Query(
        ResupplyTriggerType.MANUAL, description="Trigger type"
    ),
) -> ResupplyAlert:
    svc = get_supply_forecasting_service()
    return svc.trigger_resupply(
        trial_id=trial_id,
        site_id=site_id,
        product_name=product_name,
        current_level=current_level,
        threshold_level=threshold_level,
        recommended_quantity=recommended_quantity,
        trigger_type=trigger_type,
    )


# ---------------------------------------------------------------------------
# Supply Risk Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/risk-assessments",
    response_model=SupplyRiskAssessmentListResponse,
    summary="List supply risk assessments",
    description="Retrieve risk assessments with optional filtering by forecast and status.",
)
async def list_risk_assessments(
    forecast_id: Optional[str] = Query(None, description="Filter by forecast ID"),
    status: Optional[RiskAssessmentStatus] = Query(None, description="Filter by status"),
) -> SupplyRiskAssessmentListResponse:
    svc = get_supply_forecasting_service()
    items = svc.list_risk_assessments(forecast_id=forecast_id, status=status)
    return SupplyRiskAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/risk-assessments/{assessment_id}",
    response_model=SupplyRiskAssessment,
    summary="Get a supply risk assessment",
)
async def get_risk_assessment(assessment_id: str) -> SupplyRiskAssessment:
    svc = get_supply_forecasting_service()
    assessment = svc.get_risk_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Risk assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/risk-assessments",
    response_model=SupplyRiskAssessment,
    status_code=201,
    summary="Create a supply risk assessment",
)
async def create_risk_assessment(payload: SupplyRiskAssessmentCreate) -> SupplyRiskAssessment:
    svc = get_supply_forecasting_service()
    result = svc.create_risk_assessment(payload)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Forecast '{payload.forecast_id}' not found",
        )
    return result


@router.put(
    "/risk-assessments/{assessment_id}",
    response_model=SupplyRiskAssessment,
    summary="Update a supply risk assessment",
)
async def update_risk_assessment(
    assessment_id: str, payload: SupplyRiskAssessmentUpdate
) -> SupplyRiskAssessment:
    svc = get_supply_forecasting_service()
    updated = svc.update_risk_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Risk assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/risk-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a supply risk assessment",
)
async def delete_risk_assessment(assessment_id: str) -> None:
    svc = get_supply_forecasting_service()
    deleted = svc.delete_risk_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Risk assessment '{assessment_id}' not found")


@router.get(
    "/forecasts/{forecast_id}/risks",
    response_model=SupplyRiskAssessmentListResponse,
    summary="Assess supply risks for a forecast",
    description="Retrieve all risk assessments for a forecast sorted by risk score (highest first).",
)
async def assess_forecast_risks(forecast_id: str) -> SupplyRiskAssessmentListResponse:
    svc = get_supply_forecasting_service()
    forecast = svc.get_forecast(forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail=f"Forecast '{forecast_id}' not found")
    items = svc.assess_supply_risk(forecast_id)
    return SupplyRiskAssessmentListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Site Inventory Status
# ---------------------------------------------------------------------------


@router.get(
    "/sites/{site_id}/inventory-status",
    response_model=SiteInventoryStatus,
    summary="Get site inventory status",
    description="Retrieve aggregated inventory status for a specific clinical trial site.",
)
async def get_site_inventory_status(site_id: str) -> SiteInventoryStatus:
    svc = get_supply_forecasting_service()
    status = svc.get_site_inventory_status(site_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"No inventory data for site '{site_id}'")
    return status


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SupplyForecastingMetrics,
    summary="Get supply forecasting dashboard metrics",
    description="Aggregated supply forecasting metrics across all trials and sites.",
)
async def get_metrics() -> SupplyForecastingMetrics:
    svc = get_supply_forecasting_service()
    return svc.get_metrics()
