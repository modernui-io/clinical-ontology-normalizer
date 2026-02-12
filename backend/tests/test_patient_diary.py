"""Tests for Patient Diary / eDiary Management (EDIARY-MGT).

Covers:
- Seed data verification (diary entries, symptom records, schedules, compliance, validations)
- Diary entry CRUD (create, read, update, delete, list, filter by trial/subject/status/type)
- Symptom record CRUD (create, read, update, delete, list, filter by trial/subject/entry)
- Diary schedule CRUD (create, read, update, delete, list, filter by trial/type/active)
- Diary compliance CRUD (create, read, update, delete, list, filter by trial/subject/level)
- Diary validation CRUD (create, read, update, delete, list, filter by trial/entry/status)
- Metrics computation
- Error handling (404s, validation errors 422)
- Singleton pattern behavior
- Demo data seeding
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.patient_diary import (
    ComplianceLevel,
    DiaryType,
    EntryStatus,
    ValidationStatus,
)
from app.services.patient_diary_service import (
    PatientDiaryService,
    get_patient_diary_service,
    reset_patient_diary_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-diary"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_diary_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientDiaryService:
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


def _make_entry_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-9001",
        "site_id": "SITE-101",
        "diary_type": "symptom",
        "form_version": "v1.0",
    }
    defaults.update(overrides)
    return defaults


def _make_symptom_create(**overrides) -> dict:
    defaults = {
        "entry_id": "DE-001",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-1001",
        "symptom_name": "Nausea",
        "severity_score": 4,
    }
    defaults.update(overrides)
    return defaults


def _make_schedule_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "diary_type": "symptom",
        "form_name": "Test Diary Form",
        "frequency": "daily",
        "created_by": "Dr. Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-9001",
        "site_id": "SITE-101",
        "period_start": (now - timedelta(days=30)).isoformat(),
        "period_end": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_validation_create(**overrides) -> dict:
    defaults = {
        "entry_id": "DE-001",
        "trial_id": EYLEA_TRIAL,
        "total_checks": 10,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_diary_entries_count(self, svc: PatientDiaryService):
        entries = svc.list_diary_entries()
        assert len(entries) == 12

    def test_seed_symptom_records_count(self, svc: PatientDiaryService):
        records = svc.list_symptom_records()
        assert len(records) == 10

    def test_seed_diary_schedules_count(self, svc: PatientDiaryService):
        schedules = svc.list_diary_schedules()
        assert len(schedules) == 10

    def test_seed_diary_compliance_count(self, svc: PatientDiaryService):
        compliance = svc.list_diary_compliance()
        assert len(compliance) == 10

    def test_seed_diary_validations_count(self, svc: PatientDiaryService):
        validations = svc.list_diary_validations()
        assert len(validations) == 10

    def test_seed_entries_span_all_trials(self, svc: PatientDiaryService):
        entries = svc.list_diary_entries()
        trial_ids = {e.trial_id for e in entries}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_entries_have_multiple_types(self, svc: PatientDiaryService):
        entries = svc.list_diary_entries()
        types = {e.diary_type for e in entries}
        assert len(types) >= 5

    def test_seed_entries_have_multiple_statuses(self, svc: PatientDiaryService):
        entries = svc.list_diary_entries()
        statuses = {e.status for e in entries}
        assert EntryStatus.COMPLETED in statuses
        assert EntryStatus.PENDING in statuses
        assert EntryStatus.MISSED in statuses

    def test_seed_compliance_has_multiple_levels(self, svc: PatientDiaryService):
        compliance = svc.list_diary_compliance()
        levels = {c.compliance_level for c in compliance}
        assert ComplianceLevel.EXCELLENT in levels
        assert ComplianceLevel.GOOD in levels
        assert ComplianceLevel.POOR in levels
        assert ComplianceLevel.NON_COMPLIANT in levels

    def test_seed_validations_have_multiple_statuses(self, svc: PatientDiaryService):
        validations = svc.list_diary_validations()
        statuses = {v.validation_status for v in validations}
        assert ValidationStatus.VALID in statuses
        assert ValidationStatus.WARNINGS in statuses
        assert ValidationStatus.ERRORS in statuses
        assert ValidationStatus.PENDING_REVIEW in statuses


# =====================================================================
# DIARY ENTRY CRUD
# =====================================================================


class TestDiaryEntryCrud:
    """Test diary entry CRUD operations."""

    @pytest.mark.anyio
    async def test_list_entries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_entries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_entries_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"subject_id": "SUBJ-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_list_entries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_entries_filter_diary_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"diary_type": "symptom"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["diary_type"] == "symptom"

    @pytest.mark.anyio
    async def test_get_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries/DE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DE-001"
        assert data["diary_type"] == "symptom"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries/DE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_entry(self, client: AsyncClient):
        payload = _make_entry_create()
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["subject_id"] == "SUBJ-9001"
        assert data["status"] == "pending"
        assert data["id"].startswith("DE-")

    @pytest.mark.anyio
    async def test_create_entry_with_device(self, client: AsyncClient):
        payload = _make_entry_create(device_type="iPhone 16")
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_type"] == "iPhone 16"

    @pytest.mark.anyio
    async def test_update_entry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/DE-011",
            json={"status": "completed", "validated": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["validated"] is True
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_entry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/DE-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_entry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/entries/DE-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/entries/DE-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_entry_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/entries/DE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_entry_invalid_type(self, client: AsyncClient):
        payload = _make_entry_create(diary_type="invalid_type")
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 422


# =====================================================================
# SYMPTOM RECORD CRUD
# =====================================================================


class TestSymptomRecordCrud:
    """Test symptom record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_symptoms(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_symptoms_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_symptoms_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms", params={"subject_id": "SUBJ-2001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-2001"

    @pytest.mark.anyio
    async def test_list_symptoms_filter_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms", params={"entry_id": "DE-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["entry_id"] == "DE-001"

    @pytest.mark.anyio
    async def test_get_symptom(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms/SR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SR-001"
        assert data["symptom_name"] == "Headache"

    @pytest.mark.anyio
    async def test_get_symptom_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms/SR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_symptom(self, client: AsyncClient):
        payload = _make_symptom_create()
        resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["symptom_name"] == "Nausea"
        assert data["severity_score"] == 4
        assert data["id"].startswith("SR-")

    @pytest.mark.anyio
    async def test_create_symptom_invalid_severity(self, client: AsyncClient):
        payload = _make_symptom_create(severity_score=15)
        resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_symptom(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/symptoms/SR-004",
            json={"reported_to_site": True, "ae_reference": "AE-0099"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reported_to_site"] is True
        assert data["ae_reference"] == "AE-0099"

    @pytest.mark.anyio
    async def test_update_symptom_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/symptoms/SR-NONEXISTENT",
            json={"reported_to_site": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_symptom(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/symptoms/SR-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/symptoms/SR-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_symptom_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/symptoms/SR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DIARY SCHEDULE CRUD
# =====================================================================


class TestDiaryScheduleCrud:
    """Test diary schedule CRUD operations."""

    @pytest.mark.anyio
    async def test_list_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_schedules_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_schedules_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"diary_type": "symptom"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["diary_type"] == "symptom"

    @pytest.mark.anyio
    async def test_list_schedules_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"is_active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 9  # DS-010 is inactive
        for item in data["items"]:
            assert item["is_active"] is True

    @pytest.mark.anyio
    async def test_get_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules/DS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DS-001"
        assert data["form_name"] == "Daily Symptom Diary"

    @pytest.mark.anyio
    async def test_get_schedule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules/DS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_schedule(self, client: AsyncClient):
        payload = _make_schedule_create()
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["form_name"] == "Test Diary Form"
        assert data["is_active"] is True
        assert data["id"].startswith("DS-")

    @pytest.mark.anyio
    async def test_update_schedule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/schedules/DS-010",
            json={"is_active": True, "reminder_enabled": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True
        assert data["reminder_enabled"] is True

    @pytest.mark.anyio
    async def test_update_schedule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/schedules/DS-NONEXISTENT",
            json={"is_active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_schedule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/schedules/DS-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/schedules/DS-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_schedule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/schedules/DS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DIARY COMPLIANCE CRUD
# =====================================================================


class TestDiaryComplianceCrud:
    """Test diary compliance CRUD operations."""

    @pytest.mark.anyio
    async def test_list_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_compliance_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_compliance_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"subject_id": "SUBJ-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_list_compliance_filter_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"compliance_level": "excellent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["compliance_level"] == "excellent"

    @pytest.mark.anyio
    async def test_get_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/DC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DC-001"
        assert data["compliance_level"] == "excellent"

    @pytest.mark.anyio
    async def test_get_compliance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/DC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compliance(self, client: AsyncClient):
        payload = _make_compliance_create()
        resp = await client.post(f"{API_PREFIX}/compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["subject_id"] == "SUBJ-9001"
        assert data["id"].startswith("DC-")

    @pytest.mark.anyio
    async def test_update_compliance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance/DC-005",
            json={"compliance_level": "moderate", "alert_triggered": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_level"] == "moderate"
        assert data["alert_triggered"] is False

    @pytest.mark.anyio
    async def test_update_compliance_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance/DC-NONEXISTENT",
            json={"compliance_level": "good"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance/DC-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance/DC-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance/DC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DIARY VALIDATION CRUD
# =====================================================================


class TestDiaryValidationCrud:
    """Test diary validation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_validations_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_validations_filter_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"entry_id": "DE-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["entry_id"] == "DE-001"

    @pytest.mark.anyio
    async def test_list_validations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"validation_status": "valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["validation_status"] == "valid"

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DV-001"
        assert data["validation_status"] == "valid"

    @pytest.mark.anyio
    async def test_get_validation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = _make_validation_create()
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["entry_id"] == "DE-001"
        assert data["validation_status"] == "pending_review"
        assert data["id"].startswith("DV-")

    @pytest.mark.anyio
    async def test_update_validation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DV-008",
            json={"validation_status": "reviewed", "reviewer": "Sarah Mitchell", "review_notes": "Acceptable."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_status"] == "reviewed"
        assert data["reviewer"] == "Sarah Mitchell"
        assert data["review_date"] is not None

    @pytest.mark.anyio
    async def test_update_validation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DV-NONEXISTENT",
            json={"validation_status": "valid"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DV-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/validations/DV-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LIST FILTERING
# =====================================================================


class TestListFiltering:
    """Test list filtering across entity types."""

    @pytest.mark.anyio
    async def test_entries_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"trial_id": "nonexistent-trial"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_symptoms_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms", params={"entry_id": "DE-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_compliance_filter_non_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance", params={"compliance_level": "non_compliant"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["subject_id"] == "SUBJ-3001"

    @pytest.mark.anyio
    async def test_schedules_filter_inactive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"is_active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "DS-010"

    @pytest.mark.anyio
    async def test_validations_filter_errors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"validation_status": "errors"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"][0]["errors"]) > 0


# =====================================================================
# VALIDATION ERRORS (422)
# =====================================================================


class TestValidationErrors:
    """Test Pydantic validation errors return 422."""

    @pytest.mark.anyio
    async def test_create_entry_missing_required(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/entries", json={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_symptom_missing_name(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/symptoms",
            json={"entry_id": "DE-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_symptom_severity_too_high(self, client: AsyncClient):
        payload = _make_symptom_create(severity_score=11)
        resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_symptom_severity_negative(self, client: AsyncClient):
        payload = _make_symptom_create(severity_score=-1)
        resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_schedule_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/schedules", json={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_validation_missing_entry_id(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/validations", json={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_compliance_missing_dates(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/compliance",
            json={"trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "site_id": "SITE-101"},
        )
        assert resp.status_code == 422


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test eDiary metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] == 12
        assert data["total_symptoms"] == 10
        assert data["total_schedules"] == 10
        assert data["total_validations"] == 10
        assert data["active_schedules"] == 9

    @pytest.mark.anyio
    async def test_metrics_entries_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "symptom" in data["entries_by_type"]
        assert "medication" in data["entries_by_type"]
        total_by_type = sum(data["entries_by_type"].values())
        assert total_by_type == data["total_entries"]

    @pytest.mark.anyio
    async def test_metrics_entries_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "completed" in data["entries_by_status"]
        total_by_status = sum(data["entries_by_status"].values())
        assert total_by_status == data["total_entries"]

    @pytest.mark.anyio
    async def test_metrics_compliance_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0.0 <= data["overall_compliance_rate"] <= 100.0

    @pytest.mark.anyio
    async def test_metrics_compliance_by_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "excellent" in data["compliance_by_level"]
        total_by_level = sum(data["compliance_by_level"].values())
        assert total_by_level == 10  # 10 compliance records

    @pytest.mark.anyio
    async def test_metrics_avg_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_severity_score"] > 0

    @pytest.mark.anyio
    async def test_metrics_validations_with_errors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["validations_with_errors"] == 1

    @pytest.mark.anyio
    async def test_metrics_avg_completion_time(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_completion_time_min"] > 0

    def test_metrics_service_level(self, svc: PatientDiaryService):
        metrics = svc.get_metrics()
        assert metrics.total_entries == 12
        assert metrics.total_symptoms == 10
        assert metrics.total_schedules == 10
        assert metrics.active_schedules == 9
        assert metrics.total_validations == 10
        assert metrics.validations_with_errors == 1


# =====================================================================
# DEMO DATA SEEDING
# =====================================================================


class TestDemoDataSeeding:
    """Test that demo data seeding works correctly after reset."""

    def test_seed_creates_entries_with_responses(self, svc: PatientDiaryService):
        entry = svc.get_diary_entry("DE-001")
        assert entry is not None
        assert len(entry.responses) > 0
        assert entry.responses.get("headache") == "mild"

    def test_seed_creates_completed_entries_with_timestamps(self, svc: PatientDiaryService):
        entry = svc.get_diary_entry("DE-001")
        assert entry is not None
        assert entry.completed_date is not None
        assert entry.time_to_complete_minutes is not None

    def test_seed_creates_missed_entry(self, svc: PatientDiaryService):
        entry = svc.get_diary_entry("DE-007")
        assert entry is not None
        assert entry.status == EntryStatus.MISSED
        assert entry.completed_date is None
        assert entry.answered_questions == 0

    def test_seed_creates_symptoms_linked_to_entries(self, svc: PatientDiaryService):
        symptoms = svc.list_symptom_records(entry_id="DE-001")
        assert len(symptoms) == 2

    def test_seed_creates_validations_with_errors(self, svc: PatientDiaryService):
        validation = svc.get_diary_validation("DV-009")
        assert validation is not None
        assert validation.validation_status == ValidationStatus.ERRORS
        assert len(validation.errors) == 2

    def test_seed_creates_compliance_with_alerts(self, svc: PatientDiaryService):
        compliance = svc.get_diary_compliance("DC-007")
        assert compliance is not None
        assert compliance.compliance_level == ComplianceLevel.NON_COMPLIANT
        assert compliance.alert_triggered is True
        assert compliance.consecutive_misses == 5

    def test_seed_creates_schedules_across_trials(self, svc: PatientDiaryService):
        eylea_schedules = svc.list_diary_schedules(trial_id=EYLEA_TRIAL)
        dupixent_schedules = svc.list_diary_schedules(trial_id=DUPIXENT_TRIAL)
        libtayo_schedules = svc.list_diary_schedules(trial_id=LIBTAYO_TRIAL)
        assert len(eylea_schedules) > 0
        assert len(dupixent_schedules) > 0
        assert len(libtayo_schedules) > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_patient_diary_service()
        svc2 = get_patient_diary_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_patient_diary_service()
        svc2 = reset_patient_diary_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_patient_diary_service()
        # Delete an entry
        svc.delete_diary_entry("DE-001")
        assert svc.get_diary_entry("DE-001") is None
        # Reset should bring it back
        svc2 = reset_patient_diary_service()
        assert svc2.get_diary_entry("DE-001") is not None


# =====================================================================
# ENTRY UPDATE BEHAVIOR
# =====================================================================


class TestEntryUpdateBehavior:
    """Test special update behavior for diary entries."""

    def test_update_status_to_completed_sets_date(self, svc: PatientDiaryService):
        from app.schemas.patient_diary import DiaryEntryUpdate as DEU
        updated = svc.update_diary_entry("DE-011", DEU(status=EntryStatus.COMPLETED))
        assert updated is not None
        assert updated.status == EntryStatus.COMPLETED
        assert updated.completed_date is not None

    def test_update_answered_recalculates_pct(self, svc: PatientDiaryService):
        from app.schemas.patient_diary import DiaryEntryUpdate as DEU
        # DE-011 has total_questions=12, answered_questions=0
        updated = svc.update_diary_entry("DE-011", DEU(answered_questions=6))
        assert updated is not None
        assert updated.completion_pct == 50.0

    def test_update_validation_assigns_review_date(self, svc: PatientDiaryService):
        from app.schemas.patient_diary import DiaryValidationUpdate as DVU
        # DV-008 has no reviewer
        updated = svc.update_diary_validation("DV-008", DVU(reviewer="Test Reviewer"))
        assert updated is not None
        assert updated.reviewer == "Test Reviewer"
        assert updated.review_date is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_list_entries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_symptoms_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/symptoms")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_schedules_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_compliance_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_validations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_retrieve_entry(self, client: AsyncClient):
        payload = _make_entry_create()
        create_resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert create_resp.status_code == 201
        entry_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/entries/{entry_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == entry_id

    @pytest.mark.anyio
    async def test_create_and_delete_symptom(self, client: AsyncClient):
        payload = _make_symptom_create()
        create_resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert create_resp.status_code == 201
        record_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{API_PREFIX}/symptoms/{record_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/symptoms/{record_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_multiple_filters_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/entries",
            params={"trial_id": EYLEA_TRIAL, "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_symptom_severity_boundary_zero(self, client: AsyncClient):
        payload = _make_symptom_create(severity_score=0)
        resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert resp.status_code == 201
        assert resp.json()["severity_score"] == 0

    @pytest.mark.anyio
    async def test_symptom_severity_boundary_ten(self, client: AsyncClient):
        payload = _make_symptom_create(severity_score=10)
        resp = await client.post(f"{API_PREFIX}/symptoms", json=payload)
        assert resp.status_code == 201
        assert resp.json()["severity_score"] == 10
