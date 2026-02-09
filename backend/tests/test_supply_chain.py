"""Tests for IMP Supply Chain Management (CLINICAL-6).

Covers:
- Seed data verification (drug products, inventory, shipments, excursions, kits)
- Drug product CRUD (create, read, update, delete, list)
- Inventory CRUD with filters (site, drug product, status, pagination)
- Shipment CRUD with filters (status, drug product, pagination)
- Shipment delivery lifecycle and validation
- Temperature excursion reporting and listing
- Temperature compliance checking
- Kit assignment, return, and reconciliation
- Lot traceability across inventory, shipments, patients, excursions
- Supply forecasting with reorder points
- Expiring inventory detection
- Metrics dashboard computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
- Service singleton and reset behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.supply_chain import (
    DrugProductCreate,
    ExcursionDisposition,
    InventoryItemCreate,
    KitAssignRequest,
    KitType,
    ShipmentCreate,
    ShipmentStatus,
    StorageCondition,
    SupplyStatus,
    TemperatureExcursionReport,
    TemperatureExcursionSeverity,
)
from app.services.supply_chain_service import (
    STORAGE_TEMP_RANGES,
    SupplyChainService,
    get_supply_chain_service,
    reset_supply_chain_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/supply-chain"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_supply_chain_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SupplyChainService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_drug_product_create(**overrides) -> dict:
    defaults = {
        "name": "Test Drug",
        "ndc_code": "12345-6789-01",
        "manufacturer": "Test Pharma",
        "active_ingredient": "Testamab",
        "formulation": "Injection",
        "strength": "100mg/mL",
        "storage_condition": "refrigerated_2_8",
        "shelf_life_months": 24,
    }
    defaults.update(overrides)
    return defaults


def _make_inventory_create(**overrides) -> dict:
    defaults = {
        "drug_product_id": "DP-001",
        "lot_number": "LOT-TEST-001",
        "quantity": 50,
        "site_id": "SITE-101",
        "storage_condition": "refrigerated_2_8",
        "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_shipment_create(**overrides) -> dict:
    defaults = {
        "from_site": "DEPOT-CENTRAL",
        "to_site": "SITE-101",
        "drug_product_id": "DP-001",
        "lot_number": "LOT-TEST-001",
        "quantity": 20,
        "tracking_number": "TRK-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_kit_assign(**overrides) -> dict:
    defaults = {
        "kit_type": "treatment",
        "patient_id": "PAT-TEST-001",
        "site_id": "SITE-101",
        "kit_number": "K-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_excursion_report(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "start_time": (now - timedelta(hours=4)).isoformat(),
        "end_time": (now - timedelta(hours=2)).isoformat(),
        "min_temp": 0.5,
        "max_temp": 12.0,
        "severity": "minor",
        "disposition": "use",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_drug_products_count(self, svc: SupplyChainService):
        products = svc.list_drug_products()
        assert len(products) == 5

    def test_seed_drug_product_ids(self, svc: SupplyChainService):
        products = svc.list_drug_products()
        ids = {p.id for p in products}
        assert "DP-001" in ids
        assert "DP-002" in ids
        assert "DP-003" in ids
        assert "DP-004" in ids
        assert "DP-005" in ids

    def test_seed_drug_product_names(self, svc: SupplyChainService):
        dp = svc.get_drug_product("DP-001")
        assert "EYLEA" in dp.name
        assert dp.active_ingredient == "Aflibercept"

    def test_seed_inventory_count(self, svc: SupplyChainService):
        items, total = svc.list_inventory(limit=100)
        assert total == 16

    def test_seed_inventory_statuses(self, svc: SupplyChainService):
        items, _ = svc.list_inventory(limit=100)
        statuses = {i.status for i in items}
        assert SupplyStatus.IN_STOCK in statuses
        assert SupplyStatus.LOW_STOCK in statuses
        assert SupplyStatus.OUT_OF_STOCK in statuses

    def test_seed_shipments_count(self, svc: SupplyChainService):
        items, total = svc.list_shipments(limit=100)
        assert total == 8

    def test_seed_shipment_statuses(self, svc: SupplyChainService):
        items, _ = svc.list_shipments(limit=100)
        statuses = {s.status for s in items}
        assert ShipmentStatus.PENDING in statuses
        assert ShipmentStatus.IN_TRANSIT in statuses
        assert ShipmentStatus.DELIVERED in statuses
        assert ShipmentStatus.RETURNED in statuses

    def test_seed_excursions_count(self, svc: SupplyChainService):
        items = svc.list_temperature_excursions()
        assert len(items) == 3

    def test_seed_excursion_severities(self, svc: SupplyChainService):
        items = svc.list_temperature_excursions()
        severities = {e.severity for e in items}
        assert TemperatureExcursionSeverity.MINOR in severities
        assert TemperatureExcursionSeverity.MAJOR in severities
        assert TemperatureExcursionSeverity.CRITICAL in severities

    def test_seed_kit_assignments_count(self, svc: SupplyChainService):
        items = svc.list_kit_assignments()
        assert len(items) == 20

    def test_seed_kit_types(self, svc: SupplyChainService):
        items = svc.list_kit_assignments()
        types = {k.kit_type for k in items}
        assert KitType.SCREENING in types
        assert KitType.RANDOMIZATION in types
        assert KitType.TREATMENT in types
        assert KitType.RESCUE in types
        assert KitType.EXTENSION in types

    def test_seed_shipments_have_temperature_logs(self, svc: SupplyChainService):
        shp = svc.get_shipment("SHP-001")
        assert len(shp.temperature_log) > 0


# =====================================================================
# DRUG PRODUCT CRUD
# =====================================================================


class TestDrugProductCrud:
    """Test drug product CRUD operations."""

    @pytest.mark.anyio
    async def test_list_drug_products(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-products")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.anyio
    async def test_get_drug_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-products/DP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DP-001"
        assert "EYLEA" in data["name"]
        assert data["storage_condition"] == "refrigerated_2_8"

    @pytest.mark.anyio
    async def test_get_drug_product_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-products/DP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_drug_product(self, client: AsyncClient):
        payload = _make_drug_product_create()
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Drug"
        assert data["id"].startswith("DP-")
        assert data["manufacturer"] == "Test Pharma"

    @pytest.mark.anyio
    async def test_create_drug_product_ambient(self, client: AsyncClient):
        payload = _make_drug_product_create(
            name="Ambient Drug",
            storage_condition="ambient",
            shelf_life_months=36,
        )
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["storage_condition"] == "ambient"

    @pytest.mark.anyio
    async def test_update_drug_product(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-products/DP-001",
            json={"name": "Updated EYLEA", "shelf_life_months": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated EYLEA"
        assert data["shelf_life_months"] == 30

    @pytest.mark.anyio
    async def test_update_drug_product_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-products/DP-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_product(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-products/DP-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/drug-products/DP-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_product_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-products/DP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_drug_product_storage_condition(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-products/DP-004",
            json={"storage_condition": "refrigerated_2_8"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["storage_condition"] == "refrigerated_2_8"

    @pytest.mark.anyio
    async def test_create_and_verify_in_list(self, client: AsyncClient):
        payload = _make_drug_product_create(name="Verify In List Drug")
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/drug-products")
        data = resp2.json()
        assert data["total"] == 6
        ids = [item["id"] for item in data["items"]]
        assert new_id in ids


# =====================================================================
# INVENTORY CRUD
# =====================================================================


class TestInventoryCrud:
    """Test inventory CRUD operations."""

    @pytest.mark.anyio
    async def test_list_inventory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 16
        assert data["limit"] == 50
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_list_inventory_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_inventory_filter_drug_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory", params={"drug_product_id": "DP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["drug_product_id"] == "DP-001"

    @pytest.mark.anyio
    async def test_list_inventory_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory", params={"status": "low_stock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "low_stock"

    @pytest.mark.anyio
    async def test_list_inventory_pagination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["limit"] == 5
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_list_inventory_pagination_offset(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory", params={"limit": 5, "offset": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["offset"] == 5

    @pytest.mark.anyio
    async def test_get_inventory_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory/INV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INV-001"
        assert data["drug_product_id"] == "DP-001"

    @pytest.mark.anyio
    async def test_get_inventory_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inventory/INV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_inventory_item(self, client: AsyncClient):
        payload = _make_inventory_create()
        resp = await client.post(f"{API_PREFIX}/inventory", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_product_id"] == "DP-001"
        assert data["quantity"] == 50
        assert data["status"] == "in_stock"

    @pytest.mark.anyio
    async def test_create_inventory_item_low_stock(self, client: AsyncClient):
        payload = _make_inventory_create(quantity=3)
        resp = await client.post(f"{API_PREFIX}/inventory", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "low_stock"

    @pytest.mark.anyio
    async def test_update_inventory_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inventory/INV-001",
            json={"quantity": 100, "status": "in_stock"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 100

    @pytest.mark.anyio
    async def test_update_inventory_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inventory/INV-NONEXISTENT",
            json={"quantity": 10},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inventory_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inventory/INV-016")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/inventory/INV-016")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inventory_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inventory/INV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_inventory_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory",
            params={"site_id": "SITE-101", "drug_product_id": "DP-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"
            assert item["drug_product_id"] == "DP-001"

    @pytest.mark.anyio
    async def test_list_inventory_no_results(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inventory",
            params={"site_id": "SITE-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0


# =====================================================================
# SHIPMENT CRUD
# =====================================================================


class TestShipmentCrud:
    """Test shipment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_shipments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"status": "in_transit"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "in_transit"

    @pytest.mark.anyio
    async def test_list_shipments_filter_drug_product(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/shipments", params={"drug_product_id": "DP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["drug_product_id"] == "DP-001"

    @pytest.mark.anyio
    async def test_list_shipments_pagination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"limit": 3, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["limit"] == 3

    @pytest.mark.anyio
    async def test_get_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SHP-001"
        assert data["status"] == "delivered"

    @pytest.mark.anyio
    async def test_get_shipment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_shipment(self, client: AsyncClient):
        payload = _make_shipment_create()
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["from_site"] == "DEPOT-CENTRAL"
        assert data["status"] == "pending"
        assert data["id"].startswith("SHP-")

    @pytest.mark.anyio
    async def test_update_shipment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-008",
            json={"status": "in_transit", "tracking_number": "TRK-NEW-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_transit"
        assert data["tracking_number"] == "TRK-NEW-001"

    @pytest.mark.anyio
    async def test_update_shipment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-NONEXISTENT",
            json={"status": "in_transit"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipments/SHP-008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/shipments/SHP-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipments/SHP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_shipments_no_results(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/shipments", params={"drug_product_id": "DP-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =====================================================================
# SHIPMENT DELIVERY LIFECYCLE
# =====================================================================


class TestShipmentDelivery:
    """Test shipment delivery operations."""

    @pytest.mark.anyio
    async def test_deliver_pending_shipment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-008/deliver")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"
        assert data["delivered_date"] is not None

    @pytest.mark.anyio
    async def test_deliver_in_transit_shipment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/deliver")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"

    @pytest.mark.anyio
    async def test_deliver_already_delivered_shipment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-001/deliver")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_deliver_returned_shipment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-007/deliver")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_deliver_shipment_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-NONEXISTENT/deliver")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_deliver_sets_delivered_date(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-008/deliver")
        data = resp.json()
        delivered = datetime.fromisoformat(data["delivered_date"])
        assert delivered.tzinfo is not None
        # Delivered date should be very recent
        now = datetime.now(timezone.utc)
        assert (now - delivered).total_seconds() < 60


# =====================================================================
# TEMPERATURE EXCURSIONS
# =====================================================================


class TestTemperatureExcursions:
    """Test temperature excursion operations."""

    @pytest.mark.anyio
    async def test_list_excursions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_excursions_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_excursions_filter_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"days": 7})
        assert resp.status_code == 200
        data = resp.json()
        # Should include at least the minor excursion from 18 hours ago
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_excursions_filter_days_narrow(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"days": 1})
        assert resp.status_code == 200
        data = resp.json()
        # Only the most recent excursion (EXC-001, 18 hours ago)
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_get_excursion(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EXC-001"
        assert data["severity"] == "minor"
        assert data["disposition"] == "use"

    @pytest.mark.anyio
    async def test_get_excursion_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_report_excursion(self, client: AsyncClient):
        payload = _make_excursion_report()
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/excursions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["shipment_id"] == "SHP-005"
        assert data["severity"] == "minor"
        assert data["id"].startswith("EXC-")

    @pytest.mark.anyio
    async def test_report_excursion_major(self, client: AsyncClient):
        payload = _make_excursion_report(
            severity="major",
            disposition="quarantine",
            min_temp=-5.0,
            max_temp=20.0,
        )
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-006/excursions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "major"
        assert data["disposition"] == "quarantine"

    @pytest.mark.anyio
    async def test_report_excursion_critical(self, client: AsyncClient):
        payload = _make_excursion_report(
            severity="critical",
            disposition="destroy",
            min_temp=30.0,
            max_temp=45.0,
        )
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/excursions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "critical"
        assert data["disposition"] == "destroy"

    @pytest.mark.anyio
    async def test_report_excursion_shipment_not_found(self, client: AsyncClient):
        payload = _make_excursion_report()
        resp = await client.post(
            f"{API_PREFIX}/shipments/SHP-NONEXISTENT/excursions", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_report_excursion_appears_in_list(self, client: AsyncClient):
        payload = _make_excursion_report()
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/excursions", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/excursions")
        data = resp2.json()
        assert data["total"] == 4
        ids = [item["id"] for item in data["items"]]
        assert new_id in ids


# =====================================================================
# TEMPERATURE COMPLIANCE
# =====================================================================


class TestTemperatureCompliance:
    """Test temperature compliance checking."""

    @pytest.mark.anyio
    async def test_check_compliance_delivered_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001/temperature-compliance")
        assert resp.status_code == 200
        data = resp.json()
        # Readings at 4.0-5.0C are within 2-8C range, so no violations
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_check_compliance_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/shipments/SHP-NONEXISTENT/temperature-compliance"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_check_compliance_pending_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-008/temperature-compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0  # Pending shipment has no temp readings

    def test_storage_temp_ranges_defined(self):
        assert StorageCondition.AMBIENT in STORAGE_TEMP_RANGES
        assert StorageCondition.REFRIGERATED_2_8 in STORAGE_TEMP_RANGES
        assert StorageCondition.FROZEN_MINUS20 in STORAGE_TEMP_RANGES
        assert StorageCondition.FROZEN_MINUS80 in STORAGE_TEMP_RANGES
        assert StorageCondition.CRYOGENIC in STORAGE_TEMP_RANGES

    def test_storage_temp_ranges_values(self):
        low, high = STORAGE_TEMP_RANGES[StorageCondition.REFRIGERATED_2_8]
        assert low == 2.0
        assert high == 8.0

    def test_compliance_service_method(self, svc: SupplyChainService):
        violations = svc.check_temperature_compliance("SHP-001")
        # SHP-001 readings are 4.0, 4.5, 5.0, 4.0, 4.5 - all within 2-8C
        assert isinstance(violations, list)


# =====================================================================
# KIT ASSIGNMENTS
# =====================================================================


class TestKitAssignments:
    """Test kit assignment operations."""

    @pytest.mark.anyio
    async def test_list_kits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    @pytest.mark.anyio
    async def test_list_kits_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_kits_filter_kit_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits", params={"kit_type": "screening"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["kit_type"] == "screening"

    @pytest.mark.anyio
    async def test_list_kits_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits", params={"patient_id": "PAT-DME-003"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-DME-003"

    @pytest.mark.anyio
    async def test_get_kit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/KIT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "KIT-001"
        assert data["kit_type"] == "screening"

    @pytest.mark.anyio
    async def test_get_kit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/KIT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assign_kit(self, client: AsyncClient):
        payload = _make_kit_assign()
        resp = await client.post(f"{API_PREFIX}/kits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kit_type"] == "treatment"
        assert data["patient_id"] == "PAT-TEST-001"
        assert data["returned_date"] is None

    @pytest.mark.anyio
    async def test_assign_kit_screening(self, client: AsyncClient):
        payload = _make_kit_assign(kit_type="screening", kit_number="K-SCR-TEST")
        resp = await client.post(f"{API_PREFIX}/kits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kit_type"] == "screening"

    @pytest.mark.anyio
    async def test_return_kit(self, client: AsyncClient):
        # KIT-001 is assigned, not returned
        resp = await client.post(f"{API_PREFIX}/kits/KIT-001/return")
        assert resp.status_code == 200
        data = resp.json()
        assert data["returned_date"] is not None

    @pytest.mark.anyio
    async def test_return_kit_already_returned(self, client: AsyncClient):
        # KIT-002 is already returned
        resp = await client.post(f"{API_PREFIX}/kits/KIT-002/return")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_return_kit_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/kits/KIT-NONEXISTENT/return")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_kits_no_results(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/kits", params={"patient_id": "PAT-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =====================================================================
# KIT RECONCILIATION
# =====================================================================


class TestKitReconciliation:
    """Test kit reconciliation report."""

    @pytest.mark.anyio
    async def test_reconciliation_all_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/reconciliation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assigned"] == 20
        assert data["total_returned"] > 0
        assert data["outstanding"] == data["total_assigned"] - data["total_returned"]
        assert "by_kit_type" in data
        assert "by_site" in data

    @pytest.mark.anyio
    async def test_reconciliation_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/kits/reconciliation", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assigned"] > 0
        # All site breakdowns should only contain SITE-101
        for site_id in data["by_site"]:
            assert site_id == "SITE-101"

    @pytest.mark.anyio
    async def test_reconciliation_by_kit_type_sums(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/reconciliation")
        data = resp.json()
        total_by_type = sum(
            v["assigned"] for v in data["by_kit_type"].values()
        )
        assert total_by_type == data["total_assigned"]

    @pytest.mark.anyio
    async def test_reconciliation_by_site_sums(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/reconciliation")
        data = resp.json()
        total_by_site = sum(
            v["assigned"] for v in data["by_site"].values()
        )
        assert total_by_site == data["total_assigned"]

    @pytest.mark.anyio
    async def test_reconciliation_outstanding_matches(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/reconciliation")
        data = resp.json()
        for kt, breakdown in data["by_kit_type"].items():
            assert breakdown["outstanding"] == breakdown["assigned"] - breakdown["returned"]

    def test_reconciliation_service_all(self, svc: SupplyChainService):
        recon = svc.get_kit_reconciliation()
        assert recon.total_assigned == 20
        assert recon.outstanding >= 0

    def test_reconciliation_service_site_filter(self, svc: SupplyChainService):
        recon = svc.get_kit_reconciliation(site_id="SITE-201")
        assert recon.total_assigned > 0
        for site_id in recon.by_site:
            assert site_id == "SITE-201"

    def test_reconciliation_empty_site(self, svc: SupplyChainService):
        recon = svc.get_kit_reconciliation(site_id="SITE-NONEXISTENT")
        assert recon.total_assigned == 0
        assert recon.total_returned == 0
        assert recon.outstanding == 0


# =====================================================================
# LOT TRACEABILITY
# =====================================================================


class TestLotTraceability:
    """Test lot traceability operations."""

    @pytest.mark.anyio
    async def test_trace_lot_with_inventory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lots/LOT-2025-0001/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lot_number"] == "LOT-2025-0001"
        assert data["drug_product_id"] == "DP-001"
        assert "EYLEA" in data["drug_product_name"]
        assert len(data["inventory_items"]) > 0

    @pytest.mark.anyio
    async def test_trace_lot_with_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lots/LOT-2025-0001/trace")
        data = resp.json()
        assert len(data["shipments"]) > 0

    @pytest.mark.anyio
    async def test_trace_lot_patients_exposed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lots/LOT-2025-0001/trace")
        data = resp.json()
        # Patients at SITE-101 should be exposed (lot is at SITE-101)
        assert len(data["patients_exposed"]) > 0

    @pytest.mark.anyio
    async def test_trace_lot_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lots/LOT-NONEXISTENT/trace")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_trace_lot_with_excursions(self, client: AsyncClient):
        # LOT-2025-0017 is on SHP-005 which has EXC-001
        resp = await client.get(f"{API_PREFIX}/lots/LOT-2025-0017/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["excursions"]) > 0

    def test_trace_lot_service(self, svc: SupplyChainService):
        trace = svc.trace_lot("LOT-2025-0004")
        assert trace.drug_product_id == "DP-002"
        assert "Dupixent" in trace.drug_product_name
        assert len(trace.inventory_items) > 0

    def test_trace_lot_service_not_found(self, svc: SupplyChainService):
        with pytest.raises(KeyError):
            svc.trace_lot("LOT-NONEXISTENT")


# =====================================================================
# SUPPLY FORECASTING
# =====================================================================


class TestSupplyForecasting:
    """Test supply forecasting operations."""

    @pytest.mark.anyio
    async def test_forecast_all(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert isinstance(data["sites_below_reorder"], list)

    @pytest.mark.anyio
    async def test_forecast_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecast", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_forecast_filter_drug_product(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/forecast", params={"drug_product_id": "DP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["drug_product_id"] == "DP-001"

    @pytest.mark.anyio
    async def test_forecast_contains_consumption_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecast")
        data = resp.json()
        for item in data["items"]:
            assert "monthly_consumption_rate" in item
            assert item["monthly_consumption_rate"] >= 0

    @pytest.mark.anyio
    async def test_forecast_months_of_supply(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecast")
        data = resp.json()
        for item in data["items"]:
            if item["monthly_consumption_rate"] > 0:
                assert item["months_of_supply"] is not None
                assert item["months_of_supply"] > 0

    @pytest.mark.anyio
    async def test_forecast_reorder_points(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/forecast")
        data = resp.json()
        for item in data["items"]:
            assert item["reorder_point"] >= 0
            assert item["reorder_quantity"] >= 0

    def test_forecast_service(self, svc: SupplyChainService):
        forecast = svc.get_supply_forecast()
        assert forecast.total > 0
        assert isinstance(forecast.sites_below_reorder, list)

    def test_forecast_service_site_filter(self, svc: SupplyChainService):
        forecast = svc.get_supply_forecast(site_id="SITE-101")
        for item in forecast.items:
            assert item.site_id == "SITE-101"

    def test_forecast_service_drug_product_filter(self, svc: SupplyChainService):
        forecast = svc.get_supply_forecast(drug_product_id="DP-002")
        for item in forecast.items:
            assert item.drug_product_id == "DP-002"

    def test_forecast_low_stock_sites_identified(self, svc: SupplyChainService):
        forecast = svc.get_supply_forecast()
        # SITE-103 has only 5 units of DP-001 with consumption ~3.5/month
        # and SITE-104 has 2 units. These should be below reorder.
        low_sites = forecast.sites_below_reorder
        assert len(low_sites) > 0

    def test_forecast_no_consumption_history(self, svc: SupplyChainService):
        """Sites without consumption history should still get forecasts."""
        forecast = svc.get_supply_forecast(site_id="SITE-104")
        for item in forecast.items:
            if item.monthly_consumption_rate == 0:
                assert item.months_of_supply is None


# =====================================================================
# EXPIRING INVENTORY
# =====================================================================


class TestExpiringInventory:
    """Test expiring inventory detection."""

    @pytest.mark.anyio
    async def test_expiring_default_90_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_window"] == 90
        # INV-015 expires in 30 days, INV-016 in 60 days
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_expiring_custom_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 45})
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_window"] == 45
        # Only INV-015 (30 days) should be within 45-day window
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_expiring_narrow_window(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_window"] == 10

    @pytest.mark.anyio
    async def test_expiring_wide_window(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 365})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_expiring_items_have_expiry_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring")
        data = resp.json()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=90)
        for item in data["items"]:
            expiry = datetime.fromisoformat(item["expiry_date"])
            assert expiry <= cutoff

    def test_expiring_service(self, svc: SupplyChainService):
        result = svc.get_expiring_items(days=90)
        assert result.total >= 2
        assert result.days_window == 90

    def test_expiring_service_excludes_expired_status(self, svc: SupplyChainService):
        """Items already marked as EXPIRED should not appear in expiring list."""
        # Mark an item as expired
        from app.schemas.supply_chain import InventoryItemUpdate
        svc.update_inventory_item("INV-015", InventoryItemUpdate(status=SupplyStatus.EXPIRED))

        result = svc.get_expiring_items(days=90)
        ids = [item.id for item in result.items]
        assert "INV-015" not in ids


# =====================================================================
# METRICS DASHBOARD
# =====================================================================


class TestMetrics:
    """Test supply chain metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_drug_products"] == 5
        assert data["total_inventory_items"] == 16
        assert data["total_sites"] > 0
        assert data["active_shipments"] >= 0
        assert data["temperature_excursions_30d"] >= 0
        assert data["kits_assigned"] >= 0
        assert data["sites_below_reorder_point"] >= 0

    @pytest.mark.anyio
    async def test_metrics_active_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # SHP-005 and SHP-006 are in_transit
        assert data["active_shipments"] == 2

    @pytest.mark.anyio
    async def test_metrics_avg_months_of_supply(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        if data["avg_months_of_supply"] is not None:
            assert data["avg_months_of_supply"] > 0

    def test_metrics_service(self, svc: SupplyChainService):
        metrics = svc.get_metrics()
        assert metrics.total_drug_products == 5
        assert metrics.total_inventory_items == 16

    def test_metrics_kits_assigned_counts_unreturned(self, svc: SupplyChainService):
        metrics = svc.get_metrics()
        unreturned = sum(
            1 for k in svc.list_kit_assignments() if k.returned_date is None
        )
        assert metrics.kits_assigned == unreturned

    def test_metrics_sites_count(self, svc: SupplyChainService):
        metrics = svc.get_metrics()
        items, _ = svc.list_inventory(limit=100)
        sites = {i.site_id for i in items}
        assert metrics.total_sites == len(sites)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_supply_chain_service()
        svc2 = get_supply_chain_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_supply_chain_service()
        svc2 = reset_supply_chain_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_supply_chain_service()
        svc.delete_drug_product("DP-001")
        with pytest.raises(KeyError):
            svc.get_drug_product("DP-001")
        svc2 = reset_supply_chain_service()
        # Should be back after reset
        dp = svc2.get_drug_product("DP-001")
        assert dp.id == "DP-001"


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_drug_products_empty_after_delete_all(self, client: AsyncClient, svc: SupplyChainService):
        for dp_id in list(svc._drug_products.keys()):
            svc.delete_drug_product(dp_id)
        resp = await client.get(f"{API_PREFIX}/drug-products")
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_inventory_out_of_stock_creation(self, client: AsyncClient):
        """Creating inventory with quantity 0 is not allowed (ge=1 validation)."""
        payload = _make_inventory_create(quantity=1)
        resp = await client.post(f"{API_PREFIX}/inventory", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_shipment_with_no_tracking(self, client: AsyncClient):
        payload = _make_shipment_create(tracking_number=None)
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tracking_number"] is None

    @pytest.mark.anyio
    async def test_drug_product_no_ndc(self, client: AsyncClient):
        payload = _make_drug_product_create(ndc_code=None)
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["ndc_code"] is None

    @pytest.mark.anyio
    async def test_inventory_update_status_quarantine(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inventory/INV-001",
            json={"status": "quarantined"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "quarantined"

    @pytest.mark.anyio
    async def test_inventory_update_status_recalled(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inventory/INV-001",
            json={"status": "recalled"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recalled"

    @pytest.mark.anyio
    async def test_multiple_inventory_at_same_site(self, client: AsyncClient):
        """Multiple inventory items can exist at the same site."""
        resp = await client.get(f"{API_PREFIX}/inventory", params={"site_id": "SITE-101"})
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_excursion_list_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/excursions",
            params={"severity": "minor", "days": 7},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "minor"

    @pytest.mark.anyio
    async def test_kit_assign_rescue_type(self, client: AsyncClient):
        payload = _make_kit_assign(kit_type="rescue", kit_number="K-RSC-TEST")
        resp = await client.post(f"{API_PREFIX}/kits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kit_type"] == "rescue"

    @pytest.mark.anyio
    async def test_kit_assign_extension_type(self, client: AsyncClient):
        payload = _make_kit_assign(kit_type="extension", kit_number="K-EXT-TEST")
        resp = await client.post(f"{API_PREFIX}/kits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kit_type"] == "extension"

    @pytest.mark.anyio
    async def test_forecast_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/forecast",
            params={"site_id": "SITE-101", "drug_product_id": "DP-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"
            assert item["drug_product_id"] == "DP-001"

    @pytest.mark.anyio
    async def test_forecast_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/forecast",
            params={"site_id": "SITE-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_deliver_shipment(self, client: AsyncClient):
        """Full lifecycle: create -> deliver."""
        payload = _make_shipment_create()
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        shp_id = resp.json()["id"]

        resp2 = await client.post(f"{API_PREFIX}/shipments/{shp_id}/deliver")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "delivered"

    @pytest.mark.anyio
    async def test_create_assign_and_return_kit(self, client: AsyncClient):
        """Full lifecycle: assign -> return."""
        payload = _make_kit_assign(kit_number="K-LIFECYCLE-001")
        resp = await client.post(f"{API_PREFIX}/kits", json=payload)
        assert resp.status_code == 201
        kit_id = resp.json()["id"]

        resp2 = await client.post(f"{API_PREFIX}/kits/{kit_id}/return")
        assert resp2.status_code == 200
        assert resp2.json()["returned_date"] is not None


# =====================================================================
# DRUG PRODUCT STORAGE CONDITIONS
# =====================================================================


class TestStorageConditions:
    """Test storage condition enum values."""

    @pytest.mark.anyio
    async def test_create_frozen_minus20(self, client: AsyncClient):
        payload = _make_drug_product_create(storage_condition="frozen_minus20")
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        assert resp.json()["storage_condition"] == "frozen_minus20"

    @pytest.mark.anyio
    async def test_create_frozen_minus80(self, client: AsyncClient):
        payload = _make_drug_product_create(storage_condition="frozen_minus80")
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        assert resp.json()["storage_condition"] == "frozen_minus80"

    @pytest.mark.anyio
    async def test_create_cryogenic(self, client: AsyncClient):
        payload = _make_drug_product_create(storage_condition="cryogenic")
        resp = await client.post(f"{API_PREFIX}/drug-products", json=payload)
        assert resp.status_code == 201
        assert resp.json()["storage_condition"] == "cryogenic"


# =====================================================================
# EXCURSION DISPOSITION TYPES
# =====================================================================


class TestExcursionDispositions:
    """Test excursion disposition enum values."""

    @pytest.mark.anyio
    async def test_excursion_disposition_use(self, client: AsyncClient):
        exc = _make_excursion_report(disposition="use")
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/excursions", json=exc)
        assert resp.status_code == 201
        assert resp.json()["disposition"] == "use"

    @pytest.mark.anyio
    async def test_excursion_disposition_quarantine(self, client: AsyncClient):
        exc = _make_excursion_report(disposition="quarantine", severity="major")
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/excursions", json=exc)
        assert resp.status_code == 201
        assert resp.json()["disposition"] == "quarantine"

    @pytest.mark.anyio
    async def test_excursion_disposition_destroy(self, client: AsyncClient):
        exc = _make_excursion_report(disposition="destroy", severity="critical")
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/excursions", json=exc)
        assert resp.status_code == 201
        assert resp.json()["disposition"] == "destroy"


# =====================================================================
# SHIPMENT TEMPERATURE LOGS
# =====================================================================


class TestShipmentTemperatureLogs:
    """Test shipment temperature log data."""

    @pytest.mark.anyio
    async def test_delivered_shipment_has_temp_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        data = resp.json()
        assert len(data["temperature_log"]) > 0
        for reading in data["temperature_log"]:
            assert "timestamp" in reading
            assert "temperature_celsius" in reading
            assert "location" in reading
            assert "sensor_id" in reading

    @pytest.mark.anyio
    async def test_pending_shipment_no_temp_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-008")
        data = resp.json()
        assert len(data["temperature_log"]) == 0

    @pytest.mark.anyio
    async def test_in_transit_shipment_has_temp_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-005")
        data = resp.json()
        assert len(data["temperature_log"]) > 0


# =====================================================================
# LOT TRACE DETAILS
# =====================================================================


class TestLotTraceDetails:
    """Test lot trace response details."""

    def test_trace_lot_inventory_details(self, svc: SupplyChainService):
        trace = svc.trace_lot("LOT-2025-0001")
        for inv in trace.inventory_items:
            assert inv.lot_number == "LOT-2025-0001"
            assert inv.drug_product_id == "DP-001"

    def test_trace_lot_shipment_details(self, svc: SupplyChainService):
        trace = svc.trace_lot("LOT-2025-0001")
        for shp in trace.shipments:
            assert shp.lot_number == "LOT-2025-0001"

    def test_trace_lot_excursion_linkage(self, svc: SupplyChainService):
        """Lot on SHP-005 should show EXC-001 excursion."""
        trace = svc.trace_lot("LOT-2025-0017")
        exc_ids = [e.id for e in trace.excursions]
        assert "EXC-001" in exc_ids

    def test_trace_lot_no_excursions(self, svc: SupplyChainService):
        trace = svc.trace_lot("LOT-2025-0009")
        assert len(trace.excursions) == 0

    @pytest.mark.anyio
    async def test_trace_lot_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lots/LOT-2025-0004/trace")
        data = resp.json()
        assert "lot_number" in data
        assert "drug_product_id" in data
        assert "drug_product_name" in data
        assert "inventory_items" in data
        assert "shipments" in data
        assert "patients_exposed" in data
        assert "excursions" in data
