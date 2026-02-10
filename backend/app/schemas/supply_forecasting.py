"""Pydantic schemas for Clinical Supply Forecasting (CLINICAL-8).

Manages drug supply forecasting, demand planning, inventory optimization,
supply risk assessment, and resupply triggers for clinical trials.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ForecastStatus(str, Enum):
    """Lifecycle status of a supply forecast."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class DemandScenario(str, Enum):
    """Demand planning scenario for sensitivity analysis."""

    CONSERVATIVE = "conservative"
    BASE = "base"
    AGGRESSIVE = "aggressive"
    WORST_CASE = "worst_case"


class SupplyRiskLevel(str, Enum):
    """Risk level classification for supply chain risks."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ResupplyTriggerType(str, Enum):
    """Type of resupply trigger mechanism."""

    THRESHOLD = "threshold"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    EMERGENCY = "emergency"


class ForecastPeriod(str, Enum):
    """Time period granularity for supply forecasting."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class SupplyPlanStatus(str, Enum):
    """Status of a supply plan order."""

    PLANNED = "planned"
    ORDERED = "ordered"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class RiskAssessmentStatus(str, Enum):
    """Status of a supply risk assessment."""

    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SupplyForecast(BaseModel):
    """A supply forecast for a drug product within a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique forecast identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    product_name: str = Field(..., description="Drug product name")
    forecast_period: ForecastPeriod = Field(..., description="Forecast time period granularity")
    scenario: DemandScenario = Field(..., description="Demand scenario used for this forecast")
    status: ForecastStatus = Field(
        default=ForecastStatus.DRAFT, description="Current forecast lifecycle status"
    )
    created_date: datetime = Field(..., description="Date the forecast was created")
    created_by: str = Field(..., description="User who created the forecast")
    current_inventory: int = Field(ge=0, description="Current on-hand inventory units")
    projected_demand: int = Field(ge=0, description="Total projected demand units over forecast horizon")
    projected_supply: int = Field(ge=0, description="Total projected supply units over forecast horizon")
    safety_stock: int = Field(ge=0, description="Minimum safety stock level in units")
    reorder_point: int = Field(ge=0, description="Inventory level that triggers reorder")
    lead_time_days: int = Field(ge=0, description="Supplier lead time in days")
    months_of_supply: float = Field(ge=0.0, description="Estimated months of supply remaining")
    risk_level: SupplyRiskLevel = Field(
        default=SupplyRiskLevel.LOW, description="Overall supply risk level"
    )


class DemandProjection(BaseModel):
    """A demand projection for a specific time period within a forecast."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique demand projection identifier")
    forecast_id: str = Field(..., description="Parent supply forecast identifier")
    period_start: datetime = Field(..., description="Start of the projection period")
    period_end: datetime = Field(..., description="End of the projection period")
    projected_enrollment: int = Field(ge=0, description="Projected patient enrollment for period")
    doses_per_patient: float = Field(gt=0.0, description="Average number of doses per patient")
    total_doses_needed: int = Field(ge=0, description="Total doses needed for the period")
    wastage_factor: float = Field(
        ge=0.0, le=1.0, description="Expected wastage factor (0.0 to 1.0)"
    )
    overage_pct: float = Field(
        ge=0.0, description="Overage percentage for buffer stock"
    )
    total_units_required: int = Field(ge=0, description="Total units required including wastage and overage")


class SupplyPlan(BaseModel):
    """A supply plan order associated with a forecast."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique supply plan identifier")
    forecast_id: str = Field(..., description="Parent supply forecast identifier")
    supplier: str = Field(..., description="Supplier name")
    order_date: datetime = Field(..., description="Date the order was placed")
    expected_delivery: datetime = Field(..., description="Expected delivery date")
    quantity_ordered: int = Field(ge=1, description="Quantity ordered in units")
    unit_cost: float = Field(ge=0.0, description="Cost per unit in USD")
    total_cost: float = Field(ge=0.0, description="Total order cost in USD")
    status: SupplyPlanStatus = Field(
        default=SupplyPlanStatus.PLANNED, description="Current order status"
    )
    lot_number: str | None = Field(None, description="Assigned lot number")
    expiry_date: datetime | None = Field(None, description="Product expiry date for this lot")


class InventorySnapshot(BaseModel):
    """A point-in-time inventory snapshot for a site and product."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique snapshot identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Clinical trial site identifier")
    product_name: str = Field(..., description="Drug product name")
    snapshot_date: datetime = Field(..., description="Date and time of the snapshot")
    on_hand: int = Field(ge=0, description="Total units physically on hand")
    allocated: int = Field(ge=0, description="Units allocated to patients or visits")
    available: int = Field(ge=0, description="Units available for dispensing (on_hand - allocated)")
    expiring_30d: int = Field(ge=0, description="Units expiring within 30 days")
    expiring_90d: int = Field(ge=0, description="Units expiring within 90 days")
    below_safety_stock: bool = Field(
        default=False, description="Whether available inventory is below safety stock level"
    )


