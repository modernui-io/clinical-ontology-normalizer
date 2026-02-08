"""Pydantic v2 schemas for CFO-1: Cost Modeling & Unit Economics.

Defines schemas for cost line items, trial cost models, platform unit
economics, infrastructure cost projections, revenue modelling, scenario
analysis, and the aggregated financial dashboard.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CostCategory(str, Enum):
    """High-level cost bucket."""

    INFRASTRUCTURE = "infrastructure"
    PERSONNEL = "personnel"
    DATA_ACQUISITION = "data_acquisition"
    COMPLIANCE = "compliance"
    INTEGRATION = "integration"
    SUPPORT = "support"
    LICENSING = "licensing"


class CostFrequency(str, Enum):
    """Billing cadence for a cost line item."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ONE_TIME = "one_time"


# ---------------------------------------------------------------------------
# Cost Line Items
# ---------------------------------------------------------------------------


class CostLineItem(BaseModel):
    """A single cost entry in the platform cost model."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for this cost item")
    category: CostCategory
    name: str = Field(..., description="Human-readable cost name")
    description: str = Field(default="", description="Details about this cost")
    unit_cost: float = Field(..., ge=0, description="Cost per unit ($)")
    quantity: float = Field(default=1.0, ge=0, description="Number of units")
    frequency: CostFrequency = Field(default=CostFrequency.MONTHLY)
    notes: str = Field(default="", description="Optional notes")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_annual_cost(self) -> float:
        """Annualised cost for this line item."""
        multiplier = {
            CostFrequency.MONTHLY: 12.0,
            CostFrequency.QUARTERLY: 4.0,
            CostFrequency.ANNUALLY: 1.0,
            CostFrequency.ONE_TIME: 1.0,
        }
        return round(self.unit_cost * self.quantity * multiplier[self.frequency], 2)


class CostLineItemCreate(BaseModel):
    """Request body to create a new cost line item."""

    model_config = ConfigDict(from_attributes=True)

    category: CostCategory
    name: str
    description: str = ""
    unit_cost: float = Field(..., ge=0)
    quantity: float = Field(default=1.0, ge=0)
    frequency: CostFrequency = Field(default=CostFrequency.MONTHLY)
    notes: str = ""


class CostLineItemUpdate(BaseModel):
    """Request body to update an existing cost line item."""

    model_config = ConfigDict(from_attributes=True)

    category: CostCategory | None = None
    name: str | None = None
    description: str | None = None
    unit_cost: float | None = Field(default=None, ge=0)
    quantity: float | None = Field(default=None, ge=0)
    frequency: CostFrequency | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Category Subtotal
# ---------------------------------------------------------------------------


class CategorySubtotal(BaseModel):
    """Cost summary for a single category."""

    category: CostCategory
    items: list[CostLineItem] = []
    subtotal_annual: float = Field(default=0.0, description="Annual subtotal for category")


class CostBreakdownResponse(BaseModel):
    """Cost breakdown grouped by category."""

    categories: list[CategorySubtotal] = []
    total_annual_cost: float = 0.0
    total_monthly_cost: float = 0.0
    item_count: int = 0


# ---------------------------------------------------------------------------
# Trial Cost Model
# ---------------------------------------------------------------------------


class TrialCostModel(BaseModel):
    """Unit economics for a single clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str
    trial_name: str
    patient_target: int = Field(..., ge=0, description="Enrollment goal")
    cost_per_patient_screened: float = Field(..., ge=0)
    cost_per_patient_enrolled: float = Field(..., ge=0)
    screening_to_enrollment_ratio: float = Field(
        ..., ge=0, description="e.g. 8.0 means 8 screened per 1 enrolled"
    )
    total_screening_cost: float = Field(default=0.0, ge=0)
    total_enrollment_cost: float = Field(default=0.0, ge=0)
    overhead_allocation: float = Field(default=0.0, ge=0)
    total_trial_cost: float = Field(default=0.0, ge=0)
    margin_percent: float = Field(default=0.0, description="Gross margin %")
    revenue_per_enrolled_patient: float = Field(default=0.0, ge=0)


