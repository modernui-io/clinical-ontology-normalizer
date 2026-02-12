"""Tests for Decentralized Trial Operations (DCT-OPS).

Covers:
- Seed data verification (visits, devices, sessions, eSource)
- Remote visit CRUD (create, read, update, delete, list, filter)
- Wearable device CRUD (create, read, update, delete, list, filter)
- Telemedicine session CRUD (create, read, update, delete, list, filter)
- eSource capture CRUD (create, read, update, delete, list, filter)
- DCT metrics computation
- Auto-verified date on eSource verification
- Error handling (404s, not-found entities)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.decentralized_trials import (
    DataQuality,
    DeviceStatus,
    DeviceType,
    SessionPlatform,
    VisitStatus,
    VisitType,
)
from app.services.decentralized_trials_service import (
    DecentralizedTrialsService,
    get_decentralized_trials_service,
    reset_decentralized_trials_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/decentralized-trials"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_decentralized_trials_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DecentralizedTrialsService:
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


def _make_visit_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-9001",
        "site_id": "SITE-101",
        "visit_type": "home_nursing",
        "scheduled_date": (now + timedelta(days=7)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_device_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "subject_id": "SUBJ-9002",
        "device_type": "smartwatch",
        "manufacturer": "Apple",
        "model": "Watch Ultra 3",
        "serial_number": "APL-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_session_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "subject_id": "SUBJ-9003",
        "platform": "zoom_healthcare",
        "scheduled_date": (now + timedelta(days=5)).isoformat(),
        "provider_name": "Dr. Test Provider",
        "provider_role": "Investigator",
    }
    defaults.update(overrides)
    return defaults


def _make_esource_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-9001",
        "data_type": "blood_pressure",
        "value": "120/80",
        "unit": "mmHg",
        "source_system": "Test System",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_visits_count(self, svc: DecentralizedTrialsService):
        visits = svc.list_visits()
        assert len(visits) == 12

    def test_seed_visits_have_multiple_types(self, svc: DecentralizedTrialsService):
        visits = svc.list_visits()
        types = {v.visit_type for v in visits}
        assert VisitType.HOME_NURSING in types
        assert VisitType.TELEMEDICINE in types
        assert VisitType.LOCAL_LAB in types

    def test_seed_visits_have_multiple_statuses(self, svc: DecentralizedTrialsService):
        visits = svc.list_visits()
        statuses = {v.status for v in visits}
        assert VisitStatus.COMPLETED in statuses
        assert VisitStatus.SCHEDULED in statuses

    def test_seed_visits_across_trials(self, svc: DecentralizedTrialsService):
        trials = {v.trial_id for v in svc.list_visits()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_devices_count(self, svc: DecentralizedTrialsService):
        devices = svc.list_devices()
        assert len(devices) == 12

    def test_seed_devices_have_multiple_types(self, svc: DecentralizedTrialsService):
        devices = svc.list_devices()
        types = {d.device_type for d in devices}
        assert len(types) >= 5

    def test_seed_devices_have_multiple_statuses(self, svc: DecentralizedTrialsService):
        devices = svc.list_devices()
        statuses = {d.status for d in devices}
        assert DeviceStatus.COLLECTING_DATA in statuses
        assert DeviceStatus.PROVISIONED in statuses

    def test_seed_sessions_count(self, svc: DecentralizedTrialsService):
        sessions = svc.list_sessions()
        assert len(sessions) == 12

    def test_seed_sessions_have_multiple_platforms(self, svc: DecentralizedTrialsService):
        sessions = svc.list_sessions()
        platforms = {s.platform for s in sessions}
        assert len(platforms) >= 3

    def test_seed_esource_count(self, svc: DecentralizedTrialsService):
        esource = svc.list_esource()
        assert len(esource) == 12

    def test_seed_esource_have_multiple_data_types(self, svc: DecentralizedTrialsService):
        esource = svc.list_esource()
        data_types = {e.data_type for e in esource}
        assert len(data_types) >= 5

    def test_seed_esource_have_verified_and_unverified(self, svc: DecentralizedTrialsService):
        esource = svc.list_esource()
        verified = [e for e in esource if e.verified]
        unverified = [e for e in esource if not e.verified]
        assert len(verified) > 0
        assert len(unverified) > 0


# =====================================================================
# REMOTE VISIT CRUD
# =====================================================================


class TestRemoteVisitCrud:
    """Test remote visit create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_visits_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_visits_filter_visit_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"visit_type": "home_nursing"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["visit_type"] == "home_nursing"

    @pytest.mark.anyio
    async def test_list_visits_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_visits_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"subject_id": "SUBJ-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_get_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RV-001"
        assert data["visit_type"] == "home_nursing"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_visit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit(self, client: AsyncClient):
        payload = _make_visit_create()
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["subject_id"] == "SUBJ-9001"
        assert data["visit_type"] == "home_nursing"
        assert data["status"] == "scheduled"
        assert data["id"].startswith("RV-")

    @pytest.mark.anyio
    async def test_create_visit_with_procedures(self, client: AsyncClient):
        payload = _make_visit_create(procedures=["vitals", "blood_draw"])
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["procedures"] == ["vitals", "blood_draw"]

    @pytest.mark.anyio
    async def test_create_visit_with_provider(self, client: AsyncClient):
        payload = _make_visit_create(
            provider_name="Test Nurse",
            provider_organization="Test Health",
        )
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_name"] == "Test Nurse"
        assert data["provider_organization"] == "Test Health"

    @pytest.mark.anyio
    async def test_update_visit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/RV-008",
            json={"status": "confirmed", "notes": "Patient confirmed attendance"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["notes"] == "Patient confirmed attendance"

    @pytest.mark.anyio
    async def test_update_visit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/RV-NONEXISTENT",
            json={"status": "confirmed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/RV-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/visits/RV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/RV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_visit_sorted_by_scheduled_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        data = resp.json()
        dates = [item["scheduled_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_list_visits_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits",
            params={"trial_id": EYLEA_TRIAL, "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "completed"


# =====================================================================
# WEARABLE DEVICE CRUD
# =====================================================================


class TestWearableDeviceCrud:
    """Test wearable device create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_devices(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_devices_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_devices_filter_device_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/devices", params={"device_type": "blood_pressure_monitor"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["device_type"] == "blood_pressure_monitor"

    @pytest.mark.anyio
    async def test_list_devices_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/devices", params={"device_status": "collecting_data"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "collecting_data"

    @pytest.mark.anyio
    async def test_list_devices_filter_subject(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/devices", params={"subject_id": "SUBJ-1001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_get_device(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEV-001"
        assert data["device_type"] == "blood_pressure_monitor"
        assert data["manufacturer"] == "Omron"

    @pytest.mark.anyio
    async def test_get_device_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_device(self, client: AsyncClient):
        payload = _make_device_create()
        resp = await client.post(f"{API_PREFIX}/devices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["device_type"] == "smartwatch"
        assert data["status"] == "provisioned"
        assert data["id"].startswith("DEV-")
        assert data["data_points_collected"] == 0

    @pytest.mark.anyio
    async def test_create_device_with_firmware(self, client: AsyncClient):
        payload = _make_device_create(firmware_version="1.0.0")
        resp = await client.post(f"{API_PREFIX}/devices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["firmware_version"] == "1.0.0"

    @pytest.mark.anyio
    async def test_update_device(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/devices/DEV-009",
            json={"status": "shipped", "firmware_version": "2.1.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "shipped"
        assert data["firmware_version"] == "2.1.0"

    @pytest.mark.anyio
    async def test_update_device_compliance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/devices/DEV-001",
            json={"compliance_rate_pct": 98.5, "data_points_collected": 2000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_rate_pct"] == 98.5
        assert data["data_points_collected"] == 2000

    @pytest.mark.anyio
    async def test_update_device_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/devices/DEV-NONEXISTENT",
            json={"status": "activated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/devices/DEV-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/devices/DEV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_device_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/devices/DEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_devices_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/devices",
            params={"trial_id": EYLEA_TRIAL, "device_status": "collecting_data"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "collecting_data"

    def test_device_data_quality_values(self, svc: DecentralizedTrialsService):
        device = svc.get_device("DEV-001")
        assert device is not None
        assert device.data_quality == DataQuality.EXCELLENT

    def test_device_compliance_rate(self, svc: DecentralizedTrialsService):
        device = svc.get_device("DEV-001")
        assert device is not None
        assert device.compliance_rate_pct is not None
        assert 0 <= device.compliance_rate_pct <= 100


# =====================================================================
# TELEMEDICINE SESSION CRUD
# =====================================================================


class TestTelemedicineSessionCrud:
    """Test telemedicine session create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sessions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_sessions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sessions_filter_platform(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sessions", params={"platform": "zoom_healthcare"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["platform"] == "zoom_healthcare"

    @pytest.mark.anyio
    async def test_list_sessions_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_sessions_filter_subject(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sessions", params={"subject_id": "SUBJ-1001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_get_session(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TMS-001"
        assert data["platform"] == "zoom_healthcare"
        assert data["status"] == "completed"
        assert data["recording_available"] is True

    @pytest.mark.anyio
    async def test_get_session_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_session(self, client: AsyncClient):
        payload = _make_session_create()
        resp = await client.post(f"{API_PREFIX}/sessions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["platform"] == "zoom_healthcare"
        assert data["status"] == "scheduled"
        assert data["id"].startswith("TMS-")
        assert data["recording_available"] is False

    @pytest.mark.anyio
    async def test_create_session_with_visit_id(self, client: AsyncClient):
        payload = _make_session_create(visit_id="RV-009")
        resp = await client.post(f"{API_PREFIX}/sessions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["visit_id"] == "RV-009"

    @pytest.mark.anyio
    async def test_update_session(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/sessions/TMS-007",
            json={
                "status": "in_progress",
                "actual_start": now.isoformat(),
                "consent_documented": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["consent_documented"] is True

    @pytest.mark.anyio
    async def test_update_session_clinical_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sessions/TMS-008",
            json={"clinical_notes": "Test clinical notes added"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["clinical_notes"] == "Test clinical notes added"

    @pytest.mark.anyio
    async def test_update_session_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sessions/TMS-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_session(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sessions/TMS-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sessions/TMS-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_session_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sessions/TMS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_sessions_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sessions",
            params={"trial_id": EYLEA_TRIAL, "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "completed"

    def test_session_connection_quality(self, svc: DecentralizedTrialsService):
        session = svc.get_session("TMS-001")
        assert session is not None
        assert session.connection_quality == DataQuality.EXCELLENT

    def test_session_duration(self, svc: DecentralizedTrialsService):
        session = svc.get_session("TMS-001")
        assert session is not None
        assert session.duration_minutes == 25


# =====================================================================
# ESOURCE CAPTURE CRUD
# =====================================================================


class TestESourceCaptureCrud:
    """Test eSource capture create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_esource(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_esource_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_esource_filter_subject(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/esource", params={"subject_id": "SUBJ-1001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_list_esource_filter_data_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/esource", params={"data_type": "blood_pressure"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["data_type"] == "blood_pressure"

    @pytest.mark.anyio
    async def test_list_esource_filter_data_quality(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/esource", params={"data_quality": "excellent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["data_quality"] == "excellent"

    @pytest.mark.anyio
    async def test_get_esource(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource/ESC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ESC-001"
        assert data["data_type"] == "blood_pressure"
        assert data["value"] == "128/82"
        assert data["verified"] is True

    @pytest.mark.anyio
    async def test_get_esource_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource/ESC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_esource(self, client: AsyncClient):
        payload = _make_esource_create()
        resp = await client.post(f"{API_PREFIX}/esource", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["data_type"] == "blood_pressure"
        assert data["value"] == "120/80"
        assert data["verified"] is False
        assert data["id"].startswith("ESC-")

    @pytest.mark.anyio
    async def test_create_esource_with_device(self, client: AsyncClient):
        payload = _make_esource_create(device_id="DEV-001")
        resp = await client.post(f"{API_PREFIX}/esource", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_id"] == "DEV-001"

    @pytest.mark.anyio
    async def test_create_esource_with_visit(self, client: AsyncClient):
        payload = _make_esource_create(visit_id="RV-001")
        resp = await client.post(f"{API_PREFIX}/esource", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["visit_id"] == "RV-001"

    @pytest.mark.anyio
    async def test_update_esource(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/esource/ESC-004",
            json={"data_quality": "excellent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_quality"] == "excellent"

    @pytest.mark.anyio
    async def test_update_esource_verify(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/esource/ESC-004",
            json={"verified": True, "verified_by": "Dr. Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["verified_by"] == "Dr. Reviewer"
        assert data["verified_date"] is not None

    @pytest.mark.anyio
    async def test_update_esource_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/esource/ESC-NONEXISTENT",
            json={"data_quality": "good"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_esource(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/esource/ESC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/esource/ESC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_esource_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/esource/ESC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_esource_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/esource",
            params={"trial_id": EYLEA_TRIAL, "data_quality": "excellent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["data_quality"] == "excellent"


# =====================================================================
# ESOURCE VERIFICATION LOGIC
# =====================================================================


class TestESourceVerification:
    """Test eSource capture verification auto-date logic."""

    def test_verify_auto_sets_date(self, svc: DecentralizedTrialsService):
        from app.schemas.decentralized_trials import ESourceCaptureUpdate

        capture = svc.get_esource("ESC-004")
        assert capture is not None
        assert capture.verified is False
        assert capture.verified_date is None

        updated = svc.update_esource(
            "ESC-004",
            ESourceCaptureUpdate(verified=True, verified_by="Dr. Test"),
        )
        assert updated is not None
        assert updated.verified is True
        assert updated.verified_date is not None

    def test_already_verified_no_date_change(self, svc: DecentralizedTrialsService):
        from app.schemas.decentralized_trials import ESourceCaptureUpdate

        capture = svc.get_esource("ESC-001")
        assert capture is not None
        assert capture.verified is True
        original_date = capture.verified_date

        updated = svc.update_esource(
            "ESC-001",
            ESourceCaptureUpdate(data_quality=DataQuality.GOOD),
        )
        assert updated is not None
        assert updated.verified_date == original_date

    def test_unverified_has_no_date(self, svc: DecentralizedTrialsService):
        capture = svc.get_esource("ESC-004")
        assert capture is not None
        assert capture.verified is False
        assert capture.verified_date is None


# =====================================================================
# DCT METRICS
# =====================================================================


class TestDCTMetrics:
    """Test DCT metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_remote_visits"] == 12
        assert data["total_devices"] == 12
        assert data["total_telemedicine_sessions"] == 12
        assert data["total_esource_captures"] == 12

    @pytest.mark.anyio
    async def test_metrics_visit_completion_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["visit_completion_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_avg_device_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["avg_device_compliance_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_avg_session_duration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_session_duration_minutes"] > 0

    @pytest.mark.anyio
    async def test_metrics_verified_captures(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["verified_captures"] >= 0
        assert data["verified_captures"] <= data["total_esource_captures"]

    def test_metrics_visits_by_type(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.visits_by_type.values())
        assert total_by_type == metrics.total_remote_visits

    def test_metrics_visits_by_status(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.visits_by_status.values())
        assert total_by_status == metrics.total_remote_visits

    def test_metrics_devices_by_type(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.devices_by_type.values())
        assert total_by_type == metrics.total_devices

    def test_metrics_devices_by_status(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.devices_by_status.values())
        assert total_by_status == metrics.total_devices

    def test_metrics_sessions_by_status(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.sessions_by_status.values())
        assert total_by_status == metrics.total_telemedicine_sessions

    def test_metrics_data_quality_distribution(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        total_by_quality = sum(metrics.data_quality_distribution.values())
        assert total_by_quality == metrics.total_esource_captures

    def test_metrics_visit_completion_rate_calculation(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        visits = svc.list_visits()
        completed = sum(1 for v in visits if v.status == VisitStatus.COMPLETED)
        expected_rate = round((completed / len(visits)) * 100, 1)
        assert metrics.visit_completion_rate == expected_rate

    def test_metrics_avg_compliance_calculation(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        devices = svc.list_devices()
        compliance_values = [
            d.compliance_rate_pct for d in devices if d.compliance_rate_pct is not None
        ]
        expected_avg = round(sum(compliance_values) / len(compliance_values), 1)
        assert metrics.avg_device_compliance_pct == expected_avg

    def test_metrics_avg_session_duration_calculation(self, svc: DecentralizedTrialsService):
        metrics = svc.get_metrics()
        sessions = svc.list_sessions()
        durations = [
            s.duration_minutes
            for s in sessions
            if s.status == VisitStatus.COMPLETED and s.duration_minutes is not None
        ]
        expected_avg = round(sum(durations) / len(durations), 1)
        assert metrics.avg_session_duration_minutes == expected_avg


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_decentralized_trials_service()
        svc2 = get_decentralized_trials_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_decentralized_trials_service()
        svc2 = reset_decentralized_trials_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_decentralized_trials_service()
        svc.delete_visit("RV-001")
        assert svc.get_visit("RV-001") is None
        svc2 = reset_decentralized_trials_service()
        assert svc2.get_visit("RV-001") is not None


# =====================================================================
# VISIT TYPE & STATUS ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_visit_types_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        data = resp.json()
        types = {item["visit_type"] for item in data["items"]}
        assert "home_nursing" in types
        assert "telemedicine" in types
        assert "local_lab" in types

    @pytest.mark.anyio
    async def test_visit_statuses_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "scheduled" in statuses

    @pytest.mark.anyio
    async def test_device_types_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices")
        data = resp.json()
        types = {item["device_type"] for item in data["items"]}
        assert "blood_pressure_monitor" in types
        assert "ecg_patch" in types

    @pytest.mark.anyio
    async def test_device_statuses_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "collecting_data" in statuses
        assert "provisioned" in statuses

    @pytest.mark.anyio
    async def test_session_platforms_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions")
        data = resp.json()
        platforms = {item["platform"] for item in data["items"]}
        assert "zoom_healthcare" in platforms
        assert "doxy_me" in platforms

    @pytest.mark.anyio
    async def test_data_quality_in_esource(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource")
        data = resp.json()
        qualities = {item["data_quality"] for item in data["items"]}
        assert "excellent" in qualities
        assert "good" in qualities


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_visits_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_devices_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_sessions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_esource_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_visit_minimal_fields(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": EYLEA_TRIAL,
            "subject_id": "SUBJ-MIN",
            "site_id": "SITE-101",
            "visit_type": "local_lab",
            "scheduled_date": (now + timedelta(days=1)).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_name"] is None
        assert data["procedures"] == []

    @pytest.mark.anyio
    async def test_create_device_minimal_fields(self, client: AsyncClient):
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "subject_id": "SUBJ-MIN",
            "device_type": "pulse_oximeter",
            "manufacturer": "TestCo",
            "model": "TestModel",
            "serial_number": "TEST-001",
        }
        resp = await client.post(f"{API_PREFIX}/devices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["firmware_version"] is None
        assert data["battery_level_pct"] is None

    @pytest.mark.anyio
    async def test_create_session_minimal_fields(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "subject_id": "SUBJ-MIN",
            "platform": "phone_call",
            "scheduled_date": (now + timedelta(days=2)).isoformat(),
            "provider_name": "Dr. Minimal",
            "provider_role": "Coordinator",
        }
        resp = await client.post(f"{API_PREFIX}/sessions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["visit_id"] is None
        assert data["clinical_notes"] is None

    @pytest.mark.anyio
    async def test_create_esource_minimal_fields(self, client: AsyncClient):
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "subject_id": "SUBJ-MIN",
            "data_type": "temperature",
            "value": "37.2",
            "source_system": "Manual Entry",
        }
        resp = await client.post(f"{API_PREFIX}/esource", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit"] is None
        assert data["visit_id"] is None
        assert data["device_id"] is None

    @pytest.mark.anyio
    async def test_update_visit_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/RV-009",
            json={"notes": "Only updating notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Only updating notes"
        assert data["status"] == "confirmed"  # unchanged

    @pytest.mark.anyio
    async def test_update_device_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/devices/DEV-001",
            json={"battery_level_pct": 50.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["battery_level_pct"] == 50.0
        assert data["status"] == "collecting_data"  # unchanged

    @pytest.mark.anyio
    async def test_update_session_recording(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sessions/TMS-008",
            json={"recording_available": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recording_available"] is True

    @pytest.mark.anyio
    async def test_visit_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-001")
        data = resp.json()
        required_fields = [
            "id", "trial_id", "subject_id", "site_id", "visit_type",
            "scheduled_date", "status", "created_at",
        ]
        for field in required_fields:
            assert field in data

    @pytest.mark.anyio
    async def test_device_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-001")
        data = resp.json()
        required_fields = [
            "id", "trial_id", "subject_id", "device_type", "manufacturer",
            "model", "serial_number", "status", "assigned_date",
        ]
        for field in required_fields:
            assert field in data

    @pytest.mark.anyio
    async def test_session_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-001")
        data = resp.json()
        required_fields = [
            "id", "trial_id", "subject_id", "platform", "scheduled_date",
            "provider_name", "provider_role", "status",
        ]
        for field in required_fields:
            assert field in data

    @pytest.mark.anyio
    async def test_esource_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource/ESC-001")
        data = resp.json()
        required_fields = [
            "id", "trial_id", "subject_id", "data_type", "capture_date",
            "value", "data_quality", "source_system", "verified",
        ]
        for field in required_fields:
            assert field in data

    @pytest.mark.anyio
    async def test_create_and_get_visit_roundtrip(self, client: AsyncClient):
        payload = _make_visit_create()
        create_resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        assert create_resp.status_code == 201
        visit_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/visits/{visit_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == visit_id

    @pytest.mark.anyio
    async def test_create_and_get_device_roundtrip(self, client: AsyncClient):
        payload = _make_device_create()
        create_resp = await client.post(f"{API_PREFIX}/devices", json=payload)
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/devices/{device_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == device_id

    @pytest.mark.anyio
    async def test_create_and_get_session_roundtrip(self, client: AsyncClient):
        payload = _make_session_create()
        create_resp = await client.post(f"{API_PREFIX}/sessions", json=payload)
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/sessions/{session_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == session_id

    @pytest.mark.anyio
    async def test_create_and_get_esource_roundtrip(self, client: AsyncClient):
        payload = _make_esource_create()
        create_resp = await client.post(f"{API_PREFIX}/esource", json=payload)
        assert create_resp.status_code == 201
        esource_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/esource/{esource_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == esource_id

    @pytest.mark.anyio
    async def test_create_and_delete_visit(self, client: AsyncClient):
        payload = _make_visit_create()
        create_resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        visit_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{API_PREFIX}/visits/{visit_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/visits/{visit_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_update_visit(self, client: AsyncClient):
        payload = _make_visit_create()
        create_resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        visit_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"{API_PREFIX}/visits/{visit_id}",
            json={"status": "confirmed"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "confirmed"

    @pytest.mark.anyio
    async def test_create_multiple_visits(self, client: AsyncClient):
        for i in range(3):
            payload = _make_visit_create(subject_id=f"SUBJ-MULTI-{i}")
            resp = await client.post(f"{API_PREFIX}/visits", json=payload)
            assert resp.status_code == 201

        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_create_multiple_devices(self, client: AsyncClient):
        for i in range(3):
            payload = _make_device_create(
                serial_number=f"MULTI-{i}",
                subject_id=f"SUBJ-MULTI-{i}",
            )
            resp = await client.post(f"{API_PREFIX}/devices", json=payload)
            assert resp.status_code == 201

        resp = await client.get(f"{API_PREFIX}/devices")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_filter_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_filter_nonexistent_subject(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/devices",
            params={"subject_id": "nonexistent-subject"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# =====================================================================
# DETAILED ENTITY PROPERTIES
# =====================================================================


class TestDetailedProperties:
    """Test detailed properties of seeded entities."""

    @pytest.mark.anyio
    async def test_completed_visit_has_actual_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-001")
        data = resp.json()
        assert data["actual_date"] is not None
        assert data["duration_minutes"] == 45

    @pytest.mark.anyio
    async def test_scheduled_visit_no_actual_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-008")
        data = resp.json()
        assert data["actual_date"] is None
        assert data["duration_minutes"] is None

    @pytest.mark.anyio
    async def test_collecting_device_has_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-001")
        data = resp.json()
        assert data["data_points_collected"] > 0
        assert data["battery_level_pct"] is not None
        assert data["compliance_rate_pct"] is not None

    @pytest.mark.anyio
    async def test_provisioned_device_no_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-009")
        data = resp.json()
        assert data["data_points_collected"] == 0
        assert data["activation_date"] is None
        assert data["compliance_rate_pct"] is None

    @pytest.mark.anyio
    async def test_completed_session_has_duration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-001")
        data = resp.json()
        assert data["duration_minutes"] == 25
        assert data["actual_start"] is not None
        assert data["actual_end"] is not None

    @pytest.mark.anyio
    async def test_scheduled_session_no_duration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-008")
        data = resp.json()
        assert data["duration_minutes"] is None
        assert data["actual_start"] is None

    @pytest.mark.anyio
    async def test_verified_esource_has_verifier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource/ESC-001")
        data = resp.json()
        assert data["verified"] is True
        assert data["verified_by"] is not None
        assert data["verified_date"] is not None

    @pytest.mark.anyio
    async def test_unverified_esource_no_verifier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/esource/ESC-004")
        data = resp.json()
        assert data["verified"] is False
        assert data["verified_by"] is None
        assert data["verified_date"] is None

    @pytest.mark.anyio
    async def test_unusable_data_quality_device(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-012")
        data = resp.json()
        assert data["data_quality"] == "unusable"
        assert data["status"] == "malfunctioning"

    @pytest.mark.anyio
    async def test_cancelled_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-011")
        data = resp.json()
        assert data["status"] == "cancelled"
        assert "reschedule" in data["notes"].lower()

    @pytest.mark.anyio
    async def test_no_show_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-012")
        data = resp.json()
        assert data["status"] == "no_show"

    @pytest.mark.anyio
    async def test_self_administered_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-007")
        data = resp.json()
        assert data["visit_type"] == "self_administered"
        assert data["provider_name"] is None

    @pytest.mark.anyio
    async def test_mobile_unit_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/RV-006")
        data = resp.json()
        assert data["visit_type"] == "mobile_unit"
        assert data["duration_minutes"] == 75

    @pytest.mark.anyio
    async def test_phone_call_session(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-005")
        data = resp.json()
        assert data["platform"] == "phone_call"
        assert data["recording_available"] is False

    @pytest.mark.anyio
    async def test_custom_platform_session(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sessions/TMS-006")
        data = resp.json()
        assert data["platform"] == "custom_platform"

    @pytest.mark.anyio
    async def test_returned_device(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-011")
        data = resp.json()
        assert data["status"] == "returned"

    @pytest.mark.anyio
    async def test_deactivated_device(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/devices/DEV-010")
        data = resp.json()
        assert data["status"] == "deactivated"
        assert data["data_quality"] == "poor"
