"""Clinical Supply Forecasting Service (SUPPLY-FCST).

Manages clinical supply forecasting operations: demand forecasts,
supply plans, inventory projections, expiry risk tracking,
depot allocation planning, and supply forecasting metrics.

Usage:
    from app.services.clinical_supply_forecast_service import (
        get_clinical_supply_forecast_service,
    )

    svc = get_clinical_supply_forecast_service()
    forecasts = svc.list_demand_forecasts()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_supply_forecast import (
    AllocationStrategy,
    ClinicalSupplyForecastMetrics,
    DemandForecast,
    DemandForecastCreate,
    DemandForecastUpdate,
    DepotAllocation,
    DepotAllocationCreate,
    DepotAllocationUpdate,
    ExpiryRisk,
    ExpiryRiskCreate,
    ExpiryRiskUpdate,
    ForecastStatus,
    ForecastType,
    InventoryProjection,
    InventoryProjectionCreate,
    InventoryProjectionUpdate,
    SupplyPlan,
    SupplyPlanCreate,
    SupplyPlanUpdate,
    SupplyRisk,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalSupplyForecastService:
    """In-memory Clinical Supply Forecasting engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._demand_forecasts: dict[str, DemandForecast] = {}
        self._supply_plans: dict[str, SupplyPlan] = {}
        self._inventory_projections: dict[str, InventoryProjection] = {}
        self._expiry_risks: dict[str, ExpiryRisk] = {}
        self._depot_allocations: dict[str, DepotAllocation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic clinical supply forecast data."""
        now = datetime.now(timezone.utc)

        # --- 12 Demand Forecasts ---
        forecasts_data = [
            {
                "id": "DF-001",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "forecast_type": ForecastType.ENROLLMENT_BASED,
                "status": ForecastStatus.APPROVED,
                "forecast_date": now - timedelta(days=60),
                "horizon_months": 12,
                "total_demand_units": 24000,
                "monthly_demand": [{"month": i + 1, "units": 2000} for i in range(12)],
                "enrollment_assumption": 400,
                "dropout_rate_pct": 12.0,
                "compliance_rate_pct": 88.0,
                "overage_pct": 20.0,
                "confidence_interval_lower": 21000,
                "confidence_interval_upper": 27000,
                "created_by": "Dr. Sarah Chen",
                "approved_by": "Dr. Michael Ross",
                "notes": "Based on Phase III enrollment projections.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DF-002",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "forecast_type": ForecastType.CONSUMPTION_BASED,
                "status": ForecastStatus.UNDER_REVIEW,
                "forecast_date": now - timedelta(days=15),
                "horizon_months": 6,
                "total_demand_units": 13500,
                "monthly_demand": [{"month": i + 1, "units": 2250} for i in range(6)],
                "enrollment_assumption": 400,
                "dropout_rate_pct": 14.0,
                "compliance_rate_pct": 86.0,
                "overage_pct": 18.0,
                "confidence_interval_lower": 12000,
                "confidence_interval_upper": 15000,
                "created_by": "James Wilson",
                "approved_by": None,
                "notes": "Updated based on actual consumption data from Q4.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DF-003",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "forecast_type": ForecastType.HYBRID,
                "status": ForecastStatus.APPROVED,
                "forecast_date": now - timedelta(days=45),
                "horizon_months": 18,
                "total_demand_units": 54000,
                "monthly_demand": [{"month": i + 1, "units": 3000} for i in range(18)],
                "enrollment_assumption": 600,
                "dropout_rate_pct": 10.0,
                "compliance_rate_pct": 90.0,
                "overage_pct": 25.0,
                "confidence_interval_lower": 48000,
                "confidence_interval_upper": 60000,
                "created_by": "Dr. Emily Park",
                "approved_by": "Dr. Robert Kim",
                "notes": "Hybrid model combining enrollment and consumption trends.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DF-004",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "forecast_type": ForecastType.SCENARIO,
                "status": ForecastStatus.DRAFT,
                "forecast_date": now - timedelta(days=5),
                "horizon_months": 12,
                "total_demand_units": 40000,
                "monthly_demand": [{"month": i + 1, "units": 3333} for i in range(12)],
                "enrollment_assumption": 700,
                "dropout_rate_pct": 8.0,
                "compliance_rate_pct": 92.0,
                "overage_pct": 15.0,
                "confidence_interval_lower": 35000,
                "confidence_interval_upper": 45000,
                "created_by": "James Wilson",
                "approved_by": None,
                "notes": "Optimistic enrollment scenario.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DF-005",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "forecast_type": ForecastType.ENROLLMENT_BASED,
                "status": ForecastStatus.APPROVED,
                "forecast_date": now - timedelta(days=30),
                "horizon_months": 24,
                "total_demand_units": 72000,
                "monthly_demand": [{"month": i + 1, "units": 3000} for i in range(24)],
                "enrollment_assumption": 500,
                "dropout_rate_pct": 15.0,
                "compliance_rate_pct": 85.0,
                "overage_pct": 22.0,
                "confidence_interval_lower": 65000,
                "confidence_interval_upper": 80000,
                "created_by": "Dr. Sarah Chen",
                "approved_by": "Dr. Michael Ross",
                "notes": "Phase II/III oncology trial supply forecast.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DF-006",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "forecast_type": ForecastType.MONTE_CARLO,
                "status": ForecastStatus.UNDER_REVIEW,
                "forecast_date": now - timedelta(days=10),
                "horizon_months": 12,
                "total_demand_units": 38000,
                "monthly_demand": [{"month": i + 1, "units": 3167} for i in range(12)],
                "enrollment_assumption": 500,
                "dropout_rate_pct": 18.0,
                "compliance_rate_pct": 82.0,
                "overage_pct": 20.0,
                "confidence_interval_lower": 32000,
                "confidence_interval_upper": 44000,
                "created_by": "Dr. Emily Park",
                "approved_by": None,
                "notes": "Monte Carlo simulation with 10,000 iterations.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DF-007",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 8mg HD",
                "forecast_type": ForecastType.ENROLLMENT_BASED,
                "status": ForecastStatus.APPROVED,
                "forecast_date": now - timedelta(days=75),
                "horizon_months": 12,
                "total_demand_units": 18000,
                "monthly_demand": [{"month": i + 1, "units": 1500} for i in range(12)],
                "enrollment_assumption": 300,
                "dropout_rate_pct": 10.0,
                "compliance_rate_pct": 90.0,
                "overage_pct": 20.0,
                "confidence_interval_lower": 16000,
                "confidence_interval_upper": 20000,
                "created_by": "Dr. Sarah Chen",
                "approved_by": "Dr. Michael Ross",
                "notes": "High-dose formulation Phase III forecast.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DF-008",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 200mg",
                "forecast_type": ForecastType.CONSUMPTION_BASED,
                "status": ForecastStatus.SUPERSEDED,
                "forecast_date": now - timedelta(days=120),
                "horizon_months": 12,
                "total_demand_units": 30000,
                "monthly_demand": [{"month": i + 1, "units": 2500} for i in range(12)],
                "enrollment_assumption": 500,
                "dropout_rate_pct": 12.0,
                "compliance_rate_pct": 87.0,
                "overage_pct": 20.0,
                "confidence_interval_lower": 27000,
                "confidence_interval_upper": 33000,
                "created_by": "James Wilson",
                "approved_by": "Dr. Robert Kim",
                "notes": "Superseded by DF-003 with updated assumptions.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "DF-009",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "forecast_type": ForecastType.SCENARIO,
                "status": ForecastStatus.ARCHIVED,
                "forecast_date": now - timedelta(days=180),
                "horizon_months": 12,
                "total_demand_units": 28000,
                "monthly_demand": [{"month": i + 1, "units": 2333} for i in range(12)],
                "enrollment_assumption": 400,
                "dropout_rate_pct": 20.0,
                "compliance_rate_pct": 80.0,
                "overage_pct": 25.0,
                "confidence_interval_lower": 24000,
                "confidence_interval_upper": 32000,
                "created_by": "Dr. Emily Park",
                "approved_by": "Dr. Michael Ross",
                "notes": "Conservative scenario archived after Phase II results.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "DF-010",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "forecast_type": ForecastType.HYBRID,
                "status": ForecastStatus.DRAFT,
                "forecast_date": now - timedelta(days=2),
                "horizon_months": 6,
                "total_demand_units": 11000,
                "monthly_demand": [{"month": i + 1, "units": 1833} for i in range(6)],
                "enrollment_assumption": 380,
                "dropout_rate_pct": 13.0,
                "compliance_rate_pct": 87.0,
                "overage_pct": 18.0,
                "confidence_interval_lower": 9500,
                "confidence_interval_upper": 12500,
                "created_by": "James Wilson",
                "approved_by": None,
                "notes": "Short-horizon draft for next two quarters.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DF-011",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "forecast_type": ForecastType.MONTE_CARLO,
                "status": ForecastStatus.APPROVED,
                "forecast_date": now - timedelta(days=50),
                "horizon_months": 12,
                "total_demand_units": 36000,
                "monthly_demand": [{"month": i + 1, "units": 3000} for i in range(12)],
                "enrollment_assumption": 600,
                "dropout_rate_pct": 11.0,
                "compliance_rate_pct": 89.0,
                "overage_pct": 20.0,
                "confidence_interval_lower": 32000,
                "confidence_interval_upper": 40000,
                "created_by": "Dr. Emily Park",
                "approved_by": "Dr. Robert Kim",
                "notes": "Monte Carlo validated against historical data.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DF-012",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "forecast_type": ForecastType.CONSUMPTION_BASED,
                "status": ForecastStatus.DRAFT,
                "forecast_date": now - timedelta(days=1),
                "horizon_months": 6,
                "total_demand_units": 19000,
                "monthly_demand": [{"month": i + 1, "units": 3167} for i in range(6)],
                "enrollment_assumption": 480,
                "dropout_rate_pct": 16.0,
                "compliance_rate_pct": 84.0,
                "overage_pct": 20.0,
                "confidence_interval_lower": 17000,
                "confidence_interval_upper": 21000,
                "created_by": "James Wilson",
                "approved_by": None,
                "notes": "Short-term consumption-based draft.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for f in forecasts_data:
            self._demand_forecasts[f["id"]] = DemandForecast(**f)

        # --- 10 Supply Plans ---
        plans_data = [
            {
                "id": "SP-001",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "plan_date": now - timedelta(days=55),
                "status": ForecastStatus.APPROVED,
                "forecast_id": "DF-001",
                "manufacturing_lead_weeks": 14,
                "packaging_lead_weeks": 4,
                "shipping_lead_weeks": 2,
                "planned_production_units": 28000,
                "planned_batches": 7,
                "batch_size": 4000,
                "total_cost_estimate": 1400000.0,
                "risk_level": SupplyRisk.LOW,
                "mitigation_strategy": "Buffer stock maintained at 20% overage.",
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Michael Ross",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "SP-002",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "plan_date": now - timedelta(days=40),
                "status": ForecastStatus.APPROVED,
                "forecast_id": "DF-003",
                "manufacturing_lead_weeks": 16,
                "packaging_lead_weeks": 5,
                "shipping_lead_weeks": 3,
                "planned_production_units": 65000,
                "planned_batches": 13,
                "batch_size": 5000,
                "total_cost_estimate": 3250000.0,
                "risk_level": SupplyRisk.MODERATE,
                "mitigation_strategy": "Dual sourcing agreement with secondary manufacturer.",
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Robert Kim",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "SP-003",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "plan_date": now - timedelta(days=25),
                "status": ForecastStatus.APPROVED,
                "forecast_id": "DF-005",
                "manufacturing_lead_weeks": 18,
                "packaging_lead_weeks": 6,
                "shipping_lead_weeks": 3,
                "planned_production_units": 85000,
                "planned_batches": 17,
                "batch_size": 5000,
                "total_cost_estimate": 5950000.0,
                "risk_level": SupplyRisk.HIGH,
                "mitigation_strategy": "Long lead time requires advance ordering; cold chain backup facility secured.",
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Michael Ross",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "SP-004",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 8mg HD",
                "plan_date": now - timedelta(days=70),
                "status": ForecastStatus.APPROVED,
                "forecast_id": "DF-007",
                "manufacturing_lead_weeks": 14,
                "packaging_lead_weeks": 4,
                "shipping_lead_weeks": 2,
                "planned_production_units": 21000,
                "planned_batches": 7,
                "batch_size": 3000,
                "total_cost_estimate": 1260000.0,
                "risk_level": SupplyRisk.LOW,
                "mitigation_strategy": None,
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Michael Ross",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "SP-005",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 200mg",
                "plan_date": now - timedelta(days=115),
                "status": ForecastStatus.SUPERSEDED,
                "forecast_id": "DF-008",
                "manufacturing_lead_weeks": 16,
                "packaging_lead_weeks": 5,
                "shipping_lead_weeks": 3,
                "planned_production_units": 36000,
                "planned_batches": 9,
                "batch_size": 4000,
                "total_cost_estimate": 1800000.0,
                "risk_level": SupplyRisk.LOW,
                "mitigation_strategy": None,
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Robert Kim",
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "SP-006",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "plan_date": now - timedelta(days=8),
                "status": ForecastStatus.UNDER_REVIEW,
                "forecast_id": "DF-006",
                "manufacturing_lead_weeks": 18,
                "packaging_lead_weeks": 6,
                "shipping_lead_weeks": 3,
                "planned_production_units": 45000,
                "planned_batches": 9,
                "batch_size": 5000,
                "total_cost_estimate": 3150000.0,
                "risk_level": SupplyRisk.MODERATE,
                "mitigation_strategy": "Monitoring Monte Carlo outputs for demand variability.",
                "created_by": "Supply Chain Ops",
                "approved_by": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SP-007",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "plan_date": now - timedelta(days=3),
                "status": ForecastStatus.DRAFT,
                "forecast_id": "DF-010",
                "manufacturing_lead_weeks": 12,
                "packaging_lead_weeks": 4,
                "shipping_lead_weeks": 2,
                "planned_production_units": 13000,
                "planned_batches": 4,
                "batch_size": 3250,
                "total_cost_estimate": 650000.0,
                "risk_level": SupplyRisk.LOW,
                "mitigation_strategy": None,
                "created_by": "Supply Chain Ops",
                "approved_by": None,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "SP-008",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "plan_date": now - timedelta(days=48),
                "status": ForecastStatus.APPROVED,
                "forecast_id": "DF-011",
                "manufacturing_lead_weeks": 16,
                "packaging_lead_weeks": 5,
                "shipping_lead_weeks": 3,
                "planned_production_units": 43000,
                "planned_batches": 9,
                "batch_size": 4778,
                "total_cost_estimate": 2150000.0,
                "risk_level": SupplyRisk.LOW,
                "mitigation_strategy": None,
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Robert Kim",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "SP-009",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "plan_date": now - timedelta(days=175),
                "status": ForecastStatus.ARCHIVED,
                "forecast_id": "DF-009",
                "manufacturing_lead_weeks": 18,
                "packaging_lead_weeks": 6,
                "shipping_lead_weeks": 3,
                "planned_production_units": 34000,
                "planned_batches": 7,
                "batch_size": 4857,
                "total_cost_estimate": 2380000.0,
                "risk_level": SupplyRisk.MODERATE,
                "mitigation_strategy": "Conservative plan archived with forecast.",
                "created_by": "Supply Chain Ops",
                "approved_by": "Dr. Michael Ross",
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "SP-010",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "plan_date": now - timedelta(days=1),
                "status": ForecastStatus.DRAFT,
                "forecast_id": None,
                "manufacturing_lead_weeks": 12,
                "packaging_lead_weeks": 4,
                "shipping_lead_weeks": 2,
                "planned_production_units": 5000,
                "planned_batches": 2,
                "batch_size": 2500,
                "total_cost_estimate": 250000.0,
                "risk_level": SupplyRisk.CRITICAL,
                "mitigation_strategy": "Emergency replenishment plan pending approval.",
                "created_by": "Supply Chain Ops",
                "approved_by": None,
                "created_at": now - timedelta(days=1),
            },
        ]

        for p in plans_data:
            self._supply_plans[p["id"]] = SupplyPlan(**p)

        # --- 12 Inventory Projections ---
        projections_data = [
            {
                "id": "IP-001",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "site_id": "SITE-101",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 1200,
                "projected_demand_30d": 400,
                "projected_demand_60d": 800,
                "projected_demand_90d": 1200,
                "reorder_point": 600,
                "safety_stock": 200,
                "weeks_of_supply": 12.0,
                "stockout_risk": SupplyRisk.LOW,
                "next_resupply_date": now + timedelta(days=45),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-002",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "site_id": "SITE-102",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 350,
                "projected_demand_30d": 300,
                "projected_demand_60d": 600,
                "projected_demand_90d": 900,
                "reorder_point": 450,
                "safety_stock": 150,
                "weeks_of_supply": 4.7,
                "stockout_risk": SupplyRisk.MODERATE,
                "next_resupply_date": now + timedelta(days=14),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-003",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "site_id": "SITE-103",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 2400,
                "projected_demand_30d": 600,
                "projected_demand_60d": 1200,
                "projected_demand_90d": 1800,
                "reorder_point": 900,
                "safety_stock": 300,
                "weeks_of_supply": 16.0,
                "stockout_risk": SupplyRisk.LOW,
                "next_resupply_date": now + timedelta(days=60),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-004",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "site_id": "SITE-104",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 180,
                "projected_demand_30d": 250,
                "projected_demand_60d": 500,
                "projected_demand_90d": 750,
                "reorder_point": 375,
                "safety_stock": 125,
                "weeks_of_supply": 2.9,
                "stockout_risk": SupplyRisk.HIGH,
                "next_resupply_date": now + timedelta(days=7),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-005",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "site_id": "SITE-105",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 50,
                "projected_demand_30d": 200,
                "projected_demand_60d": 400,
                "projected_demand_90d": 600,
                "reorder_point": 300,
                "safety_stock": 100,
                "weeks_of_supply": 1.0,
                "stockout_risk": SupplyRisk.CRITICAL,
                "next_resupply_date": now + timedelta(days=3),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-006",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "site_id": "SITE-106",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 800,
                "projected_demand_30d": 300,
                "projected_demand_60d": 600,
                "projected_demand_90d": 900,
                "reorder_point": 450,
                "safety_stock": 150,
                "weeks_of_supply": 10.7,
                "stockout_risk": SupplyRisk.LOW,
                "next_resupply_date": now + timedelta(days=50),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-007",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 8mg HD",
                "site_id": "SITE-101",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 600,
                "projected_demand_30d": 150,
                "projected_demand_60d": 300,
                "projected_demand_90d": 450,
                "reorder_point": 225,
                "safety_stock": 75,
                "weeks_of_supply": 16.0,
                "stockout_risk": SupplyRisk.LOW,
                "next_resupply_date": now + timedelta(days=75),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-008",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "site_id": "SITE-107",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 90,
                "projected_demand_30d": 200,
                "projected_demand_60d": 400,
                "projected_demand_90d": 600,
                "reorder_point": 300,
                "safety_stock": 100,
                "weeks_of_supply": 1.8,
                "stockout_risk": SupplyRisk.CRITICAL,
                "next_resupply_date": now + timedelta(days=5),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-009",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "site_id": "SITE-108",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 1500,
                "projected_demand_30d": 350,
                "projected_demand_60d": 700,
                "projected_demand_90d": 1050,
                "reorder_point": 525,
                "safety_stock": 175,
                "weeks_of_supply": 17.1,
                "stockout_risk": SupplyRisk.LOW,
                "next_resupply_date": now + timedelta(days=80),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-010",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "site_id": "SITE-105",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 500,
                "projected_demand_30d": 200,
                "projected_demand_60d": 400,
                "projected_demand_90d": 600,
                "reorder_point": 300,
                "safety_stock": 100,
                "weeks_of_supply": 10.0,
                "stockout_risk": SupplyRisk.LOW,
                "next_resupply_date": now + timedelta(days=40),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-011",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 200mg",
                "site_id": "SITE-102",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 220,
                "projected_demand_30d": 180,
                "projected_demand_60d": 360,
                "projected_demand_90d": 540,
                "reorder_point": 270,
                "safety_stock": 90,
                "weeks_of_supply": 4.9,
                "stockout_risk": SupplyRisk.MODERATE,
                "next_resupply_date": now + timedelta(days=18),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-012",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "site_id": "SITE-107",
                "projection_date": now - timedelta(days=1),
                "current_inventory": 300,
                "projected_demand_30d": 250,
                "projected_demand_60d": 500,
                "projected_demand_90d": 750,
                "reorder_point": 375,
                "safety_stock": 125,
                "weeks_of_supply": 4.8,
                "stockout_risk": SupplyRisk.MODERATE,
                "next_resupply_date": now + timedelta(days=20),
                "created_at": now - timedelta(days=1),
            },
        ]

        for p in projections_data:
            self._inventory_projections[p["id"]] = InventoryProjection(**p)

        # --- 10 Expiry Risks ---
        expiry_data = [
            {
                "id": "ER-001",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "batch_number": "EYLEA-B2025-001",
                "site_id": "SITE-101",
                "expiry_date": now + timedelta(days=30),
                "quantity_at_risk": 200,
                "days_to_expiry": 30,
                "risk_level": SupplyRisk.HIGH,
                "mitigation_action": "Redistribute to high-demand site SITE-102.",
                "can_redistribute": True,
                "redistribution_site": "SITE-102",
                "financial_impact": 12000.0,
                "flagged_by": "Inventory Manager",
                "resolved": False,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "ER-002",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "batch_number": "EYLEA-B2025-002",
                "site_id": "SITE-103",
                "expiry_date": now + timedelta(days=15),
                "quantity_at_risk": 100,
                "days_to_expiry": 15,
                "risk_level": SupplyRisk.CRITICAL,
                "mitigation_action": "Expedite patient dosing schedule.",
                "can_redistribute": False,
                "redistribution_site": None,
                "financial_impact": 6000.0,
                "flagged_by": "Site Pharmacist",
                "resolved": False,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "ER-003",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "batch_number": "DUPX-B2025-010",
                "site_id": "SITE-104",
                "expiry_date": now + timedelta(days=60),
                "quantity_at_risk": 500,
                "days_to_expiry": 60,
                "risk_level": SupplyRisk.MODERATE,
                "mitigation_action": None,
                "can_redistribute": True,
                "redistribution_site": None,
                "financial_impact": 45000.0,
                "flagged_by": "Inventory Manager",
                "resolved": False,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "ER-004",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "batch_number": "DUPX-B2024-008",
                "site_id": "SITE-107",
                "expiry_date": now + timedelta(days=7),
                "quantity_at_risk": 80,
                "days_to_expiry": 7,
                "risk_level": SupplyRisk.CRITICAL,
                "mitigation_action": "Emergency redistribution to SITE-103.",
                "can_redistribute": True,
                "redistribution_site": "SITE-103",
                "financial_impact": 7200.0,
                "flagged_by": "Site Pharmacist",
                "resolved": False,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "ER-005",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "batch_number": "LIB-B2025-005",
                "site_id": "SITE-105",
                "expiry_date": now + timedelta(days=45),
                "quantity_at_risk": 300,
                "days_to_expiry": 45,
                "risk_level": SupplyRisk.HIGH,
                "mitigation_action": "Coordinate with depot for redistribution.",
                "can_redistribute": True,
                "redistribution_site": "SITE-106",
                "financial_impact": 33000.0,
                "flagged_by": "Inventory Manager",
                "resolved": False,
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "ER-006",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "batch_number": "LIB-B2024-012",
                "site_id": "SITE-108",
                "expiry_date": now - timedelta(days=5),
                "quantity_at_risk": 150,
                "days_to_expiry": -5,
                "risk_level": SupplyRisk.CRITICAL,
                "mitigation_action": "Expired units quarantined for destruction.",
                "can_redistribute": False,
                "redistribution_site": None,
                "financial_impact": 16500.0,
                "flagged_by": "QA Manager",
                "resolved": True,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "ER-007",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 8mg HD",
                "batch_number": "EYLEA-HD-B2025-003",
                "site_id": "SITE-101",
                "expiry_date": now + timedelta(days=90),
                "quantity_at_risk": 100,
                "days_to_expiry": 90,
                "risk_level": SupplyRisk.LOW,
                "mitigation_action": None,
                "can_redistribute": True,
                "redistribution_site": None,
                "financial_impact": 8000.0,
                "flagged_by": "Inventory Manager",
                "resolved": False,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "ER-008",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 200mg",
                "batch_number": "DUPX-200-B2024-015",
                "site_id": "SITE-102",
                "expiry_date": now + timedelta(days=20),
                "quantity_at_risk": 60,
                "days_to_expiry": 20,
                "risk_level": SupplyRisk.HIGH,
                "mitigation_action": "Accelerate enrollment at site.",
                "can_redistribute": False,
                "redistribution_site": None,
                "financial_impact": 3600.0,
                "flagged_by": "Site Pharmacist",
                "resolved": False,
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "ER-009",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "batch_number": "LIB-B2024-009",
                "site_id": "SITE-106",
                "expiry_date": now - timedelta(days=20),
                "quantity_at_risk": 200,
                "days_to_expiry": -20,
                "risk_level": SupplyRisk.CRITICAL,
                "mitigation_action": "Expired units destroyed per SOP.",
                "can_redistribute": False,
                "redistribution_site": None,
                "financial_impact": 22000.0,
                "flagged_by": "QA Manager",
                "resolved": True,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "ER-010",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "batch_number": "EYLEA-B2025-007",
                "site_id": "SITE-105",
                "expiry_date": now + timedelta(days=120),
                "quantity_at_risk": 400,
                "days_to_expiry": 120,
                "risk_level": SupplyRisk.LOW,
                "mitigation_action": None,
                "can_redistribute": True,
                "redistribution_site": None,
                "financial_impact": 24000.0,
                "flagged_by": "Inventory Manager",
                "resolved": False,
                "created_at": now - timedelta(days=1),
            },
        ]

        for e in expiry_data:
            self._expiry_risks[e["id"]] = ExpiryRisk(**e)

        # --- 10 Depot Allocations ---
        depots_data = [
            {
                "id": "DA-001",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "depot_name": "US Northeast Depot",
                "region": "North America",
                "allocation_strategy": AllocationStrategy.DEMAND_DRIVEN,
                "allocation_date": now - timedelta(days=30),
                "sites_served": 5,
                "allocated_units": 8000,
                "shipped_units": 5500,
                "remaining_units": 2500,
                "utilization_pct": 68.75,
                "next_shipment_date": now + timedelta(days=10),
                "capacity_units": 12000,
                "is_active": True,
                "managed_by": "Depot Ops Northeast",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DA-002",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "depot_name": "US Southwest Depot",
                "region": "North America",
                "allocation_strategy": AllocationStrategy.PROPORTIONAL,
                "allocation_date": now - timedelta(days=28),
                "sites_served": 3,
                "allocated_units": 5000,
                "shipped_units": 3800,
                "remaining_units": 1200,
                "utilization_pct": 76.0,
                "next_shipment_date": now + timedelta(days=7),
                "capacity_units": 8000,
                "is_active": True,
                "managed_by": "Depot Ops Southwest",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DA-003",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "depot_name": "EU Central Depot",
                "region": "Europe",
                "allocation_strategy": AllocationStrategy.PRIORITY_BASED,
                "allocation_date": now - timedelta(days=25),
                "sites_served": 8,
                "allocated_units": 15000,
                "shipped_units": 9200,
                "remaining_units": 5800,
                "utilization_pct": 61.33,
                "next_shipment_date": now + timedelta(days=14),
                "capacity_units": 20000,
                "is_active": True,
                "managed_by": "EU Logistics Hub",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DA-004",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 300mg",
                "depot_name": "Asia Pacific Depot",
                "region": "Asia Pacific",
                "allocation_strategy": AllocationStrategy.DEMAND_DRIVEN,
                "allocation_date": now - timedelta(days=20),
                "sites_served": 6,
                "allocated_units": 10000,
                "shipped_units": 7500,
                "remaining_units": 2500,
                "utilization_pct": 75.0,
                "next_shipment_date": now + timedelta(days=5),
                "capacity_units": 15000,
                "is_active": True,
                "managed_by": "APAC Distribution Center",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DA-005",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "depot_name": "US Central Depot",
                "region": "North America",
                "allocation_strategy": AllocationStrategy.FIXED,
                "allocation_date": now - timedelta(days=22),
                "sites_served": 4,
                "allocated_units": 12000,
                "shipped_units": 8000,
                "remaining_units": 4000,
                "utilization_pct": 66.67,
                "next_shipment_date": now + timedelta(days=12),
                "capacity_units": 18000,
                "is_active": True,
                "managed_by": "Central Distribution",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "DA-006",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "depot_name": "EU Southern Depot",
                "region": "Europe",
                "allocation_strategy": AllocationStrategy.PROPORTIONAL,
                "allocation_date": now - timedelta(days=18),
                "sites_served": 5,
                "allocated_units": 8000,
                "shipped_units": 6200,
                "remaining_units": 1800,
                "utilization_pct": 77.5,
                "next_shipment_date": now + timedelta(days=8),
                "capacity_units": 10000,
                "is_active": True,
                "managed_by": "Southern EU Logistics",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "DA-007",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 8mg HD",
                "depot_name": "US Northeast Depot",
                "region": "North America",
                "allocation_strategy": AllocationStrategy.DEMAND_DRIVEN,
                "allocation_date": now - timedelta(days=15),
                "sites_served": 3,
                "allocated_units": 4000,
                "shipped_units": 2000,
                "remaining_units": 2000,
                "utilization_pct": 50.0,
                "next_shipment_date": now + timedelta(days=20),
                "capacity_units": 6000,
                "is_active": True,
                "managed_by": "Depot Ops Northeast",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "DA-008",
                "trial_id": DUPIXENT_TRIAL,
                "drug_name": "Dupilumab 200mg",
                "depot_name": "Latin America Depot",
                "region": "Latin America",
                "allocation_strategy": AllocationStrategy.PRIORITY_BASED,
                "allocation_date": now - timedelta(days=100),
                "sites_served": 4,
                "allocated_units": 6000,
                "shipped_units": 5800,
                "remaining_units": 200,
                "utilization_pct": 96.67,
                "next_shipment_date": None,
                "capacity_units": 8000,
                "is_active": False,
                "managed_by": "LATAM Distribution",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "DA-009",
                "trial_id": LIBTAYO_TRIAL,
                "drug_name": "Cemiplimab 350mg",
                "depot_name": "Middle East Depot",
                "region": "Middle East & Africa",
                "allocation_strategy": AllocationStrategy.FIXED,
                "allocation_date": now - timedelta(days=12),
                "sites_served": 2,
                "allocated_units": 3000,
                "shipped_units": 1500,
                "remaining_units": 1500,
                "utilization_pct": 50.0,
                "next_shipment_date": now + timedelta(days=15),
                "capacity_units": 5000,
                "is_active": True,
                "managed_by": "MEA Logistics",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DA-010",
                "trial_id": EYLEA_TRIAL,
                "drug_name": "Aflibercept 2mg",
                "depot_name": "Canada Depot",
                "region": "North America",
                "allocation_strategy": AllocationStrategy.PROPORTIONAL,
                "allocation_date": now - timedelta(days=10),
                "sites_served": 2,
                "allocated_units": 3000,
                "shipped_units": 1800,
                "remaining_units": 1200,
                "utilization_pct": 60.0,
                "next_shipment_date": now + timedelta(days=18),
                "capacity_units": 5000,
                "is_active": True,
                "managed_by": "Canada Distribution",
                "created_at": now - timedelta(days=10),
            },
        ]

        for d in depots_data:
            self._depot_allocations[d["id"]] = DepotAllocation(**d)

    # ------------------------------------------------------------------
    # Demand Forecasts
    # ------------------------------------------------------------------

    def list_demand_forecasts(
        self,
        *,
        trial_id: str | None = None,
        forecast_type: ForecastType | None = None,
        status: ForecastStatus | None = None,
    ) -> list[DemandForecast]:
        """List demand forecasts with optional filters."""
        with self._lock:
            result = list(self._demand_forecasts.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if forecast_type is not None:
            result = [f for f in result if f.forecast_type == forecast_type]
        if status is not None:
            result = [f for f in result if f.status == status]

        return sorted(result, key=lambda f: f.forecast_date, reverse=True)

    def get_demand_forecast(self, forecast_id: str) -> DemandForecast | None:
        """Get a single demand forecast by ID."""
        with self._lock:
            return self._demand_forecasts.get(forecast_id)

    def create_demand_forecast(self, payload: DemandForecastCreate) -> DemandForecast:
        """Create a new demand forecast."""
        now = datetime.now(timezone.utc)
        forecast_id = f"DF-{uuid4().hex[:8].upper()}"
        forecast = DemandForecast(
            id=forecast_id,
            trial_id=payload.trial_id,
            drug_name=payload.drug_name,
            forecast_type=payload.forecast_type,
            status=ForecastStatus.DRAFT,
            forecast_date=now,
            horizon_months=payload.horizon_months,
            total_demand_units=0,
            monthly_demand=[],
            enrollment_assumption=payload.enrollment_assumption,
            dropout_rate_pct=15.0,
            compliance_rate_pct=85.0,
            overage_pct=20.0,
            confidence_interval_lower=None,
            confidence_interval_upper=None,
            created_by=payload.created_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._demand_forecasts[forecast_id] = forecast
        logger.info("Created demand forecast %s for trial %s", forecast_id, payload.trial_id)
        return forecast

    def update_demand_forecast(
        self, forecast_id: str, payload: DemandForecastUpdate
    ) -> DemandForecast | None:
        """Update an existing demand forecast."""
        with self._lock:
            existing = self._demand_forecasts.get(forecast_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DemandForecast(**data)
            self._demand_forecasts[forecast_id] = updated
        return updated

    def delete_demand_forecast(self, forecast_id: str) -> bool:
        """Delete a demand forecast. Returns True if deleted."""
        with self._lock:
            if forecast_id in self._demand_forecasts:
                del self._demand_forecasts[forecast_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Supply Plans
    # ------------------------------------------------------------------

    def list_supply_plans(
        self,
        *,
        trial_id: str | None = None,
        status: ForecastStatus | None = None,
        risk_level: SupplyRisk | None = None,
    ) -> list[SupplyPlan]:
        """List supply plans with optional filters."""
        with self._lock:
            result = list(self._supply_plans.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]
        if risk_level is not None:
            result = [p for p in result if p.risk_level == risk_level]

        return sorted(result, key=lambda p: p.plan_date, reverse=True)

    def get_supply_plan(self, plan_id: str) -> SupplyPlan | None:
        """Get a single supply plan by ID."""
        with self._lock:
            return self._supply_plans.get(plan_id)

    def create_supply_plan(self, payload: SupplyPlanCreate) -> SupplyPlan:
        """Create a new supply plan."""
        now = datetime.now(timezone.utc)
        plan_id = f"SP-{uuid4().hex[:8].upper()}"
        plan = SupplyPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            drug_name=payload.drug_name,
            plan_date=now,
            status=ForecastStatus.DRAFT,
            forecast_id=payload.forecast_id,
            manufacturing_lead_weeks=12,
            packaging_lead_weeks=4,
            shipping_lead_weeks=2,
            planned_production_units=payload.planned_production_units,
            planned_batches=0,
            batch_size=0,
            total_cost_estimate=0.0,
            risk_level=SupplyRisk.LOW,
            mitigation_strategy=None,
            created_by=payload.created_by,
            approved_by=None,
            created_at=now,
        )
        with self._lock:
            self._supply_plans[plan_id] = plan
        logger.info("Created supply plan %s for trial %s", plan_id, payload.trial_id)
        return plan

    def update_supply_plan(
        self, plan_id: str, payload: SupplyPlanUpdate
    ) -> SupplyPlan | None:
        """Update an existing supply plan."""
        with self._lock:
            existing = self._supply_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SupplyPlan(**data)
            self._supply_plans[plan_id] = updated
        return updated

    def delete_supply_plan(self, plan_id: str) -> bool:
        """Delete a supply plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._supply_plans:
                del self._supply_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Inventory Projections
    # ------------------------------------------------------------------

    def list_inventory_projections(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        stockout_risk: SupplyRisk | None = None,
    ) -> list[InventoryProjection]:
        """List inventory projections with optional filters."""
        with self._lock:
            result = list(self._inventory_projections.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if site_id is not None:
            result = [p for p in result if p.site_id == site_id]
        if stockout_risk is not None:
            result = [p for p in result if p.stockout_risk == stockout_risk]

        return sorted(result, key=lambda p: p.weeks_of_supply)

    def get_inventory_projection(self, projection_id: str) -> InventoryProjection | None:
        """Get a single inventory projection by ID."""
        with self._lock:
            return self._inventory_projections.get(projection_id)

    def create_inventory_projection(
        self, payload: InventoryProjectionCreate
    ) -> InventoryProjection:
        """Create a new inventory projection."""
        now = datetime.now(timezone.utc)
        proj_id = f"IP-{uuid4().hex[:8].upper()}"
        projection = InventoryProjection(
            id=proj_id,
            trial_id=payload.trial_id,
            drug_name=payload.drug_name,
            site_id=payload.site_id,
            projection_date=now,
            current_inventory=payload.current_inventory,
            projected_demand_30d=0,
            projected_demand_60d=0,
            projected_demand_90d=0,
            reorder_point=payload.reorder_point,
            safety_stock=0,
            weeks_of_supply=0.0,
            stockout_risk=SupplyRisk.LOW,
            next_resupply_date=None,
            created_at=now,
        )
        with self._lock:
            self._inventory_projections[proj_id] = projection
        logger.info("Created inventory projection %s", proj_id)
        return projection

    def update_inventory_projection(
        self, projection_id: str, payload: InventoryProjectionUpdate
    ) -> InventoryProjection | None:
        """Update an existing inventory projection."""
        with self._lock:
            existing = self._inventory_projections.get(projection_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InventoryProjection(**data)
            self._inventory_projections[projection_id] = updated
        return updated

    def delete_inventory_projection(self, projection_id: str) -> bool:
        """Delete an inventory projection. Returns True if deleted."""
        with self._lock:
            if projection_id in self._inventory_projections:
                del self._inventory_projections[projection_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Expiry Risks
    # ------------------------------------------------------------------

    def list_expiry_risks(
        self,
        *,
        trial_id: str | None = None,
        risk_level: SupplyRisk | None = None,
        resolved: bool | None = None,
    ) -> list[ExpiryRisk]:
        """List expiry risks with optional filters."""
        with self._lock:
            result = list(self._expiry_risks.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if risk_level is not None:
            result = [e for e in result if e.risk_level == risk_level]
        if resolved is not None:
            result = [e for e in result if e.resolved == resolved]

        return sorted(result, key=lambda e: e.days_to_expiry)

    def get_expiry_risk(self, expiry_risk_id: str) -> ExpiryRisk | None:
        """Get a single expiry risk by ID."""
        with self._lock:
            return self._expiry_risks.get(expiry_risk_id)

    def create_expiry_risk(self, payload: ExpiryRiskCreate) -> ExpiryRisk:
        """Create a new expiry risk record."""
        now = datetime.now(timezone.utc)
        risk_id = f"ER-{uuid4().hex[:8].upper()}"
        days_to_expiry = (payload.expiry_date - now).days
        risk = ExpiryRisk(
            id=risk_id,
            trial_id=payload.trial_id,
            drug_name=payload.drug_name,
            batch_number=payload.batch_number,
            site_id=payload.site_id,
            expiry_date=payload.expiry_date,
            quantity_at_risk=payload.quantity_at_risk,
            days_to_expiry=days_to_expiry,
            risk_level=SupplyRisk.LOW,
            mitigation_action=None,
            can_redistribute=False,
            redistribution_site=None,
            financial_impact=0.0,
            flagged_by=payload.flagged_by,
            resolved=False,
            created_at=now,
        )
        with self._lock:
            self._expiry_risks[risk_id] = risk
        logger.info("Created expiry risk %s for batch %s", risk_id, payload.batch_number)
        return risk

    def update_expiry_risk(
        self, expiry_risk_id: str, payload: ExpiryRiskUpdate
    ) -> ExpiryRisk | None:
        """Update an existing expiry risk."""
        with self._lock:
            existing = self._expiry_risks.get(expiry_risk_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ExpiryRisk(**data)
            self._expiry_risks[expiry_risk_id] = updated
        return updated

    def delete_expiry_risk(self, expiry_risk_id: str) -> bool:
        """Delete an expiry risk. Returns True if deleted."""
        with self._lock:
            if expiry_risk_id in self._expiry_risks:
                del self._expiry_risks[expiry_risk_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Depot Allocations
    # ------------------------------------------------------------------

    def list_depot_allocations(
        self,
        *,
        trial_id: str | None = None,
        region: str | None = None,
        is_active: bool | None = None,
    ) -> list[DepotAllocation]:
        """List depot allocations with optional filters."""
        with self._lock:
            result = list(self._depot_allocations.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if region is not None:
            result = [d for d in result if d.region == region]
        if is_active is not None:
            result = [d for d in result if d.is_active == is_active]

        return sorted(result, key=lambda d: d.depot_name)

    def get_depot_allocation(self, allocation_id: str) -> DepotAllocation | None:
        """Get a single depot allocation by ID."""
        with self._lock:
            return self._depot_allocations.get(allocation_id)

    def create_depot_allocation(self, payload: DepotAllocationCreate) -> DepotAllocation:
        """Create a new depot allocation."""
        now = datetime.now(timezone.utc)
        alloc_id = f"DA-{uuid4().hex[:8].upper()}"
        allocation = DepotAllocation(
            id=alloc_id,
            trial_id=payload.trial_id,
            drug_name=payload.drug_name,
            depot_name=payload.depot_name,
            region=payload.region,
            allocation_strategy=payload.allocation_strategy,
            allocation_date=now,
            sites_served=0,
            allocated_units=payload.allocated_units,
            shipped_units=0,
            remaining_units=payload.allocated_units,
            utilization_pct=0.0,
            next_shipment_date=None,
            capacity_units=0,
            is_active=True,
            managed_by=payload.managed_by,
            created_at=now,
        )
        with self._lock:
            self._depot_allocations[alloc_id] = allocation
        logger.info("Created depot allocation %s at %s", alloc_id, payload.depot_name)
        return allocation

    def update_depot_allocation(
        self, allocation_id: str, payload: DepotAllocationUpdate
    ) -> DepotAllocation | None:
        """Update an existing depot allocation."""
        with self._lock:
            existing = self._depot_allocations.get(allocation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DepotAllocation(**data)
            self._depot_allocations[allocation_id] = updated
        return updated

    def delete_depot_allocation(self, allocation_id: str) -> bool:
        """Delete a depot allocation. Returns True if deleted."""
        with self._lock:
            if allocation_id in self._depot_allocations:
                del self._depot_allocations[allocation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalSupplyForecastMetrics:
        """Compute aggregated clinical supply forecast metrics."""
        with self._lock:
            forecasts = list(self._demand_forecasts.values())
            plans = list(self._supply_plans.values())
            projections = list(self._inventory_projections.values())
            expiry_risks = list(self._expiry_risks.values())
            depots = list(self._depot_allocations.values())

        # Forecasts by type
        forecasts_by_type: dict[str, int] = {}
        for f in forecasts:
            key = f.forecast_type.value
            forecasts_by_type[key] = forecasts_by_type.get(key, 0) + 1

        # Forecasts by status
        forecasts_by_status: dict[str, int] = {}
        for f in forecasts:
            key = f.status.value
            forecasts_by_status[key] = forecasts_by_status.get(key, 0) + 1

        # Plans by risk
        plans_by_risk: dict[str, int] = {}
        for p in plans:
            key = p.risk_level.value
            plans_by_risk[key] = plans_by_risk.get(key, 0) + 1

        # Sites at stockout risk (high or critical)
        sites_at_stockout_risk = sum(
            1 for p in projections
            if p.stockout_risk in (SupplyRisk.HIGH, SupplyRisk.CRITICAL)
        )

        # Unresolved expiry risks
        unresolved_expiry = sum(1 for e in expiry_risks if not e.resolved)

        # Total financial exposure (unresolved)
        total_financial = sum(
            e.financial_impact for e in expiry_risks if not e.resolved
        )

        # Depot metrics
        active_depots = sum(1 for d in depots if d.is_active)
        active_depot_list = [d for d in depots if d.is_active]
        avg_utilization = (
            round(
                sum(d.utilization_pct for d in active_depot_list)
                / len(active_depot_list),
                1,
            )
            if active_depot_list
            else 0.0
        )

        return ClinicalSupplyForecastMetrics(
            total_forecasts=len(forecasts),
            forecasts_by_type=forecasts_by_type,
            forecasts_by_status=forecasts_by_status,
            total_supply_plans=len(plans),
            plans_by_risk=plans_by_risk,
            total_projections=len(projections),
            sites_at_stockout_risk=sites_at_stockout_risk,
            total_expiry_risks=len(expiry_risks),
            unresolved_expiry_risks=unresolved_expiry,
            total_financial_exposure=round(total_financial, 2),
            total_depots=len(depots),
            active_depots=active_depots,
            avg_depot_utilization=avg_utilization,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalSupplyForecastService | None = None
_instance_lock = threading.Lock()


def get_clinical_supply_forecast_service() -> ClinicalSupplyForecastService:
    """Return the singleton ClinicalSupplyForecastService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalSupplyForecastService()
    return _instance


def reset_clinical_supply_forecast_service() -> ClinicalSupplyForecastService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalSupplyForecastService()
    return _instance
