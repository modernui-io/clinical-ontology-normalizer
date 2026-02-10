"""Tests for Site Initiation & Activation (CLINICAL-17).

Covers:
- Seed data verification (sites, qualification visits, regulatory documents, milestones, readiness)
- Site CRUD (create, read, update, delete, list, filter by trial/status/country)
- Site lifecycle transitions (identified -> selected -> qualification_visit ->
  regulatory_submitted -> activated -> enrolling -> closed)
- Invalid lifecycle transitions (409 Conflict)
- Qualification visit management (add, list)
- Regulatory document management (add, list, update, filter by type/status)
- Readiness assessment (get, update, auto-calculation of overall score)
- Milestone tracking (get, update)
- Activation metrics (site counts, avg days, bottleneck analysis)
- Error handling (404s, 400s, 409s)
- Edge cases (empty filters, boundary conditions, sorting)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.site_initiation import (
    DocumentStatus,
    DocumentType,
    MilestoneStatus,
    MilestoneType,
    QualificationRecommendation,
    ReadinessCategory,
    SiteStatus,
)
from app.services.site_initiation_service import (
    SiteInitiationService,
    get_site_initiation_service,
    reset_site_initiation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-initiation"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_initiation_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SiteInitiationService:
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


def _make_site_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_number": "9001",
        "site_name": "Test Clinical Research Center - Site 9001",
        "principal_investigator": "Dr. Jane Test",
        "institution": "Test University Medical Center",
        "country": "US",
        "target_enrollment": 25,
    }
    defaults.update(overrides)
    return defaults


def _make_qualification_visit_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "visit_date": now.isoformat(),
        "attendees": ["Dr. Jane Test", "CRA Smith"],
        "findings": "Adequate facilities and staffing for trial participation.",
        "recommendation": "approved",
        "action_items": ["Complete training"],
    }
    defaults.update(overrides)
    return defaults


def _make_regulatory_document_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "doc_type": "irb_approval",
        "submitted_date": now.isoformat(),
        "notes": "Submitted for review",
        "version": "1.0",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_sites_count(self, svc: SiteInitiationService):
        sites = svc.list_sites()
        assert len(sites) == 10

    def test_seed_sites_across_trials(self, svc: SiteInitiationService):
        eylea = svc.list_sites(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_sites(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_sites(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 3
        assert len(libtayo) == 3

    def test_seed_site_statuses(self, svc: SiteInitiationService):
        sites = svc.list_sites()
        statuses = {s.status for s in sites}
        assert SiteStatus.IDENTIFIED in statuses
        assert SiteStatus.ENROLLING in statuses
        assert SiteStatus.ACTIVATED in statuses
        assert SiteStatus.SELECTED in statuses
        assert SiteStatus.QUALIFICATION_VISIT in statuses
        assert SiteStatus.REGULATORY_SUBMITTED in statuses

    def test_seed_enrolling_sites_have_enrollment(self, svc: SiteInitiationService):
        sites = svc.list_sites(status=SiteStatus.ENROLLING)
        for site in sites:
            assert site.current_enrollment > 0
            assert site.target_enrollment > 0

    def test_seed_activated_sites_have_activation_date(self, svc: SiteInitiationService):
        for site in svc.list_sites():
            if site.status in (SiteStatus.ACTIVATED, SiteStatus.ENROLLING):
                assert site.activation_date is not None

    def test_seed_identified_site_has_no_activation_date(self, svc: SiteInitiationService):
        site = svc.get_site("SINIT-010")
        assert site is not None
        assert site.status == SiteStatus.IDENTIFIED
        assert site.activation_date is None

    def test_seed_qualification_visits_count(self, svc: SiteInitiationService):
        all_visits = []
        for site in svc.list_sites():
            all_visits.extend(svc.list_qualification_visits(site.id))
        assert len(all_visits) == 7

    def test_seed_qualification_visit_recommendations(self, svc: SiteInitiationService):
        visits = svc.list_qualification_visits("SINIT-001")
        assert len(visits) > 0
        assert visits[0].recommendation == QualificationRecommendation.APPROVED

    def test_seed_qualification_visit_with_conditions(self, svc: SiteInitiationService):
        visits = svc.list_qualification_visits("SINIT-002")
        assert len(visits) > 0
        assert visits[0].recommendation == QualificationRecommendation.APPROVED_WITH_CONDITIONS

    def test_seed_regulatory_documents_count(self, svc: SiteInitiationService):
        all_docs = []
        for site in svc.list_sites():
            all_docs.extend(svc.list_regulatory_documents(site.id))
        assert len(all_docs) == 24

    def test_seed_regulatory_document_statuses(self, svc: SiteInitiationService):
        docs = svc.list_regulatory_documents("SINIT-001")
        statuses = {d.status for d in docs}
        assert DocumentStatus.APPROVED in statuses

    def test_seed_milestones_count(self, svc: SiteInitiationService):
        all_ms = []
        for site in svc.list_sites():
            all_ms.extend(svc.get_milestones(site.id))
        assert len(all_ms) == 32

    def test_seed_milestone_statuses(self, svc: SiteInitiationService):
        all_ms = []
        for site in svc.list_sites():
            all_ms.extend(svc.get_milestones(site.id))
        statuses = {m.status for m in all_ms}
        assert MilestoneStatus.COMPLETED in statuses
        assert MilestoneStatus.PENDING in statuses
        assert MilestoneStatus.OVERDUE in statuses
        assert MilestoneStatus.IN_PROGRESS in statuses

    def test_seed_readiness_assessments(self, svc: SiteInitiationService):
        assessed_sites = ["SINIT-001", "SINIT-002", "SINIT-003", "SINIT-004",
                          "SINIT-005", "SINIT-008", "SINIT-009"]
        for site_id in assessed_sites:
            assessment = svc.get_readiness_assessment(site_id)
            assert assessment is not None, f"No readiness assessment for {site_id}"

    def test_seed_readiness_has_blockers(self, svc: SiteInitiationService):
        assessment = svc.get_readiness_assessment("SINIT-003")
        assert assessment is not None
        assert len(assessment.blockers) > 0

    def test_seed_fully_ready_site_no_blockers(self, svc: SiteInitiationService):
        assessment = svc.get_readiness_assessment("SINIT-001")
        assert assessment is not None
        assert len(assessment.blockers) == 0
        assert assessment.overall_score >= 95.0

    def test_seed_qualification_visits_embedded(self, svc: SiteInitiationService):
        site = svc.get_site("SINIT-001")
        assert site is not None
        assert len(site.qualification_visits) > 0

    def test_seed_regulatory_documents_embedded(self, svc: SiteInitiationService):
        site = svc.get_site("SINIT-001")
        assert site is not None
        assert len(site.regulatory_documents) > 0

    def test_seed_milestones_embedded(self, svc: SiteInitiationService):
        site = svc.get_site("SINIT-001")
        assert site is not None
        assert len(site.milestones) > 0


# =====================================================================
# SITE CRUD
# =====================================================================


class TestSiteCrud:
    """Test site create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_sites_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sites_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"status": "enrolling"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_list_sites_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"country": "US"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10  # All are US

    @pytest.mark.anyio
    async def test_list_sites_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_get_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SINIT-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "enrolling"
        assert data["site_number"] == "1001"

    @pytest.mark.anyio
    async def test_get_site_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "Test Clinical Research Center - Site 9001"
        assert data["status"] == "identified"
        assert data["id"].startswith("SINIT-")

    @pytest.mark.anyio
    async def test_create_site_auto_creates_milestone(self, client: AsyncClient, svc: SiteInitiationService):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        site_id = resp.json()["id"]
        milestones = svc.get_milestones(site_id)
        assert len(milestones) == 1
        assert milestones[0].milestone_type == MilestoneType.SITE_IDENTIFIED
        assert milestones[0].status == MilestoneStatus.COMPLETED

    @pytest.mark.anyio
    async def test_create_site_starts_identified(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "identified"
        assert data["current_enrollment"] == 0
        assert data["activation_date"] is None

    @pytest.mark.anyio
    async def test_update_site(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SINIT-010",
            json={"site_name": "Updated Site Name", "target_enrollment": 50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_name"] == "Updated Site Name"
        assert data["target_enrollment"] == 50

    @pytest.mark.anyio
    async def test_update_site_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SINIT-NONEXISTENT",
            json={"site_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/SINIT-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/SINIT-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/SINIT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_cleans_up_related_data(self, svc: SiteInitiationService, client: AsyncClient):
        # Verify related data exists before deletion
        assert svc.get_readiness_assessment("SINIT-001") is not None
        assert len(svc.list_qualification_visits("SINIT-001")) > 0
        assert len(svc.list_regulatory_documents("SINIT-001")) > 0
        assert len(svc.get_milestones("SINIT-001")) > 0

        resp = await client.delete(f"{API_PREFIX}/SINIT-001")
        assert resp.status_code == 204

        # Verify related data is cleaned up
        assert svc.get_readiness_assessment("SINIT-001") is None
        assert len(svc.list_qualification_visits("SINIT-001")) == 0
        assert len(svc.list_regulatory_documents("SINIT-001")) == 0
        assert len(svc.get_milestones("SINIT-001")) == 0

    @pytest.mark.anyio
    async def test_sites_sorted_by_created_at_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# SITE LIFECYCLE
# =====================================================================


class TestSiteLifecycle:
    """Test site lifecycle transitions."""

    @pytest.mark.anyio
    async def test_select_identified_site(self, client: AsyncClient):
        # SINIT-010 is identified
        resp = await client.post(f"{API_PREFIX}/SINIT-010/select")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "selected"

    @pytest.mark.anyio
    async def test_complete_qualification_selected_site(self, client: AsyncClient):
        # SINIT-007 is selected
        resp = await client.post(f"{API_PREFIX}/SINIT-007/complete-qualification")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "qualification_visit"

    @pytest.mark.anyio
    async def test_submit_regulatory_from_qualification(self, client: AsyncClient):
        # SINIT-004 is qualification_visit
        resp = await client.post(f"{API_PREFIX}/SINIT-004/submit-regulatory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "regulatory_submitted"

    @pytest.mark.anyio
    async def test_activate_from_regulatory(self, client: AsyncClient):
        # SINIT-003 is regulatory_submitted
        resp = await client.post(f"{API_PREFIX}/SINIT-003/activate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "activated"
        assert data["activation_date"] is not None

    @pytest.mark.anyio
    async def test_begin_enrollment_from_activated(self, client: AsyncClient):
        # SINIT-002 is activated
        resp = await client.post(f"{API_PREFIX}/SINIT-002/begin-enrollment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_close_enrolling_site(self, client: AsyncClient):
        # SINIT-001 is enrolling
        resp = await client.post(f"{API_PREFIX}/SINIT-001/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_close_activated_site(self, client: AsyncClient):
        # SINIT-002 is activated
        resp = await client.post(f"{API_PREFIX}/SINIT-002/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_invalid_transition_select_enrolling(self, client: AsyncClient):
        # SINIT-001 is enrolling, cannot go to selected
        resp = await client.post(f"{API_PREFIX}/SINIT-001/select")
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_invalid_transition_activate_identified(self, client: AsyncClient):
        # SINIT-010 is identified, cannot activate
        resp = await client.post(f"{API_PREFIX}/SINIT-010/activate")
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_invalid_transition_close_identified(self, client: AsyncClient):
        # SINIT-010 is identified, cannot close
        resp = await client.post(f"{API_PREFIX}/SINIT-010/close")
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_invalid_transition_begin_enrollment_regulatory(self, client: AsyncClient):
        # SINIT-003 is regulatory_submitted, cannot begin enrollment
        resp = await client.post(f"{API_PREFIX}/SINIT-003/begin-enrollment")
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_lifecycle_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/SINIT-NONEXISTENT/select")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_activate_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/SINIT-NONEXISTENT/activate")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/SINIT-NONEXISTENT/close")
        assert resp.status_code == 404

    def test_full_lifecycle_via_service(self, svc: SiteInitiationService):
        """Test complete lifecycle: identified -> selected -> qualification_visit -> regulatory -> activated -> enrolling -> closed."""
        from app.schemas.site_initiation import SiteInitiationCreate

        site = svc.create_site(SiteInitiationCreate(
            trial_id=EYLEA_TRIAL,
            site_number="9999",
            site_name="Full Lifecycle Test Site",
            principal_investigator="Dr. Lifecycle Test",
            institution="Test University",
        ))
        assert site.status == SiteStatus.IDENTIFIED

        site = svc.submit_for_qualification(site.id)
        assert site is not None
        assert site.status == SiteStatus.SELECTED

        site = svc.complete_qualification(site.id)
        assert site is not None
        assert site.status == SiteStatus.QUALIFICATION_VISIT

        site = svc.submit_regulatory(site.id)
        assert site is not None
        assert site.status == SiteStatus.REGULATORY_SUBMITTED

        site = svc.activate_site(site.id)
        assert site is not None
        assert site.status == SiteStatus.ACTIVATED
        assert site.activation_date is not None

        site = svc.begin_enrollment(site.id)
        assert site is not None
        assert site.status == SiteStatus.ENROLLING

        site = svc.close_site(site.id)
        assert site is not None
        assert site.status == SiteStatus.CLOSED

    def test_closed_site_cannot_transition(self, svc: SiteInitiationService):
        """Verify closed sites cannot transition to any other state."""
        from app.schemas.site_initiation import SiteInitiationCreate

        site = svc.create_site(SiteInitiationCreate(
            trial_id=EYLEA_TRIAL,
            site_number="8888",
            site_name="Close Test Site",
            principal_investigator="Dr. Close Test",
            institution="Test University",
        ))
        # Advance to activated then close
        svc.submit_for_qualification(site.id)
        svc.complete_qualification(site.id)
        svc.submit_regulatory(site.id)
        svc.activate_site(site.id)
        svc.close_site(site.id)

        with pytest.raises(ValueError):
            svc.submit_for_qualification(site.id)

    def test_invalid_transition_raises_value_error(self, svc: SiteInitiationService):
        # SINIT-001 is enrolling, cannot select
        with pytest.raises(ValueError, match="cannot transition"):
            svc.submit_for_qualification("SINIT-001")


# =====================================================================
# QUALIFICATION VISITS
# =====================================================================


class TestQualificationVisits:
    """Test qualification visit operations."""

    @pytest.mark.anyio
    async def test_list_qualification_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/qualification-visits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SINIT-001"

    @pytest.mark.anyio
    async def test_list_qualification_visits_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-010/qualification-visits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_add_qualification_visit(self, client: AsyncClient):
        payload = _make_qualification_visit_create()
        resp = await client.post(f"{API_PREFIX}/SINIT-007/qualification-visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SINIT-007"
        assert data["recommendation"] == "approved"
        assert data["id"].startswith("QV-")

    @pytest.mark.anyio
    async def test_add_qualification_visit_invalid_site(self, client: AsyncClient):
        payload = _make_qualification_visit_create()
        resp = await client.post(f"{API_PREFIX}/SINIT-NONEXISTENT/qualification-visits", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_add_qualification_visit_with_conditions(self, client: AsyncClient):
        payload = _make_qualification_visit_create(
            recommendation="approved_with_conditions",
            action_items=["Upgrade pharmacy storage", "Hire additional coordinator"],
        )
        resp = await client.post(f"{API_PREFIX}/SINIT-007/qualification-visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["recommendation"] == "approved_with_conditions"
        assert len(data["action_items"]) == 2

    def test_qualification_visit_embedded_after_add(self, svc: SiteInitiationService):
        now = datetime.now(timezone.utc)
        from app.schemas.site_initiation import QualificationVisitCreate

        initial_count = len(svc.get_site("SINIT-007").qualification_visits) if svc.get_site("SINIT-007") else 0
        svc.add_qualification_visit("SINIT-007", QualificationVisitCreate(
            visit_date=now,
            attendees=["Dr. Test"],
            findings="Good findings",
            recommendation=QualificationRecommendation.APPROVED,
        ))
        site = svc.get_site("SINIT-007")
        assert site is not None
        assert len(site.qualification_visits) == initial_count + 1

    def test_qualification_visit_sorted_by_date_desc(self, svc: SiteInitiationService):
        visits = svc.list_qualification_visits("SINIT-001")
        if len(visits) > 1:
            dates = [v.visit_date for v in visits]
            assert dates == sorted(dates, reverse=True)

    def test_all_recommendations_in_seed_data(self, svc: SiteInitiationService):
        all_visits = []
        for site in svc.list_sites():
            all_visits.extend(svc.list_qualification_visits(site.id))
        recommendations = {v.recommendation for v in all_visits}
        assert QualificationRecommendation.APPROVED in recommendations
        assert QualificationRecommendation.APPROVED_WITH_CONDITIONS in recommendations


# =====================================================================
# REGULATORY DOCUMENTS
# =====================================================================


class TestRegulatoryDocuments:
    """Test regulatory document operations."""

    @pytest.mark.anyio
    async def test_list_regulatory_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/regulatory-documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SINIT-001"

    @pytest.mark.anyio
    async def test_list_regulatory_documents_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/SINIT-001/regulatory-documents",
            params={"doc_type": "irb_approval"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["doc_type"] == "irb_approval"

    @pytest.mark.anyio
    async def test_list_regulatory_documents_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/SINIT-001/regulatory-documents",
            params={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_regulatory_documents_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-010/regulatory-documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_add_regulatory_document(self, client: AsyncClient):
        payload = _make_regulatory_document_create()
        resp = await client.post(f"{API_PREFIX}/SINIT-007/regulatory-documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SINIT-007"
        assert data["doc_type"] == "irb_approval"
        assert data["status"] == "submitted"
        assert data["id"].startswith("DOC-")

    @pytest.mark.anyio
    async def test_add_regulatory_document_no_submit_date(self, client: AsyncClient):
        payload = {
            "doc_type": "financial_disclosure",
            "notes": "Awaiting signature",
        }
        resp = await client.post(f"{API_PREFIX}/SINIT-007/regulatory-documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "not_submitted"
        assert data["submitted_date"] is None

    @pytest.mark.anyio
    async def test_add_regulatory_document_invalid_site(self, client: AsyncClient):
        payload = _make_regulatory_document_create()
        resp = await client.post(f"{API_PREFIX}/SINIT-NONEXISTENT/regulatory-documents", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_get_regulatory_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DOC-001"
        assert data["site_id"] == "SINIT-001"

    @pytest.mark.anyio
    async def test_get_regulatory_document_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_regulatory_document(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-006",
            json={
                "status": "approved",
                "approved_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_update_regulatory_document_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    def test_regulatory_document_embedded_after_add(self, svc: SiteInitiationService):
        from app.schemas.site_initiation import RegulatoryDocumentCreate

        now = datetime.now(timezone.utc)
        initial = len(svc.get_site("SINIT-007").regulatory_documents) if svc.get_site("SINIT-007") else 0
        svc.add_regulatory_document("SINIT-007", RegulatoryDocumentCreate(
            doc_type=DocumentType.INFORMED_CONSENT,
            submitted_date=now,
        ))
        site = svc.get_site("SINIT-007")
        assert site is not None
        assert len(site.regulatory_documents) == initial + 1

    def test_document_types_in_seed(self, svc: SiteInitiationService):
        all_docs = []
        for site in svc.list_sites():
            all_docs.extend(svc.list_regulatory_documents(site.id))
        types = {d.doc_type for d in all_docs}
        assert DocumentType.IRB_APPROVAL in types
        assert DocumentType.INFORMED_CONSENT in types
        assert DocumentType.FDA_1572 in types
        assert DocumentType.SITE_CONTRACT in types

    def test_document_statuses_in_seed(self, svc: SiteInitiationService):
        all_docs = []
        for site in svc.list_sites():
            all_docs.extend(svc.list_regulatory_documents(site.id))
        statuses = {d.status for d in all_docs}
        assert DocumentStatus.APPROVED in statuses
        assert DocumentStatus.SUBMITTED in statuses
        assert DocumentStatus.UNDER_REVIEW in statuses
        assert DocumentStatus.NOT_SUBMITTED in statuses


# =====================================================================
# READINESS ASSESSMENT
# =====================================================================


class TestReadinessAssessment:
    """Test readiness assessment operations."""

    @pytest.mark.anyio
    async def test_get_readiness_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SINIT-001"
        assert data["overall_score"] >= 90.0
        assert len(data["blockers"]) == 0

    @pytest.mark.anyio
    async def test_get_readiness_assessment_with_blockers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-003/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["blockers"]) > 0
        assert data["overall_score"] < 90.0

    @pytest.mark.anyio
    async def test_get_readiness_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-010/readiness")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_readiness_assessment(self, client: AsyncClient):
        payload = {
            "category_scores": {
                "regulatory": 100.0,
                "staffing": 100.0,
                "facilities": 100.0,
                "equipment": 100.0,
                "pharmacy": 100.0,
                "laboratory": 100.0,
                "training": 100.0,
                "it_systems": 100.0,
            },
            "blockers": [],
            "assessed_by": "Test Assessor",
        }
        resp = await client.put(f"{API_PREFIX}/SINIT-003/readiness", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 100.0
        assert len(data["blockers"]) == 0

    @pytest.mark.anyio
    async def test_update_readiness_auto_calculates_score(self, client: AsyncClient):
        payload = {
            "category_scores": {
                "regulatory": 80.0,
                "staffing": 60.0,
            },
            "blockers": ["Staffing below threshold"],
            "assessed_by": "Test Assessor",
        }
        resp = await client.put(f"{API_PREFIX}/SINIT-003/readiness", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 70.0  # (80 + 60) / 2

    @pytest.mark.anyio
    async def test_update_readiness_invalid_site(self, client: AsyncClient):
        payload = {
            "category_scores": {"regulatory": 100.0},
            "blockers": [],
            "assessed_by": "Test",
        }
        resp = await client.put(f"{API_PREFIX}/SINIT-NONEXISTENT/readiness", json=payload)
        assert resp.status_code == 400

    def test_readiness_category_scores(self, svc: SiteInitiationService):
        assessment = svc.get_readiness_assessment("SINIT-004")
        assert assessment is not None
        assert ReadinessCategory.REGULATORY.value in assessment.category_scores
        assert ReadinessCategory.STAFFING.value in assessment.category_scores
        assert assessment.category_scores[ReadinessCategory.REGULATORY.value] < 50.0

    def test_readiness_overall_score_range(self, svc: SiteInitiationService):
        for site_id in ["SINIT-001", "SINIT-002", "SINIT-003", "SINIT-004", "SINIT-005"]:
            assessment = svc.get_readiness_assessment(site_id)
            if assessment:
                assert 0.0 <= assessment.overall_score <= 100.0

    def test_perfect_readiness_site(self, svc: SiteInitiationService):
        assessment = svc.get_readiness_assessment("SINIT-008")
        assert assessment is not None
        assert assessment.overall_score == 100.0
        for score in assessment.category_scores.values():
            assert score == 100.0


# =====================================================================
# MILESTONES
# =====================================================================


class TestMilestones:
    """Test milestone tracking operations."""

    @pytest.mark.anyio
    async def test_get_milestones(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SINIT-001"

    @pytest.mark.anyio
    async def test_get_milestones_empty(self, client: AsyncClient):
        # SINIT-007 has no milestones in seed data
        resp = await client.get(f"{API_PREFIX}/SINIT-007/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_update_milestone_status(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-009",
            json={
                "status": "completed",
                "actual_date": now.isoformat(),
                "notes": "IRB approved after extended review",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["actual_date"] is not None
        assert data["notes"] == "IRB approved after extended review"

    @pytest.mark.anyio
    async def test_update_milestone_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_milestones_sorted_by_target_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/milestones")
        data = resp.json()
        dates = [item["target_date"] for item in data["items"]]
        assert dates == sorted(dates)

    def test_milestone_types_in_seed(self, svc: SiteInitiationService):
        all_ms = []
        for site in svc.list_sites():
            all_ms.extend(svc.get_milestones(site.id))
        types = {m.milestone_type for m in all_ms}
        assert MilestoneType.SITE_IDENTIFIED in types
        assert MilestoneType.QUALIFICATION_VISIT_COMPLETE in types
        assert MilestoneType.IRB_APPROVAL in types
        assert MilestoneType.SITE_ACTIVATED in types
        assert MilestoneType.FIRST_PATIENT_SCREENED in types

    def test_overdue_milestone_exists(self, svc: SiteInitiationService):
        milestones = svc.get_milestones("SINIT-003")
        overdue = [m for m in milestones if m.status == MilestoneStatus.OVERDUE]
        assert len(overdue) > 0

    def test_in_progress_milestone_exists(self, svc: SiteInitiationService):
        milestones = svc.get_milestones("SINIT-009")
        in_progress = [m for m in milestones if m.status == MilestoneStatus.IN_PROGRESS]
        assert len(in_progress) > 0

    def test_milestone_update_refreshes_site(self, svc: SiteInitiationService):
        from app.schemas.site_initiation import MilestoneUpdate

        now = datetime.now(timezone.utc)
        svc.update_milestone("MS-009", MilestoneUpdate(
            status=MilestoneStatus.COMPLETED,
            actual_date=now,
        ))
        site = svc.get_site("SINIT-003")
        assert site is not None
        ms = [m for m in site.milestones if m.id == "MS-009"]
        assert len(ms) == 1
        assert ms[0].status == MilestoneStatus.COMPLETED


# =====================================================================
# ACTIVATION METRICS
# =====================================================================


class TestActivationMetrics:
    """Test activation metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites"] == 10
        assert data["sites_activated"] > 0
        assert data["sites_pending_activation"] > 0

    @pytest.mark.anyio
    async def test_metrics_sites_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["sites_by_status"].values())
        assert total_by_status == data["total_sites"]

    @pytest.mark.anyio
    async def test_metrics_avg_days_to_activate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_days_to_activate"] > 0

    @pytest.mark.anyio
    async def test_metrics_documents_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_docs = sum(data["documents_by_status"].values())
        assert total_docs == data["total_regulatory_documents"]

    @pytest.mark.anyio
    async def test_metrics_avg_readiness_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0.0 <= data["avg_readiness_score"] <= 100.0

    @pytest.mark.anyio
    async def test_metrics_avg_target_enrollment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_target_enrollment"] > 0

    def test_metrics_bottleneck_categories(self, svc: SiteInitiationService):
        metrics = svc.get_activation_metrics()
        # There should be at least one bottleneck from sites with low scores
        assert len(metrics.bottleneck_categories) > 0

    def test_metrics_total_regulatory_documents(self, svc: SiteInitiationService):
        metrics = svc.get_activation_metrics()
        assert metrics.total_regulatory_documents == 24

    def test_metrics_activated_plus_pending_plus_closed(self, svc: SiteInitiationService):
        metrics = svc.get_activation_metrics()
        # activated + pending + closed = total
        closed_count = metrics.sites_by_status.get("closed", 0)
        assert metrics.sites_activated + metrics.sites_pending_activation + closed_count == metrics.total_sites


# =====================================================================
# SITE DETAILS
# =====================================================================


class TestSiteDetails:
    """Test site content and field validation."""

    @pytest.mark.anyio
    async def test_site_has_principal_investigator(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001")
        data = resp.json()
        assert len(data["principal_investigator"]) > 0

    @pytest.mark.anyio
    async def test_site_has_institution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001")
        data = resp.json()
        assert len(data["institution"]) > 0

    @pytest.mark.anyio
    async def test_enrolling_site_has_enrollment_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001")
        data = resp.json()
        assert data["status"] == "enrolling"
        assert data["current_enrollment"] > 0
        assert data["target_enrollment"] > 0
        assert data["current_enrollment"] <= data["target_enrollment"]

    @pytest.mark.anyio
    async def test_identified_site_has_no_enrollment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-010")
        data = resp.json()
        assert data["status"] == "identified"
        assert data["current_enrollment"] == 0

    @pytest.mark.anyio
    async def test_site_has_site_number(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001")
        data = resp.json()
        assert data["site_number"] == "1001"

    @pytest.mark.anyio
    async def test_site_has_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001")
        data = resp.json()
        assert data["country"] == "US"


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_site_initiation_service()
        svc2 = get_site_initiation_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_site_initiation_service()
        svc2 = reset_site_initiation_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_initiation_service()
        svc.delete_site("SINIT-001")
        assert svc.get_site("SINIT-001") is None
        svc2 = reset_site_initiation_service()
        assert svc2.get_site("SINIT-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_sites_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_site_with_minimal_fields(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_number": "5001",
            "site_name": "Minimal Site",
            "principal_investigator": "Dr. Minimal",
            "institution": "Minimal Institution",
        }
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "US"  # Default
        assert data["target_enrollment"] == 0

    @pytest.mark.anyio
    async def test_update_site_enrollment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SINIT-002",
            json={"current_enrollment": 15},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_enrollment"] == 15

    @pytest.mark.anyio
    async def test_site_with_no_qualification_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-010/qualification-visits")
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_multiple_qualification_visits_per_site(self, client: AsyncClient):
        # Add two visits to SINIT-007
        payload1 = _make_qualification_visit_create(findings="First visit findings")
        payload2 = _make_qualification_visit_create(
            findings="Second visit findings",
            recommendation="approved_with_conditions",
        )
        resp1 = await client.post(f"{API_PREFIX}/SINIT-007/qualification-visits", json=payload1)
        resp2 = await client.post(f"{API_PREFIX}/SINIT-007/qualification-visits", json=payload2)
        assert resp1.status_code == 201
        assert resp2.status_code == 201

        # List and verify
        resp = await client.get(f"{API_PREFIX}/SINIT-007/qualification-visits")
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_regulatory_document_version_tracking(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-002")
        data = resp.json()
        assert data["version"] == "4.0"

    @pytest.mark.anyio
    async def test_regulatory_document_expiry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp.json()
        assert data["expiry_date"] is not None

    @pytest.mark.anyio
    async def test_update_milestone_target_date(self, client: AsyncClient):
        new_target = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-010",
            json={"target_date": new_target},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_date"] is not None


# =====================================================================
# ENUMERATION VALUES
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout."""

    @pytest.mark.anyio
    async def test_site_statuses_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "identified" in statuses
        assert "enrolling" in statuses
        assert "activated" in statuses

    @pytest.mark.anyio
    async def test_document_types_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/regulatory-documents")
        data = resp.json()
        valid_types = {e.value for e in DocumentType}
        for item in data["items"]:
            assert item["doc_type"] in valid_types

    @pytest.mark.anyio
    async def test_milestone_statuses_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/milestones")
        data = resp.json()
        valid_statuses = {e.value for e in MilestoneStatus}
        for item in data["items"]:
            assert item["status"] in valid_statuses

    @pytest.mark.anyio
    async def test_milestone_types_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/milestones")
        data = resp.json()
        valid_types = {e.value for e in MilestoneType}
        for item in data["items"]:
            assert item["milestone_type"] in valid_types

    @pytest.mark.anyio
    async def test_qualification_recommendations_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SINIT-001/qualification-visits")
        data = resp.json()
        valid_recs = {e.value for e in QualificationRecommendation}
        for item in data["items"]:
            assert item["recommendation"] in valid_recs


# =====================================================================
# CROSS-SITE ANALYSIS
# =====================================================================


class TestCrossSiteAnalysis:
    """Test cross-site and cross-trial analysis."""

    def test_sites_across_multiple_trials(self, svc: SiteInitiationService):
        all_sites = svc.list_sites()
        trial_ids = {s.trial_id for s in all_sites}
        assert len(trial_ids) >= 3

    def test_enrollment_progress_across_sites(self, svc: SiteInitiationService):
        all_sites = svc.list_sites()
        total_enrolled = sum(s.current_enrollment for s in all_sites)
        total_target = sum(s.target_enrollment for s in all_sites)
        assert total_enrolled > 0
        assert total_target > 0
        assert total_enrolled <= total_target

    def test_regulatory_documents_across_sites(self, svc: SiteInitiationService):
        all_docs = []
        for site in svc.list_sites():
            all_docs.extend(svc.list_regulatory_documents(site.id))
        site_ids = {d.site_id for d in all_docs}
        assert len(site_ids) >= 5

    def test_readiness_scores_distribution(self, svc: SiteInitiationService):
        scores = []
        for site in svc.list_sites():
            assessment = svc.get_readiness_assessment(site.id)
            if assessment:
                scores.append(assessment.overall_score)
        assert len(scores) >= 5
        assert min(scores) < 80.0  # At least one low readiness
        assert max(scores) >= 95.0  # At least one high readiness

    def test_milestones_across_sites(self, svc: SiteInitiationService):
        all_ms = []
        for site in svc.list_sites():
            all_ms.extend(svc.get_milestones(site.id))
        site_ids = {m.site_id for m in all_ms}
        assert len(site_ids) >= 5

    def test_activated_sites_have_completed_milestones(self, svc: SiteInitiationService):
        for site in svc.list_sites():
            if site.status in (SiteStatus.ACTIVATED, SiteStatus.ENROLLING):
                milestones = svc.get_milestones(site.id)
                completed = [m for m in milestones if m.status == MilestoneStatus.COMPLETED]
                assert len(completed) > 0, f"Activated site {site.id} has no completed milestones"

    def test_identified_site_minimal_milestones(self, svc: SiteInitiationService):
        milestones = svc.get_milestones("SINIT-010")
        completed = [m for m in milestones if m.status == MilestoneStatus.COMPLETED]
        # Should have at least site_identified completed
        assert len(completed) >= 1
