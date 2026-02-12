"""Pydantic schemas for Clinical Supply Forecasting (SUPPLY-FCST).

Manages clinical supply forecasting operations: demand forecasts,
supply plans, inventory projections, expiry risk tracking,
depot allocation planning, and supply forecasting metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ForecastType(str, Enum):
    ENROLLMENT_BASED = "enrollment_based"
    CONSUMPTION_BASED = "consumption_based"
    HYBRID = "hybrid"
    SCENARIO = "scenario"
    MONTE_CARLO = "monte_carlo"


class ForecastStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class SupplyRisk(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class AllocationStrategy(str, Enum):
    PROPORTIONAL = "proportional"
    PRIORITY_BASED = "priority_based"
    DEMAND_DRIVEN = "demand_driven"
    FIXED = "fixed"


class DemandForecast(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    drug_name: str
    forecast_type: ForecastType
    status: ForecastStatus = ForecastStatus.DRAFT
    forecast_date: datetime
    horizon_months: int = Field(ge=1, default=12)
    total_demand_units: int = Field(ge=0, default=0)
    monthly_demand: list[dict] = Field(default_factory=list)
    enrollment_assumption: int = Field(ge=0, default=0)
    dropout_rate_pct: float = Field(ge=0, le=100, default=15.0)
    compliance_rate_pct: float = Field(ge=0, le=100, default=85.0)
    overage_pct: float = Field(ge=0, le=100, default=20.0)
    confidence_interval_lower: int | None = None
    confidence_interval_upper: int | None = None
    created_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class SupplyPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    drug_name: str
    plan_date: datetime
    status: ForecastStatus = ForecastStatus.DRAFT
    forecast_id: str | None = None
    manufacturing_lead_weeks: int = Field(ge=0, default=12)
    packaging_lead_weeks: int = Field(ge=0, default=4)
    shipping_lead_weeks: int = Field(ge=0, default=2)
    planned_production_units: int = Field(ge=0, default=0)
    planned_batches: int = Field(ge=0, default=0)
    batch_size: int = Field(ge=0, default=0)
    total_cost_estimate: float = Field(ge=0, default=0.0)
    risk_level: SupplyRisk = SupplyRisk.LOW
    mitigation_strategy: str | None = None
    created_by: str
    approved_by: str | None = None
    created_at: datetime


class InventoryProjection(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    drug_name: str
    site_id: str | None = None
    projection_date: datetime
    current_inventory: int = Field(ge=0, default=0)
    projected_demand_30d: int = Field(ge=0, default=0)
    projected_demand_60d: int = Field(ge=0, default=0)
    projected_demand_90d: int = Field(ge=0, default=0)
    reorder_point: int = Field(ge=0, default=0)
    safety_stock: int = Field(ge=0, default=0)
    weeks_of_supply: float = Field(ge=0, default=0.0)
    stockout_risk: SupplyRisk = SupplyRisk.LOW
    next_resupply_date: datetime | None = None
    created_at: datetime


class ExpiryRisk(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    drug_name: str
    batch_number: str
    site_id: str | None = None
    expiry_date: datetime
    quantity_at_risk: int = Field(ge=0, default=0)
    days_to_expiry: int = 0
    risk_level: SupplyRisk = SupplyRisk.LOW
    mitigation_action: str | None = None
    can_redistribute: bool = False
    redistribution_site: str | None = None
    financial_impact: float = Field(ge=0, default=0.0)
    flagged_by: str
    resolved: bool = False
    created_at: datetime


class DepotAllocation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    drug_name: str
    depot_name: str
    region: str
    allocation_strategy: AllocationStrategy
    allocation_date: datetime
    sites_served: int = Field(ge=0, default=0)
    allocated_units: int = Field(ge=0, default=0)
    shipped_units: int = Field(ge=0, default=0)
    remaining_units: int = Field(ge=0, default=0)
    utilization_pct: float = Field(ge=0, le=100, default=0.0)
    next_shipment_date: datetime | None = None
    capacity_units: int = Field(ge=0, default=0)
    is_active: bool = True
    managed_by: str
    created_at: datetime


class DemandForecastCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    drug_name: str
    forecast_type: ForecastType
    created_by: str
    horizon_months: int = Field(ge=1, default=12)
    enrollment_assumption: int = Field(ge=0, default=0)


class DemandForecastUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ForecastStatus | None = None
    total_demand_units: int | None = None
    approved_by: str | None = None
    notes: str | None = None
    dropout_rate_pct: float | None = None


class SupplyPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    drug_name: str
    created_by: str
    forecast_id: str | None = None
    planned_production_units: int = Field(ge=0, default=0)


class SupplyPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ForecastStatus | None = None
    risk_level: SupplyRisk | None = None
    approved_by: str | None = None
    mitigation_strategy: str | None = None
    total_cost_estimate: float | None = None


class InventoryProjectionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    drug_name: str
    current_inventory: int = Field(ge=0, default=0)
    site_id: str | None = None
    reorder_point: int = Field(ge=0, default=0)


class InventoryProjectionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    current_inventory: int | None = None
    stockout_risk: SupplyRisk | None = None
    next_resupply_date: datetime | None = None
    safety_stock: int | None = None


class ExpiryRiskCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    drug_name: str
    batch_number: str
    expiry_date: datetime
    quantity_at_risk: int = Field(ge=0, default=0)
    flagged_by: str
    site_id: str | None = None


class ExpiryRiskUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    mitigation_action: str | None = None
    can_redistribute: bool | None = None
    resolved: bool | None = None
    risk_level: SupplyRisk | None = None


class DepotAllocationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    drug_name: str
    depot_name: str
    region: str
    allocation_strategy: AllocationStrategy
    managed_by: str
    allocated_units: int = Field(ge=0, default=0)


class DepotAllocationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    shipped_units: int | None = None
    next_shipment_date: datetime | None = None
    utilization_pct: float | None = None


class DemandForecastListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DemandForecast] = Field(default_factory=list)
    total: int = Field(ge=0)


class SupplyPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SupplyPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class InventoryProjectionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InventoryProjection] = Field(default_factory=list)
    total: int = Field(ge=0)


class ExpiryRiskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ExpiryRisk] = Field(default_factory=list)
    total: int = Field(ge=0)


class DepotAllocationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DepotAllocation] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalSupplyForecastMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_forecasts: int = Field(ge=0)
    forecasts_by_type: dict[str, int] = Field(default_factory=dict)
    forecasts_by_status: dict[str, int] = Field(default_factory=dict)
    total_supply_plans: int = Field(ge=0)
    plans_by_risk: dict[str, int] = Field(default_factory=dict)
    total_projections: int = Field(ge=0)
    sites_at_stockout_risk: int = Field(ge=0)
    total_expiry_risks: int = Field(ge=0)
    unresolved_expiry_risks: int = Field(ge=0)
    total_financial_exposure: float = Field(ge=0)
    total_depots: int = Field(ge=0)
    active_depots: int = Field(ge=0)
    avg_depot_utilization: float = Field(ge=0)