class ResupplyAlert(BaseModel):
    """A resupply alert triggered when inventory drops below threshold."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique alert identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Clinical trial site identifier")
    product_name: str = Field(..., description="Drug product name")
    alert_type: SupplyRiskLevel = Field(..., description="Severity level of the alert")
    trigger_type: ResupplyTriggerType = Field(..., description="Type of trigger that generated the alert")
    current_level: int = Field(ge=0, description="Current inventory level when alert was triggered")
    threshold_level: int = Field(ge=0, description="Threshold level that was breached")
    recommended_quantity: int = Field(ge=0, description="Recommended resupply quantity")
    created_date: datetime = Field(..., description="Date and time the alert was created")
    acknowledged: bool = Field(default=False, description="Whether the alert has been acknowledged")
    acknowledged_by: str | None = Field(None, description="User who acknowledged the alert")


class SupplyRiskAssessment(BaseModel):
    """A risk assessment for a supply forecast."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique risk assessment identifier")
    forecast_id: str = Field(..., description="Parent supply forecast identifier")
    risk_category: str = Field(..., description="Category of supply risk (e.g., supplier, logistics, regulatory)")
    description: str = Field(..., description="Detailed description of the risk")
    probability: float = Field(
        ge=0.0, le=1.0, description="Probability of occurrence (0.0 to 1.0)"
    )
    impact: float = Field(
        ge=0.0, le=1.0, description="Impact severity (0.0 to 1.0)"
    )
    risk_score: float = Field(
        ge=0.0, le=1.0, description="Composite risk score (probability x impact)"
    )
    mitigation_plan: str = Field(..., description="Planned mitigation actions")
    owner: str = Field(..., description="Person responsible for the risk")
    status: RiskAssessmentStatus = Field(
        default=RiskAssessmentStatus.IDENTIFIED, description="Current status of the risk assessment"
    )


class SupplyForecastingMetrics(BaseModel):
    """Aggregated supply forecasting metrics for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_forecasts: int = Field(ge=0, description="Total number of supply forecasts")
    active_forecasts: int = Field(ge=0, description="Number of active forecasts")
    total_demand_projections: int = Field(ge=0, description="Total demand projections")
    total_supply_plans: int = Field(ge=0, description="Total supply plan orders")
    pending_orders: int = Field(ge=0, description="Number of planned or ordered supply plans")
    total_inventory_snapshots: int = Field(ge=0, description="Total inventory snapshots")
    sites_below_safety_stock: int = Field(ge=0, description="Number of sites below safety stock")
    active_resupply_alerts: int = Field(ge=0, description="Number of unacknowledged resupply alerts")
    total_risk_assessments: int = Field(ge=0, description="Total supply risk assessments")
    high_critical_risks: int = Field(ge=0, description="Number of high or critical unresolved risks")
    avg_months_of_supply: float | None = Field(
        None, description="Average months of supply across active forecasts"
    )
    total_order_value: float = Field(ge=0.0, description="Total value of all supply plan orders in USD")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SupplyForecastCreate(BaseModel):
    """Request payload for creating a new supply forecast."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Clinical trial identifier")
    product_name: str = Field(..., description="Drug product name")
    forecast_period: ForecastPeriod = Field(..., description="Forecast time period granularity")
    scenario: DemandScenario = Field(
        default=DemandScenario.BASE, description="Demand scenario"
    )
    created_by: str = Field(..., description="User creating the forecast")
    current_inventory: int = Field(ge=0, description="Current on-hand inventory units")
    safety_stock: int = Field(ge=0, description="Minimum safety stock level")
    lead_time_days: int = Field(ge=0, description="Supplier lead time in days")


