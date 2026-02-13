"""Tests for Medical Device Tracking (MDT-TRK).

Covers:
- Seed data verification (device registrations, device deployments, maintenance logs,
  device incident reports)
- Device registration CRUD (create, read, update, delete, list, filter by trial/classification)
- Device deployment CRUD (create, read, update, delete, list, filter by trial/status/site)
- Maintenance log CRUD (create, read, update, delete, list, filter by trial/type/result)
- Device incident report CRUD (create, read, update, delete, list, filter by trial/severity/site)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.medical_device_tracking import (
    DeploymentStatus,
    DeviceClassification,
    IncidentSeverity,
    MaintenanceResult,
    MaintenanceType,
)
from app.services.medical_device_tracking_service import (
    MedicalDeviceTrackingService,
    get_medical_device_tracking_service,
    reset_medical_device_tracking_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-device-tracking"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_device_tracking_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalDeviceTrackingService:
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


def _make_registration_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "device_name": "Test Device",
        "manufacturer": "Test Manufacturer",
        "model_number": "TEST-100",
        "serial_number": "TST-2025-00001",
        "registered_by": "Test Engineer",
        "device_classification": "investigational",
    }
    defaults.update(overrides)
    return defaults


def _make_deployment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "device_id": "DEV-001",
        "site_id": "SITE-TEST-001",
        "deployment_status": "in_storage",
    }
    defaults.update(overrides)
    return defaults


def _make_maintenance_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "device_id": "DEV-001",
        "maintenance_type": "calibration",
        "scheduled_date": "2026-03-15T09:00:00Z",
        "performed_by": "Test Engineer",
    }
    defaults.update(overrides)
    return defaults


def _make_incident_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "device_id": "DEV-001",
        "site_id": "SITE-TEST-001",
        "incident_date": "2026-02-10T14:00:00Z",
        "description": "Test incident description for unit testing.",
        "reported_by": "Test Reporter",
        "incident_severity": "minor",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_device_registrations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_device_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-deployments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_maintenance_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/maintenance-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_device_incidents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# DEVICE REGISTRATION CRUD
# ===================================================================


class TestDeviceRegistrationCRUD:
    @pytest.mark.anyio
    async def test_list_device_registrations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_device_registration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations/DEV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEV-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_device_registration_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_device_registration(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/device-registrations", json=_make_registration_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DEV-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["device_name"] == "Test Device"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/device-registrations")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/device-registrations", json=_make_registration_create())
        resp2 = await client.get(f"{API_PREFIX}/device-registrations")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_device_registration(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/device-registrations/DEV-001",
            json={"firmware_version": "7.0.0", "notes": "Updated firmware"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["firmware_version"] == "7.0.0"
        assert data["notes"] == "Updated firmware"

    @pytest.mark.anyio
    async def test_update_device_registration_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/device-registrations/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device_registration(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/device-registrations/DEV-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/device-registrations/DEV-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device_registration_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/device-registrations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_device_classification(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/device-registrations", params={"device_classification": "class_ii"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["device_classification"] == "class_ii"


# ===================================================================
# DEVICE DEPLOYMENT CRUD
# ===================================================================


class TestDeviceDeploymentCRUD:
    @pytest.mark.anyio
    async def test_list_device_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-deployments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_device_deployment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-deployments/DDP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DDP-001"

    @pytest.mark.anyio
    async def test_get_device_deployment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-deployments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_device_deployment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/device-deployments", json=_make_deployment_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DDP-")
        assert data["deployment_status"] == "in_storage"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/device-deployments")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/device-deployments", json=_make_deployment_create())
        resp2 = await client.get(f"{API_PREFIX}/device-deployments")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_device_deployment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/device-deployments/DDP-001",
            json={"deployment_status": "deployed", "notes": "Redeployed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deployment_status"] == "deployed"
        assert data["notes"] == "Redeployed"

    @pytest.mark.anyio
    async def test_update_device_deployment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/device-deployments/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device_deployment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/device-deployments/DDP-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_device_deployment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/device-deployments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_deployment_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/device-deployments", params={"deployment_status": "deployed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["deployment_status"] == "deployed"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/device-deployments", params={"site_id": "SITE-HOU-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-HOU-001"


# ===================================================================
# MAINTENANCE LOG CRUD
# ===================================================================


class TestMaintenanceLogCRUD:
    @pytest.mark.anyio
    async def test_list_maintenance_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/maintenance-logs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_maintenance_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/maintenance-logs/MNT-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "MNT-001"

    @pytest.mark.anyio
    async def test_get_maintenance_log_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/maintenance-logs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_maintenance_log(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/maintenance-logs", json=_make_maintenance_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("MNT-")
        assert data["maintenance_type"] == "calibration"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/maintenance-logs")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/maintenance-logs", json=_make_maintenance_create())
        resp2 = await client.get(f"{API_PREFIX}/maintenance-logs")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_maintenance_log(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/maintenance-logs/MNT-001",
            json={"maintenance_result": "pass", "notes": "Re-verified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["maintenance_result"] == "pass"
        assert data["notes"] == "Re-verified"

    @pytest.mark.anyio
    async def test_update_maintenance_log_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/maintenance-logs/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_maintenance_log(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/maintenance-logs/MNT-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_maintenance_log_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/maintenance-logs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_maintenance_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/maintenance-logs", params={"maintenance_type": "calibration"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["maintenance_type"] == "calibration"

    @pytest.mark.anyio
    async def test_filter_by_maintenance_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/maintenance-logs", params={"maintenance_result": "pass"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["maintenance_result"] == "pass"


# ===================================================================
# DEVICE INCIDENT REPORT CRUD
# ===================================================================


class TestDeviceIncidentReportCRUD:
    @pytest.mark.anyio
    async def test_list_device_incidents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-incidents")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_device_incident(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-incidents/DIR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DIR-001"

    @pytest.mark.anyio
    async def test_get_device_incident_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-incidents/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_device_incident(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/device-incidents", json=_make_incident_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DIR-")
        assert data["incident_severity"] == "minor"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/device-incidents")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/device-incidents", json=_make_incident_create())
        resp2 = await client.get(f"{API_PREFIX}/device-incidents")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_device_incident(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/device-incidents/DIR-001",
            json={"root_cause": "Software bug", "notes": "Investigation complete"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause"] == "Software bug"
        assert data["notes"] == "Investigation complete"

    @pytest.mark.anyio
    async def test_update_device_incident_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/device-incidents/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device_incident(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/device-incidents/DIR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/device-incidents/DIR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device_incident_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/device-incidents/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_incident_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/device-incidents", params={"incident_severity": "minor"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["incident_severity"] == "minor"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/device-incidents", params={"site_id": "SITE-HOU-001"}
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
        assert "total_devices" in data
        assert "total_deployments" in data
        assert "total_maintenance_logs" in data
        assert "total_incidents" in data
        assert "maintenance_pass_rate" in data
        assert "patient_harm_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_devices(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_devices"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_deployments"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_maintenance_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_maintenance_logs"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_incidents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_incidents"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["devices_by_classification"], dict)
        assert isinstance(data["deployments_by_status"], dict)
        assert isinstance(data["maintenance_by_type"], dict)
        assert isinstance(data["incidents_by_severity"], dict)

    def test_metrics_service_level(self, svc: MedicalDeviceTrackingService):
        metrics = svc.get_metrics()
        assert metrics.total_devices == 12
        assert metrics.total_deployments == 12
        assert metrics.total_maintenance_logs == 12
        assert metrics.total_incidents == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_registration_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations/DEV-001")
        original = resp.json()
        original_name = original["device_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/device-registrations/DEV-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["device_name"] == original_name
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_deployment_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-deployments/DDP-001")
        original = resp.json()
        original_device = original["device_id"]

        resp2 = await client.put(
            f"{API_PREFIX}/device-deployments/DDP-001",
            json={"notes": "Updated deployment note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["device_id"] == original_device

    @pytest.mark.anyio
    async def test_update_maintenance_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/maintenance-logs/MNT-001")
        original = resp.json()
        original_type = original["maintenance_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/maintenance-logs/MNT-001",
            json={"notes": "Updated maintenance note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["maintenance_type"] == original_type

    @pytest.mark.anyio
    async def test_update_incident_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-incidents/DIR-001")
        original = resp.json()
        original_severity = original["incident_severity"]

        resp2 = await client.put(
            f"{API_PREFIX}/device-incidents/DIR-001",
            json={"notes": "Updated incident note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["incident_severity"] == original_severity


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_medical_device_tracking_service()
        svc2 = get_medical_device_tracking_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_medical_device_tracking_service()
        svc2 = reset_medical_device_tracking_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_device_tracking_service()
        svc.delete_device_registration("DEV-001")
        assert svc.get_device_registration("DEV-001") is None
        svc2 = reset_medical_device_tracking_service()
        assert svc2.get_device_registration("DEV-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_device_registrations_service(self, svc: MedicalDeviceTrackingService):
        items = svc.list_device_registrations()
        assert len(items) == 12

    def test_get_device_registration_service(self, svc: MedicalDeviceTrackingService):
        record = svc.get_device_registration("DEV-001")
        assert record is not None
        assert record.id == "DEV-001"

    def test_list_device_deployments_service(self, svc: MedicalDeviceTrackingService):
        items = svc.list_device_deployments()
        assert len(items) == 12

    def test_get_device_deployment_service(self, svc: MedicalDeviceTrackingService):
        record = svc.get_device_deployment("DDP-001")
        assert record is not None
        assert record.id == "DDP-001"

    def test_list_maintenance_logs_service(self, svc: MedicalDeviceTrackingService):
        items = svc.list_maintenance_logs()
        assert len(items) == 12

    def test_get_maintenance_log_service(self, svc: MedicalDeviceTrackingService):
        record = svc.get_maintenance_log("MNT-001")
        assert record is not None
        assert record.id == "MNT-001"

    def test_list_device_incident_reports_service(self, svc: MedicalDeviceTrackingService):
        items = svc.list_device_incident_reports()
        assert len(items) == 12

    def test_get_device_incident_report_service(self, svc: MedicalDeviceTrackingService):
        record = svc.get_device_incident_report("DIR-001")
        assert record is not None
        assert record.id == "DIR-001"

    def test_delete_device_registration_service(self, svc: MedicalDeviceTrackingService):
        assert svc.delete_device_registration("DEV-001") is True
        assert svc.get_device_registration("DEV-001") is None

    def test_delete_nonexistent_returns_false(self, svc: MedicalDeviceTrackingService):
        assert svc.delete_device_registration("NONEXISTENT") is False

    def test_filter_registration_by_trial(self, svc: MedicalDeviceTrackingService):
        items = svc.list_device_registrations(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_deployment_by_status(self, svc: MedicalDeviceTrackingService):
        items = svc.list_device_deployments(deployment_status=DeploymentStatus.DEPLOYED)
        for item in items:
            assert item.deployment_status == DeploymentStatus.DEPLOYED

    def test_filter_maintenance_by_type(self, svc: MedicalDeviceTrackingService):
        items = svc.list_maintenance_logs(maintenance_type=MaintenanceType.CALIBRATION)
        for item in items:
            assert item.maintenance_type == MaintenanceType.CALIBRATION

    def test_filter_incident_by_severity(self, svc: MedicalDeviceTrackingService):
        items = svc.list_device_incident_reports(incident_severity=IncidentSeverity.MINOR)
        for item in items:
            assert item.incident_severity == IncidentSeverity.MINOR


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_registrations(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/device-registrations",
                json=_make_registration_create(serial_number=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/device-registrations")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_incidents(self, client: AsyncClient):
        for incident_id in ["DIR-001", "DIR-002", "DIR-003"]:
            resp = await client.delete(f"{API_PREFIX}/device-incidents/{incident_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/device-incidents")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_registration_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations/DEV-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "device_name", "manufacturer", "model_number",
                       "serial_number", "device_classification", "registered_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_deployment_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-deployments/DDP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "device_id", "site_id", "deployment_status",
                       "subjects_using", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_maintenance_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/maintenance-logs/MNT-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "device_id", "maintenance_type",
                       "maintenance_result", "performed_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_incident_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-incidents/DIR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "device_id", "site_id", "incident_severity",
                       "description", "reported_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/device-registrations")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
