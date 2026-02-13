"""Tests for Site Resource Planning (SRP-PLN).

Covers:
- Seed data verification (staff allocations, equipment, capacity, workloads)
- Staff Allocation CRUD (create, read, update, delete, list, filter by trial)
- Equipment Inventory CRUD (create, read, update, delete, list, filter by trial)
- Capacity Assessment CRUD (create, read, update, delete, list, filter by trial)
- Workload Distribution CRUD (create, read, update, delete, list, filter by trial)
- Metrics computation (total counts, breakdowns, averages)
- Not-found error handling (404s for all entities)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.site_resource_planning_service import (
    SiteResourcePlanningService,
    get_site_resource_planning_service,
    reset_site_resource_planning_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-resource-planning"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_resource_planning_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SiteResourcePlanningService:
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


def _make_staff_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "staff_name": "Test Staff",
        "staff_role": "study_coordinator",
        "start_date": now.isoformat(),
        "allocated_by": "Test Manager",
    }
    defaults.update(overrides)
    return defaults


def _make_equipment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "equipment_name": "Test Equipment",
        "equipment_type": "Imaging",
        "managed_by": "Test Department",
    }
    defaults.update(overrides)
    return defaults


def _make_capacity_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "assessment_date": now.isoformat(),
        "assessed_by": "Test Assessor",
        "max_subjects": 30,
    }
    defaults.update(overrides)
    return defaults


def _make_workload_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "task_category": "Subject Visits",
        "assigned_staff": "Test Staff",
        "week_start_date": now.isoformat(),
        "week_end_date": (now + timedelta(days=6)).isoformat(),
        "distributed_by": "Test Distributor",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_staff_allocations_count(self, svc: SiteResourcePlanningService):
        items = svc.list_staff_allocations()
        assert len(items) == 12

    def test_seed_equipment_inventories_count(self, svc: SiteResourcePlanningService):
        items = svc.list_equipment_inventories()
        assert len(items) == 12

    def test_seed_capacity_assessments_count(self, svc: SiteResourcePlanningService):
        items = svc.list_capacity_assessments()
        assert len(items) == 12

    def test_seed_workload_distributions_count(self, svc: SiteResourcePlanningService):
        items = svc.list_workload_distributions()
        assert len(items) == 12

    def test_seed_staff_across_trials(self, svc: SiteResourcePlanningService):
        eylea = svc.list_staff_allocations(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_staff_allocations(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_staff_allocations(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_equipment_across_trials(self, svc: SiteResourcePlanningService):
        eylea = svc.list_equipment_inventories(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_equipment_inventories(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_equipment_inventories(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_capacity_across_trials(self, svc: SiteResourcePlanningService):
        eylea = svc.list_capacity_assessments(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_capacity_assessments(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_capacity_assessments(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_workloads_across_trials(self, svc: SiteResourcePlanningService):
        eylea = svc.list_workload_distributions(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_workload_distributions(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_workload_distributions(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4


# =====================================================================
# STAFF ALLOCATION CRUD
# =====================================================================


class TestStaffAllocationCrud:
    """Test Staff Allocation create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_staff_allocations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-allocations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_staff_allocations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/staff-allocations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_staff_allocation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-allocations/STA-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "STA-00000001"
        assert data["staff_name"] == "Dr. Sarah Chen"
        assert data["staff_role"] == "principal_investigator"

    @pytest.mark.anyio
    async def test_get_staff_allocation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-allocations/STA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_staff_allocation(self, client: AsyncClient):
        payload = _make_staff_create()
        resp = await client.post(f"{API_PREFIX}/staff-allocations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["staff_name"] == "Test Staff"
        assert data["id"].startswith("STA-")
        assert data["allocation_status"] == "pending"

    @pytest.mark.anyio
    async def test_update_staff_allocation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/staff-allocations/STA-00000003",
            json={"allocation_status": "allocated", "certification_verified": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allocation_status"] == "allocated"
        assert data["certification_verified"] is True

    @pytest.mark.anyio
    async def test_update_staff_allocation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/staff-allocations/STA-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_staff_allocation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/staff-allocations/STA-00000012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/staff-allocations/STA-00000012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_staff_allocation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/staff-allocations/STA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EQUIPMENT INVENTORY CRUD
# =====================================================================


class TestEquipmentInventoryCrud:
    """Test Equipment Inventory create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_equipment_inventories(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-inventories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_equipment_inventories_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/equipment-inventories", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_equipment_inventory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-inventories/EQI-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EQI-00000001"
        assert data["equipment_name"] == "OCT Scanner"
        assert data["equipment_status"] == "available"

    @pytest.mark.anyio
    async def test_get_equipment_inventory_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-inventories/EQI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_equipment_inventory(self, client: AsyncClient):
        payload = _make_equipment_create()
        resp = await client.post(f"{API_PREFIX}/equipment-inventories", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["equipment_name"] == "Test Equipment"
        assert data["id"].startswith("EQI-")
        assert data["equipment_status"] == "available"

    @pytest.mark.anyio
    async def test_update_equipment_inventory(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/equipment-inventories/EQI-00000004",
            json={"equipment_status": "available", "location": "Pharmacy Storage - New Wing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["equipment_status"] == "available"
        assert data["location"] == "Pharmacy Storage - New Wing"

    @pytest.mark.anyio
    async def test_update_equipment_inventory_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/equipment-inventories/EQI-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_equipment_inventory(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/equipment-inventories/EQI-00000008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/equipment-inventories/EQI-00000008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_equipment_inventory_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/equipment-inventories/EQI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CAPACITY ASSESSMENT CRUD
# =====================================================================


class TestCapacityAssessmentCrud:
    """Test Capacity Assessment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_capacity_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capacity-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_capacity_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capacity-assessments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_capacity_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capacity-assessments/CPA-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CPA-00000001"
        assert data["capacity_level"] == "optimal"
        assert data["max_subjects"] == 40

    @pytest.mark.anyio
    async def test_get_capacity_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capacity-assessments/CPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capacity_assessment(self, client: AsyncClient):
        payload = _make_capacity_create()
        resp = await client.post(f"{API_PREFIX}/capacity-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["max_subjects"] == 30
        assert data["id"].startswith("CPA-")
        assert data["capacity_level"] == "unknown"

    @pytest.mark.anyio
    async def test_update_capacity_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capacity-assessments/CPA-00000009",
            json={"capacity_level": "at_capacity", "current_subjects": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capacity_level"] == "at_capacity"
        assert data["current_subjects"] == 20

    @pytest.mark.anyio
    async def test_update_capacity_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capacity-assessments/CPA-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capacity_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capacity-assessments/CPA-00000012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/capacity-assessments/CPA-00000012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capacity_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capacity-assessments/CPA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# WORKLOAD DISTRIBUTION CRUD
# =====================================================================


class TestWorkloadDistributionCrud:
    """Test Workload Distribution create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_workload_distributions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/workload-distributions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_workload_distributions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/workload-distributions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_workload_distribution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/workload-distributions/WLD-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "WLD-00000001"
        assert data["task_category"] == "Subject Visits"
        assert data["workload_priority"] == "high"

    @pytest.mark.anyio
    async def test_get_workload_distribution_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/workload-distributions/WLD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_workload_distribution(self, client: AsyncClient):
        payload = _make_workload_create()
        resp = await client.post(f"{API_PREFIX}/workload-distributions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_category"] == "Subject Visits"
        assert data["id"].startswith("WLD-")
        assert data["workload_priority"] == "medium"

    @pytest.mark.anyio
    async def test_update_workload_distribution(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/workload-distributions/WLD-00000004",
            json={"workload_priority": "high", "estimated_hours": 8.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["workload_priority"] == "high"
        assert data["estimated_hours"] == 8.0

    @pytest.mark.anyio
    async def test_update_workload_distribution_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/workload-distributions/WLD-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_workload_distribution(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/workload-distributions/WLD-00000012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/workload-distributions/WLD-00000012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_workload_distribution_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/workload-distributions/WLD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test site resource planning metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_staff_allocations"] == 12
        assert data["total_equipment"] == 12
        assert data["total_capacity_assessments"] == 12
        assert data["total_workload_entries"] == 12
        assert data["avg_fte_utilization"] > 0
        assert data["avg_utilization_pct"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_staff_allocations"] == 4
        assert data["total_equipment"] == 4
        assert data["total_capacity_assessments"] == 4
        assert data["total_workload_entries"] == 4

    def test_metrics_allocations_by_status(self, svc: SiteResourcePlanningService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.allocations_by_status.values())
        assert total_by_status == metrics.total_staff_allocations

    def test_metrics_allocations_by_role(self, svc: SiteResourcePlanningService):
        metrics = svc.get_metrics()
        total_by_role = sum(metrics.allocations_by_role.values())
        assert total_by_role == metrics.total_staff_allocations

    def test_metrics_equipment_by_status(self, svc: SiteResourcePlanningService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.equipment_by_status.values())
        assert total_by_status == metrics.total_equipment

    def test_metrics_assessments_by_level(self, svc: SiteResourcePlanningService):
        metrics = svc.get_metrics()
        total_by_level = sum(metrics.assessments_by_level.values())
        assert total_by_level == metrics.total_capacity_assessments

    def test_metrics_workloads_by_priority(self, svc: SiteResourcePlanningService):
        metrics = svc.get_metrics()
        total_by_priority = sum(metrics.workloads_by_priority.values())
        assert total_by_priority == metrics.total_workload_entries


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_site_resource_planning_service()
        svc2 = get_site_resource_planning_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_site_resource_planning_service()
        svc2 = reset_site_resource_planning_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_resource_planning_service()
        svc.delete_staff_allocation("STA-00000001")
        assert svc.get_staff_allocation("STA-00000001") is None
        svc2 = reset_site_resource_planning_service()
        assert svc2.get_staff_allocation("STA-00000001") is not None


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Test that seed data covers various enum values."""

    def test_allocation_statuses_represented(self, svc: SiteResourcePlanningService):
        items = svc.list_staff_allocations()
        statuses = {s.allocation_status.value for s in items}
        assert "allocated" in statuses
        assert "pending" in statuses
        assert "released" in statuses
        assert "on_hold" in statuses
        assert "requested" in statuses
        assert "denied" in statuses

    def test_staff_roles_represented(self, svc: SiteResourcePlanningService):
        items = svc.list_staff_allocations()
        roles = {s.staff_role.value for s in items}
        assert "principal_investigator" in roles
        assert "sub_investigator" in roles
        assert "study_coordinator" in roles
        assert "research_nurse" in roles
        assert "pharmacist" in roles
        assert "data_entry" in roles

    def test_equipment_statuses_represented(self, svc: SiteResourcePlanningService):
        items = svc.list_equipment_inventories()
        statuses = {e.equipment_status.value for e in items}
        assert "available" in statuses
        assert "in_use" in statuses
        assert "maintenance" in statuses
        assert "calibration_due" in statuses
        assert "decommissioned" in statuses
        assert "on_order" in statuses

    def test_capacity_levels_represented(self, svc: SiteResourcePlanningService):
        items = svc.list_capacity_assessments()
        levels = {c.capacity_level.value for c in items}
        assert "under_capacity" in levels
        assert "optimal" in levels
        assert "near_capacity" in levels
        assert "at_capacity" in levels
        assert "over_capacity" in levels
        assert "unknown" in levels

    def test_workload_priorities_represented(self, svc: SiteResourcePlanningService):
        items = svc.list_workload_distributions()
        priorities = {w.workload_priority.value for w in items}
        assert "critical" in priorities
        assert "high" in priorities
        assert "medium" in priorities
        assert "low" in priorities
        assert "deferred" in priorities
        assert "routine" in priorities
