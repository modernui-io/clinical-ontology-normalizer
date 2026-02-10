"""Clinical Supply Forecasting Service (CLINICAL-8).

Manages drug supply forecasting, demand planning, inventory optimization,
supply risk assessment, and resupply triggers for clinical trials.

Usage:
    from app.services.supply_forecasting_service import (
        get_supply_forecasting_service,
    )

    svc = get_supply_forecasting_service()
    forecasts = svc.list_forecasts()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.supply_forecasting import (
    DemandProjection,
    DemandProjectionCreate,
    DemandScenario,
    ForecastPeriod,
    ForecastStatus,
    InventorySnapshot,
    ResupplyAlert,
    ResupplyAlertAcknowledge,
    ResupplyTriggerType,
    RiskAssessmentStatus,
    SiteInventoryStatus,
    SupplyForecast,
    SupplyForecastCreate,
    SupplyForecastingMetrics,
    SupplyForecastUpdate,
    SupplyPlan,
    SupplyPlanCreate,
    SupplyPlanStatus,
    SupplyPlanUpdate,
    SupplyRiskAssessment,
    SupplyRiskAssessmentCreate,
    SupplyRiskAssessmentUpdate,
    SupplyRiskLevel,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trial IDs matching trial_eligibility_service
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

SITE_IDS = [
    "SITE-101", "SITE-102", "SITE-103", "SITE-104",
    "SITE-201", "SITE-202", "SITE-301", "SITE-302",
]


class SupplyForecastingService:
    """In-memory clinical supply forecasting engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._forecasts: dict[str, SupplyForecast] = {}
        self._demand_projections: dict[str, DemandProjection] = {}
        self._supply_plans: dict[str, SupplyPlan] = {}
        self._inventory_snapshots: dict[str, InventorySnapshot] = {}
        self._resupply_alerts: dict[str, ResupplyAlert] = {}
        self._risk_assessments: dict[str, SupplyRiskAssessment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic supply forecasting data for Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- Supply Forecasts ---
        forecasts = [
            SupplyForecast(
                id="SF-001",
                trial_id=EYLEA_TRIAL,
                product_name="EYLEA HD (Aflibercept) 8mg",
                forecast_period=ForecastPeriod.QUARTERLY,
                scenario=DemandScenario.BASE,
                status=ForecastStatus.ACTIVE,
                created_date=now - timedelta(days=30),
                created_by="Sarah Chen",
                current_inventory=480,
                projected_demand=360,
                projected_supply=400,
                safety_stock=120,
                reorder_point=200,
                lead_time_days=45,
                months_of_supply=4.0,
                risk_level=SupplyRiskLevel.LOW,
            ),
            SupplyForecast(
                id="SF-002",
                trial_id=DUPIXENT_TRIAL,
                product_name="Dupixent (Dupilumab) 300mg",
                forecast_period=ForecastPeriod.MONTHLY,
                scenario=DemandScenario.AGGRESSIVE,
                status=ForecastStatus.ACTIVE,
                created_date=now - timedelta(days=15),
                created_by="James Rodriguez",
                current_inventory=180,
                projected_demand=250,
                projected_supply=200,
                safety_stock=80,
                reorder_point=150,
                lead_time_days=60,
                months_of_supply=2.2,
                risk_level=SupplyRiskLevel.HIGH,
            ),
            SupplyForecast(
                id="SF-003",
                trial_id=LIBTAYO_TRIAL,
                product_name="Libtayo (Cemiplimab) 350mg",
                forecast_period=ForecastPeriod.QUARTERLY,
                scenario=DemandScenario.CONSERVATIVE,
                status=ForecastStatus.DRAFT,
                created_date=now - timedelta(days=5),
                created_by="Maria Thompson",
                current_inventory=140,
                projected_demand=100,
                projected_supply=150,
                safety_stock=50,
                reorder_point=80,
                lead_time_days=30,
                months_of_supply=4.2,
                risk_level=SupplyRiskLevel.LOW,
            ),
            SupplyForecast(
                id="SF-004",
                trial_id=EYLEA_TRIAL,
                product_name="EYLEA HD (Aflibercept) 8mg",
                forecast_period=ForecastPeriod.QUARTERLY,
                scenario=DemandScenario.WORST_CASE,
                status=ForecastStatus.SUPERSEDED,
                created_date=now - timedelta(days=90),
                created_by="Sarah Chen",
                current_inventory=300,
                projected_demand=500,
                projected_supply=350,
                safety_stock=120,
                reorder_point=200,
                lead_time_days=45,
                months_of_supply=1.8,
                risk_level=SupplyRiskLevel.CRITICAL,
            ),
        ]
        for f in forecasts:
            self._forecasts[f.id] = f

        # --- Demand Projections ---
        demand_projections = [
            DemandProjection(
                id="DP-001",
                forecast_id="SF-001",
                period_start=now,
                period_end=now + timedelta(days=90),
                projected_enrollment=45,
                doses_per_patient=6.0,
                total_doses_needed=270,
                wastage_factor=0.05,
                overage_pct=10.0,
                total_units_required=312,
            ),
            DemandProjection(
                id="DP-002",
                forecast_id="SF-001",
                period_start=now + timedelta(days=90),
                period_end=now + timedelta(days=180),
                projected_enrollment=50,
                doses_per_patient=6.0,
                total_doses_needed=300,
                wastage_factor=0.05,
                overage_pct=10.0,
                total_units_required=347,
            ),
            DemandProjection(
                id="DP-003",
                forecast_id="SF-002",
                period_start=now,
                period_end=now + timedelta(days=30),
                projected_enrollment=20,
                doses_per_patient=4.0,
                total_doses_needed=80,
                wastage_factor=0.03,
                overage_pct=15.0,
                total_units_required=95,
            ),
            DemandProjection(
                id="DP-004",
                forecast_id="SF-002",
                period_start=now + timedelta(days=30),
                period_end=now + timedelta(days=60),
                projected_enrollment=25,
                doses_per_patient=4.0,
                total_doses_needed=100,
                wastage_factor=0.03,
                overage_pct=15.0,
                total_units_required=119,
            ),
            DemandProjection(
                id="DP-005",
                forecast_id="SF-003",
                period_start=now,
                period_end=now + timedelta(days=90),
                projected_enrollment=15,
                doses_per_patient=3.0,
                total_doses_needed=45,
                wastage_factor=0.08,
                overage_pct=12.0,
                total_units_required=55,
            ),
            DemandProjection(
                id="DP-006",
                forecast_id="SF-003",
                period_start=now + timedelta(days=90),
                period_end=now + timedelta(days=180),
                projected_enrollment=18,
                doses_per_patient=3.0,
                total_doses_needed=54,
                wastage_factor=0.08,
                overage_pct=12.0,
                total_units_required=65,
            ),
            DemandProjection(
                id="DP-007",
                forecast_id="SF-004",
                period_start=now - timedelta(days=90),
                period_end=now,
                projected_enrollment=60,
                doses_per_patient=6.0,
                total_doses_needed=360,
                wastage_factor=0.10,
                overage_pct=15.0,
                total_units_required=455,
            ),
        ]
        for dp in demand_projections:
            self._demand_projections[dp.id] = dp

        # --- Supply Plans ---
        supply_plans = [
            SupplyPlan(
                id="SP-001",
                forecast_id="SF-001",
                supplier="Regeneron Pharmaceuticals",
                order_date=now - timedelta(days=20),
                expected_delivery=now + timedelta(days=25),
                quantity_ordered=200,
                unit_cost=850.00,
                total_cost=170000.00,
                status=SupplyPlanStatus.ORDERED,
                lot_number="LOT-2026-A001",
                expiry_date=now + timedelta(days=540),
            ),
            SupplyPlan(
                id="SP-002",
                forecast_id="SF-001",
                supplier="Regeneron Pharmaceuticals",
                order_date=now + timedelta(days=30),
                expected_delivery=now + timedelta(days=75),
                quantity_ordered=200,
                unit_cost=850.00,
                total_cost=170000.00,
                status=SupplyPlanStatus.PLANNED,
                lot_number=None,
                expiry_date=None,
            ),
            SupplyPlan(
                id="SP-003",
                forecast_id="SF-002",
                supplier="Sanofi (CMO)",
                order_date=now - timedelta(days=10),
                expected_delivery=now + timedelta(days=50),
                quantity_ordered=150,
                unit_cost=1200.00,
                total_cost=180000.00,
                status=SupplyPlanStatus.IN_TRANSIT,
                lot_number="LOT-2026-B003",
                expiry_date=now + timedelta(days=365),
            ),
            SupplyPlan(
                id="SP-004",
                forecast_id="SF-003",
                supplier="Regeneron Pharmaceuticals",
                order_date=now - timedelta(days=45),
                expected_delivery=now - timedelta(days=15),
                quantity_ordered=100,
                unit_cost=2100.00,
                total_cost=210000.00,
                status=SupplyPlanStatus.RECEIVED,
                lot_number="LOT-2026-C004",
                expiry_date=now + timedelta(days=720),
            ),
            SupplyPlan(
                id="SP-005",
                forecast_id="SF-002",
                supplier="Sanofi (CMO)",
                order_date=now + timedelta(days=20),
                expected_delivery=now + timedelta(days=80),
                quantity_ordered=100,
                unit_cost=1200.00,
                total_cost=120000.00,
                status=SupplyPlanStatus.PLANNED,
                lot_number=None,
                expiry_date=None,
            ),
        ]
        for sp in supply_plans:
            self._supply_plans[sp.id] = sp

        # --- Inventory Snapshots ---
        inventory_snapshots = [
            InventorySnapshot(
                id="IS-001",
                trial_id=EYLEA_TRIAL,
                site_id="SITE-101",
                product_name="EYLEA HD (Aflibercept) 8mg",
                snapshot_date=now,
                on_hand=120,
                allocated=30,
                available=90,
                expiring_30d=0,
                expiring_90d=5,
                below_safety_stock=False,
            ),
            InventorySnapshot(
                id="IS-002",
                trial_id=EYLEA_TRIAL,
                site_id="SITE-102",
                product_name="EYLEA HD (Aflibercept) 8mg",
                snapshot_date=now,
                on_hand=80,
                allocated=25,
                available=55,
                expiring_30d=0,
                expiring_90d=3,
                below_safety_stock=False,
            ),
            InventorySnapshot(
                id="IS-003",
                trial_id=EYLEA_TRIAL,
                site_id="SITE-103",
                product_name="EYLEA HD (Aflibercept) 8mg",
                snapshot_date=now,
                on_hand=15,
                allocated=10,
                available=5,
                expiring_30d=2,
                expiring_90d=5,
                below_safety_stock=True,
            ),
            InventorySnapshot(
                id="IS-004",
                trial_id=DUPIXENT_TRIAL,
                site_id="SITE-201",
                product_name="Dupixent (Dupilumab) 300mg",
                snapshot_date=now,
                on_hand=60,
                allocated=20,
                available=40,
                expiring_30d=0,
                expiring_90d=8,
                below_safety_stock=False,
            ),
            InventorySnapshot(
                id="IS-005",
                trial_id=DUPIXENT_TRIAL,
                site_id="SITE-202",
                product_name="Dupixent (Dupilumab) 300mg",
                snapshot_date=now,
                on_hand=25,
                allocated=15,
                available=10,
                expiring_30d=3,
                expiring_90d=10,
                below_safety_stock=True,
            ),
            InventorySnapshot(
                id="IS-006",
                trial_id=DUPIXENT_TRIAL,
                site_id="SITE-104",
                product_name="Dupixent (Dupilumab) 300mg",
                snapshot_date=now,
                on_hand=8,
                allocated=5,
                available=3,
                expiring_30d=2,
                expiring_90d=4,
                below_safety_stock=True,
            ),
            InventorySnapshot(
                id="IS-007",
                trial_id=LIBTAYO_TRIAL,
                site_id="SITE-301",
                product_name="Libtayo (Cemiplimab) 350mg",
                snapshot_date=now,
                on_hand=50,
                allocated=12,
                available=38,
                expiring_30d=0,
                expiring_90d=0,
                below_safety_stock=False,
            ),
            InventorySnapshot(
                id="IS-008",
                trial_id=LIBTAYO_TRIAL,
                site_id="SITE-302",
                product_name="Libtayo (Cemiplimab) 350mg",
                snapshot_date=now,
                on_hand=40,
                allocated=8,
                available=32,
                expiring_30d=0,
                expiring_90d=2,
                below_safety_stock=False,
            ),
            InventorySnapshot(
                id="IS-009",
                trial_id=EYLEA_TRIAL,
                site_id="SITE-104",
                product_name="EYLEA HD (Aflibercept) 8mg",
                snapshot_date=now,
                on_hand=10,
                allocated=8,
                available=2,
                expiring_30d=4,
                expiring_90d=6,
                below_safety_stock=True,
            ),
        ]
        for snap in inventory_snapshots:
            self._inventory_snapshots[snap.id] = snap

        # --- Resupply Alerts ---
        resupply_alerts = [
            ResupplyAlert(
                id="RA-001",
                trial_id=EYLEA_TRIAL,
                site_id="SITE-103",
                product_name="EYLEA HD (Aflibercept) 8mg",
                alert_type=SupplyRiskLevel.HIGH,
                trigger_type=ResupplyTriggerType.THRESHOLD,
                current_level=5,
                threshold_level=20,
                recommended_quantity=40,
                created_date=now - timedelta(hours=6),
                acknowledged=False,
                acknowledged_by=None,
            ),
            ResupplyAlert(
                id="RA-002",
                trial_id=DUPIXENT_TRIAL,
                site_id="SITE-202",
                product_name="Dupixent (Dupilumab) 300mg",
                alert_type=SupplyRiskLevel.MODERATE,
                trigger_type=ResupplyTriggerType.THRESHOLD,
                current_level=10,
                threshold_level=15,
                recommended_quantity=30,
                created_date=now - timedelta(hours=12),
                acknowledged=True,
                acknowledged_by="James Rodriguez",
            ),
            ResupplyAlert(
                id="RA-003",
                trial_id=DUPIXENT_TRIAL,
                site_id="SITE-104",
                product_name="Dupixent (Dupilumab) 300mg",
                alert_type=SupplyRiskLevel.CRITICAL,
                trigger_type=ResupplyTriggerType.EMERGENCY,
                current_level=3,
                threshold_level=15,
                recommended_quantity=50,
                created_date=now - timedelta(hours=2),
                acknowledged=False,
                acknowledged_by=None,
            ),
            ResupplyAlert(
                id="RA-004",
                trial_id=EYLEA_TRIAL,
                site_id="SITE-104",
                product_name="EYLEA HD (Aflibercept) 8mg",
                alert_type=SupplyRiskLevel.CRITICAL,
                trigger_type=ResupplyTriggerType.THRESHOLD,
                current_level=2,
                threshold_level=20,
                recommended_quantity=45,
                created_date=now - timedelta(hours=1),
                acknowledged=False,
                acknowledged_by=None,
            ),
        ]
        for alert in resupply_alerts:
            self._resupply_alerts[alert.id] = alert

        # --- Risk Assessments ---
        risk_assessments = [
            SupplyRiskAssessment(
                id="SRA-001",
                forecast_id="SF-001",
                risk_category="supplier",
                description="Single-source dependency for aflibercept API manufacturing",
                probability=0.2,
                impact=0.9,
                risk_score=0.18,
                mitigation_plan="Qualify secondary API supplier; maintain 6-month strategic reserve",
                owner="Sarah Chen",
                status=RiskAssessmentStatus.MITIGATING,
            ),
            SupplyRiskAssessment(
                id="SRA-002",
                forecast_id="SF-002",
                risk_category="logistics",
                description="Cold chain disruption risk during international shipping",
                probability=0.15,
                impact=0.7,
                risk_score=0.105,
                mitigation_plan="Implement redundant cold-chain monitoring; pre-qualify backup logistics providers",
                owner="James Rodriguez",
                status=RiskAssessmentStatus.IDENTIFIED,
            ),
            SupplyRiskAssessment(
                id="SRA-003",
                forecast_id="SF-002",
                risk_category="regulatory",
                description="Potential import permit delays for dupilumab in EU sites",
                probability=0.3,
                impact=0.8,
                risk_score=0.24,
                mitigation_plan="Submit import permits 90 days in advance; engage local regulatory consultants",
                owner="Maria Thompson",
                status=RiskAssessmentStatus.MITIGATING,
            ),
            SupplyRiskAssessment(
                id="SRA-004",
                forecast_id="SF-003",
                risk_category="demand",
                description="Higher-than-expected enrollment may deplete cemiplimab stock faster",
                probability=0.25,
                impact=0.6,
                risk_score=0.15,
                mitigation_plan="Monitor enrollment weekly; trigger early reorder at 80% of projected demand",
                owner="Maria Thompson",
                status=RiskAssessmentStatus.IDENTIFIED,
            ),
            SupplyRiskAssessment(
                id="SRA-005",
                forecast_id="SF-001",
                risk_category="quality",
                description="Lot release testing failure may delay product availability",
                probability=0.1,
                impact=0.85,
                risk_score=0.085,
                mitigation_plan="Maintain backup lots; implement concurrent stability testing",
                owner="Sarah Chen",
                status=RiskAssessmentStatus.RESOLVED,
            ),
        ]
        for ra in risk_assessments:
            self._risk_assessments[ra.id] = ra

        logger.info(
            "Supply forecasting service initialised with %d forecasts, %d demand projections, "
            "%d supply plans, %d inventory snapshots, %d resupply alerts, %d risk assessments",
            len(self._forecasts),
            len(self._demand_projections),
            len(self._supply_plans),
            len(self._inventory_snapshots),
            len(self._resupply_alerts),
            len(self._risk_assessments),
        )

    # ------------------------------------------------------------------
    # Forecast CRUD
    # ------------------------------------------------------------------

    def list_forecasts(
        self,
        trial_id: str | None = None,
        status: ForecastStatus | None = None,
        scenario: DemandScenario | None = None,
    ) -> list[SupplyForecast]:
        """List supply forecasts with optional filtering."""
        with self._lock:
            items = list(self._forecasts.values())

        if trial_id:
            items = [f for f in items if f.trial_id == trial_id]
        if status:
            items = [f for f in items if f.status == status]
        if scenario:
            items = [f for f in items if f.scenario == scenario]

        return items

    def get_forecast(self, forecast_id: str) -> SupplyForecast | None:
        """Get a single supply forecast by ID."""
        with self._lock:
            return self._forecasts.get(forecast_id)

    def create_forecast(self, data: SupplyForecastCreate) -> SupplyForecast:
        """Create a new supply forecast."""
        now = datetime.now(timezone.utc)
        forecast_id = f"SF-{uuid4().hex[:6].upper()}"

        record = SupplyForecast(
            id=forecast_id,
            trial_id=data.trial_id,
            product_name=data.product_name,
            forecast_period=data.forecast_period,
            scenario=data.scenario,
            status=ForecastStatus.DRAFT,
            created_date=now,
            created_by=data.created_by,
            current_inventory=data.current_inventory,
            projected_demand=0,
            projected_supply=0,
            safety_stock=data.safety_stock,
            reorder_point=int(data.safety_stock * 1.5),
            lead_time_days=data.lead_time_days,
            months_of_supply=0.0,
            risk_level=SupplyRiskLevel.LOW,
        )
        with self._lock:
            self._forecasts[forecast_id] = record
        logger.info("Created supply forecast %s for trial %s", forecast_id, data.trial_id)
        return record

    def update_forecast(self, forecast_id: str, data: SupplyForecastUpdate) -> SupplyForecast | None:
        """Update an existing supply forecast."""
        with self._lock:
            if forecast_id not in self._forecasts:
                return None
            existing = self._forecasts[forecast_id]
            updates = data.model_dump(exclude_none=True)
            updated = existing.model_copy(update=updates)
            self._forecasts[forecast_id] = updated
        logger.info("Updated supply forecast %s", forecast_id)
        return updated

    def delete_forecast(self, forecast_id: str) -> bool:
        """Delete a supply forecast."""
        with self._lock:
            if forecast_id not in self._forecasts:
                return False
            del self._forecasts[forecast_id]
        logger.info("Deleted supply forecast %s", forecast_id)
        return True

    # ------------------------------------------------------------------
    # Forecast Generation
    # ------------------------------------------------------------------

    def generate_forecast(self, forecast_id: str) -> SupplyForecast | None:
        """Generate/recalculate a supply forecast based on demand projections and supply plans.

        Aggregates demand projections to compute projected demand, aggregates supply
        plans to compute projected supply, and calculates months of supply and risk level.
        """
        with self._lock:
            if forecast_id not in self._forecasts:
                return None
            forecast = self._forecasts[forecast_id]

            # Aggregate demand projections
            projections = [
                dp for dp in self._demand_projections.values()
                if dp.forecast_id == forecast_id
            ]
            total_demand = sum(dp.total_units_required for dp in projections)

            # Aggregate supply plans (exclude cancelled)
            plans = [
                sp for sp in self._supply_plans.values()
                if sp.forecast_id == forecast_id and sp.status != SupplyPlanStatus.CANCELLED
            ]
            total_supply = sum(sp.quantity_ordered for sp in plans)

            # Calculate months of supply
            if total_demand > 0 and len(projections) > 0:
                # Average monthly demand
                total_period_months = 0.0
                for dp in projections:
                    days = (dp.period_end - dp.period_start).days
                    total_period_months += days / 30.0
                avg_monthly_demand = total_demand / total_period_months if total_period_months > 0 else total_demand
                months_of_supply = (forecast.current_inventory + total_supply) / avg_monthly_demand
            else:
                months_of_supply = forecast.months_of_supply

            # Determine risk level
            risk_level = self._calculate_risk_level(
                months_of_supply, forecast.safety_stock, forecast.current_inventory
            )

            updated = forecast.model_copy(update={
                "projected_demand": total_demand,
                "projected_supply": total_supply,
                "months_of_supply": round(months_of_supply, 2),
                "risk_level": risk_level,
                "status": ForecastStatus.ACTIVE,
            })
            self._forecasts[forecast_id] = updated

        logger.info("Generated forecast %s: demand=%d, supply=%d, MoS=%.2f",
                     forecast_id, total_demand, total_supply, months_of_supply)
        return updated

    def _calculate_risk_level(
        self, months_of_supply: float, safety_stock: int, current_inventory: int
    ) -> SupplyRiskLevel:
        """Calculate supply risk level based on months of supply and safety stock."""
        if current_inventory <= safety_stock * 0.5 or months_of_supply < 1.0:
            return SupplyRiskLevel.CRITICAL
        if current_inventory <= safety_stock or months_of_supply < 2.0:
            return SupplyRiskLevel.HIGH
        if months_of_supply < 3.0:
            return SupplyRiskLevel.MODERATE
        return SupplyRiskLevel.LOW

    # ------------------------------------------------------------------
    # Demand Projection CRUD
    # ------------------------------------------------------------------

    def list_demand_projections(
        self, forecast_id: str | None = None
    ) -> list[DemandProjection]:
        """List demand projections with optional filtering by forecast."""
        with self._lock:
            items = list(self._demand_projections.values())

        if forecast_id:
            items = [dp for dp in items if dp.forecast_id == forecast_id]

        return items

    def get_demand_projection(self, projection_id: str) -> DemandProjection | None:
        """Get a single demand projection by ID."""
        with self._lock:
            return self._demand_projections.get(projection_id)

    def create_demand_projection(self, data: DemandProjectionCreate) -> DemandProjection | None:
        """Create a new demand projection.

        Returns None if the parent forecast does not exist.
        Automatically computes total_doses_needed and total_units_required.
        """
        with self._lock:
            if data.forecast_id not in self._forecasts:
                return None

        projection_id = f"DP-{uuid4().hex[:6].upper()}"
        total_doses = int(data.projected_enrollment * data.doses_per_patient)
        wastage_units = int(math.ceil(total_doses * data.wastage_factor))
        subtotal = total_doses + wastage_units
        overage_units = int(math.ceil(subtotal * (data.overage_pct / 100.0)))
        total_units = subtotal + overage_units

        record = DemandProjection(
            id=projection_id,
            forecast_id=data.forecast_id,
            period_start=data.period_start,
            period_end=data.period_end,
            projected_enrollment=data.projected_enrollment,
            doses_per_patient=data.doses_per_patient,
            total_doses_needed=total_doses,
            wastage_factor=data.wastage_factor,
            overage_pct=data.overage_pct,
            total_units_required=total_units,
        )
        with self._lock:
            self._demand_projections[projection_id] = record
        logger.info("Created demand projection %s for forecast %s", projection_id, data.forecast_id)
        return record

    def delete_demand_projection(self, projection_id: str) -> bool:
        """Delete a demand projection."""
        with self._lock:
            if projection_id not in self._demand_projections:
                return False
            del self._demand_projections[projection_id]
        logger.info("Deleted demand projection %s", projection_id)
        return True

    # ------------------------------------------------------------------
    # Supply Plan CRUD
    # ------------------------------------------------------------------

    def list_supply_plans(
        self,
        forecast_id: str | None = None,
        status: SupplyPlanStatus | None = None,
    ) -> list[SupplyPlan]:
        """List supply plans with optional filtering."""
        with self._lock:
            items = list(self._supply_plans.values())

        if forecast_id:
            items = [sp for sp in items if sp.forecast_id == forecast_id]
        if status:
            items = [sp for sp in items if sp.status == status]

        return items

    def get_supply_plan(self, plan_id: str) -> SupplyPlan | None:
        """Get a single supply plan by ID."""
        with self._lock:
            return self._supply_plans.get(plan_id)

    def create_supply_plan(self, data: SupplyPlanCreate) -> SupplyPlan | None:
        """Create a new supply plan order.

        Returns None if the parent forecast does not exist.
        """
        with self._lock:
            if data.forecast_id not in self._forecasts:
                return None

        plan_id = f"SP-{uuid4().hex[:6].upper()}"
        total_cost = round(data.quantity_ordered * data.unit_cost, 2)

        record = SupplyPlan(
            id=plan_id,
            forecast_id=data.forecast_id,
            supplier=data.supplier,
            order_date=data.order_date,
            expected_delivery=data.expected_delivery,
            quantity_ordered=data.quantity_ordered,
            unit_cost=data.unit_cost,
            total_cost=total_cost,
            status=SupplyPlanStatus.PLANNED,
            lot_number=None,
            expiry_date=None,
        )
        with self._lock:
            self._supply_plans[plan_id] = record
        logger.info("Created supply plan %s for forecast %s", plan_id, data.forecast_id)
        return record

    def update_supply_plan(self, plan_id: str, data: SupplyPlanUpdate) -> SupplyPlan | None:
        """Update a supply plan order."""
        with self._lock:
            if plan_id not in self._supply_plans:
                return None
            existing = self._supply_plans[plan_id]
            updates = data.model_dump(exclude_none=True)
            updated = existing.model_copy(update=updates)
            self._supply_plans[plan_id] = updated
        logger.info("Updated supply plan %s", plan_id)
        return updated

    def delete_supply_plan(self, plan_id: str) -> bool:
        """Delete a supply plan order."""
        with self._lock:
            if plan_id not in self._supply_plans:
                return False
            del self._supply_plans[plan_id]
        logger.info("Deleted supply plan %s", plan_id)
        return True

    # ------------------------------------------------------------------
    # Inventory Snapshot CRUD
    # ------------------------------------------------------------------

    def list_inventory_snapshots(
        self,
        trial_id: str | None = None,
        site_id: str | None = None,
        product_name: str | None = None,
    ) -> list[InventorySnapshot]:
        """List inventory snapshots with optional filtering."""
        with self._lock:
            items = list(self._inventory_snapshots.values())

        if trial_id:
            items = [s for s in items if s.trial_id == trial_id]
        if site_id:
            items = [s for s in items if s.site_id == site_id]
        if product_name:
            items = [s for s in items if s.product_name == product_name]

        return items

    def get_inventory_snapshot(self, snapshot_id: str) -> InventorySnapshot | None:
        """Get a single inventory snapshot by ID."""
        with self._lock:
            return self._inventory_snapshots.get(snapshot_id)

    def delete_inventory_snapshot(self, snapshot_id: str) -> bool:
        """Delete an inventory snapshot."""
        with self._lock:
            if snapshot_id not in self._inventory_snapshots:
                return False
            del self._inventory_snapshots[snapshot_id]
        logger.info("Deleted inventory snapshot %s", snapshot_id)
        return True

    # ------------------------------------------------------------------
    # Resupply Alert Management
    # ------------------------------------------------------------------

    def list_resupply_alerts(
        self,
        trial_id: str | None = None,
        site_id: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[ResupplyAlert]:
        """List resupply alerts with optional filtering."""
        with self._lock:
            items = list(self._resupply_alerts.values())

        if trial_id:
            items = [a for a in items if a.trial_id == trial_id]
        if site_id:
            items = [a for a in items if a.site_id == site_id]
        if acknowledged is not None:
            items = [a for a in items if a.acknowledged == acknowledged]

        return items

    def get_resupply_alert(self, alert_id: str) -> ResupplyAlert | None:
        """Get a single resupply alert by ID."""
        with self._lock:
            return self._resupply_alerts.get(alert_id)

    def acknowledge_resupply_alert(
        self, alert_id: str, data: ResupplyAlertAcknowledge
    ) -> ResupplyAlert | None:
        """Acknowledge a resupply alert.

        Returns None if not found. Raises ValueError if already acknowledged.
        """
        with self._lock:
            if alert_id not in self._resupply_alerts:
                return None
            existing = self._resupply_alerts[alert_id]
            if existing.acknowledged:
                raise ValueError(f"Alert '{alert_id}' has already been acknowledged")
            updated = existing.model_copy(update={
                "acknowledged": True,
                "acknowledged_by": data.acknowledged_by,
            })
            self._resupply_alerts[alert_id] = updated
        logger.info("Acknowledged resupply alert %s by %s", alert_id, data.acknowledged_by)
        return updated

    def trigger_resupply(
        self,
        trial_id: str,
        site_id: str,
        product_name: str,
        current_level: int,
        threshold_level: int,
        recommended_quantity: int,
        trigger_type: ResupplyTriggerType = ResupplyTriggerType.MANUAL,
    ) -> ResupplyAlert:
        """Create a resupply alert manually or programmatically."""
        now = datetime.now(timezone.utc)
        alert_id = f"RA-{uuid4().hex[:6].upper()}"

        # Determine alert type based on how far below threshold
        if current_level <= threshold_level * 0.25:
            alert_type = SupplyRiskLevel.CRITICAL
        elif current_level <= threshold_level * 0.5:
            alert_type = SupplyRiskLevel.HIGH
        elif current_level <= threshold_level * 0.75:
            alert_type = SupplyRiskLevel.MODERATE
        else:
            alert_type = SupplyRiskLevel.LOW

        record = ResupplyAlert(
            id=alert_id,
            trial_id=trial_id,
            site_id=site_id,
            product_name=product_name,
            alert_type=alert_type,
            trigger_type=trigger_type,
            current_level=current_level,
            threshold_level=threshold_level,
            recommended_quantity=recommended_quantity,
            created_date=now,
            acknowledged=False,
            acknowledged_by=None,
        )
        with self._lock:
            self._resupply_alerts[alert_id] = record
        logger.info("Triggered resupply alert %s for %s at %s", alert_id, product_name, site_id)
        return record

    # ------------------------------------------------------------------
    # Supply Risk Assessment CRUD
    # ------------------------------------------------------------------

    def list_risk_assessments(
        self,
        forecast_id: str | None = None,
        status: RiskAssessmentStatus | None = None,
    ) -> list[SupplyRiskAssessment]:
        """List supply risk assessments with optional filtering."""
        with self._lock:
            items = list(self._risk_assessments.values())

        if forecast_id:
            items = [ra for ra in items if ra.forecast_id == forecast_id]
        if status:
            items = [ra for ra in items if ra.status == status]

        return items

    def get_risk_assessment(self, assessment_id: str) -> SupplyRiskAssessment | None:
        """Get a single risk assessment by ID."""
        with self._lock:
            return self._risk_assessments.get(assessment_id)

    def create_risk_assessment(self, data: SupplyRiskAssessmentCreate) -> SupplyRiskAssessment | None:
        """Create a new supply risk assessment.

        Returns None if the parent forecast does not exist.
        """
        with self._lock:
            if data.forecast_id not in self._forecasts:
                return None

        assessment_id = f"SRA-{uuid4().hex[:6].upper()}"
        risk_score = round(data.probability * data.impact, 4)

        record = SupplyRiskAssessment(
            id=assessment_id,
            forecast_id=data.forecast_id,
            risk_category=data.risk_category,
            description=data.description,
            probability=data.probability,
            impact=data.impact,
            risk_score=risk_score,
            mitigation_plan=data.mitigation_plan,
            owner=data.owner,
            status=RiskAssessmentStatus.IDENTIFIED,
        )
        with self._lock:
            self._risk_assessments[assessment_id] = record
        logger.info("Created risk assessment %s for forecast %s", assessment_id, data.forecast_id)
        return record

    def update_risk_assessment(
        self, assessment_id: str, data: SupplyRiskAssessmentUpdate
    ) -> SupplyRiskAssessment | None:
        """Update a supply risk assessment."""
        with self._lock:
            if assessment_id not in self._risk_assessments:
                return None
            existing = self._risk_assessments[assessment_id]
            updates = data.model_dump(exclude_none=True)

            # Recalculate risk score if probability or impact changed
            prob = updates.get("probability", existing.probability)
            imp = updates.get("impact", existing.impact)
            updates["risk_score"] = round(prob * imp, 4)

            updated = existing.model_copy(update=updates)
            self._risk_assessments[assessment_id] = updated
        logger.info("Updated risk assessment %s", assessment_id)
        return updated

    def delete_risk_assessment(self, assessment_id: str) -> bool:
        """Delete a supply risk assessment."""
        with self._lock:
            if assessment_id not in self._risk_assessments:
                return False
            del self._risk_assessments[assessment_id]
        logger.info("Deleted risk assessment %s", assessment_id)
        return True

    def assess_supply_risk(self, forecast_id: str) -> list[SupplyRiskAssessment]:
        """Retrieve all risk assessments for a forecast, sorted by risk score descending."""
        with self._lock:
            items = [
                ra for ra in self._risk_assessments.values()
                if ra.forecast_id == forecast_id
            ]
        return sorted(items, key=lambda ra: ra.risk_score, reverse=True)

    # ------------------------------------------------------------------
    # Site Inventory Status
    # ------------------------------------------------------------------

    def get_site_inventory_status(self, site_id: str) -> SiteInventoryStatus | None:
        """Get aggregated inventory status for a specific site."""
        with self._lock:
            snapshots = [
                s for s in self._inventory_snapshots.values()
                if s.site_id == site_id
            ]

        if not snapshots:
            return None

        total_on_hand = sum(s.on_hand for s in snapshots)
        total_available = sum(s.available for s in snapshots)
        any_below = any(s.below_safety_stock for s in snapshots)
        trial_id = snapshots[0].trial_id

        # Count active (unacknowledged) alerts for this site
        with self._lock:
            active_alerts = sum(
                1 for a in self._resupply_alerts.values()
                if a.site_id == site_id and not a.acknowledged
            )

        return SiteInventoryStatus(
            site_id=site_id,
            trial_id=trial_id,
            products=snapshots,
            total_on_hand=total_on_hand,
            total_available=total_available,
            any_below_safety_stock=any_below,
            active_alerts=active_alerts,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SupplyForecastingMetrics:
        """Calculate aggregated supply forecasting metrics."""
        with self._lock:
            forecasts = list(self._forecasts.values())
            demand_projections = list(self._demand_projections.values())
            supply_plans = list(self._supply_plans.values())
            inventory_snapshots = list(self._inventory_snapshots.values())
            resupply_alerts = list(self._resupply_alerts.values())
            risk_assessments = list(self._risk_assessments.values())

        total_forecasts = len(forecasts)
        active_forecasts = sum(1 for f in forecasts if f.status == ForecastStatus.ACTIVE)

        total_demand = len(demand_projections)
        total_plans = len(supply_plans)
        pending_orders = sum(
            1 for sp in supply_plans
            if sp.status in (SupplyPlanStatus.PLANNED, SupplyPlanStatus.ORDERED)
        )

        total_snapshots = len(inventory_snapshots)
        sites_below = sum(1 for s in inventory_snapshots if s.below_safety_stock)

        active_alerts = sum(1 for a in resupply_alerts if not a.acknowledged)

        total_risks = len(risk_assessments)
        high_critical_risks = sum(
            1 for ra in risk_assessments
            if ra.risk_score >= 0.15
            and ra.status not in (RiskAssessmentStatus.RESOLVED, RiskAssessmentStatus.ACCEPTED)
        )

        # Average months of supply across active forecasts
        active_mos = [f.months_of_supply for f in forecasts if f.status == ForecastStatus.ACTIVE]
        avg_mos = round(sum(active_mos) / len(active_mos), 2) if active_mos else None

        # Total order value
        total_value = sum(sp.total_cost for sp in supply_plans)

        return SupplyForecastingMetrics(
            total_forecasts=total_forecasts,
            active_forecasts=active_forecasts,
            total_demand_projections=total_demand,
            total_supply_plans=total_plans,
            pending_orders=pending_orders,
            total_inventory_snapshots=total_snapshots,
            sites_below_safety_stock=sites_below,
            active_resupply_alerts=active_alerts,
            total_risk_assessments=total_risks,
            high_critical_risks=high_critical_risks,
            avg_months_of_supply=avg_mos,
            total_order_value=total_value,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SupplyForecastingService | None = None
_instance_lock = threading.Lock()


def get_supply_forecasting_service() -> SupplyForecastingService:
    """Return the singleton SupplyForecastingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SupplyForecastingService()
    return _instance


def reset_supply_forecasting_service() -> SupplyForecastingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SupplyForecastingService()
    return _instance
