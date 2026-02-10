"""Tests for Protocol Feasibility Assessment module.

Covers:
- Seed data verification (studies, site assessments, competitive entries, projections,
  questions, questionnaire responses)
- Feasibility study CRUD (create, read, update, delete, list, filter by status/area)
- Study lifecycle transitions (draft -> in_progress -> completed -> approved -> archived)
- Site assessment creation and auto-scoring
- Site assessment update with rating recomputation
- Competitive landscape management (create, read, update, list, filter by threat)
- Enrollment projection creation with auto-computed values
- Enrollment projection auto-generation
- Feasibility summary computation (sites by rating, risks, recommendations)
- Questionnaire and response workflows
- Metrics aggregation
- Error handling (404s, 400s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.protocol_feasibility import (
    CompetitiveThreatLevel,
    EnrollmentRisk,
    FeasibilityStatus,
    SiteRating,
)
from app.services.protocol_feasibility_service import (
    ProtocolFeasibilityService,
    get_protocol_feasibility_service,
    reset_protocol_feasibility_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/protocol-feasibility"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    reset_protocol_feasibility_service()
    svc = get_protocol_feasibility_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProtocolFeasibilityService:
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


def _make_study_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "protocol_id": "PROT-TEST-001",
        "protocol_version": "1.0",
        "therapeutic_area": "Cardiology",
        "indication": "Heart Failure",
        "phase": "Phase III",
        "lead_analyst": "Test Analyst",
        "target_enrollment": 200,
        "enrollment_duration_months": 12,
        "target_countries": ["United States", "Canada"],
        "target_sites_count": 30,
    }
    defaults.update(overrides)
    return defaults


def _make_site_assessment_create(**overrides) -> dict:
    defaults = {
        "site_id": "SITE-TEST-001",
        "site_name": "Test Medical Center",
        "country": "United States",
        "investigator_name": "Dr. Test Investigator",
        "investigator_experience_years": 10,
        "competing_studies_count": 1,
        "patient_pool_estimate": 200,
        "annual_enrollment_estimate": 15,
        "infrastructure_score": 85.0,
        "regulatory_readiness": 90.0,
        "staff_availability": 80.0,
        "lab_capabilities": 82.0,
        "pharmacy_capabilities": 78.0,
        "notes": "Good site for testing",
        "assessed_by": "Test Assessor",
    }
    defaults.update(overrides)
    return defaults


def _make_competitive_create(**overrides) -> dict:
    defaults = {
        "competitor_trial_id": "NCT09999999",
        "sponsor_name": "Test Pharma Inc",
        "phase": "Phase II",
        "indication": "Test Indication",
        "estimated_enrollment": 250,
        "competing_sites_overlap": 5,
        "threat_level": "moderate",
    }
    defaults.update(overrides)
    return defaults


def _make_projection_create(**overrides) -> dict:
    defaults = {
        "scenario_name": "Test Scenario",
        "sites_count": 30,
        "patients_per_site_per_month": 0.5,
        "screen_failure_rate": 0.25,
        "dropout_rate": 0.10,
    }
    defaults.update(overrides)
    return defaults


def _make_question_create(**overrides) -> dict:
    defaults = {
        "category": "logistics",
        "question_text": "Does the site have adequate storage for study drug?",
        "response_type": "yes_no",
        "required": True,
        "display_order": 10,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_studies_count(self, svc: ProtocolFeasibilityService):
        studies = svc.list_studies()
        assert len(studies) == 3

    def test_seed_studies_statuses(self, svc: ProtocolFeasibilityService):
        studies = svc.list_studies()
        statuses = {s.status for s in studies}
        assert FeasibilityStatus.DRAFT in statuses
        assert FeasibilityStatus.IN_PROGRESS in statuses
        assert FeasibilityStatus.COMPLETED in statuses

    def test_seed_site_assessments_count(self, svc: ProtocolFeasibilityService):
        # FS-001 should have 7 assessments, FS-002 should have 3
        fs001_sites = svc.list_site_assessments("FS-001")
        fs002_sites = svc.list_site_assessments("FS-002")
        assert len(fs001_sites) == 7
        assert len(fs002_sites) == 3

    def test_seed_site_ratings_variety(self, svc: ProtocolFeasibilityService):
        sites = svc.list_site_assessments("FS-001")
        ratings = {s.site_rating for s in sites}
        assert SiteRating.EXCELLENT in ratings
        assert SiteRating.GOOD in ratings
        assert SiteRating.NOT_SUITABLE in ratings

    def test_seed_competitive_entries_count(self, svc: ProtocolFeasibilityService):
        fs001_comp = svc.list_competitive_landscape("FS-001")
        fs002_comp = svc.list_competitive_landscape("FS-002")
        assert len(fs001_comp) == 3
        assert len(fs002_comp) == 2

    def test_seed_enrollment_projections_count(self, svc: ProtocolFeasibilityService):
        fs001_proj = svc.list_enrollment_projections("FS-001")
        fs002_proj = svc.list_enrollment_projections("FS-002")
        assert len(fs001_proj) == 4
        assert len(fs002_proj) == 2

    def test_seed_questions_count(self, svc: ProtocolFeasibilityService):
        questions = svc.list_questions("FS-001")
        assert len(questions) == 6

    def test_seed_questionnaire_responses_count(self, svc: ProtocolFeasibilityService):
        responses = svc.list_questionnaire_responses("FS-001")
        assert len(responses) == 4


# =====================================================================
# FEASIBILITY STUDY CRUD
# =====================================================================


class TestFeasibilityStudyCrud:
    """Test feasibility study CRUD operations."""

    @pytest.mark.anyio
    async def test_list_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_studies_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"status": "in_progress"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_list_studies_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies", params={"therapeutic_area": "Oncology"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["therapeutic_area"] == "Oncology"

    @pytest.mark.anyio
    async def test_get_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FS-001"
        assert data["therapeutic_area"] == "Ophthalmology"

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_study(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["therapeutic_area"] == "Cardiology"
        assert data["status"] == "draft"
        assert data["id"].startswith("FS-")
        assert data["overall_feasibility_score"] is None

    @pytest.mark.anyio
    async def test_create_study_sets_initiated_date(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["initiated_date"] is not None

    @pytest.mark.anyio
    async def test_update_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/FS-001",
            json={"lead_analyst": "Dr. Updated Analyst", "target_enrollment": 500},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["lead_analyst"] == "Dr. Updated Analyst"
        assert data["target_enrollment"] == 500

    @pytest.mark.anyio
    async def test_update_study_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/FS-001",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/FS-NONEXISTENT",
            json={"lead_analyst": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/FS-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/studies/FS-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/FS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STUDY LIFECYCLE
# =====================================================================


class TestStudyLifecycle:
    """Test study status lifecycle transitions."""

    def test_study_lifecycle_transitions(self, svc: ProtocolFeasibilityService):
        from app.schemas.protocol_feasibility import FeasibilityStudyUpdate

        study = svc.get_study("FS-003")
        assert study is not None
        assert study.status == FeasibilityStatus.DRAFT

        updated = svc.update_study(
            "FS-003", FeasibilityStudyUpdate(status=FeasibilityStatus.IN_PROGRESS)
        )
        assert updated is not None
        assert updated.status == FeasibilityStatus.IN_PROGRESS

        updated = svc.update_study(
            "FS-003", FeasibilityStudyUpdate(status=FeasibilityStatus.COMPLETED)
        )
        assert updated is not None
        assert updated.status == FeasibilityStatus.COMPLETED
        assert updated.completed_date is not None

        updated = svc.update_study(
            "FS-003", FeasibilityStudyUpdate(status=FeasibilityStatus.APPROVED)
        )
        assert updated is not None
        assert updated.status == FeasibilityStatus.APPROVED

        updated = svc.update_study(
            "FS-003", FeasibilityStudyUpdate(status=FeasibilityStatus.ARCHIVED)
        )
        assert updated is not None
        assert updated.status == FeasibilityStatus.ARCHIVED

    def test_completed_study_has_completed_date(self, svc: ProtocolFeasibilityService):
        study = svc.get_study("FS-002")
        assert study is not None
        assert study.status == FeasibilityStatus.COMPLETED
        assert study.completed_date is not None


# =====================================================================
# SITE ASSESSMENT CRUD
# =====================================================================


class TestSiteAssessmentCrud:
    """Test site assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_site_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/site-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_site_assessments_filter_country(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies/FS-001/site-assessments",
            params={"country": "United States"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "United States"

    @pytest.mark.anyio
    async def test_list_site_assessments_filter_rating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies/FS-001/site-assessments",
            params={"site_rating": "excellent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_rating"] == "excellent"

    @pytest.mark.anyio
    async def test_list_site_assessments_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-NONEXISTENT/site-assessments")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site_assessment(self, client: AsyncClient):
        payload = _make_site_assessment_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/site-assessments", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "Test Medical Center"
        assert data["id"].startswith("SA-")
        # Rating should be auto-computed
        assert data["site_rating"] in [r.value for r in SiteRating]

    @pytest.mark.anyio
    async def test_create_site_assessment_excellent_scores(self, client: AsyncClient):
        payload = _make_site_assessment_create(
            infrastructure_score=95.0,
            regulatory_readiness=92.0,
            staff_availability=90.0,
            lab_capabilities=88.0,
            pharmacy_capabilities=85.0,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/site-assessments", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_rating"] == "excellent"

    @pytest.mark.anyio
    async def test_create_site_assessment_poor_scores(self, client: AsyncClient):
        payload = _make_site_assessment_create(
            infrastructure_score=20.0,
            regulatory_readiness=15.0,
            staff_availability=25.0,
            lab_capabilities=10.0,
            pharmacy_capabilities=10.0,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/site-assessments", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_rating"] == "not_suitable"

    @pytest.mark.anyio
    async def test_create_site_assessment_study_not_found(self, client: AsyncClient):
        payload = _make_site_assessment_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/site-assessments", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_site_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-assessments/SA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SA-001"
        assert data["site_name"] == "Memorial Hermann Eye Institute"

    @pytest.mark.anyio
    async def test_get_site_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-assessments/SA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_site_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-assessments/SA-001",
            json={"investigator_name": "Dr. Updated Name", "patient_pool_estimate": 400},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["investigator_name"] == "Dr. Updated Name"
        assert data["patient_pool_estimate"] == 400

    @pytest.mark.anyio
    async def test_update_site_assessment_recomputes_rating(self, client: AsyncClient):
        # Set very low scores to force rating change
        resp = await client.put(
            f"{API_PREFIX}/site-assessments/SA-001",
            json={
                "infrastructure_score": 20.0,
                "regulatory_readiness": 15.0,
                "staff_availability": 10.0,
                "lab_capabilities": 10.0,
                "pharmacy_capabilities": 10.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_rating"] == "not_suitable"

    @pytest.mark.anyio
    async def test_update_site_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-assessments/SA-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404


# =====================================================================
# SITE SCORING
# =====================================================================


class TestSiteScoring:
    """Test site rating computation logic."""

    def test_compute_rating_excellent(self, svc: ProtocolFeasibilityService):
        rating = svc._compute_site_rating(95.0, 92.0, 88.0, 90.0, 85.0)
        assert rating == SiteRating.EXCELLENT

    def test_compute_rating_good(self, svc: ProtocolFeasibilityService):
        rating = svc._compute_site_rating(80.0, 75.0, 72.0, 70.0, 68.0)
        assert rating == SiteRating.GOOD

    def test_compute_rating_acceptable(self, svc: ProtocolFeasibilityService):
        rating = svc._compute_site_rating(65.0, 60.0, 55.0, 55.0, 50.0)
        assert rating == SiteRating.ACCEPTABLE

    def test_compute_rating_marginal(self, svc: ProtocolFeasibilityService):
        rating = svc._compute_site_rating(50.0, 45.0, 40.0, 35.0, 30.0)
        assert rating == SiteRating.MARGINAL

    def test_compute_rating_not_suitable(self, svc: ProtocolFeasibilityService):
        rating = svc._compute_site_rating(20.0, 15.0, 10.0, 10.0, 5.0)
        assert rating == SiteRating.NOT_SUITABLE

    def test_score_site_method(self, svc: ProtocolFeasibilityService):
        result = svc.score_site("SA-001")
        assert result is not None
        assert result.site_rating == SiteRating.EXCELLENT

    def test_score_site_not_found(self, svc: ProtocolFeasibilityService):
        result = svc.score_site("SA-NONEXISTENT")
        assert result is None


# =====================================================================
# COMPETITIVE LANDSCAPE
# =====================================================================


class TestCompetitiveLandscape:
    """Test competitive landscape management."""

    @pytest.mark.anyio
    async def test_list_competitive_landscape(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/competitive-landscape")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_competitive_landscape_filter_threat(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies/FS-001/competitive-landscape",
            params={"threat_level": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["threat_level"] == "high"

    @pytest.mark.anyio
    async def test_list_competitive_sorted_by_threat(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/competitive-landscape")
        data = resp.json()
        threat_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        levels = [threat_order[item["threat_level"]] for item in data["items"]]
        assert levels == sorted(levels)

    @pytest.mark.anyio
    async def test_list_competitive_study_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/competitive-landscape"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_competitive_entry(self, client: AsyncClient):
        payload = _make_competitive_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/competitive-landscape", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sponsor_name"] == "Test Pharma Inc"
        assert data["id"].startswith("CL-")

    @pytest.mark.anyio
    async def test_create_competitive_entry_with_date(self, client: AsyncClient):
        payload = _make_competitive_create(
            enrollment_start_date="2026-06-01",
            notes="Trial starting mid-year",
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/competitive-landscape", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["enrollment_start_date"] == "2026-06-01"

    @pytest.mark.anyio
    async def test_create_competitive_study_not_found(self, client: AsyncClient):
        payload = _make_competitive_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/competitive-landscape", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_competitive_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competitive-landscape/CL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CL-001"
        assert data["sponsor_name"] == "Roche/Genentech"

    @pytest.mark.anyio
    async def test_get_competitive_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competitive-landscape/CL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_competitive_entry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/competitive-landscape/CL-001",
            json={"threat_level": "critical", "estimated_enrollment": 700},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threat_level"] == "critical"
        assert data["estimated_enrollment"] == 700

    @pytest.mark.anyio
    async def test_update_competitive_entry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/competitive-landscape/CL-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404


# =====================================================================
# ENROLLMENT PROJECTIONS
# =====================================================================


class TestEnrollmentProjections:
    """Test enrollment projection scenarios."""

    @pytest.mark.anyio
    async def test_list_enrollment_projections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/enrollment-projections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_projections_sorted_by_confidence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/enrollment-projections")
        data = resp.json()
        confidences = [item["confidence_level"] for item in data["items"]]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.anyio
    async def test_list_projections_study_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/enrollment-projections"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_enrollment_projection(self, client: AsyncClient):
        payload = _make_projection_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/enrollment-projections", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["scenario_name"] == "Test Scenario"
        assert data["id"].startswith("EP-")
        # Auto-computed fields
        assert data["projected_enrollment_months"] >= 1
        assert data["projected_total_enrolled"] >= 0
        assert data["confidence_level"] > 0
        assert data["risk_level"] in [r.value for r in EnrollmentRisk]

    @pytest.mark.anyio
    async def test_create_projection_optimistic(self, client: AsyncClient):
        payload = _make_projection_create(
            scenario_name="Very Optimistic",
            sites_count=200,
            patients_per_site_per_month=2.0,
            screen_failure_rate=0.05,
            dropout_rate=0.03,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/enrollment-projections", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_level"] == "low"

    @pytest.mark.anyio
    async def test_create_projection_pessimistic(self, client: AsyncClient):
        payload = _make_projection_create(
            scenario_name="Very Pessimistic",
            sites_count=10,
            patients_per_site_per_month=0.1,
            screen_failure_rate=0.50,
            dropout_rate=0.30,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/enrollment-projections", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_level"] in ("high", "very_high")

    @pytest.mark.anyio
    async def test_create_projection_study_not_found(self, client: AsyncClient):
        payload = _make_projection_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/enrollment-projections", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_enrollment_projection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-projections/EP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EP-001"
        assert data["scenario_name"] == "Base Case"

    @pytest.mark.anyio
    async def test_get_enrollment_projection_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-projections/EP-NONEXISTENT")
        assert resp.status_code == 404

    def test_generate_enrollment_projections(self, svc: ProtocolFeasibilityService):
        """Test auto-generation of standard projection scenarios."""
        generated = svc.generate_enrollment_projections("FS-003")
        assert len(generated) == 3
        names = {p.scenario_name for p in generated}
        assert "Auto - Optimistic" in names
        assert "Auto - Base Case" in names
        assert "Auto - Conservative" in names

    def test_generate_projections_nonexistent_study(self, svc: ProtocolFeasibilityService):
        generated = svc.generate_enrollment_projections("FS-NONEXISTENT")
        assert len(generated) == 0


# =====================================================================
# FEASIBILITY SUMMARY
# =====================================================================


class TestFeasibilitySummary:
    """Test feasibility summary generation."""

    @pytest.mark.anyio
    async def test_get_feasibility_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_id"] == "FS-001"
        assert data["total_sites_assessed"] == 7
        assert "sites_by_rating" in data
        assert data["avg_feasibility_score"] > 0

    @pytest.mark.anyio
    async def test_summary_has_enrollment_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/summary")
        data = resp.json()
        enrollment_range = data["projected_enrollment_range"]
        assert "min" in enrollment_range
        assert "max" in enrollment_range
        assert enrollment_range["min"] <= enrollment_range["max"]

    @pytest.mark.anyio
    async def test_summary_has_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/summary")
        data = resp.json()
        assert len(data["top_risks"]) > 0

    @pytest.mark.anyio
    async def test_summary_has_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/summary")
        data = resp.json()
        assert len(data["recommendations"]) > 0

    @pytest.mark.anyio
    async def test_summary_sites_by_rating_sums(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/summary")
        data = resp.json()
        total_by_rating = sum(data["sites_by_rating"].values())
        assert total_by_rating == data["total_sites_assessed"]

    @pytest.mark.anyio
    async def test_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-NONEXISTENT/summary")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_summary_updates_study_score(self, client: AsyncClient):
        # Get summary to trigger score update
        await client.get(f"{API_PREFIX}/studies/FS-001/summary")
        # Now check study has updated score
        resp = await client.get(f"{API_PREFIX}/studies/FS-001")
        data = resp.json()
        assert data["overall_feasibility_score"] is not None
        assert data["overall_feasibility_score"] > 0

    def test_summary_competitive_risk_detection(self, svc: ProtocolFeasibilityService):
        """FS-002 has a critical competitor (AbbVie) - should show in risks."""
        summary = svc.get_feasibility_summary("FS-002")
        assert summary is not None
        risk_texts = " ".join(summary.top_risks)
        assert "critical" in risk_texts.lower() or "competitive" in risk_texts.lower()


# =====================================================================
# QUESTIONNAIRE WORKFLOW
# =====================================================================


class TestQuestionnaireWorkflow:
    """Test questionnaire and response workflows."""

    @pytest.mark.anyio
    async def test_list_questionnaire(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/questionnaire")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_questionnaire_sorted_by_order(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/questionnaire")
        data = resp.json()
        orders = [item["display_order"] for item in data["items"]]
        assert orders == sorted(orders)

    @pytest.mark.anyio
    async def test_list_questionnaire_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-NONEXISTENT/questionnaire")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_question(self, client: AsyncClient):
        payload = _make_question_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/questionnaire", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["question_text"] == "Does the site have adequate storage for study drug?"
        assert data["id"].startswith("FQ-")

    @pytest.mark.anyio
    async def test_create_question_study_not_found(self, client: AsyncClient):
        payload = _make_question_create()
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/questionnaire", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_questionnaire_response(self, client: AsyncClient):
        payload = {
            "site_id": "SITE-201",
            "question_id": "FQ-001",
            "response_value": "Yes",
            "responded_by": "Prof. Hans Mueller",
        }
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/questionnaire-responses", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["response_value"] == "Yes"
        assert data["id"].startswith("QR-")
        assert data["responded_date"] is not None

    @pytest.mark.anyio
    async def test_submit_response_invalid_question(self, client: AsyncClient):
        payload = {
            "site_id": "SITE-201",
            "question_id": "FQ-NONEXISTENT",
            "response_value": "Yes",
            "responded_by": "Test User",
        }
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/questionnaire-responses", json=payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_response_wrong_study(self, client: AsyncClient):
        # FQ-001 belongs to FS-001, not FS-002
        payload = {
            "site_id": "SITE-103",
            "question_id": "FQ-001",
            "response_value": "Yes",
            "responded_by": "Test User",
        }
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-002/questionnaire-responses", json=payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_response_study_not_found(self, client: AsyncClient):
        payload = {
            "site_id": "SITE-101",
            "question_id": "FQ-001",
            "response_value": "Yes",
            "responded_by": "Test User",
        }
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-NONEXISTENT/questionnaire-responses", json=payload
        )
        assert resp.status_code == 404

    def test_list_responses_filter_site(self, svc: ProtocolFeasibilityService):
        responses = svc.list_questionnaire_responses("FS-001", site_id="SITE-101")
        assert len(responses) == 3
        for r in responses:
            assert r.site_id == "SITE-101"


# =====================================================================
# METRICS
# =====================================================================


class TestFeasibilityMetrics:
    """Test feasibility metrics aggregation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_studies"] == 3
        assert data["active_studies"] == 2  # draft + in_progress
        assert data["sites_assessed_total"] == 10
        assert data["avg_sites_per_study"] > 0
        assert data["avg_enrollment_projection"] > 0

    def test_metrics_active_studies_count(self, svc: ProtocolFeasibilityService):
        metrics = svc.get_metrics()
        studies = svc.list_studies()
        active = sum(
            1 for s in studies
            if s.status in (FeasibilityStatus.DRAFT, FeasibilityStatus.IN_PROGRESS)
        )
        assert metrics.active_studies == active

    def test_metrics_total_sites(self, svc: ProtocolFeasibilityService):
        metrics = svc.get_metrics()
        assert metrics.sites_assessed_total == 10

    def test_metrics_avg_feasibility_score(self, svc: ProtocolFeasibilityService):
        metrics = svc.get_metrics()
        # FS-001 has 72.5, FS-002 has 81.3, FS-003 has None
        # So avg should be (72.5 + 81.3) / 2
        expected = round((72.5 + 81.3) / 2, 1)
        assert metrics.avg_feasibility_score == expected


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_protocol_feasibility_service()
        svc2 = get_protocol_feasibility_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_protocol_feasibility_service()
        reset_protocol_feasibility_service()
        svc2 = get_protocol_feasibility_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_protocol_feasibility_service()
        svc.delete_study("FS-001")
        assert svc.get_study("FS-001") is None
        reset_protocol_feasibility_service()
        svc2 = get_protocol_feasibility_service()
        assert svc2.get_study("FS-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_studies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_studies_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies", params={"therapeutic_area": "Nonexistent Area"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_study_with_all_fields(self, client: AsyncClient):
        payload = _make_study_create(
            therapeutic_area="Neurology",
            indication="Alzheimer Disease",
            phase="Phase I",
            target_enrollment=50,
            enrollment_duration_months=6,
            target_countries=["United States"],
            target_sites_count=10,
        )
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_site_assessment_score_boundaries(self, client: AsyncClient):
        # Test boundary values (0 and 100)
        payload = _make_site_assessment_create(
            infrastructure_score=0.0,
            regulatory_readiness=0.0,
            staff_availability=0.0,
            lab_capabilities=0.0,
            pharmacy_capabilities=0.0,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/site-assessments", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_rating"] == "not_suitable"

    @pytest.mark.anyio
    async def test_site_assessment_max_scores(self, client: AsyncClient):
        payload = _make_site_assessment_create(
            infrastructure_score=100.0,
            regulatory_readiness=100.0,
            staff_availability=100.0,
            lab_capabilities=100.0,
            pharmacy_capabilities=100.0,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/site-assessments", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_rating"] == "excellent"

    @pytest.mark.anyio
    async def test_competitive_entry_all_threat_levels(self, client: AsyncClient):
        for level in ["low", "moderate", "high", "critical"]:
            payload = _make_competitive_create(
                competitor_trial_id=f"NCT-{level}",
                threat_level=level,
            )
            resp = await client.post(
                f"{API_PREFIX}/studies/FS-001/competitive-landscape", json=payload
            )
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_projection_with_start_date(self, client: AsyncClient):
        payload = _make_projection_create(
            enrollment_start_date="2026-09-01",
            assumptions="Testing with explicit start date",
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/enrollment-projections", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["enrollment_start_date"] == "2026-09-01"

    @pytest.mark.anyio
    async def test_projection_zero_enrollment_rate(self, client: AsyncClient):
        payload = _make_projection_create(
            patients_per_site_per_month=0.0,
        )
        resp = await client.post(
            f"{API_PREFIX}/studies/FS-001/enrollment-projections", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        # Should fall back to max months
        assert data["projected_enrollment_months"] == 36

    @pytest.mark.anyio
    async def test_question_various_response_types(self, client: AsyncClient):
        for rtype in ["text", "number", "yes_no", "scale"]:
            payload = _make_question_create(
                question_text=f"Test question for {rtype}",
                response_type=rtype,
                display_order=20 + ["text", "number", "yes_no", "scale"].index(rtype),
            )
            resp = await client.post(
                f"{API_PREFIX}/studies/FS-001/questionnaire", json=payload
            )
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_summary_empty_study(self, client: AsyncClient):
        """A study with no assessments should still return a valid summary."""
        resp = await client.get(f"{API_PREFIX}/studies/FS-003/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites_assessed"] == 0
        assert data["avg_feasibility_score"] == 0.0


# =====================================================================
# DATA INTEGRITY
# =====================================================================


class TestDataIntegrity:
    """Test data consistency and relationship integrity."""

    @pytest.mark.anyio
    async def test_site_assessments_belong_to_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/site-assessments")
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "FS-001"

    @pytest.mark.anyio
    async def test_competitive_entries_belong_to_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-002/competitive-landscape")
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "FS-002"

    @pytest.mark.anyio
    async def test_projections_belong_to_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-002/enrollment-projections")
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "FS-002"

    @pytest.mark.anyio
    async def test_questions_belong_to_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/questionnaire")
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "FS-001"

    @pytest.mark.anyio
    async def test_all_site_ratings_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/site-assessments")
        data = resp.json()
        valid_ratings = {r.value for r in SiteRating}
        for item in data["items"]:
            assert item["site_rating"] in valid_ratings

    @pytest.mark.anyio
    async def test_all_threat_levels_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/competitive-landscape")
        data = resp.json()
        valid_levels = {t.value for t in CompetitiveThreatLevel}
        for item in data["items"]:
            assert item["threat_level"] in valid_levels

    @pytest.mark.anyio
    async def test_all_risk_levels_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FS-001/enrollment-projections")
        data = resp.json()
        valid_risks = {r.value for r in EnrollmentRisk}
        for item in data["items"]:
            assert item["risk_level"] in valid_risks

    @pytest.mark.anyio
    async def test_score_ranges_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-assessments/SA-001")
        data = resp.json()
        for field in [
            "infrastructure_score", "regulatory_readiness",
            "staff_availability", "lab_capabilities", "pharmacy_capabilities",
        ]:
            assert 0.0 <= data[field] <= 100.0

    @pytest.mark.anyio
    async def test_projection_rates_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-projections/EP-001")
        data = resp.json()
        assert 0.0 <= data["screen_failure_rate"] <= 1.0
        assert 0.0 <= data["dropout_rate"] <= 1.0
        assert 0.0 <= data["confidence_level"] <= 100.0
