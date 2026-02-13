"""Tests for Lab Proficiency (LAB-PROF).

Covers:
- Seed data verification (proficiency tests, lab comparisons, accreditation records, corrective actions)
- Proficiency test CRUD (create, read, update, delete, list, filter by trial/category/result)
- Lab comparison CRUD (create, read, update, delete, list, filter by trial/status)
- Accreditation record CRUD (create, read, update, delete, list, filter by trial/status)
- Corrective action CRUD (create, read, update, delete, list, filter by trial/priority/completed)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
- Service-level CRUD operations
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.lab_proficiency import (
    AccreditationStatus,
    ComparisonStatus,
    CorrectiveActionPriority,
    TestCategory,
    TestResult,
)
from app.services.lab_proficiency_service import (
    LabProficiencyService,
    get_lab_proficiency_service,
    reset_lab_proficiency_service,
)


# ---------------------------------------------------------------------------
# Force asyncio backend only (trio causes event-loop conflicts with SQLAlchemy)
# ---------------------------------------------------------------------------

@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/lab-proficiency"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_lab_proficiency_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> LabProficiencyService:
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


def _make_proficiency_test_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "lab_id": "LAB-TEST-001",
        "lab_name": "Test Lab",
        "test_category": "clinical_chemistry",
        "test_name": "Test Proficiency Panel",
        "analyte_name": "Glucose",
        "pt_provider": "CAP",
        "cycle_number": "2025-T1",
        "test_date": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_lab_comparison_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reference_lab_id": "LAB-REF-001",
        "comparison_lab_id": "LAB-CMP-001",
        "analyte_name": "Test Analyte",
        "tolerance_limit_pct": 15.0,
        "sample_count": 0,
    }
    defaults.update(overrides)
    return defaults


def _make_accreditation_record_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "lab_id": "LAB-TEST-001",
        "lab_name": "Test Lab",
        "accrediting_body": "CAP",
        "accreditation_number": "CAP-TEST-001",
        "scope": "Clinical Chemistry",
        "issue_date": now.isoformat(),
        "expiry_date": now.isoformat(),
        "verified_by": "Test Verifier",
    }
    defaults.update(overrides)
    return defaults


def _make_corrective_action_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "lab_id": "LAB-TEST-001",
        "finding_description": "Test finding",
        "corrective_action": "Test corrective action",
        "assigned_to": "Test Assignee",
        "due_date": now.isoformat(),
        "priority": "medium",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_proficiency_tests_count(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests()
        assert len(tests) == 12

    def test_seed_proficiency_tests_ids(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests()
        ids = {t.id for t in tests}
        for i in range(1, 13):
            assert f"PT-{i:03d}" in ids

    def test_seed_lab_comparisons_count(self, svc: LabProficiencyService):
        comparisons = svc.list_lab_comparisons()
        assert len(comparisons) == 12

    def test_seed_lab_comparisons_ids(self, svc: LabProficiencyService):
        comparisons = svc.list_lab_comparisons()
        ids = {c.id for c in comparisons}
        for i in range(1, 13):
            assert f"LC-{i:03d}" in ids

    def test_seed_accreditation_records_count(self, svc: LabProficiencyService):
        records = svc.list_accreditation_records()
        assert len(records) == 12

    def test_seed_accreditation_records_ids(self, svc: LabProficiencyService):
        records = svc.list_accreditation_records()
        ids = {r.id for r in records}
        for i in range(1, 13):
            assert f"ACC-{i:03d}" in ids

    def test_seed_corrective_actions_count(self, svc: LabProficiencyService):
        actions = svc.list_corrective_actions()
        assert len(actions) == 12

    def test_seed_corrective_actions_ids(self, svc: LabProficiencyService):
        actions = svc.list_corrective_actions()
        ids = {a.id for a in actions}
        for i in range(1, 13):
            assert f"LCA-{i:03d}" in ids

    def test_seed_proficiency_tests_have_all_trials(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests()
        trial_ids = {t.trial_id for t in tests}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_proficiency_tests_have_multiple_categories(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests()
        categories = {t.test_category for t in tests}
        assert TestCategory.CLINICAL_CHEMISTRY in categories
        assert TestCategory.HEMATOLOGY in categories
        assert TestCategory.IMMUNOLOGY in categories
        assert TestCategory.MOLECULAR in categories

    def test_seed_proficiency_tests_have_multiple_results(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests()
        results = {t.test_result for t in tests}
        assert TestResult.SATISFACTORY in results
        assert TestResult.UNSATISFACTORY in results
        assert TestResult.MARGINAL in results
        assert TestResult.PENDING in results

    def test_seed_lab_comparisons_have_multiple_statuses(self, svc: LabProficiencyService):
        comparisons = svc.list_lab_comparisons()
        statuses = {c.comparison_status for c in comparisons}
        assert ComparisonStatus.COMPLETED in statuses
        assert ComparisonStatus.FAILED in statuses
        assert ComparisonStatus.SCHEDULED in statuses

    def test_seed_accreditation_records_have_multiple_statuses(self, svc: LabProficiencyService):
        records = svc.list_accreditation_records()
        statuses = {r.accreditation_status for r in records}
        assert AccreditationStatus.ACTIVE in statuses
        assert AccreditationStatus.EXPIRED in statuses
        assert AccreditationStatus.PENDING_RENEWAL in statuses
        assert AccreditationStatus.SUSPENDED in statuses

    def test_seed_corrective_actions_have_multiple_priorities(self, svc: LabProficiencyService):
        actions = svc.list_corrective_actions()
        priorities = {a.priority for a in actions}
        assert CorrectiveActionPriority.CRITICAL in priorities
        assert CorrectiveActionPriority.HIGH in priorities
        assert CorrectiveActionPriority.MEDIUM in priorities
        assert CorrectiveActionPriority.LOW in priorities


# =====================================================================
# PROFICIENCY TEST CRUD
# =====================================================================


class TestProficiencyTestCRUD:
    """Test proficiency test create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_proficiency_tests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_category_chemistry(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"test_category": "clinical_chemistry"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["test_category"] == "clinical_chemistry"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_category_immunology(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"test_category": "immunology"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["test_category"] == "immunology"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_result_satisfactory(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"test_result": "satisfactory"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["test_result"] == "satisfactory"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_result_unsatisfactory(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"test_result": "unsatisfactory"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["test_result"] == "unsatisfactory"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests",
            params={"trial_id": EYLEA_TRIAL, "test_category": "clinical_chemistry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["test_category"] == "clinical_chemistry"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_proficiency_test(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PT-001"
        assert data["test_category"] == "clinical_chemistry"
        assert data["test_result"] == "satisfactory"
        assert data["analyte_name"] == "Glucose"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_proficiency_test_pt003(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PT-003"
        assert data["test_result"] == "unsatisfactory"
        assert data["z_score"] == 3.5

    @pytest.mark.anyio
    async def test_get_proficiency_test_pt009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PT-009"
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["analyte_name"] == "PD-L1"

    @pytest.mark.anyio
    async def test_get_proficiency_test_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_proficiency_test(self, client: AsyncClient):
        payload = _make_proficiency_test_create()
        resp = await client.post(f"{API_PREFIX}/proficiency-tests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["test_name"] == "Test Proficiency Panel"
        assert data["test_category"] == "clinical_chemistry"
        assert data["test_result"] == "pending"
        assert data["analyte_name"] == "Glucose"
        assert data["id"].startswith("PT-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_proficiency_test_hematology(self, client: AsyncClient):
        payload = _make_proficiency_test_create(
            test_name="Hematology Panel",
            test_category="hematology",
            analyte_name="WBC",
        )
        resp = await client.post(f"{API_PREFIX}/proficiency-tests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["test_category"] == "hematology"
        assert data["analyte_name"] == "WBC"

    @pytest.mark.anyio
    async def test_create_proficiency_test_appears_in_list(self, client: AsyncClient):
        payload = _make_proficiency_test_create(test_name="Unique Test")
        resp = await client.post(f"{API_PREFIX}/proficiency-tests", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/proficiency-tests")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_proficiency_test_result(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-007",
            json={"test_result": "satisfactory"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_result"] == "satisfactory"

    @pytest.mark.anyio
    async def test_update_proficiency_test_z_score(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-001",
            json={"z_score": -0.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["z_score"] == -0.5

    @pytest.mark.anyio
    async def test_update_proficiency_test_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-001",
            json={"notes": "Updated notes for testing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for testing"

    @pytest.mark.anyio
    async def test_update_proficiency_test_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_proficiency_test(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/proficiency-tests/PT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/proficiency-tests/PT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_proficiency_test_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/proficiency-tests/PT-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/proficiency-tests")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_proficiency_test_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/proficiency-tests/PT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LAB COMPARISON CRUD
# =====================================================================


class TestLabComparisonCRUD:
    """Test lab comparison create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_lab_comparisons(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lab-comparisons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_lab_comparisons_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lab-comparisons", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_lab_comparisons_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lab-comparisons", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_lab_comparisons_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lab-comparisons", params={"comparison_status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["comparison_status"] == "completed"

    @pytest.mark.anyio
    async def test_list_lab_comparisons_filter_status_failed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lab-comparisons", params={"comparison_status": "failed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["comparison_status"] == "failed"

    @pytest.mark.anyio
    async def test_list_lab_comparisons_filter_status_scheduled(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lab-comparisons", params={"comparison_status": "scheduled"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["comparison_status"] == "scheduled"

    @pytest.mark.anyio
    async def test_list_lab_comparisons_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lab-comparisons", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_lab_comparison(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lab-comparisons/LC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LC-001"
        assert data["comparison_status"] == "completed"
        assert data["within_tolerance"] is True
        assert data["analyte_name"] == "VEGF-A"

    @pytest.mark.anyio
    async def test_get_lab_comparison_lc003(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lab-comparisons/LC-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LC-003"
        assert data["comparison_status"] == "failed"
        assert data["within_tolerance"] is False

    @pytest.mark.anyio
    async def test_get_lab_comparison_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lab-comparisons/LC-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_lab_comparison(self, client: AsyncClient):
        payload = _make_lab_comparison_create()
        resp = await client.post(f"{API_PREFIX}/lab-comparisons", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["analyte_name"] == "Test Analyte"
        assert data["comparison_status"] == "scheduled"
        assert data["id"].startswith("LC-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_lab_comparison_appears_in_list(self, client: AsyncClient):
        payload = _make_lab_comparison_create(analyte_name="Unique Analyte")
        resp = await client.post(f"{API_PREFIX}/lab-comparisons", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/lab-comparisons")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_lab_comparison_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lab-comparisons/LC-006",
            json={"comparison_status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison_status"] == "completed"

    @pytest.mark.anyio
    async def test_update_lab_comparison_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lab-comparisons/LC-001",
            json={"notes": "Updated comparison notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated comparison notes"

    @pytest.mark.anyio
    async def test_update_lab_comparison_bias(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lab-comparisons/LC-006",
            json={"mean_bias_pct": 4.5, "cv_pct": 7.2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mean_bias_pct"] == 4.5
        assert data["cv_pct"] == 7.2

    @pytest.mark.anyio
    async def test_update_lab_comparison_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lab-comparisons/LC-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_lab_comparison(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lab-comparisons/LC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/lab-comparisons/LC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lab_comparison_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lab-comparisons/LC-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/lab-comparisons")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_lab_comparison_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lab-comparisons/LC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ACCREDITATION RECORD CRUD
# =====================================================================


class TestAccreditationRecordCRUD:
    """Test accreditation record create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_accreditation_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accreditation-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_accreditation_records_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/accreditation-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_accreditation_records_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/accreditation-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_accreditation_records_filter_status_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/accreditation-records", params={"accreditation_status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["accreditation_status"] == "active"

    @pytest.mark.anyio
    async def test_list_accreditation_records_filter_status_expired(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/accreditation-records", params={"accreditation_status": "expired"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["accreditation_status"] == "expired"

    @pytest.mark.anyio
    async def test_list_accreditation_records_filter_status_suspended(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/accreditation-records", params={"accreditation_status": "suspended"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["accreditation_status"] == "suspended"

    @pytest.mark.anyio
    async def test_list_accreditation_records_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/accreditation-records", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_accreditation_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accreditation-records/ACC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACC-001"
        assert data["accrediting_body"] == "CAP"
        assert data["accreditation_status"] == "active"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_accreditation_record_acc004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accreditation-records/ACC-004")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACC-004"
        assert data["accreditation_status"] == "suspended"

    @pytest.mark.anyio
    async def test_get_accreditation_record_acc012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accreditation-records/ACC-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACC-012"
        assert data["accreditation_status"] == "revoked"

    @pytest.mark.anyio
    async def test_get_accreditation_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accreditation-records/ACC-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_accreditation_record(self, client: AsyncClient):
        payload = _make_accreditation_record_create()
        resp = await client.post(f"{API_PREFIX}/accreditation-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["accrediting_body"] == "CAP"
        assert data["accreditation_status"] == "active"
        assert data["id"].startswith("ACC-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_accreditation_record_appears_in_list(self, client: AsyncClient):
        payload = _make_accreditation_record_create(
            accreditation_number="CAP-UNIQUE-001"
        )
        resp = await client.post(f"{API_PREFIX}/accreditation-records", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/accreditation-records")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_accreditation_record_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accreditation-records/ACC-003",
            json={"accreditation_status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accreditation_status"] == "active"

    @pytest.mark.anyio
    async def test_update_accreditation_record_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accreditation-records/ACC-001",
            json={"notes": "Updated accreditation notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated accreditation notes"

    @pytest.mark.anyio
    async def test_update_accreditation_record_conditions(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accreditation-records/ACC-001",
            json={"conditions": "Minor observation noted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"] == "Minor observation noted"

    @pytest.mark.anyio
    async def test_update_accreditation_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accreditation-records/ACC-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_accreditation_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accreditation-records/ACC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/accreditation-records/ACC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_accreditation_record_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accreditation-records/ACC-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/accreditation-records")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_accreditation_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accreditation-records/ACC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CORRECTIVE ACTION CRUD
# =====================================================================


class TestLabCorrectiveActionCRUD:
    """Test corrective action create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_corrective_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_priority_critical(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"priority": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_priority_high(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"priority": "high"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "high"

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_completed_true(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"is_completed": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_completed"] is True

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_completed_false(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"is_completed": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_completed"] is False

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions",
            params={"trial_id": LIBTAYO_TRIAL, "priority": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_corrective_actions_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_corrective_action(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/LCA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LCA-001"
        assert data["priority"] == "critical"
        assert data["is_completed"] is True
        assert data["effectiveness_verified"] is True

    @pytest.mark.anyio
    async def test_get_corrective_action_lca003(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/LCA-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LCA-003"
        assert data["priority"] == "medium"
        assert data["is_completed"] is False

    @pytest.mark.anyio
    async def test_get_corrective_action_lca010(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/LCA-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LCA-010"
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["priority"] == "critical"

    @pytest.mark.anyio
    async def test_get_corrective_action_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/LCA-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_corrective_action(self, client: AsyncClient):
        payload = _make_corrective_action_create()
        resp = await client.post(f"{API_PREFIX}/corrective-actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_description"] == "Test finding"
        assert data["corrective_action"] == "Test corrective action"
        assert data["priority"] == "medium"
        assert data["is_completed"] is False
        assert data["id"].startswith("LCA-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_corrective_action_critical(self, client: AsyncClient):
        payload = _make_corrective_action_create(
            priority="critical",
            finding_description="Critical finding",
        )
        resp = await client.post(f"{API_PREFIX}/corrective-actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "critical"

    @pytest.mark.anyio
    async def test_create_corrective_action_appears_in_list(self, client: AsyncClient):
        payload = _make_corrective_action_create(finding_description="Unique Finding")
        resp = await client.post(f"{API_PREFIX}/corrective-actions", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/corrective-actions")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_corrective_action_completed(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/LCA-003",
            json={"is_completed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_completed"] is True

    @pytest.mark.anyio
    async def test_update_corrective_action_root_cause(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/LCA-003",
            json={"root_cause": "Identified calibration drift"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause"] == "Identified calibration drift"

    @pytest.mark.anyio
    async def test_update_corrective_action_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/LCA-001",
            json={"notes": "Updated corrective action notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated corrective action notes"

    @pytest.mark.anyio
    async def test_update_corrective_action_verified(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/LCA-002",
            json={"effectiveness_verified": True, "verified_by": "Test Verifier"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["effectiveness_verified"] is True
        assert data["verified_by"] == "Test Verifier"

    @pytest.mark.anyio
    async def test_update_corrective_action_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/LCA-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_corrective_action(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-actions/LCA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/corrective-actions/LCA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_corrective_action_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-actions/LCA-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/corrective-actions")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_corrective_action_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-actions/LCA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test lab proficiency metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_proficiency_tests"] == 12
        assert data["total_comparisons"] == 12
        assert data["total_accreditations"] == 12
        assert data["total_corrective_actions"] == 12

    @pytest.mark.anyio
    async def test_metrics_tests_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        tests_by_category = data["tests_by_category"]
        assert "clinical_chemistry" in tests_by_category
        assert "immunology" in tests_by_category
        assert "hematology" in tests_by_category
        total_by_category = sum(tests_by_category.values())
        assert total_by_category == 12

    @pytest.mark.anyio
    async def test_metrics_tests_by_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        tests_by_result = data["tests_by_result"]
        assert "satisfactory" in tests_by_result
        assert "unsatisfactory" in tests_by_result
        total_by_result = sum(tests_by_result.values())
        assert total_by_result == 12

    @pytest.mark.anyio
    async def test_metrics_satisfactory_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["satisfactory_rate"] > 0
        assert data["satisfactory_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_comparisons_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        comparisons_by_status = data["comparisons_by_status"]
        assert "completed" in comparisons_by_status
        total_by_status = sum(comparisons_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_within_tolerance_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["within_tolerance_rate"] >= 0
        assert data["within_tolerance_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_accreditations_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        accreditations_by_status = data["accreditations_by_status"]
        assert "active" in accreditations_by_status
        total_by_status = sum(accreditations_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_active_accreditation_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_accreditation_rate"] > 0
        assert data["active_accreditation_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_corrective_actions_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        ca_by_priority = data["corrective_actions_by_priority"]
        assert "critical" in ca_by_priority
        assert "high" in ca_by_priority
        total_by_priority = sum(ca_by_priority.values())
        assert total_by_priority == 12

    @pytest.mark.anyio
    async def test_metrics_completion_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["corrective_action_completion_rate"] > 0
        assert data["corrective_action_completion_rate"] <= 100

    def test_service_metrics_satisfactory_rate(self, svc: LabProficiencyService):
        metrics = svc.get_metrics()
        tests = svc.list_proficiency_tests()
        graded = [
            t for t in tests
            if t.test_result not in (TestResult.PENDING, TestResult.NOT_GRADED, TestResult.WITHDRAWN)
        ]
        sat = sum(1 for t in graded if t.test_result == TestResult.SATISFACTORY)
        expected_rate = round((sat / max(1, len(graded))) * 100, 1)
        assert metrics.satisfactory_rate == expected_rate

    def test_service_metrics_active_accreditation_rate(self, svc: LabProficiencyService):
        metrics = svc.get_metrics()
        records = svc.list_accreditation_records()
        active = sum(1 for r in records if r.accreditation_status == AccreditationStatus.ACTIVE)
        expected_rate = round((active / max(1, len(records))) * 100, 1)
        assert metrics.active_accreditation_rate == expected_rate

    def test_service_metrics_completion_rate(self, svc: LabProficiencyService):
        metrics = svc.get_metrics()
        actions = svc.list_corrective_actions()
        completed = sum(1 for a in actions if a.is_completed)
        expected_rate = round((completed / max(1, len(actions))) * 100, 1)
        assert metrics.corrective_action_completion_rate == expected_rate

    def test_service_metrics_after_create(self, svc: LabProficiencyService):
        """Metrics should update after creating a new proficiency test."""
        from app.schemas.lab_proficiency import ProficiencyTestCreate, TestCategory

        initial_metrics = svc.get_metrics()
        svc.create_proficiency_test(
            ProficiencyTestCreate(
                trial_id=EYLEA_TRIAL,
                lab_id="LAB-TEST",
                lab_name="Test Lab",
                test_category=TestCategory.CLINICAL_CHEMISTRY,
                test_name="New Test",
                analyte_name="Test Analyte",
                pt_provider="CAP",
                cycle_number="2025-T1",
                test_date=datetime.now(timezone.utc),
            )
        )
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_proficiency_tests == initial_metrics.total_proficiency_tests + 1

    def test_service_metrics_after_delete(self, svc: LabProficiencyService):
        """Metrics should update after deleting a proficiency test."""
        initial_metrics = svc.get_metrics()
        svc.delete_proficiency_test("PT-001")
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_proficiency_tests == initial_metrics.total_proficiency_tests - 1


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_get_nonexistent_proficiency_test(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_lab_comparison(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lab-comparisons/LC-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_accreditation_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accreditation-records/ACC-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_corrective_action(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/LCA-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_proficiency_test(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-999",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_lab_comparison(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lab-comparisons/LC-999",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_accreditation_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accreditation-records/ACC-999",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_corrective_action(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/LCA-999",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_proficiency_test(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/proficiency-tests/PT-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_lab_comparison(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lab-comparisons/LC-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_accreditation_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accreditation-records/ACC-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_corrective_action(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-actions/LCA-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_with_no_matches(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests",
            params={"trial_id": "nonexistent", "test_category": "clinical_chemistry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# =====================================================================
# SINGLETON PATTERN
# =====================================================================


class TestSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_lab_proficiency_service()
        svc2 = get_lab_proficiency_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_lab_proficiency_service()
        svc2 = reset_lab_proficiency_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_lab_proficiency_service()
        svc.delete_proficiency_test("PT-001")
        assert svc.get_proficiency_test("PT-001") is None
        svc2 = reset_lab_proficiency_service()
        assert svc2.get_proficiency_test("PT-001") is not None

    def test_reset_reseeds_lab_comparisons(self):
        svc = get_lab_proficiency_service()
        svc.delete_lab_comparison("LC-001")
        assert svc.get_lab_comparison("LC-001") is None
        svc2 = reset_lab_proficiency_service()
        assert svc2.get_lab_comparison("LC-001") is not None

    def test_reset_reseeds_accreditation_records(self):
        svc = get_lab_proficiency_service()
        svc.delete_accreditation_record("ACC-001")
        assert svc.get_accreditation_record("ACC-001") is None
        svc2 = reset_lab_proficiency_service()
        assert svc2.get_accreditation_record("ACC-001") is not None

    def test_reset_reseeds_corrective_actions(self):
        svc = get_lab_proficiency_service()
        svc.delete_corrective_action("LCA-001")
        assert svc.get_corrective_action("LCA-001") is None
        svc2 = reset_lab_proficiency_service()
        assert svc2.get_corrective_action("LCA-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        svc1 = get_lab_proficiency_service()
        reset_lab_proficiency_service()
        svc2 = get_lab_proficiency_service()
        assert svc1 is not svc2


# =====================================================================
# SERVICE-LEVEL CRUD
# =====================================================================


class TestServiceLevelCRUD:
    """Test service-level CRUD operations directly."""

    # --- Proficiency Tests ---

    def test_service_list_proficiency_tests_filter_category(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests(test_category=TestCategory.CLINICAL_CHEMISTRY)
        assert len(tests) > 0
        for t in tests:
            assert t.test_category == TestCategory.CLINICAL_CHEMISTRY

    def test_service_list_proficiency_tests_filter_result(self, svc: LabProficiencyService):
        tests = svc.list_proficiency_tests(test_result=TestResult.SATISFACTORY)
        assert len(tests) > 0
        for t in tests:
            assert t.test_result == TestResult.SATISFACTORY

    def test_service_get_proficiency_test_none(self, svc: LabProficiencyService):
        result = svc.get_proficiency_test("PT-NONEXISTENT")
        assert result is None

    def test_service_delete_proficiency_test_nonexistent(self, svc: LabProficiencyService):
        result = svc.delete_proficiency_test("PT-NONEXISTENT")
        assert result is False

    # --- Lab Comparisons ---

    def test_service_list_lab_comparisons_filter_status(self, svc: LabProficiencyService):
        comparisons = svc.list_lab_comparisons(comparison_status=ComparisonStatus.COMPLETED)
        assert len(comparisons) > 0
        for c in comparisons:
            assert c.comparison_status == ComparisonStatus.COMPLETED

    def test_service_get_lab_comparison_none(self, svc: LabProficiencyService):
        result = svc.get_lab_comparison("LC-NONEXISTENT")
        assert result is None

    def test_service_delete_lab_comparison_nonexistent(self, svc: LabProficiencyService):
        result = svc.delete_lab_comparison("LC-NONEXISTENT")
        assert result is False

    # --- Accreditation Records ---

    def test_service_list_accreditation_records_filter_status(self, svc: LabProficiencyService):
        records = svc.list_accreditation_records(accreditation_status=AccreditationStatus.ACTIVE)
        assert len(records) > 0
        for r in records:
            assert r.accreditation_status == AccreditationStatus.ACTIVE

    def test_service_get_accreditation_record_none(self, svc: LabProficiencyService):
        result = svc.get_accreditation_record("ACC-NONEXISTENT")
        assert result is None

    def test_service_delete_accreditation_record_nonexistent(self, svc: LabProficiencyService):
        result = svc.delete_accreditation_record("ACC-NONEXISTENT")
        assert result is False

    # --- Corrective Actions ---

    def test_service_list_corrective_actions_filter_priority(self, svc: LabProficiencyService):
        actions = svc.list_corrective_actions(priority=CorrectiveActionPriority.CRITICAL)
        assert len(actions) > 0
        for a in actions:
            assert a.priority == CorrectiveActionPriority.CRITICAL

    def test_service_list_corrective_actions_filter_completed(self, svc: LabProficiencyService):
        completed = svc.list_corrective_actions(is_completed=True)
        not_completed = svc.list_corrective_actions(is_completed=False)
        assert len(completed) + len(not_completed) == 12
        assert len(completed) > 0
        assert len(not_completed) > 0

    def test_service_get_corrective_action_none(self, svc: LabProficiencyService):
        result = svc.get_corrective_action("LCA-NONEXISTENT")
        assert result is None

    def test_service_delete_corrective_action_nonexistent(self, svc: LabProficiencyService):
        result = svc.delete_corrective_action("LCA-NONEXISTENT")
        assert result is False
