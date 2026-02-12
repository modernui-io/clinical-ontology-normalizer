"""Tests for Environmental Monitoring (ENV-MON) module.

Covers:
- Seed data verification (facilities, sensors, excursions, calibrations, shipments)
- Storage Facility CRUD (create, read, update, delete, list, filter by trial)
- Monitoring Sensor CRUD (create, read, update, delete, list, filter by facility)
- Temperature Excursion CRUD (create, read, update, delete, list, filter by trial)
- Calibration Record management (create, read, delete, list, filter by sensor)
- Cold Chain Shipment CRUD (create, read, update, delete, list, filter by trial)
- Environmental monitoring metrics computation
- Error handling (404s)
- Edge cases (empty filters, nonexistent trial)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.environmental_monitoring_service import (
    EnvironmentalMonitoringService,
    reset_environmental_monitoring_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/environmental-monitoring"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_environmental_monitoring_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EnvironmentalMonitoringService:
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


def _make_facility_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "facility_name": "Test Facility",
        "facility_type": "site_pharmacy",
        "location": "Test City, USA",
        "storage_condition": "refrigerated_2_8",
        "temperature_min": 2.0,
        "temperature_max": 8.0,
        "responsible_person": "Dr. Test Person",
    }
    defaults.update(overrides)
    return defaults


def _make_sensor_create(**overrides) -> dict:
    defaults = {
        "facility_id": "FAC-001",
        "sensor_type": "temperature",
        "sensor_serial": "TH-TEST-0001",
        "location_in_facility": "Test location",
        "installed_by": "Test Installer",
    }
    defaults.update(overrides)
    return defaults


def _make_excursion_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "facility_id": "FAC-001",
        "sensor_id": "SEN-001",
        "trial_id": EYLEA_TRIAL,
        "severity": "minor",
        "excursion_start": (now - timedelta(hours=2)).isoformat(),
        "allowed_min": 2.0,
        "allowed_max": 8.0,
        "reported_by": "Test Reporter",
    }
    defaults.update(overrides)
    return defaults


def _make_calibration_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "sensor_id": "SEN-001",
        "next_due_date": (now + timedelta(days=180)).isoformat(),
        "performed_by": "Test Calibrator",
        "reference_standard": "NIST-traceable Pt100 RTD",
    }
    defaults.update(overrides)
    return defaults


def _make_shipment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "shipment_id": "TEST-SHIP-001",
        "origin_facility_id": "FAC-001",
        "storage_condition": "refrigerated_2_8",
        "shipper_type": "Qualified passive shipper 48h",
        "units_shipped": 100,
        "carrier": "Test Carrier",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_facilities_count(self, svc: EnvironmentalMonitoringService):
        facilities = svc.list_facilities()
        assert len(facilities) == 12

    def test_seed_facilities_across_trials(self, svc: EnvironmentalMonitoringService):
        eylea = svc.list_facilities(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_facilities(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_facilities(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) >= 3
        assert len(dupixent) >= 3
        assert len(libtayo) >= 3

    def test_seed_sensors_count(self, svc: EnvironmentalMonitoringService):
        sensors = svc.list_sensors()
        assert len(sensors) == 15

    def test_seed_excursions_count(self, svc: EnvironmentalMonitoringService):
        excursions = svc.list_excursions()
        assert len(excursions) == 12

    def test_seed_calibrations_count(self, svc: EnvironmentalMonitoringService):
        calibrations = svc.list_calibrations()
        assert len(calibrations) == 12

    def test_seed_shipments_count(self, svc: EnvironmentalMonitoringService):
        shipments = svc.list_shipments()
        assert len(shipments) == 12

    def test_seed_has_unqualified_facility(self, svc: EnvironmentalMonitoringService):
        facilities = svc.list_facilities()
        unqualified = [f for f in facilities if not f.qualified]
        assert len(unqualified) >= 1

    def test_seed_has_inactive_sensor(self, svc: EnvironmentalMonitoringService):
        sensors = svc.list_sensors()
        inactive = [s for s in sensors if not s.active]
        assert len(inactive) >= 1

    def test_seed_has_overdue_calibration(self, svc: EnvironmentalMonitoringService):
        sensors = svc.list_sensors()
        from app.schemas.environmental_monitoring import CalibrationStatus
        overdue = [s for s in sensors if s.calibration_status == CalibrationStatus.OVERDUE]
        assert len(overdue) >= 1

    def test_seed_has_shipment_with_excursion(self, svc: EnvironmentalMonitoringService):
        shipments = svc.list_shipments()
        with_exc = [s for s in shipments if s.excursion_detected]
        assert len(with_exc) >= 1


# =====================================================================
# FACILITY CRUD
# =====================================================================


class TestFacilityCrud:
    """Test storage facility CRUD operations."""

    @pytest.mark.anyio
    async def test_list_facilities(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/facilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_facilities_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/facilities", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_facility(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/facilities/FAC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FAC-001"
        assert data["facility_name"] == "Tarrytown Central Pharmacy"

    @pytest.mark.anyio
    async def test_get_facility_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/facilities/FAC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_facility(self, client: AsyncClient):
        payload = _make_facility_create()
        resp = await client.post(f"{API_PREFIX}/facilities", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["facility_name"] == "Test Facility"
        assert data["id"].startswith("FAC-")

    @pytest.mark.anyio
    async def test_update_facility(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/facilities/FAC-001",
            json={"current_occupancy": 4000, "qualified": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_occupancy"] == 4000
        assert data["qualified"] is False

    @pytest.mark.anyio
    async def test_update_facility_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/facilities/FAC-NONEXISTENT",
            json={"current_occupancy": 100},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_facility(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/facilities/FAC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/facilities/FAC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_facility_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/facilities/FAC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SENSOR CRUD
# =====================================================================


class TestSensorCrud:
    """Test monitoring sensor CRUD operations."""

    @pytest.mark.anyio
    async def test_list_sensors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_sensors_filter_facility(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensors", params={"facility_id": "FAC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["facility_id"] == "FAC-001"

    @pytest.mark.anyio
    async def test_get_sensor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensors/SEN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SEN-001"
        assert data["sensor_serial"] == "TH-2024-0451"

    @pytest.mark.anyio
    async def test_get_sensor_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensors/SEN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sensor(self, client: AsyncClient):
        payload = _make_sensor_create()
        resp = await client.post(f"{API_PREFIX}/sensors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sensor_serial"] == "TH-TEST-0001"
        assert data["id"].startswith("SEN-")

    @pytest.mark.anyio
    async def test_update_sensor(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sensors/SEN-001",
            json={"active": False, "last_reading_value": 7.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
        assert data["last_reading_value"] == 7.5

    @pytest.mark.anyio
    async def test_update_sensor_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sensors/SEN-NONEXISTENT",
            json={"active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sensor(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sensors/SEN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sensors/SEN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sensor_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sensors/SEN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EXCURSION CRUD
# =====================================================================


class TestExcursionCrud:
    """Test temperature excursion CRUD operations."""

    @pytest.mark.anyio
    async def test_list_excursions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_excursions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_excursion(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EXC-001"
        assert data["severity"] == "minor"

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
        assert data["severity"] == "minor"
        assert data["id"].startswith("EXC-")

    @pytest.mark.anyio
    async def test_update_excursion(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/excursions/EXC-010",
            json={"status": "under_investigation", "root_cause": "Under review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_investigation"
        assert data["root_cause"] == "Under review"

    @pytest.mark.anyio
    async def test_update_excursion_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/excursions/EXC-NONEXISTENT",
            json={"status": "resolved"},
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
# CALIBRATION CRUD
# =====================================================================


class TestCalibrationCrud:
    """Test calibration record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_calibrations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/calibrations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_calibrations_filter_sensor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/calibrations", params={"sensor_id": "SEN-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["sensor_id"] == "SEN-001"

    @pytest.mark.anyio
    async def test_get_calibration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/calibrations/CAL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAL-001"
        assert data["passed"] is True

    @pytest.mark.anyio
    async def test_get_calibration_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/calibrations/CAL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_calibration(self, client: AsyncClient):
        payload = _make_calibration_create()
        resp = await client.post(f"{API_PREFIX}/calibrations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sensor_id"] == "SEN-001"
        assert data["id"].startswith("CAL-")

    @pytest.mark.anyio
    async def test_delete_calibration(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/calibrations/CAL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/calibrations/CAL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_calibration_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/calibrations/CAL-NONEXISTENT")
        assert resp.status_code == 404

    def test_seed_has_failed_calibration(self, svc: EnvironmentalMonitoringService):
        calibrations = svc.list_calibrations()
        failed = [c for c in calibrations if not c.passed]
        assert len(failed) >= 1


# =====================================================================
# SHIPMENT CRUD
# =====================================================================


class TestShipmentCrud:
    """Test cold chain shipment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_shipments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

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
        assert data["shipment_id"] == "TEST-SHIP-001"
        assert data["id"].startswith("SHP-")

    @pytest.mark.anyio
    async def test_update_shipment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-010",
            json={"status": "delivered", "min_temp_recorded": 3.0, "max_temp_recorded": 6.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"
        assert data["min_temp_recorded"] == 3.0

    @pytest.mark.anyio
    async def test_update_shipment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-NONEXISTENT",
            json={"status": "delivered"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipments/SHP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipments/SHP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test environmental monitoring metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_facilities"] == 12
        assert data["qualified_facilities"] >= 10
        assert data["total_sensors"] == 15
        assert data["active_sensors"] >= 13
        assert data["total_excursions"] == 12
        assert data["open_excursions"] >= 1
        assert data["total_calibrations"] == 12
        assert 0.0 <= data["calibrations_passed_pct"] <= 100.0
        assert data["total_shipments"] == 12
        assert data["shipments_with_excursions"] >= 1

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_facilities"] >= 3
        assert data["total_excursions"] >= 3

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_facilities"] == 0
        assert data["total_sensors"] == 0

    def test_metrics_facilities_by_condition(self, svc: EnvironmentalMonitoringService):
        metrics = svc.get_metrics()
        total_by_condition = sum(metrics.facilities_by_condition.values())
        assert total_by_condition == metrics.total_facilities

    def test_metrics_sensors_by_calibration(self, svc: EnvironmentalMonitoringService):
        metrics = svc.get_metrics()
        total_by_cal = sum(metrics.sensors_by_calibration.values())
        assert total_by_cal == metrics.total_sensors

    def test_metrics_excursions_by_severity(self, svc: EnvironmentalMonitoringService):
        metrics = svc.get_metrics()
        total_by_sev = sum(metrics.excursions_by_severity.values())
        assert total_by_sev == metrics.total_excursions

    def test_metrics_excursions_by_status(self, svc: EnvironmentalMonitoringService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.excursions_by_status.values())
        assert total_by_status == metrics.total_excursions


# =====================================================================
# SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_reset_creates_fresh_instance(self):
        from app.services.environmental_monitoring_service import (
            get_environmental_monitoring_service,
        )
        svc1 = get_environmental_monitoring_service()
        svc2 = reset_environmental_monitoring_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        from app.services.environmental_monitoring_service import (
            get_environmental_monitoring_service,
        )
        svc = get_environmental_monitoring_service()
        svc.delete_facility("FAC-001")
        assert svc.get_facility("FAC-001") is None
        svc2 = reset_environmental_monitoring_service()
        assert svc2.get_facility("FAC-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_facilities_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/facilities", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_sensors_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensors", params={"facility_id": "FAC-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_excursions_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_calibrations_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/calibrations", params={"sensor_id": "SEN-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_shipments_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_facility_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/facilities/FAC-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "facility_name" in data
        assert "storage_condition" in data
        assert "temperature_min" in data
        assert "temperature_max" in data
        assert "responsible_person" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_sensor_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensors/SEN-001")
        data = resp.json()
        assert "id" in data
        assert "facility_id" in data
        assert "sensor_type" in data
        assert "sensor_serial" in data
        assert "active" in data
        assert "calibration_status" in data

    @pytest.mark.anyio
    async def test_excursion_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/excursions/EXC-001")
        data = resp.json()
        assert "id" in data
        assert "facility_id" in data
        assert "sensor_id" in data
        assert "trial_id" in data
        assert "severity" in data
        assert "status" in data
        assert "allowed_min" in data
        assert "allowed_max" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_facilities" in data
        assert "qualified_facilities" in data
        assert "facilities_by_condition" in data
        assert "total_sensors" in data
        assert "active_sensors" in data
        assert "sensors_by_calibration" in data
        assert "total_excursions" in data
        assert "excursions_by_severity" in data
        assert "excursions_by_status" in data
        assert "open_excursions" in data
        assert "total_calibrations" in data
        assert "calibrations_passed_pct" in data
        assert "total_shipments" in data
        assert "shipments_with_excursions" in data
