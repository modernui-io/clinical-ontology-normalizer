"""Tests for Adverse Event Reconciliation (AER-REC).

Covers:
- Seed data verification (12 records per entity)
- CRUD for reconciliation tasks (list, get, create, update, delete, not-found)
- CRUD for discrepancy records (list, get, create, update, delete, not-found)
- CRUD for line item comparisons (list, get, create, update, delete, not-found)
- CRUD for reconciliation sign-offs (list, get, create, update, delete, not-found)
- Trial ID filtering across all entities
- Metrics computation with and without trial filter
- Singleton reset behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.adverse_event_reconciliation_service import (
    get_adverse_event_reconciliation_service,
    reset_adverse_event_reconciliation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/adverse-event-reconciliation"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_adverse_event_reconciliation_service()
    yield svc


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
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reconciliation_period_start": (now - timedelta(days=30)).isoformat(),
        "reconciliation_period_end": now.isoformat(),
        "safety_db_name": "Test Safety DB",
        "clinical_db_name": "Test Clinical DB",
        "assigned_to": "Test User",
        "target_completion_date": (now + timedelta(days=14)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_discrepancy_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reconciliation_task_id": "RCT-00000003",
        "discrepancy_type": "date_mismatch",
        "subject_id": "SUBJ-TEST-001",
        "ae_identifier": "AE-TEST-001",
        "field_name": "onset_date",
        "description": "Test discrepancy description",
        "identified_by": "Test User",
        "identified_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_comparison_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reconciliation_task_id": "RCT-00000003",
        "subject_id": "SUBJ-TEST-001",
        "ae_identifier": "AE-TEST-001",
        "compared_by": "Test User",
        "comparison_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_sign_off_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reconciliation_task_id": "RCT-00000003",
        "sign_off_role": "Safety Physician",
        "signer_name": "Dr. Test User",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_reconciliation_tasks_count(self, fresh_service):
        tasks = fresh_service.list_reconciliation_tasks()
        assert len(tasks) == 12

    def test_seed_discrepancy_records_count(self, fresh_service):
        records = fresh_service.list_discrepancy_records()
        assert len(records) == 12

    def test_seed_line_item_comparisons_count(self, fresh_service):
        comparisons = fresh_service.list_line_item_comparisons()
        assert len(comparisons) == 12

    def test_seed_reconciliation_sign_offs_count(self, fresh_service):
        sign_offs = fresh_service.list_reconciliation_sign_offs()
        assert len(sign_offs) == 12

    def test_seed_tasks_across_three_trials(self, fresh_service):
        eylea = fresh_service.list_reconciliation_tasks(trial_id=EYLEA_TRIAL)
        dupixent = fresh_service.list_reconciliation_tasks(trial_id=DUPIXENT_TRIAL)
        libtayo = fresh_service.list_reconciliation_tasks(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_discrepancies_across_three_trials(self, fresh_service):
        eylea = fresh_service.list_discrepancy_records(trial_id=EYLEA_TRIAL)
        dupixent = fresh_service.list_discrepancy_records(trial_id=DUPIXENT_TRIAL)
        libtayo = fresh_service.list_discrepancy_records(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_comparisons_across_three_trials(self, fresh_service):
        eylea = fresh_service.list_line_item_comparisons(trial_id=EYLEA_TRIAL)
        dupixent = fresh_service.list_line_item_comparisons(trial_id=DUPIXENT_TRIAL)
        libtayo = fresh_service.list_line_item_comparisons(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_sign_offs_across_three_trials(self, fresh_service):
        eylea = fresh_service.list_reconciliation_sign_offs(trial_id=EYLEA_TRIAL)
        dupixent = fresh_service.list_reconciliation_sign_offs(trial_id=DUPIXENT_TRIAL)
        libtayo = fresh_service.list_reconciliation_sign_offs(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4


# =====================================================================
# RECONCILIATION TASKS CRUD
# =====================================================================


class TestReconciliationTasksCrud:
    """Test reconciliation task CRUD operations."""

    @pytest.mark.anyio
    async def test_list_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_tasks_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliation-tasks", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-tasks/RCT-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RCT-00000001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["reconciliation_status"] == "completed"

    @pytest.mark.anyio
    async def test_get_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-tasks/RCT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_task(self, client: AsyncClient):
        payload = _make_task_create()
        resp = await client.post(f"{API_PREFIX}/reconciliation-tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RCT-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["assigned_to"] == "Test User"

    @pytest.mark.anyio
    async def test_update_task(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliation-tasks/RCT-00000003",
            json={"reconciliation_status": "completed", "notes": "Updated via test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reconciliation_status"] == "completed"
        assert data["notes"] == "Updated via test"

    @pytest.mark.anyio
    async def test_update_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliation-tasks/RCT-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliation-tasks/RCT-00000004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reconciliation-tasks/RCT-00000004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_task_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliation-tasks/RCT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DISCREPANCY RECORDS CRUD
# =====================================================================


class TestDiscrepancyRecordsCrud:
    """Test discrepancy record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancy-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records/DSR-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSR-00000001"
        assert data["discrepancy_type"] == "date_mismatch"

    @pytest.mark.anyio
    async def test_get_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records/DSR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_record(self, client: AsyncClient):
        payload = _make_discrepancy_create()
        resp = await client.post(f"{API_PREFIX}/discrepancy-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DSR-")
        assert data["discrepancy_type"] == "date_mismatch"
        assert data["subject_id"] == "SUBJ-TEST-001"

    @pytest.mark.anyio
    async def test_update_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/discrepancy-records/DSR-00000003",
            json={
                "root_cause": "Data entry lag",
                "corrective_action": "Re-training scheduled",
                "resolved": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause"] == "Data entry lag"
        assert data["resolved"] is True

    @pytest.mark.anyio
    async def test_update_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/discrepancy-records/DSR-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/discrepancy-records/DSR-00000004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/discrepancy-records/DSR-00000004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/discrepancy-records/DSR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LINE ITEM COMPARISONS CRUD
# =====================================================================


class TestLineItemComparisonsCrud:
    """Test line item comparison CRUD operations."""

    @pytest.mark.anyio
    async def test_list_comparisons(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-item-comparisons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_comparisons_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/line-item-comparisons", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_comparison(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-item-comparisons/LIC-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LIC-00000001"
        assert data["comparison_outcome"] == "matched"

    @pytest.mark.anyio
    async def test_get_comparison_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-item-comparisons/LIC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_comparison(self, client: AsyncClient):
        payload = _make_comparison_create()
        resp = await client.post(f"{API_PREFIX}/line-item-comparisons", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("LIC-")
        assert data["subject_id"] == "SUBJ-TEST-001"

    @pytest.mark.anyio
    async def test_update_comparison(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-item-comparisons/LIC-00000003",
            json={
                "comparison_outcome": "mismatched",
                "notes": "Confirmed mismatch after review",
                "discrepancy_count": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison_outcome"] == "mismatched"
        assert data["discrepancy_count"] == 2

    @pytest.mark.anyio
    async def test_update_comparison_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-item-comparisons/LIC-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_comparison(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-item-comparisons/LIC-00000008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/line-item-comparisons/LIC-00000008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_comparison_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-item-comparisons/LIC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RECONCILIATION SIGN-OFFS CRUD
# =====================================================================


class TestReconciliationSignOffsCrud:
    """Test reconciliation sign-off CRUD operations."""

    @pytest.mark.anyio
    async def test_list_sign_offs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-sign-offs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_sign_offs_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliation-sign-offs", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_sign_off(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-sign-offs/RSO-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RSO-00000001"
        assert data["sign_off_status"] == "signed_off"

    @pytest.mark.anyio
    async def test_get_sign_off_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-sign-offs/RSO-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sign_off(self, client: AsyncClient):
        payload = _make_sign_off_create()
        resp = await client.post(f"{API_PREFIX}/reconciliation-sign-offs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RSO-")
        assert data["sign_off_role"] == "Safety Physician"
        assert data["signer_name"] == "Dr. Test User"

    @pytest.mark.anyio
    async def test_update_sign_off(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliation-sign-offs/RSO-00000004",
            json={
                "sign_off_status": "signed_off",
                "notes": "Approved after discrepancy resolution",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sign_off_status"] == "signed_off"
        assert data["notes"] == "Approved after discrepancy resolution"

    @pytest.mark.anyio
    async def test_update_sign_off_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliation-sign-offs/RSO-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sign_off(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliation-sign-offs/RSO-00000012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reconciliation-sign-offs/RSO-00000012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sign_off_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliation-sign-offs/RSO-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reconciliation_tasks"] == 12
        assert data["total_discrepancies"] == 12
        assert data["total_comparisons"] == 12
        assert data["total_sign_offs"] == 12
        assert data["discrepancy_resolution_rate"] >= 0
        assert data["match_rate"] >= 0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reconciliation_tasks"] == 4
        assert data["total_discrepancies"] == 4
        assert data["total_comparisons"] == 4
        assert data["total_sign_offs"] == 4

    @pytest.mark.anyio
    async def test_metrics_tasks_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["tasks_by_status"].values())
        assert total_by_status == data["total_reconciliation_tasks"]

    @pytest.mark.anyio
    async def test_metrics_discrepancies_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_type = sum(data["discrepancies_by_type"].values())
        assert total_by_type == data["total_discrepancies"]

    @pytest.mark.anyio
    async def test_metrics_discrepancies_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_severity = sum(data["discrepancies_by_severity"].values())
        assert total_by_severity == data["total_discrepancies"]

    @pytest.mark.anyio
    async def test_metrics_comparisons_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_outcome = sum(data["comparisons_by_outcome"].values())
        assert total_by_outcome == data["total_comparisons"]

    @pytest.mark.anyio
    async def test_metrics_sign_offs_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["sign_offs_by_status"].values())
        assert total_by_status == data["total_sign_offs"]

    @pytest.mark.anyio
    async def test_metrics_resolution_rate_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["discrepancy_resolution_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_match_rate_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["match_rate"] <= 100


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_adverse_event_reconciliation_service()
        svc2 = get_adverse_event_reconciliation_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_adverse_event_reconciliation_service()
        svc2 = reset_adverse_event_reconciliation_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_adverse_event_reconciliation_service()
        svc.delete_reconciliation_task("RCT-00000001")
        assert svc.get_reconciliation_task("RCT-00000001") is None
        svc2 = reset_adverse_event_reconciliation_service()
        assert svc2.get_reconciliation_task("RCT-00000001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and additional verification."""

    @pytest.mark.anyio
    async def test_list_tasks_empty_trial_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliation-tasks",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_task_with_status(self, client: AsyncClient):
        payload = _make_task_create(reconciliation_status="in_progress")
        resp = await client.post(f"{API_PREFIX}/reconciliation-tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reconciliation_status"] == "in_progress"

    @pytest.mark.anyio
    async def test_create_discrepancy_with_severity(self, client: AsyncClient):
        payload = _make_discrepancy_create(discrepancy_severity="critical")
        resp = await client.post(f"{API_PREFIX}/discrepancy-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["discrepancy_severity"] == "critical"

    @pytest.mark.anyio
    async def test_create_comparison_with_outcome(self, client: AsyncClient):
        payload = _make_comparison_create(comparison_outcome="matched")
        resp = await client.post(f"{API_PREFIX}/line-item-comparisons", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["comparison_outcome"] == "matched"

    @pytest.mark.anyio
    async def test_create_sign_off_with_status(self, client: AsyncClient):
        payload = _make_sign_off_create(sign_off_status="conditional")
        resp = await client.post(f"{API_PREFIX}/reconciliation-sign-offs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sign_off_status"] == "conditional"

    @pytest.mark.anyio
    async def test_seed_data_has_all_discrepancy_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancy-records")
        data = resp.json()
        types = {item["discrepancy_type"] for item in data["items"]}
        assert "date_mismatch" in types
        assert "missing_in_safety_db" in types
        assert "missing_in_clinical_db" in types
        assert "severity_mismatch" in types
        assert "causality_mismatch" in types
        assert "coding_mismatch" in types

    @pytest.mark.anyio
    async def test_seed_data_has_all_comparison_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-item-comparisons")
        data = resp.json()
        outcomes = {item["comparison_outcome"] for item in data["items"]}
        assert "matched" in outcomes
        assert "mismatched" in outcomes
        assert "partial_match" in outcomes
        assert "not_found" in outcomes
        assert "pending_review" in outcomes
        assert "excluded" in outcomes

    @pytest.mark.anyio
    async def test_seed_data_has_all_sign_off_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-sign-offs")
        data = resp.json()
        statuses = {item["sign_off_status"] for item in data["items"]}
        assert "pending" in statuses
        assert "signed_off" in statuses
        assert "rejected" in statuses
        assert "conditional" in statuses
        assert "deferred" in statuses
        assert "revoked" in statuses

    @pytest.mark.anyio
    async def test_seed_data_has_all_reconciliation_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliation-tasks")
        data = resp.json()
        statuses = {item["reconciliation_status"] for item in data["items"]}
        assert "scheduled" in statuses
        assert "in_progress" in statuses
        assert "completed" in statuses
        assert "discrepancies_found" in statuses
        assert "escalated" in statuses
        assert "closed" in statuses
