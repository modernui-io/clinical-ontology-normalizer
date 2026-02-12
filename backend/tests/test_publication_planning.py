"""Tests for Publication Planning & Management (PUB-PLAN).

Covers:
- Seed data verification (plans, manuscripts, authors, congress submissions,
  journal submissions)
- Publication plan CRUD (create, read, update, delete, list, filter by trial/status)
- Manuscript CRUD (create, read, update, delete, list, filter by plan/trial/status/type)
- Author CRUD (create, read, update, delete, list, filter by manuscript/role)
- Congress submission CRUD (create, read, update, delete, list, filter by plan/trial/tier/status)
- Journal submission CRUD (create, read, update, delete, list, filter by manuscript/decision)
- Publication metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.publication_planning import (
    AuthorRole,
    CongressTier,
    JournalTier,
    PublicationStatus,
    PublicationType,
)
from app.services.publication_planning_service import (
    PublicationPlanningService,
    get_publication_planning_service,
    reset_publication_planning_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/publication-planning"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_publication_planning_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PublicationPlanningService:
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


def _make_plan_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "plan_name": "Test Publication Plan",
        "therapeutic_area": "Ophthalmology",
        "publication_lead": "Dr. Test Lead",
    }
    defaults.update(overrides)
    return defaults


def _make_manuscript_create(**overrides) -> dict:
    defaults = {
        "plan_id": "PP-001",
        "trial_id": EYLEA_TRIAL,
        "title": "Test Manuscript Title",
        "publication_type": PublicationType.PRIMARY_MANUSCRIPT.value,
    }
    defaults.update(overrides)
    return defaults


def _make_author_create(**overrides) -> dict:
    defaults = {
        "manuscript_id": "MS-001",
        "name": "Dr. Test Author",
        "institution": "Test University",
        "role": AuthorRole.CO_AUTHOR.value,
        "order_position": 5,
    }
    defaults.update(overrides)
    return defaults


def _make_congress_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "plan_id": "PP-001",
        "trial_id": EYLEA_TRIAL,
        "congress_name": "Test Congress 2025",
        "congress_date": (now + timedelta(days=90)).isoformat(),
        "congress_tier": CongressTier.TIER_1.value,
        "abstract_title": "Test Abstract Title",
        "submission_type": PublicationType.POSTER.value,
    }
    defaults.update(overrides)
    return defaults


def _make_journal_create(**overrides) -> dict:
    defaults = {
        "manuscript_id": "MS-001",
        "journal_name": "Test Journal of Medicine",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify pre-populated demo data."""

    def test_seed_plans_count(self, svc: PublicationPlanningService):
        plans = svc.list_plans()
        assert len(plans) == 12

    def test_seed_manuscripts_count(self, svc: PublicationPlanningService):
        manuscripts = svc.list_manuscripts()
        assert len(manuscripts) == 15

    def test_seed_authors_count(self, svc: PublicationPlanningService):
        authors = svc.list_authors()
        assert len(authors) == 18

    def test_seed_congress_count(self, svc: PublicationPlanningService):
        subs = svc.list_congress_submissions()
        assert len(subs) == 12

    def test_seed_journal_count(self, svc: PublicationPlanningService):
        subs = svc.list_journal_submissions()
        assert len(subs) == 12

    def test_seed_plan_pp001(self, svc: PublicationPlanningService):
        plan = svc.get_plan("PP-001")
        assert plan is not None
        assert plan.trial_id == EYLEA_TRIAL
        assert plan.status == "active"
        assert plan.target_publications == 8

    def test_seed_plan_pp009_completed(self, svc: PublicationPlanningService):
        plan = svc.get_plan("PP-009")
        assert plan is not None
        assert plan.status == "completed"
        assert plan.completed_publications == 4

    def test_seed_manuscript_ms001_published(self, svc: PublicationPlanningService):
        ms = svc.get_manuscript("MS-001")
        assert ms is not None
        assert ms.status == PublicationStatus.PUBLISHED
        assert ms.doi is not None
        assert ms.pmid is not None

    def test_seed_manuscript_ms014_planned(self, svc: PublicationPlanningService):
        ms = svc.get_manuscript("MS-014")
        assert ms is not None
        assert ms.status == PublicationStatus.PLANNED
        assert ms.word_count == 0

    def test_seed_author_au001(self, svc: PublicationPlanningService):
        author = svc.get_author("AU-001")
        assert author is not None
        assert author.role == AuthorRole.FIRST_AUTHOR
        assert author.approved_final is True

    def test_seed_congress_cs001_published(self, svc: PublicationPlanningService):
        cs = svc.get_congress_submission("CS-001")
        assert cs is not None
        assert cs.status == PublicationStatus.PUBLISHED
        assert cs.abstract_number == "PA-0234"

    def test_seed_journal_js001_accepted(self, svc: PublicationPlanningService):
        js = svc.get_journal_submission("JS-001")
        assert js is not None
        assert js.decision == "accepted"
        assert js.round_number == 2

    def test_seed_journal_js012_rejected(self, svc: PublicationPlanningService):
        js = svc.get_journal_submission("JS-012")
        assert js is not None
        assert js.decision == "rejected"

    def test_seed_eylea_plans(self, svc: PublicationPlanningService):
        plans = svc.list_plans(trial_id=EYLEA_TRIAL)
        assert len(plans) >= 3

    def test_seed_dupixent_plans(self, svc: PublicationPlanningService):
        plans = svc.list_plans(trial_id=DUPIXENT_TRIAL)
        assert len(plans) >= 3

    def test_seed_libtayo_plans(self, svc: PublicationPlanningService):
        plans = svc.list_plans(trial_id=LIBTAYO_TRIAL)
        assert len(plans) >= 3


