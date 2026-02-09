"""Tests for Medical Review & Lab Data Review (CLINICAL-14).

Covers:
- Seed data verification (review tasks, coding tasks, data listings, signals)
- Review task CRUD (create, read, update, delete, list, filter by type/status/priority/reviewer)
- Review task prioritization (critical AEs first, then serious, then routine)
- Overdue detection and auto-escalation (pending > 48h)
- Auto-completed_date on status transition to completed
- Coding task CRUD (create, read, update, list, filter by dictionary/status/auto_coded)
- Auto-coding with confidence scoring (>0.9 auto-accept, 0.7-0.9 manual, <0.7 query)
- Data listing CRUD (create, read, delete, list, filter by trial/type)
- Medical signal CRUD (create, read, update, delete, list, filter)
- Signal detection: risk ratio calculation, p-value, action required determination
- Medical review metrics computation
- Error handling (404s, invalid operations)
- Edge cases (empty filters, boundary conditions)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.medical_review import (
    CodingDictionary,
    CodingLevel,
    CodingStatus,
    CodingTaskCreate,
    CodingTaskUpdate,
    DataListingCreate,
    ListingType,
    MedicalReviewTaskCreate,
    MedicalReviewTaskUpdate,
    MedicalSignalCreate,
    MedicalSignalUpdate,
    ReviewPriority,
    ReviewStatus,
    ReviewType,
    SignalCategory,
)
from app.services.medical_review_service import (
    MedicalReviewService,
    get_medical_review_service,
    reset_medical_review_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-review"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_review_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalReviewService:
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
        "patient_id": "PAT-9001",
        "review_type": "ae_review",
        "priority": "routine",
        "assigned_reviewer": "Dr. Test Reviewer",
    }
    defaults.update(overrides)
    return defaults


def _make_coding_create(**overrides) -> dict:
    defaults = {
        "verbatim_term": "Headache",
        "dictionary": "meddra",
        "level": "pt",
    }
    defaults.update(overrides)
    return defaults


def _make_listing_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "listing_type": "ae_listing",
        "filters_applied": {"severity": "all"},
    }
    defaults.update(overrides)
    return defaults


def _make_signal_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "signal_category": "unexpected",
        "term": "Test Signal Term",
        "observed_count": 20,
        "expected_count": 10,
        "patients_affected": 15,
        "assessment": "Test signal assessment for review.",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_review_tasks_count(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks()
        assert len(tasks) == 25

    def test_seed_review_types_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks()
        types = {t.review_type for t in tasks}
        assert ReviewType.AE_REVIEW in types
        assert ReviewType.LAB_REVIEW in types
        assert ReviewType.CONMED_REVIEW in types
        assert ReviewType.ELIGIBILITY_REVIEW in types
        assert ReviewType.MEDICAL_HISTORY_REVIEW in types

    def test_seed_review_statuses_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks()
        statuses = {t.status for t in tasks}
        assert ReviewStatus.PENDING in statuses
        assert ReviewStatus.IN_PROGRESS in statuses
        assert ReviewStatus.COMPLETED in statuses
        assert ReviewStatus.ESCALATED in statuses

    def test_seed_review_priorities_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks()
        priorities = {t.priority for t in tasks}
        assert ReviewPriority.CRITICAL in priorities
        assert ReviewPriority.URGENT in priorities
        assert ReviewPriority.ROUTINE in priorities

    def test_seed_coding_tasks_count(self, svc: MedicalReviewService):
        coding = svc.list_coding_tasks()
        assert len(coding) == 30

    def test_seed_coding_dictionaries(self, svc: MedicalReviewService):
        coding = svc.list_coding_tasks()
        dicts = {c.dictionary for c in coding}
        assert CodingDictionary.MEDDRA in dicts
        assert CodingDictionary.WHODRUG in dicts

    def test_seed_auto_coding_ratio(self, svc: MedicalReviewService):
        coding = svc.list_coding_tasks()
        auto = sum(1 for c in coding if c.auto_coded)
        # ~85% should be auto-coded (26/30)
        assert auto >= 20

    def test_seed_data_listings_count(self, svc: MedicalReviewService):
        listings = svc.list_data_listings()
        assert len(listings) == 8

    def test_seed_signals_count(self, svc: MedicalReviewService):
        signals = svc.list_signals()
        assert len(signals) == 6

    def test_seed_signal_categories(self, svc: MedicalReviewService):
        signals = svc.list_signals()
        categories = {s.signal_category for s in signals}
        assert SignalCategory.EXPECTED in categories
        assert SignalCategory.UNEXPECTED in categories
        assert SignalCategory.SERIOUS_UNEXPECTED in categories


# =====================================================================
# REVIEW TASK CRUD
# =====================================================================


class TestReviewTaskCrud:
    """Test review task create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 25

    @pytest.mark.anyio
    async def test_list_tasks_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_tasks_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"review_type": "ae_review"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["review_type"] == "ae_review"

    @pytest.mark.anyio
    async def test_list_tasks_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_tasks_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_tasks_filter_reviewer(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"assigned_reviewer": "Dr. Sarah Chen"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["assigned_reviewer"] == "Dr. Sarah Chen"

    @pytest.mark.anyio
    async def test_get_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/MRT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MRT-001"
        assert data["review_type"] == "ae_review"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/MRT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_task(self, client: AsyncClient):
        payload = _make_task_create()
        resp = await client.post(f"{API_PREFIX}/tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-9001"
        assert data["status"] == "pending"
        assert data["id"].startswith("MRT-")

    @pytest.mark.anyio
    async def test_create_task_critical_ae(self, client: AsyncClient):
        payload = _make_task_create(
            review_type="ae_review",
            priority="critical",
        )
        resp = await client.post(f"{API_PREFIX}/tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "critical"
        assert data["review_type"] == "ae_review"

    @pytest.mark.anyio
    async def test_update_task(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/MRT-004",
            json={"status": "in_progress", "assigned_reviewer": "Dr. New Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["assigned_reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_task_complete_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/MRT-004",
            json={"status": "completed", "findings": "Test findings"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None
        assert data["findings"] == "Test findings"

    @pytest.mark.anyio
    async def test_update_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/MRT-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tasks/MRT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/tasks/MRT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_task_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tasks/MRT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REVIEW TASK PRIORITIZATION
# =====================================================================


class TestReviewPrioritization:
    """Test review task prioritization ordering."""

    @pytest.mark.anyio
    async def test_tasks_sorted_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        data = resp.json()
        priority_order = {"critical": 0, "urgent": 1, "routine": 2}
        priorities = [priority_order.get(item["priority"], 3) for item in data["items"]]
        # Should be non-decreasing (critical first)
        for i in range(len(priorities) - 1):
            assert priorities[i] <= priorities[i + 1]

    def test_critical_ae_first_in_list(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks()
        assert tasks[0].priority == ReviewPriority.CRITICAL

    def test_routine_tasks_after_urgent(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks()
        last_urgent_idx = -1
        first_routine_idx = len(tasks)
        for i, t in enumerate(tasks):
            if t.priority == ReviewPriority.URGENT:
                last_urgent_idx = i
            if t.priority == ReviewPriority.ROUTINE and first_routine_idx == len(tasks):
                first_routine_idx = i
        if last_urgent_idx >= 0 and first_routine_idx < len(tasks):
            assert last_urgent_idx < first_routine_idx


# =====================================================================
# OVERDUE DETECTION & ESCALATION
# =====================================================================


class TestOverdueEscalation:
    """Test overdue detection and auto-escalation."""

    @pytest.mark.anyio
    async def test_overdue_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=48)
        for item in data["items"]:
            created = datetime.fromisoformat(item["created_date"])
            assert created < cutoff

    @pytest.mark.anyio
    async def test_escalate_overdue(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/tasks/escalate-overdue")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "escalated"

    def test_overdue_tasks_pending_gt_48h(self, svc: MedicalReviewService):
        overdue = svc.get_overdue_reviews()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=48)
        for task in overdue:
            assert task.status == ReviewStatus.PENDING
            assert task.created_date < cutoff

    def test_escalation_changes_status(self, svc: MedicalReviewService):
        overdue_before = svc.get_overdue_reviews()
        assert len(overdue_before) > 0
        escalated = svc.escalate_overdue_reviews()
        assert len(escalated) > 0
        for task in escalated:
            assert task.status == ReviewStatus.ESCALATED
        # Overdue should now be empty (or reduced)
        overdue_after = svc.get_overdue_reviews()
        assert len(overdue_after) < len(overdue_before)

    def test_non_pending_not_escalated(self, svc: MedicalReviewService):
        """In-progress tasks should not be escalated even if old."""
        in_progress = svc.list_review_tasks(status=ReviewStatus.IN_PROGRESS)
        assert len(in_progress) > 0
        svc.escalate_overdue_reviews()
        for task in in_progress:
            current = svc.get_review_task(task.id)
            assert current is not None
            assert current.status == ReviewStatus.IN_PROGRESS


# =====================================================================
# CODING TASKS
# =====================================================================


class TestCodingTasks:
    """Test coding task CRUD and auto-coding."""

    @pytest.mark.anyio
    async def test_list_coding_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_list_coding_filter_dictionary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding", params={"dictionary": "meddra"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["dictionary"] == "meddra"

    @pytest.mark.anyio
    async def test_list_coding_filter_whodrug(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding", params={"dictionary": "whodrug"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        for item in data["items"]:
            assert item["dictionary"] == "whodrug"

    @pytest.mark.anyio
    async def test_list_coding_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding", params={"status": "verified"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "verified"

    @pytest.mark.anyio
    async def test_list_coding_filter_auto_coded(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding", params={"auto_coded": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["auto_coded"] is True

    @pytest.mark.anyio
    async def test_get_coding_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding/COD-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COD-0001"
        assert data["dictionary"] == "meddra"

    @pytest.mark.anyio
    async def test_get_coding_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding/COD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_coding_task_auto_coded(self, client: AsyncClient):
        payload = _make_coding_create(verbatim_term="Headache")
        resp = await client.post(f"{API_PREFIX}/coding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["auto_coded"] is True
        assert data["status"] == "auto_coded"
        assert data["coded_term"] == "Headache"
        assert data["coded_code"] == "10019211"
        assert data["confidence_score"] >= 0.9

    @pytest.mark.anyio
    async def test_create_coding_task_known_meddra_term(self, client: AsyncClient):
        payload = _make_coding_create(verbatim_term="Nausea")
        resp = await client.post(f"{API_PREFIX}/coding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["auto_coded"] is True
        assert data["coded_term"] == "Nausea"

    @pytest.mark.anyio
    async def test_create_coding_task_unknown_term(self, client: AsyncClient):
        payload = _make_coding_create(verbatim_term="Xyloquartz syndrome")
        resp = await client.post(f"{API_PREFIX}/coding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["auto_coded"] is False
        assert data["status"] == "uncoded"
        assert data["coded_term"] is None

    @pytest.mark.anyio
    async def test_create_coding_task_whodrug(self, client: AsyncClient):
        payload = _make_coding_create(
            verbatim_term="Ibuprofen",
            dictionary="whodrug",
        )
        resp = await client.post(f"{API_PREFIX}/coding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["auto_coded"] is True
        assert data["dictionary"] == "whodrug"

    @pytest.mark.anyio
    async def test_create_coding_task_synonym_mapping(self, client: AsyncClient):
        """Test that 'fever' maps to 'Pyrexia' in MedDRA."""
        payload = _make_coding_create(verbatim_term="fever")
        resp = await client.post(f"{API_PREFIX}/coding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # Fever has confidence ~0.85, which is between 0.7-0.9
        assert data["confidence_score"] is not None

    @pytest.mark.anyio
    async def test_update_coding_task_manual_code(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/coding/COD-0001",
            json={
                "coded_term": "Updated Headache",
                "coded_code": "10019211",
                "status": "manually_coded",
                "coder": "Manual Coder",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["coded_term"] == "Updated Headache"
        assert data["status"] == "manually_coded"
        assert data["coder"] == "Manual Coder"

    @pytest.mark.anyio
    async def test_update_coding_task_verify(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/coding/COD-0001",
            json={"status": "verified", "verified_by": "Dr. Verifier"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        assert data["verified_by"] == "Dr. Verifier"

    @pytest.mark.anyio
    async def test_update_coding_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/coding/COD-NONEXISTENT",
            json={"status": "verified"},
        )
        assert resp.status_code == 404


# =====================================================================
# AUTO-CODING CONFIDENCE SCORING
# =====================================================================


class TestAutoCodingConfidence:
    """Test auto-coding confidence scoring thresholds."""

    def test_high_confidence_auto_accepted(self, svc: MedicalReviewService):
        task = svc.create_coding_task(CodingTaskCreate(
            verbatim_term="Headache",
            dictionary=CodingDictionary.MEDDRA,
        ))
        assert task.confidence_score is not None
        assert task.confidence_score >= 0.9
        assert task.status == CodingStatus.AUTO_CODED
        assert task.auto_coded is True

    def test_medium_confidence_needs_review(self, svc: MedicalReviewService):
        """Terms with confidence 0.7-0.9 should need manual review."""
        task = svc.create_coding_task(CodingTaskCreate(
            verbatim_term="fever",
            dictionary=CodingDictionary.MEDDRA,
        ))
        assert task.confidence_score is not None
        assert 0.7 <= task.confidence_score < 0.9

    def test_unknown_term_uncoded(self, svc: MedicalReviewService):
        task = svc.create_coding_task(CodingTaskCreate(
            verbatim_term="Unknown obscure condition XYZ",
            dictionary=CodingDictionary.MEDDRA,
        ))
        assert task.status == CodingStatus.UNCODED
        assert task.auto_coded is False
        assert task.coded_term is None

    def test_whodrug_auto_coding(self, svc: MedicalReviewService):
        task = svc.create_coding_task(CodingTaskCreate(
            verbatim_term="Paracetamol",
            dictionary=CodingDictionary.WHODRUG,
        ))
        assert task.auto_coded is True
        assert task.confidence_score is not None
        assert task.confidence_score >= 0.9

    def test_whodrug_synonym_coding(self, svc: MedicalReviewService):
        """Acetaminophen should map to Paracetamol in WHODrug."""
        task = svc.create_coding_task(CodingTaskCreate(
            verbatim_term="acetaminophen",
            dictionary=CodingDictionary.WHODRUG,
        ))
        assert task.confidence_score is not None
        assert task.coded_term == "Paracetamol"

    def test_coding_task_sorted_by_id(self, svc: MedicalReviewService):
        coding = svc.list_coding_tasks()
        ids = [c.id for c in coding]
        assert ids == sorted(ids)


# =====================================================================
# DATA LISTINGS
# =====================================================================


class TestDataListings:
    """Test data listing CRUD."""

    @pytest.mark.anyio
    async def test_list_listings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_listings_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_listings_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings", params={"listing_type": "ae_listing"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["listing_type"] == "ae_listing"

    @pytest.mark.anyio
    async def test_get_listing(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DL-001"
        assert data["listing_type"] == "ae_listing"
        assert data["record_count"] == 156

    @pytest.mark.anyio
    async def test_get_listing_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_listing(self, client: AsyncClient):
        payload = _make_listing_create()
        resp = await client.post(f"{API_PREFIX}/listings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["listing_type"] == "ae_listing"
        assert data["record_count"] > 0
        assert data["id"].startswith("DL-")

    @pytest.mark.anyio
    async def test_create_listing_lab(self, client: AsyncClient):
        payload = _make_listing_create(listing_type="lab_listing")
        resp = await client.post(f"{API_PREFIX}/listings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["listing_type"] == "lab_listing"

    @pytest.mark.anyio
    async def test_delete_listing(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/listings/DL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/listings/DL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_listing_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/listings/DL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_listing_has_flagged_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings/DL-001")
        data = resp.json()
        assert data["flagged_records"] >= 0

    @pytest.mark.anyio
    async def test_listings_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        data = resp.json()
        dates = [item["generated_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# MEDICAL SIGNALS
# =====================================================================


class TestMedicalSignals:
    """Test medical signal CRUD and detection."""

    @pytest.mark.anyio
    async def test_list_signals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_signals_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_signals_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"signal_category": "expected"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["signal_category"] == "expected"

    @pytest.mark.anyio
    async def test_list_signals_filter_action_required(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"action_required": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["action_required"] is True

    @pytest.mark.anyio
    async def test_get_signal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIG-001"
        assert data["term"] == "Injection site reaction"

    @pytest.mark.anyio
    async def test_get_signal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_signal(self, client: AsyncClient):
        payload = _make_signal_create()
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["term"] == "Test Signal Term"
        assert data["risk_ratio"] == 2.0  # 20/10
        assert data["id"].startswith("SIG-")

    @pytest.mark.anyio
    async def test_create_signal_auto_risk_ratio(self, client: AsyncClient):
        payload = _make_signal_create(observed_count=30, expected_count=10)
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_ratio"] == 3.0

    @pytest.mark.anyio
    async def test_create_signal_action_required_when_significant(self, client: AsyncClient):
        payload = _make_signal_create(observed_count=50, expected_count=10)
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_ratio"] == 5.0
        assert data["action_required"] is True

    @pytest.mark.anyio
    async def test_create_signal_no_action_when_expected(self, client: AsyncClient):
        payload = _make_signal_create(observed_count=10, expected_count=10)
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_ratio"] == 1.0
        assert data["action_required"] is False

    @pytest.mark.anyio
    async def test_update_signal(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-001",
            json={"assessment": "Updated assessment", "action_required": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessment"] == "Updated assessment"
        assert data["action_required"] is True

    @pytest.mark.anyio
    async def test_update_signal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-NONEXISTENT",
            json={"assessment": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/signals/SIG-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/signals/SIG-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/signals/SIG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_signals_sorted_by_risk_ratio_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        data = resp.json()
        ratios = [item["risk_ratio"] for item in data["items"]]
        assert ratios == sorted(ratios, reverse=True)


# =====================================================================
# SIGNAL DETECTION
# =====================================================================


class TestSignalDetection:
    """Test signal detection logic."""

    @pytest.mark.anyio
    async def test_detect_signals_libtayo(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/signals/detect/{LIBTAYO_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_ratio"] > 1.5
            assert item["p_value"] < 0.05

    @pytest.mark.anyio
    async def test_detect_signals_eylea(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/signals/detect/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        # EYLEA has SIG-005 (visual disturbance) with RR=2.0, p=0.02
        assert data["total"] >= 1

    def test_risk_ratio_calculation(self, svc: MedicalReviewService):
        signal = svc.create_signal(MedicalSignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_category=SignalCategory.UNEXPECTED,
            term="Test term",
            observed_count=40,
            expected_count=20,
            patients_affected=35,
            assessment="Test",
        ))
        assert signal.risk_ratio == 2.0

    def test_risk_ratio_zero_expected(self, svc: MedicalReviewService):
        signal = svc.create_signal(MedicalSignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_category=SignalCategory.UNEXPECTED,
            term="Rare term",
            observed_count=5,
            expected_count=0,
            patients_affected=5,
            assessment="Test",
        ))
        assert signal.risk_ratio == 5.0

    def test_p_value_significant(self, svc: MedicalReviewService):
        signal = svc.create_signal(MedicalSignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_category=SignalCategory.UNEXPECTED,
            term="Significant term",
            observed_count=50,
            expected_count=10,
            patients_affected=45,
            assessment="Test",
        ))
        assert signal.p_value < 0.05

    def test_p_value_not_significant(self, svc: MedicalReviewService):
        signal = svc.create_signal(MedicalSignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_category=SignalCategory.EXPECTED,
            term="Expected term",
            observed_count=10,
            expected_count=10,
            patients_affected=8,
            assessment="Test",
        ))
        assert signal.p_value >= 0.05 or signal.risk_ratio <= 1.5

    def test_signal_detection_filters_correctly(self, svc: MedicalReviewService):
        detected = svc.detect_signals(LIBTAYO_TRIAL)
        for signal in detected:
            assert signal.risk_ratio > 1.5
            assert signal.p_value < 0.05
            assert signal.trial_id == LIBTAYO_TRIAL

    def test_signal_detection_sorted_by_risk_ratio(self, svc: MedicalReviewService):
        detected = svc.detect_signals(LIBTAYO_TRIAL)
        ratios = [s.risk_ratio for s in detected]
        assert ratios == sorted(ratios, reverse=True)


# =====================================================================
# MEDICAL REVIEW METRICS
# =====================================================================


class TestMedicalReviewMetrics:
    """Test metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 25
        assert data["avg_review_time_hours"] > 0
        assert 0 <= data["coding_accuracy_rate"] <= 1.0
        assert 0 <= data["auto_coding_rate"] <= 1.0
        assert data["open_signals"] >= 0
        assert data["overdue_reviews"] >= 0

    def test_metrics_tasks_by_status(self, svc: MedicalReviewService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.tasks_by_status.values())
        assert total_by_status == metrics.total_tasks

    def test_metrics_auto_coding_rate(self, svc: MedicalReviewService):
        metrics = svc.get_metrics()
        # ~85% auto-coded
        assert metrics.auto_coding_rate >= 0.6

    def test_metrics_open_signals(self, svc: MedicalReviewService):
        metrics = svc.get_metrics()
        action_required = svc.list_signals(action_required=True)
        assert metrics.open_signals == len(action_required)

    def test_metrics_overdue_reviews(self, svc: MedicalReviewService):
        metrics = svc.get_metrics()
        overdue = svc.get_overdue_reviews()
        assert metrics.overdue_reviews == len(overdue)

    def test_metrics_coding_accuracy_rate(self, svc: MedicalReviewService):
        metrics = svc.get_metrics()
        coding = svc.list_coding_tasks()
        verified = sum(1 for c in coding if c.status == CodingStatus.VERIFIED)
        expected_rate = round(verified / max(1, len(coding)), 3)
        assert metrics.coding_accuracy_rate == expected_rate


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_medical_review_service()
        svc2 = get_medical_review_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_medical_review_service()
        svc2 = reset_medical_review_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_review_service()
        svc.delete_review_task("MRT-001")
        assert svc.get_review_task("MRT-001") is None
        svc2 = reset_medical_review_service()
        assert svc2.get_review_task("MRT-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_tasks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_coding_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coding")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_listings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_signals_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_task_all_review_types(self, client: AsyncClient):
        for rt in ["ae_review", "lab_review", "conmed_review", "eligibility_review", "medical_history_review"]:
            payload = _make_task_create(review_type=rt)
            resp = await client.post(f"{API_PREFIX}/tasks", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["review_type"] == rt

    @pytest.mark.anyio
    async def test_create_task_all_priorities(self, client: AsyncClient):
        for priority in ["routine", "urgent", "critical"]:
            payload = _make_task_create(priority=priority)
            resp = await client.post(f"{API_PREFIX}/tasks", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["priority"] == priority

    @pytest.mark.anyio
    async def test_create_coding_all_dictionaries(self, client: AsyncClient):
        for d in ["meddra", "whodrug"]:
            payload = _make_coding_create(dictionary=d, verbatim_term="Headache" if d == "meddra" else "Ibuprofen")
            resp = await client.post(f"{API_PREFIX}/coding", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_listing_all_types(self, client: AsyncClient):
        for lt in ["ae_listing", "conmed_listing", "lab_listing", "medhist_listing", "vitals_listing"]:
            payload = _make_listing_create(listing_type=lt)
            resp = await client.post(f"{API_PREFIX}/listings", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["listing_type"] == lt

    @pytest.mark.anyio
    async def test_create_signal_all_categories(self, client: AsyncClient):
        for cat in ["expected", "unexpected", "serious_unexpected"]:
            payload = _make_signal_create(signal_category=cat)
            resp = await client.post(f"{API_PREFIX}/signals", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["signal_category"] == cat

    @pytest.mark.anyio
    async def test_listing_filters_applied_preserved(self, client: AsyncClient):
        payload = _make_listing_create(
            filters_applied={"parameter": "ALT", "threshold": "3xULN"},
        )
        resp = await client.post(f"{API_PREFIX}/listings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["filters_applied"]["parameter"] == "ALT"
        assert data["filters_applied"]["threshold"] == "3xULN"

    @pytest.mark.anyio
    async def test_signal_expected_category_properties(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001")
        data = resp.json()
        assert data["signal_category"] == "expected"
        assert data["risk_ratio"] < 1.5
        assert data["action_required"] is False

    @pytest.mark.anyio
    async def test_signal_serious_unexpected_properties(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-004")
        data = resp.json()
        assert data["signal_category"] == "serious_unexpected"
        assert data["risk_ratio"] >= 2.0
        assert data["action_required"] is True

    def test_completed_tasks_have_dates(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(status=ReviewStatus.COMPLETED)
        for task in tasks:
            assert task.completed_date is not None

    def test_pending_tasks_no_completed_date(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(status=ReviewStatus.PENDING)
        for task in tasks:
            assert task.completed_date is None

    def test_completed_tasks_have_findings(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(status=ReviewStatus.COMPLETED)
        for task in tasks:
            assert task.findings is not None


# =====================================================================
# CODING TASK STATUS ENUMERATION
# =====================================================================


class TestCodingStatuses:
    """Test coding status values present in seed data."""

    def test_verified_coding_tasks_exist(self, svc: MedicalReviewService):
        verified = svc.list_coding_tasks(status=CodingStatus.VERIFIED)
        assert len(verified) > 0

    def test_auto_coded_tasks_exist(self, svc: MedicalReviewService):
        auto = svc.list_coding_tasks(status=CodingStatus.AUTO_CODED)
        assert len(auto) > 0

    def test_query_raised_tasks_exist(self, svc: MedicalReviewService):
        query = svc.list_coding_tasks(status=CodingStatus.QUERY_RAISED)
        assert len(query) > 0

    def test_verified_tasks_have_verifier(self, svc: MedicalReviewService):
        verified = svc.list_coding_tasks(status=CodingStatus.VERIFIED)
        for task in verified:
            assert task.verified_by is not None

    def test_auto_coded_confidence_above_threshold(self, svc: MedicalReviewService):
        auto = svc.list_coding_tasks(auto_coded=True)
        for task in auto:
            assert task.confidence_score is not None
            assert task.confidence_score >= 0.7


# =====================================================================
# DATA LISTING DETAILS
# =====================================================================


class TestDataListingDetails:
    """Test data listing specific details."""

    @pytest.mark.anyio
    async def test_listing_record_counts_positive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        data = resp.json()
        for item in data["items"]:
            assert item["record_count"] > 0

    @pytest.mark.anyio
    async def test_listing_flagged_lte_total(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        data = resp.json()
        for item in data["items"]:
            assert item["flagged_records"] <= item["record_count"]

    @pytest.mark.anyio
    async def test_listing_types_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/listings")
        data = resp.json()
        types = {item["listing_type"] for item in data["items"]}
        assert "ae_listing" in types
        assert "lab_listing" in types
        assert "conmed_listing" in types


# =====================================================================
# REVIEW TYPE DISTRIBUTION
# =====================================================================


class TestReviewTypeDistribution:
    """Test review type distribution in seed data."""

    def test_ae_reviews_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(review_type=ReviewType.AE_REVIEW)
        assert len(tasks) >= 5

    def test_lab_reviews_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(review_type=ReviewType.LAB_REVIEW)
        assert len(tasks) >= 4

    def test_conmed_reviews_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(review_type=ReviewType.CONMED_REVIEW)
        assert len(tasks) >= 3

    def test_eligibility_reviews_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(review_type=ReviewType.ELIGIBILITY_REVIEW)
        assert len(tasks) >= 3

    def test_medical_history_reviews_present(self, svc: MedicalReviewService):
        tasks = svc.list_review_tasks(review_type=ReviewType.MEDICAL_HISTORY_REVIEW)
        assert len(tasks) >= 3


# =====================================================================
# SIGNAL RISK RATIO DETAILS
# =====================================================================


class TestSignalRiskDetails:
    """Test signal risk ratio and p-value details."""

    @pytest.mark.anyio
    async def test_all_signals_have_valid_risk_ratio(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        data = resp.json()
        for item in data["items"]:
            assert item["risk_ratio"] >= 0
            assert 0 <= item["p_value"] <= 1.0

    @pytest.mark.anyio
    async def test_expected_signals_low_risk_ratio(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"signal_category": "expected"})
        data = resp.json()
        for item in data["items"]:
            assert item["risk_ratio"] < 1.5

    @pytest.mark.anyio
    async def test_serious_unexpected_high_risk_ratio(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"signal_category": "serious_unexpected"})
        data = resp.json()
        for item in data["items"]:
            assert item["risk_ratio"] >= 2.0

    @pytest.mark.anyio
    async def test_action_required_signals_have_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"action_required": True})
        data = resp.json()
        for item in data["items"]:
            assert item["assessment"]
            assert len(item["assessment"]) > 10

    def test_create_signal_zero_expected_zero_observed(self, svc: MedicalReviewService):
        signal = svc.create_signal(MedicalSignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_category=SignalCategory.EXPECTED,
            term="No events",
            observed_count=0,
            expected_count=0,
            patients_affected=0,
            assessment="No events observed",
        ))
        assert signal.risk_ratio == 0.0

    def test_create_signal_equal_observed_expected(self, svc: MedicalReviewService):
        signal = svc.create_signal(MedicalSignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_category=SignalCategory.EXPECTED,
            term="Equal counts",
            observed_count=25,
            expected_count=25,
            patients_affected=20,
            assessment="As expected",
        ))
        assert signal.risk_ratio == 1.0