class TrialCostModelCreate(BaseModel):
    """Request body to create a trial cost model."""

    trial_id: str
    trial_name: str
    patient_target: int = Field(..., ge=0)
    cost_per_patient_screened: float = Field(..., ge=0)
    cost_per_patient_enrolled: float = Field(..., ge=0)
    screening_to_enrollment_ratio: float = Field(..., gt=0)
    overhead_allocation: float = Field(default=0.0, ge=0)
    revenue_per_enrolled_patient: float = Field(default=0.0, ge=0)


class TrialCostModelListResponse(BaseModel):
    """List of trial cost models."""

    total: int = 0
    trials: list[TrialCostModel] = []


# ---------------------------------------------------------------------------
# Platform Unit Economics
# ---------------------------------------------------------------------------


class PlatformUnitEconomics(BaseModel):
    """Platform-wide unit economics snapshot."""

    total_monthly_cost: float = 0.0
    total_monthly_revenue: float = 0.0
    gross_margin: float = Field(default=0.0, description="(revenue - cost) / revenue")
    patient_acquisition_cost: float = Field(default=0.0, description="CAC ($)")
    lifetime_value_per_patient: float = Field(default=0.0, description="LTV ($)")
    ltv_to_cac_ratio: float = Field(default=0.0, description="LTV / CAC")
    burn_rate: float = Field(default=0.0, description="Monthly burn ($)")
    runway_months: float = Field(default=0.0, description="Cash / monthly burn")
    break_even_patients: int = Field(default=0, description="Patients to break even")


# ---------------------------------------------------------------------------
# Infrastructure Cost Projection
# ---------------------------------------------------------------------------


class ComponentCostProjection(BaseModel):
    """Projected cost for a single infrastructure component."""

    name: str
    current_cost: float = 0.0
    projected_cost: float = 0.0
    scaling_factor: float = Field(
        default=1.0, description="Sub-linear exponent (< 1 = economies of scale)"
    )


class InfrastructureCostProjection(BaseModel):
    """Infrastructure cost projection at a target patient volume."""

    current_patients: int = 0
    projected_patients: int = 0
    current_monthly_cost: float = 0.0
    projected_monthly_cost: float = 0.0
    cost_per_patient_at_scale: float = 0.0
    scaling_efficiency: float = Field(
        default=0.0, description="1 - (projected_cost_ratio / patient_ratio); > 0 = sub-linear"
    )
    components: list[ComponentCostProjection] = []


# ---------------------------------------------------------------------------
# Revenue Model
# ---------------------------------------------------------------------------


class RevenueModel(BaseModel):
    """Current and projected revenue."""

    active_trials: int = 0
    avg_revenue_per_trial: float = 0.0
    monthly_recurring_revenue: float = 0.0
    annual_recurring_revenue: float = 0.0
    growth_rate_monthly: float = Field(default=0.0, description="MoM growth rate (fraction)")
    projected_arr_12months: float = 0.0


# ---------------------------------------------------------------------------
# Scenario Analysis
# ---------------------------------------------------------------------------


class ScenarioRequest(BaseModel):
    """What-if scenario parameters."""

    patient_growth_rate: float = Field(
        default=0.0, description="Monthly patient growth rate (fraction)"
    )
    trial_count: int | None = Field(
        default=None, ge=0, description="Override active trial count"
    )
    pricing_change: float = Field(
        default=0.0, description="Pricing change fraction (+0.10 = +10%)"
    )


class ScenarioResult(BaseModel):
    """Result of a what-if scenario analysis."""

    scenario: ScenarioRequest
    projected_unit_economics: PlatformUnitEconomics
    projected_revenue: RevenueModel
    projected_infrastructure: InfrastructureCostProjection
    summary: str = ""


# ---------------------------------------------------------------------------
# Financial Dashboard (top-level aggregate)
# ---------------------------------------------------------------------------


class FinancialDashboard(BaseModel):
    """Aggregated financial dashboard for the platform."""

    unit_economics: PlatformUnitEconomics
    infrastructure_projection: InfrastructureCostProjection
    revenue: RevenueModel
    cost_breakdown: list[CostLineItem] = []
    trial_models: list[TrialCostModel] = []
    generated_at: datetime
