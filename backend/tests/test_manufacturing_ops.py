"""Tests for Manufacturing Operations & Batch Record (MFG-OPS).

Covers:
- Seed data verification (batches, equipment, env monitoring, validations, deviations, checklists)
- Batch record CRUD (create, read, update, delete, list, filter by status/site/product)
- Batch lifecycle (planned -> in_progress -> completed -> released)
- Batch release validation (checklist completeness, open critical deviations)
- Equipment CRUD (create, read, update, delete, list, filter by status/type/area)
- Environmental monitoring (list, filter by zone/result/room, log with auto-evaluation)
- Process validation CRUD and lifecycle (planned -> in_progress -> passed/failed)
- Deviation management (create, update, close, filter, critical auto-quarantine)
- Batch release checklist CRUD (create, update, check items, filter)
- Manufacturing metrics computation
- Error handling (404s, 400s, invalid state transitions)
- Edge cases (boundary conditions, partial filters, yield calculations)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.manufacturing_ops import (
    BatchReleaseRequest,
    BatchStatus,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DeviationCreate,
    DeviationStatus,
    DeviationType,
    DeviationUpdate,
    EnvironmentalMonitoringCreate,
    EnvironmentalZone,
    EquipmentCreate,
    EquipmentStatus,
    EquipmentUpdate,
    MonitoringResult,
    ProcessValidationCreate,
    ProcessValidationUpdate,
    ValidationStatus,
)
from app.services.manufacturing_ops_service import (
    ManufacturingOpsService,
    get_manufacturing_ops_service,
    reset_manufacturing_ops_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/manufacturing-ops"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_manufacturing_ops_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ManufacturingOpsService:
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


def _make_batch_create(**overrides) -> dict:
    defaults = {
        "product_name": "Test Biologic 100mg",
        "batch_number": "TEST-2026-001",
        "lot_number": "LOT-TEST-001",
        "manufacturing_site": "Test Manufacturing Plant",
        "batch_size": 1000.0,
        "unit_of_measure": "vials",
        "master_batch_record_version": "MBR-TEST-v1.0",
        "yield_theoretical": 1000.0,
    }
    defaults.update(overrides)
    return defaults


def _make_equipment_create(**overrides) -> dict:
    defaults = {
        "name": "Test Bioreactor",
        "equipment_type": "bioreactor",
        "serial_number": "TB-2026-001",
        "location": "Test Building, Suite 100",
        "maintenance_schedule": "Quarterly",
        "assigned_area": "Test Suite",
    }
    defaults.update(overrides)
    return defaults


def _make_env_monitoring_create(**overrides) -> dict:
    defaults = {
        "zone": "grade_a",
        "room_name": "Test Room A-100",
        "temperature": 20.0,
        "humidity": 42.0,
        "particle_count_05um": 2000,
        "particle_count_5um": 10,
        "viable_count": 0,
        "alert_limit": 3520.0,
        "action_limit": 3520.0,
        "monitored_by": "Test Operator",
    }
    defaults.update(overrides)
    return defaults


def _make_validation_create(**overrides) -> dict:
    defaults = {
        "product_name": "Test Drug Product",
        "process_step": "Test Process Step",
        "validation_protocol": "VP-TEST-001",
        "batches_required": 3,
        "acceptance_criteria": "All test parameters within specification",
    }
    defaults.update(overrides)
    return defaults


def _make_deviation_create(**overrides) -> dict:
    defaults = {
        "batch_id": "BATCH-003",
        "deviation_type": "minor",
        "description": "Test deviation description",
        "reported_by": "Test Reporter",
        "impact_assessment": "No impact on product quality",
    }
    defaults.update(overrides)
    return defaults


def _make_checklist_create(**overrides) -> dict:
    defaults = {
        "batch_id": "BATCH-002",
        "item_description": "Test checklist item",
        "required": True,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_batches_count(self, svc: ManufacturingOpsService):
        batches = svc.list_batches()
        assert len(batches) == 5

    def test_seed_batches_statuses(self, svc: ManufacturingOpsService):
        batches = svc.list_batches()
        statuses = {b.status for b in batches}
        assert BatchStatus.RELEASED in statuses
        assert BatchStatus.COMPLETED in statuses
        assert BatchStatus.IN_PROGRESS in statuses
        assert BatchStatus.PLANNED in statuses
        assert BatchStatus.QUARANTINE in statuses

    def test_seed_equipment_count(self, svc: ManufacturingOpsService):
        equipment = svc.list_equipment()
        assert len(equipment) == 8

    def test_seed_equipment_statuses(self, svc: ManufacturingOpsService):
        equipment = svc.list_equipment()
        statuses = {e.status for e in equipment}
        assert EquipmentStatus.QUALIFIED in statuses
        assert EquipmentStatus.DUE_FOR_REQUALIFICATION in statuses
        assert EquipmentStatus.UNDER_MAINTENANCE in statuses
        assert EquipmentStatus.OUT_OF_SERVICE in statuses

    def test_seed_env_monitoring_count(self, svc: ManufacturingOpsService):
        records = svc.list_environmental_monitoring()
        assert len(records) == 12

    def test_seed_env_monitoring_results(self, svc: ManufacturingOpsService):
        records = svc.list_environmental_monitoring()
        results = {r.result for r in records}
        assert MonitoringResult.PASS in results
        assert MonitoringResult.ALERT in results
        assert MonitoringResult.ACTION_REQUIRED in results
        assert MonitoringResult.FAIL in results

    def test_seed_env_monitoring_zones(self, svc: ManufacturingOpsService):
        records = svc.list_environmental_monitoring()
        zones = {r.zone for r in records}
        assert EnvironmentalZone.GRADE_A in zones
        assert EnvironmentalZone.GRADE_B in zones
        assert EnvironmentalZone.GRADE_C in zones
        assert EnvironmentalZone.GRADE_D in zones
        assert EnvironmentalZone.UNCLASSIFIED in zones

    def test_seed_validations_count(self, svc: ManufacturingOpsService):
        validations = svc.list_validations()
        assert len(validations) == 4

    def test_seed_validations_statuses(self, svc: ManufacturingOpsService):
        validations = svc.list_validations()
        statuses = {v.status for v in validations}
        assert ValidationStatus.PASSED in statuses
        assert ValidationStatus.IN_PROGRESS in statuses
        assert ValidationStatus.PLANNED in statuses
        assert ValidationStatus.FAILED in statuses

    def test_seed_deviations_count(self, svc: ManufacturingOpsService):
        deviations = svc.list_deviations()
        assert len(deviations) == 5

    def test_seed_deviations_types(self, svc: ManufacturingOpsService):
        deviations = svc.list_deviations()
        types = {d.deviation_type for d in deviations}
        assert DeviationType.MINOR in types
        assert DeviationType.MAJOR in types
        assert DeviationType.CRITICAL in types

    def test_seed_checklists_count(self, svc: ManufacturingOpsService):
        checklists = svc.list_checklists()
        assert len(checklists) == 14

    def test_seed_released_batch_has_all_checked(self, svc: ManufacturingOpsService):
        batch1_items = svc.list_checklists(batch_id="BATCH-001")
        for item in batch1_items:
            assert item.checked is True

    def test_seed_quarantine_batch_has_unchecked(self, svc: ManufacturingOpsService):
        batch5_items = svc.list_checklists(batch_id="BATCH-005")
        unchecked = [i for i in batch5_items if not i.checked]
        assert len(unchecked) > 0


# =====================================================================
# BATCH RECORD CRUD
# =====================================================================


class TestBatchCrud:
    """Test batch record create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_batches(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.anyio
    async def test_list_batches_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"status": "released"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "released"

    @pytest.mark.anyio
    async def test_list_batches_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"manufacturing_site": "Rensselaer"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "Rensselaer" in item["manufacturing_site"]

    @pytest.mark.anyio
    async def test_list_batches_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"product_name": "Dupilumab"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "Dupilumab" in item["product_name"]

    @pytest.mark.anyio
    async def test_get_batch(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/BATCH-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BATCH-001"
        assert data["status"] == "released"
        assert data["released_by"] is not None

    @pytest.mark.anyio
    async def test_get_batch_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/BATCH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_batch(self, client: AsyncClient):
        payload = _make_batch_create()
        resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Test Biologic 100mg"
        assert data["status"] == "planned"
        assert data["id"].startswith("BATCH-")

    @pytest.mark.anyio
    async def test_update_batch(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/BATCH-004",
            json={"product_name": "Updated Product Name", "batch_size": 10000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_name"] == "Updated Product Name"
        assert data["batch_size"] == 10000.0

    @pytest.mark.anyio
    async def test_update_batch_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/BATCH-NONEXISTENT",
            json={"product_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_batch(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/batches/BATCH-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/batches/BATCH-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_batch_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/batches/BATCH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_batch_yield_recalculation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/BATCH-002",
            json={"yield_actual": 9500.0, "yield_theoretical": 10000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["yield_pct"] == 95.0


# =====================================================================
# BATCH LIFECYCLE
# =====================================================================


class TestBatchLifecycle:
    """Test batch lifecycle transitions."""

    @pytest.mark.anyio
    async def test_start_batch(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-004/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["start_date"] is not None

    @pytest.mark.anyio
    async def test_start_batch_not_planned(self, client: AsyncClient):
        # BATCH-003 is already in_progress
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-003/start")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_start_batch_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-NONEXISTENT/start")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_complete_batch(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches/BATCH-003/complete",
            params={"yield_actual": 1850.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["yield_actual"] == 1850.0
        assert data["yield_pct"] == 92.5
        assert data["end_date"] is not None

    @pytest.mark.anyio
    async def test_complete_batch_not_in_progress(self, client: AsyncClient):
        # BATCH-004 is planned, not in_progress
        resp = await client.post(
            f"{API_PREFIX}/batches/BATCH-004/complete",
            params={"yield_actual": 7000.0},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_complete_batch_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches/BATCH-NONEXISTENT/complete",
            params={"yield_actual": 100.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_full_batch_lifecycle(self, client: AsyncClient):
        """Test planned -> start -> complete -> release."""
        # Create new batch
        payload = _make_batch_create()
        resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert resp.status_code == 201
        batch_id = resp.json()["id"]
        assert resp.json()["status"] == "planned"

        # Start
        resp = await client.post(f"{API_PREFIX}/batches/{batch_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

        # Complete
        resp = await client.post(
            f"{API_PREFIX}/batches/{batch_id}/complete",
            params={"yield_actual": 950.0},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["yield_pct"] == 95.0


# =====================================================================
# BATCH RELEASE
# =====================================================================


class TestBatchRelease:
    """Test batch release with checklist and deviation verification."""

    @pytest.mark.anyio
    async def test_release_batch_not_completed(self, client: AsyncClient):
        # BATCH-003 is in_progress
        payload = {"released_by": "Dr. Test", "reviewed_by": "Dr. Reviewer"}
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-003/release", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_release_batch_unchecked_items(self, client: AsyncClient):
        # BATCH-002 is completed but has unchecked required items
        payload = {"released_by": "Dr. Test", "reviewed_by": "Dr. Reviewer"}
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-002/release", json=payload)
        assert resp.status_code == 400
        body = resp.json()
        error_text = (body.get("detail") or body.get("message") or "").lower()
        assert "checklist" in error_text

    @pytest.mark.anyio
    async def test_release_batch_not_found(self, client: AsyncClient):
        payload = {"released_by": "Dr. Test", "reviewed_by": "Dr. Reviewer"}
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-NONEXISTENT/release", json=payload)
        assert resp.status_code == 404

    def test_release_batch_with_open_critical_deviation(self, svc: ManufacturingOpsService):
        """Batch with open critical deviations cannot be released."""
        # First complete BATCH-003 so we can attempt release
        completed = svc.complete_batch("BATCH-003", yield_actual=1900.0)
        assert completed is not None
        # Record a critical deviation for BATCH-003 (auto-quarantines the batch)
        svc.record_deviation(DeviationCreate(
            batch_id="BATCH-003",
            deviation_type=DeviationType.CRITICAL,
            description="Test critical deviation",
            reported_by="Test",
        ))
        # Attempt release should fail — batch is quarantined (not completed)
        with pytest.raises(ValueError, match="cannot be released"):
            svc.release_batch("BATCH-003", BatchReleaseRequest(
                released_by="Dr. Test",
                reviewed_by="Dr. Reviewer",
            ))

    def test_release_batch_success(self, svc: ManufacturingOpsService):
        """Batch with all checklist items complete and no critical deviations can be released."""
        # Complete BATCH-003
        completed = svc.complete_batch("BATCH-003", yield_actual=1900.0)
        assert completed is not None
        # No checklist items, so release should succeed
        released = svc.release_batch("BATCH-003", BatchReleaseRequest(
            released_by="Dr. QP",
            reviewed_by="Dr. QA",
        ))
        assert released is not None
        assert released.status == BatchStatus.RELEASED
        assert released.released_by == "Dr. QP"
        assert released.release_date is not None


# =====================================================================
# EQUIPMENT CRUD
# =====================================================================


class TestEquipmentCrud:
    """Test equipment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_equipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_equipment_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment", params={"status": "qualified"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "qualified"

    @pytest.mark.anyio
    async def test_list_equipment_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment", params={"equipment_type": "bioreactor"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "bioreactor" in item["equipment_type"].lower()

    @pytest.mark.anyio
    async def test_list_equipment_filter_area(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment", params={"assigned_area": "Purification"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "Purification" in item["assigned_area"]

    @pytest.mark.anyio
    async def test_get_equipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment/EQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EQ-001"
        assert data["name"] == "Bioreactor BR-500"

    @pytest.mark.anyio
    async def test_get_equipment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment/EQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_equipment(self, client: AsyncClient):
        payload = _make_equipment_create()
        resp = await client.post(f"{API_PREFIX}/equipment", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Bioreactor"
        assert data["status"] == "qualified"
        assert data["id"].startswith("EQ-")

    @pytest.mark.anyio
    async def test_update_equipment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/equipment/EQ-001",
            json={"name": "Updated Bioreactor", "status": "under_maintenance"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Bioreactor"
        assert data["status"] == "under_maintenance"

    @pytest.mark.anyio
    async def test_update_equipment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/equipment/EQ-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_equipment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/equipment/EQ-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/equipment/EQ-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_equipment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/equipment/EQ-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ENVIRONMENTAL MONITORING
# =====================================================================


class TestEnvironmentalMonitoring:
    """Test environmental monitoring operations."""

    @pytest.mark.anyio
    async def test_list_env_monitoring(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_env_monitoring_filter_zone(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring", params={"zone": "grade_a"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["zone"] == "grade_a"

    @pytest.mark.anyio
    async def test_list_env_monitoring_filter_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring", params={"result": "fail"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["result"] == "fail"

    @pytest.mark.anyio
    async def test_list_env_monitoring_filter_room(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/environmental-monitoring",
            params={"room_name": "Aseptic Fill"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "Aseptic Fill" in item["room_name"]

    @pytest.mark.anyio
    async def test_get_env_monitoring(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring/ENV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ENV-001"
        assert data["zone"] == "grade_a"

    @pytest.mark.anyio
    async def test_get_env_monitoring_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring/ENV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_log_env_monitoring_pass(self, client: AsyncClient):
        payload = _make_env_monitoring_create()
        resp = await client.post(f"{API_PREFIX}/environmental-monitoring", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == "pass"
        assert data["id"].startswith("ENV-")

    @pytest.mark.anyio
    async def test_log_env_monitoring_grade_a_exceedance(self, client: AsyncClient):
        payload = _make_env_monitoring_create(
            particle_count_05um=5000,
            particle_count_5um=25,
        )
        resp = await client.post(f"{API_PREFIX}/environmental-monitoring", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # Should trigger action_required or fail due to exceeding Grade A limits
        assert data["result"] in ("action_required", "fail")

    @pytest.mark.anyio
    async def test_log_env_monitoring_high_viable(self, client: AsyncClient):
        payload = _make_env_monitoring_create(viable_count=2)
        resp = await client.post(f"{API_PREFIX}/environmental-monitoring", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] in ("alert", "action_required")

    @pytest.mark.anyio
    async def test_log_env_monitoring_grade_b(self, client: AsyncClient):
        payload = _make_env_monitoring_create(
            zone="grade_b",
            room_name="Test Grade B Room",
            particle_count_05um=300000,
            particle_count_5um=2000,
            viable_count=3,
        )
        resp = await client.post(f"{API_PREFIX}/environmental-monitoring", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == "pass"

    @pytest.mark.anyio
    async def test_log_env_monitoring_temp_excursion(self, client: AsyncClient):
        payload = _make_env_monitoring_create(
            zone="grade_c",
            room_name="Test Grade C Room",
            temperature=26.0,
            particle_count_05um=None,
            particle_count_5um=None,
            viable_count=None,
            alert_limit=None,
            action_limit=None,
        )
        resp = await client.post(f"{API_PREFIX}/environmental-monitoring", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == "action_required"

    @pytest.mark.anyio
    async def test_env_monitoring_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring")
        data = resp.json()
        dates = [item["monitoring_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# ENVIRONMENTAL MONITORING AUTO-EVALUATION
# =====================================================================


class TestEnvironmentalAutoEvaluation:
    """Test automatic result evaluation for environmental monitoring."""

    def test_grade_a_pass(self, svc: ManufacturingOpsService):
        record = svc.log_environmental_monitoring(EnvironmentalMonitoringCreate(
            zone=EnvironmentalZone.GRADE_A,
            room_name="Test Room",
            particle_count_05um=2000,
            particle_count_5um=10,
            viable_count=0,
            temperature=20.0,
            humidity=42.0,
            monitored_by="Tester",
        ))
        assert record.result == MonitoringResult.PASS

    def test_grade_a_action_required_particles(self, svc: ManufacturingOpsService):
        record = svc.log_environmental_monitoring(EnvironmentalMonitoringCreate(
            zone=EnvironmentalZone.GRADE_A,
            room_name="Test Room",
            particle_count_05um=4000,
            particle_count_5um=10,
            viable_count=0,
            temperature=20.0,
            humidity=42.0,
            monitored_by="Tester",
        ))
        assert record.result == MonitoringResult.ACTION_REQUIRED

    def test_grade_a_fail_high_particles(self, svc: ManufacturingOpsService):
        record = svc.log_environmental_monitoring(EnvironmentalMonitoringCreate(
            zone=EnvironmentalZone.GRADE_A,
            room_name="Test Room",
            particle_count_05um=6000,
            particle_count_5um=10,
            viable_count=0,
            temperature=20.0,
            humidity=42.0,
            monitored_by="Tester",
        ))
        assert record.result == MonitoringResult.FAIL

    def test_grade_a_alert_viable(self, svc: ManufacturingOpsService):
        record = svc.log_environmental_monitoring(EnvironmentalMonitoringCreate(
            zone=EnvironmentalZone.GRADE_A,
            room_name="Test Room",
            particle_count_05um=2000,
            particle_count_5um=10,
            viable_count=2,
            temperature=20.0,
            humidity=42.0,
            monitored_by="Tester",
        ))
        assert record.result == MonitoringResult.ALERT

    def test_grade_b_fail_viable(self, svc: ManufacturingOpsService):
        record = svc.log_environmental_monitoring(EnvironmentalMonitoringCreate(
            zone=EnvironmentalZone.GRADE_B,
            room_name="Test Room",
            particle_count_05um=300000,
            particle_count_5um=2000,
            viable_count=15,
            temperature=20.0,
            humidity=42.0,
            monitored_by="Tester",
        ))
        assert record.result == MonitoringResult.FAIL

    def test_humidity_alert(self, svc: ManufacturingOpsService):
        record = svc.log_environmental_monitoring(EnvironmentalMonitoringCreate(
            zone=EnvironmentalZone.GRADE_D,
            room_name="Test Room",
            humidity=58.0,
            temperature=20.0,
            monitored_by="Tester",
        ))
        assert record.result == MonitoringResult.ALERT


# =====================================================================
# PROCESS VALIDATION
# =====================================================================


class TestProcessValidation:
    """Test process validation CRUD and lifecycle."""

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_validations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"status": "passed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "passed"

    @pytest.mark.anyio
    async def test_list_validations_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"product_name": "Dupilumab"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/PV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PV-001"
        assert data["status"] == "passed"

    @pytest.mark.anyio
    async def test_get_validation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/PV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = _make_validation_create()
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "planned"
        assert data["batches_completed"] == 0
        assert data["id"].startswith("PV-")

    @pytest.mark.anyio
    async def test_update_validation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/PV-003",
            json={"status": "in_progress", "batches_completed": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["batches_completed"] == 1
        assert data["start_date"] is not None  # Auto-set on status transition

    @pytest.mark.anyio
    async def test_update_validation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/PV-NONEXISTENT",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/PV-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/validations/PV-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/PV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_validate_process_pass(self, client: AsyncClient, svc: ManufacturingOpsService):
        # PV-002 is in_progress with 2/3 batches - update to 3/3 first
        svc.update_validation("PV-002", ProcessValidationUpdate(batches_completed=3))
        resp = await client.post(f"{API_PREFIX}/validations/PV-002/pass")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "passed"
        assert data["completion_date"] is not None

    @pytest.mark.anyio
    async def test_validate_process_not_in_progress(self, client: AsyncClient):
        # PV-001 is already passed
        resp = await client.post(f"{API_PREFIX}/validations/PV-001/pass")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_validate_process_insufficient_batches(self, client: AsyncClient):
        # PV-002 has 2/3 batches
        resp = await client.post(f"{API_PREFIX}/validations/PV-002/pass")
        assert resp.status_code == 400
        body = resp.json()
        error_text = (body.get("detail") or body.get("message") or "").lower()
        assert "batches" in error_text

    @pytest.mark.anyio
    async def test_validate_process_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/validations/PV-NONEXISTENT/pass")
        assert resp.status_code == 404


# =====================================================================
# PROCESS VALIDATION LIFECYCLE
# =====================================================================


class TestValidationLifecycle:
    """Test validation status transitions."""

    def test_planned_to_in_progress(self, svc: ManufacturingOpsService):
        updated = svc.update_validation("PV-003", ProcessValidationUpdate(status=ValidationStatus.IN_PROGRESS))
        assert updated is not None
        assert updated.status == ValidationStatus.IN_PROGRESS
        assert updated.start_date is not None

    def test_in_progress_to_passed(self, svc: ManufacturingOpsService):
        # Complete all required batches first
        svc.update_validation("PV-002", ProcessValidationUpdate(batches_completed=3))
        result = svc.validate_process("PV-002")
        assert result is not None
        assert result.status == ValidationStatus.PASSED
        assert result.completion_date is not None

    def test_in_progress_to_failed(self, svc: ManufacturingOpsService):
        updated = svc.update_validation("PV-002", ProcessValidationUpdate(
            status=ValidationStatus.FAILED,
            results_summary="Batch 3 did not meet acceptance criteria",
        ))
        assert updated is not None
        assert updated.status == ValidationStatus.FAILED
        assert updated.completion_date is not None


# =====================================================================
# DEVIATION MANAGEMENT
# =====================================================================


class TestDeviationManagement:
    """Test manufacturing deviation operations."""

    @pytest.mark.anyio
    async def test_list_deviations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_deviations_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations", params={"deviation_type": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["deviation_type"] == "critical"

    @pytest.mark.anyio
    async def test_list_deviations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations", params={"status": "closed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "closed"

    @pytest.mark.anyio
    async def test_list_deviations_filter_batch(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations", params={"batch_id": "BATCH-005"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["batch_id"] == "BATCH-005"

    @pytest.mark.anyio
    async def test_get_deviation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations/DEV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEV-001"
        assert data["deviation_type"] == "major"

    @pytest.mark.anyio
    async def test_get_deviation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations/DEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_deviation(self, client: AsyncClient):
        payload = _make_deviation_create()
        resp = await client.post(f"{API_PREFIX}/deviations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["deviation_type"] == "minor"
        assert data["status"] == "open"
        assert data["id"].startswith("DEV-")

    @pytest.mark.anyio
    async def test_update_deviation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deviations/DEV-004",
            json={
                "corrective_action": "Probe replaced and verified",
                "status": "closed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_deviation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deviations/DEV-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deviation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deviations/DEV-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/deviations/DEV-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deviation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deviations/DEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_deviations_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations")
        data = resp.json()
        dates = [item["reported_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# CRITICAL DEVIATION AUTO-QUARANTINE
# =====================================================================


class TestCriticalDeviationAutoQuarantine:
    """Test that critical deviations automatically quarantine the associated batch."""

    def test_critical_deviation_quarantines_batch(self, svc: ManufacturingOpsService):
        # BATCH-003 is in_progress
        batch_before = svc.get_batch("BATCH-003")
        assert batch_before is not None
        assert batch_before.status == BatchStatus.IN_PROGRESS

        svc.record_deviation(DeviationCreate(
            batch_id="BATCH-003",
            deviation_type=DeviationType.CRITICAL,
            description="Critical contamination event",
            reported_by="Test Operator",
        ))

        batch_after = svc.get_batch("BATCH-003")
        assert batch_after is not None
        assert batch_after.status == BatchStatus.QUARANTINE

    def test_minor_deviation_does_not_quarantine(self, svc: ManufacturingOpsService):
        batch_before = svc.get_batch("BATCH-003")
        assert batch_before is not None
        assert batch_before.status == BatchStatus.IN_PROGRESS

        svc.record_deviation(DeviationCreate(
            batch_id="BATCH-003",
            deviation_type=DeviationType.MINOR,
            description="Minor documentation error",
            reported_by="Test Operator",
        ))

        batch_after = svc.get_batch("BATCH-003")
        assert batch_after is not None
        assert batch_after.status == BatchStatus.IN_PROGRESS

    def test_critical_deviation_no_quarantine_if_released(self, svc: ManufacturingOpsService):
        # BATCH-001 is already released - should not be quarantined
        svc.record_deviation(DeviationCreate(
            batch_id="BATCH-001",
            deviation_type=DeviationType.CRITICAL,
            description="Post-release finding",
            reported_by="Test",
        ))
        batch = svc.get_batch("BATCH-001")
        assert batch is not None
        assert batch.status == BatchStatus.RELEASED  # Stays released

    def test_critical_deviation_without_batch(self, svc: ManufacturingOpsService):
        """Critical deviation without batch_id should not raise."""
        dev = svc.record_deviation(DeviationCreate(
            batch_id=None,
            deviation_type=DeviationType.CRITICAL,
            description="Facility-level critical deviation",
            reported_by="Test",
        ))
        assert dev.status == DeviationStatus.OPEN


# =====================================================================
# DEVIATION LIFECYCLE
# =====================================================================


class TestDeviationLifecycle:
    """Test deviation lifecycle transitions."""

    def test_open_to_under_investigation(self, svc: ManufacturingOpsService):
        updated = svc.update_deviation("DEV-004", DeviationUpdate(
            status=DeviationStatus.UNDER_INVESTIGATION,
        ))
        assert updated is not None
        assert updated.status == DeviationStatus.UNDER_INVESTIGATION

    def test_under_investigation_to_corrective_action(self, svc: ManufacturingOpsService):
        updated = svc.update_deviation("DEV-003", DeviationUpdate(
            root_cause="Identified root cause",
            status=DeviationStatus.CORRECTIVE_ACTION,
            corrective_action="Corrective action taken",
        ))
        assert updated is not None
        assert updated.status == DeviationStatus.CORRECTIVE_ACTION
        assert updated.root_cause == "Identified root cause"

    def test_close_deviation_auto_resolved_date(self, svc: ManufacturingOpsService):
        updated = svc.update_deviation("DEV-004", DeviationUpdate(
            status=DeviationStatus.CLOSED,
            preventive_action="Updated maintenance schedule",
        ))
        assert updated is not None
        assert updated.status == DeviationStatus.CLOSED
        assert updated.resolved_date is not None

    def test_already_closed_keeps_resolved_date(self, svc: ManufacturingOpsService):
        dev = svc.get_deviation("DEV-001")
        assert dev is not None
        assert dev.resolved_date is not None
        original_date = dev.resolved_date

        updated = svc.update_deviation("DEV-001", DeviationUpdate(
            description="Updated description",
        ))
        assert updated is not None
        assert updated.resolved_date == original_date


# =====================================================================
# BATCH RELEASE CHECKLISTS
# =====================================================================


class TestBatchReleaseChecklists:
    """Test batch release checklist operations."""

    @pytest.mark.anyio
    async def test_list_checklists(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14

    @pytest.mark.anyio
    async def test_list_checklists_filter_batch(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists", params={"batch_id": "BATCH-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        for item in data["items"]:
            assert item["batch_id"] == "BATCH-001"

    @pytest.mark.anyio
    async def test_list_checklists_filter_checked(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists", params={"checked": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["checked"] is False

    @pytest.mark.anyio
    async def test_get_checklist_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CL-001"
        assert data["checked"] is True

    @pytest.mark.anyio
    async def test_get_checklist_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_checklist_item(self, client: AsyncClient):
        payload = _make_checklist_create()
        resp = await client.post(f"{API_PREFIX}/checklists", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["batch_id"] == "BATCH-002"
        assert data["checked"] is False
        assert data["id"].startswith("CL-")

    @pytest.mark.anyio
    async def test_update_checklist_item_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CL-010",
            json={"checked": True, "checked_by": "Dr. Tester"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["checked"] is True
        assert data["checked_by"] == "Dr. Tester"
        assert data["checked_date"] is not None

    @pytest.mark.anyio
    async def test_update_checklist_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CL-NONEXISTENT",
            json={"checked": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_checklist_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/checklists/CL-014")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/checklists/CL-014")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_checklist_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/checklists/CL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_checklist_add_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CL-011",
            json={"notes": "Sterility results expected next Tuesday"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Sterility results expected next Tuesday"


# =====================================================================
# MANUFACTURING METRICS
# =====================================================================


class TestManufacturingMetrics:
    """Test manufacturing metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_batches"] == 5
        assert data["total_equipment"] == 8
        assert data["total_environmental_records"] == 12
        assert data["total_validations"] == 4
        assert data["total_deviations"] == 5
        assert data["total_checklist_items"] == 14

    def test_metrics_batches_by_status(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.batches_by_status.values())
        assert total_by_status == metrics.total_batches

    def test_metrics_avg_yield(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.avg_yield_pct > 0
        assert metrics.avg_yield_pct <= 100

    def test_metrics_equipment_by_status(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        total_eq_by_status = sum(metrics.equipment_by_status.values())
        assert total_eq_by_status == metrics.total_equipment

    def test_metrics_equipment_due_requalification(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.equipment_due_for_requalification == 1  # EQ-003

    def test_metrics_environmental_excursions(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.environmental_excursions >= 2  # ENV-009 (action_required) + ENV-010 (fail)

    def test_metrics_validations_in_progress(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.validations_in_progress == 1  # PV-002

    def test_metrics_open_deviations(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.open_deviations >= 2  # DEV-003, DEV-004

    def test_metrics_deviations_by_type(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.deviations_by_type.values())
        assert total_by_type == metrics.total_deviations

    def test_metrics_checklist_completion(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.checklist_completion_pct <= 100

    def test_metrics_batches_released(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.batches_released == 1  # BATCH-001

    def test_metrics_batches_rejected(self, svc: ManufacturingOpsService):
        metrics = svc.get_metrics()
        assert metrics.batches_rejected == 0  # None rejected in seed data


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_manufacturing_ops_service()
        svc2 = get_manufacturing_ops_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_manufacturing_ops_service()
        svc2 = reset_manufacturing_ops_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_manufacturing_ops_service()
        svc.delete_batch("BATCH-001")
        assert svc.get_batch("BATCH-001") is None
        svc2 = reset_manufacturing_ops_service()
        assert svc2.get_batch("BATCH-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_batches_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_equipment_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_env_monitoring_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_validations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_deviations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_checklists_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_batch_create_with_all_fields(self, client: AsyncClient):
        payload = _make_batch_create(
            product_name="Full Batch Product",
            batch_number="FULL-001",
            lot_number="LOT-FULL-001",
            manufacturing_site="Full Test Plant",
            batch_size=5000.0,
            unit_of_measure="kg",
            master_batch_record_version="MBR-FULL-v1.0",
            yield_theoretical=5000.0,
        )
        resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_equipment_create_minimal(self, client: AsyncClient):
        payload = {
            "name": "Minimal Equipment",
            "equipment_type": "mixer",
            "serial_number": "MIN-001",
            "location": "Test Lab",
        }
        resp = await client.post(f"{API_PREFIX}/equipment", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "qualified"
        assert data["last_qualification_date"] is not None

    @pytest.mark.anyio
    async def test_env_monitoring_grade_d_pass(self, client: AsyncClient):
        payload = _make_env_monitoring_create(
            zone="grade_d",
            room_name="Test D Room",
            temperature=21.0,
            humidity=45.0,
            particle_count_05um=3000000,
            particle_count_5um=25000,
            viable_count=80,
            alert_limit=None,
            action_limit=None,
        )
        resp = await client.post(f"{API_PREFIX}/environmental-monitoring", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == "pass"

    @pytest.mark.anyio
    async def test_checklist_create_non_required(self, client: AsyncClient):
        payload = {
            "batch_id": "BATCH-002",
            "item_description": "Optional observation item",
            "required": False,
        }
        resp = await client.post(f"{API_PREFIX}/checklists", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["required"] is False

    @pytest.mark.anyio
    async def test_start_released_batch_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-001/start")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_complete_planned_batch_fails(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches/BATCH-004/complete",
            params={"yield_actual": 1000.0},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_release_planned_batch_fails(self, client: AsyncClient):
        payload = {"released_by": "Dr. Test", "reviewed_by": "Dr. Reviewer"}
        resp = await client.post(f"{API_PREFIX}/batches/BATCH-004/release", json=payload)
        assert resp.status_code == 400

    def test_deviation_create_without_batch(self, svc: ManufacturingOpsService):
        dev = svc.record_deviation(DeviationCreate(
            batch_id=None,
            deviation_type=DeviationType.MINOR,
            description="Equipment calibration deviation",
            reported_by="Operator",
        ))
        assert dev.batch_id is None
        assert dev.status == DeviationStatus.OPEN

    def test_batch_yield_calculation_on_update(self, svc: ManufacturingOpsService):
        from app.schemas.manufacturing_ops import BatchRecordUpdate
        updated = svc.update_batch("BATCH-002", BatchRecordUpdate(
            yield_actual=8000.0,
            yield_theoretical=10000.0,
        ))
        assert updated is not None
        assert updated.yield_pct == 80.0

    @pytest.mark.anyio
    async def test_multiple_checklist_items_creation(self, client: AsyncClient):
        """Create multiple checklist items for the same batch."""
        for i in range(5):
            payload = _make_checklist_create(item_description=f"Checklist item #{i + 1}")
            resp = await client.post(f"{API_PREFIX}/checklists", json=payload)
            assert resp.status_code == 201

        # Verify they all exist
        resp = await client.get(f"{API_PREFIX}/checklists", params={"batch_id": "BATCH-002"})
        data = resp.json()
        # Original 5 for BATCH-002 + 5 new ones
        assert data["total"] == 10


# =====================================================================
# BATCH RECORD DETAILS
# =====================================================================


class TestBatchRecordDetails:
    """Test detailed batch record properties."""

    @pytest.mark.anyio
    async def test_released_batch_has_all_release_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/BATCH-001")
        data = resp.json()
        assert data["status"] == "released"
        assert data["released_by"] is not None
        assert data["reviewed_by"] is not None
        assert data["release_date"] is not None
        assert data["yield_actual"] is not None
        assert data["yield_pct"] is not None

    @pytest.mark.anyio
    async def test_planned_batch_has_null_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/BATCH-004")
        data = resp.json()
        assert data["status"] == "planned"
        assert data["start_date"] is None
        assert data["end_date"] is None
        assert data["yield_actual"] is None
        assert data["released_by"] is None
        assert data["release_date"] is None

    @pytest.mark.anyio
    async def test_in_progress_batch_has_start_no_end(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/BATCH-003")
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["start_date"] is not None
        assert data["end_date"] is None

    @pytest.mark.anyio
    async def test_quarantine_batch(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/BATCH-005")
        data = resp.json()
        assert data["status"] == "quarantine"
        assert data["yield_pct"] == 80.0


# =====================================================================
# EQUIPMENT DETAILS
# =====================================================================


class TestEquipmentDetails:
    """Test equipment record details."""

    @pytest.mark.anyio
    async def test_qualified_equipment_has_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment/EQ-001")
        data = resp.json()
        assert data["status"] == "qualified"
        assert data["last_qualification_date"] is not None
        assert data["next_qualification_date"] is not None
        assert data["calibration_due_date"] is not None

    @pytest.mark.anyio
    async def test_out_of_service_equipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment/EQ-007")
        data = resp.json()
        assert data["status"] == "out_of_service"
        assert data["next_qualification_date"] is None

    @pytest.mark.anyio
    async def test_due_for_requalification_equipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment/EQ-003")
        data = resp.json()
        assert data["status"] == "due_for_requalification"


# =====================================================================
# ENVIRONMENTAL MONITORING DETAILS
# =====================================================================


class TestEnvMonitoringDetails:
    """Test environmental monitoring record details."""

    @pytest.mark.anyio
    async def test_grade_a_record_has_particle_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring/ENV-001")
        data = resp.json()
        assert data["zone"] == "grade_a"
        assert data["particle_count_05um"] is not None
        assert data["particle_count_5um"] is not None
        assert data["viable_count"] is not None

    @pytest.mark.anyio
    async def test_unclassified_zone_no_particles(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring/ENV-012")
        data = resp.json()
        assert data["zone"] == "unclassified"
        assert data["particle_count_05um"] is None

    @pytest.mark.anyio
    async def test_action_required_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring/ENV-009")
        data = resp.json()
        assert data["result"] == "action_required"

    @pytest.mark.anyio
    async def test_fail_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/environmental-monitoring/ENV-010")
        data = resp.json()
        assert data["result"] == "fail"
