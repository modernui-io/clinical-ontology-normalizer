"""Tests for Inventory Reconciliation (INV-REC).

Covers:
- Seed data verification (site inventory snapshots, reconciliation audits,
  discrepancy records, lot accountability logs)
- Site inventory snapshot CRUD (create, read, update, delete, list, filter by trial/status/site)
- Reconciliation audit CRUD (create, read, update, delete, list, filter by trial/outcome/site)
- Discrepancy record CRUD (create, read, update, delete, list, filter by trial/type/severity/resolved)
- Lot accountability log CRUD (create, read, update, delete, list, filter by trial/action/site)
- Metrics computation (overall and per-trial)
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.inventory_reconciliation import (
    AccountabilityAction,
    AuditOutcome,
    DiscrepancySeverity,
    DiscrepancyType,
    InventoryStatus,
)
from app.services.inventory_reconciliation_service import (
    InventoryReconciliationService,
    get_inventory_reconciliation_service,
    reset_inventory_reconciliation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/inventory-reconciliation"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_inventory_reconciliation_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> InventoryReconciliationService:
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


def _make_snapshot_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "site_name": "Test Clinical Center",
        "product_name": "Test Product 10mg",
        "lot_number": "LOT-TEST-001",
        "snapshot_date": "2026-01-15T09:00:00Z",
        "recorded_by": "Test Pharmacist",
        "total_received": 50,
    }
    defaults.update(overrides)
    return defaults


def _make_audit_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "snapshot_id": "SIS-001",
        "audit_date": "2026-01-16T10:00:00Z",
        "auditor_name": "Dr. Test Auditor",
        "auditor_role": "Clinical Monitor",
        "units_counted": 48,
        "units_expected": 48,
    }
    defaults.update(overrides)
    return defaults


def _make_discrepancy_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "discrepancy_type": "quantity_mismatch",
        "description": "Test discrepancy for unit testing",
        "reported_by": "Test Reporter",
        "quantity_affected": 2,
        "discrepancy_severity": "minor",
    }
    defaults.update(overrides)
    return defaults


def _make_log_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "lot_number": "LOT-TEST-001",
        "product_name": "Test Product 10mg",
        "accountability_action": "received",
        "action_date": "2026-01-10T08:00:00Z",
        "quantity": 50,
        "performed_by": "Test Pharmacist",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_site_inventory_snapshots(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_reconciliation_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-audits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_discrepancy_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_lot_accountability_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lot-accountability-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# SITE INVENTORY SNAPSHOTS CRUD
# ===================================================================


class TestSiteInventorySnapshotCRUD:
    @pytest.mark.anyio
    async def test_list_snapshots(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_snapshot(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots/SIS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIS-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_snapshot_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_snapshot(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/site-inventory-snapshots", json=_make_snapshot_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SIS-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["product_name"] == "Test Product 10mg"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/site-inventory-snapshots")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/site-inventory-snapshots", json=_make_snapshot_create())
        resp2 = await client.get(f"{API_PREFIX}/site-inventory-snapshots")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_snapshot(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-inventory-snapshots/SIS-001",
            json={"inventory_status": "closed", "notes": "Final reconciliation done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inventory_status"] == "closed"
        assert data["notes"] == "Final reconciliation done"

    @pytest.mark.anyio
    async def test_update_snapshot_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-inventory-snapshots/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_snapshot(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-inventory-snapshots/SIS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-inventory-snapshots/SIS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_snapshot_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-inventory-snapshots/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-inventory-snapshots", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_inventory_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-inventory-snapshots",
            params={"inventory_status": "reconciled"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["inventory_status"] == "reconciled"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-inventory-snapshots",
            params={"site_id": "SITE-NY-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# RECONCILIATION AUDITS CRUD
# ===================================================================


class TestReconciliationAuditCRUD:
    @pytest.mark.anyio
    async def test_list_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-audits")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-audits/RAD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RAD-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_audit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-audits/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_audit(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/reconciliation-audits", json=_make_audit_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RAD-")
        assert data["auditor_name"] == "Dr. Test Auditor"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/reconciliation-audits")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/reconciliation-audits", json=_make_audit_create())
        resp2 = await client.get(f"{API_PREFIX}/reconciliation-audits")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_audit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliation-audits/RAD-001",
            json={"audit_outcome": "pass", "notes": "Verified all counts"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audit_outcome"] == "pass"
        assert data["notes"] == "Verified all counts"

    @pytest.mark.anyio
    async def test_update_audit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliation-audits/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_audit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliation-audits/RAD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reconciliation-audits/RAD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_audit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliation-audits/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliation-audits", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_audit_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliation-audits", params={"audit_outcome": "pass"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["audit_outcome"] == "pass"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliation-audits", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# DISCREPANCY RECORDS CRUD
# ===================================================================


class TestDiscrepancyRecordCRUD:
    @pytest.mark.anyio
    async def test_list_discrepancies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_discrepancy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records/DIS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DIS-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_discrepancy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_discrepancy(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/discrepancy-records", json=_make_discrepancy_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DIS-")
        assert data["discrepancy_type"] == "quantity_mismatch"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/discrepancy-records")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/discrepancy-records", json=_make_discrepancy_create())
        resp2 = await client.get(f"{API_PREFIX}/discrepancy-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_discrepancy(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/discrepancy-records/DIS-001",
            json={"root_cause": "Documentation error", "notes": "Resolved after review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause"] == "Documentation error"
        assert data["notes"] == "Resolved after review"

    @pytest.mark.anyio
    async def test_update_discrepancy_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/discrepancy-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_discrepancy(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/discrepancy-records/DIS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/discrepancy-records/DIS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_discrepancy_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/discrepancy-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancy-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_discrepancy_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancy-records",
            params={"discrepancy_type": "quantity_mismatch"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["discrepancy_type"] == "quantity_mismatch"

    @pytest.mark.anyio
    async def test_filter_by_discrepancy_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancy-records",
            params={"discrepancy_severity": "critical"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["discrepancy_severity"] == "critical"

    @pytest.mark.anyio
    async def test_filter_by_resolved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancy-records", params={"resolved": True}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["resolved"] is True


# ===================================================================
# LOT ACCOUNTABILITY LOGS CRUD
# ===================================================================


class TestLotAccountabilityLogCRUD:
    @pytest.mark.anyio
    async def test_list_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lot-accountability-logs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lot-accountability-logs/LAL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LAL-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_log_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lot-accountability-logs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_log(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/lot-accountability-logs", json=_make_log_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("LAL-")
        assert data["accountability_action"] == "received"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/lot-accountability-logs")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/lot-accountability-logs", json=_make_log_create())
        resp2 = await client.get(f"{API_PREFIX}/lot-accountability-logs")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_log(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lot-accountability-logs/LAL-001",
            json={"witnessed_by": "New Witness", "notes": "Updated witness info"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["witnessed_by"] == "New Witness"
        assert data["notes"] == "Updated witness info"

    @pytest.mark.anyio
    async def test_update_log_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lot-accountability-logs/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_log(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lot-accountability-logs/LAL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/lot-accountability-logs/LAL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_log_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lot-accountability-logs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lot-accountability-logs", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_accountability_action(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lot-accountability-logs",
            params={"accountability_action": "received"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["accountability_action"] == "received"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lot-accountability-logs",
            params={"site_id": "SITE-HOU-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-HOU-001"


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_snapshots" in data
        assert "total_audits" in data
        assert "total_discrepancies" in data
        assert "total_accountability_logs" in data
        assert "reconciliation_rate" in data
        assert "audit_pass_rate" in data
        assert "discrepancy_resolution_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_snapshots(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_snapshots"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_audits"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_discrepancies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_discrepancies"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_accountability_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_accountability_logs"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["snapshots_by_status"], dict)
        assert isinstance(data["audits_by_outcome"], dict)
        assert isinstance(data["discrepancies_by_type"], dict)
        assert isinstance(data["discrepancies_by_severity"], dict)
        assert isinstance(data["logs_by_action"], dict)

    @pytest.mark.anyio
    async def test_metrics_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        # EYLEA has 4 snapshots (SIS-001..SIS-004)
        assert data["total_snapshots"] == 4

    def test_metrics_service_level(self, svc: InventoryReconciliationService):
        metrics = svc.get_metrics()
        assert metrics.total_snapshots == 12
        assert metrics.total_audits == 12
        assert metrics.total_discrepancies == 12
        assert metrics.total_accountability_logs == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_snapshot_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots/SIS-001")
        original = resp.json()
        original_product = original["product_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/site-inventory-snapshots/SIS-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["product_name"] == original_product
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_audit_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-audits/RAD-001")
        original = resp.json()
        original_auditor = original["auditor_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/reconciliation-audits/RAD-001",
            json={"notes": "Updated audit note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["auditor_name"] == original_auditor

    @pytest.mark.anyio
    async def test_update_discrepancy_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records/DIS-001")
        original = resp.json()
        original_type = original["discrepancy_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/discrepancy-records/DIS-001",
            json={"notes": "Updated discrepancy note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["discrepancy_type"] == original_type

    @pytest.mark.anyio
    async def test_update_log_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lot-accountability-logs/LAL-001")
        original = resp.json()
        original_action = original["accountability_action"]

        resp2 = await client.put(
            f"{API_PREFIX}/lot-accountability-logs/LAL-001",
            json={"notes": "Updated log note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["accountability_action"] == original_action


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_inventory_reconciliation_service()
        svc2 = get_inventory_reconciliation_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_inventory_reconciliation_service()
        svc2 = reset_inventory_reconciliation_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_inventory_reconciliation_service()
        svc.delete_site_inventory_snapshot("SIS-001")
        assert svc.get_site_inventory_snapshot("SIS-001") is None
        svc2 = reset_inventory_reconciliation_service()
        assert svc2.get_site_inventory_snapshot("SIS-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_snapshots_service(self, svc: InventoryReconciliationService):
        items = svc.list_site_inventory_snapshots()
        assert len(items) == 12

    def test_get_snapshot_service(self, svc: InventoryReconciliationService):
        record = svc.get_site_inventory_snapshot("SIS-001")
        assert record is not None
        assert record.id == "SIS-001"

    def test_list_audits_service(self, svc: InventoryReconciliationService):
        items = svc.list_reconciliation_audits()
        assert len(items) == 12

    def test_get_audit_service(self, svc: InventoryReconciliationService):
        record = svc.get_reconciliation_audit("RAD-001")
        assert record is not None
        assert record.id == "RAD-001"

    def test_list_discrepancies_service(self, svc: InventoryReconciliationService):
        items = svc.list_discrepancy_records()
        assert len(items) == 12

    def test_get_discrepancy_service(self, svc: InventoryReconciliationService):
        record = svc.get_discrepancy_record("DIS-001")
        assert record is not None
        assert record.id == "DIS-001"

    def test_list_logs_service(self, svc: InventoryReconciliationService):
        items = svc.list_lot_accountability_logs()
        assert len(items) == 12

    def test_get_log_service(self, svc: InventoryReconciliationService):
        record = svc.get_lot_accountability_log("LAL-001")
        assert record is not None
        assert record.id == "LAL-001"

    def test_delete_snapshot_service(self, svc: InventoryReconciliationService):
        assert svc.delete_site_inventory_snapshot("SIS-001") is True
        assert svc.get_site_inventory_snapshot("SIS-001") is None

    def test_delete_nonexistent_returns_false(self, svc: InventoryReconciliationService):
        assert svc.delete_site_inventory_snapshot("NONEXISTENT") is False

    def test_filter_snapshot_by_trial(self, svc: InventoryReconciliationService):
        items = svc.list_site_inventory_snapshots(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_snapshot_by_status(self, svc: InventoryReconciliationService):
        items = svc.list_site_inventory_snapshots(inventory_status=InventoryStatus.RECONCILED)
        for item in items:
            assert item.inventory_status == InventoryStatus.RECONCILED

    def test_filter_audit_by_outcome(self, svc: InventoryReconciliationService):
        items = svc.list_reconciliation_audits(audit_outcome=AuditOutcome.PASS)
        for item in items:
            assert item.audit_outcome == AuditOutcome.PASS

    def test_filter_discrepancy_by_type(self, svc: InventoryReconciliationService):
        items = svc.list_discrepancy_records(discrepancy_type=DiscrepancyType.QUANTITY_MISMATCH)
        for item in items:
            assert item.discrepancy_type == DiscrepancyType.QUANTITY_MISMATCH

    def test_filter_discrepancy_by_severity(self, svc: InventoryReconciliationService):
        items = svc.list_discrepancy_records(discrepancy_severity=DiscrepancySeverity.CRITICAL)
        for item in items:
            assert item.discrepancy_severity == DiscrepancySeverity.CRITICAL

    def test_filter_discrepancy_by_resolved(self, svc: InventoryReconciliationService):
        items = svc.list_discrepancy_records(resolved=True)
        for item in items:
            assert item.resolved is True

    def test_filter_log_by_action(self, svc: InventoryReconciliationService):
        items = svc.list_lot_accountability_logs(
            accountability_action=AccountabilityAction.RECEIVED
        )
        for item in items:
            assert item.accountability_action == AccountabilityAction.RECEIVED


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_snapshots(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/site-inventory-snapshots",
                json=_make_snapshot_create(site_name=f"Bulk Site {i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_discrepancies(self, client: AsyncClient):
        for dis_id in ["DIS-001", "DIS-002", "DIS-003"]:
            resp = await client.delete(f"{API_PREFIX}/discrepancy-records/{dis_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/discrepancy-records")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_snapshot_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots/SIS-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "site_name", "snapshot_date",
            "inventory_status", "product_name", "lot_number", "total_received",
            "current_on_hand", "expected_on_hand", "recorded_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_audit_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-audits/RAD-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "snapshot_id", "audit_date",
            "audit_outcome", "auditor_name", "auditor_role", "units_counted",
            "units_expected", "variance", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_discrepancy_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records/DIS-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "discrepancy_type",
            "discrepancy_severity", "description", "quantity_affected",
            "resolved", "reported_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_log_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lot-accountability-logs/LAL-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "lot_number", "product_name",
            "accountability_action", "action_date", "quantity",
            "performed_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-inventory-snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
