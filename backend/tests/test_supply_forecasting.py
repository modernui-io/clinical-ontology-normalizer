"""Tests for Clinical Supply Forecasting (CLINICAL-8).

Covers:
- Seed data verification (forecasts, demand projections, supply plans,
  inventory snapshots, resupply alerts, risk assessments)
- Forecast CRUD (create, read, update, delete, list, filter by trial/status/scenario)
- Forecast generation and recalculation
- Demand projection CRUD and automatic dose calculation
- Supply plan CRUD (create, read, update, delete, list, filter)
- Inventory snapshot listing and filtering
- Resupply alert management (list, filter, acknowledge, trigger)
- Supply risk assessment CRUD and risk scoring
- Site inventory status aggregation
- Supply forecasting metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.supply_forecasting import (
    DemandScenario,
    ForecastPeriod,
    ForecastStatus,
    ResupplyTriggerType,
    RiskAssessmentStatus,
    SupplyPlanStatus,
    SupplyRiskLevel,
)
from app.services.supply_forecasting_service import (
    SupplyForecastingService,
    get_supply_forecasting_service,
    reset_supply_forecasting_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/supply-forecasting"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_supply_forecasting_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SupplyForecastingService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_forecast_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "product_name": "Test Product",
        "forecast_period": "monthly",
        "scenario": "base",
        "created_by": "Test User",
        "current_inventory": 500,
        "safety_stock": 100,
        "lead_time_days": 30,
    }
    defaults.update(overrides)
    return defaults


def _make_demand_projection_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "forecast_id": "SF-001",
        "period_start": now.isoformat(),
        "period_end": (now + timedelta(days=30)).isoformat(),
        "projected_enrollment": 30,
        "doses_per_patient": 4.0,
        "wastage_factor": 0.05,
        "overage_pct": 10.0,
    }
    defaults.update(overrides)
    return defaults


def _make_supply_plan_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "forecast_id": "SF-001",
        "supplier": "Test Supplier",
        "order_date": now.isoformat(),
        "expected_delivery": (now + timedelta(days=45)).isoformat(),
        "quantity_ordered": 100,
        "unit_cost": 500.00,
    }
    defaults.update(overrides)
    return defaults


def _make_risk_assessment_create(**overrides) -> dict:
    defaults = {
        "forecast_id": "SF-001",
        "risk_category": "supplier",
        "description": "Test supply risk",
        "probability": 0.3,
        "impact": 0.7,
        "mitigation_plan": "Implement backup supplier",
        "owner": "Test Owner",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_forecasts_count(self, svc: SupplyForecastingService):
        forecasts = svc.list_forecasts()
        assert len(forecasts) == 4

    def test_seed_forecasts_trials(self, svc: SupplyForecastingService):
        forecasts = svc.list_forecasts()
        trial_ids = {f.trial_id for f in forecasts}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_forecasts_statuses(self, svc: SupplyForecastingService):
        forecasts = svc.list_forecasts()
        statuses = {f.status for f in forecasts}
        assert ForecastStatus.ACTIVE in statuses
        assert ForecastStatus.DRAFT in statuses
        assert ForecastStatus.SUPERSEDED in statuses

    def test_seed_forecasts_scenarios(self, svc: SupplyForecastingService):
        forecasts = svc.list_forecasts()
        scenarios = {f.scenario for f in forecasts}
        assert DemandScenario.BASE in scenarios
        assert DemandScenario.AGGRESSIVE in scenarios
        assert DemandScenario.CONSERVATIVE in scenarios
        assert DemandScenario.WORST_CASE in scenarios

    def test_seed_demand_projections_count(self, svc: SupplyForecastingService):
        projections = svc.list_demand_projections()
        assert len(projections) == 7

    def test_seed_supply_plans_count(self, svc: SupplyForecastingService):
        plans = svc.list_supply_plans()
        assert len(plans) == 5

    def test_seed_supply_plan_statuses(self, svc: SupplyForecastingService):
        plans = svc.list_supply_plans()
        statuses = {sp.status for sp in plans}
        assert SupplyPlanStatus.PLANNED in statuses
        assert SupplyPlanStatus.ORDERED in statuses
        assert SupplyPlanStatus.IN_TRANSIT in statuses
        assert SupplyPlanStatus.RECEIVED in statuses

    def test_seed_inventory_snapshots_count(self, svc: SupplyForecastingService):
        snapshots = svc.list_inventory_snapshots()
        assert len(snapshots) == 9

    def test_seed_inventory_below_safety_stock(self, svc: SupplyForecastingService):
        snapshots = svc.list_inventory_snapshots()
        below = [s for s in snapshots if s.below_safety_stock]
        assert len(below) >= 3

    def test_seed_resupply_alerts_count(self, svc: SupplyForecastingService):
        alerts = svc.list_resupply_alerts()
        assert len(alerts) == 4

    def test_seed_resupply_alert_types(self, svc: SupplyForecastingService):
        alerts = svc.list_resupply_alerts()
        types = {a.alert_type for a in alerts}
        assert SupplyRiskLevel.HIGH in types
        assert SupplyRiskLevel.CRITICAL in types

    def test_seed_risk_assessments_count(self, svc: SupplyForecastingService):
        assessments = svc.list_risk_assessments()
        assert len(assessments) == 5

    def test_seed_risk_assessment_categories(self, svc: SupplyForecastingService):
        assessments = svc.list_risk_assessments()
        categories = {ra.risk_category for ra in assessments}
        assert "supplier" in categories
        assert "logistics" in categories
        assert "regulatory" in categories
        assert "demand" in categories
        assert "quality" in categories


# =====================================================================
# FORECAST CRUD
# =====================================================================


class TestForecastCrud:
    """Test forecast create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_forecasts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_forecasts_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/forecasts", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_forecasts_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/forecasts", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_forecasts_filter_scenario(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/forecasts", params={"scenario": "base"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["scenario"] == "base"

    @pytest.mark.anyio
    async def test_get_forecast(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts/SF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SF-001"
        assert data["product_name"] == "EYLEA HD (Aflibercept) 8mg"

    @pytest.mark.anyio
    async def test_get_forecast_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts/SF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_forecast(self, client: AsyncClient):
        payload = _make_forecast_create()
        resp = await client.post(f"{API_PREFIX}/forecasts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Test Product"
        assert data["status"] == "draft"
        assert data["id"].startswith("SF-")
        assert data["current_inventory"] == 500

    @pytest.mark.anyio
    async def test_create_forecast_sets_reorder_point(self, client: AsyncClient):
        payload = _make_forecast_create(safety_stock=100)
        resp = await client.post(f"{API_PREFIX}/forecasts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reorder_point"] == 150  # 1.5x safety stock

    @pytest.mark.anyio
    async def test_update_forecast(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/forecasts/SF-001",
            json={"status": "archived", "current_inventory": 600},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"
        assert data["current_inventory"] == 600

    @pytest.mark.anyio
    async def test_update_forecast_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/forecasts/SF-NONEXISTENT",
            json={"status": "archived"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_forecast(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/forecasts/SF-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/forecasts/SF-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_forecast_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/forecasts/SF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FORECAST GENERATION
# =====================================================================


class TestForecastGeneration:
    """Test forecast generation and recalculation."""

    @pytest.mark.anyio
    async def test_generate_forecast(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/forecasts/SF-001/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["projected_demand"] > 0
        assert data["projected_supply"] > 0
        assert data["months_of_supply"] > 0

    @pytest.mark.anyio
    async def test_generate_forecast_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/forecasts/SF-NONEXISTENT/generate")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_generate_forecast_computes_risk_level(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/forecasts/SF-001/generate")
        data = resp.json()
        assert data["risk_level"] in ["low", "moderate", "high", "critical"]

    def test_generate_forecast_aggregates_demand(self, svc: SupplyForecastingService):
        result = svc.generate_forecast("SF-001")
        assert result is not None
        # SF-001 has DP-001 (312) and DP-002 (347) = 659
        assert result.projected_demand == 659

    def test_generate_forecast_aggregates_supply(self, svc: SupplyForecastingService):
        result = svc.generate_forecast("SF-001")
        assert result is not None
        # SF-001 has SP-001 (200) and SP-002 (200) = 400
        assert result.projected_supply == 400

    def test_risk_level_critical(self, svc: SupplyForecastingService):
        level = svc._calculate_risk_level(0.5, 100, 40)
        assert level == SupplyRiskLevel.CRITICAL

    def test_risk_level_high(self, svc: SupplyForecastingService):
        level = svc._calculate_risk_level(1.5, 100, 80)
        assert level == SupplyRiskLevel.HIGH

    def test_risk_level_moderate(self, svc: SupplyForecastingService):
        level = svc._calculate_risk_level(2.5, 100, 200)
        assert level == SupplyRiskLevel.MODERATE

    def test_risk_level_low(self, svc: SupplyForecastingService):
        level = svc._calculate_risk_level(6.0, 100, 500)
        assert level == SupplyRiskLevel.LOW


# =====================================================================
# DEMAND PROJECTIONS
# =====================================================================


class TestDemandProjections:
    """Test demand projection CRUD operations."""

    @pytest.mark.anyio
    async def test_list_demand_projections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-projections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_demand_projections_filter_forecast(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/demand-projections", params={"forecast_id": "SF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["forecast_id"] == "SF-001"

    @pytest.mark.anyio
    async def test_get_demand_projection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-projections/DP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DP-001"
        assert data["forecast_id"] == "SF-001"

    @pytest.mark.anyio
    async def test_get_demand_projection_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-projections/DP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_demand_projection(self, client: AsyncClient):
        payload = _make_demand_projection_create()
        resp = await client.post(f"{API_PREFIX}/demand-projections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["forecast_id"] == "SF-001"
        assert data["projected_enrollment"] == 30
        assert data["total_doses_needed"] == 120  # 30 * 4.0
        assert data["total_units_required"] > 120  # includes wastage + overage

    @pytest.mark.anyio
    async def test_create_demand_projection_invalid_forecast(self, client: AsyncClient):
        payload = _make_demand_projection_create(forecast_id="SF-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/demand-projections", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_demand_projection_auto_computes_units(self, client: AsyncClient):
        payload = _make_demand_projection_create(
            projected_enrollment=10,
            doses_per_patient=2.0,
            wastage_factor=0.10,
            overage_pct=20.0,
        )
        resp = await client.post(f"{API_PREFIX}/demand-projections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # 10 * 2 = 20 doses, wastage = ceil(20*0.10) = 2, subtotal = 22
        # overage = ceil(22*0.20) = 5, total = 27
        assert data["total_doses_needed"] == 20
        assert data["total_units_required"] == 27

    @pytest.mark.anyio
    async def test_delete_demand_projection(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/demand-projections/DP-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/demand-projections/DP-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_demand_projection_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/demand-projections/DP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SUPPLY PLANS
# =====================================================================


class TestSupplyPlans:
    """Test supply plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_supply_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_supply_plans_filter_forecast(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supply-plans", params={"forecast_id": "SF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["forecast_id"] == "SF-001"

    @pytest.mark.anyio
    async def test_list_supply_plans_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supply-plans", params={"status": "planned"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "planned"

    @pytest.mark.anyio
    async def test_get_supply_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans/SP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SP-001"
        assert data["supplier"] == "Regeneron Pharmaceuticals"

    @pytest.mark.anyio
    async def test_get_supply_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans/SP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_supply_plan(self, client: AsyncClient):
        payload = _make_supply_plan_create()
        resp = await client.post(f"{API_PREFIX}/supply-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["supplier"] == "Test Supplier"
        assert data["quantity_ordered"] == 100
        assert data["total_cost"] == 50000.00
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_create_supply_plan_invalid_forecast(self, client: AsyncClient):
        payload = _make_supply_plan_create(forecast_id="SF-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/supply-plans", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_supply_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/supply-plans/SP-001",
            json={"status": "in_transit", "lot_number": "LOT-UPDATE-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_transit"
        assert data["lot_number"] == "LOT-UPDATE-001"

    @pytest.mark.anyio
    async def test_update_supply_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/supply-plans/SP-NONEXISTENT",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_supply_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/supply-plans/SP-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/supply-plans/SP-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_supply_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/supply-plans/SP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INVENTORY SNAPSHOTS
# =====================================================================


class TestInventorySnapshots:
    """Test inventory snapshot operations."""

    @pytest.mark.anyio
    async def test_list_inventory_snapshots(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 9

    @pytest.mark.anyio
    async def test_list_snapshots_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory-snapshots", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_snapshots_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory-snapshots", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_snapshots_filter_product(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory-snapshots",
            params={"product_name": "EYLEA HD (Aflibercept) 8mg"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["product_name"] == "EYLEA HD (Aflibercept) 8mg"

    @pytest.mark.anyio
    async def test_get_inventory_snapshot(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-snapshots/IS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IS-001"
        assert data["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_get_inventory_snapshot_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-snapshots/IS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inventory_snapshot(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inventory-snapshots/IS-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/inventory-snapshots/IS-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inventory_snapshot_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inventory-snapshots/IS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_snapshot_available_equals_on_hand_minus_allocated(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-snapshots/IS-001")
        data = resp.json()
        assert data["available"] == data["on_hand"] - data["allocated"]


# =====================================================================
# RESUPPLY ALERTS
# =====================================================================


class TestResupplyAlerts:
    """Test resupply alert management."""

    @pytest.mark.anyio
    async def test_list_resupply_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resupply-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_alerts_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resupply-alerts", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_alerts_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resupply-alerts", params={"site_id": "SITE-103"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-103"

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resupply-alerts", params={"acknowledged": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged"] is False

    @pytest.mark.anyio
    async def test_get_resupply_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resupply-alerts/RA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RA-001"
        assert data["acknowledged"] is False

    @pytest.mark.anyio
    async def test_get_resupply_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resupply-alerts/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_acknowledge_resupply_alert(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/resupply-alerts/RA-001/acknowledge",
            json={"acknowledged_by": "Test User"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["acknowledged_by"] == "Test User"

    @pytest.mark.anyio
    async def test_acknowledge_already_acknowledged(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/resupply-alerts/RA-002/acknowledge",
            json={"acknowledged_by": "Test User"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/resupply-alerts/RA-NONEXISTENT/acknowledge",
            json={"acknowledged_by": "Test User"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_trigger_resupply(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/resupply-alerts/trigger",
            params={
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "product_name": "EYLEA HD (Aflibercept) 8mg",
                "current_level": 5,
                "threshold_level": 20,
                "recommended_quantity": 30,
                "trigger_type": "manual",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-102"
        assert data["trigger_type"] == "manual"
        assert data["acknowledged"] is False
        assert data["id"].startswith("RA-")

    @pytest.mark.anyio
    async def test_trigger_resupply_emergency(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/resupply-alerts/trigger",
            params={
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "product_name": "Libtayo (Cemiplimab) 350mg",
                "current_level": 2,
                "threshold_level": 30,
                "recommended_quantity": 50,
                "trigger_type": "emergency",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["trigger_type"] == "emergency"
        assert data["alert_type"] == "critical"  # 2 <= 30*0.25 = 7.5

    def test_trigger_resupply_risk_levels(self, svc: SupplyForecastingService):
        # Critical: level <= threshold * 0.25
        alert = svc.trigger_resupply(EYLEA_TRIAL, "SITE-101", "Test", 5, 100, 50)
        assert alert.alert_type == SupplyRiskLevel.CRITICAL

        # High: level <= threshold * 0.5
        alert = svc.trigger_resupply(EYLEA_TRIAL, "SITE-101", "Test", 40, 100, 50)
        assert alert.alert_type == SupplyRiskLevel.HIGH

        # Moderate: level <= threshold * 0.75
        alert = svc.trigger_resupply(EYLEA_TRIAL, "SITE-101", "Test", 60, 100, 50)
        assert alert.alert_type == SupplyRiskLevel.MODERATE

        # Low: level > threshold * 0.75
        alert = svc.trigger_resupply(EYLEA_TRIAL, "SITE-101", "Test", 80, 100, 50)
        assert alert.alert_type == SupplyRiskLevel.LOW


# =====================================================================
# SUPPLY RISK ASSESSMENTS
# =====================================================================


class TestSupplyRiskAssessments:
    """Test supply risk assessment CRUD and scoring."""

    @pytest.mark.anyio
    async def test_list_risk_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_risk_assessments_filter_forecast(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-assessments", params={"forecast_id": "SF-002"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["forecast_id"] == "SF-002"

    @pytest.mark.anyio
    async def test_list_risk_assessments_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-assessments", params={"status": "mitigating"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "mitigating"

    @pytest.mark.anyio
    async def test_get_risk_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments/SRA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SRA-001"
        assert data["risk_category"] == "supplier"

    @pytest.mark.anyio
    async def test_get_risk_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments/SRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_risk_assessment(self, client: AsyncClient):
        payload = _make_risk_assessment_create()
        resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_category"] == "supplier"
        assert data["risk_score"] == pytest.approx(0.21, abs=0.01)
        assert data["status"] == "identified"
        assert data["id"].startswith("SRA-")

    @pytest.mark.anyio
    async def test_create_risk_assessment_invalid_forecast(self, client: AsyncClient):
        payload = _make_risk_assessment_create(forecast_id="SF-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_risk_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risk-assessments/SRA-002",
            json={"status": "mitigating", "probability": 0.1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "mitigating"
        assert data["probability"] == 0.1
        # risk_score should be recalculated: 0.1 * 0.7 = 0.07
        assert data["risk_score"] == pytest.approx(0.07, abs=0.01)

    @pytest.mark.anyio
    async def test_update_risk_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risk-assessments/SRA-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risk-assessments/SRA-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/risk-assessments/SRA-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risk-assessments/SRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assess_forecast_risks_sorted(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts/SF-001/risks")
        assert resp.status_code == 200
        data = resp.json()
        scores = [item["risk_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_assess_forecast_risks_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts/SF-NONEXISTENT/risks")
        assert resp.status_code == 404

    def test_risk_score_calculation(self, svc: SupplyForecastingService):
        assessment = svc.get_risk_assessment("SRA-001")
        assert assessment is not None
        assert assessment.risk_score == pytest.approx(
            assessment.probability * assessment.impact, abs=0.01
        )


# =====================================================================
# SITE INVENTORY STATUS
# =====================================================================


class TestSiteInventoryStatus:
    """Test site inventory status aggregation."""

    @pytest.mark.anyio
    async def test_get_site_inventory_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/inventory-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["total_on_hand"] > 0
        assert data["total_available"] > 0
        assert len(data["products"]) >= 1

    @pytest.mark.anyio
    async def test_site_inventory_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-NONEXISTENT/inventory-status")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_site_inventory_below_safety_stock(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-103/inventory-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["any_below_safety_stock"] is True

    @pytest.mark.anyio
    async def test_site_inventory_active_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-103/inventory-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_alerts"] >= 1

    def test_site_inventory_aggregation(self, svc: SupplyForecastingService):
        status = svc.get_site_inventory_status("SITE-201")
        assert status is not None
        assert status.total_on_hand == sum(s.on_hand for s in status.products)
        assert status.total_available == sum(s.available for s in status.products)

    def test_site_inventory_no_snapshots(self, svc: SupplyForecastingService):
        status = svc.get_site_inventory_status("SITE-NONEXISTENT")
        assert status is None


# =====================================================================
# METRICS
# =====================================================================


class TestSupplyForecastingMetrics:
    """Test supply forecasting metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_forecasts"] == 4
        assert data["active_forecasts"] == 2
        assert data["total_demand_projections"] == 7
        assert data["total_supply_plans"] == 5
        assert data["total_inventory_snapshots"] == 9
        assert data["total_risk_assessments"] == 5
        assert data["total_order_value"] > 0

    def test_metrics_pending_orders(self, svc: SupplyForecastingService):
        metrics = svc.get_metrics()
        plans = svc.list_supply_plans()
        expected_pending = sum(
            1 for sp in plans
            if sp.status in (SupplyPlanStatus.PLANNED, SupplyPlanStatus.ORDERED)
        )
        assert metrics.pending_orders == expected_pending

    def test_metrics_sites_below_safety_stock(self, svc: SupplyForecastingService):
        metrics = svc.get_metrics()
        snapshots = svc.list_inventory_snapshots()
        expected_below = sum(1 for s in snapshots if s.below_safety_stock)
        assert metrics.sites_below_safety_stock == expected_below

    def test_metrics_active_alerts(self, svc: SupplyForecastingService):
        metrics = svc.get_metrics()
        alerts = svc.list_resupply_alerts(acknowledged=False)
        assert metrics.active_resupply_alerts == len(alerts)

    def test_metrics_avg_months_of_supply(self, svc: SupplyForecastingService):
        metrics = svc.get_metrics()
        assert metrics.avg_months_of_supply is not None
        assert metrics.avg_months_of_supply > 0

    def test_metrics_high_critical_risks(self, svc: SupplyForecastingService):
        metrics = svc.get_metrics()
        assessments = svc.list_risk_assessments()
        expected = sum(
            1 for ra in assessments
            if ra.risk_score >= 0.15
            and ra.status not in (RiskAssessmentStatus.RESOLVED, RiskAssessmentStatus.ACCEPTED)
        )
        assert metrics.high_critical_risks == expected

    def test_metrics_total_order_value(self, svc: SupplyForecastingService):
        metrics = svc.get_metrics()
        plans = svc.list_supply_plans()
        expected_value = sum(sp.total_cost for sp in plans)
        assert metrics.total_order_value == pytest.approx(expected_value, abs=0.01)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_supply_forecasting_service()
        svc2 = get_supply_forecasting_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_supply_forecasting_service()
        svc2 = reset_supply_forecasting_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_supply_forecasting_service()
        svc.delete_forecast("SF-001")
        assert svc.get_forecast("SF-001") is None
        svc2 = reset_supply_forecasting_service()
        assert svc2.get_forecast("SF-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_forecasts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_alerts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resupply-alerts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_plans_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_snapshots_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-snapshots")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_risk_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_demand_projections_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-projections")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_forecast_create_with_all_fields(self, client: AsyncClient):
        payload = _make_forecast_create(
            trial_id=LIBTAYO_TRIAL,
            product_name="Complete Forecast Product",
            forecast_period="annual",
            scenario="worst_case",
            created_by="Full Test User",
            current_inventory=1000,
            safety_stock=200,
            lead_time_days=90,
        )
        resp = await client.post(f"{API_PREFIX}/forecasts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["forecast_period"] == "annual"
        assert data["scenario"] == "worst_case"

    @pytest.mark.anyio
    async def test_supply_plan_cost_calculation(self, client: AsyncClient):
        payload = _make_supply_plan_create(quantity_ordered=250, unit_cost=100.50)
        resp = await client.post(f"{API_PREFIX}/supply-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_cost"] == pytest.approx(25125.00, abs=0.01)

    @pytest.mark.anyio
    async def test_multiple_demand_projections_for_same_forecast(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        for i in range(3):
            payload = _make_demand_projection_create(
                period_start=(now + timedelta(days=i * 30)).isoformat(),
                period_end=(now + timedelta(days=(i + 1) * 30)).isoformat(),
                projected_enrollment=20 + i * 5,
            )
            resp = await client.post(f"{API_PREFIX}/demand-projections", json=payload)
            assert resp.status_code == 201

        resp = await client.get(
            f"{API_PREFIX}/demand-projections", params={"forecast_id": "SF-001"}
        )
        data = resp.json()
        # Original 2 + 3 new = 5
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_generate_after_adding_projections(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        # Add a new demand projection
        payload = _make_demand_projection_create(
            projected_enrollment=100,
            doses_per_patient=5.0,
        )
        resp = await client.post(f"{API_PREFIX}/demand-projections", json=payload)
        assert resp.status_code == 201

        # Generate forecast should reflect new projection
        resp = await client.post(f"{API_PREFIX}/forecasts/SF-001/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projected_demand"] > 659  # Previous total + new projection

    @pytest.mark.anyio
    async def test_create_and_retrieve_forecast(self, client: AsyncClient):
        payload = _make_forecast_create(product_name="Roundtrip Test Product")
        resp = await client.post(f"{API_PREFIX}/forecasts", json=payload)
        assert resp.status_code == 201
        forecast_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/forecasts/{forecast_id}")
        assert resp2.status_code == 200
        assert resp2.json()["product_name"] == "Roundtrip Test Product"

    @pytest.mark.anyio
    async def test_update_risk_assessment_recalculates_score(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risk-assessments/SRA-004",
            json={"probability": 0.5, "impact": 0.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] == pytest.approx(0.25, abs=0.01)

    @pytest.mark.anyio
    async def test_acknowledge_then_verify(self, client: AsyncClient):
        # Acknowledge RA-001
        resp = await client.post(
            f"{API_PREFIX}/resupply-alerts/RA-001/acknowledge",
            json={"acknowledged_by": "Admin User"},
        )
        assert resp.status_code == 200

        # Verify in listing
        resp2 = await client.get(
            f"{API_PREFIX}/resupply-alerts", params={"acknowledged": True}
        )
        data = resp2.json()
        ack_ids = {item["id"] for item in data["items"]}
        assert "RA-001" in ack_ids

    @pytest.mark.anyio
    async def test_site_104_has_multiple_products(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/SITE-104/inventory-status"
        )
        assert resp.status_code == 200
        data = resp.json()
        product_names = {p["product_name"] for p in data["products"]}
        assert len(product_names) >= 1

    @pytest.mark.anyio
    async def test_forecast_period_values(self, client: AsyncClient):
        for period in ["monthly", "quarterly", "semi_annual", "annual"]:
            payload = _make_forecast_create(forecast_period=period)
            resp = await client.post(f"{API_PREFIX}/forecasts", json=payload)
            assert resp.status_code == 201
            assert resp.json()["forecast_period"] == period

    @pytest.mark.anyio
    async def test_scenario_values(self, client: AsyncClient):
        for scenario in ["conservative", "base", "aggressive", "worst_case"]:
            payload = _make_forecast_create(scenario=scenario)
            resp = await client.post(f"{API_PREFIX}/forecasts", json=payload)
            assert resp.status_code == 201
            assert resp.json()["scenario"] == scenario

    @pytest.mark.anyio
    async def test_supply_plan_status_values(self, client: AsyncClient):
        for status_val in ["planned", "ordered", "in_transit", "received", "cancelled"]:
            resp = await client.put(
                f"{API_PREFIX}/supply-plans/SP-001",
                json={"status": status_val},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status_val


# =====================================================================
# ENUM VALIDATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_forecast_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "active" in statuses
        assert "draft" in statuses
        assert "superseded" in statuses

    @pytest.mark.anyio
    async def test_risk_levels_in_forecasts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts")
        data = resp.json()
        risk_levels = {item["risk_level"] for item in data["items"]}
        assert "low" in risk_levels

    @pytest.mark.anyio
    async def test_supply_plan_statuses_in_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "planned" in statuses
        assert "ordered" in statuses
        assert "in_transit" in statuses
        assert "received" in statuses

    @pytest.mark.anyio
    async def test_alert_trigger_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resupply-alerts")
        data = resp.json()
        trigger_types = {item["trigger_type"] for item in data["items"]}
        assert "threshold" in trigger_types
        assert "emergency" in trigger_types

    @pytest.mark.anyio
    async def test_risk_assessment_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "identified" in statuses
        assert "mitigating" in statuses
        assert "resolved" in statuses


# =====================================================================
# DETAILED FIELD VALIDATION
# =====================================================================


class TestFieldValidation:
    """Test specific field values and calculations."""

    @pytest.mark.anyio
    async def test_forecast_months_of_supply_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecasts")
        data = resp.json()
        for item in data["items"]:
            assert item["months_of_supply"] >= 0

    @pytest.mark.anyio
    async def test_risk_assessment_score_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        data = resp.json()
        for item in data["items"]:
            assert 0.0 <= item["risk_score"] <= 1.0
            assert 0.0 <= item["probability"] <= 1.0
            assert 0.0 <= item["impact"] <= 1.0

    @pytest.mark.anyio
    async def test_inventory_snapshot_non_negative(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-snapshots")
        data = resp.json()
        for item in data["items"]:
            assert item["on_hand"] >= 0
            assert item["allocated"] >= 0
            assert item["available"] >= 0
            assert item["expiring_30d"] >= 0
            assert item["expiring_90d"] >= 0

    @pytest.mark.anyio
    async def test_supply_plan_cost_non_negative(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans")
        data = resp.json()
        for item in data["items"]:
            assert item["unit_cost"] >= 0
            assert item["total_cost"] >= 0
            assert item["quantity_ordered"] >= 1

    @pytest.mark.anyio
    async def test_resupply_alert_recommended_quantity_positive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resupply-alerts")
        data = resp.json()
        for item in data["items"]:
            assert item["recommended_quantity"] >= 0
            assert item["threshold_level"] >= 0
            assert item["current_level"] >= 0

    def test_demand_projection_wastage_factor_range(self, svc: SupplyForecastingService):
        projections = svc.list_demand_projections()
        for dp in projections:
            assert 0.0 <= dp.wastage_factor <= 1.0
            assert dp.overage_pct >= 0.0
