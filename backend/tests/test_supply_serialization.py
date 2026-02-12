"""Tests for Supply Chain Serialization & Track-and-Trace (CLINICAL-11).

Covers:
- Seed data verification (units, tracking events, cold chain, compliance,
  verification requests, distribution records)
- Serialized unit CRUD (register, read, update, delete, list, filter)
- Serialization hierarchy (parent-child, children endpoint)
- Tracking event recording and lifecycle status updates
- Cold chain monitoring (logging, classification, alert acknowledgement)
- Compliance verification (DSCSA, FMD, SNCM, auto-determination)
- Counterfeit detection (verification requests, suspect resolution)
- Distribution tracking (create, receipt, discrepancy detection)
- Unit history tracing (full provenance chain)
- Serialization metrics computation
- Error handling (404s, 400s, 409 duplicate serials, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.supply_serialization import (
    ColdChainStatus,
    ComplianceStandard,
    SerializationLevel,
    TrackingEventType,
    UnitStatus,
    VerificationStatus,
)
from app.services.supply_serialization_service import (
    SupplySerializationService,
    get_supply_serialization_service,
    reset_supply_serialization_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/supply-serialization"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_supply_serialization_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SupplySerializationService:
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


def _make_unit_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "product_name": "Test Drug 100mg",
        "gtin": "99999999999999",
        "serial_number": f"SN-TEST-{now.timestamp()}",
        "lot_number": "LOT-TEST-001",
        "expiry_date": (now + timedelta(days=365)).isoformat(),
        "serialization_level": "unit",
        "parent_id": None,
        "manufacturing_site": "Test Plant",
        "manufacturing_date": (now - timedelta(days=30)).isoformat(),
        "current_location": "Test Depot",
    }
    defaults.update(overrides)
    return defaults


def _make_tracking_event_create(**overrides) -> dict:
    defaults = {
        "unit_id": "SU-006",
        "event_type": "dispensed",
        "location": "SITE-101",
        "facility_name": "Test Clinical Site",
        "scanned_by": "TEST-PHARM-001",
        "gps_latitude": 39.2984,
        "gps_longitude": -76.5922,
        "temperature": 5.0,
        "humidity": 43.0,
        "notes": "Test dispensing event",
        "transaction_id": "TXN-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_cold_chain_create(**overrides) -> dict:
    defaults = {
        "shipment_id": "DIST-004",
        "sensor_id": "SENS-TEST-001",
        "temperature": 5.0,
        "humidity": 42.0,
        "location": "Test Transit Point",
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_create(**overrides) -> dict:
    defaults = {
        "unit_id": "SU-006",
        "standard": "dscsa",
        "country": "US",
        "verified_by": "TEST-COMPLIANCE-SYS",
        "transaction_information": "TI-TEST-001",
        "transaction_history": "TH-TEST-001",
        "transaction_statement": "TS-TEST-001",
        "certificate_reference": "CERT-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_verification_create(**overrides) -> dict:
    defaults = {
        "requestor": "Test Pharmacy",
        "gtin": "00361755000601",
        "serial_number": "SN-UNIT-2025-0002",
        "lot_number": "LOT-2025-A001",
    }
    defaults.update(overrides)
    return defaults


def _make_distribution_create(**overrides) -> dict:
    defaults = {
        "from_facility": "DEPOT-CENTRAL",
        "to_facility": "SITE-101",
        "units_shipped": 10,
        "carrier": "FedEx Priority",
        "tracking_number": "FX-TEST-001",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_units_count(self, svc: SupplySerializationService):
        items, total = svc.list_units()
        assert total == 12

    def test_seed_units_hierarchy_pallet(self, svc: SupplySerializationService):
        items, _ = svc.list_units(serialization_level=SerializationLevel.PALLET)
        assert len(items) == 1
        assert items[0].id == "SU-001"

    def test_seed_units_hierarchy_cases(self, svc: SupplySerializationService):
        items, _ = svc.list_units(serialization_level=SerializationLevel.CASE)
        assert len(items) == 4

    def test_seed_units_hierarchy_bundles(self, svc: SupplySerializationService):
        items, _ = svc.list_units(serialization_level=SerializationLevel.BUNDLE)
        assert len(items) == 1

    def test_seed_units_hierarchy_individual(self, svc: SupplySerializationService):
        items, _ = svc.list_units(serialization_level=SerializationLevel.UNIT)
        assert len(items) == 6

    def test_seed_units_statuses(self, svc: SupplySerializationService):
        items, _ = svc.list_units()
        statuses = {u.status for u in items}
        assert UnitStatus.ACTIVE in statuses
        assert UnitStatus.DISPENSED in statuses
        assert UnitStatus.RECALLED in statuses
        assert UnitStatus.QUARANTINED in statuses

    def test_seed_tracking_events_count(self, svc: SupplySerializationService):
        items, total = svc.list_tracking_events()
        assert total == 18

    def test_seed_cold_chain_count(self, svc: SupplySerializationService):
        items, total = svc.list_cold_chain_readings()
        assert total == 10

    def test_seed_cold_chain_alerts(self, svc: SupplySerializationService):
        items, total = svc.list_cold_chain_readings(alert_triggered=True)
        assert total == 3

    def test_seed_compliance_count(self, svc: SupplySerializationService):
        items, total = svc.list_compliance_records()
        assert total == 7

    def test_seed_compliance_standards(self, svc: SupplySerializationService):
        items, _ = svc.list_compliance_records()
        standards = {c.standard for c in items}
        assert ComplianceStandard.DSCSA in standards
        assert ComplianceStandard.EU_FMD in standards
        assert ComplianceStandard.BRAZIL_SNCM in standards

    def test_seed_verification_count(self, svc: SupplySerializationService):
        items, total = svc.list_verification_requests()
        assert total == 3

    def test_seed_verification_statuses(self, svc: SupplySerializationService):
        items, _ = svc.list_verification_requests()
        statuses = {v.verification_status for v in items}
        assert VerificationStatus.VERIFIED in statuses
        assert VerificationStatus.SUSPECT in statuses
        assert VerificationStatus.QUARANTINED in statuses

    def test_seed_distribution_count(self, svc: SupplySerializationService):
        items, total = svc.list_distribution_records()
        assert total == 5

    def test_seed_distribution_discrepancy(self, svc: SupplySerializationService):
        items, _ = svc.list_distribution_records(discrepancy=True)
        assert len(items) == 1
        assert items[0].id == "DIST-002"

    def test_seed_parent_child_relationship(self, svc: SupplySerializationService):
        children = svc.get_children("SU-001")
        child_ids = {c.id for c in children}
        assert "SU-002" in child_ids
        assert "SU-003" in child_ids


# =====================================================================
# SERIALIZED UNIT CRUD
# =====================================================================


class TestSerializedUnitCrud:
    """Test serialized unit create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_units(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_units_filter_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units", params={"serialization_level": "pallet"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["serialization_level"] == "pallet"

    @pytest.mark.anyio
    async def test_list_units_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units", params={"status": "dispensed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["status"] == "dispensed"

    @pytest.mark.anyio
    async def test_list_units_filter_lot(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units", params={"lot_number": "LOT-2025-A001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 6
        for item in data["items"]:
            assert item["lot_number"] == "LOT-2025-A001"

    @pytest.mark.anyio
    async def test_list_units_filter_gtin(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units", params={"gtin": "00024591801"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["gtin"] == "00024591801"

    @pytest.mark.anyio
    async def test_list_units_pagination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units", params={"limit": 3, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_get_unit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SU-001"
        assert data["serialization_level"] == "pallet"

    @pytest.mark.anyio
    async def test_get_unit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_register_serial(self, client: AsyncClient):
        payload = _make_unit_create(serial_number="SN-NEW-001")
        resp = await client.post(f"{API_PREFIX}/units", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["serial_number"] == "SN-NEW-001"
        assert data["id"].startswith("SU-")
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_register_serial_with_parent(self, client: AsyncClient):
        payload = _make_unit_create(
            serial_number="SN-NEW-CHILD-001",
            parent_id="SU-002",
            serialization_level="bundle",
        )
        resp = await client.post(f"{API_PREFIX}/units", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_id"] == "SU-002"

    @pytest.mark.anyio
    async def test_register_serial_invalid_parent(self, client: AsyncClient):
        payload = _make_unit_create(
            serial_number="SN-NEW-BAD-PARENT",
            parent_id="SU-NONEXISTENT",
        )
        resp = await client.post(f"{API_PREFIX}/units", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_register_duplicate_serial(self, client: AsyncClient):
        payload = _make_unit_create(
            gtin="00361755000601",
            serial_number="SN-PAL-2025-0001",
        )
        resp = await client.post(f"{API_PREFIX}/units", json=payload)
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_update_unit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/units/SU-006",
            json={"status": "dispensed", "current_location": "PATIENT-HOME"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dispensed"
        assert data["current_location"] == "PATIENT-HOME"

    @pytest.mark.anyio
    async def test_update_unit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/units/SU-NONEXISTENT",
            json={"status": "active"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_unit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/units/SU-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/units/SU-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_unit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/units/SU-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SERIALIZATION HIERARCHY
# =====================================================================


class TestSerializationHierarchy:
    """Test parent-child hierarchy and aggregation."""

    @pytest.mark.anyio
    async def test_get_children_pallet(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-001/children")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        child_ids = {c["id"] for c in data["items"]}
        assert "SU-002" in child_ids
        assert "SU-003" in child_ids

    @pytest.mark.anyio
    async def test_get_children_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-002/children")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "SU-004"

    @pytest.mark.anyio
    async def test_get_children_bundle(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-004/children")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        child_ids = {c["id"] for c in data["items"]}
        assert "SU-005" in child_ids
        assert "SU-006" in child_ids

    @pytest.mark.anyio
    async def test_get_children_leaf_unit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-005/children")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_get_children_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-NONEXISTENT/children")
        assert resp.status_code == 404

    def test_hierarchy_depth(self, svc: SupplySerializationService):
        """Verify full 4-level hierarchy: pallet -> case -> bundle -> unit."""
        pallet = svc.get_unit("SU-001")
        assert pallet.serialization_level == SerializationLevel.PALLET
        cases = svc.get_children("SU-001")
        assert all(c.serialization_level == SerializationLevel.CASE for c in cases)
        bundles = svc.get_children("SU-002")
        assert all(b.serialization_level == SerializationLevel.BUNDLE for b in bundles)
        units = svc.get_children("SU-004")
        assert all(u.serialization_level == SerializationLevel.UNIT for u in units)


# =====================================================================
# TRACKING EVENTS
# =====================================================================


class TestTrackingEvents:
    """Test tracking event recording and lifecycle management."""

    @pytest.mark.anyio
    async def test_list_tracking_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracking-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 18

    @pytest.mark.anyio
    async def test_list_tracking_events_filter_unit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracking-events", params={"unit_id": "SU-005"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["unit_id"] == "SU-005"

    @pytest.mark.anyio
    async def test_list_tracking_events_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tracking-events", params={"event_type": "dispensed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["event_type"] == "dispensed"

    @pytest.mark.anyio
    async def test_get_tracking_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracking-events/TE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TE-001"
        assert data["event_type"] == "manufactured"

    @pytest.mark.anyio
    async def test_get_tracking_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracking-events/TE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_tracking_event(self, client: AsyncClient):
        payload = _make_tracking_event_create()
        resp = await client.post(f"{API_PREFIX}/tracking-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit_id"] == "SU-006"
        assert data["event_type"] == "dispensed"
        assert data["id"].startswith("TE-")

    @pytest.mark.anyio
    async def test_record_tracking_event_updates_unit_status(self, client: AsyncClient):
        payload = _make_tracking_event_create(event_type="shipped", location="DEPOT-CENTRAL")
        resp = await client.post(f"{API_PREFIX}/tracking-events", json=payload)
        assert resp.status_code == 201

        unit_resp = await client.get(f"{API_PREFIX}/units/SU-006")
        assert unit_resp.status_code == 200
        unit_data = unit_resp.json()
        assert unit_data["status"] == "in_transit"
        assert unit_data["current_location"] == "DEPOT-CENTRAL"

    @pytest.mark.anyio
    async def test_record_tracking_event_received_updates_active(self, client: AsyncClient):
        payload = _make_tracking_event_create(
            unit_id="SU-003", event_type="received", location="SITE-102",
        )
        resp = await client.post(f"{API_PREFIX}/tracking-events", json=payload)
        assert resp.status_code == 201

        unit_resp = await client.get(f"{API_PREFIX}/units/SU-003")
        unit_data = unit_resp.json()
        assert unit_data["status"] == "active"

    @pytest.mark.anyio
    async def test_record_tracking_event_invalid_unit(self, client: AsyncClient):
        payload = _make_tracking_event_create(unit_id="SU-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/tracking-events", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_tracking_event(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tracking-events/TE-018")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/tracking-events/TE-018")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_tracking_event_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tracking-events/TE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_tracking_events_sorted_by_timestamp(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracking-events", params={"unit_id": "SU-005"})
        data = resp.json()
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps)


# =====================================================================
# COLD CHAIN MONITORING
# =====================================================================


class TestColdChainMonitoring:
    """Test cold chain reading logging, classification, and alerts."""

    @pytest.mark.anyio
    async def test_list_cold_chain(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cold-chain")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_cold_chain_filter_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cold-chain", params={"shipment_id": "DIST-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["shipment_id"] == "DIST-001"

    @pytest.mark.anyio
    async def test_list_cold_chain_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cold-chain", params={"status": "breach"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "breach"

    @pytest.mark.anyio
    async def test_list_cold_chain_filter_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cold-chain", params={"alert_triggered": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_get_cold_chain_reading(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cold-chain/CC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CC-001"
        assert data["status"] == "within_range"

    @pytest.mark.anyio
    async def test_get_cold_chain_reading_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cold-chain/CC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_log_cold_chain_within_range(self, client: AsyncClient):
        payload = _make_cold_chain_create(temperature=5.0)
        resp = await client.post(f"{API_PREFIX}/cold-chain", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "within_range"
        assert data["alert_triggered"] is False

    @pytest.mark.anyio
    async def test_log_cold_chain_minor_excursion(self, client: AsyncClient):
        payload = _make_cold_chain_create(temperature=8.5)
        resp = await client.post(f"{API_PREFIX}/cold-chain", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "excursion_minor"
        assert data["alert_triggered"] is True

    @pytest.mark.anyio
    async def test_log_cold_chain_major_excursion(self, client: AsyncClient):
        payload = _make_cold_chain_create(temperature=11.0)
        resp = await client.post(f"{API_PREFIX}/cold-chain", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "excursion_major"
        assert data["alert_triggered"] is True

    @pytest.mark.anyio
    async def test_log_cold_chain_breach(self, client: AsyncClient):
        payload = _make_cold_chain_create(temperature=15.0)
        resp = await client.post(f"{API_PREFIX}/cold-chain", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "breach"
        assert data["alert_triggered"] is True

    @pytest.mark.anyio
    async def test_log_cold_chain_low_temp_breach(self, client: AsyncClient):
        payload = _make_cold_chain_create(temperature=-5.0)
        resp = await client.post(f"{API_PREFIX}/cold-chain", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "breach"
        assert data["alert_triggered"] is True

    @pytest.mark.anyio
    async def test_acknowledge_cold_chain_alert(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/cold-chain/CC-008/acknowledge",
            json={"acknowledged_by": "QA-MGR-TEST"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_acknowledged_by"] == "QA-MGR-TEST"
        assert data["alert_acknowledged_date"] is not None

    @pytest.mark.anyio
    async def test_acknowledge_non_alert_reading(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/cold-chain/CC-001/acknowledge",
            json={"acknowledged_by": "QA-MGR-TEST"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_already_acknowledged(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/cold-chain/CC-003/acknowledge",
            json={"acknowledged_by": "QA-MGR-TEST-2"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/cold-chain/CC-NONEXISTENT/acknowledge",
            json={"acknowledged_by": "QA-MGR-TEST"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cold_chain_reading(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cold-chain/CC-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/cold-chain/CC-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cold_chain_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cold-chain/CC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE VERIFICATION
# =====================================================================


class TestComplianceVerification:
    """Test compliance record creation and verification logic."""

    @pytest.mark.anyio
    async def test_list_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_compliance_filter_unit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"unit_id": "SU-008"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["unit_id"] == "SU-008"

    @pytest.mark.anyio
    async def test_list_compliance_filter_standard(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"standard": "dscsa"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 4
        for item in data["items"]:
            assert item["standard"] == "dscsa"

    @pytest.mark.anyio
    async def test_list_compliance_filter_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"compliant": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["unit_id"] == "SU-012"

    @pytest.mark.anyio
    async def test_get_compliance_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CR-001"
        assert data["standard"] == "dscsa"
        assert data["compliant"] is True

    @pytest.mark.anyio
    async def test_get_compliance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/CR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_check_compliance_active_unit(self, client: AsyncClient):
        payload = _make_compliance_create(unit_id="SU-006")
        resp = await client.post(f"{API_PREFIX}/compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["compliant"] is True
        assert data["standard"] == "dscsa"

    @pytest.mark.anyio
    async def test_check_compliance_quarantined_unit(self, client: AsyncClient):
        payload = _make_compliance_create(unit_id="SU-012")
        resp = await client.post(f"{API_PREFIX}/compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["compliant"] is False

    @pytest.mark.anyio
    async def test_check_compliance_recalled_unit(self, client: AsyncClient):
        payload = _make_compliance_create(unit_id="SU-011")
        resp = await client.post(f"{API_PREFIX}/compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["compliant"] is False

    @pytest.mark.anyio
    async def test_check_compliance_invalid_unit(self, client: AsyncClient):
        payload = _make_compliance_create(unit_id="SU-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/compliance", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_check_compliance_eu_fmd(self, client: AsyncClient):
        payload = _make_compliance_create(
            unit_id="SU-008", standard="eu_fmd", country="FR",
        )
        resp = await client.post(f"{API_PREFIX}/compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["standard"] == "eu_fmd"
        assert data["country"] == "FR"

    @pytest.mark.anyio
    async def test_delete_compliance(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance/CR-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance/CR-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance/CR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COUNTERFEIT DETECTION (VERIFICATION REQUESTS)
# =====================================================================


class TestCounterfeitDetection:
    """Test verification requests and counterfeit detection logic."""

    @pytest.mark.anyio
    async def test_list_verifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/verifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_verifications_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/verifications",
            params={"verification_status": "suspect"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_get_verification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/verifications/VR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VR-001"
        assert data["verification_status"] == "suspect"

    @pytest.mark.anyio
    async def test_get_verification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/verifications/VR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_verify_known_authentic_unit(self, client: AsyncClient):
        payload = _make_verification_create(
            gtin="00361755000601",
            serial_number="SN-UNIT-2025-0002",
            lot_number="LOT-2025-A001",
        )
        resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["verification_status"] == "verified"
        assert data["resolution"] == "Product verified as authentic"

    @pytest.mark.anyio
    async def test_verify_unknown_serial(self, client: AsyncClient):
        payload = _make_verification_create(
            gtin="00361755000601",
            serial_number="SN-UNKNOWN-FAKE",
            lot_number="LOT-2025-A001",
        )
        resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["verification_status"] == "suspect"
        assert "not found" in data["investigation_notes"].lower()

    @pytest.mark.anyio
    async def test_verify_quarantined_unit(self, client: AsyncClient):
        payload = _make_verification_create(
            gtin="00361755000601",
            serial_number="SN-UNIT-2025-SUSPECT",
            lot_number="LOT-2025-X001",
        )
        resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["verification_status"] == "quarantined"

    @pytest.mark.anyio
    async def test_verify_recalled_unit(self, client: AsyncClient):
        payload = _make_verification_create(
            gtin="00361755000601",
            serial_number="SN-UNIT-2025-0099",
            lot_number="LOT-2025-A002",
        )
        resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["verification_status"] == "suspect"
        assert "recalled" in data["investigation_notes"].lower()

    @pytest.mark.anyio
    async def test_update_verification_resolve(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/verifications/VR-001",
            json={
                "verification_status": "confirmed_counterfeit",
                "responder": "Regeneron Investigations",
                "investigation_notes": "Confirmed counterfeit via lab analysis",
                "resolution": "Counterfeit confirmed - law enforcement notified",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_status"] == "confirmed_counterfeit"
        assert data["resolution"] is not None

    @pytest.mark.anyio
    async def test_update_verification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/verifications/VR-NONEXISTENT",
            json={"verification_status": "verified"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_verification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/verifications/VR-002")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/verifications/VR-002")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_verification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/verifications/VR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DISTRIBUTION TRACKING
# =====================================================================


class TestDistributionTracking:
    """Test distribution record management and discrepancy detection."""

    @pytest.mark.anyio
    async def test_list_distributions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distributions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_distributions_filter_from(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/distributions",
            params={"from_facility": "DEPOT-CENTRAL"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["from_facility"] == "DEPOT-CENTRAL"

    @pytest.mark.anyio
    async def test_list_distributions_filter_to(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/distributions",
            params={"to_facility": "SITE-101"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_distributions_filter_discrepancy(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/distributions", params={"discrepancy": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_get_distribution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distributions/DIST-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DIST-001"
        assert data["chain_of_custody_verified"] is True

    @pytest.mark.anyio
    async def test_get_distribution_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distributions/DIST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_distribution(self, client: AsyncClient):
        payload = _make_distribution_create()
        resp = await client.post(f"{API_PREFIX}/distributions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["from_facility"] == "DEPOT-CENTRAL"
        assert data["to_facility"] == "SITE-101"
        assert data["units_shipped"] == 10
        assert data["received_date"] is None
        assert data["chain_of_custody_verified"] is False

    @pytest.mark.anyio
    async def test_update_distribution_receipt_no_discrepancy(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/distributions/DIST-003",
            json={
                "received_date": now.isoformat(),
                "units_received": 12,
                "chain_of_custody_verified": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["units_received"] == 12
        assert data["discrepancy"] is False
        assert data["chain_of_custody_verified"] is True

    @pytest.mark.anyio
    async def test_update_distribution_receipt_with_discrepancy(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/distributions/DIST-004",
            json={
                "received_date": now.isoformat(),
                "units_received": 15,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["units_received"] == 15
        assert data["units_shipped"] == 18
        assert data["discrepancy"] is True

    @pytest.mark.anyio
    async def test_update_distribution_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/distributions/DIST-NONEXISTENT",
            json={"units_received": 5},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_distribution(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/distributions/DIST-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/distributions/DIST-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_distribution_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/distributions/DIST-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# UNIT HISTORY TRACING
# =====================================================================


class TestUnitHistoryTracing:
    """Test full unit history tracing across the supply chain."""

    @pytest.mark.anyio
    async def test_trace_unit_full_lifecycle(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-005/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unit"]["id"] == "SU-005"
        assert len(data["events"]) == 5
        assert data["events"][0]["event_type"] == "manufactured"
        assert data["events"][-1]["event_type"] == "dispensed"

    @pytest.mark.anyio
    async def test_trace_unit_includes_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-005/trace")
        data = resp.json()
        assert len(data["compliance_records"]) >= 1
        assert data["compliance_records"][0]["unit_id"] == "SU-005"

    @pytest.mark.anyio
    async def test_trace_unit_includes_verifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-005/trace")
        data = resp.json()
        # SU-005 has serial SN-UNIT-2025-0001 which was verified in VR-002
        assert len(data["verification_requests"]) >= 1

    @pytest.mark.anyio
    async def test_trace_unit_includes_children(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-004/trace")
        data = resp.json()
        assert len(data["children"]) == 2
        child_ids = {c["id"] for c in data["children"]}
        assert "SU-005" in child_ids
        assert "SU-006" in child_ids

    @pytest.mark.anyio
    async def test_trace_recalled_unit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-011/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unit"]["status"] == "recalled"
        event_types = [e["event_type"] for e in data["events"]]
        assert "recalled" in event_types

    @pytest.mark.anyio
    async def test_trace_suspect_unit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-012/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unit"]["status"] == "quarantined"
        assert len(data["compliance_records"]) >= 1
        # Should have a non-compliant compliance record
        non_compliant = [c for c in data["compliance_records"] if not c["compliant"]]
        assert len(non_compliant) >= 1

    @pytest.mark.anyio
    async def test_trace_unit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/units/SU-NONEXISTENT/trace")
        assert resp.status_code == 404

    def test_trace_events_sorted_chronologically(self, svc: SupplySerializationService):
        trace = svc.trace_unit_history("SU-005")
        timestamps = [e.timestamp for e in trace.events]
        assert timestamps == sorted(timestamps)


# =====================================================================
# SERIALIZATION METRICS
# =====================================================================


class TestSerializationMetrics:
    """Test aggregated metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_serialized_units"] == 12
        assert data["total_tracking_events"] == 18
        assert data["total_cold_chain_readings"] == 10
        assert data["total_compliance_records"] == 7
        assert data["total_verification_requests"] == 3
        assert data["total_distribution_records"] == 5

    @pytest.mark.anyio
    async def test_metrics_units_by_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_level = data["units_by_level"]
        assert by_level["pallet"] == 1
        assert by_level["case"] == 4
        assert by_level["bundle"] == 1
        assert by_level["unit"] == 6

    @pytest.mark.anyio
    async def test_metrics_units_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["units_by_status"]
        assert by_status.get("active", 0) >= 5
        assert by_status.get("dispensed", 0) >= 2
        assert by_status.get("recalled", 0) >= 1
        assert by_status.get("quarantined", 0) >= 1

    @pytest.mark.anyio
    async def test_metrics_cold_chain_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["cold_chain_alerts"] == 3

    @pytest.mark.anyio
    async def test_metrics_compliance_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # 6 compliant out of 7 total = 85.71%
        assert 85.0 <= data["compliance_rate"] <= 86.0

    @pytest.mark.anyio
    async def test_metrics_suspect_or_counterfeit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["suspect_or_counterfeit"] == 1

    @pytest.mark.anyio
    async def test_metrics_distribution_discrepancies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["distribution_discrepancies"] == 1

    @pytest.mark.anyio
    async def test_metrics_dispensed_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["units_dispensed"] >= 2

    @pytest.mark.anyio
    async def test_metrics_recalled_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["units_recalled"] >= 1


# =====================================================================
# SERVICE-LEVEL UNIT TESTS
# =====================================================================


class TestServiceDirect:
    """Direct service-level tests for edge cases and internal logic."""

    def test_classify_cold_chain_boundary_low(self, svc: SupplySerializationService):
        from app.services.supply_serialization_service import _classify_cold_chain
        assert _classify_cold_chain(2.0) == ColdChainStatus.WITHIN_RANGE
        assert _classify_cold_chain(8.0) == ColdChainStatus.WITHIN_RANGE

    def test_classify_cold_chain_boundary_minor(self, svc: SupplySerializationService):
        from app.services.supply_serialization_service import _classify_cold_chain
        assert _classify_cold_chain(1.0) == ColdChainStatus.EXCURSION_MINOR
        assert _classify_cold_chain(9.0) == ColdChainStatus.EXCURSION_MINOR

    def test_classify_cold_chain_boundary_major(self, svc: SupplySerializationService):
        from app.services.supply_serialization_service import _classify_cold_chain
        assert _classify_cold_chain(-2.0) == ColdChainStatus.EXCURSION_MAJOR
        assert _classify_cold_chain(12.0) == ColdChainStatus.EXCURSION_MAJOR

    def test_classify_cold_chain_breach(self, svc: SupplySerializationService):
        from app.services.supply_serialization_service import _classify_cold_chain
        assert _classify_cold_chain(-5.0) == ColdChainStatus.BREACH
        assert _classify_cold_chain(20.0) == ColdChainStatus.BREACH

    def test_register_serial_duplicate_detection(self, svc: SupplySerializationService):
        from app.schemas.supply_serialization import SerializedUnitCreate
        now = datetime.now(timezone.utc)
        data = SerializedUnitCreate(
            product_name="Test",
            gtin="00361755000601",
            serial_number="SN-PAL-2025-0001",
            lot_number="LOT-TEST",
            expiry_date=now + timedelta(days=365),
            serialization_level=SerializationLevel.UNIT,
            manufacturing_site="Test",
            manufacturing_date=now,
            current_location="Test",
        )
        with pytest.raises(ValueError, match="Duplicate serial number"):
            svc.register_serial(data)

    def test_update_distribution_discrepancy_auto_detect(
        self, svc: SupplySerializationService,
    ):
        from app.schemas.supply_serialization import DistributionRecordUpdate
        now = datetime.now(timezone.utc)
        updated = svc.update_distribution_record(
            "DIST-003",
            DistributionRecordUpdate(
                received_date=now, units_received=10,
            ),
        )
        # DIST-003 shipped 12, received 10 -> discrepancy
        assert updated.discrepancy is True

    def test_update_distribution_no_discrepancy(
        self, svc: SupplySerializationService,
    ):
        from app.schemas.supply_serialization import DistributionRecordUpdate
        now = datetime.now(timezone.utc)
        updated = svc.update_distribution_record(
            "DIST-003",
            DistributionRecordUpdate(
                received_date=now, units_received=12,
            ),
        )
        assert updated.discrepancy is False

    def test_verify_unit_with_mismatched_lot(self, svc: SupplySerializationService):
        from app.schemas.supply_serialization import VerificationRequestCreate
        result = svc.verify_unit(VerificationRequestCreate(
            requestor="Test",
            gtin="00361755000601",
            serial_number="SN-UNIT-2025-0001",
            lot_number="LOT-WRONG",
        ))
        # GTIN+SN match SU-005 but lot doesn't -> suspect
        assert result.verification_status == VerificationStatus.SUSPECT

    def test_trace_includes_cold_chain_from_related_distributions(
        self, svc: SupplySerializationService,
    ):
        trace = svc.trace_unit_history("SU-005")
        # SU-005 was at DEPOT-CENTRAL and SITE-101; DIST-001 goes from
        # DEPOT-CENTRAL to SITE-101 so its cold chain readings should appear
        assert len(trace.cold_chain_readings) >= 1

    def test_metrics_update_after_operations(self, svc: SupplySerializationService):
        from app.schemas.supply_serialization import (
            SerializedUnitCreate,
            VerificationRequestCreate,
        )
        now = datetime.now(timezone.utc)
        # Add a unit
        svc.register_serial(SerializedUnitCreate(
            product_name="New Drug",
            gtin="11111111111111",
            serial_number="SN-METRICS-TEST",
            lot_number="LOT-METRICS",
            expiry_date=now + timedelta(days=365),
            serialization_level=SerializationLevel.UNIT,
            manufacturing_site="Test",
            manufacturing_date=now,
            current_location="Test",
        ))
        metrics = svc.get_metrics()
        assert metrics.total_serialized_units == 13

    def test_get_children_no_unit(self, svc: SupplySerializationService):
        with pytest.raises(KeyError):
            svc.get_children("SU-NONEXISTENT")

    def test_delete_unit_cascade_check(self, svc: SupplySerializationService):
        """Deleting a parent does not auto-delete children, they become orphans."""
        svc.delete_unit("SU-004")
        # Children SU-005, SU-006 still exist but their parent is gone
        su005 = svc.get_unit("SU-005")
        assert su005.parent_id == "SU-004"
        # Parent ID is stale but unit is still accessible
        with pytest.raises(KeyError):
            svc.get_unit("SU-004")