# ===========================================================================
# PUBLICATION PLAN CRUD
# ===========================================================================


class TestPlanCRUD:
    """Test publication plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12
        assert len(body["items"]) == 12

    @pytest.mark.anyio
    async def test_list_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_plans_filter_status_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"status": "active"})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_plans_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"status": "completed"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for item in body["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_plans_filter_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    @pytest.mark.anyio
    async def test_get_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PP-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "PP-001"
        assert body["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_plan(self, client: AsyncClient):
        payload = _make_plan_create()
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["plan_name"] == "Test Publication Plan"
        assert body["status"] == "active"
        assert body["id"].startswith("PP-")

    @pytest.mark.anyio
    async def test_create_plan_with_medical_writer(self, client: AsyncClient):
        payload = _make_plan_create(medical_writer="Jane Writer")
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["medical_writer"] == "Jane Writer"

    @pytest.mark.anyio
    async def test_create_plan_missing_required(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/plans", json={"trial_id": "t1"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_plan(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PP-001", json={"target_publications": 20})
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_publications"] == 20

    @pytest.mark.anyio
    async def test_update_plan_status(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PP-001", json={"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.anyio
    async def test_update_plan_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PP-NONEXISTENT", json={"status": "completed"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/PP-001")
        assert resp.status_code == 204
        # verify deleted
        resp2 = await client.get(f"{API_PREFIX}/plans/PP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/PP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_plan(self, client: AsyncClient):
        payload = _make_plan_create(plan_name="Roundtrip Test Plan")
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        plan_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/plans/{plan_id}")
        assert resp2.status_code == 200
        assert resp2.json()["plan_name"] == "Roundtrip Test Plan"

    @pytest.mark.anyio
    async def test_create_plan_increases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/plans")
        count_before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/plans", json=_make_plan_create())
        resp2 = await client.get(f"{API_PREFIX}/plans")
        assert resp2.json()["total"] == count_before + 1

    @pytest.mark.anyio
    async def test_delete_plan_decreases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/plans")
        count_before = resp1.json()["total"]
        await client.delete(f"{API_PREFIX}/plans/PP-001")
        resp2 = await client.get(f"{API_PREFIX}/plans")
        assert resp2.json()["total"] == count_before - 1

    @pytest.mark.anyio
    async def test_update_plan_partial(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PP-001", json={"completed_publications": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body["completed_publications"] == 5
        # Other fields unchanged
        assert body["plan_name"] is not None

    @pytest.mark.anyio
    async def test_list_plans_filter_combined(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"trial_id": EYLEA_TRIAL, "status": "active"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "active"


# ===========================================================================
# MANUSCRIPT CRUD
# ===========================================================================


class TestManuscriptCRUD:
    """Test manuscript CRUD operations."""

    @pytest.mark.anyio
    async def test_list_manuscripts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 15

    @pytest.mark.anyio
    async def test_list_manuscripts_filter_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"plan_id": "PP-001"})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["plan_id"] == "PP-001"

    @pytest.mark.anyio
    async def test_list_manuscripts_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_manuscripts_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"status": "published"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 5
        for item in body["items"]:
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_list_manuscripts_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"publication_type": "primary_manuscript"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["publication_type"] == "primary_manuscript"

    @pytest.mark.anyio
    async def test_list_manuscripts_filter_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"plan_id": "PP-NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_manuscript(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts/MS-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "MS-001"
        assert body["status"] == "published"

    @pytest.mark.anyio
    async def test_get_manuscript_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts/MS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_manuscript(self, client: AsyncClient):
        payload = _make_manuscript_create()
        resp = await client.post(f"{API_PREFIX}/manuscripts", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Test Manuscript Title"
        assert body["status"] == "planned"
        assert body["id"].startswith("MS-")

    @pytest.mark.anyio
    async def test_create_manuscript_with_journal(self, client: AsyncClient):
        payload = _make_manuscript_create(
            target_journal="Nature Medicine",
            journal_tier=JournalTier.HIGH_IMPACT.value,
        )
        resp = await client.post(f"{API_PREFIX}/manuscripts", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["target_journal"] == "Nature Medicine"
        assert body["journal_tier"] == "high_impact"

    @pytest.mark.anyio
    async def test_create_manuscript_missing_required(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/manuscripts", json={"plan_id": "PP-001"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_manuscript(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/manuscripts/MS-003", json={"word_count": 4500})
        assert resp.status_code == 200
        assert resp.json()["word_count"] == 4500

    @pytest.mark.anyio
    async def test_update_manuscript_status(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/manuscripts/MS-003", json={"status": "submitted"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

    @pytest.mark.anyio
    async def test_update_manuscript_doi(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/manuscripts/MS-002", json={"doi": "10.1234/test"})
        assert resp.status_code == 200
        assert resp.json()["doi"] == "10.1234/test"

    @pytest.mark.anyio
    async def test_update_manuscript_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/manuscripts/MS-NONEXISTENT", json={"word_count": 100})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_manuscript(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/manuscripts/MS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/manuscripts/MS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_manuscript_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/manuscripts/MS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_manuscript(self, client: AsyncClient):
        payload = _make_manuscript_create(title="Roundtrip Manuscript")
        resp = await client.post(f"{API_PREFIX}/manuscripts", json=payload)
        ms_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/manuscripts/{ms_id}")
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "Roundtrip Manuscript"

    @pytest.mark.anyio
    async def test_create_manuscript_increases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/manuscripts")
        count_before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/manuscripts", json=_make_manuscript_create())
        resp2 = await client.get(f"{API_PREFIX}/manuscripts")
        assert resp2.json()["total"] == count_before + 1

    @pytest.mark.anyio
    async def test_delete_manuscript_decreases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/manuscripts")
        count_before = resp1.json()["total"]
        await client.delete(f"{API_PREFIX}/manuscripts/MS-001")
        resp2 = await client.get(f"{API_PREFIX}/manuscripts")
        assert resp2.json()["total"] == count_before - 1

    @pytest.mark.anyio
    async def test_update_manuscript_impact_factor(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/manuscripts/MS-003", json={"impact_factor": 12.5})
        assert resp.status_code == 200
        assert resp.json()["impact_factor"] == 12.5

    @pytest.mark.anyio
    async def test_list_manuscripts_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/manuscripts",
            params={"trial_id": EYLEA_TRIAL, "status": "published"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_update_manuscript_figure_table_count(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/manuscripts/MS-011",
            json={"figure_count": 10, "table_count": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["figure_count"] == 10
        assert body["table_count"] == 5


# ===========================================================================
# AUTHOR CRUD
# ===========================================================================


class TestAuthorCRUD:
    """Test author CRUD operations."""

    @pytest.mark.anyio
    async def test_list_authors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 18

    @pytest.mark.anyio
    async def test_list_authors_filter_manuscript(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors", params={"manuscript_id": "MS-001"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        for item in body["items"]:
            assert item["manuscript_id"] == "MS-001"

    @pytest.mark.anyio
    async def test_list_authors_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors", params={"role": "first_author"})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["role"] == "first_author"

    @pytest.mark.anyio
    async def test_list_authors_filter_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors", params={"manuscript_id": "MS-NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_author(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors/AU-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "AU-001"
        assert body["role"] == "first_author"

    @pytest.mark.anyio
    async def test_get_author_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors/AU-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_author(self, client: AsyncClient):
        payload = _make_author_create()
        resp = await client.post(f"{API_PREFIX}/authors", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Dr. Test Author"
        assert body["id"].startswith("AU-")
        assert body["approved_final"] is False

    @pytest.mark.anyio
    async def test_create_author_with_orcid(self, client: AsyncClient):
        payload = _make_author_create(orcid="0000-0001-0000-0001", email="test@example.com")
        resp = await client.post(f"{API_PREFIX}/authors", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["orcid"] == "0000-0001-0000-0001"
        assert body["email"] == "test@example.com"

    @pytest.mark.anyio
    async def test_create_author_missing_required(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/authors", json={"name": "Incomplete"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_author(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/authors/AU-001", json={"approved_final": False})
        assert resp.status_code == 200
        assert resp.json()["approved_final"] is False

    @pytest.mark.anyio
    async def test_update_author_role(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/authors/AU-013", json={"role": "senior_author"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "senior_author"

    @pytest.mark.anyio
    async def test_update_author_disclosure(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/authors/AU-001",
            json={"disclosure_statement": "Consultant for Regeneron"},
        )
        assert resp.status_code == 200
        assert resp.json()["disclosure_statement"] == "Consultant for Regeneron"

    @pytest.mark.anyio
    async def test_update_author_contribution(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/authors/AU-001",
            json={"contribution_statement": "Did everything"},
        )
        assert resp.status_code == 200
        assert resp.json()["contribution_statement"] == "Did everything"

    @pytest.mark.anyio
    async def test_update_author_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/authors/AU-NONEXISTENT", json={"approved_final": True})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_author(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/authors/AU-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/authors/AU-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_author_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/authors/AU-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_author(self, client: AsyncClient):
        payload = _make_author_create(name="Roundtrip Author")
        resp = await client.post(f"{API_PREFIX}/authors", json=payload)
        au_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/authors/{au_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Roundtrip Author"

    @pytest.mark.anyio
    async def test_create_author_increases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/authors")
        count_before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/authors", json=_make_author_create())
        resp2 = await client.get(f"{API_PREFIX}/authors")
        assert resp2.json()["total"] == count_before + 1

    @pytest.mark.anyio
    async def test_delete_author_decreases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/authors")
        count_before = resp1.json()["total"]
        await client.delete(f"{API_PREFIX}/authors/AU-001")
        resp2 = await client.get(f"{API_PREFIX}/authors")
        assert resp2.json()["total"] == count_before - 1

    @pytest.mark.anyio
    async def test_list_authors_filter_corresponding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors", params={"role": "corresponding"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["role"] == "corresponding"

    @pytest.mark.anyio
    async def test_list_authors_filter_statistician(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors", params={"role": "statistician"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_list_authors_filter_medical_writer(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors", params={"role": "medical_writer"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_update_author_order_position(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/authors/AU-001", json={"order_position": 10})
        assert resp.status_code == 200
        assert resp.json()["order_position"] == 10

    @pytest.mark.anyio
    async def test_list_authors_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authors",
            params={"manuscript_id": "MS-001", "role": "first_author"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["manuscript_id"] == "MS-001"
            assert item["role"] == "first_author"


# ===========================================================================
# CONGRESS SUBMISSION CRUD
# ===========================================================================


class TestCongressSubmissionCRUD:
    """Test congress submission CRUD operations."""

    @pytest.mark.anyio
    async def test_list_congress_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12

    @pytest.mark.anyio
    async def test_list_congress_filter_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"plan_id": "PP-001"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["plan_id"] == "PP-001"

    @pytest.mark.anyio
    async def test_list_congress_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_congress_filter_tier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"congress_tier": "tier_1_major"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["congress_tier"] == "tier_1_major"

    @pytest.mark.anyio
    async def test_list_congress_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"status": "published"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_list_congress_filter_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"plan_id": "PP-NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_congress_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions/CS-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "CS-001"
        assert body["congress_tier"] == "tier_1_major"

    @pytest.mark.anyio
    async def test_get_congress_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions/CS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_congress_submission(self, client: AsyncClient):
        payload = _make_congress_create()
        resp = await client.post(f"{API_PREFIX}/congress-submissions", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["abstract_title"] == "Test Abstract Title"
        assert body["status"] == "planned"
        assert body["id"].startswith("CS-")

    @pytest.mark.anyio
    async def test_create_congress_missing_required(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/congress-submissions", json={"plan_id": "PP-001"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_congress_submission(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congress-submissions/CS-002",
            json={"status": "accepted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    @pytest.mark.anyio
    async def test_update_congress_presenter(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congress-submissions/CS-002",
            json={"presenter": "Dr. New Presenter"},
        )
        assert resp.status_code == 200
        assert resp.json()["presenter"] == "Dr. New Presenter"

    @pytest.mark.anyio
    async def test_update_congress_abstract_number(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congress-submissions/CS-002",
            json={"abstract_number": "EP-999"},
        )
        assert resp.status_code == 200
        assert resp.json()["abstract_number"] == "EP-999"

    @pytest.mark.anyio
    async def test_update_congress_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congress-submissions/CS-NONEXISTENT",
            json={"status": "accepted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_congress_submission(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/congress-submissions/CS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/congress-submissions/CS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_congress_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/congress-submissions/CS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_congress(self, client: AsyncClient):
        payload = _make_congress_create(abstract_title="Roundtrip Abstract")
        resp = await client.post(f"{API_PREFIX}/congress-submissions", json=payload)
        cs_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/congress-submissions/{cs_id}")
        assert resp2.status_code == 200
        assert resp2.json()["abstract_title"] == "Roundtrip Abstract"

    @pytest.mark.anyio
    async def test_create_congress_increases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/congress-submissions")
        count_before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/congress-submissions", json=_make_congress_create())
        resp2 = await client.get(f"{API_PREFIX}/congress-submissions")
        assert resp2.json()["total"] == count_before + 1

    @pytest.mark.anyio
    async def test_delete_congress_decreases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/congress-submissions")
        count_before = resp1.json()["total"]
        await client.delete(f"{API_PREFIX}/congress-submissions/CS-001")
        resp2 = await client.get(f"{API_PREFIX}/congress-submissions")
        assert resp2.json()["total"] == count_before - 1

    @pytest.mark.anyio
    async def test_list_congress_filter_internal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"congress_tier": "internal"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
        for item in resp.json()["items"]:
            assert item["congress_tier"] == "internal"

    @pytest.mark.anyio
    async def test_list_congress_filter_tier2(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"congress_tier": "tier_2_regional"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["congress_tier"] == "tier_2_regional"

    @pytest.mark.anyio
    async def test_list_congress_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/congress-submissions",
            params={"trial_id": EYLEA_TRIAL, "status": "published"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_update_congress_submission_date(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/congress-submissions/CS-009",
            json={"submission_date": now.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["submission_date"] is not None


# ===========================================================================
# JOURNAL SUBMISSION CRUD
# ===========================================================================


class TestJournalSubmissionCRUD:
    """Test journal submission CRUD operations."""

    @pytest.mark.anyio
    async def test_list_journal_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12

    @pytest.mark.anyio
    async def test_list_journal_filter_manuscript(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions", params={"manuscript_id": "MS-001"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for item in body["items"]:
            assert item["manuscript_id"] == "MS-001"

    @pytest.mark.anyio
    async def test_list_journal_filter_decision_accepted(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions", params={"decision": "accepted"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 5
        for item in body["items"]:
            assert item["decision"] == "accepted"

    @pytest.mark.anyio
    async def test_list_journal_filter_decision_rejected(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions", params={"decision": "rejected"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for item in body["items"]:
            assert item["decision"] == "rejected"

    @pytest.mark.anyio
    async def test_list_journal_filter_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions", params={"manuscript_id": "MS-NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_journal_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "JS-001"
        assert body["decision"] == "accepted"

    @pytest.mark.anyio
    async def test_get_journal_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions/JS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_journal_submission(self, client: AsyncClient):
        payload = _make_journal_create()
        resp = await client.post(f"{API_PREFIX}/journal-submissions", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["journal_name"] == "Test Journal of Medicine"
        assert body["round_number"] == 1
        assert body["id"].startswith("JS-")

    @pytest.mark.anyio
    async def test_create_journal_missing_required(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/journal-submissions", json={"manuscript_id": "MS-001"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_journal_submission(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/journal-submissions/JS-006",
            json={"decision": "revision_requested"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "revision_requested"

    @pytest.mark.anyio
    async def test_update_journal_reviewer_comments(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/journal-submissions/JS-006",
            json={"reviewer_comments": ["Good paper", "Needs more data"]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["reviewer_comments"]) == 2

    @pytest.mark.anyio
    async def test_update_journal_revision_due_date(self, client: AsyncClient):
        due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/journal-submissions/JS-009",
            json={"revision_due_date": due},
        )
        assert resp.status_code == 200
        assert resp.json()["revision_due_date"] is not None

    @pytest.mark.anyio
    async def test_update_journal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/journal-submissions/JS-NONEXISTENT",
            json={"decision": "accepted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_journal_submission(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_journal_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/journal-submissions/JS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_journal(self, client: AsyncClient):
        payload = _make_journal_create(journal_name="Roundtrip Journal")
        resp = await client.post(f"{API_PREFIX}/journal-submissions", json=payload)
        js_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/journal-submissions/{js_id}")
        assert resp2.status_code == 200
        assert resp2.json()["journal_name"] == "Roundtrip Journal"

    @pytest.mark.anyio
    async def test_create_journal_increases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/journal-submissions")
        count_before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/journal-submissions", json=_make_journal_create())
        resp2 = await client.get(f"{API_PREFIX}/journal-submissions")
        assert resp2.json()["total"] == count_before + 1

    @pytest.mark.anyio
    async def test_delete_journal_decreases_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/journal-submissions")
        count_before = resp1.json()["total"]
        await client.delete(f"{API_PREFIX}/journal-submissions/JS-001")
        resp2 = await client.get(f"{API_PREFIX}/journal-submissions")
        assert resp2.json()["total"] == count_before - 1

    @pytest.mark.anyio
    async def test_list_journal_filter_revision_requested(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions", params={"decision": "revision_requested"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["decision"] == "revision_requested"

    @pytest.mark.anyio
    async def test_journal_submission_ms009_multiple(self, client: AsyncClient):
        """MS-009 has two journal submissions (one rejected, one revision_requested)."""
        resp = await client.get(f"{API_PREFIX}/journal-submissions", params={"manuscript_id": "MS-009"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_journal_submission_has_tracking_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp.status_code == 200
        assert resp.json()["tracking_id"] == "NEJM-2024-12345"

    @pytest.mark.anyio
    async def test_journal_submission_reviewer_comments_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp.status_code == 200
        comments = resp.json()["reviewer_comments"]
        assert isinstance(comments, list)
        assert len(comments) == 3


# ===========================================================================
# METRICS
# ===========================================================================


class TestMetrics:
    """Test publication metrics endpoint."""

    @pytest.mark.anyio
    async def test_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_plans"] == 12
        assert body["total_manuscripts"] == 15
        assert body["total_authors"] == 18
        assert body["total_congress_submissions"] == 12
        assert body["total_journal_submissions"] == 12

    @pytest.mark.anyio
    async def test_metrics_active_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["active_plans"] >= 10

    @pytest.mark.anyio
    async def test_metrics_published_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["published_count"] >= 5

    @pytest.mark.anyio
    async def test_metrics_manuscripts_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_status = body["manuscripts_by_status"]
        assert "published" in by_status
        assert by_status["published"] >= 5

    @pytest.mark.anyio
    async def test_metrics_manuscripts_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_type = body["manuscripts_by_type"]
        assert "primary_manuscript" in by_type
        assert by_type["primary_manuscript"] >= 5

    @pytest.mark.anyio
    async def test_metrics_congress_by_tier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_tier = body["congress_by_tier"]
        assert "tier_1_major" in by_tier

    @pytest.mark.anyio
    async def test_metrics_accepted_congress_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert 0.0 <= body["accepted_congress_rate_pct"] <= 100.0

    @pytest.mark.anyio
    async def test_metrics_avg_review_rounds(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["avg_review_rounds"] >= 1.0

    @pytest.mark.anyio
    async def test_metrics_avg_submission_to_acceptance_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["avg_submission_to_acceptance_days"] > 0

    @pytest.mark.anyio
    async def test_metrics_after_create_plan(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        before_total = resp1.json()["total_plans"]
        await client.post(f"{API_PREFIX}/plans", json=_make_plan_create())
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_plans"] == before_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_delete_manuscript(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        before_total = resp1.json()["total_manuscripts"]
        await client.delete(f"{API_PREFIX}/manuscripts/MS-001")
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_manuscripts"] == before_total - 1

    @pytest.mark.anyio
    async def test_metrics_after_create_author(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        before_total = resp1.json()["total_authors"]
        await client.post(f"{API_PREFIX}/authors", json=_make_author_create())
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_authors"] == before_total + 1


# ===========================================================================
# SERVICE-LEVEL TESTS
# ===========================================================================


class TestServiceDirect:
    """Direct service-level tests for edge cases."""

    def test_get_plan_nonexistent(self, svc: PublicationPlanningService):
        assert svc.get_plan("NONEXISTENT") is None

    def test_get_manuscript_nonexistent(self, svc: PublicationPlanningService):
        assert svc.get_manuscript("NONEXISTENT") is None

    def test_get_author_nonexistent(self, svc: PublicationPlanningService):
        assert svc.get_author("NONEXISTENT") is None

    def test_get_congress_nonexistent(self, svc: PublicationPlanningService):
        assert svc.get_congress_submission("NONEXISTENT") is None

    def test_get_journal_nonexistent(self, svc: PublicationPlanningService):
        assert svc.get_journal_submission("NONEXISTENT") is None

    def test_delete_plan_nonexistent(self, svc: PublicationPlanningService):
        assert svc.delete_plan("NONEXISTENT") is False

    def test_delete_manuscript_nonexistent(self, svc: PublicationPlanningService):
        assert svc.delete_manuscript("NONEXISTENT") is False

    def test_delete_author_nonexistent(self, svc: PublicationPlanningService):
        assert svc.delete_author("NONEXISTENT") is False

    def test_delete_congress_nonexistent(self, svc: PublicationPlanningService):
        assert svc.delete_congress_submission("NONEXISTENT") is False

    def test_delete_journal_nonexistent(self, svc: PublicationPlanningService):
        assert svc.delete_journal_submission("NONEXISTENT") is False

    def test_update_plan_nonexistent(self, svc: PublicationPlanningService):
        result = svc.update_plan("NONEXISTENT", PublicationPlanUpdate(status="completed"))
        assert result is None

    def test_update_manuscript_nonexistent(self, svc: PublicationPlanningService):
        result = svc.update_manuscript("NONEXISTENT", ManuscriptUpdate(word_count=100))
        assert result is None

    def test_update_author_nonexistent(self, svc: PublicationPlanningService):
        result = svc.update_author("NONEXISTENT", AuthorUpdate(approved_final=True))
        assert result is None

    def test_update_congress_nonexistent(self, svc: PublicationPlanningService):
        result = svc.update_congress_submission("NONEXISTENT", CongressSubmissionUpdate(status=PublicationStatus.ACCEPTED))
        assert result is None

    def test_update_journal_nonexistent(self, svc: PublicationPlanningService):
        result = svc.update_journal_submission("NONEXISTENT", JournalSubmissionUpdate(decision="accepted"))
        assert result is None

    def test_list_plans_sorted(self, svc: PublicationPlanningService):
        plans = svc.list_plans()
        ids = [p.id for p in plans]
        assert ids == sorted(ids)

    def test_list_manuscripts_sorted(self, svc: PublicationPlanningService):
        manuscripts = svc.list_manuscripts()
        ids = [m.id for m in manuscripts]
        assert ids == sorted(ids)

    def test_list_authors_sorted(self, svc: PublicationPlanningService):
        authors = svc.list_authors()
        ids = [a.id for a in authors]
        assert ids == sorted(ids)

    def test_list_congress_sorted(self, svc: PublicationPlanningService):
        subs = svc.list_congress_submissions()
        ids = [s.id for s in subs]
        assert ids == sorted(ids)

    def test_list_journal_sorted(self, svc: PublicationPlanningService):
        subs = svc.list_journal_submissions()
        ids = [s.id for s in subs]
        assert ids == sorted(ids)

    def test_create_plan_returns_active(self, svc: PublicationPlanningService):
        from app.schemas.publication_planning import PublicationPlanCreate
        payload = PublicationPlanCreate(
            trial_id=EYLEA_TRIAL,
            plan_name="Direct Test",
            therapeutic_area="Test",
            publication_lead="Dr. X",
        )
        plan = svc.create_plan(payload)
        assert plan.status == "active"
        assert plan.target_publications == 0
        assert plan.completed_publications == 0

    def test_create_manuscript_returns_planned(self, svc: PublicationPlanningService):
        from app.schemas.publication_planning import ManuscriptCreate
        payload = ManuscriptCreate(
            plan_id="PP-001",
            trial_id=EYLEA_TRIAL,
            title="Direct Test MS",
            publication_type=PublicationType.PRIMARY_MANUSCRIPT,
        )
        ms = svc.create_manuscript(payload)
        assert ms.status == PublicationStatus.PLANNED
        assert ms.word_count == 0

    def test_create_congress_returns_planned(self, svc: PublicationPlanningService):
        from app.schemas.publication_planning import CongressSubmissionCreate
        now = datetime.now(timezone.utc)
        payload = CongressSubmissionCreate(
            plan_id="PP-001",
            trial_id=EYLEA_TRIAL,
            congress_name="Direct Test Congress",
            congress_date=now + timedelta(days=90),
            congress_tier=CongressTier.TIER_1,
            abstract_title="Test Abstract",
            submission_type=PublicationType.POSTER,
        )
        cs = svc.create_congress_submission(payload)
        assert cs.status == PublicationStatus.PLANNED

    def test_create_journal_sets_date(self, svc: PublicationPlanningService):
        from app.schemas.publication_planning import JournalSubmissionCreate
        payload = JournalSubmissionCreate(
            manuscript_id="MS-001",
            journal_name="Direct Test Journal",
        )
        js = svc.create_journal_submission(payload)
        assert js.submission_date is not None
        assert js.round_number == 1

    def test_create_author_not_approved(self, svc: PublicationPlanningService):
        from app.schemas.publication_planning import AuthorCreate
        payload = AuthorCreate(
            manuscript_id="MS-001",
            name="New Author",
            institution="Test Uni",
            role=AuthorRole.CO_AUTHOR,
            order_position=10,
        )
        author = svc.create_author(payload)
        assert author.approved_final is False

    def test_metrics_returns_valid(self, svc: PublicationPlanningService):
        metrics = svc.get_metrics()
        assert metrics.total_plans == 12
        assert metrics.active_plans >= 10
        assert metrics.total_manuscripts == 15
        assert metrics.published_count >= 5
        assert metrics.total_authors == 18
        assert metrics.total_congress_submissions == 12
        assert metrics.total_journal_submissions == 12
        assert 0.0 <= metrics.accepted_congress_rate_pct <= 100.0
        assert metrics.avg_review_rounds >= 1.0
        assert metrics.avg_submission_to_acceptance_days > 0

    def test_reset_service(self):
        svc = get_publication_planning_service()
        svc.delete_plan("PP-001")
        assert svc.get_plan("PP-001") is None
        svc2 = reset_publication_planning_service()
        assert svc2.get_plan("PP-001") is not None

    def test_singleton_returns_same_instance(self):
        svc1 = get_publication_planning_service()
        svc2 = get_publication_planning_service()
        assert svc1 is svc2

    def test_list_manuscripts_filter_all_four(self, svc: PublicationPlanningService):
        items = svc.list_manuscripts(
            plan_id="PP-001",
            trial_id=EYLEA_TRIAL,
            status=PublicationStatus.PUBLISHED,
            publication_type=PublicationType.PRIMARY_MANUSCRIPT,
        )
        assert len(items) >= 1
        for m in items:
            assert m.plan_id == "PP-001"
            assert m.trial_id == EYLEA_TRIAL
            assert m.status == PublicationStatus.PUBLISHED
            assert m.publication_type == PublicationType.PRIMARY_MANUSCRIPT

    def test_list_congress_filter_all_four(self, svc: PublicationPlanningService):
        items = svc.list_congress_submissions(
            plan_id="PP-001",
            trial_id=EYLEA_TRIAL,
            congress_tier=CongressTier.TIER_1,
            status=PublicationStatus.PUBLISHED,
        )
        assert len(items) >= 1

    def test_plan_all_trials_present(self, svc: PublicationPlanningService):
        all_plans = svc.list_plans()
        trial_ids = {p.trial_id for p in all_plans}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_manuscript_all_trials_present(self, svc: PublicationPlanningService):
        all_ms = svc.list_manuscripts()
        trial_ids = {m.trial_id for m in all_ms}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids


# ===========================================================================
# VALIDATION / EDGE CASE TESTS
# ===========================================================================


class TestValidationEdgeCases:
    """Test validation errors and edge cases."""

    @pytest.mark.anyio
    async def test_create_plan_empty_body(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/plans", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_manuscript_empty_body(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/manuscripts", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_author_empty_body(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/authors", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_congress_empty_body(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/congress-submissions", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_journal_empty_body(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/journal-submissions", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_author_invalid_role(self, client: AsyncClient):
        payload = _make_author_create(role="invalid_role")
        resp = await client.post(f"{API_PREFIX}/authors", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_manuscript_invalid_type(self, client: AsyncClient):
        payload = _make_manuscript_create(publication_type="invalid_type")
        resp = await client.post(f"{API_PREFIX}/manuscripts", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_congress_invalid_tier(self, client: AsyncClient):
        payload = _make_congress_create(congress_tier="invalid_tier")
        resp = await client.post(f"{API_PREFIX}/congress-submissions", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_author_order_position_zero(self, client: AsyncClient):
        payload = _make_author_create(order_position=0)
        resp = await client.post(f"{API_PREFIX}/authors", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_plan_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PP-001", json={})
        assert resp.status_code == 200  # No-op but valid

    @pytest.mark.anyio
    async def test_update_manuscript_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/manuscripts/MS-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_author_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/authors/AU-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_congress_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/congress-submissions/CS-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_journal_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/journal-submissions/JS-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_double_delete_plan(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/plans/PP-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/plans/PP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_manuscript(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/manuscripts/MS-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/manuscripts/MS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_author(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/authors/AU-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/authors/AU-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_congress(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/congress-submissions/CS-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/congress-submissions/CS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_journal(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/journal-submissions/JS-001")
        assert resp2.status_code == 404


# ===========================================================================
# ADDITIONAL API-LEVEL TESTS (coverage boost)
# ===========================================================================


class TestAdditionalAPI:
    """Additional API tests to boost test count."""

    @pytest.mark.anyio
    async def test_plans_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans")
        body = resp.json()
        assert "items" in body
        assert "total" in body
        item = body["items"][0]
        assert "id" in item
        assert "trial_id" in item
        assert "plan_name" in item
        assert "therapeutic_area" in item
        assert "created_at" in item

    @pytest.mark.anyio
    async def test_manuscripts_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts")
        body = resp.json()
        item = body["items"][0]
        assert "id" in item
        assert "plan_id" in item
        assert "trial_id" in item
        assert "title" in item
        assert "publication_type" in item
        assert "status" in item

    @pytest.mark.anyio
    async def test_authors_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors")
        body = resp.json()
        item = body["items"][0]
        assert "id" in item
        assert "manuscript_id" in item
        assert "name" in item
        assert "institution" in item
        assert "role" in item
        assert "order_position" in item

    @pytest.mark.anyio
    async def test_congress_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions")
        body = resp.json()
        item = body["items"][0]
        assert "id" in item
        assert "plan_id" in item
        assert "trial_id" in item
        assert "congress_name" in item
        assert "congress_tier" in item
        assert "abstract_title" in item

    @pytest.mark.anyio
    async def test_journal_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions")
        body = resp.json()
        item = body["items"][0]
        assert "id" in item
        assert "manuscript_id" in item
        assert "journal_name" in item
        assert "submission_date" in item
        assert "round_number" in item

    @pytest.mark.anyio
    async def test_metrics_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert "total_plans" in body
        assert "active_plans" in body
        assert "total_manuscripts" in body
        assert "manuscripts_by_status" in body
        assert "manuscripts_by_type" in body
        assert "published_count" in body
        assert "total_authors" in body
        assert "total_congress_submissions" in body
        assert "congress_by_tier" in body
        assert "accepted_congress_rate_pct" in body
        assert "total_journal_submissions" in body
        assert "avg_review_rounds" in body
        assert "avg_submission_to_acceptance_days" in body

    @pytest.mark.anyio
    async def test_manuscript_published_has_doi(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts/MS-001")
        body = resp.json()
        assert body["doi"] is not None
        assert body["pmid"] is not None

    @pytest.mark.anyio
    async def test_manuscript_planned_has_no_doi(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts/MS-014")
        body = resp.json()
        assert body["doi"] is None
        assert body["pmid"] is None

    @pytest.mark.anyio
    async def test_congress_published_has_abstract_number(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions/CS-001")
        body = resp.json()
        assert body["abstract_number"] is not None

    @pytest.mark.anyio
    async def test_congress_planned_has_no_abstract_number(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions/CS-009")
        body = resp.json()
        assert body["abstract_number"] is None

    @pytest.mark.anyio
    async def test_journal_no_decision_yet(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-submissions/JS-006")
        body = resp.json()
        assert body["decision"] is None

    @pytest.mark.anyio
    async def test_author_has_orcid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors/AU-001")
        body = resp.json()
        assert body["orcid"] is not None

    @pytest.mark.anyio
    async def test_author_without_orcid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authors/AU-008")
        body = resp.json()
        assert body["orcid"] is None

    @pytest.mark.anyio
    async def test_create_multiple_plans(self, client: AsyncClient):
        for i in range(5):
            payload = _make_plan_create(plan_name=f"Batch Plan {i}")
            resp = await client.post(f"{API_PREFIX}/plans", json=payload)
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.json()["total"] == 17  # 12 seed + 5 new

    @pytest.mark.anyio
    async def test_create_multiple_manuscripts(self, client: AsyncClient):
        for i in range(3):
            payload = _make_manuscript_create(title=f"Batch Manuscript {i}")
            resp = await client.post(f"{API_PREFIX}/manuscripts", json=payload)
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/manuscripts")
        assert resp.json()["total"] == 18

    @pytest.mark.anyio
    async def test_create_multiple_authors(self, client: AsyncClient):
        for i in range(3):
            payload = _make_author_create(name=f"Batch Author {i}", order_position=i + 20)
            resp = await client.post(f"{API_PREFIX}/authors", json=payload)
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/authors")
        assert resp.json()["total"] == 21

    @pytest.mark.anyio
    async def test_manuscript_icmje_compliant_default(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts/MS-001")
        assert resp.json()["icmje_compliant"] is True

    @pytest.mark.anyio
    async def test_plan_pp012_pediatric(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PP-012")
        assert resp.status_code == 200
        assert "Pediatric" in resp.json()["therapeutic_area"]

    @pytest.mark.anyio
    async def test_manuscript_ms012_review_article(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts/MS-012")
        assert resp.status_code == 200
        assert resp.json()["publication_type"] == "review_article"

    @pytest.mark.anyio
    async def test_manuscript_under_review_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"status": "under_review"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_manuscript_in_development_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"status": "in_development"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_manuscript_revision_requested_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/manuscripts", params={"status": "revision_requested"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_congress_submitted_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"status": "submitted"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_congress_planned_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congress-submissions", params={"status": "planned"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_plan_dupixent_asthma(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PP-004")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_id"] == DUPIXENT_TRIAL
        assert "Asthma" in body["plan_name"]

    @pytest.mark.anyio
    async def test_plan_libtayo_cscc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PP-007")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_id"] == LIBTAYO_TRIAL
        assert "CSCC" in body["plan_name"]


# We need these additional imports for some service direct tests
from app.schemas.publication_planning import (
    AuthorUpdate,
    CongressSubmissionUpdate,
    JournalSubmissionUpdate,
    ManuscriptUpdate,
    PublicationPlanUpdate,
)
