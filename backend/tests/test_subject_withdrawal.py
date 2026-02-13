"""Tests for Subject Withdrawal (SWD-MGT).

Covers:
- Seed data verification (withdrawal requests, withdrawal assessments,
  withdrawal follow-ups, data disposition records)
- Withdrawal request CRUD (create, read, update, delete, list, filter by
  trial/reason/status)
- Withdrawal assessment CRUD (create, read, update, delete, list, filter by
  trial/type/request)
- Withdrawal follow-up CRUD (create, read, update, delete, list, filter by
  trial/outcome/subject)
- Data disposition record CRUD (create, read, update, delete, list, filter by
  trial/disposition/subject)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.subject_withdrawal import (
    AssessmentType,
    DataDisposition,
    FollowUpOutcome,
    WithdrawalReason,
    WithdrawalStatus,
)
from app.services.subject_withdrawal_service import (
    SubjectWithdrawalService,
    get_subject_withdrawal_service,
    reset_subject_withdrawal_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/subject-withdrawal"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_subject_withdrawal_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SubjectWithdrawalService:
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


def _make_request_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "withdrawal_reason": "adverse_event",
        "initiated_by": "Dr. Test",
        "investigator_name": "Dr. Test",
        "request_date": "2026-01-15T09:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "withdrawal_request_id": "WDR-001",
        "assessment_type": "safety_assessment",
        "assessment_date": "2026-01-16T09:00:00Z",
        "assessor_name": "Dr. Test Assessor",
        "assessor_role": "Principal Investigator",
        "clinical_findings": "No significant findings.",
    }
    defaults.update(overrides)
    return defaults


def _make_follow_up_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "withdrawal_request_id": "WDR-001",
        "subject_id": "SUBJ-E001",
        "scheduled_date": "2026-02-15T09:00:00Z",
        "performed_by": "Nurse Test",
        "visit_number": 1,
    }
    defaults.update(overrides)
    return defaults


def _make_disposition_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "withdrawal_request_id": "WDR-001",
        "subject_id": "SUBJ-E001",
        "analysis_population": "ITT",
        "rationale": "Subject consents to data use. All data collected per protocol.",
        "statistician_name": "Dr. Stats",
        "data_disposition": "include_all",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_withdrawal_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_withdrawal_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_withdrawal_follow_ups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-follow-ups")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_data_disposition_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-disposition-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# WITHDRAWAL REQUESTS CRUD
# ===================================================================


class TestWithdrawalRequestCRUD:
    @pytest.mark.anyio
    async def test_list_withdrawal_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_withdrawal_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests/WDR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "WDR-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_withdrawal_request_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_withdrawal_request(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/withdrawal-requests", json=_make_request_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("WDR-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["withdrawal_reason"] == "adverse_event"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/withdrawal-requests")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/withdrawal-requests", json=_make_request_create())
        resp2 = await client.get(f"{API_PREFIX}/withdrawal-requests")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_withdrawal_request(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/withdrawal-requests/WDR-001",
            json={"withdrawal_status": "completed", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["withdrawal_status"] == "completed"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_withdrawal_request_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/withdrawal-requests/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_withdrawal_request(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/withdrawal-requests/WDR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/withdrawal-requests/WDR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_withdrawal_request_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/withdrawal-requests/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_withdrawal_reason(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-requests", params={"withdrawal_reason": "adverse_event"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["withdrawal_reason"] == "adverse_event"

    @pytest.mark.anyio
    async def test_filter_by_withdrawal_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-requests", params={"withdrawal_status": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["withdrawal_status"] == "completed"


# ===================================================================
# WITHDRAWAL ASSESSMENTS CRUD
# ===================================================================


class TestWithdrawalAssessmentCRUD:
    @pytest.mark.anyio
    async def test_list_withdrawal_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_withdrawal_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments/WDA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "WDA-001"

    @pytest.mark.anyio
    async def test_get_withdrawal_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_withdrawal_assessment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/withdrawal-assessments", json=_make_assessment_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("WDA-")
        assert data["assessment_type"] == "safety_assessment"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/withdrawal-assessments")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/withdrawal-assessments", json=_make_assessment_create())
        resp2 = await client.get(f"{API_PREFIX}/withdrawal-assessments")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_withdrawal_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/withdrawal-assessments/WDA-001",
            json={"safety_concerns_identified": False, "notes": "Reassessed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_concerns_identified"] is False
        assert data["notes"] == "Reassessed"

    @pytest.mark.anyio
    async def test_update_withdrawal_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/withdrawal-assessments/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_withdrawal_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/withdrawal-assessments/WDA-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_withdrawal_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/withdrawal-assessments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_assessment_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-assessments",
            params={"assessment_type": "safety_assessment"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["assessment_type"] == "safety_assessment"

    @pytest.mark.anyio
    async def test_filter_by_withdrawal_request_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-assessments",
            params={"withdrawal_request_id": "WDR-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["withdrawal_request_id"] == "WDR-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-assessments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL


# ===================================================================
# WITHDRAWAL FOLLOW-UPS CRUD
# ===================================================================


class TestWithdrawalFollowUpCRUD:
    @pytest.mark.anyio
    async def test_list_withdrawal_follow_ups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-follow-ups")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_withdrawal_follow_up(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-follow-ups/WDF-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "WDF-001"

    @pytest.mark.anyio
    async def test_get_withdrawal_follow_up_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-follow-ups/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_withdrawal_follow_up(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/withdrawal-follow-ups", json=_make_follow_up_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("WDF-")
        assert data["follow_up_outcome"] == "ongoing"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/withdrawal-follow-ups")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/withdrawal-follow-ups", json=_make_follow_up_create())
        resp2 = await client.get(f"{API_PREFIX}/withdrawal-follow-ups")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_withdrawal_follow_up(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/withdrawal-follow-ups/WDF-001",
            json={"follow_up_outcome": "completed", "notes": "Visit done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["follow_up_outcome"] == "completed"
        assert data["notes"] == "Visit done"

    @pytest.mark.anyio
    async def test_update_withdrawal_follow_up_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/withdrawal-follow-ups/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_withdrawal_follow_up(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/withdrawal-follow-ups/WDF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/withdrawal-follow-ups/WDF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_withdrawal_follow_up_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/withdrawal-follow-ups/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_follow_up_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-follow-ups", params={"follow_up_outcome": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["follow_up_outcome"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_subject_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-follow-ups", params={"subject_id": "SUBJ-E001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["subject_id"] == "SUBJ-E001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/withdrawal-follow-ups", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# DATA DISPOSITION RECORDS CRUD
# ===================================================================


class TestDataDispositionRecordCRUD:
    @pytest.mark.anyio
    async def test_list_data_disposition_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-disposition-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_data_disposition_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-disposition-records/DDR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DDR-001"

    @pytest.mark.anyio
    async def test_get_data_disposition_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-disposition-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_data_disposition_record(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/data-disposition-records", json=_make_disposition_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DDR-")
        assert data["data_disposition"] == "include_all"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/data-disposition-records")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/data-disposition-records", json=_make_disposition_create())
        resp2 = await client.get(f"{API_PREFIX}/data-disposition-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_data_disposition_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-disposition-records/DDR-001",
            json={"approved_by": "Dr. Approver", "notes": "Approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "Dr. Approver"
        assert data["notes"] == "Approved"

    @pytest.mark.anyio
    async def test_update_data_disposition_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-disposition-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_disposition_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-disposition-records/DDR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/data-disposition-records/DDR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_disposition_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-disposition-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_data_disposition(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-disposition-records",
            params={"data_disposition": "include_all"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["data_disposition"] == "include_all"

    @pytest.mark.anyio
    async def test_filter_by_subject_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-disposition-records", params={"subject_id": "SUBJ-E001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["subject_id"] == "SUBJ-E001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-disposition-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_withdrawals" in data
        assert "total_assessments" in data
        assert "total_follow_ups" in data
        assert "total_disposition_records" in data
        assert "withdrawal_rate" in data
        assert "safety_concern_rate" in data
        assert "follow_up_completion_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_withdrawals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_withdrawals"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_assessments"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_follow_ups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_follow_ups"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_disposition_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_disposition_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["withdrawals_by_reason"], dict)
        assert isinstance(data["withdrawals_by_status"], dict)
        assert isinstance(data["assessments_by_type"], dict)
        assert isinstance(data["follow_ups_by_outcome"], dict)
        assert isinstance(data["dispositions_by_type"], dict)

    @pytest.mark.anyio
    async def test_metrics_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_withdrawals"] == 4  # WDR-001 through WDR-004

    def test_metrics_service_level(self, svc: SubjectWithdrawalService):
        metrics = svc.get_metrics()
        assert metrics.total_withdrawals == 12
        assert metrics.total_assessments == 12
        assert metrics.total_follow_ups == 12
        assert metrics.total_disposition_records == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_request_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests/WDR-001")
        original = resp.json()
        original_reason = original["withdrawal_reason"]

        resp2 = await client.put(
            f"{API_PREFIX}/withdrawal-requests/WDR-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["withdrawal_reason"] == original_reason
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_assessment_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments/WDA-001")
        original = resp.json()
        original_type = original["assessment_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/withdrawal-assessments/WDA-001",
            json={"notes": "Updated assessment note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["assessment_type"] == original_type

    @pytest.mark.anyio
    async def test_update_follow_up_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-follow-ups/WDF-001")
        original = resp.json()
        original_performed_by = original["performed_by"]

        resp2 = await client.put(
            f"{API_PREFIX}/withdrawal-follow-ups/WDF-001",
            json={"notes": "Updated follow-up note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["performed_by"] == original_performed_by

    @pytest.mark.anyio
    async def test_update_disposition_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-disposition-records/DDR-001")
        original = resp.json()
        original_population = original["analysis_population"]

        resp2 = await client.put(
            f"{API_PREFIX}/data-disposition-records/DDR-001",
            json={"notes": "Updated disposition note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["analysis_population"] == original_population


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_subject_withdrawal_service()
        svc2 = get_subject_withdrawal_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_subject_withdrawal_service()
        svc2 = reset_subject_withdrawal_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_subject_withdrawal_service()
        svc.delete_withdrawal_request("WDR-001")
        assert svc.get_withdrawal_request("WDR-001") is None
        svc2 = reset_subject_withdrawal_service()
        assert svc2.get_withdrawal_request("WDR-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_withdrawal_requests_service(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_requests()
        assert len(items) == 12

    def test_get_withdrawal_request_service(self, svc: SubjectWithdrawalService):
        record = svc.get_withdrawal_request("WDR-001")
        assert record is not None
        assert record.id == "WDR-001"

    def test_list_withdrawal_assessments_service(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_assessments()
        assert len(items) == 12

    def test_get_withdrawal_assessment_service(self, svc: SubjectWithdrawalService):
        record = svc.get_withdrawal_assessment("WDA-001")
        assert record is not None
        assert record.id == "WDA-001"

    def test_list_withdrawal_follow_ups_service(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_follow_ups()
        assert len(items) == 12

    def test_get_withdrawal_follow_up_service(self, svc: SubjectWithdrawalService):
        record = svc.get_withdrawal_follow_up("WDF-001")
        assert record is not None
        assert record.id == "WDF-001"

    def test_list_data_disposition_records_service(self, svc: SubjectWithdrawalService):
        items = svc.list_data_disposition_records()
        assert len(items) == 12

    def test_get_data_disposition_record_service(self, svc: SubjectWithdrawalService):
        record = svc.get_data_disposition_record("DDR-001")
        assert record is not None
        assert record.id == "DDR-001"

    def test_delete_withdrawal_request_service(self, svc: SubjectWithdrawalService):
        assert svc.delete_withdrawal_request("WDR-001") is True
        assert svc.get_withdrawal_request("WDR-001") is None

    def test_delete_nonexistent_returns_false(self, svc: SubjectWithdrawalService):
        assert svc.delete_withdrawal_request("NONEXISTENT") is False

    def test_filter_requests_by_trial(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_requests(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_requests_by_reason(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_requests(withdrawal_reason=WithdrawalReason.ADVERSE_EVENT)
        for item in items:
            assert item.withdrawal_reason == WithdrawalReason.ADVERSE_EVENT

    def test_filter_assessments_by_type(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_assessments(assessment_type=AssessmentType.SAFETY_ASSESSMENT)
        for item in items:
            assert item.assessment_type == AssessmentType.SAFETY_ASSESSMENT

    def test_filter_follow_ups_by_outcome(self, svc: SubjectWithdrawalService):
        items = svc.list_withdrawal_follow_ups(follow_up_outcome=FollowUpOutcome.COMPLETED)
        for item in items:
            assert item.follow_up_outcome == FollowUpOutcome.COMPLETED

    def test_filter_dispositions_by_type(self, svc: SubjectWithdrawalService):
        items = svc.list_data_disposition_records(data_disposition=DataDisposition.INCLUDE_ALL)
        for item in items:
            assert item.data_disposition == DataDisposition.INCLUDE_ALL


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_withdrawal_requests(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/withdrawal-requests",
                json=_make_request_create(subject_id=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_assessments(self, client: AsyncClient):
        for aid in ["WDA-001", "WDA-002", "WDA-003"]:
            resp = await client.delete(f"{API_PREFIX}/withdrawal-assessments/{aid}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_withdrawal_request_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests/WDR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "subject_id", "site_id", "withdrawal_reason",
                       "withdrawal_status", "request_date", "initiated_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_withdrawal_assessment_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-assessments/WDA-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "withdrawal_request_id", "assessment_type",
                       "assessor_name", "clinical_findings", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_withdrawal_follow_up_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-follow-ups/WDF-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "withdrawal_request_id", "subject_id",
                       "follow_up_outcome", "scheduled_date", "performed_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_data_disposition_record_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-disposition-records/DDR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "withdrawal_request_id", "subject_id",
                       "data_disposition", "analysis_population", "statistician_name", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawal-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
