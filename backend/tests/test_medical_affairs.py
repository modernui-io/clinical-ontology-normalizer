"""Tests for Medical Affairs & Publication Planning (CLINICAL-12).

Covers:
- Seed data verification (publications, congress plans, publication plans)
- Publication CRUD (create, read, update, delete, list, filter by trial/status/type)
- Publication lifecycle (advance status, auto-date setting)
- Publication search
- ICMJE compliance checking (compliant, non-compliant, no authors, missing roles)
- Congress plan CRUD (create, read, update, delete, list, filter by tier)
- Congress ROI calculation
- Publication plan CRUD (create, read, update, delete, list, filter by trial)
- Impact factor weighted count
- Journal tier classification
- Medical affairs metrics computation
- Error handling (404s, edge cases)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.medical_affairs import (
    AuthorEntry,
    AuthorRole,
    CongressPlanCreate,
    CongressPlanUpdate,
    CongressTier,
    ICMJEComplianceResult,
    JournalImpactTier,
    PublicationCreate,
    PublicationMilestone,
    PublicationPlanCreate,
    PublicationPlanUpdate,
    PublicationStatus,
    PublicationType,
    PublicationUpdate,
)
from app.services.medical_affairs_service import (
    MedicalAffairsService,
    get_medical_affairs_service,
    reset_medical_affairs_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-affairs"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_affairs_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalAffairsService:
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


def _make_pub_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "publication_type": "primary_manuscript",
        "title": "Test Publication Title",
        "target_journal": "Test Journal",
        "impact_factor": 15.0,
        "authors": [
            {
                "name": "Dr. Test Author",
                "affiliation": "Test University",
                "role": "first_author",
                "orcid": "0000-0000-0000-0001",
                "contributions": ["Data analysis"],
                "conflicts_disclosed": True,
            }
        ],
    }
    defaults.update(overrides)
    return defaults


def _make_congress_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "congress_name": "Test Congress 2026",
        "tier": "tier2",
        "date": (now + timedelta(days=90)).isoformat(),
        "location": "Test City, USA",
        "budget": 200000.0,
        "booth_reserved": False,
    }
    defaults.update(overrides)
    return defaults


def _make_plan_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "planned_publications": [],
        "timeline": "Test timeline description",
        "milestones": [
            {
                "name": "First draft",
                "target_date": (now + timedelta(days=30)).isoformat(),
                "completed": False,
            }
        ],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_publications_count(self, svc: MedicalAffairsService):
        pubs = svc.list_publications()
        assert len(pubs) == 12

    def test_seed_publications_types(self, svc: MedicalAffairsService):
        pubs = svc.list_publications()
        types = {p.publication_type for p in pubs}
        assert PublicationType.PRIMARY_MANUSCRIPT in types
        assert PublicationType.SECONDARY_ANALYSIS in types
        assert PublicationType.POST_HOC in types
        assert PublicationType.POSTER in types
        assert PublicationType.ORAL_PRESENTATION in types
        assert PublicationType.ABSTRACT in types
        assert PublicationType.REVIEW_ARTICLE in types

    def test_seed_publications_statuses(self, svc: MedicalAffairsService):
        pubs = svc.list_publications()
        statuses = {p.status for p in pubs}
        assert PublicationStatus.PUBLISHED in statuses
        assert PublicationStatus.UNDER_REVIEW in statuses
        assert PublicationStatus.DRAFTING in statuses
        assert PublicationStatus.PLANNED in statuses

    def test_seed_publications_trials(self, svc: MedicalAffairsService):
        pubs = svc.list_publications()
        trials = {p.trial_id for p in pubs}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_congress_plans_count(self, svc: MedicalAffairsService):
        plans = svc.list_congress_plans()
        assert len(plans) == 5

    def test_seed_congress_tiers(self, svc: MedicalAffairsService):
        plans = svc.list_congress_plans()
        tiers = {c.tier for c in plans}
        assert CongressTier.TIER1 in tiers
        assert CongressTier.TIER2 in tiers

    def test_seed_publication_plans_count(self, svc: MedicalAffairsService):
        plans = svc.list_publication_plans()
        assert len(plans) == 3

    def test_seed_publication_plans_trials(self, svc: MedicalAffairsService):
        plans = svc.list_publication_plans()
        trials = {p.trial_id for p in plans}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_published_have_doi(self, svc: MedicalAffairsService):
        pubs = svc.list_publications(status=PublicationStatus.PUBLISHED)
        journal_pubs = [p for p in pubs if p.publication_type == PublicationType.PRIMARY_MANUSCRIPT]
        for pub in journal_pubs:
            assert pub.doi is not None

    def test_seed_published_have_dates(self, svc: MedicalAffairsService):
        pubs = svc.list_publications(status=PublicationStatus.PUBLISHED)
        journal_pubs = [p for p in pubs if p.publication_type == PublicationType.PRIMARY_MANUSCRIPT]
        for pub in journal_pubs:
            assert pub.publication_date is not None


# =====================================================================
# PUBLICATION CRUD
# =====================================================================


class TestPublicationCrud:
    """Test publication create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_publications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_publications_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_publications_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications", params={"status": "published"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_list_publications_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications", params={"publication_type": "primary_manuscript"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["publication_type"] == "primary_manuscript"

    @pytest.mark.anyio
    async def test_get_publication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PUB-001"
        assert "Aflibercept" in data["title"]

    @pytest.mark.anyio
    async def test_get_publication_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_publication(self, client: AsyncClient):
        payload = _make_pub_create()
        resp = await client.post(f"{API_PREFIX}/publications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Publication Title"
        assert data["status"] == "planned"
        assert data["id"].startswith("PUB-")

    @pytest.mark.anyio
    async def test_create_publication_poster(self, client: AsyncClient):
        payload = _make_pub_create(
            publication_type="poster",
            title="Test Poster",
            congress_name="ASCO 2026",
            congress_date=datetime.now(timezone.utc).isoformat(),
        )
        resp = await client.post(f"{API_PREFIX}/publications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["publication_type"] == "poster"
        assert data["congress_name"] == "ASCO 2026"

    @pytest.mark.anyio
    async def test_update_publication(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publications/PUB-003",
            json={"title": "Updated Post Hoc Analysis Title", "status": "internal_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Post Hoc Analysis Title"
        assert data["status"] == "internal_review"

    @pytest.mark.anyio
    async def test_update_publication_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publications/PUB-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_publication(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/publications/PUB-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/publications/PUB-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_publication_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/publications/PUB-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PUBLICATION LIFECYCLE
# =====================================================================


class TestPublicationLifecycle:
    """Test publication lifecycle advancement."""

    @pytest.mark.anyio
    async def test_advance_to_submitted(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/publications/PUB-012/advance-status",
            params={"status": "journal_submitted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "journal_submitted"
        assert data["submission_date"] is not None

    @pytest.mark.anyio
    async def test_advance_to_accepted(self, client: AsyncClient):
        # PUB-002 is under_review, advance to accepted
        resp = await client.post(
            f"{API_PREFIX}/publications/PUB-002/advance-status",
            params={"status": "accepted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["acceptance_date"] is not None

    @pytest.mark.anyio
    async def test_advance_to_published(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/publications/PUB-005/advance-status",
            params={"status": "published"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "published"
        assert data["publication_date"] is not None

    @pytest.mark.anyio
    async def test_advance_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/publications/PUB-NONEXISTENT/advance-status",
            params={"status": "accepted"},
        )
        assert resp.status_code == 404

    def test_advance_preserves_existing_dates(self, svc: MedicalAffairsService):
        """Advancing status should not overwrite existing dates."""
        pub = svc.get_publication("PUB-001")
        assert pub is not None
        original_submission = pub.submission_date
        # Advance to published again
        updated = svc.advance_publication_status("PUB-001", PublicationStatus.PUBLISHED)
        assert updated is not None
        assert updated.submission_date == original_submission

    def test_advance_drafting_to_internal_review(self, svc: MedicalAffairsService):
        updated = svc.advance_publication_status("PUB-003", PublicationStatus.INTERNAL_REVIEW)
        assert updated is not None
        assert updated.status == PublicationStatus.INTERNAL_REVIEW

    def test_advance_to_rejected(self, svc: MedicalAffairsService):
        updated = svc.advance_publication_status("PUB-002", PublicationStatus.REJECTED)
        assert updated is not None
        assert updated.status == PublicationStatus.REJECTED

    def test_advance_to_revision_requested(self, svc: MedicalAffairsService):
        updated = svc.advance_publication_status("PUB-006", PublicationStatus.REVISION_REQUESTED)
        assert updated is not None
        assert updated.status == PublicationStatus.REVISION_REQUESTED


# =====================================================================
# PUBLICATION SEARCH
# =====================================================================


class TestPublicationSearch:
    """Test publication search functionality."""

    @pytest.mark.anyio
    async def test_search_by_title(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/search", params={"q": "Aflibercept"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "aflibercept" in item["title"].lower()

    @pytest.mark.anyio
    async def test_search_case_insensitive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/search", params={"q": "dupilumab"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_search_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/search", params={"q": "xyznonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_search_partial_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/search", params={"q": "EMPOWER"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0


# =====================================================================
# ICMJE COMPLIANCE
# =====================================================================


class TestICMJECompliance:
    """Test ICMJE compliance checking."""

    @pytest.mark.anyio
    async def test_icmje_compliant_publication(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/publications/PUB-001/check-icmje")
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliant"] is True
        assert len(data["issues"]) == 0

    @pytest.mark.anyio
    async def test_icmje_non_compliant_publication(self, client: AsyncClient):
        # PUB-011 has an author without conflicts_disclosed
        resp = await client.post(f"{API_PREFIX}/publications/PUB-011/check-icmje")
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliant"] is False
        assert len(data["issues"]) > 0

    @pytest.mark.anyio
    async def test_icmje_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/publications/PUB-NONEXISTENT/check-icmje")
        assert resp.status_code == 404

    def test_icmje_no_authors(self, svc: MedicalAffairsService):
        """Publication with no authors should fail ICMJE check."""
        # Create a publication with no authors
        pub = svc.create_publication(PublicationCreate(
            trial_id=EYLEA_TRIAL,
            publication_type=PublicationType.PRIMARY_MANUSCRIPT,
            title="No Authors Pub",
            authors=[],
        ))
        result = svc.check_icmje_compliance(pub.id)
        assert result is not None
        assert result.compliant is False
        assert "No authors listed" in result.issues

    def test_icmje_missing_first_author(self, svc: MedicalAffairsService):
        """Publication without first author should fail ICMJE check."""
        pub = svc.create_publication(PublicationCreate(
            trial_id=EYLEA_TRIAL,
            publication_type=PublicationType.PRIMARY_MANUSCRIPT,
            title="Missing First Author",
            authors=[
                AuthorEntry(
                    name="Dr. Test",
                    affiliation="Test",
                    role=AuthorRole.CONTRIBUTING,
                    contributions=["Data analysis"],
                    conflicts_disclosed=True,
                ),
            ],
        ))
        result = svc.check_icmje_compliance(pub.id)
        assert result is not None
        assert result.compliant is False
        assert any("first author" in issue.lower() for issue in result.issues)

    def test_icmje_missing_contributions(self, svc: MedicalAffairsService):
        """Author without contributions should fail ICMJE check."""
        pub = svc.create_publication(PublicationCreate(
            trial_id=EYLEA_TRIAL,
            publication_type=PublicationType.PRIMARY_MANUSCRIPT,
            title="Missing Contributions",
            authors=[
                AuthorEntry(
                    name="Dr. First",
                    affiliation="Test",
                    role=AuthorRole.FIRST_AUTHOR,
                    contributions=[],
                    conflicts_disclosed=True,
                ),
                AuthorEntry(
                    name="Dr. Senior",
                    affiliation="Test",
                    role=AuthorRole.SENIOR_AUTHOR,
                    contributions=["Final approval"],
                    conflicts_disclosed=True,
                ),
            ],
        ))
        result = svc.check_icmje_compliance(pub.id)
        assert result is not None
        assert result.compliant is False
        assert any("contributions" in issue.lower() for issue in result.issues)

    def test_icmje_missing_senior_or_corresponding(self, svc: MedicalAffairsService):
        """Publication without senior or corresponding author should fail."""
        pub = svc.create_publication(PublicationCreate(
            trial_id=EYLEA_TRIAL,
            publication_type=PublicationType.PRIMARY_MANUSCRIPT,
            title="Missing Senior",
            authors=[
                AuthorEntry(
                    name="Dr. First",
                    affiliation="Test",
                    role=AuthorRole.FIRST_AUTHOR,
                    contributions=["Data analysis"],
                    conflicts_disclosed=True,
                ),
            ],
        ))
        result = svc.check_icmje_compliance(pub.id)
        assert result is not None
        assert result.compliant is False
        assert any("senior" in issue.lower() or "corresponding" in issue.lower() for issue in result.issues)

    def test_icmje_updates_publication_status(self, svc: MedicalAffairsService):
        """Running ICMJE check should update icmje_compliant field."""
        # PUB-003 starts non-compliant
        pub = svc.get_publication("PUB-003")
        assert pub is not None
        assert pub.icmje_compliant is False

        result = svc.check_icmje_compliance("PUB-003")
        assert result is not None
        # After check, publication should have updated icmje_compliant
        pub_after = svc.get_publication("PUB-003")
        assert pub_after is not None
        assert pub_after.icmje_compliant == result.compliant

    def test_icmje_compliant_sets_true(self, svc: MedicalAffairsService):
        """Passing ICMJE check should set icmje_compliant to True."""
        result = svc.check_icmje_compliance("PUB-001")
        assert result is not None
        assert result.compliant is True
        pub = svc.get_publication("PUB-001")
        assert pub is not None
        assert pub.icmje_compliant is True


# =====================================================================
# CONGRESS PLANS
# =====================================================================


class TestCongressPlans:
    """Test congress plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_congresses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_congresses_filter_tier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses", params={"tier": "tier1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["tier"] == "tier1"

    @pytest.mark.anyio
    async def test_get_congress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CONG-001"
        assert "ASCO" in data["congress_name"]

    @pytest.mark.anyio
    async def test_get_congress_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_congress(self, client: AsyncClient):
        payload = _make_congress_create()
        resp = await client.post(f"{API_PREFIX}/congresses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["congress_name"] == "Test Congress 2026"
        assert data["id"].startswith("CONG-")
        assert data["abstracts_submitted"] == 0

    @pytest.mark.anyio
    async def test_update_congress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congresses/CONG-003",
            json={"abstracts_accepted": 2, "posters": 1, "orals": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["abstracts_accepted"] == 2
        assert data["posters"] == 1
        assert data["orals"] == 1

    @pytest.mark.anyio
    async def test_update_congress_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congresses/CONG-NONEXISTENT",
            json={"location": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_congress(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/congresses/CONG-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/congresses/CONG-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_congress_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/congresses/CONG-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CONGRESS ROI
# =====================================================================


class TestCongressROI:
    """Test congress ROI calculation."""

    @pytest.mark.anyio
    async def test_congress_roi(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-001/roi")
        assert resp.status_code == 200
        data = resp.json()
        assert data["congress_id"] == "CONG-001"
        assert data["acceptance_rate"] > 0
        assert data["total_presentations"] > 0
        assert data["cost_per_presentation"] > 0

    @pytest.mark.anyio
    async def test_congress_roi_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-NONEXISTENT/roi")
        assert resp.status_code == 404

    def test_congress_roi_acceptance_rate(self, svc: MedicalAffairsService):
        roi = svc.get_congress_roi("CONG-001")
        assert roi is not None
        # ASCO: 5 submitted, 4 accepted = 80%
        assert roi["acceptance_rate"] == 80.0

    def test_congress_roi_zero_submissions(self, svc: MedicalAffairsService):
        """Congress with 0 submissions should have 0% acceptance rate."""
        cong = svc.create_congress_plan(CongressPlanCreate(
            congress_name="Empty Congress",
            tier=CongressTier.TIER3,
            date=datetime.now(timezone.utc),
            location="Nowhere",
            budget=10000.0,
        ))
        roi = svc.get_congress_roi(cong.id)
        assert roi is not None
        assert roi["acceptance_rate"] == 0.0

    def test_congress_roi_cost_per_presentation(self, svc: MedicalAffairsService):
        roi = svc.get_congress_roi("CONG-004")
        assert roi is not None
        # AAO: budget=400000, posters=3, orals=2 -> 5 presentations
        assert roi["total_presentations"] == 5
        assert roi["cost_per_presentation"] == 80000.0

    def test_congress_roi_no_presentations(self, svc: MedicalAffairsService):
        roi = svc.get_congress_roi("CONG-003")
        assert roi is not None
        # AACR has 0 accepted so far
        assert roi["total_presentations"] == 0
        assert roi["cost_per_presentation"] == 0.0


# =====================================================================
# PUBLICATION PLANS
# =====================================================================


class TestPublicationPlans:
    """Test publication plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_publication_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_publication_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-plans", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_publication_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-plans/PPLAN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PPLAN-001"
        assert len(data["planned_publications"]) > 0
        assert len(data["milestones"]) > 0

    @pytest.mark.anyio
    async def test_get_publication_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-plans/PPLAN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_publication_plan(self, client: AsyncClient):
        payload = _make_plan_create()
        resp = await client.post(f"{API_PREFIX}/publication-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["id"].startswith("PPLAN-")
        assert len(data["milestones"]) == 1

    @pytest.mark.anyio
    async def test_update_publication_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publication-plans/PPLAN-001",
            json={"timeline": "Updated timeline description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["timeline"] == "Updated timeline description"

    @pytest.mark.anyio
    async def test_update_publication_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publication-plans/PPLAN-NONEXISTENT",
            json={"timeline": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_publication_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/publication-plans/PPLAN-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/publication-plans/PPLAN-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_publication_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/publication-plans/PPLAN-NONEXISTENT")
        assert resp.status_code == 404

    def test_plan_milestones_have_dates(self, svc: MedicalAffairsService):
        plan = svc.get_publication_plan("PPLAN-001")
        assert plan is not None
        for milestone in plan.milestones:
            assert milestone.target_date is not None
            assert milestone.name

    def test_plan_has_completed_milestones(self, svc: MedicalAffairsService):
        plan = svc.get_publication_plan("PPLAN-001")
        assert plan is not None
        completed = [m for m in plan.milestones if m.completed]
        pending = [m for m in plan.milestones if not m.completed]
        assert len(completed) > 0
        assert len(pending) > 0


# =====================================================================
# IMPACT FACTOR ANALYSIS
# =====================================================================


class TestImpactFactorAnalysis:
    """Test impact factor weighted count and journal tier classification."""

    @pytest.mark.anyio
    async def test_impact_factor_weighted_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-factor-weighted-count")
        assert resp.status_code == 200
        data = resp.json()
        assert "impact_factor_weighted_count" in data
        assert data["impact_factor_weighted_count"] > 0

    def test_impact_factor_includes_published(self, svc: MedicalAffairsService):
        count = svc.get_impact_factor_weighted_count()
        # PUB-001 (176.1, published) + PUB-004 (168.9, published) + PUB-005 (12.8, accepted)
        # = 357.8 (at minimum for those three)
        assert count >= 357.8

    def test_impact_factor_excludes_planned(self, svc: MedicalAffairsService):
        """Planned publications should not contribute to weighted count."""
        # PUB-012 is planned with IF 18.6 -- should not be counted
        count_before = svc.get_impact_factor_weighted_count()
        svc.advance_publication_status("PUB-012", PublicationStatus.PUBLISHED)
        count_after = svc.get_impact_factor_weighted_count()
        assert count_after > count_before

    @pytest.mark.anyio
    async def test_journal_tier_high_impact(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-tier/50.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "high_impact"

    @pytest.mark.anyio
    async def test_journal_tier_mid_impact(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-tier/15.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "mid_impact"

    @pytest.mark.anyio
    async def test_journal_tier_specialized(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/journal-tier/5.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "specialized"

    def test_journal_tier_boundary_high(self, svc: MedicalAffairsService):
        assert svc.classify_journal_tier(30.0) == JournalImpactTier.HIGH_IMPACT

    def test_journal_tier_boundary_mid(self, svc: MedicalAffairsService):
        assert svc.classify_journal_tier(10.0) == JournalImpactTier.MID_IMPACT

    def test_journal_tier_boundary_specialized(self, svc: MedicalAffairsService):
        assert svc.classify_journal_tier(9.9) == JournalImpactTier.SPECIALIZED


# =====================================================================
# METRICS
# =====================================================================


class TestMedicalAffairsMetrics:
    """Test medical affairs metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_publications"] == 12
        assert data["icmje_compliance_rate"] >= 0
        assert data["impact_factor_weighted_count"] > 0

    def test_metrics_publications_by_status(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.publications_by_status.values())
        assert total_by_status == metrics.total_publications

    def test_metrics_publications_by_type(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.publications_by_type.values())
        assert total_by_type == metrics.total_publications

    def test_metrics_avg_acceptance_days(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        # PUB-001 and PUB-004 have both submission and acceptance dates
        assert metrics.avg_submission_to_acceptance_days is not None
        assert metrics.avg_submission_to_acceptance_days > 0

    def test_metrics_congress_roi(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        # Should have ROI for congresses with submissions
        assert len(metrics.congress_roi) > 0
        for name, rate in metrics.congress_roi.items():
            assert 0 <= rate <= 100

    def test_metrics_icmje_compliance_rate(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.icmje_compliance_rate <= 100

    def test_metrics_impact_factor_weighted(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        assert metrics.impact_factor_weighted_count > 0

    def test_metrics_has_status_keys(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        assert "published" in metrics.publications_by_status

    def test_metrics_has_type_keys(self, svc: MedicalAffairsService):
        metrics = svc.get_metrics()
        assert "primary_manuscript" in metrics.publications_by_type


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_medical_affairs_service()
        svc2 = get_medical_affairs_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_medical_affairs_service()
        svc2 = reset_medical_affairs_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_affairs_service()
        svc.delete_publication("PUB-001")
        assert svc.get_publication("PUB-001") is None
        svc2 = reset_medical_affairs_service()
        assert svc2.get_publication("PUB-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_publications_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_congresses_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_plans_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-plans")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_publication_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "publication_type": "abstract",
            "title": "Minimal Abstract",
        }
        resp = await client.post(f"{API_PREFIX}/publications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "planned"
        assert data["icmje_compliant"] is False

    @pytest.mark.anyio
    async def test_create_congress_with_booth(self, client: AsyncClient):
        payload = _make_congress_create(booth_reserved=True, tier="tier1")
        resp = await client.post(f"{API_PREFIX}/congresses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["booth_reserved"] is True
        assert data["tier"] == "tier1"

    @pytest.mark.anyio
    async def test_update_publication_doi(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publications/PUB-005",
            json={"doi": "10.1016/j.jaad.2025.12345"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["doi"] == "10.1016/j.jaad.2025.12345"

    @pytest.mark.anyio
    async def test_update_congress_budget(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/congresses/CONG-001",
            json={"budget": 500000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["budget"] == 500000.0

    @pytest.mark.anyio
    async def test_publication_authors_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-001")
        data = resp.json()
        assert len(data["authors"]) > 0
        author = data["authors"][0]
        assert "name" in author
        assert "affiliation" in author
        assert "role" in author
        assert "contributions" in author
        assert "conflicts_disclosed" in author

    def test_search_empty_query(self, svc: MedicalAffairsService):
        results = svc.search_publications("")
        assert len(results) == 12  # Empty string matches all

    def test_list_publications_filter_combined(self, svc: MedicalAffairsService):
        pubs = svc.list_publications(
            trial_id=EYLEA_TRIAL,
            status=PublicationStatus.PUBLISHED,
        )
        for pub in pubs:
            assert pub.trial_id == EYLEA_TRIAL
            assert pub.status == PublicationStatus.PUBLISHED

    def test_list_publications_filter_no_matches(self, svc: MedicalAffairsService):
        pubs = svc.list_publications(
            trial_id="nonexistent-trial",
        )
        assert len(pubs) == 0


# =====================================================================
# ENUMERATIONS
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_publication_types_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications")
        data = resp.json()
        types = {item["publication_type"] for item in data["items"]}
        assert "primary_manuscript" in types
        assert "secondary_analysis" in types
        assert "post_hoc" in types
        assert "poster" in types

    @pytest.mark.anyio
    async def test_publication_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "published" in statuses
        assert "drafting" in statuses
        assert "planned" in statuses

    @pytest.mark.anyio
    async def test_congress_tiers_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses")
        data = resp.json()
        tiers = {item["tier"] for item in data["items"]}
        assert "tier1" in tiers
        assert "tier2" in tiers

    @pytest.mark.anyio
    async def test_author_roles_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-001")
        data = resp.json()
        roles = {a["role"] for a in data["authors"]}
        assert "first_author" in roles
        assert "senior_author" in roles
        assert "corresponding" in roles
        assert "contributing" in roles


# =====================================================================
# PUBLICATION DETAILS
# =====================================================================


class TestPublicationDetails:
    """Test detailed publication components."""

    @pytest.mark.anyio
    async def test_published_manuscript_has_journal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-001")
        data = resp.json()
        assert data["target_journal"] is not None
        assert data["impact_factor"] is not None

    @pytest.mark.anyio
    async def test_poster_has_congress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-007")
        data = resp.json()
        assert data["congress_name"] is not None

    @pytest.mark.anyio
    async def test_nejm_impact_factor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-001")
        data = resp.json()
        assert data["target_journal"] == "New England Journal of Medicine"
        assert data["impact_factor"] > 100

    @pytest.mark.anyio
    async def test_lancet_impact_factor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-004")
        data = resp.json()
        assert data["target_journal"] == "The Lancet"
        assert data["impact_factor"] > 100

    @pytest.mark.anyio
    async def test_jco_impact_factor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-006")
        data = resp.json()
        assert data["target_journal"] == "Journal of Clinical Oncology"
        assert data["impact_factor"] > 30

    @pytest.mark.anyio
    async def test_jaad_impact_factor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications/PUB-005")
        data = resp.json()
        assert "Dermatology" in data["target_journal"]
        assert data["impact_factor"] > 10

    @pytest.mark.anyio
    async def test_publication_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publications")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)


# =====================================================================
# CONGRESS PLAN DETAILS
# =====================================================================


class TestCongressPlanDetails:
    """Test detailed congress plan components."""

    @pytest.mark.anyio
    async def test_asco_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-001")
        data = resp.json()
        assert "ASCO" in data["congress_name"]
        assert data["tier"] == "tier1"
        assert data["booth_reserved"] is True
        assert data["budget"] > 0

    @pytest.mark.anyio
    async def test_eadv_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-005")
        data = resp.json()
        assert "EADV" in data["congress_name"]
        assert data["tier"] == "tier2"

    @pytest.mark.anyio
    async def test_congress_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses")
        data = resp.json()
        dates = [item["date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_congress_abstracts_tracking(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/congresses/CONG-004")
        data = resp.json()
        # AAO: 6 submitted, 5 accepted
        assert data["abstracts_submitted"] == 6
        assert data["abstracts_accepted"] == 5
        assert data["abstracts_accepted"] <= data["abstracts_submitted"]
