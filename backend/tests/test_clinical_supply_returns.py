"""Tests for Clinical Supply Returns Management (SUPPLY-RET).

Covers:
- Seed data verification (returns, destructions, excursions, quarantines, accountabilities)
- Supply Return CRUD (create, read, update, delete, list, filter by trial/status/reason)
- Destruction Record CRUD (create, read, delete, list, filter by trial/method)
- Temperature Excursion CRUD (create, read, update, delete, list, filter by trial/severity)
- Quarantine Record CRUD (create, read, update, delete, list, filter by trial/released)
- Drug Accountability CRUD (create, read, update, delete, list, filter by trial/result)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.clinical_supply_returns_service import (
    ClinicalSupplyReturnsService,
    get_clinical_supply_returns_service,
    reset_clinical_supply_returns_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-supply-returns"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_supply_returns_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalSupplyReturnsService:
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


def _make_return_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "product_name": "Test Product",
        "lot_number": "LOT-TEST-001",
        "quantity_returned": 10,
        "unit": "vials",
        "return_reason": "study_completion",
        "initiated_by": "Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_destruction_create(**overrides) -> dict:
    defaults = {
        "return_id": "RET-001",
        "trial_id": EYLEA_TRIAL,
        "product_name": "EYLEA HD 8mg",
        "lot_number": "EYL-TEST-001",
        "quantity_destroyed": 10,
        "destruction_method": "incineration",
        "destruction_facility": "Test Facility",
        "witnessed_by": "Dr. Test Witness",
        "approved_by": "Dr. Test Approver",
    }
    defaults.update(overrides)
    return defaults


def _make_excursion_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "product_name": "Test Product",
        "lot_number": "LOT-TEST-001",
        "excursion_start": (now - timedelta(hours=4)).isoformat(),
        "min_temp": 2.0,
        "max_temp": 15.0,
        "required_range_min": 2.0,
        "required_range_max": 8.0,
        "duration_minutes": 120,
        "severity": "moderate",
        "reported_by": "Test Reporter",
    }
    defaults.update(overrides)
    return defaults


def _make_quarantine_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "product_name": "Test Product",
        "lot_number": "LOT-TEST-001",
        "quantity": 5,
        "reason": "pending_inspection",
        "location": "Building A - Room 1",
    }
    defaults.update(overrides)
    return defaults


def _make_accountability_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "product_name": "Test Product",
        "lot_number": "LOT-TEST-001",
        "quantity_received": 100,
        "quantity_dispensed": 40,
        "quantity_returned": 10,
        "quantity_destroyed_at_site": 0,
        "quantity_returned_to_sponsor": 10,
        "quantity_remaining": 40,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_returns_count(self, svc: ClinicalSupplyReturnsService):
        returns = svc.list_returns()
        assert len(returns) == 12

    def test_seed_returns_all_trials(self, svc: ClinicalSupplyReturnsService):
        trials = {r.trial_id for r in svc.list_returns()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_destructions_count(self, svc: ClinicalSupplyReturnsService):
        destructions = svc.list_destructions()
        assert len(destructions) == 5

    def test_seed_excursions_count(self, svc: ClinicalSupplyReturnsService):
        excursions = svc.list_excursions()
        assert len(excursions) == 5

    def test_seed_quarantines_count(self, svc: ClinicalSupplyReturnsService):
        quarantines = svc.list_quarantines()
        assert len(quarantines) == 5

    def test_seed_accountabilities_count(self, svc: ClinicalSupplyReturnsService):
        accountabilities = svc.list_accountabilities()
        assert len(accountabilities) == 6

    def test_seed_returns_multiple_statuses(self, svc: ClinicalSupplyReturnsService):
        statuses = {r.status.value for r in svc.list_returns()}
        assert "destroyed" in statuses
        assert "initiated" in statuses
        assert "shipped" in statuses

    def test_seed_returns_multiple_reasons(self, svc: ClinicalSupplyReturnsService):
        reasons = {r.return_reason.value for r in svc.list_returns()}
        assert "study_completion" in reasons
        assert "expired" in reasons
        assert "temperature_excursion" in reasons

    def test_seed_excursions_multiple_severities(self, svc: ClinicalSupplyReturnsService):
        severities = {e.severity.value for e in svc.list_excursions()}
        assert "minor" in severities
        assert "moderate" in severities
        assert "critical" in severities

    def test_seed_accountabilities_multiple_results(self, svc: ClinicalSupplyReturnsService):
        results = {a.result.value for a in svc.list_accountabilities()}
        assert "reconciled" in results
        assert "minor_discrepancy" in results
        assert "major_discrepancy" in results
        assert "pending" in results


# =====================================================================
# SUPPLY RETURN CRUD
# =====================================================================


class TestSupplyReturnCrud:
    """Test supply return create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_returns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_returns_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_returns_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns", params={"status": "destroyed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "destroyed"

    @pytest.mark.anyio
    async def test_list_returns_filter_reason(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns", params={"return_reason": "study_completion"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["return_reason"] == "study_completion"

    @pytest.mark.anyio
    async def test_get_return(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns/RET-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RET-001"
        assert data["product_name"] == "EYLEA HD 8mg"

    @pytest.mark.anyio
    async def test_get_return_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns/RET-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_return(self, client: AsyncClient):
        payload = _make_return_create()
        resp = await client.post(f"{API_PREFIX}/returns", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Test Product"
        assert data["status"] == "initiated"
        assert data["id"].startswith("RET-")

    @pytest.mark.anyio
    async def test_update_return(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/returns/RET-004",
            json={"status": "inspected", "condition_on_receipt": "All seals intact"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "inspected"
        assert data["condition_on_receipt"] == "All seals intact"

    @pytest.mark.anyio
    async def test_update_return_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/returns/RET-NONEXISTENT",
            json={"status": "received"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_return(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/returns/RET-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/returns/RET-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_return_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/returns/RET-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DESTRUCTION RECORD CRUD
# =====================================================================


class TestDestructionRecordCrud:
    """Test destruction record create, read, delete operations."""

    @pytest.mark.anyio
    async def test_list_destructions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_destructions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_destructions_filter_method(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions", params={"destruction_method": "incineration"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["destruction_method"] == "incineration"

    @pytest.mark.anyio
    async def test_get_destruction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions/DES-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DES-001"
        assert data["quantity_destroyed"] == 24

    @pytest.mark.anyio
    async def test_get_destruction_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions/DES-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_destruction(self, client: AsyncClient):
        payload = _make_destruction_create()
        resp = await client.post(f"{API_PREFIX}/destructions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["destruction_method"] == "incineration"
        assert data["id"].startswith("DES-")

    @pytest.mark.anyio
    async def test_delete_destruction(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/destructions/DES-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/destructions/DES-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_destruction_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/destructions/DES-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TEMPERATURE EXCURSION CRUD
# =====================================================================


class TestTemperatureExcursionCrud:
    """Test temperature excursion create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_excursions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_excursions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_excursions_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_get_excursion(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EXC-001"
        assert data["severity"] == "moderate"

    @pytest.mark.anyio
    async def test_get_excursion_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_excursion(self, client: AsyncClient):
        payload = _make_excursion_create()
        resp = await client.post(f"{API_PREFIX}/excursions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "moderate"
        assert data["id"].startswith("EXC-")

    @pytest.mark.anyio
    async def test_update_excursion(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/excursions/EXC-005",
            json={"product_disposition": "Destroyed", "assessed_by": "Dr. Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_disposition"] == "Destroyed"
        assert data["assessed_by"] == "Dr. Test"

    @pytest.mark.anyio
    async def test_update_excursion_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/excursions/EXC-NONEXISTENT",
            json={"severity": "critical"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_excursion(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/excursions/EXC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/excursions/EXC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_excursion_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/excursions/EXC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# QUARANTINE RECORD CRUD
# =====================================================================


class TestQuarantineRecordCrud:
    """Test quarantine record create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_quarantines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_quarantines_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_quarantines_filter_released(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines", params={"released": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["released"] is False

    @pytest.mark.anyio
    async def test_get_quarantine(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines/QUA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "QUA-001"
        assert data["reason"] == "temperature_excursion"

    @pytest.mark.anyio
    async def test_get_quarantine_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines/QUA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_quarantine(self, client: AsyncClient):
        payload = _make_quarantine_create()
        resp = await client.post(f"{API_PREFIX}/quarantines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reason"] == "pending_inspection"
        assert data["released"] is False
        assert data["id"].startswith("QUA-")

    @pytest.mark.anyio
    async def test_update_quarantine(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/quarantines/QUA-001",
            json={"released": True, "released_by": "Dr. Test", "disposition": "Released for use"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["released"] is True
        assert data["released_by"] == "Dr. Test"
        assert data["disposition"] == "Released for use"
        assert data["release_date"] is not None

    @pytest.mark.anyio
    async def test_update_quarantine_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/quarantines/QUA-NONEXISTENT",
            json={"released": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_quarantine(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/quarantines/QUA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/quarantines/QUA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_quarantine_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/quarantines/QUA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DRUG ACCOUNTABILITY CRUD
# =====================================================================


class TestDrugAccountabilityCrud:
    """Test drug accountability create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_accountabilities(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_accountabilities_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_accountabilities_filter_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities", params={"result": "reconciled"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["result"] == "reconciled"

    @pytest.mark.anyio
    async def test_get_accountability(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities/ACC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACC-001"
        assert data["result"] == "reconciled"

    @pytest.mark.anyio
    async def test_get_accountability_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities/ACC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_accountability(self, client: AsyncClient):
        payload = _make_accountability_create()
        resp = await client.post(f"{API_PREFIX}/accountabilities", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == "pending"
        assert data["id"].startswith("ACC-")

    @pytest.mark.anyio
    async def test_update_accountability(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accountabilities/ACC-006",
            json={"result": "reconciled", "reconciled_by": "Dr. Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "reconciled"
        assert data["reconciled_by"] == "Dr. Test"
        assert data["reconciled_date"] is not None

    @pytest.mark.anyio
    async def test_update_accountability_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accountabilities/ACC-NONEXISTENT",
            json={"result": "reconciled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_accountability(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accountabilities/ACC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/accountabilities/ACC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_accountability_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accountabilities/ACC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestSupplyReturnsMetrics:
    """Test supply returns metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returns"] == 12
        assert data["total_destructions"] == 5
        assert data["total_excursions"] == 5
        assert data["total_quarantined"] == 5
        assert data["total_accountability_records"] == 6
        assert data["total_units_returned"] > 0
        assert data["total_units_destroyed"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returns"] == 4

    def test_metrics_returns_by_status(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.returns_by_status.values())
        assert total_by_status == metrics.total_returns

    def test_metrics_returns_by_reason(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        total_by_reason = sum(metrics.returns_by_reason.values())
        assert total_by_reason == metrics.total_returns

    def test_metrics_destructions_by_method(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        total_by_method = sum(metrics.destructions_by_method.values())
        assert total_by_method == metrics.total_destructions

    def test_metrics_excursions_by_severity(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        total_by_severity = sum(metrics.excursions_by_severity.values())
        assert total_by_severity == metrics.total_excursions

    def test_metrics_currently_quarantined(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        # 3 not released in seed data (QUA-001, QUA-003, QUA-005)
        assert metrics.currently_quarantined == 3

    def test_metrics_reconciled_records(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        # ACC-001, ACC-002, ACC-003 are reconciled
        assert metrics.reconciled_records == 3

    def test_metrics_discrepancy_records(self, svc: ClinicalSupplyReturnsService):
        metrics = svc.get_metrics()
        # ACC-004 minor, ACC-005 major
        assert metrics.discrepancy_records == 2

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returns"] == 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_supply_returns_service()
        svc2 = get_clinical_supply_returns_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_supply_returns_service()
        svc2 = reset_clinical_supply_returns_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_supply_returns_service()
        svc.delete_return("RET-001")
        assert svc.get_return("RET-001") is None
        svc2 = reset_clinical_supply_returns_service()
        assert svc2.get_return("RET-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_returns_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_destructions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_excursions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_quarantines_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_accountabilities_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_return_all_reasons(self, client: AsyncClient):
        for reason in [
            "study_completion", "patient_withdrawal", "expired", "damaged",
            "temperature_excursion", "protocol_amendment", "site_closure",
            "recall", "excess_inventory",
        ]:
            payload = _make_return_create(return_reason=reason, lot_number=f"LOT-{reason}")
            resp = await client.post(f"{API_PREFIX}/returns", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["return_reason"] == reason

    @pytest.mark.anyio
    async def test_create_destruction_all_methods(self, client: AsyncClient):
        for method in ["incineration", "chemical", "autoclaving", "landfill", "return_to_manufacturer"]:
            payload = _make_destruction_create(destruction_method=method, lot_number=f"LOT-{method}")
            resp = await client.post(f"{API_PREFIX}/destructions", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["destruction_method"] == method

    @pytest.mark.anyio
    async def test_create_excursion_all_severities(self, client: AsyncClient):
        for sev in ["minor", "moderate", "major", "critical"]:
            payload = _make_excursion_create(severity=sev, lot_number=f"LOT-{sev}")
            resp = await client.post(f"{API_PREFIX}/excursions", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["severity"] == sev

    @pytest.mark.anyio
    async def test_create_quarantine_all_reasons(self, client: AsyncClient):
        for reason in [
            "temperature_excursion", "damaged_packaging",
            "accountability_discrepancy", "pending_inspection",
            "recall_hold", "suspected_counterfeit",
        ]:
            payload = _make_quarantine_create(reason=reason, lot_number=f"LOT-{reason}")
            resp = await client.post(f"{API_PREFIX}/quarantines", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["reason"] == reason

    @pytest.mark.anyio
    async def test_return_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/returns/RET-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "site_id" in data
        assert "product_name" in data
        assert "lot_number" in data
        assert "quantity_returned" in data
        assert "unit" in data
        assert "return_reason" in data
        assert "status" in data
        assert "initiated_date" in data
        assert "initiated_by" in data

    @pytest.mark.anyio
    async def test_destruction_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destructions/DES-001")
        data = resp.json()
        assert "id" in data
        assert "return_id" in data
        assert "trial_id" in data
        assert "destruction_method" in data
        assert "destruction_facility" in data
        assert "witnessed_by" in data
        assert "approved_by" in data

    @pytest.mark.anyio
    async def test_excursion_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "min_temp" in data
        assert "max_temp" in data
        assert "required_range_min" in data
        assert "required_range_max" in data
        assert "duration_minutes" in data
        assert "severity" in data

    @pytest.mark.anyio
    async def test_quarantine_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/quarantines/QUA-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "reason" in data
        assert "location" in data
        assert "released" in data
        assert "quantity" in data

    @pytest.mark.anyio
    async def test_accountability_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountabilities/ACC-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "quantity_received" in data
        assert "quantity_dispensed" in data
        assert "quantity_returned" in data
        assert "quantity_remaining" in data
        assert "result" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_returns" in data
        assert "returns_by_status" in data
        assert "returns_by_reason" in data
        assert "total_units_returned" in data
        assert "total_destructions" in data
        assert "total_units_destroyed" in data
        assert "destructions_by_method" in data
        assert "total_excursions" in data
        assert "excursions_by_severity" in data
        assert "total_quarantined" in data
        assert "currently_quarantined" in data
        assert "total_accountability_records" in data
        assert "reconciled_records" in data
        assert "discrepancy_records" in data

    def test_eylea_returns_count(self, svc: ClinicalSupplyReturnsService):
        returns = svc.list_returns(trial_id=EYLEA_TRIAL)
        assert len(returns) == 4

    def test_dupixent_returns_count(self, svc: ClinicalSupplyReturnsService):
        returns = svc.list_returns(trial_id=DUPIXENT_TRIAL)
        assert len(returns) == 4

    def test_libtayo_returns_count(self, svc: ClinicalSupplyReturnsService):
        returns = svc.list_returns(trial_id=LIBTAYO_TRIAL)
        assert len(returns) == 4
