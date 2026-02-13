"""Tests for Source Data Verification (SDV).

Covers:
- Seed data verification (SDV tasks, findings, site progress, review records)
- SDV task CRUD (create, read, update, delete, list, filter by trial/status/priority/site)
- SDV finding CRUD (create, read, update, delete, list, filter by trial/severity/status/task/site)
- SDV site progress CRUD (create, read, update, delete, list, filter by trial/site)
- SDV review record CRUD (create, read, update, delete, list, filter by trial/site/outcome)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
- Service-level CRUD operations
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


def _make_sdv_task_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NY-001",
        "subject_id": "SUBJ-TEST-001",
        "visit_name": "Week 1",
        "crf_name": "Demographics",
        "priority": "medium",
        "assigned_to": "CRA Test User",
        "due_date": "2026-03-01T00:00:00Z",
        "fields_total": 15,
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "task_id": "SDVT-001",
        "site_id": "SITE-NY-001",
        "subject_id": "SUBJ-TEST-001",
        "field_name": "Blood Pressure",
        "finding_severity": "minor",
        "source_value": "120 mmHg",
        "crf_value": "130 mmHg",
        "description": "BP transcription error",
        "identified_by": "CRA Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_site_progress_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NEW-001",
        "site_name": "New Test Site",
        "total_subjects": 20,
        "total_crfs": 120,
        "total_fields": 1800,
        "assigned_cra": "CRA Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_review_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NY-001",
        "reviewer_name": "CRA Test Reviewer",
        "review_type": "Routine Monitoring Visit",
        "subjects_reviewed": 5,
        "crfs_reviewed": 30,
        "duration_hours": 6.0,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_sdv_tasks_count(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks()
        assert len(tasks) == 12

    def test_seed_sdv_tasks_ids(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks()
        ids = {t.id for t in tasks}
        for i in range(1, 13):
            assert f"SDVT-{i:03d}" in ids

    def test_seed_findings_count(self, svc: SourceDataVerificationService):
        findings = svc.list_findings()
        assert len(findings) == 12

    def test_seed_findings_ids(self, svc: SourceDataVerificationService):
        findings = svc.list_findings()
        ids = {f.id for f in findings}
        for i in range(1, 13):
            assert f"SDVF-{i:03d}" in ids

    def test_seed_site_progress_count(self, svc: SourceDataVerificationService):
        progress = svc.list_site_progress()
        assert len(progress) == 12

    def test_seed_site_progress_ids(self, svc: SourceDataVerificationService):
        progress = svc.list_site_progress()
        ids = {p.id for p in progress}
        for i in range(1, 13):
            assert f"SDVP-{i:03d}" in ids

    def test_seed_review_records_count(self, svc: SourceDataVerificationService):
        reviews = svc.list_review_records()
        assert len(reviews) == 12

    def test_seed_review_records_ids(self, svc: SourceDataVerificationService):
        reviews = svc.list_review_records()
        ids = {r.id for r in reviews}
        for i in range(1, 13):
            assert f"SDVR-{i:03d}" in ids

    def test_seed_tasks_have_all_trials(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks()
        trial_ids = {t.trial_id for t in tasks}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_tasks_have_multiple_statuses(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks()
        statuses = {t.task_status for t in tasks}
        assert SDVTaskStatus.COMPLETED in statuses
        assert SDVTaskStatus.IN_PROGRESS in statuses
        assert SDVTaskStatus.PENDING in statuses
        assert SDVTaskStatus.OVERDUE in statuses

    def test_seed_tasks_have_multiple_priorities(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks()
        priorities = {t.priority for t in tasks}
        assert SDVPriority.CRITICAL in priorities
        assert SDVPriority.HIGH in priorities
        assert SDVPriority.MEDIUM in priorities

    def test_seed_findings_have_multiple_severities(self, svc: SourceDataVerificationService):
        findings = svc.list_findings()
        severities = {f.finding_severity for f in findings}
        assert FindingSeverity.CRITICAL in severities
        assert FindingSeverity.MAJOR in severities
        assert FindingSeverity.MINOR in severities
        assert FindingSeverity.OBSERVATION in severities
        assert FindingSeverity.INFORMATIONAL in severities

    def test_seed_findings_have_multiple_statuses(self, svc: SourceDataVerificationService):
        findings = svc.list_findings()
        statuses = {f.finding_status for f in findings}
        assert FindingStatus.OPEN in statuses
        assert FindingStatus.RESOLVED in statuses
        assert FindingStatus.ESCALATED in statuses

    def test_seed_reviews_have_multiple_outcomes(self, svc: SourceDataVerificationService):
        reviews = svc.list_review_records()
        outcomes = {r.review_outcome for r in reviews}
        assert ReviewOutcome.PASS in outcomes
        assert ReviewOutcome.CONDITIONAL_PASS in outcomes
        assert ReviewOutcome.FAIL in outcomes


# =====================================================================
# SDV TASK CRUD
# =====================================================================


class TestSDVTaskCRUD:
    """Test SDV task create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_sdv_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"task_status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["task_status"] == "completed"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_status_in_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"task_status": "in_progress"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["task_status"] == "in_progress"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_status_pending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"task_status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["task_status"] == "pending"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_priority_critical(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_priority_high(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"priority": "high"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "high"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks", params={"site_id": "SITE-NY-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-NY-001"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sdv-tasks",
            params={"trial_id": EYLEA_TRIAL, "task_status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["task_status"] == "completed"

    @pytest.mark.anyio
    async def test_list_sdv_tasks_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sdv-tasks", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_sdv_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks/SDVT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVT-001"
        assert data["visit_name"] == "Screening"
        assert data["crf_name"] == "Demographics"
        assert data["task_status"] == "completed"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_sdv_task_sdvt004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks/SDVT-004")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVT-004"
        assert data["task_status"] == "overdue"
        assert data["priority"] == "critical"

    @pytest.mark.anyio
    async def test_get_sdv_task_sdvt009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks/SDVT-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVT-009"
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["task_status"] == "completed"

    @pytest.mark.anyio
    async def test_get_sdv_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks/SDVT-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_sdv_task(self, client: AsyncClient):
        payload = _make_sdv_task_create()
        resp = await client.post(f"{API_PREFIX}/sdv-tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["visit_name"] == "Week 1"
        assert data["crf_name"] == "Demographics"
        assert data["task_status"] == "pending"
        assert data["priority"] == "medium"
        assert data["fields_total"] == 15
        assert data["fields_verified"] == 0
        assert data["discrepancies_found"] == 0
        assert data["id"].startswith("SDVT-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_sdv_task_critical(self, client: AsyncClient):
        payload = _make_sdv_task_create(
            priority="critical",
            crf_name="Adverse Events",
        )
        resp = await client.post(f"{API_PREFIX}/sdv-tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "critical"
        assert data["crf_name"] == "Adverse Events"

    @pytest.mark.anyio
    async def test_create_sdv_task_appears_in_list(self, client: AsyncClient):
        payload = _make_sdv_task_create(crf_name="Unique CRF")
        resp = await client.post(f"{API_PREFIX}/sdv-tasks", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/sdv-tasks")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_sdv_task_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdv-tasks/SDVT-003",
            json={"task_status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_status"] == "completed"

    @pytest.mark.anyio
    async def test_update_sdv_task_fields_verified(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdv-tasks/SDVT-003",
            json={"fields_verified": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields_verified"] == 20

    @pytest.mark.anyio
    async def test_update_sdv_task_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdv-tasks/SDVT-001",
            json={"notes": "Updated task notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated task notes"

    @pytest.mark.anyio
    async def test_update_sdv_task_discrepancies(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdv-tasks/SDVT-003",
            json={"discrepancies_found": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["discrepancies_found"] == 5

    @pytest.mark.anyio
    async def test_update_sdv_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdv-tasks/SDVT-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_sdv_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sdv-tasks/SDVT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sdv-tasks/SDVT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdv_task_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sdv-tasks/SDVT-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/sdv-tasks")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_sdv_task_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sdv-tasks/SDVT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SDV FINDING CRUD
# =====================================================================


class TestSDVFindingCRUD:
    """Test SDV finding create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_findings_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_findings_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_findings_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_findings_filter_severity_critical(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"finding_severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["finding_severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_severity_major(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"finding_severity": "major"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["finding_severity"] == "major"

    @pytest.mark.anyio
    async def test_list_findings_filter_severity_minor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"finding_severity": "minor"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["finding_severity"] == "minor"

    @pytest.mark.anyio
    async def test_list_findings_filter_status_open(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"finding_status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["finding_status"] == "open"

    @pytest.mark.anyio
    async def test_list_findings_filter_status_resolved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"finding_status": "resolved"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["finding_status"] == "resolved"

    @pytest.mark.anyio
    async def test_list_findings_filter_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"task_id": "SDVT-006"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["task_id"] == "SDVT-006"

    @pytest.mark.anyio
    async def test_list_findings_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"site_id": "SITE-LA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-LA-001"

    @pytest.mark.anyio
    async def test_list_findings_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/findings",
            params={"trial_id": EYLEA_TRIAL, "finding_status": "open"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["finding_status"] == "open"

    @pytest.mark.anyio
    async def test_list_findings_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/findings", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVF-001"
        assert data["field_name"] == "Systolic Blood Pressure"
        assert data["finding_severity"] == "minor"
        assert data["finding_status"] == "resolved"

    @pytest.mark.anyio
    async def test_get_finding_sdvf004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-004")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVF-004"
        assert data["finding_severity"] == "critical"
        assert data["finding_status"] == "escalated"

    @pytest.mark.anyio
    async def test_get_finding_sdvf009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVF-009"
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["finding_status"] == "resolved"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/SDVF-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_finding(self, client: AsyncClient):
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["field_name"] == "Blood Pressure"
        assert data["finding_severity"] == "minor"
        assert data["finding_status"] == "open"
        assert data["source_value"] == "120 mmHg"
        assert data["crf_value"] == "130 mmHg"
        assert data["id"].startswith("SDVF-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_finding_critical(self, client: AsyncClient):
        payload = _make_finding_create(
            field_name="AE Onset Date",
            finding_severity="critical",
        )
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_severity"] == "critical"

    @pytest.mark.anyio
    async def test_create_finding_appears_in_list(self, client: AsyncClient):
        payload = _make_finding_create(field_name="Unique Field")
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/findings")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_finding_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/SDVF-002",
            json={"finding_status": "resolved", "resolved_by": "Test Resolver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["finding_status"] == "resolved"
        assert data["resolved_by"] == "Test Resolver"

    @pytest.mark.anyio
    async def test_update_finding_corrective_action(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/SDVF-002",
            json={"corrective_action": "CRF corrected"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["corrective_action"] == "CRF corrected"

    @pytest.mark.anyio
    async def test_update_finding_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/SDVF-001",
            json={"notes": "Updated finding notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated finding notes"

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/SDVF-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/SDVF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/findings/SDVF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/SDVF-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/findings")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/SDVF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SDV SITE PROGRESS CRUD
# =====================================================================


class TestSDVSiteProgressCRUD:
    """Test SDV site progress create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_site_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_site_progress_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_site_progress_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_site_progress_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_site_progress_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress", params={"site_id": "SITE-HOU-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-HOU-001"

    @pytest.mark.anyio
    async def test_list_site_progress_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-progress",
            params={"trial_id": EYLEA_TRIAL, "site_id": "SITE-NY-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["site_id"] == "SITE-NY-001"

    @pytest.mark.anyio
    async def test_list_site_progress_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-progress", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_site_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVP-001"
        assert data["site_name"] == "NYC Medical Center"
        assert data["sdv_completion_pct"] == 86.7
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_site_progress_sdvp003(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVP-003"
        assert data["sdv_completion_pct"] == 100.0

    @pytest.mark.anyio
    async def test_get_site_progress_sdvp008(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-008")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVP-008"
        assert data["sdv_completion_pct"] == 0.0

    @pytest.mark.anyio
    async def test_get_site_progress_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/SDVP-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_site_progress(self, client: AsyncClient):
        payload = _make_site_progress_create()
        resp = await client.post(f"{API_PREFIX}/site-progress", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "New Test Site"
        assert data["total_subjects"] == 20
        assert data["subjects_verified"] == 0
        assert data["sdv_completion_pct"] == 0.0
        assert data["id"].startswith("SDVP-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_site_progress_appears_in_list(self, client: AsyncClient):
        payload = _make_site_progress_create(site_name="Unique Site")
        resp = await client.post(f"{API_PREFIX}/site-progress", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/site-progress")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_site_progress_subjects_verified(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/SDVP-002",
            json={"subjects_verified": 15},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subjects_verified"] == 15

    @pytest.mark.anyio
    async def test_update_site_progress_completion_pct(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/SDVP-002",
            json={"sdv_completion_pct": 75.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sdv_completion_pct"] == 75.0

    @pytest.mark.anyio
    async def test_update_site_progress_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/SDVP-001",
            json={"notes": "Updated progress notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated progress notes"

    @pytest.mark.anyio
    async def test_update_site_progress_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/SDVP-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_site_progress(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-progress/SDVP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-progress/SDVP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_progress_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-progress/SDVP-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/site-progress")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_site_progress_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-progress/SDVP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SDV REVIEW RECORD CRUD
# =====================================================================


class TestSDVReviewRecordCRUD:
    """Test SDV review record create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_review_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_review_records_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_review_records_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_review_records_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_review_records_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records", params={"site_id": "SITE-CHI-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-CHI-001"

    @pytest.mark.anyio
    async def test_list_review_records_filter_outcome_pass(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records", params={"review_outcome": "pass"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["review_outcome"] == "pass"

    @pytest.mark.anyio
    async def test_list_review_records_filter_outcome_fail(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records", params={"review_outcome": "fail"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["review_outcome"] == "fail"

    @pytest.mark.anyio
    async def test_list_review_records_filter_outcome_conditional(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/review-records", params={"review_outcome": "conditional_pass"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["review_outcome"] == "conditional_pass"

    @pytest.mark.anyio
    async def test_list_review_records_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/review-records",
            params={"trial_id": EYLEA_TRIAL, "review_outcome": "pass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["review_outcome"] == "pass"

    @pytest.mark.anyio
    async def test_list_review_records_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/review-records", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_review_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVR-001"
        assert data["reviewer_name"] == "CRA Sarah Mitchell"
        assert data["review_outcome"] == "pass"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_review_record_sdvr006(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-006")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVR-006"
        assert data["review_outcome"] == "fail"
        assert data["follow_up_required"] is True

    @pytest.mark.anyio
    async def test_get_review_record_sdvr012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDVR-012"
        assert data["review_outcome"] == "deferred"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_review_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/SDVR-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_review_record(self, client: AsyncClient):
        payload = _make_review_record_create()
        resp = await client.post(f"{API_PREFIX}/review-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer_name"] == "CRA Test Reviewer"
        assert data["review_type"] == "Routine Monitoring Visit"
        assert data["review_outcome"] == "pass"
        assert data["subjects_reviewed"] == 5
        assert data["crfs_reviewed"] == 30
        assert data["findings_generated"] == 0
        assert data["follow_up_required"] is False
        assert data["id"].startswith("SDVR-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_review_record_appears_in_list(self, client: AsyncClient):
        payload = _make_review_record_create(reviewer_name="Unique Reviewer")
        resp = await client.post(f"{API_PREFIX}/review-records", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/review-records")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_review_record_outcome(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/SDVR-002",
            json={"review_outcome": "pass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_outcome"] == "pass"

    @pytest.mark.anyio
    async def test_update_review_record_findings_generated(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/SDVR-001",
            json={"findings_generated": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["findings_generated"] == 2

    @pytest.mark.anyio
    async def test_update_review_record_follow_up(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/SDVR-001",
            json={"follow_up_required": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["follow_up_required"] is True

    @pytest.mark.anyio
    async def test_update_review_record_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/SDVR-001",
            json={"notes": "Updated review notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated review notes"

    @pytest.mark.anyio
    async def test_update_review_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/SDVR-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_review_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/review-records/SDVR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review_record_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/review-records/SDVR-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/review-records")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_review_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/review-records/SDVR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test source data verification metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 12
        assert data["total_findings"] == 12
        assert data["total_sites_tracked"] == 12
        assert data["total_reviews"] == 12

    @pytest.mark.anyio
    async def test_metrics_task_completion_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # 4 completed tasks out of 12: SDVT-001, SDVT-002, SDVT-005, SDVT-009
        assert data["task_completion_rate"] > 0

    @pytest.mark.anyio
    async def test_metrics_tasks_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        tasks_by_status = data["tasks_by_status"]
        assert "completed" in tasks_by_status
        assert "in_progress" in tasks_by_status
        assert "pending" in tasks_by_status
        total_by_status = sum(tasks_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_tasks_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        tasks_by_priority = data["tasks_by_priority"]
        assert "critical" in tasks_by_priority
        assert "high" in tasks_by_priority
        total_by_priority = sum(tasks_by_priority.values())
        assert total_by_priority == 12

    @pytest.mark.anyio
    async def test_metrics_findings_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        findings_by_severity = data["findings_by_severity"]
        assert "critical" in findings_by_severity
        assert "major" in findings_by_severity
        assert "minor" in findings_by_severity
        total_by_severity = sum(findings_by_severity.values())
        assert total_by_severity == 12

    @pytest.mark.anyio
    async def test_metrics_findings_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        findings_by_status = data["findings_by_status"]
        assert "open" in findings_by_status
        assert "resolved" in findings_by_status
        total_by_status = sum(findings_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_open_finding_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_finding_rate"] > 0

    @pytest.mark.anyio
    async def test_metrics_avg_sdv_completion_pct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_sdv_completion_pct"] > 0

    @pytest.mark.anyio
    async def test_metrics_reviews_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        reviews_by_outcome = data["reviews_by_outcome"]
        assert "pass" in reviews_by_outcome
        assert "conditional_pass" in reviews_by_outcome
        total_by_outcome = sum(reviews_by_outcome.values())
        assert total_by_outcome == 12

    def test_service_metrics_task_completion_rate(self, svc: SourceDataVerificationService):
        metrics = svc.get_metrics()
        tasks = svc.list_sdv_tasks()
        completed = sum(1 for t in tasks if t.task_status == SDVTaskStatus.COMPLETED)
        expected = round((completed / max(1, len(tasks))) * 100, 1)
        assert metrics.task_completion_rate == expected

    def test_service_metrics_open_finding_rate(self, svc: SourceDataVerificationService):
        metrics = svc.get_metrics()
        findings = svc.list_findings()
        open_count = sum(
            1 for f in findings
            if f.finding_status in (FindingStatus.OPEN, FindingStatus.IN_REVIEW, FindingStatus.ESCALATED)
        )
        expected = round((open_count / max(1, len(findings))) * 100, 1)
        assert metrics.open_finding_rate == expected

    def test_service_metrics_avg_sdv_completion(self, svc: SourceDataVerificationService):
        metrics = svc.get_metrics()
        progress = svc.list_site_progress()
        expected = round(sum(p.sdv_completion_pct for p in progress) / max(1, len(progress)), 1)
        assert metrics.avg_sdv_completion_pct == expected

    def test_service_metrics_after_create(self, svc: SourceDataVerificationService):
        """Metrics should update after creating a new task."""
        from app.schemas.source_data_verification import SDVTaskCreate

        initial_metrics = svc.get_metrics()
        svc.create_sdv_task(
            SDVTaskCreate(
                trial_id=EYLEA_TRIAL,
                site_id="SITE-NY-001",
                subject_id="SUBJ-NEW",
                visit_name="Week 1",
                crf_name="Test CRF",
                assigned_to="CRA Test",
                due_date="2026-03-01T00:00:00Z",
            )
        )
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_tasks == initial_metrics.total_tasks + 1

    def test_service_metrics_after_delete(self, svc: SourceDataVerificationService):
        """Metrics should update after deleting a task."""
        initial_metrics = svc.get_metrics()
        svc.delete_sdv_task("SDVT-001")
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_tasks == initial_metrics.total_tasks - 1


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test error handling and edge cases."""

    @pytest.mark.anyio
    async def test_get_nonexistent_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv-tasks/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_site_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-progress/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_review_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/review-records/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_task(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdv-tasks/DOES-NOT-EXIST",
            json={"notes": "fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/DOES-NOT-EXIST",
            json={"notes": "fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_site_progress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-progress/DOES-NOT-EXIST",
            json={"notes": "fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_review_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/review-records/DOES-NOT-EXIST",
            json={"notes": "fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sdv-tasks/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_site_progress(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-progress/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_review_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/review-records/DOES-NOT-EXIST")
        assert resp.status_code == 404


# =====================================================================
# SINGLETON PATTERN
# =====================================================================


class TestSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_source_data_verification_service()
        svc2 = get_source_data_verification_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_source_data_verification_service()
        svc2 = reset_source_data_verification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_source_data_verification_service()
        svc.delete_sdv_task("SDVT-001")
        assert svc.get_sdv_task("SDVT-001") is None
        svc2 = reset_source_data_verification_service()
        assert svc2.get_sdv_task("SDVT-001") is not None

    def test_reset_reseeds_findings(self):
        svc = get_source_data_verification_service()
        svc.delete_finding("SDVF-001")
        assert svc.get_finding("SDVF-001") is None
        svc2 = reset_source_data_verification_service()
        assert svc2.get_finding("SDVF-001") is not None

    def test_reset_reseeds_site_progress(self):
        svc = get_source_data_verification_service()
        svc.delete_site_progress("SDVP-001")
        assert svc.get_site_progress("SDVP-001") is None
        svc2 = reset_source_data_verification_service()
        assert svc2.get_site_progress("SDVP-001") is not None

    def test_reset_reseeds_review_records(self):
        svc = get_source_data_verification_service()
        svc.delete_review_record("SDVR-001")
        assert svc.get_review_record("SDVR-001") is None
        svc2 = reset_source_data_verification_service()
        assert svc2.get_review_record("SDVR-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        svc1 = get_source_data_verification_service()
        reset_source_data_verification_service()
        svc2 = get_source_data_verification_service()
        assert svc1 is not svc2


# =====================================================================
# SERVICE-LEVEL CRUD
# =====================================================================


class TestServiceLevelCRUD:
    """Test service-level CRUD operations directly."""

    # --- SDV Tasks ---

    def test_service_list_tasks_filter_status(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks(task_status=SDVTaskStatus.COMPLETED)
        assert len(tasks) > 0
        for t in tasks:
            assert t.task_status == SDVTaskStatus.COMPLETED

    def test_service_list_tasks_filter_priority(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks(priority=SDVPriority.CRITICAL)
        assert len(tasks) > 0
        for t in tasks:
            assert t.priority == SDVPriority.CRITICAL

    def test_service_list_tasks_filter_site(self, svc: SourceDataVerificationService):
        tasks = svc.list_sdv_tasks(site_id="SITE-NY-001")
        assert len(tasks) > 0
        for t in tasks:
            assert t.site_id == "SITE-NY-001"

    def test_service_get_task_none(self, svc: SourceDataVerificationService):
        result = svc.get_sdv_task("SDVT-NONEXISTENT")
        assert result is None

    def test_service_delete_task_nonexistent(self, svc: SourceDataVerificationService):
        result = svc.delete_sdv_task("SDVT-NONEXISTENT")
        assert result is False

    # --- Findings ---

    def test_service_list_findings_filter_severity(self, svc: SourceDataVerificationService):
        findings = svc.list_findings(finding_severity=FindingSeverity.CRITICAL)
        assert len(findings) > 0
        for f in findings:
            assert f.finding_severity == FindingSeverity.CRITICAL

    def test_service_list_findings_filter_status(self, svc: SourceDataVerificationService):
        findings = svc.list_findings(finding_status=FindingStatus.OPEN)
        assert len(findings) > 0
        for f in findings:
            assert f.finding_status == FindingStatus.OPEN

    def test_service_list_findings_filter_task(self, svc: SourceDataVerificationService):
        findings = svc.list_findings(task_id="SDVT-006")
        assert len(findings) > 0
        for f in findings:
            assert f.task_id == "SDVT-006"

    def test_service_get_finding_none(self, svc: SourceDataVerificationService):
        result = svc.get_finding("SDVF-NONEXISTENT")
        assert result is None

    def test_service_delete_finding_nonexistent(self, svc: SourceDataVerificationService):
        result = svc.delete_finding("SDVF-NONEXISTENT")
        assert result is False

    # --- Site Progress ---

    def test_service_list_progress_filter_site(self, svc: SourceDataVerificationService):
        progress = svc.list_site_progress(site_id="SITE-HOU-001")
        assert len(progress) > 0
        for p in progress:
            assert p.site_id == "SITE-HOU-001"

    def test_service_get_progress_none(self, svc: SourceDataVerificationService):
        result = svc.get_site_progress("SDVP-NONEXISTENT")
        assert result is None

    def test_service_delete_progress_nonexistent(self, svc: SourceDataVerificationService):
        result = svc.delete_site_progress("SDVP-NONEXISTENT")
        assert result is False

    # --- Review Records ---

    def test_service_list_reviews_filter_outcome(self, svc: SourceDataVerificationService):
        reviews = svc.list_review_records(review_outcome=ReviewOutcome.PASS)
        assert len(reviews) > 0
        for r in reviews:
            assert r.review_outcome == ReviewOutcome.PASS

    def test_service_list_reviews_filter_site(self, svc: SourceDataVerificationService):
        reviews = svc.list_review_records(site_id="SITE-CHI-001")
        assert len(reviews) > 0
        for r in reviews:
            assert r.site_id == "SITE-CHI-001"

    def test_service_get_review_none(self, svc: SourceDataVerificationService):
        result = svc.get_review_record("SDVR-NONEXISTENT")
        assert result is None

    def test_service_delete_review_nonexistent(self, svc: SourceDataVerificationService):
        result = svc.delete_review_record("SDVR-NONEXISTENT")
        assert result is False
