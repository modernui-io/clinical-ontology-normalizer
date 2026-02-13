"""Tests for Specimen Management (SPEC-MGT).

Covers:
- Seed data verification (collection records, storage inventory, chain of custody,
  shipping logistics, specimen QC)
- Collection record CRUD (create, read, update, delete, list, filter by trial/type/status)
- Storage inventory CRUD (create, read, update, delete, list, filter by trial/condition/available)
- Chain of custody CRUD (create, read, update, delete, list, filter by trial/specimen)
- Shipping logistics CRUD (create, read, update, delete, list, filter by trial/status)
- Specimen QC CRUD (create, read, update, delete, list, filter by trial/specimen/result)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.specimen_management import (
    CollectionStatus,
    QCResult,
    ShippingStatus,
    SpecimenType,
    StorageCondition,
)
from app.services.specimen_management_service import (
    SpecimenManagementService,
    get_specimen_management_service,
    reset_specimen_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/specimen-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_specimen_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SpecimenManagementService:
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


def _make_collection_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "specimen_type": "blood",
        "protocol_timepoint": "Screening",
        "scheduled_date": "2026-01-15T09:00:00Z",
        "tube_count": 3,
        "volume_ml": 15.0,
    }
    defaults.update(overrides)
    return defaults


def _make_storage_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "specimen_id": "COL-001",
        "storage_condition": "frozen_minus_80",
        "freezer_id": "FRZ-TEST-001",
        "rack_position": "R99",
        "box_number": "B999",
        "slot_number": "Z1",
        "managed_by": "Test Technician",
        "volume_remaining_ml": 5.0,
    }
    defaults.update(overrides)
    return defaults


def _make_custody_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "specimen_id": "COL-001",
        "custody_event": "collection_to_lab",
        "from_location": "Collection Room A",
        "to_location": "Central Lab",
        "from_person": "Nurse A",
        "to_person": "Lab Tech B",
        "recorded_by": "Test Admin",
    }
    defaults.update(overrides)
    return defaults


def _make_shipping_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "shipment_number": "TEST-SHP-001",
        "origin_site": "SITE-TEST-001",
        "destination_site": "Central Lab",
        "shipping_condition": "frozen_minus_80",
        "carrier_name": "FedEx Clinical",
        "prepared_by": "Test Technician",
        "specimen_count": 5,
    }
    defaults.update(overrides)
    return defaults


def _make_qc_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "specimen_id": "COL-001",
        "test_performed": "Hemolysis Index",
        "performed_by": "QC Analyst",
        "qc_result": "pass",
        "volume_adequate": True,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 5 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_collection_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_storage_inventory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-inventory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_chain_of_custody(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/chain-of-custody")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_shipping_logistics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipping-logistics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_specimen_qc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# COLLECTION RECORDS CRUD
# ===================================================================


class TestCollectionRecordCRUD:
    @pytest.mark.anyio
    async def test_list_collection_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_collection_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records/COL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COL-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_collection_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_collection_record(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/collection-records", json=_make_collection_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("COL-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["specimen_type"] == "blood"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/collection-records")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/collection-records", json=_make_collection_create())
        resp2 = await client.get(f"{API_PREFIX}/collection-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_collection_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/collection-records/COL-001",
            json={"collection_status": "collected", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["collection_status"] == "collected"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_collection_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/collection-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_collection_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/collection-records/COL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/collection-records/COL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_collection_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/collection-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_specimen_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/collection-records", params={"specimen_type": "blood"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["specimen_type"] == "blood"

    @pytest.mark.anyio
    async def test_filter_by_collection_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/collection-records", params={"collection_status": "collected"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["collection_status"] == "collected"


# ===================================================================
# STORAGE INVENTORY CRUD
# ===================================================================


class TestStorageInventoryCRUD:
    @pytest.mark.anyio
    async def test_list_storage_inventory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-inventory")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_storage_inventory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-inventory/STR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "STR-001"

    @pytest.mark.anyio
    async def test_get_storage_inventory_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-inventory/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_storage_inventory(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/storage-inventory", json=_make_storage_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("STR-")
        assert data["storage_condition"] == "frozen_minus_80"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/storage-inventory")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/storage-inventory", json=_make_storage_create())
        resp2 = await client.get(f"{API_PREFIX}/storage-inventory")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_storage_inventory(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/storage-inventory/STR-001",
            json={"is_available": False, "notes": "Depleted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_available"] is False
        assert data["notes"] == "Depleted"

    @pytest.mark.anyio
    async def test_update_storage_inventory_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/storage-inventory/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_storage_inventory(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/storage-inventory/STR-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_storage_inventory_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/storage-inventory/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_storage_condition(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/storage-inventory",
            params={"storage_condition": "frozen_minus_80"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["storage_condition"] == "frozen_minus_80"

    @pytest.mark.anyio
    async def test_filter_by_is_available(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/storage-inventory", params={"is_available": True}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["is_available"] is True


# ===================================================================
# CHAIN OF CUSTODY CRUD
# ===================================================================


class TestChainOfCustodyCRUD:
    @pytest.mark.anyio
    async def test_list_chain_of_custody(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/chain-of-custody")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_chain_of_custody(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/chain-of-custody/COC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "COC-001"

    @pytest.mark.anyio
    async def test_get_chain_of_custody_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/chain-of-custody/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_chain_of_custody(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/chain-of-custody", json=_make_custody_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("COC-")
        assert data["custody_event"] == "collection_to_lab"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/chain-of-custody")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/chain-of-custody", json=_make_custody_create())
        resp2 = await client.get(f"{API_PREFIX}/chain-of-custody")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_chain_of_custody(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/chain-of-custody/COC-001",
            json={"condition_at_transfer": "good", "notes": "Verified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["condition_at_transfer"] == "good"
        assert data["notes"] == "Verified"

    @pytest.mark.anyio
    async def test_update_chain_of_custody_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/chain-of-custody/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_chain_of_custody(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/chain-of-custody/COC-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_chain_of_custody_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/chain-of-custody/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/chain-of-custody", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_specimen_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/chain-of-custody", params={"specimen_id": "COL-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["specimen_id"] == "COL-001"


# ===================================================================
# SHIPPING LOGISTICS CRUD
# ===================================================================


class TestShippingLogisticsCRUD:
    @pytest.mark.anyio
    async def test_list_shipping_logistics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipping-logistics")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_shipping_logistic(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipping-logistics/SHP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SHP-001"

    @pytest.mark.anyio
    async def test_get_shipping_logistic_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipping-logistics/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_shipping_logistic(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipping-logistics", json=_make_shipping_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SHP-")
        assert data["carrier_name"] == "FedEx Clinical"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/shipping-logistics")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/shipping-logistics", json=_make_shipping_create())
        resp2 = await client.get(f"{API_PREFIX}/shipping-logistics")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_shipping_logistic(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipping-logistics/SHP-001",
            json={"shipping_status": "delivered", "notes": "Arrived on time"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["shipping_status"] == "delivered"
        assert data["notes"] == "Arrived on time"

    @pytest.mark.anyio
    async def test_update_shipping_logistic_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipping-logistics/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipping_logistic(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipping-logistics/SHP-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_shipping_logistic_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipping-logistics/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_shipping_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/shipping-logistics", params={"shipping_status": "delivered"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["shipping_status"] == "delivered"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/shipping-logistics", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# SPECIMEN QC CRUD
# ===================================================================


class TestSpecimenQCCRUD:
    @pytest.mark.anyio
    async def test_list_specimen_qc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_specimen_qc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc/QC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "QC-001"

    @pytest.mark.anyio
    async def test_get_specimen_qc_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_specimen_qc(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/specimen-qc", json=_make_qc_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("QC-")
        assert data["test_performed"] == "Hemolysis Index"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/specimen-qc")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/specimen-qc", json=_make_qc_create())
        resp2 = await client.get(f"{API_PREFIX}/specimen-qc")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_specimen_qc(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/specimen-qc/QC-001",
            json={"qc_result": "pass", "notes": "All clear"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qc_result"] == "pass"
        assert data["notes"] == "All clear"

    @pytest.mark.anyio
    async def test_update_specimen_qc_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/specimen-qc/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen_qc(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimen-qc/QC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/specimen-qc/QC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen_qc_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimen-qc/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_qc_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc", params={"qc_result": "pass"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["qc_result"] == "pass"

    @pytest.mark.anyio
    async def test_filter_by_specimen_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/specimen-qc", params={"specimen_id": "COL-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["specimen_id"] == "COL-001"


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_collections" in data
        assert "total_stored_specimens" in data
        assert "total_custody_events" in data
        assert "total_shipments" in data
        assert "total_qc_records" in data
        assert "collection_completion_rate" in data
        assert "qc_pass_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_collections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_collections"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_stored_specimens(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_stored_specimens"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_custody_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_custody_events"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_shipments"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_qc_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_qc_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["collections_by_type"], dict)
        assert isinstance(data["collections_by_status"], dict)
        assert isinstance(data["specimens_by_condition"], dict)
        assert isinstance(data["shipments_by_status"], dict)
        assert isinstance(data["qc_by_result"], dict)

    def test_metrics_service_level(self, svc: SpecimenManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_collections == 12
        assert metrics.total_stored_specimens == 12
        assert metrics.total_custody_events == 12
        assert metrics.total_shipments == 12
        assert metrics.total_qc_records == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_collection_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records/COL-001")
        original = resp.json()
        original_type = original["specimen_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/collection-records/COL-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["specimen_type"] == original_type
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_storage_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-inventory/STR-001")
        original = resp.json()
        original_condition = original["storage_condition"]

        resp2 = await client.put(
            f"{API_PREFIX}/storage-inventory/STR-001",
            json={"notes": "Updated storage note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["storage_condition"] == original_condition

    @pytest.mark.anyio
    async def test_update_custody_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/chain-of-custody/COC-001")
        original = resp.json()
        original_event = original["custody_event"]

        resp2 = await client.put(
            f"{API_PREFIX}/chain-of-custody/COC-001",
            json={"notes": "Verified transfer"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["custody_event"] == original_event

    @pytest.mark.anyio
    async def test_update_shipping_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipping-logistics/SHP-001")
        original = resp.json()
        original_carrier = original["carrier_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/shipping-logistics/SHP-001",
            json={"notes": "Updated shipping note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["carrier_name"] == original_carrier

    @pytest.mark.anyio
    async def test_update_qc_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc/QC-001")
        original = resp.json()
        original_test = original["test_performed"]

        resp2 = await client.put(
            f"{API_PREFIX}/specimen-qc/QC-001",
            json={"notes": "Updated QC note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["test_performed"] == original_test


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_specimen_management_service()
        svc2 = get_specimen_management_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_specimen_management_service()
        svc2 = reset_specimen_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_specimen_management_service()
        svc.delete_collection_record("COL-001")
        assert svc.get_collection_record("COL-001") is None
        svc2 = reset_specimen_management_service()
        assert svc2.get_collection_record("COL-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_collection_records_service(self, svc: SpecimenManagementService):
        items = svc.list_collection_records()
        assert len(items) == 12

    def test_get_collection_record_service(self, svc: SpecimenManagementService):
        record = svc.get_collection_record("COL-001")
        assert record is not None
        assert record.id == "COL-001"

    def test_list_storage_inventory_service(self, svc: SpecimenManagementService):
        items = svc.list_storage_inventory()
        assert len(items) == 12

    def test_get_storage_inventory_service(self, svc: SpecimenManagementService):
        record = svc.get_storage_inventory("STR-001")
        assert record is not None
        assert record.id == "STR-001"

    def test_list_chain_of_custody_service(self, svc: SpecimenManagementService):
        items = svc.list_chain_of_custody()
        assert len(items) == 12

    def test_get_chain_of_custody_service(self, svc: SpecimenManagementService):
        record = svc.get_chain_of_custody("COC-001")
        assert record is not None
        assert record.id == "COC-001"

    def test_list_shipping_logistics_service(self, svc: SpecimenManagementService):
        items = svc.list_shipping_logistics()
        assert len(items) == 12

    def test_get_shipping_logistic_service(self, svc: SpecimenManagementService):
        record = svc.get_shipping_logistic("SHP-001")
        assert record is not None
        assert record.id == "SHP-001"

    def test_list_specimen_qc_service(self, svc: SpecimenManagementService):
        items = svc.list_specimen_qc()
        assert len(items) == 12

    def test_get_specimen_qc_service(self, svc: SpecimenManagementService):
        record = svc.get_specimen_qc("QC-001")
        assert record is not None
        assert record.id == "QC-001"

    def test_delete_collection_record_service(self, svc: SpecimenManagementService):
        assert svc.delete_collection_record("COL-001") is True
        assert svc.get_collection_record("COL-001") is None

    def test_delete_nonexistent_returns_false(self, svc: SpecimenManagementService):
        assert svc.delete_collection_record("NONEXISTENT") is False

    def test_filter_collection_by_trial(self, svc: SpecimenManagementService):
        items = svc.list_collection_records(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_storage_by_condition(self, svc: SpecimenManagementService):
        items = svc.list_storage_inventory(storage_condition=StorageCondition.FROZEN_MINUS_80)
        for item in items:
            assert item.storage_condition == StorageCondition.FROZEN_MINUS_80

    def test_filter_shipping_by_status(self, svc: SpecimenManagementService):
        items = svc.list_shipping_logistics(shipping_status=ShippingStatus.DELIVERED)
        for item in items:
            assert item.shipping_status == ShippingStatus.DELIVERED

    def test_filter_qc_by_result(self, svc: SpecimenManagementService):
        items = svc.list_specimen_qc(qc_result=QCResult.PASS)
        for item in items:
            assert item.qc_result == QCResult.PASS


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_collection_records(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/collection-records",
                json=_make_collection_create(subject_id=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/collection-records")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_qc_records(self, client: AsyncClient):
        for qc_id in ["QC-001", "QC-002", "QC-003"]:
            resp = await client.delete(f"{API_PREFIX}/specimen-qc/{qc_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/specimen-qc")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_collection_record_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records/COL-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "subject_id", "site_id", "specimen_type",
                       "collection_status", "protocol_timepoint", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_storage_inventory_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-inventory/STR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "specimen_id", "storage_condition",
                       "freezer_id", "rack_position", "is_available", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_chain_of_custody_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/chain-of-custody/COC-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "specimen_id", "custody_event",
                       "from_location", "to_location", "recorded_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_shipping_logistic_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipping-logistics/SHP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "shipment_number", "shipping_status",
                       "carrier_name", "origin_site", "destination_site", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_specimen_qc_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimen-qc/QC-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "specimen_id", "qc_result",
                       "test_performed", "performed_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/collection-records")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