class SupplyForecastUpdate(BaseModel):
    """Request payload for updating a supply forecast."""

    model_config = ConfigDict(from_attributes=True)

    status: ForecastStatus | None = Field(None, description="Updated forecast status")
    current_inventory: int | None = Field(None, ge=0, description="Updated current inventory")
    safety_stock: int | None = Field(None, ge=0, description="Updated safety stock level")
    lead_time_days: int | None = Field(None, ge=0, description="Updated lead time")
    scenario: DemandScenario | None = Field(None, description="Updated demand scenario")


class DemandProjectionCreate(BaseModel):
    """Request payload for creating a demand projection."""

    model_config = ConfigDict(from_attributes=True)

    forecast_id: str = Field(..., description="Parent forecast identifier")
    period_start: datetime = Field(..., description="Start of the projection period")
    period_end: datetime = Field(..., description="End of the projection period")
    projected_enrollment: int = Field(ge=0, description="Projected patient enrollment")
    doses_per_patient: float = Field(gt=0.0, description="Doses per patient")
    wastage_factor: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Wastage factor"
    )
    overage_pct: float = Field(default=10.0, ge=0.0, description="Overage percentage")


class SupplyPlanCreate(BaseModel):
    """Request payload for creating a supply plan order."""

    model_config = ConfigDict(from_attributes=True)

    forecast_id: str = Field(..., description="Parent forecast identifier")
    supplier: str = Field(..., description="Supplier name")
    order_date: datetime = Field(..., description="Order date")
    expected_delivery: datetime = Field(..., description="Expected delivery date")
    quantity_ordered: int = Field(ge=1, description="Quantity ordered")
    unit_cost: float = Field(ge=0.0, description="Cost per unit")


class SupplyPlanUpdate(BaseModel):
    """Request payload for updating a supply plan order."""

    model_config = ConfigDict(from_attributes=True)

    status: SupplyPlanStatus | None = Field(None, description="Updated order status")
    expected_delivery: datetime | None = Field(None, description="Updated delivery date")
    lot_number: str | None = Field(None, description="Assigned lot number")
    expiry_date: datetime | None = Field(None, description="Product expiry date")


class ResupplyAlertAcknowledge(BaseModel):
    """Request payload for acknowledging a resupply alert."""

    model_config = ConfigDict(from_attributes=True)

    acknowledged_by: str = Field(..., description="User acknowledging the alert")


class SupplyRiskAssessmentCreate(BaseModel):
    """Request payload for creating a supply risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    forecast_id: str = Field(..., description="Parent forecast identifier")
    risk_category: str = Field(..., description="Risk category")
    description: str = Field(..., description="Risk description")
    probability: float = Field(ge=0.0, le=1.0, description="Probability of occurrence")
    impact: float = Field(ge=0.0, le=1.0, description="Impact severity")
    mitigation_plan: str = Field(..., description="Mitigation actions")
    owner: str = Field(..., description="Risk owner")


class SupplyRiskAssessmentUpdate(BaseModel):
    """Request payload for updating a supply risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = Field(None, description="Updated description")
    probability: float | None = Field(None, ge=0.0, le=1.0, description="Updated probability")
    impact: float | None = Field(None, ge=0.0, le=1.0, description="Updated impact")
    mitigation_plan: str | None = Field(None, description="Updated mitigation plan")
    owner: str | None = Field(None, description="Updated owner")
    status: RiskAssessmentStatus | None = Field(None, description="Updated status")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SupplyForecastListResponse(BaseModel):
    """Paginated list of supply forecasts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SupplyForecast] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DemandProjectionListResponse(BaseModel):
    """List of demand projections."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DemandProjection] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SupplyPlanListResponse(BaseModel):
    """List of supply plan orders."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SupplyPlan] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InventorySnapshotListResponse(BaseModel):
    """List of inventory snapshots."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InventorySnapshot] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ResupplyAlertListResponse(BaseModel):
    """List of resupply alerts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ResupplyAlert] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SupplyRiskAssessmentListResponse(BaseModel):
    """List of supply risk assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SupplyRiskAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteInventoryStatus(BaseModel):
    """Inventory status summary for a specific site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    products: list[InventorySnapshot] = Field(
        default_factory=list, description="Latest inventory snapshot per product"
    )
    total_on_hand: int = Field(ge=0, description="Total units on hand across all products")
    total_available: int = Field(ge=0, description="Total available units across all products")
    any_below_safety_stock: bool = Field(
        default=False, description="Whether any product is below safety stock"
    )
    active_alerts: int = Field(ge=0, description="Number of active resupply alerts for this site")
