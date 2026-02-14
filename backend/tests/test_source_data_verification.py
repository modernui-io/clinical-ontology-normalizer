"""Tests for Source Data Verification (SDV).

Covers:
- Seed data verification (SDV tasks, findings, site progress, review records)
- SDV task CRUD (create, read, update, delete, list, filter by trial/status/priority/site)
- SDV finding CRUD (create, read, update, delete, list, filter by trial/severity/status/task)
- SDV site progress CRUD (create, read, update, delete, list, filter by trial/site)
- SDV review record CRUD (create, read, update, delete, list, filter by trial/outcome/site)
- Metrics computation (with and without trial filter)
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.source_data_verification import (
    FindingSeverity,
    FindingStatus,
    ReviewOutcome,
    SDVPriority,
    SDVTaskStatus,
)
from app.services.source_data_verification_service import (
    SourceDataVerificationService,
    get_source_data_verification_service,
    reset_source_data_verification_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/source-data-verification"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_source_data_verification_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SourceDataVerificationService:
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


def _make_task_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "subject_id": "SUBJ-TEST-001",
        "visit_name": "Screening",
        "crf_name": "Demographics",
        "assigned_to": "CRA Test User",
        "due_date": "2026-03-15T09:00:00Z",
        "fields_total": 15,
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "task_id": "SDVT-001",
        "site_id": "SITE-TEST-001",
        "subject_id": "SUBJ-TEST-001",
        "field_name": "blood_pressure",
        "source_value": "120",
        "crf_value": "130",
        "description": "Blood pressure transcription error.",
        "identified_by": "CRA Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_site_progress_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "site_name": "Test Medical Center",
        "total_subjects": 10,
        "total_crfs": 60,
        "total_fields": 900,
        "assigned_cra": "CRA Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_review_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "reviewer_name": "CRA Test User",
        "review_type": "Routine Monitoring Visit",
        "subjects_reviewed": 5,
        "crfs_reviewed": 30,
        "duration_hours": 6.0,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_sdv_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_sdv_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_sdv_site_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_sdv_review_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# SDV TASK CRUD
# ===================================================================


class TestSDVTaskCRUD:
    @pytest.mark.anyio
    async def test_list_sdv_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_sdv_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/SDVT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVT-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_sdv_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sdv_task(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/tasks", json=_make_task_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SDVT-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["task_status"] == "pending"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/tasks")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/tasks", json=_make_task_create())
        resp2 = await client.get(f"{API_PREFIX}/tasks")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_sdv_task(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/SDVT-001",
            json={"task_status": "in_progress", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_status"] == "in_progress"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_sdv_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tasks/SDVT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/tasks/SDVT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_task_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tasks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_task_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tasks", params={"task_status": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["task_status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tasks", params={"priority": "critical"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tasks", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# SDV FINDING CRUD
# ===================================================================


class TestSDVFindingCRUD:
    @pytest.mark.anyio
    async def test_list_sdv_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_sdv_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SDVF-001"

    @pytest.mark.anyio
    async def test_get_sdv_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sdv_finding(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings", json=_make_finding_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SDVF-")
        assert data["finding_status"] == "open"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/findings")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/findings", json=_make_finding_create())
        resp2 = await client.get(f"{API_PREFIX}/findings")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_sdv_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/SDVF-001",
            json={"finding_status": "resolved", "notes": "Corrected"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["finding_status"] == "resolved"
        assert data["notes"] == "Corrected"

    @pytest.mark.anyio
    async def test_update_sdv_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/SDVF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/findings/SDVF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_finding_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/findings", params={"finding_severity": "critical"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["finding_severity"] == "critical"

    @pytest.mark.anyio
    async def test_filter_by_finding_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/findings", params={"finding_status": "open"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["finding_status"] == "open"

    @pytest.mark.anyio
    async def test_filter_by_task_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/findings", params={"task_id": "SDVT-006"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["task_id"] == "SDVT-006"


# ===================================================================
# SDV SITE PROGRESS CRUD
# ===================================================================


class TestSDVSiteProgressCRUD:
    @pytest.mark.anyio
    async def test_list_sdv_site_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_sdv_site_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SDVP-001"

    @pytest.mark.anyio
    async def test_get_sdv_site_progress_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sdv_site_progress(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/site-progress", json=_make_site_progress_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SDVP-")
        assert data["sdv_completion_pct"] == 0.0

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/site-progress")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/site-progress", json=_make_site_progress_create())
        resp2 = await client.get(f"{API_PREFIX}/site-progress")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_sdv_site_progress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/SDVP-001",
            json={"subjects_verified": 25, "notes": "All subjects verified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subjects_verified"] == 25
        assert data["notes"] == "All subjects verified"

    @pytest.mark.anyio
    async def test_update_sdv_site_progress_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_site_progress(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-progress/SDVP-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_sdv_site_progress_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-progress/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-progress", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-progress", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# SDV REVIEW RECORD CRUD
# ===================================================================


class TestSDVReviewRecordCRUD:
    @pytest.mark.anyio
    async def test_list_sdv_review_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_sdv_review_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SDVR-001"

    @pytest.mark.anyio
    async def test_get_sdv_review_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sdv_review_record(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/review-records", json=_make_review_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SDVR-")
        assert data["review_outcome"] == "pass"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/review-records")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/review-records", json=_make_review_create())
        resp2 = await client.get(f"{API_PREFIX}/review-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_sdv_review_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/SDVR-001",
            json={"review_outcome": "fail", "notes": "Issues found"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_outcome"] == "fail"
        assert data["notes"] == "Issues found"

    @pytest.mark.anyio
    async def test_update_sdv_review_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_review_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_review_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/review-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_review_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/review-records", params={"review_outcome": "pass"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["review_outcome"] == "pass"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/review-records", params={"site_id": "SITE-HOU-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-HOU-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/review-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tasks" in data
        assert "total_findings" in data
        assert "total_sites_tracked" in data
        assert "total_reviews" in data
        assert "task_completion_rate" in data
        assert "open_finding_rate" in data
        assert "avg_sdv_completion_pct" in data

    @pytest.mark.anyio
    async def test_metrics_total_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_tasks"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_findings"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_sites_tracked(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_sites_tracked"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_reviews"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["tasks_by_status"], dict)
        assert isinstance(data["tasks_by_priority"], dict)
        assert isinstance(data["findings_by_severity"], dict)
        assert isinstance(data["findings_by_status"], dict)
        assert isinstance(data["reviews_by_outcome"], dict)

    @pytest.mark.anyio
    async def test_metrics_with_trial_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 4  # SDVT-001 through SDVT-004
        assert data["total_findings"] == 4  # SDVF-001 through SDVF-004
        assert data["total_sites_tracked"] == 4  # SDVP-001 through SDVP-004
        assert data["total_reviews"] == 4  # SDVR-001 through SDVR-004

    def test_metrics_service_level(self, svc: SourceDataVerificationService):
        metrics = svc.get_metrics()
        assert metrics.total_tasks == 12
        assert metrics.total_findings == 12
        assert metrics.total_sites_tracked == 12
        assert metrics.total_reviews == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_task_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/SDVT-001")
        original = resp.json()
        original_crf = original["crf_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/tasks/SDVT-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["crf_name"] == original_crf
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_finding_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-001")
        original = resp.json()
        original_field = original["field_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/findings/SDVF-001",
            json={"notes": "Updated finding note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["field_name"] == original_field

    @pytest.mark.anyio
    async def test_update_site_progress_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-001")
        original = resp.json()
        original_name = original["site_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/site-progress/SDVP-001",
            json={"notes": "Updated progress note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["site_name"] == original_name

    @pytest.mark.anyio
    async def test_update_review_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-001")
        original = resp.json()
        original_type = original["review_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/review-records/SDVR-001",
            json={"notes": "Updated review note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["review_type"] == original_type


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_source_data_verification_service()
        svc2 = get_source_data_verification_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_source_data_verification_service()
        svc2 = reset_source_data_verification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_source_data_verification_service()
        svc.delete_sdv_task("SDVT-001")
        assert svc.get_sdv_task("SDVT-001") is None
        svc2 = reset_source_data_verification_service()
        assert svc2.get_sdv_task("SDVT-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_sdv_tasks_service(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_tasks()
        assert len(items) == 12

    def test_get_sdv_task_service(self, svc: SourceDataVerificationService):
        task = svc.get_sdv_task("SDVT-001")
        assert task is not None
        assert task.id == "SDVT-001"

    def test_list_sdv_findings_service(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_findings()
        assert len(items) == 12

    def test_get_sdv_finding_service(self, svc: SourceDataVerificationService):
        finding = svc.get_sdv_finding("SDVF-001")
        assert finding is not None
        assert finding.id == "SDVF-001"

    def test_list_sdv_site_progress_service(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_site_progress()
        assert len(items) == 12

    def test_get_sdv_site_progress_service(self, svc: SourceDataVerificationService):
        record = svc.get_sdv_site_progress("SDVP-001")
        assert record is not None
        assert record.id == "SDVP-001"

    def test_list_sdv_review_records_service(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_review_records()
        assert len(items) == 12

    def test_get_sdv_review_record_service(self, svc: SourceDataVerificationService):
        record = svc.get_sdv_review_record("SDVR-001")
        assert record is not None
        assert record.id == "SDVR-001"

    def test_delete_sdv_task_service(self, svc: SourceDataVerificationService):
        assert svc.delete_sdv_task("SDVT-001") is True
        assert svc.get_sdv_task("SDVT-001") is None

    def test_delete_nonexistent_returns_false(self, svc: SourceDataVerificationService):
        assert svc.delete_sdv_task("NONEXISTENT") is False

    def test_filter_tasks_by_trial(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_tasks(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_tasks_by_status(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_tasks(task_status=SDVTaskStatus.COMPLETED)
        for item in items:
            assert item.task_status == SDVTaskStatus.COMPLETED

    def test_filter_findings_by_severity(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_findings(finding_severity=FindingSeverity.CRITICAL)
        for item in items:
            assert item.finding_severity == FindingSeverity.CRITICAL

    def test_filter_findings_by_status(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_findings(finding_status=FindingStatus.OPEN)
        for item in items:
            assert item.finding_status == FindingStatus.OPEN

    def test_filter_reviews_by_outcome(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_review_records(review_outcome=ReviewOutcome.PASS)
        for item in items:
            assert item.review_outcome == ReviewOutcome.PASS

    def test_filter_site_progress_by_site(self, svc: SourceDataVerificationService):
        items = svc.list_sdv_site_progress(site_id="SITE-NY-001")
        for item in items:
            assert item.site_id == "SITE-NY-001"


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_tasks(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/tasks",
                json=_make_task_create(subject_id=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_findings(self, client: AsyncClient):
        for finding_id in ["SDVF-001", "SDVF-002", "SDVF-003"]:
            resp = await client.delete(f"{API_PREFIX}/findings/{finding_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_task_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/SDVT-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "site_id", "subject_id", "visit_name",
                       "crf_name", "task_status", "priority", "assigned_to",
                       "due_date", "fields_verified", "fields_total", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_finding_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "task_id", "site_id", "subject_id",
                       "field_name", "finding_severity", "finding_status",
                       "source_value", "crf_value", "identified_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_site_progress_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "site_id", "site_name", "total_subjects",
                       "subjects_verified", "sdv_completion_pct", "assigned_cra", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_review_record_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "site_id", "review_date", "reviewer_name",
                       "review_type", "review_outcome", "duration_hours", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
