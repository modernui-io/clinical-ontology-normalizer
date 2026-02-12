"""Tests for Clinical Data Review Management (DATA-REV).

Covers:
- Seed data verification (listings, queries, cleaning tasks, edit checks, assignments)
- Data Review Listing CRUD (create, read, update, delete, list, filter by trial_id)
- Data Query CRUD (create, read, update, delete, list, filter by trial_id)
- Data Cleaning Task CRUD (create, read, update, delete, list, filter by trial_id)
- Edit Check CRUD (create, read, update, delete, list, filter by trial_id)
- Reviewer Assignment CRUD (create, read, update, delete, list, filter by trial_id)
- Metrics computation
- 404 error handling for all entity types
- 422 validation errors
- Demo data seeding and reset
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.clinical_data_review_service import (
    ClinicalDataReviewService,
    get_clinical_data_review_service,
    reset_clinical_data_review_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-data-review"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_data_review_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalDataReviewService:
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


def _make_listing_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "listing_type": "patient",
        "listing_name": "Test Patient Listing",
        "site_id": "SITE-101",
        "total_records": 100,
    }
    defaults.update(overrides)
    return defaults


def _make_query_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "subject_id": "SUBJ-9999",
        "form_name": "Demographics",
        "field_name": "weight",
        "query_text": "Weight value appears implausible. Please verify.",
        "issued_by": "Data Reviewer",
    }
    defaults.update(overrides)
    return defaults


def _make_cleaning_task_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "task_name": "Test Cleaning Task",
        "description": "Review flagged records for data consistency",
        "assigned_to": "Test Reviewer",
        "records_to_review": 50,
    }
    defaults.update(overrides)
    return defaults


def _make_edit_check_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "check_name": "Test Range Check",
        "check_description": "Validates test values within range",
        "form_name": "Test Form",
        "field_name": "test_field",
        "check_logic": "IF test_field > 100 THEN FIRE",
        "created_by": "Test DM Lead",
    }
    defaults.update(overrides)
    return defaults


def _make_reviewer_assignment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reviewer_name": "Test Reviewer",
        "reviewer_role": "Data Reviewer",
        "assigned_sites": ["SITE-101"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_listings_count(self, svc: ClinicalDataReviewService):
        listings = svc.list_data_review_listings()
        assert len(listings) == 12

    def test_seed_queries_count(self, svc: ClinicalDataReviewService):
        queries = svc.list_data_queries()
        assert len(queries) == 14

    def test_seed_cleaning_tasks_count(self, svc: ClinicalDataReviewService):
        tasks = svc.list_data_cleaning_tasks()
        assert len(tasks) == 11

    def test_seed_edit_checks_count(self, svc: ClinicalDataReviewService):
        checks = svc.list_edit_checks()
        assert len(checks) == 10

    def test_seed_reviewer_assignments_count(self, svc: ClinicalDataReviewService):
        assignments = svc.list_reviewer_assignments()
        assert len(assignments) == 10

    def test_seed_listings_have_all_types(self, svc: ClinicalDataReviewService):
        listings = svc.list_data_review_listings()
        types = {l.listing_type.value for l in listings}
        assert "patient" in types
        assert "laboratory" in types
        assert "adverse_event" in types
        assert "vital_signs" in types
        assert "efficacy" in types
        assert "visit" in types
        assert "protocol_deviation" in types
        assert "concomitant_medication" in types

    def test_seed_listings_across_trials(self, svc: ClinicalDataReviewService):
        trial_ids = {l.trial_id for l in svc.list_data_review_listings()}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_queries_have_mixed_statuses(self, svc: ClinicalDataReviewService):
        queries = svc.list_data_queries()
        statuses = {q.query_status.value for q in queries}
        assert "open" in statuses
        assert "closed" in statuses
        assert "answered" in statuses

    def test_seed_edit_checks_have_mixed_severity(self, svc: ClinicalDataReviewService):
        checks = svc.list_edit_checks()
        severities = {c.severity.value for c in checks}
        assert "warning" in severities
        assert "error" in severities
        assert "hard_stop" in severities
        assert "informational" in severities

    def test_seed_reviewer_assignments_have_active_and_inactive(self, svc: ClinicalDataReviewService):
        assignments = svc.list_reviewer_assignments()
        active_statuses = {a.is_active for a in assignments}
        assert True in active_statuses
        assert False in active_statuses


# =====================================================================
# DATA REVIEW LISTING CRUD
# =====================================================================


class TestDataReviewListingCrud:
    """Test data review listing CRUD operations."""

    @pytest.mark.anyio
    async def test_list_listings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_listings_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_listings_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_listing(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DRL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DRL-001"
        assert data["listing_name"] == "EYLEA Patient Demographics Listing"
        assert data["review_status"] == "clean"

    @pytest.mark.anyio
    async def test_get_listing_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DRL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_listing(self, client: AsyncClient):
        payload = _make_listing_create()
        resp = await client.post(f"{API_PREFIX}/listings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["listing_name"] == "Test Patient Listing"
        assert data["listing_type"] == "patient"
        assert data["review_status"] == "pending"
        assert data["id"].startswith("DRL-")

    @pytest.mark.anyio
    async def test_update_listing(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/listings/DRL-005",
            json={"review_status": "in_review", "assigned_reviewer": "Test Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "in_review"
        assert data["assigned_reviewer"] == "Test Reviewer"

    @pytest.mark.anyio
    async def test_update_listing_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/listings/DRL-NONEXISTENT",
            json={"review_status": "in_review"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_listing(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/listings/DRL-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/listings/DRL-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_listing_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/listings/DRL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_listing_validation_error(self, client: AsyncClient):
        # Missing required fields
        resp = await client.post(f"{API_PREFIX}/listings", json={"listing_name": "Incomplete"})
        assert resp.status_code == 422


# =====================================================================
# DATA QUERY CRUD
# =====================================================================


class TestDataQueryCrud:
    """Test data query CRUD operations."""

    @pytest.mark.anyio
    async def test_list_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14
        assert len(data["items"]) == 14

    @pytest.mark.anyio
    async def test_list_queries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DQ-001"
        assert data["query_status"] == "open"
        assert data["priority"] == "high"

    @pytest.mark.anyio
    async def test_get_query_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_query(self, client: AsyncClient):
        payload = _make_query_create()
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["query_text"] == "Weight value appears implausible. Please verify."
        assert data["query_status"] == "open"
        assert data["id"].startswith("DQ-")

    @pytest.mark.anyio
    async def test_update_query_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/DQ-001",
            json={"query_status": "answered", "response_text": "Value corrected.", "responded_by": "Site CRC"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_status"] == "answered"
        assert data["response_text"] == "Value corrected."
        assert data["response_date"] is not None

    @pytest.mark.anyio
    async def test_update_query_close_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/DQ-002",
            json={"query_status": "closed", "closed_by": "Dr. Park"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_status"] == "closed"
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_update_query_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/DQ-NONEXISTENT",
            json={"query_status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_query(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/queries/DQ-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/queries/DQ-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_query_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/queries/DQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_query_validation_error(self, client: AsyncClient):
        # Missing required fields
        resp = await client.post(f"{API_PREFIX}/queries", json={"query_text": "Incomplete"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_query_with_priority(self, client: AsyncClient):
        payload = _make_query_create(priority="critical")
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "critical"


# =====================================================================
# DATA CLEANING TASK CRUD
# =====================================================================


class TestDataCleaningTaskCrud:
    """Test data cleaning task CRUD operations."""

    @pytest.mark.anyio
    async def test_list_cleaning_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cleaning-tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 11
        assert len(data["items"]) == 11

    @pytest.mark.anyio
    async def test_list_cleaning_tasks_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cleaning-tasks", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_cleaning_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cleaning-tasks/DCT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DCT-001"
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_get_cleaning_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cleaning-tasks/DCT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_cleaning_task(self, client: AsyncClient):
        payload = _make_cleaning_task_create()
        resp = await client.post(f"{API_PREFIX}/cleaning-tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_name"] == "Test Cleaning Task"
        assert data["status"] == "pending"
        assert data["id"].startswith("DCT-")

    @pytest.mark.anyio
    async def test_update_cleaning_task(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cleaning-tasks/DCT-001",
            json={"records_cleaned": 100, "notes": "Progress update"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_cleaned"] == 100
        assert data["notes"] == "Progress update"

    @pytest.mark.anyio
    async def test_update_cleaning_task_complete_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cleaning-tasks/DCT-001",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_cleaning_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cleaning-tasks/DCT-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cleaning_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cleaning-tasks/DCT-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/cleaning-tasks/DCT-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cleaning_task_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cleaning-tasks/DCT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_cleaning_task_validation_error(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/cleaning-tasks", json={"task_name": "Incomplete"})
        assert resp.status_code == 422


# =====================================================================
# EDIT CHECK CRUD
# =====================================================================


class TestEditCheckCrud:
    """Test edit check CRUD operations."""

    @pytest.mark.anyio
    async def test_list_edit_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_edit_checks_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_edit_check(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks/EC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EC-001"
        assert data["check_name"] == "Lab Value Range Check"
        assert data["severity"] == "error"

    @pytest.mark.anyio
    async def test_get_edit_check_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks/EC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_edit_check(self, client: AsyncClient):
        payload = _make_edit_check_create()
        resp = await client.post(f"{API_PREFIX}/edit-checks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["check_name"] == "Test Range Check"
        assert data["is_active"] is True
        assert data["total_firings"] == 0
        assert data["id"].startswith("EC-")

    @pytest.mark.anyio
    async def test_create_edit_check_with_severity(self, client: AsyncClient):
        payload = _make_edit_check_create(severity="hard_stop")
        resp = await client.post(f"{API_PREFIX}/edit-checks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "hard_stop"

    @pytest.mark.anyio
    async def test_update_edit_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-checks/EC-005",
            json={"auto_query": True, "approved_by": "Medical Monitor"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_query"] is True
        assert data["approved_by"] == "Medical Monitor"

    @pytest.mark.anyio
    async def test_update_edit_check_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-checks/EC-001",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    @pytest.mark.anyio
    async def test_update_edit_check_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-checks/EC-NONEXISTENT",
            json={"is_active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_edit_check(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-checks/EC-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/edit-checks/EC-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_edit_check_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-checks/EC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_edit_check_validation_error(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/edit-checks", json={"check_name": "Incomplete"})
        assert resp.status_code == 422


# =====================================================================
# REVIEWER ASSIGNMENT CRUD
# =====================================================================


class TestReviewerAssignmentCrud:
    """Test reviewer assignment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reviewer_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviewer-assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_reviewer_assignments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reviewer-assignments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_reviewer_assignment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviewer-assignments/RA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RA-001"
        assert data["reviewer_name"] == "Dr. Sarah Chen"
        assert data["is_active"] is True

    @pytest.mark.anyio
    async def test_get_reviewer_assignment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviewer-assignments/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reviewer_assignment(self, client: AsyncClient):
        payload = _make_reviewer_assignment_create()
        resp = await client.post(f"{API_PREFIX}/reviewer-assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer_name"] == "Test Reviewer"
        assert data["is_active"] is True
        assert data["workload_records"] == 0
        assert data["id"].startswith("RA-")

    @pytest.mark.anyio
    async def test_update_reviewer_assignment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviewer-assignments/RA-010",
            json={"is_active": True, "workload_records": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True
        assert data["workload_records"] == 100

    @pytest.mark.anyio
    async def test_update_reviewer_assignment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviewer-assignments/RA-NONEXISTENT",
            json={"is_active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reviewer_assignment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reviewer-assignments/RA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reviewer-assignments/RA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reviewer_assignment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reviewer-assignments/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reviewer_assignment_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/reviewer-assignments", json={"reviewer_name": "Incomplete"}
        )
        assert resp.status_code == 422


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test clinical data review metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_listings"] == 12
        assert data["total_queries"] == 14
        assert data["total_cleaning_tasks"] == 11
        assert data["total_edit_checks"] == 10
        assert data["total_reviewers"] == 10

    @pytest.mark.anyio
    async def test_metrics_listings_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_type = sum(data["listings_by_type"].values())
        assert total_by_type == data["total_listings"]

    @pytest.mark.anyio
    async def test_metrics_listings_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["listings_by_status"].values())
        assert total_by_status == data["total_listings"]

    @pytest.mark.anyio
    async def test_metrics_queries_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["queries_by_status"].values())
        assert total_by_status == data["total_queries"]

    @pytest.mark.anyio
    async def test_metrics_queries_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_priority = sum(data["queries_by_priority"].values())
        assert total_by_priority == data["total_queries"]

    def test_metrics_overall_review_completion(self, svc: ClinicalDataReviewService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.overall_review_completion_pct <= 100

    def test_metrics_avg_query_resolution(self, svc: ClinicalDataReviewService):
        metrics = svc.get_metrics()
        assert metrics.avg_query_resolution_days >= 0

    def test_metrics_cleaning_tasks_completed(self, svc: ClinicalDataReviewService):
        metrics = svc.get_metrics()
        assert metrics.cleaning_tasks_completed <= metrics.total_cleaning_tasks

    def test_metrics_active_edit_checks(self, svc: ClinicalDataReviewService):
        metrics = svc.get_metrics()
        assert metrics.active_edit_checks <= metrics.total_edit_checks
        assert metrics.active_edit_checks > 0

    def test_metrics_active_reviewers(self, svc: ClinicalDataReviewService):
        metrics = svc.get_metrics()
        assert metrics.active_reviewers <= metrics.total_reviewers
        assert metrics.active_reviewers > 0

    def test_metrics_avg_false_positive_rate(self, svc: ClinicalDataReviewService):
        metrics = svc.get_metrics()
        assert metrics.avg_false_positive_rate >= 0


# =====================================================================
# LIST FILTERING
# =====================================================================


class TestListFiltering:
    """Test trial_id filtering across all entity types."""

    @pytest.mark.anyio
    async def test_listings_filter_returns_subset(self, client: AsyncClient):
        all_resp = await client.get(f"{API_PREFIX}/listings")
        filtered_resp = await client.get(
            f"{API_PREFIX}/listings", params={"trial_id": EYLEA_TRIAL}
        )
        assert filtered_resp.json()["total"] < all_resp.json()["total"]

    @pytest.mark.anyio
    async def test_queries_filter_returns_subset(self, client: AsyncClient):
        all_resp = await client.get(f"{API_PREFIX}/queries")
        filtered_resp = await client.get(
            f"{API_PREFIX}/queries", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert filtered_resp.json()["total"] < all_resp.json()["total"]

    @pytest.mark.anyio
    async def test_cleaning_tasks_filter_returns_subset(self, client: AsyncClient):
        all_resp = await client.get(f"{API_PREFIX}/cleaning-tasks")
        filtered_resp = await client.get(
            f"{API_PREFIX}/cleaning-tasks", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert filtered_resp.json()["total"] < all_resp.json()["total"]

    @pytest.mark.anyio
    async def test_edit_checks_filter_returns_subset(self, client: AsyncClient):
        all_resp = await client.get(f"{API_PREFIX}/edit-checks")
        filtered_resp = await client.get(
            f"{API_PREFIX}/edit-checks", params={"trial_id": EYLEA_TRIAL}
        )
        assert filtered_resp.json()["total"] < all_resp.json()["total"]

    @pytest.mark.anyio
    async def test_reviewer_assignments_filter_returns_subset(self, client: AsyncClient):
        all_resp = await client.get(f"{API_PREFIX}/reviewer-assignments")
        filtered_resp = await client.get(
            f"{API_PREFIX}/reviewer-assignments", params={"trial_id": EYLEA_TRIAL}
        )
        assert filtered_resp.json()["total"] < all_resp.json()["total"]

    @pytest.mark.anyio
    async def test_filter_nonexistent_trial_returns_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/listings", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_data_review_service()
        svc2 = get_clinical_data_review_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_data_review_service()
        svc2 = reset_clinical_data_review_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_data_review_service()
        # Delete a listing
        svc.delete_data_review_listing("DRL-001")
        assert svc.get_data_review_listing("DRL-001") is None
        # Reset should bring it back
        svc2 = reset_clinical_data_review_service()
        assert svc2.get_data_review_listing("DRL-001") is not None


# =====================================================================
# EDGE CASES AND COMPREHENSIVE SCENARIOS
# =====================================================================


class TestEdgeCases:
    """Test edge cases and comprehensive scenarios."""

    @pytest.mark.anyio
    async def test_locked_listing_has_locked_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DRL-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "locked"
        assert data["locked_by"] is not None
        assert data["locked_date"] is not None

    @pytest.mark.anyio
    async def test_clean_listing_is_100_percent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DRL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "clean"
        assert data["completion_pct"] == 100.0

    @pytest.mark.anyio
    async def test_pending_listing_has_zero_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DRL-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "pending"
        assert data["reviewed_records"] == 0
        assert data["completion_pct"] == 0.0

    @pytest.mark.anyio
    async def test_query_with_critical_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "critical"

    @pytest.mark.anyio
    async def test_cancelled_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_status"] == "cancelled"

    @pytest.mark.anyio
    async def test_requeried_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_status"] == "requeried"
        assert data["requery_count"] == 1

    @pytest.mark.anyio
    async def test_inactive_edit_check(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks/EC-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False
        assert data["false_positive_rate"] > 80  # Very high FP rate

    @pytest.mark.anyio
    async def test_inactive_reviewer(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviewer-assignments/RA-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False
        assert data["completed_records"] == 0

    @pytest.mark.anyio
    async def test_completed_cleaning_task_has_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cleaning-tasks/DCT-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_verified_cleaning_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cleaning-tasks/DCT-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified_by"] is not None
        assert data["verification_required"] is True

    @pytest.mark.anyio
    async def test_create_and_retrieve_listing(self, client: AsyncClient):
        """Full roundtrip: create then get."""
        payload = _make_listing_create(listing_name="Roundtrip Test Listing")
        create_resp = await client.post(f"{API_PREFIX}/listings", json=payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/listings/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["listing_name"] == "Roundtrip Test Listing"

    @pytest.mark.anyio
    async def test_create_and_delete_query(self, client: AsyncClient):
        """Full roundtrip: create then delete."""
        payload = _make_query_create()
        create_resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"{API_PREFIX}/queries/{created_id}")
        assert delete_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/queries/{created_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_metrics_change_after_create(self, client: AsyncClient):
        """Metrics should reflect newly created entities."""
        # Get initial metrics
        metrics_before = (await client.get(f"{API_PREFIX}/metrics")).json()

        # Create a new listing
        payload = _make_listing_create()
        await client.post(f"{API_PREFIX}/listings", json=payload)

        # Get updated metrics
        metrics_after = (await client.get(f"{API_PREFIX}/metrics")).json()
        assert metrics_after["total_listings"] == metrics_before["total_listings"] + 1

    @pytest.mark.anyio
    async def test_metrics_change_after_delete(self, client: AsyncClient):
        """Metrics should reflect deleted entities."""
        metrics_before = (await client.get(f"{API_PREFIX}/metrics")).json()

        await client.delete(f"{API_PREFIX}/edit-checks/EC-001")

        metrics_after = (await client.get(f"{API_PREFIX}/metrics")).json()
        assert metrics_after["total_edit_checks"] == metrics_before["total_edit_checks"] - 1
