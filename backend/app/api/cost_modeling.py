"""Cost Modeling & Unit Economics API (CFO-1).

Endpoints for financial analytics on a pharma-regulated clinical trial
patient recruitment platform:
- Cost breakdown by category (CRUD)
- Trial-specific cost models
- Platform unit economics (CAC, LTV, margins, runway)
- Infrastructure cost projections with sub-linear scaling
- Revenue modelling
- Scenario (what-if) analysis
- Aggregated financial dashboard
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.cost_modeling import (
    CostBreakdownResponse,
    CostLineItem,
    CostLineItemCreate,
    CostLineItemUpdate,
    FinancialDashboard,
    InfrastructureCostProjection,
    PlatformUnitEconomics,
    RevenueModel,
    ScenarioRequest,
    ScenarioResult,
    TrialCostModel,
    TrialCostModelCreate,
    TrialCostModelListResponse,
)
from app.services.cost_modeling_service import get_cost_modeling_service

router = APIRouter(prefix="/cost-modeling", tags=["Cost Modeling"])


# ============================================================================
# Dashboard
# ============================================================================


@router.get(
    "/dashboard",
    response_model=FinancialDashboard,
    summary="Full financial dashboard",
    description="Aggregated financial data: unit economics, infrastructure projection, revenue, costs, and trial models.",
)
async def get_dashboard() -> FinancialDashboard:
    """Return the full financial dashboard."""
    service = get_cost_modeling_service()
    return service.get_financial_dashboard()


# ============================================================================
# Cost Line Items
# ============================================================================


@router.get(
    "/costs",
    response_model=CostBreakdownResponse,
    summary="Cost breakdown by category",
    description="All cost line items grouped by category with annual subtotals.",
)
async def get_costs() -> CostBreakdownResponse:
    """Return cost breakdown."""
    service = get_cost_modeling_service()
    return service.get_cost_breakdown()


@router.post(
    "/costs",
    response_model=CostLineItem,
    status_code=201,
    summary="Add a cost line item",
    description="Create a new cost line item in the platform cost model.",
)
async def add_cost(body: CostLineItemCreate) -> CostLineItem:
    """Add a new cost line item."""
    service = get_cost_modeling_service()
    return service.add_cost_item(
        category=body.category,
        name=body.name,
        description=body.description,
        unit_cost=body.unit_cost,
        quantity=body.quantity,
        frequency=body.frequency,
        notes=body.notes,
    )


@router.put(
    "/costs/{item_id}",
    response_model=CostLineItem,
    summary="Update a cost item",
    description="Update fields on an existing cost line item.",
)
async def update_cost(item_id: str, body: CostLineItemUpdate) -> CostLineItem:
    """Update an existing cost line item."""
    service = get_cost_modeling_service()
    try:
        return service.update_cost_item(
            item_id,
            category=body.category,
            name=body.name,
            description=body.description,
            unit_cost=body.unit_cost,
            quantity=body.quantity,
            frequency=body.frequency,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete(
    "/costs/{item_id}",
    status_code=204,
    summary="Remove a cost item",
    description="Delete a cost line item by ID.",
)
async def delete_cost(item_id: str) -> None:
    """Remove a cost line item."""
    service = get_cost_modeling_service()
    try:
        service.remove_cost_item(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ============================================================================
# Trial Cost Models
# ============================================================================


@router.get(
    "/trials",
    response_model=TrialCostModelListResponse,
    summary="List trial cost models",
    description="Return all trial-specific cost models.",
)
async def list_trials() -> TrialCostModelListResponse:
    """List all trial cost models."""
    service = get_cost_modeling_service()
    return service.list_trial_models()


@router.get(
    "/trials/{trial_id}",
    response_model=TrialCostModel,
    summary="Get trial cost model",
    description="Return a single trial cost model by trial_id.",
)
async def get_trial(trial_id: str) -> TrialCostModel:
    """Get a trial cost model."""
    service = get_cost_modeling_service()
    try:
        return service.get_trial_cost_model(trial_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/trials",
    response_model=TrialCostModel,
    status_code=201,
    summary="Create trial cost model",
    description="Create a new trial cost model with auto-calculated derived fields.",
)
async def create_trial(body: TrialCostModelCreate) -> TrialCostModel:
    """Create a new trial cost model."""
    service = get_cost_modeling_service()
    try:
        return service.create_trial_model(
            trial_id=body.trial_id,
            trial_name=body.trial_name,
            patient_target=body.patient_target,
            cost_per_patient_screened=body.cost_per_patient_screened,
            cost_per_patient_enrolled=body.cost_per_patient_enrolled,
            screening_to_enrollment_ratio=body.screening_to_enrollment_ratio,
            overhead_allocation=body.overhead_allocation,
            revenue_per_enrolled_patient=body.revenue_per_enrolled_patient,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ============================================================================
# Unit Economics
# ============================================================================


@router.get(
    "/unit-economics",
    response_model=PlatformUnitEconomics,
    summary="Platform unit economics",
    description="Platform-wide unit economics: CAC, LTV, margins, burn rate, runway.",
)
async def get_unit_economics() -> PlatformUnitEconomics:
    """Return platform unit economics."""
    service = get_cost_modeling_service()
    return service.get_unit_economics()


# ============================================================================
# Infrastructure Projection
# ============================================================================


@router.get(
    "/infrastructure/projection",
    response_model=InfrastructureCostProjection,
    summary="Infrastructure cost projection",
    description="Project infrastructure costs at a target patient volume with sub-linear scaling.",
)
async def get_infrastructure_projection(
    target_patients: int = Query(
        100_000, ge=1, description="Target patient count for projection"
    ),
) -> InfrastructureCostProjection:
    """Project infrastructure costs at target scale."""
    service = get_cost_modeling_service()
    return service.project_infrastructure_costs(target_patients)


# ============================================================================
# Revenue
# ============================================================================


@router.get(
    "/revenue",
    response_model=RevenueModel,
    summary="Revenue model",
    description="Current and projected revenue based on active trial contracts.",
)
async def get_revenue() -> RevenueModel:
    """Return the revenue model."""
    service = get_cost_modeling_service()
    return service.get_revenue_model()


# ============================================================================
# Scenario Analysis
# ============================================================================


@router.post(
    "/scenarios",
    response_model=ScenarioResult,
    summary="Scenario analysis",
    description="Run a what-if scenario varying patient growth, trial count, and pricing.",
)
async def run_scenario(body: ScenarioRequest) -> ScenarioResult:
    """Run a what-if scenario analysis."""
    service = get_cost_modeling_service()
    return service.scenario_analysis(
        patient_growth_rate=body.patient_growth_rate,
        trial_count=body.trial_count,
        pricing_change=body.pricing_change,
    )
