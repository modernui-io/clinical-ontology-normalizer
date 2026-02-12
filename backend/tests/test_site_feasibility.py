"""Tests for Site Feasibility Management (SITE-FEAS).

Covers:
- Seed data verification (site assessments, investigator qualifications,
  patient pool analyses, capability evaluations, feasibility surveys)
- Full CRUD for all 5 entity types (create, read, update, delete, list)
- List filtering by trial_id
- 404 handling for all entity types
- Validation errors (422)
- Metrics endpoint
- Service singleton pattern
- Demo data seeding and reset
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.site_feasibility_service import (
    SiteFeasibilityService,
    get_site_feasibility_service,
    reset_site_feasibility_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-feasibility"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_feasibility_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SiteFeasibilityService:
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


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NEW-001",
        "site_name": "New Test Hospital",
        "country": "United States",
        "assessor": "Test Assessor",
        "region": "Northeast",
        "enrollment_potential": 25,
    }
    defaults.update(overrides)
    return defaults


def _make_investigator_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "site_id": "SITE-NEW-001",
        "investigator_name": "Dr. Test Investigator",
        "specialty": "Dermatology",
        "years_experience": 10,
        "gcp_certified": True,
    }
    defaults.update(overrides)
    return defaults


def _make_patient_pool_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "site_id": "SITE-NEW-001",
        "indication": "Advanced CSCC",
        "analyst": "Test Analyst",
        "estimated_prevalence": 5000,
        "estimated_eligible": 300,
    }
    defaults.update(overrides)
    return defaults


def _make_capability_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NEW-001",
        "capability_area": "laboratory",
        "evaluator": "Test Evaluator",
        "score": 85.0,
        "meets_requirements": True,
    }
    defaults.update(overrides)
    return defaults


def _make_survey_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "site_id": "SITE-NEW-001",
        "survey_name": "Test Feasibility Survey",
        "total_questions": 40,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_assessments_count(self, svc: SiteFeasibilityService):
        assessments = svc.list_site_assessments()
        assert len(assessments) == 12

    def test_seed_investigators_count(self, svc: SiteFeasibilityService):
        qualifications = svc.list_investigator_qualifications()
        assert len(qualifications) == 12

    def test_seed_patient_pool_count(self, svc: SiteFeasibilityService):
        analyses = svc.list_patient_pool_analyses()
        assert len(analyses) == 12

    def test_seed_capability_evaluations_count(self, svc: SiteFeasibilityService):
        evaluations = svc.list_capability_evaluations()
        assert len(evaluations) == 12

    def test_seed_surveys_count(self, svc: SiteFeasibilityService):
        surveys = svc.list_feasibility_surveys()
        assert len(surveys) == 12

    def test_seed_assessments_have_all_three_trials(self, svc: SiteFeasibilityService):
        assessments = svc.list_site_assessments()
        trial_ids = {a.trial_id for a in assessments}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_assessments_have_multiple_statuses(self, svc: SiteFeasibilityService):
        assessments = svc.list_site_assessments()
        statuses = {a.status.value for a in assessments}
        assert "completed" in statuses
        assert "planned" in statuses

    def test_seed_assessments_have_multiple_results(self, svc: SiteFeasibilityService):
        assessments = svc.list_site_assessments()
        results = {a.result.value for a in assessments}
        assert "highly_feasible" in results
        assert "feasible" in results
        assert "not_feasible" in results
        assert "pending" in results

    def test_seed_investigators_have_multiple_statuses(self, svc: SiteFeasibilityService):
        qualifications = svc.list_investigator_qualifications()
        statuses = {iq.qualification_status.value for iq in qualifications}
        assert "qualified" in statuses
        assert "not_qualified" in statuses
        assert "pending_review" in statuses

    def test_seed_capability_evaluations_have_gaps(self, svc: SiteFeasibilityService):
        evaluations = svc.list_capability_evaluations()
        not_meeting = [ce for ce in evaluations if not ce.meets_requirements]
        assert len(not_meeting) >= 3

    def test_seed_surveys_have_responded_and_pending(self, svc: SiteFeasibilityService):
        surveys = svc.list_feasibility_surveys()
        responded = [fs for fs in surveys if fs.response_date is not None]
        pending = [fs for fs in surveys if fs.response_date is None]
        assert len(responded) >= 5
        assert len(pending) >= 2


# =====================================================================
# SITE ASSESSMENT CRUD
# =====================================================================


class TestSiteAssessmentCrud:
    """Test site assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-assessments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-assessments/SA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SA-001"
        assert data["site_name"] == "Memorial Hermann Hospital"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-assessments/SA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/site-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "New Test Hospital"
        assert data["country"] == "United States"
        assert data["status"] == "planned"
        assert data["result"] == "pending"
        assert data["id"].startswith("SA-")

    @pytest.mark.anyio
    async def test_create_assessment_validation_error(self, client: AsyncClient):
        # Missing required fields
        resp = await client.post(f"{API_PREFIX}/site-assessments", json={"trial_id": "test"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-assessments/SA-001",
            json={"status": "in_progress", "overall_score": 88.0, "comments": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["overall_score"] == 88.0
        assert data["comments"] == "Updated"

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-assessments/SA-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-assessments/SA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-assessments/SA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-assessments/SA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INVESTIGATOR QUALIFICATION CRUD
# =====================================================================


class TestInvestigatorQualificationCrud:
    """Test investigator qualification CRUD operations."""

    @pytest.mark.anyio
    async def test_list_qualifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigator-qualifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_qualifications_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/investigator-qualifications",
            params={"trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_qualification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigator-qualifications/IQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IQ-001"
        assert data["investigator_name"] == "Dr. Robert Chen"

    @pytest.mark.anyio
    async def test_get_qualification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigator-qualifications/IQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_qualification(self, client: AsyncClient):
        payload = _make_investigator_create()
        resp = await client.post(f"{API_PREFIX}/investigator-qualifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["investigator_name"] == "Dr. Test Investigator"
        assert data["specialty"] == "Dermatology"
        assert data["qualification_status"] == "pending_review"
        assert data["id"].startswith("IQ-")

    @pytest.mark.anyio
    async def test_create_qualification_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/investigator-qualifications", json={"trial_id": "test"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_qualification(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/investigator-qualifications/IQ-004",
            json={
                "qualification_status": "qualified",
                "reviewed_by": "Test Reviewer",
                "financial_disclosure_complete": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualification_status"] == "qualified"
        assert data["reviewed_by"] == "Test Reviewer"
        assert data["financial_disclosure_complete"] is True

    @pytest.mark.anyio
    async def test_update_qualification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/investigator-qualifications/IQ-NONEXISTENT",
            json={"qualification_status": "qualified"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qualification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/investigator-qualifications/IQ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/investigator-qualifications/IQ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qualification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/investigator-qualifications/IQ-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PATIENT POOL ANALYSIS CRUD
# =====================================================================


class TestPatientPoolAnalysisCrud:
    """Test patient pool analysis CRUD operations."""

    @pytest.mark.anyio
    async def test_list_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patient-pool-analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_analyses_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patient-pool-analyses", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patient-pool-analyses/PPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PPA-001"
        assert "macular" in data["indication"].lower() or "amd" in data["indication"].lower()

    @pytest.mark.anyio
    async def test_get_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patient-pool-analyses/PPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_analysis(self, client: AsyncClient):
        payload = _make_patient_pool_create()
        resp = await client.post(f"{API_PREFIX}/patient-pool-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["indication"] == "Advanced CSCC"
        assert data["estimated_prevalence"] == 5000
        assert data["estimated_eligible"] == 300
        assert data["id"].startswith("PPA-")

    @pytest.mark.anyio
    async def test_create_analysis_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/patient-pool-analyses", json={"trial_id": "test"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patient-pool-analyses/PPA-001",
            json={
                "expected_enrollment": 50,
                "enrollment_rate_per_month": 5.0,
                "methodology_notes": "Updated analysis methodology",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["expected_enrollment"] == 50
        assert data["enrollment_rate_per_month"] == 5.0
        assert data["methodology_notes"] == "Updated analysis methodology"

    @pytest.mark.anyio
    async def test_update_analysis_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patient-pool-analyses/PPA-NONEXISTENT",
            json={"expected_enrollment": 10},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patient-pool-analyses/PPA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/patient-pool-analyses/PPA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patient-pool-analyses/PPA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CAPABILITY EVALUATION CRUD
# =====================================================================


class TestCapabilityEvaluationCrud:
    """Test capability evaluation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_evaluations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-evaluations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_evaluations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capability-evaluations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_evaluation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-evaluations/CE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CE-001"
        assert data["capability_area"] == "imaging"

    @pytest.mark.anyio
    async def test_get_evaluation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-evaluations/CE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_evaluation(self, client: AsyncClient):
        payload = _make_capability_create()
        resp = await client.post(f"{API_PREFIX}/capability-evaluations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["capability_area"] == "laboratory"
        assert data["score"] == 85.0
        assert data["meets_requirements"] is True
        assert data["id"].startswith("CE-")

    @pytest.mark.anyio
    async def test_create_evaluation_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/capability-evaluations", json={"trial_id": "test"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_evaluation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capability-evaluations/CE-004",
            json={
                "score": 80.0,
                "meets_requirements": True,
                "gap_description": "Resolved: staff hired",
                "remediation_plan": "Completed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 80.0
        assert data["meets_requirements"] is True
        assert data["gap_description"] == "Resolved: staff hired"

    @pytest.mark.anyio
    async def test_update_evaluation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capability-evaluations/CE-NONEXISTENT",
            json={"score": 50.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_evaluation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capability-evaluations/CE-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/capability-evaluations/CE-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_evaluation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capability-evaluations/CE-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FEASIBILITY SURVEY CRUD
# =====================================================================


class TestFeasibilitySurveyCrud:
    """Test feasibility survey CRUD operations."""

    @pytest.mark.anyio
    async def test_list_surveys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/feasibility-surveys")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_surveys_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/feasibility-surveys", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_survey(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/feasibility-surveys/FS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FS-001"
        assert "EYLEA" in data["survey_name"]

    @pytest.mark.anyio
    async def test_get_survey_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/feasibility-surveys/FS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_survey(self, client: AsyncClient):
        payload = _make_survey_create()
        resp = await client.post(f"{API_PREFIX}/feasibility-surveys", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["survey_name"] == "Test Feasibility Survey"
        assert data["total_questions"] == 40
        assert data["answered_questions"] == 0
        assert data["response_date"] is None
        assert data["id"].startswith("FS-")

    @pytest.mark.anyio
    async def test_create_survey_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/feasibility-surveys", json={"trial_id": "test"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_survey(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/feasibility-surveys/FS-010",
            json={
                "respondent": "Prof. Andrew Blackwood",
                "interest_level": "very_high",
                "estimated_enrollment": 60,
                "follow_up_required": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["respondent"] == "Prof. Andrew Blackwood"
        assert data["interest_level"] == "very_high"
        assert data["estimated_enrollment"] == 60
        assert data["follow_up_required"] is False

    @pytest.mark.anyio
    async def test_update_survey_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/feasibility-surveys/FS-NONEXISTENT",
            json={"interest_level": "low"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_survey(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/feasibility-surveys/FS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/feasibility-surveys/FS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_survey_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/feasibility-surveys/FS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestSiteFeasibilityMetrics:
    """Test site feasibility metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assessments"] == 12
        assert data["total_investigators"] == 12
        assert data["total_pool_analyses"] == 12
        assert data["total_evaluations"] == 12
        assert data["total_surveys"] == 12

    @pytest.mark.anyio
    async def test_metrics_avg_feasibility_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_feasibility_score"] > 0

    @pytest.mark.anyio
    async def test_metrics_qualified_investigators(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["qualified_investigators"] > 0
        assert data["qualified_investigators"] <= data["total_investigators"]

    @pytest.mark.anyio
    async def test_metrics_capabilities_meeting_requirements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["capabilities_meeting_requirements"] > 0
        assert data["capabilities_meeting_requirements"] <= data["total_evaluations"]

    @pytest.mark.anyio
    async def test_metrics_surveys_responded(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["surveys_responded"] > 0
        assert data["surveys_responded"] <= data["total_surveys"]

    @pytest.mark.anyio
    async def test_metrics_total_estimated_eligible(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_estimated_eligible"] > 0

    def test_metrics_assessments_by_status(self, svc: SiteFeasibilityService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.assessments_by_status.values())
        assert total_by_status == metrics.total_assessments

    def test_metrics_assessments_by_result(self, svc: SiteFeasibilityService):
        metrics = svc.get_metrics()
        total_by_result = sum(metrics.assessments_by_result.values())
        assert total_by_result == metrics.total_assessments

    def test_metrics_investigators_by_status(self, svc: SiteFeasibilityService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.investigators_by_status.values())
        assert total_by_status == metrics.total_investigators

    def test_metrics_evaluations_by_area(self, svc: SiteFeasibilityService):
        metrics = svc.get_metrics()
        total_by_area = sum(metrics.evaluations_by_area.values())
        assert total_by_area == metrics.total_evaluations


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_site_feasibility_service()
        svc2 = get_site_feasibility_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_site_feasibility_service()
        svc2 = reset_site_feasibility_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_feasibility_service()
        # Delete an assessment
        svc.delete_site_assessment("SA-001")
        assert svc.get_site_assessment("SA-001") is None
        # Reset should bring it back
        svc2 = reset_site_feasibility_service()
        assert svc2.get_site_assessment("SA-001") is not None


# =====================================================================
# LIST FILTERING
# =====================================================================


class TestListFiltering:
    """Test list filtering across all entity types."""

    @pytest.mark.anyio
    async def test_assessments_filter_returns_subset(self, client: AsyncClient):
        # Get all
        resp_all = await client.get(f"{API_PREFIX}/site-assessments")
        total = resp_all.json()["total"]
        # Get filtered
        resp_filtered = await client.get(
            f"{API_PREFIX}/site-assessments", params={"trial_id": EYLEA_TRIAL}
        )
        filtered_total = resp_filtered.json()["total"]
        assert 0 < filtered_total < total

    @pytest.mark.anyio
    async def test_investigators_filter_returns_subset(self, client: AsyncClient):
        resp_all = await client.get(f"{API_PREFIX}/investigator-qualifications")
        total = resp_all.json()["total"]
        resp_filtered = await client.get(
            f"{API_PREFIX}/investigator-qualifications",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        filtered_total = resp_filtered.json()["total"]
        assert 0 < filtered_total < total

    @pytest.mark.anyio
    async def test_patient_pool_filter_returns_subset(self, client: AsyncClient):
        resp_all = await client.get(f"{API_PREFIX}/patient-pool-analyses")
        total = resp_all.json()["total"]
        resp_filtered = await client.get(
            f"{API_PREFIX}/patient-pool-analyses", params={"trial_id": DUPIXENT_TRIAL}
        )
        filtered_total = resp_filtered.json()["total"]
        assert 0 < filtered_total < total

    @pytest.mark.anyio
    async def test_evaluations_filter_returns_subset(self, client: AsyncClient):
        resp_all = await client.get(f"{API_PREFIX}/capability-evaluations")
        total = resp_all.json()["total"]
        resp_filtered = await client.get(
            f"{API_PREFIX}/capability-evaluations", params={"trial_id": LIBTAYO_TRIAL}
        )
        filtered_total = resp_filtered.json()["total"]
        assert 0 < filtered_total < total

    @pytest.mark.anyio
    async def test_surveys_filter_returns_subset(self, client: AsyncClient):
        resp_all = await client.get(f"{API_PREFIX}/feasibility-surveys")
        total = resp_all.json()["total"]
        resp_filtered = await client.get(
            f"{API_PREFIX}/feasibility-surveys", params={"trial_id": EYLEA_TRIAL}
        )
        filtered_total = resp_filtered.json()["total"]
        assert 0 < filtered_total < total


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_all_entity_types_no_filters(self, client: AsyncClient):
        for endpoint in [
            "site-assessments",
            "investigator-qualifications",
            "patient-pool-analyses",
            "capability-evaluations",
            "feasibility-surveys",
        ]:
            resp = await client.get(f"{API_PREFIX}/{endpoint}")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data

    @pytest.mark.anyio
    async def test_filter_with_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-assessments",
            params={"trial_id": "nonexistent-trial-id"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_create_assessment_with_minimal_fields(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-MINIMAL",
            "site_name": "Minimal Site",
            "country": "Canada",
            "assessor": "Minimal Assessor",
        }
        resp = await client.post(f"{API_PREFIX}/site-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["enrollment_potential"] == 0
        assert data["region"] is None

    @pytest.mark.anyio
    async def test_create_capability_all_areas(self, client: AsyncClient):
        """Test creating capability evaluations for different areas."""
        for area in ["laboratory", "pharmacy", "imaging", "regulatory", "staff", "facilities", "it_systems", "patient_access"]:
            payload = _make_capability_create(capability_area=area)
            resp = await client.post(f"{API_PREFIX}/capability-evaluations", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["capability_area"] == area

    @pytest.mark.anyio
    async def test_create_and_immediately_read(self, client: AsyncClient):
        """Create an entity and immediately read it back."""
        payload = _make_assessment_create()
        create_resp = await client.post(f"{API_PREFIX}/site-assessments", json=payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        read_resp = await client.get(f"{API_PREFIX}/site-assessments/{created_id}")
        assert read_resp.status_code == 200
        assert read_resp.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_update_does_not_change_unset_fields(self, client: AsyncClient):
        """Updating with partial data should not erase unset fields."""
        # Read original
        resp = await client.get(f"{API_PREFIX}/site-assessments/SA-001")
        original = resp.json()
        original_site_name = original["site_name"]

        # Update only comments
        resp2 = await client.put(
            f"{API_PREFIX}/site-assessments/SA-001",
            json={"comments": "Partial update test"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["comments"] == "Partial update test"
        assert updated["site_name"] == original_site_name

    @pytest.mark.anyio
    async def test_delete_then_create_new(self, client: AsyncClient):
        """Delete an entity then create a new one to verify store integrity."""
        # Delete
        resp = await client.delete(f"{API_PREFIX}/site-assessments/SA-001")
        assert resp.status_code == 204

        # Verify count decreased
        resp2 = await client.get(f"{API_PREFIX}/site-assessments")
        assert resp2.json()["total"] == 11

        # Create new
        payload = _make_assessment_create()
        resp3 = await client.post(f"{API_PREFIX}/site-assessments", json=payload)
        assert resp3.status_code == 201

        # Verify count restored
        resp4 = await client.get(f"{API_PREFIX}/site-assessments")
        assert resp4.json()["total"] == 12

    @pytest.mark.anyio
    async def test_metrics_after_deletion(self, client: AsyncClient):
        """Metrics should reflect deletions."""
        # Delete one assessment
        await client.delete(f"{API_PREFIX}/site-assessments/SA-001")

        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_assessments"] == 11

    @pytest.mark.anyio
    async def test_metrics_after_creation(self, client: AsyncClient):
        """Metrics should reflect new creations."""
        payload = _make_survey_create()
        await client.post(f"{API_PREFIX}/feasibility-surveys", json=payload)

        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_surveys"] == 13
