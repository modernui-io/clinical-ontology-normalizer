"""Tests for Patient Visit Tracking (PVT-TRK).

Covers:
- Seed data verification (visit schedules, visit adherence, window violations,
  missed visit follow-ups)
- Visit schedule CRUD (create, read, update, delete, list, filter by trial/type/status/site)
- Visit adherence CRUD (create, read, update, delete, list, filter by trial/rating/subject)
- Window violation CRUD (create, read, update, delete, list, filter by trial/severity)
- Missed visit follow-up CRUD (create, read, update, delete, list, filter by trial/status)
- Metrics computation (overall and per-trial)
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.patient_visit_tracking import (
    AdherenceRating,
    FollowUpStatus,
    ViolationSeverity,
    VisitStatus,
    VisitType,
)
from app.services.patient_visit_tracking_service import (
    PatientVisitTrackingService,
    get_patient_visit_tracking_service,
    reset_patient_visit_tracking_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-visit-tracking"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_visit_tracking_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientVisitTrackingService:
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


def _make_schedule_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "visit_type": "screening",
        "visit_number": 1,
        "visit_name": "Test Screening Visit",
        "scheduled_date": "2026-03-15T09:00:00Z",
        "duration_minutes": 120,
    }
    defaults.update(overrides)
    return defaults


def _make_adherence_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "visit_schedule_id": "VS-001",
        "assessed_by": "CRA Test Assessor",
        "assessment_date": "2026-03-15T10:00:00Z",
        "days_from_target": 0,
    }
    defaults.update(overrides)
    return defaults


def _make_violation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "visit_schedule_id": "VS-001",
        "violation_severity": "minor",
        "days_out_of_window": 2,
        "expected_window_open": "2026-03-10T00:00:00Z",
        "expected_window_close": "2026-03-20T00:00:00Z",
        "actual_visit_date": "2026-03-22T00:00:00Z",
        "reason": "Subject arrived late due to transportation.",
    }
    defaults.update(overrides)
    return defaults


def _make_follow_up_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "visit_schedule_id": "VS-001",
        "assigned_to": "CRA Test Coordinator",
        "reason_for_miss": "Subject unable to attend.",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_visit_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_visit_adherence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-adherence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_window_violations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/window-violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_missed_visit_follow_ups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# VISIT SCHEDULE CRUD
# ===================================================================


class TestVisitScheduleCRUD:
    @pytest.mark.anyio
    async def test_list_visit_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_visit_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules/VS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VS-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_visit_schedule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit_schedule(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visit-schedules", json=_make_schedule_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("VS-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["visit_type"] == "screening"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/visit-schedules")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/visit-schedules", json=_make_schedule_create())
        resp2 = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_visit_schedule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visit-schedules/VS-001",
            json={"visit_status": "completed", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["visit_status"] == "completed"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_visit_schedule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visit-schedules/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_schedule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visit-schedules/VS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/visit-schedules/VS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_schedule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visit-schedules/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_visit_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"visit_type": "screening"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["visit_type"] == "screening"

    @pytest.mark.anyio
    async def test_filter_by_visit_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"visit_status": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["visit_status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# VISIT ADHERENCE CRUD
# ===================================================================


class TestVisitAdherenceCRUD:
    @pytest.mark.anyio
    async def test_list_visit_adherence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-adherence")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_visit_adherence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-adherence/VA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "VA-001"

    @pytest.mark.anyio
    async def test_get_visit_adherence_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-adherence/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit_adherence(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visit-adherence", json=_make_adherence_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("VA-")
        assert data["assessed_by"] == "CRA Test Assessor"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/visit-adherence")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/visit-adherence", json=_make_adherence_create())
        resp2 = await client.get(f"{API_PREFIX}/visit-adherence")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_visit_adherence(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visit-adherence/VA-001",
            json={"adherence_rating": "good", "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adherence_rating"] == "good"
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_visit_adherence_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visit-adherence/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_adherence(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visit-adherence/VA-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_visit_adherence_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visit-adherence/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_adherence_rating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-adherence", params={"adherence_rating": "excellent"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["adherence_rating"] == "excellent"

    @pytest.mark.anyio
    async def test_filter_by_subject_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-adherence", params={"subject_id": "SUBJ-E001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["subject_id"] == "SUBJ-E001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-adherence", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# WINDOW VIOLATION CRUD
# ===================================================================


class TestWindowViolationCRUD:
    @pytest.mark.anyio
    async def test_list_window_violations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/window-violations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_window_violation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/window-violations/WV-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "WV-001"

    @pytest.mark.anyio
    async def test_get_window_violation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/window-violations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_window_violation(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/window-violations", json=_make_violation_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("WV-")
        assert data["reason"] == "Subject arrived late due to transportation."

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/window-violations")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/window-violations", json=_make_violation_create())
        resp2 = await client.get(f"{API_PREFIX}/window-violations")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_window_violation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/window-violations/WV-001",
            json={"impact_on_data": "No impact", "notes": "Reviewed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["impact_on_data"] == "No impact"
        assert data["notes"] == "Reviewed"

    @pytest.mark.anyio
    async def test_update_window_violation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/window-violations/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_window_violation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/window-violations/WV-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_window_violation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/window-violations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_violation_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/window-violations", params={"violation_severity": "critical"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["violation_severity"] == "critical"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/window-violations", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# MISSED VISIT FOLLOW-UP CRUD
# ===================================================================


class TestMissedVisitFollowUpCRUD:
    @pytest.mark.anyio
    async def test_list_missed_visit_follow_ups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_missed_visit_follow_up(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups/MVF-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "MVF-001"

    @pytest.mark.anyio
    async def test_get_missed_visit_follow_up_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_missed_visit_follow_up(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/missed-visit-follow-ups", json=_make_follow_up_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("MVF-")
        assert data["assigned_to"] == "CRA Test Coordinator"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/missed-visit-follow-ups")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/missed-visit-follow-ups", json=_make_follow_up_create())
        resp2 = await client.get(f"{API_PREFIX}/missed-visit-follow-ups")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_missed_visit_follow_up(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/missed-visit-follow-ups/MVF-001",
            json={"follow_up_status": "completed", "notes": "Resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["follow_up_status"] == "completed"
        assert data["notes"] == "Resolved"

    @pytest.mark.anyio
    async def test_update_missed_visit_follow_up_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/missed-visit-follow-ups/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_missed_visit_follow_up(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/missed-visit-follow-ups/MVF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/missed-visit-follow-ups/MVF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_missed_visit_follow_up_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/missed-visit-follow-ups/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_follow_up_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/missed-visit-follow-ups", params={"follow_up_status": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["follow_up_status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/missed-visit-follow-ups", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_visits" in data
        assert "total_adherence_records" in data
        assert "total_window_violations" in data
        assert "total_missed_follow_ups" in data
        assert "visit_completion_rate" in data
        assert "within_window_rate" in data
        assert "missed_visit_resolution_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_visits"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_adherence_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_adherence_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_window_violations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_window_violations"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_missed_follow_ups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_missed_follow_ups"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["visits_by_status"], dict)
        assert isinstance(data["visits_by_type"], dict)
        assert isinstance(data["adherence_by_rating"], dict)
        assert isinstance(data["violations_by_severity"], dict)
        assert isinstance(data["follow_ups_by_status"], dict)

    @pytest.mark.anyio
    async def test_metrics_filtered_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_visits"] == 4  # 4 EYLEA schedules

    def test_metrics_service_level(self, svc: PatientVisitTrackingService):
        metrics = svc.get_metrics()
        assert metrics.total_visits == 12
        assert metrics.total_adherence_records == 12
        assert metrics.total_window_violations == 12
        assert metrics.total_missed_follow_ups == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_schedule_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules/VS-001")
        original = resp.json()
        original_type = original["visit_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/visit-schedules/VS-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["visit_type"] == original_type
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_adherence_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-adherence/VA-001")
        original = resp.json()
        original_rating = original["adherence_rating"]

        resp2 = await client.put(
            f"{API_PREFIX}/visit-adherence/VA-001",
            json={"notes": "Updated adherence note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["adherence_rating"] == original_rating

    @pytest.mark.anyio
    async def test_update_violation_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/window-violations/WV-001")
        original = resp.json()
        original_severity = original["violation_severity"]

        resp2 = await client.put(
            f"{API_PREFIX}/window-violations/WV-001",
            json={"notes": "Verified violation"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["violation_severity"] == original_severity

    @pytest.mark.anyio
    async def test_update_follow_up_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups/MVF-001")
        original = resp.json()
        original_assigned = original["assigned_to"]

        resp2 = await client.put(
            f"{API_PREFIX}/missed-visit-follow-ups/MVF-001",
            json={"notes": "Updated follow-up note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["assigned_to"] == original_assigned


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_patient_visit_tracking_service()
        svc2 = get_patient_visit_tracking_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_patient_visit_tracking_service()
        svc2 = reset_patient_visit_tracking_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_patient_visit_tracking_service()
        svc.delete_visit_schedule("VS-001")
        assert svc.get_visit_schedule("VS-001") is None
        svc2 = reset_patient_visit_tracking_service()
        assert svc2.get_visit_schedule("VS-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_visit_schedules_service(self, svc: PatientVisitTrackingService):
        items = svc.list_visit_schedules()
        assert len(items) == 12

    def test_get_visit_schedule_service(self, svc: PatientVisitTrackingService):
        record = svc.get_visit_schedule("VS-001")
        assert record is not None
        assert record.id == "VS-001"

    def test_list_visit_adherence_service(self, svc: PatientVisitTrackingService):
        items = svc.list_visit_adherence()
        assert len(items) == 12

    def test_get_visit_adherence_service(self, svc: PatientVisitTrackingService):
        record = svc.get_visit_adherence("VA-001")
        assert record is not None
        assert record.id == "VA-001"

    def test_list_window_violations_service(self, svc: PatientVisitTrackingService):
        items = svc.list_window_violations()
        assert len(items) == 12

    def test_get_window_violation_service(self, svc: PatientVisitTrackingService):
        record = svc.get_window_violation("WV-001")
        assert record is not None
        assert record.id == "WV-001"

    def test_list_missed_visit_follow_ups_service(self, svc: PatientVisitTrackingService):
        items = svc.list_missed_visit_follow_ups()
        assert len(items) == 12

    def test_get_missed_visit_follow_up_service(self, svc: PatientVisitTrackingService):
        record = svc.get_missed_visit_follow_up("MVF-001")
        assert record is not None
        assert record.id == "MVF-001"

    def test_delete_visit_schedule_service(self, svc: PatientVisitTrackingService):
        assert svc.delete_visit_schedule("VS-001") is True
        assert svc.get_visit_schedule("VS-001") is None

    def test_delete_nonexistent_returns_false(self, svc: PatientVisitTrackingService):
        assert svc.delete_visit_schedule("NONEXISTENT") is False

    def test_filter_schedule_by_trial(self, svc: PatientVisitTrackingService):
        items = svc.list_visit_schedules(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_schedule_by_visit_type(self, svc: PatientVisitTrackingService):
        items = svc.list_visit_schedules(visit_type=VisitType.SCREENING)
        for item in items:
            assert item.visit_type == VisitType.SCREENING

    def test_filter_adherence_by_rating(self, svc: PatientVisitTrackingService):
        items = svc.list_visit_adherence(adherence_rating=AdherenceRating.EXCELLENT)
        for item in items:
            assert item.adherence_rating == AdherenceRating.EXCELLENT

    def test_filter_violations_by_severity(self, svc: PatientVisitTrackingService):
        items = svc.list_window_violations(violation_severity=ViolationSeverity.CRITICAL)
        for item in items:
            assert item.violation_severity == ViolationSeverity.CRITICAL

    def test_filter_follow_ups_by_status(self, svc: PatientVisitTrackingService):
        items = svc.list_missed_visit_follow_ups(follow_up_status=FollowUpStatus.COMPLETED)
        for item in items:
            assert item.follow_up_status == FollowUpStatus.COMPLETED


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_visit_schedules(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/visit-schedules",
                json=_make_schedule_create(subject_id=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_follow_ups(self, client: AsyncClient):
        for fid in ["MVF-001", "MVF-002", "MVF-003"]:
            resp = await client.delete(f"{API_PREFIX}/missed-visit-follow-ups/{fid}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_visit_schedule_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules/VS-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id", "visit_type",
            "visit_status", "visit_name", "scheduled_date", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_visit_adherence_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-adherence/VA-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id", "visit_schedule_id",
            "adherence_rating", "assessed_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_window_violation_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/window-violations/WV-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id", "visit_schedule_id",
            "violation_severity", "reason", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_missed_visit_follow_up_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/missed-visit-follow-ups/MVF-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id", "visit_schedule_id",
            "follow_up_status", "assigned_to", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
