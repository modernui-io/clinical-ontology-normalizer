"""Tests for Clinical Supply Forecasting (SUPPLY-FCST).

Covers:
- Seed data verification (demand forecasts, supply plans, inventory projections,
  expiry risks, depot allocations)
- Demand forecast CRUD (create, read, update, delete, list, filter by trial/type/status)
- Supply plan CRUD (create, read, update, delete, list, filter by trial/status/risk)
- Inventory projection CRUD (create, read, update, delete, list, filter by trial/site/risk)
- Expiry risk CRUD (create, read, update, delete, list, filter by trial/risk/resolved)
- Depot allocation CRUD (create, read, update, delete, list, filter by trial/region/active)
- Metrics computation
- Not-found error handling (404s)
- Service singleton pattern
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_supply_forecast import (
    AllocationStrategy,
    ForecastStatus,
    ForecastType,
    SupplyRisk,
)
from app.services.clinical_supply_forecast_service import (
    ClinicalSupplyForecastService,
    get_clinical_supply_forecast_service,
    reset_clinical_supply_forecast_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-supply-forecast"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_supply_forecast_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalSupplyForecastService:
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


def _make_demand_forecast_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "drug_name": "Test Drug 100mg",
        "forecast_type": "enrollment_based",
        "created_by": "Test User",
        "horizon_months": 12,
        "enrollment_assumption": 200,
    }
    defaults.update(overrides)
    return defaults


def _make_supply_plan_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "drug_name": "Test Drug 200mg",
        "created_by": "Supply Planner",
        "forecast_id": None,
        "planned_production_units": 10000,
    }
    defaults.update(overrides)
    return defaults


def _make_inventory_projection_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "drug_name": "Test Drug 350mg",
        "current_inventory": 500,
        "site_id": "SITE-201",
        "reorder_point": 200,
    }
    defaults.update(overrides)
    return defaults


def _make_expiry_risk_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "drug_name": "Test Drug 100mg",
        "batch_number": "TEST-B2026-001",
        "expiry_date": (now + timedelta(days=45)).isoformat(),
        "quantity_at_risk": 100,
        "flagged_by": "Test Pharmacist",
        "site_id": "SITE-201",
    }
    defaults.update(overrides)
    return defaults


def _make_depot_allocation_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "drug_name": "Test Drug 200mg",
        "depot_name": "Test Depot",
        "region": "North America",
        "allocation_strategy": "demand_driven",
        "managed_by": "Test Manager",
        "allocated_units": 5000,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_demand_forecasts_count(self, svc: ClinicalSupplyForecastService):
        items = svc.list_demand_forecasts()
        assert len(items) == 12

    def test_seed_supply_plans_count(self, svc: ClinicalSupplyForecastService):
        items = svc.list_supply_plans()
        assert len(items) == 10

    def test_seed_inventory_projections_count(self, svc: ClinicalSupplyForecastService):
        items = svc.list_inventory_projections()
        assert len(items) == 12

    def test_seed_expiry_risks_count(self, svc: ClinicalSupplyForecastService):
        items = svc.list_expiry_risks()
        assert len(items) == 10

    def test_seed_depot_allocations_count(self, svc: ClinicalSupplyForecastService):
        items = svc.list_depot_allocations()
        assert len(items) == 10

    def test_seed_forecasts_cover_all_types(self, svc: ClinicalSupplyForecastService):
        items = svc.list_demand_forecasts()
        types = {f.forecast_type for f in items}
        assert ForecastType.ENROLLMENT_BASED in types
        assert ForecastType.CONSUMPTION_BASED in types
        assert ForecastType.HYBRID in types
        assert ForecastType.SCENARIO in types
        assert ForecastType.MONTE_CARLO in types

    def test_seed_forecasts_cover_all_statuses(self, svc: ClinicalSupplyForecastService):
        items = svc.list_demand_forecasts()
        statuses = {f.status for f in items}
        assert ForecastStatus.DRAFT in statuses
        assert ForecastStatus.UNDER_REVIEW in statuses
        assert ForecastStatus.APPROVED in statuses
        assert ForecastStatus.SUPERSEDED in statuses
        assert ForecastStatus.ARCHIVED in statuses

    def test_seed_plans_cover_risk_levels(self, svc: ClinicalSupplyForecastService):
        items = svc.list_supply_plans()
        risks = {p.risk_level for p in items}
        assert SupplyRisk.LOW in risks
        assert SupplyRisk.MODERATE in risks
        assert SupplyRisk.HIGH in risks
        assert SupplyRisk.CRITICAL in risks

    def test_seed_projections_cover_stockout_risks(self, svc: ClinicalSupplyForecastService):
        items = svc.list_inventory_projections()
        risks = {p.stockout_risk for p in items}
        assert SupplyRisk.LOW in risks
        assert SupplyRisk.MODERATE in risks
        assert SupplyRisk.HIGH in risks
        assert SupplyRisk.CRITICAL in risks

    def test_seed_depot_strategies(self, svc: ClinicalSupplyForecastService):
        items = svc.list_depot_allocations()
        strategies = {d.allocation_strategy for d in items}
        assert AllocationStrategy.PROPORTIONAL in strategies
        assert AllocationStrategy.PRIORITY_BASED in strategies
        assert AllocationStrategy.DEMAND_DRIVEN in strategies
        assert AllocationStrategy.FIXED in strategies

    def test_seed_data_uses_trial_ids(self, svc: ClinicalSupplyForecastService):
        items = svc.list_demand_forecasts()
        trial_ids = {f.trial_id for f in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids


# =====================================================================
# DEMAND FORECAST CRUD
# =====================================================================


class TestDemandForecastCrud:
    """Test demand forecast create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_demand_forecasts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-forecasts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_demand_forecasts_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/demand-forecasts", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_demand_forecasts_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/demand-forecasts", params={"forecast_type": "monte_carlo"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["forecast_type"] == "monte_carlo"

    @pytest.mark.anyio
    async def test_list_demand_forecasts_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/demand-forecasts", params={"status": "approved"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_get_demand_forecast(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-forecasts/DF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DF-001"
        assert data["drug_name"] == "Aflibercept 2mg"

    @pytest.mark.anyio
    async def test_get_demand_forecast_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/demand-forecasts/DF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_demand_forecast(self, client: AsyncClient):
        payload = _make_demand_forecast_create()
        resp = await client.post(f"{API_PREFIX}/demand-forecasts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Test Drug 100mg"
        assert data["status"] == "draft"
        assert data["id"].startswith("DF-")

    @pytest.mark.anyio
    async def test_update_demand_forecast(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/demand-forecasts/DF-002",
            json={"status": "approved", "approved_by": "Dr. Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Test"

    @pytest.mark.anyio
    async def test_update_demand_forecast_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/demand-forecasts/DF-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_demand_forecast(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/demand-forecasts/DF-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/demand-forecasts/DF-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_demand_forecast_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/demand-forecasts/DF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SUPPLY PLAN CRUD
# =====================================================================


class TestSupplyPlanCrud:
    """Test supply plan create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_supply_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_supply_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supply-plans", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_supply_plans_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supply-plans", params={"status": "approved"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_supply_plans_filter_risk(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supply-plans", params={"risk_level": "high"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_level"] == "high"

    @pytest.mark.anyio
    async def test_get_supply_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supply-plans/SP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SP-001"
        assert data["drug_name"] == "Aflibercept 2mg"

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
        assert data["drug_name"] == "Test Drug 200mg"
        assert data["status"] == "draft"
        assert data["id"].startswith("SP-")

    @pytest.mark.anyio
    async def test_update_supply_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/supply-plans/SP-006",
            json={"status": "approved", "approved_by": "Dr. Approver", "risk_level": "low"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Approver"
        assert data["risk_level"] == "low"

    @pytest.mark.anyio
    async def test_update_supply_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/supply-plans/SP-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_supply_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/supply-plans/SP-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/supply-plans/SP-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_supply_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/supply-plans/SP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INVENTORY PROJECTION CRUD
# =====================================================================


class TestInventoryProjectionCrud:
    """Test inventory projection create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_inventory_projections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-projections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_inventory_projections_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory-projections", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_inventory_projections_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory-projections", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_inventory_projections_filter_stockout_risk(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory-projections", params={"stockout_risk": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["stockout_risk"] == "critical"

    @pytest.mark.anyio
    async def test_get_inventory_projection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-projections/IP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IP-001"
        assert data["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_get_inventory_projection_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-projections/IP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_inventory_projection(self, client: AsyncClient):
        payload = _make_inventory_projection_create()
        resp = await client.post(f"{API_PREFIX}/inventory-projections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Test Drug 350mg"
        assert data["current_inventory"] == 500
        assert data["id"].startswith("IP-")

    @pytest.mark.anyio
    async def test_update_inventory_projection(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inventory-projections/IP-005",
            json={"stockout_risk": "high", "current_inventory": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stockout_risk"] == "high"
        assert data["current_inventory"] == 100

    @pytest.mark.anyio
    async def test_update_inventory_projection_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inventory-projections/IP-NONEXISTENT",
            json={"current_inventory": 100},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inventory_projection(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inventory-projections/IP-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/inventory-projections/IP-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inventory_projection_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inventory-projections/IP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EXPIRY RISK CRUD
# =====================================================================


class TestExpiryRiskCrud:
    """Test expiry risk create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_expiry_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiry-risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_expiry_risks_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiry-risks", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_expiry_risks_filter_risk_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiry-risks", params={"risk_level": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_level"] == "critical"

    @pytest.mark.anyio
    async def test_list_expiry_risks_filter_resolved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiry-risks", params={"resolved": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolved"] is False

    @pytest.mark.anyio
    async def test_list_expiry_risks_filter_resolved_true(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiry-risks", params={"resolved": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolved"] is True

    @pytest.mark.anyio
    async def test_get_expiry_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiry-risks/ER-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ER-001"
        assert data["batch_number"] == "EYLEA-B2025-001"

    @pytest.mark.anyio
    async def test_get_expiry_risk_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiry-risks/ER-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_expiry_risk(self, client: AsyncClient):
        payload = _make_expiry_risk_create()
        resp = await client.post(f"{API_PREFIX}/expiry-risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["batch_number"] == "TEST-B2026-001"
        assert data["resolved"] is False
        assert data["id"].startswith("ER-")

    @pytest.mark.anyio
    async def test_update_expiry_risk(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/expiry-risks/ER-003",
            json={
                "mitigation_action": "Redistribute to SITE-105",
                "risk_level": "high",
                "can_redistribute": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mitigation_action"] == "Redistribute to SITE-105"
        assert data["risk_level"] == "high"
        assert data["can_redistribute"] is True

    @pytest.mark.anyio
    async def test_update_expiry_risk_resolve(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/expiry-risks/ER-001",
            json={"resolved": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True

    @pytest.mark.anyio
    async def test_update_expiry_risk_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/expiry-risks/ER-NONEXISTENT",
            json={"resolved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_expiry_risk(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/expiry-risks/ER-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/expiry-risks/ER-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_expiry_risk_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/expiry-risks/ER-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DEPOT ALLOCATION CRUD
# =====================================================================


class TestDepotAllocationCrud:
    """Test depot allocation create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_depot_allocations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/depot-allocations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_depot_allocations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/depot-allocations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_depot_allocations_filter_region(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/depot-allocations", params={"region": "Europe"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["region"] == "Europe"

    @pytest.mark.anyio
    async def test_list_depot_allocations_filter_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/depot-allocations", params={"is_active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is True

    @pytest.mark.anyio
    async def test_list_depot_allocations_filter_inactive(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/depot-allocations", params={"is_active": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is False

    @pytest.mark.anyio
    async def test_get_depot_allocation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/depot-allocations/DA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DA-001"
        assert data["depot_name"] == "US Northeast Depot"

    @pytest.mark.anyio
    async def test_get_depot_allocation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/depot-allocations/DA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_depot_allocation(self, client: AsyncClient):
        payload = _make_depot_allocation_create()
        resp = await client.post(f"{API_PREFIX}/depot-allocations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["depot_name"] == "Test Depot"
        assert data["is_active"] is True
        assert data["remaining_units"] == 5000
        assert data["id"].startswith("DA-")

    @pytest.mark.anyio
    async def test_update_depot_allocation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/depot-allocations/DA-001",
            json={"shipped_units": 6000, "utilization_pct": 75.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["shipped_units"] == 6000
        assert data["utilization_pct"] == 75.0

    @pytest.mark.anyio
    async def test_update_depot_allocation_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/depot-allocations/DA-001",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    @pytest.mark.anyio
    async def test_update_depot_allocation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/depot-allocations/DA-NONEXISTENT",
            json={"is_active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_depot_allocation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/depot-allocations/DA-008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/depot-allocations/DA-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_depot_allocation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/depot-allocations/DA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test clinical supply forecast metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_forecasts"] == 12
        assert data["total_supply_plans"] == 10
        assert data["total_projections"] == 12
        assert data["total_expiry_risks"] == 10
        assert data["total_depots"] == 10

    @pytest.mark.anyio
    async def test_metrics_forecasts_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["forecasts_by_type"]
        total = sum(by_type.values())
        assert total == data["total_forecasts"]

    @pytest.mark.anyio
    async def test_metrics_forecasts_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["forecasts_by_status"]
        total = sum(by_status.values())
        assert total == data["total_forecasts"]

    @pytest.mark.anyio
    async def test_metrics_plans_by_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_risk = data["plans_by_risk"]
        total = sum(by_risk.values())
        assert total == data["total_supply_plans"]

    def test_metrics_sites_at_stockout_risk(self, svc: ClinicalSupplyForecastService):
        metrics = svc.get_metrics()
        # Count projections with HIGH or CRITICAL stockout_risk
        high_or_critical = sum(
            1 for p in svc.list_inventory_projections()
            if p.stockout_risk in (SupplyRisk.HIGH, SupplyRisk.CRITICAL)
        )
        assert metrics.sites_at_stockout_risk == high_or_critical

    def test_metrics_unresolved_expiry_risks(self, svc: ClinicalSupplyForecastService):
        metrics = svc.get_metrics()
        unresolved = sum(
            1 for e in svc.list_expiry_risks() if not e.resolved
        )
        assert metrics.unresolved_expiry_risks == unresolved

    def test_metrics_financial_exposure(self, svc: ClinicalSupplyForecastService):
        metrics = svc.get_metrics()
        total_unresolved = sum(
            e.financial_impact for e in svc.list_expiry_risks() if not e.resolved
        )
        assert metrics.total_financial_exposure == round(total_unresolved, 2)

    def test_metrics_active_depots(self, svc: ClinicalSupplyForecastService):
        metrics = svc.get_metrics()
        active = sum(1 for d in svc.list_depot_allocations() if d.is_active)
        assert metrics.active_depots == active

    def test_metrics_avg_depot_utilization(self, svc: ClinicalSupplyForecastService):
        metrics = svc.get_metrics()
        assert metrics.avg_depot_utilization > 0
        assert metrics.avg_depot_utilization <= 100


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_supply_forecast_service()
        svc2 = get_clinical_supply_forecast_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_supply_forecast_service()
        svc2 = reset_clinical_supply_forecast_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_supply_forecast_service()
        svc.delete_demand_forecast("DF-001")
        assert svc.get_demand_forecast("DF-001") is None
        svc2 = reset_clinical_supply_forecast_service()
        assert svc2.get_demand_forecast("DF-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_list_all_entities_no_filters(self, client: AsyncClient):
        for endpoint in [
            "demand-forecasts",
            "supply-plans",
            "inventory-projections",
            "expiry-risks",
            "depot-allocations",
        ]:
            resp = await client.get(f"{API_PREFIX}/{endpoint}")
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_with_nonmatching_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/demand-forecasts",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_create_and_immediately_retrieve(self, client: AsyncClient):
        payload = _make_demand_forecast_create()
        create_resp = await client.post(f"{API_PREFIX}/demand-forecasts", json=payload)
        assert create_resp.status_code == 201
        new_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/demand-forecasts/{new_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == new_id

    @pytest.mark.anyio
    async def test_update_partial_fields(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/demand-forecasts/DF-004",
            json={"notes": "Updated notes only"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes only"
        # Other fields unchanged
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_delete_then_delete_again(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/supply-plans/SP-010")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/supply-plans/SP-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_inventory_projections_sorted_by_weeks_of_supply(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory-projections")
        data = resp.json()
        weeks = [item["weeks_of_supply"] for item in data["items"]]
        assert weeks == sorted(weeks)

    @pytest.mark.anyio
    async def test_expiry_risks_sorted_by_days_to_expiry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiry-risks")
        data = resp.json()
        days = [item["days_to_expiry"] for item in data["items"]]
        assert days == sorted(days)

    @pytest.mark.anyio
    async def test_depot_allocations_sorted_by_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/depot-allocations")
        data = resp.json()
        names = [item["depot_name"] for item in data["items"]]
        assert names == sorted(names)

    @pytest.mark.anyio
    async def test_create_expiry_risk_calculates_days(self, client: AsyncClient):
        payload = _make_expiry_risk_create()
        resp = await client.post(f"{API_PREFIX}/expiry-risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # Should have calculated days_to_expiry > 0 for a future date
        assert data["days_to_expiry"] > 0

    @pytest.mark.anyio
    async def test_create_depot_allocation_sets_remaining(self, client: AsyncClient):
        payload = _make_depot_allocation_create(allocated_units=7000)
        resp = await client.post(f"{API_PREFIX}/depot-allocations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["allocated_units"] == 7000
        assert data["remaining_units"] == 7000
        assert data["shipped_units"] == 0

    @pytest.mark.anyio
    async def test_multiple_filters_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiry-risks",
            params={"trial_id": LIBTAYO_TRIAL, "resolved": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["resolved"] is False
