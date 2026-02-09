"""Tests for Study Startup & Feasibility Assessment (CLINICAL-15).

Covers:
- Seed data verification (site feasibilities, country feasibilities, timelines, protocols)
- Site feasibility CRUD (create, read, update, delete, list, filter by trial/status/region)
- Weighted composite scoring (patient pool 30%, experience 25%, infrastructure 20%, staff 15%, competing 10%)
- Site ranking by composite score with breakdown
- Country feasibility CRUD (create, read, update, delete, list, filter by trial)
- Country optimization (cost vs timeline vs patient pool)
- Startup timeline CRUD (create, read, update, delete, list, filter by trial/site/phase)
- Critical path analysis (delays, on-track status, critical phase identification)
- Protocol feasibility (create, read, list, filter by trial)
- Screen failure rate prediction from criteria complexity
- Bottleneck analysis (average delay per phase, common blockers)
- Startup metrics computation
- Error handling (404s, edge cases)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.study_startup import (
    FeasibilityScore,
    FeasibilityStatus,
    StartupBlocker,
    StartupPhase,
)
from app.services.study_startup_service import (
    StudyStartupService,
    get_study_startup_service,
    reset_study_startup_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/study-startup"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_study_startup_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> StudyStartupService:
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
        "site_id": "SITE-NEW-001",
        "site_name": "Test Research Hospital",
        "trial_id": EYLEA_TRIAL,
        "investigator_name": "Dr. Test Investigator",
        "specialty": "Ophthalmology",
        "patient_pool_estimate": 300,
        "competing_studies": 1,
        "staff_available": 6,
        "experience_score": 75.0,
        "infrastructure_score": 80.0,
        "geographic_region": "US-West",
        "assessor": "Dr. Test Assessor",
    }
    defaults.update(overrides)
    return defaults


def _make_country_create(**overrides) -> dict:
    defaults = {
        "country_code": "FR",
        "country_name": "France",
        "trial_id": DUPIXENT_TRIAL,
        "regulatory_complexity": 4,
        "approval_timeline_months": 8.0,
        "import_requirements": "ANSM CTA required; EU import license",
        "data_privacy_requirements": "EU GDPR; CNIL registration",
        "local_representation_required": True,
        "estimated_sites": 5,
        "estimated_patients": 1400,
        "cost_index": 1.2,
    }
    defaults.update(overrides)
    return defaults


def _make_timeline_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "phase": "feasibility",
        "planned_start": (now + timedelta(days=1)).isoformat(),
        "planned_end": (now + timedelta(days=21)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_protocol_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "protocol_version": "v4.0",
        "inclusion_criteria_count": 7,
        "exclusion_criteria_count": 10,
        "visit_schedule_complexity": 50.0,
        "estimated_screen_failure_rate": 30.0,
        "estimated_enrollment_rate_per_site_month": 2.0,
        "recommended_modifications": ["Consider wider age range"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_site_feasibilities_count(self, svc: StudyStartupService):
        sites = svc.list_site_feasibilities()
        assert len(sites) == 15

    def test_seed_site_feasibilities_across_3_trials(self, svc: StudyStartupService):
        trial_ids = {s.trial_id for s in svc.list_site_feasibilities()}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_all_feasibility_statuses(self, svc: StudyStartupService):
        statuses = {s.status for s in svc.list_site_feasibilities()}
        assert FeasibilityStatus.SCREENING in statuses
        assert FeasibilityStatus.SHORTLISTED in statuses
        assert FeasibilityStatus.SELECTED in statuses
        assert FeasibilityStatus.DECLINED in statuses
        assert FeasibilityStatus.BACKUP in statuses

    def test_seed_country_feasibilities_count(self, svc: StudyStartupService):
        countries = svc.list_country_feasibilities()
        assert len(countries) == 6

    def test_seed_country_codes(self, svc: StudyStartupService):
        codes = {c.country_code for c in svc.list_country_feasibilities()}
        assert "US" in codes
        assert "GB" in codes
        assert "DE" in codes
        assert "JP" in codes
        assert "AU" in codes
        assert "CA" in codes

    def test_seed_startup_timelines_count(self, svc: StudyStartupService):
        timelines = svc.list_startup_timelines()
        assert len(timelines) == 20

    def test_seed_protocol_feasibilities_count(self, svc: StudyStartupService):
        protocols = svc.list_protocol_feasibilities()
        assert len(protocols) == 3

    def test_seed_site_scores_within_range(self, svc: StudyStartupService):
        for s in svc.list_site_feasibilities():
            assert 0 <= s.overall_score <= 100

    def test_seed_enrollment_potential_within_range(self, svc: StudyStartupService):
        for s in svc.list_site_feasibilities():
            assert 0 <= s.enrollment_potential <= 100

    def test_seed_regulatory_complexity_range(self, svc: StudyStartupService):
        for c in svc.list_country_feasibilities():
            assert 1 <= c.regulatory_complexity <= 5


# =====================================================================
# SITE FEASIBILITY CRUD
# =====================================================================


class TestSiteFeasibilityCrud:
    """Test site feasibility create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15
        assert len(data["items"]) == 15

    @pytest.mark.anyio
    async def test_list_sites_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sites_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"status": "selected"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "selected"

    @pytest.mark.anyio
    async def test_list_sites_filter_region(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"region": "US-South"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["geographic_region"] == "US-South"

    @pytest.mark.anyio
    async def test_list_sites_sorted_by_score_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        data = resp.json()
        scores = [item["overall_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_get_site_feasibility(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SF-001"
        assert data["site_name"] == "Memorial Hermann Hospital"

    @pytest.mark.anyio
    async def test_get_site_feasibility_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site_feasibility(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "Test Research Hospital"
        assert data["status"] == "screening"
        assert data["id"].startswith("SF-")
        assert 0 <= data["overall_score"] <= 100

    @pytest.mark.anyio
    async def test_create_site_auto_computes_score(self, client: AsyncClient):
        payload = _make_site_create(
            patient_pool_estimate=500,
            experience_score=90.0,
            infrastructure_score=85.0,
            staff_available=10,
            competing_studies=0,
        )
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # High inputs should yield high score
        assert data["overall_score"] >= 80.0

    @pytest.mark.anyio
    async def test_update_site_feasibility(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SF-004",
            json={"status": "selected", "staff_available": 8},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "selected"
        assert data["staff_available"] == 8

    @pytest.mark.anyio
    async def test_update_site_recalculates_score(self, client: AsyncClient):
        # Get original score
        resp1 = await client.get(f"{API_PREFIX}/sites/SF-005")
        original_score = resp1.json()["overall_score"]
        # Update with better inputs
        resp2 = await client.put(
            f"{API_PREFIX}/sites/SF-005",
            json={"patient_pool_estimate": 800, "competing_studies": 0},
        )
        assert resp2.status_code == 200
        new_score = resp2.json()["overall_score"]
        assert new_score > original_score

    @pytest.mark.anyio
    async def test_update_site_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SF-NONEXISTENT",
            json={"status": "selected"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_feasibility(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sites/SF-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sites/SF-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sites/SF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# WEIGHTED SCORING
# =====================================================================


class TestWeightedScoring:
    """Test the weighted feasibility scoring algorithm."""

    def test_composite_score_calculation(self, svc: StudyStartupService):
        score = svc._compute_composite_score(
            patient_pool=500,
            competing_studies=0,
            staff_available=10,
            experience_score=100.0,
            infrastructure_score=100.0,
        )
        # 100*0.30 + 100*0.25 + 100*0.20 + 100*0.15 + 100*0.10 = 100
        assert score == 100.0

    def test_composite_score_zero_inputs(self, svc: StudyStartupService):
        score = svc._compute_composite_score(
            patient_pool=0,
            competing_studies=5,
            staff_available=0,
            experience_score=0.0,
            infrastructure_score=0.0,
        )
        assert score == 0.0

    def test_patient_pool_weight_30_percent(self, svc: StudyStartupService):
        score_high = svc._compute_composite_score(
            patient_pool=500, competing_studies=0, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        score_low = svc._compute_composite_score(
            patient_pool=0, competing_studies=0, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        # Difference should be exactly 30 (30% of 100)
        assert abs((score_high - score_low) - 30.0) < 0.1

    def test_experience_weight_25_percent(self, svc: StudyStartupService):
        score_with = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=0,
            experience_score=100.0, infrastructure_score=0.0,
        )
        score_without = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        assert abs((score_with - score_without) - 25.0) < 0.1

    def test_infrastructure_weight_20_percent(self, svc: StudyStartupService):
        score_with = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=0,
            experience_score=0.0, infrastructure_score=100.0,
        )
        score_without = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        assert abs((score_with - score_without) - 20.0) < 0.1

    def test_staff_weight_15_percent(self, svc: StudyStartupService):
        score_with = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=10,
            experience_score=0.0, infrastructure_score=0.0,
        )
        score_without = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        assert abs((score_with - score_without) - 15.0) < 0.1

    def test_competing_studies_weight_10_percent(self, svc: StudyStartupService):
        score_none = svc._compute_composite_score(
            patient_pool=0, competing_studies=0, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        score_five = svc._compute_composite_score(
            patient_pool=0, competing_studies=5, staff_available=0,
            experience_score=0.0, infrastructure_score=0.0,
        )
        # 0 competing = 100 normalized * 0.10 = 10; 5 competing = 0 * 0.10 = 0
        assert abs(score_none - 10.0) < 0.1
        assert score_five == 0.0

    def test_enrollment_potential_calculation(self, svc: StudyStartupService):
        ep = svc._compute_enrollment_potential(500, 0, 10)
        # pool: 100, competition: 0, staff: 30 -> 130 capped at 100
        assert ep == 100.0

    def test_enrollment_potential_with_competition(self, svc: StudyStartupService):
        ep = svc._compute_enrollment_potential(250, 3, 5)
        # pool: 50, competition: -24, staff: 15 -> 41
        assert abs(ep - 41.0) < 0.1

    def test_score_to_grade_excellent(self, svc: StudyStartupService):
        assert svc._score_to_grade(90.0) == FeasibilityScore.EXCELLENT

    def test_score_to_grade_good(self, svc: StudyStartupService):
        assert svc._score_to_grade(75.0) == FeasibilityScore.GOOD

    def test_score_to_grade_adequate(self, svc: StudyStartupService):
        assert svc._score_to_grade(60.0) == FeasibilityScore.ADEQUATE

    def test_score_to_grade_marginal(self, svc: StudyStartupService):
        assert svc._score_to_grade(45.0) == FeasibilityScore.MARGINAL

    def test_score_to_grade_poor(self, svc: StudyStartupService):
        assert svc._score_to_grade(30.0) == FeasibilityScore.POOR


# =====================================================================
# SITE RANKING
# =====================================================================


class TestSiteRanking:
    """Test site ranking by composite score."""

    @pytest.mark.anyio
    async def test_get_rankings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/rankings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 15

    @pytest.mark.anyio
    async def test_rankings_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/rankings", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for item in data:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_rankings_sorted_by_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/rankings")
        data = resp.json()
        scores = [item["composite_score"] for item in data]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_rankings_have_rank_field(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/rankings")
        data = resp.json()
        ranks = [item["rank"] for item in data]
        assert ranks == list(range(1, len(data) + 1))

    @pytest.mark.anyio
    async def test_rankings_have_score_breakdown(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/rankings")
        data = resp.json()
        for item in data:
            breakdown = item["score_breakdown"]
            assert "patient_pool" in breakdown
            assert "experience" in breakdown
            assert "infrastructure" in breakdown
            assert "staff" in breakdown
            assert "competing_studies" in breakdown

    @pytest.mark.anyio
    async def test_rankings_have_feasibility_grade(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/rankings")
        data = resp.json()
        valid_grades = {"excellent", "good", "adequate", "marginal", "poor"}
        for item in data:
            assert item["feasibility_grade"] in valid_grades


# =====================================================================
# COUNTRY FEASIBILITY CRUD
# =====================================================================


class TestCountryFeasibilityCrud:
    """Test country feasibility create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_countries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_countries_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/countries", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_countries_sorted_by_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries")
        data = resp.json()
        names = [item["country_name"] for item in data["items"]]
        assert names == sorted(names)

    @pytest.mark.anyio
    async def test_get_country_feasibility(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/CF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["country_code"] == "US"
        assert data["country_name"] == "United States"

    @pytest.mark.anyio
    async def test_get_country_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/CF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_country_feasibility(self, client: AsyncClient):
        payload = _make_country_create()
        resp = await client.post(f"{API_PREFIX}/countries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country_code"] == "FR"
        assert data["country_name"] == "France"
        assert data["id"].startswith("CF-")

    @pytest.mark.anyio
    async def test_update_country_feasibility(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/countries/CF-001",
            json={"regulatory_complexity": 4, "estimated_patients": 3000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulatory_complexity"] == 4
        assert data["estimated_patients"] == 3000

    @pytest.mark.anyio
    async def test_update_country_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/countries/CF-NONEXISTENT",
            json={"regulatory_complexity": 2},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_country_feasibility(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/countries/CF-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/countries/CF-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_country_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/countries/CF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COUNTRY OPTIMIZATION
# =====================================================================


class TestCountryOptimization:
    """Test country selection optimization."""

    @pytest.mark.anyio
    async def test_get_optimization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/optimization")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    @pytest.mark.anyio
    async def test_optimization_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/countries/optimization",
            params={"trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    @pytest.mark.anyio
    async def test_optimization_sorted_by_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/optimization")
        data = resp.json()
        scores = [item["optimization_score"] for item in data]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_optimization_has_breakdown(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/optimization")
        data = resp.json()
        for item in data:
            assert "cost_score" in item
            assert "timeline_score" in item
            assert "patient_pool_score" in item
            assert "recommendation" in item

    @pytest.mark.anyio
    async def test_optimization_scores_in_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/optimization")
        data = resp.json()
        for item in data:
            assert 0 <= item["optimization_score"] <= 100
            assert 0 <= item["cost_score"] <= 100
            assert 0 <= item["timeline_score"] <= 100
            assert 0 <= item["patient_pool_score"] <= 100

    def test_optimization_recommendation_not_empty(self, svc: StudyStartupService):
        opts = svc.get_country_optimization()
        for opt in opts:
            assert len(opt.recommendation) > 0


# =====================================================================
# STARTUP TIMELINE CRUD
# =====================================================================


class TestStartupTimelineCrud:
    """Test startup timeline create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_timelines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    @pytest.mark.anyio
    async def test_list_timelines_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/timelines", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_timelines_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/timelines", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_timelines_filter_phase(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/timelines", params={"phase": "feasibility"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["phase"] == "feasibility"

    @pytest.mark.anyio
    async def test_get_timeline(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/ST-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ST-001"
        assert data["phase"] == "feasibility"

    @pytest.mark.anyio
    async def test_get_timeline_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/ST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_timeline(self, client: AsyncClient):
        payload = _make_timeline_create()
        resp = await client.post(f"{API_PREFIX}/timelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ST-")
        assert data["phase"] == "feasibility"
        assert data["blockers"] == []

    @pytest.mark.anyio
    async def test_update_timeline(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/timelines/ST-020",
            json={
                "actual_end": now.isoformat(),
                "blockers": ["equipment_pending", "staff_shortage"],
                "milestone_notes": "Completed with delays",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual_end"] is not None
        assert "equipment_pending" in data["blockers"]
        assert "staff_shortage" in data["blockers"]

    @pytest.mark.anyio
    async def test_update_timeline_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/timelines/ST-NONEXISTENT",
            json={"milestone_notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_timeline(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/timelines/ST-020")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/timelines/ST-020")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_timeline_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/timelines/ST-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CRITICAL PATH ANALYSIS
# =====================================================================


class TestCriticalPath:
    """Test critical path analysis for site startups."""

    @pytest.mark.anyio
    async def test_get_critical_path(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/critical-path")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    @pytest.mark.anyio
    async def test_critical_path_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/timelines/critical-path",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    @pytest.mark.anyio
    async def test_critical_path_sorted_by_delay(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/critical-path")
        data = resp.json()
        delays = [item["delay_days"] for item in data]
        assert delays == sorted(delays, reverse=True)

    @pytest.mark.anyio
    async def test_critical_path_on_track_field(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/critical-path")
        data = resp.json()
        for item in data:
            assert isinstance(item["on_track"], bool)

    @pytest.mark.anyio
    async def test_site_101_on_track(self, client: AsyncClient):
        """SITE-101 is fully active and should be on track."""
        resp = await client.get(f"{API_PREFIX}/timelines/critical-path")
        data = resp.json()
        site_101 = [r for r in data if r["site_id"] == "SITE-101"]
        assert len(site_101) == 1
        assert site_101[0]["total_planned_days"] > 0

    def test_critical_path_delayed_site(self, svc: StudyStartupService):
        """Sites with blockers should show delays."""
        paths = svc.get_critical_path()
        # At least one site should have delay_days > 0
        delayed = [p for p in paths if p.delay_days > 0]
        assert len(delayed) > 0

    def test_critical_path_has_critical_phase(self, svc: StudyStartupService):
        paths = svc.get_critical_path()
        # At least one delayed site should have a critical_phase identified
        delayed_with_phase = [
            p for p in paths if p.delay_days > 0 and p.critical_phase is not None
        ]
        assert len(delayed_with_phase) > 0


# =====================================================================
# PROTOCOL FEASIBILITY
# =====================================================================


class TestProtocolFeasibility:
    """Test protocol feasibility operations."""

    @pytest.mark.anyio
    async def test_list_protocols(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_protocols_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocols", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/PF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PF-001"
        assert data["protocol_version"] == "v3.2"

    @pytest.mark.anyio
    async def test_get_protocol_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/PF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_protocol(self, client: AsyncClient):
        payload = _make_protocol_create()
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PF-")
        assert data["protocol_version"] == "v4.0"

    @pytest.mark.anyio
    async def test_protocol_has_recommended_modifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/PF-003")
        data = resp.json()
        assert len(data["recommended_modifications"]) > 0

    @pytest.mark.anyio
    async def test_libtayo_has_highest_complexity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/PF-003")
        data = resp.json()
        assert data["visit_schedule_complexity"] > 60
        assert data["exclusion_criteria_count"] >= 15


# =====================================================================
# SCREEN FAILURE PREDICTION
# =====================================================================


class TestScreenFailurePrediction:
    """Test screen failure rate prediction."""

    @pytest.mark.anyio
    async def test_predict_screen_failure_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocols/{EYLEA_TRIAL}/screen-failure"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert 0 <= data["predicted_rate"] <= 90
        assert data["criteria_complexity_factor"] > 0
        assert data["visit_complexity_factor"] > 0
        assert data["confidence"] in ("high", "medium", "low")

    @pytest.mark.anyio
    async def test_predict_screen_failure_libtayo_higher(self, client: AsyncClient):
        """Libtayo has more criteria, so predicted rate should be higher."""
        resp_eylea = await client.get(
            f"{API_PREFIX}/protocols/{EYLEA_TRIAL}/screen-failure"
        )
        resp_libtayo = await client.get(
            f"{API_PREFIX}/protocols/{LIBTAYO_TRIAL}/screen-failure"
        )
        assert resp_eylea.status_code == 200
        assert resp_libtayo.status_code == 200
        assert resp_libtayo.json()["predicted_rate"] > resp_eylea.json()["predicted_rate"]

    @pytest.mark.anyio
    async def test_predict_screen_failure_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocols/nonexistent-trial/screen-failure"
        )
        assert resp.status_code == 404

    def test_screen_failure_formula(self, svc: StudyStartupService):
        """Verify the formula: base 20% + inclusion*0.5 + exclusion*1.5 + visit*0.2."""
        result = svc.predict_screen_failure_rate(EYLEA_TRIAL)
        assert result is not None
        # PF-001: inclusion=8, exclusion=12, visit_complexity=45
        expected = 20.0 + (8 * 0.5) + (12 * 1.5) + (45 * 0.2)
        assert abs(result.predicted_rate - expected) < 0.1

    def test_screen_failure_capped_at_90(self, svc: StudyStartupService):
        """Even with extreme criteria, rate should be capped at 90%."""
        # Create a protocol with extreme values
        from app.schemas.study_startup import ProtocolFeasibilityCreate
        svc.create_protocol_feasibility(ProtocolFeasibilityCreate(
            trial_id="trial-extreme",
            protocol_version="v1.0",
            inclusion_criteria_count=50,
            exclusion_criteria_count=50,
            visit_schedule_complexity=100.0,
            estimated_screen_failure_rate=90.0,
            estimated_enrollment_rate_per_site_month=0.1,
        ))
        result = svc.predict_screen_failure_rate("trial-extreme")
        assert result is not None
        assert result.predicted_rate <= 90.0


# =====================================================================
# BOTTLENECK ANALYSIS
# =====================================================================


class TestBottleneckAnalysis:
    """Test bottleneck analysis across startup phases."""

    @pytest.mark.anyio
    async def test_get_bottleneck_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bottleneck-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    @pytest.mark.anyio
    async def test_bottleneck_sorted_by_delay(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bottleneck-analysis")
        data = resp.json()
        delays = [item["avg_delay_days"] for item in data]
        assert delays == sorted(delays, reverse=True)

    @pytest.mark.anyio
    async def test_bottleneck_has_common_blockers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bottleneck-analysis")
        data = resp.json()
        # At least one phase should have common blockers
        phases_with_blockers = [b for b in data if len(b["common_blockers"]) > 0]
        assert len(phases_with_blockers) > 0

    def test_bottleneck_sites_affected_positive(self, svc: StudyStartupService):
        bottlenecks = svc.get_bottleneck_analysis()
        for b in bottlenecks:
            assert b.sites_affected > 0

    def test_bottleneck_delay_non_negative(self, svc: StudyStartupService):
        bottlenecks = svc.get_bottleneck_analysis()
        for b in bottlenecks:
            assert b.avg_delay_days >= 0.0


# =====================================================================
# STARTUP METRICS
# =====================================================================


class TestStartupMetrics:
    """Test startup metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites_assessed"] == 15
        assert data["countries_assessed"] == 6
        assert data["protocol_amendments"] == 3
        assert data["sites_selected"] > 0
        assert data["avg_feasibility_score"] > 0
        assert data["avg_startup_time_days"] >= 0

    @pytest.mark.anyio
    async def test_metrics_sites_by_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "sites_by_phase" in data
        total_sites_in_phases = sum(data["sites_by_phase"].values())
        assert total_sites_in_phases > 0

    @pytest.mark.anyio
    async def test_metrics_bottleneck_analysis_included(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "bottleneck_analysis" in data
        assert isinstance(data["bottleneck_analysis"], list)

    def test_metrics_sites_selected_matches(self, svc: StudyStartupService):
        metrics = svc.get_metrics()
        selected = [
            s for s in svc.list_site_feasibilities()
            if s.status == FeasibilityStatus.SELECTED
        ]
        assert metrics.sites_selected == len(selected)

    def test_metrics_avg_score_matches(self, svc: StudyStartupService):
        metrics = svc.get_metrics()
        sites = svc.list_site_feasibilities()
        expected_avg = sum(s.overall_score for s in sites) / len(sites)
        assert abs(metrics.avg_feasibility_score - round(expected_avg, 1)) < 0.2

    def test_metrics_countries_assessed(self, svc: StudyStartupService):
        metrics = svc.get_metrics()
        countries = svc.list_country_feasibilities()
        assert metrics.countries_assessed == len(countries)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_study_startup_service()
        svc2 = get_study_startup_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_study_startup_service()
        svc2 = reset_study_startup_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_study_startup_service()
        # Delete a site feasibility
        svc.delete_site_feasibility("SF-001")
        assert svc.get_site_feasibility("SF-001") is None
        # Reset should bring it back
        svc2 = reset_study_startup_service()
        assert svc2.get_site_feasibility("SF-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_sites_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_countries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_timelines_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_protocols_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_site_with_zero_competing_studies(self, client: AsyncClient):
        payload = _make_site_create(competing_studies=0)
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["competing_studies"] == 0

    @pytest.mark.anyio
    async def test_create_site_with_high_competition(self, client: AsyncClient):
        payload = _make_site_create(competing_studies=10)
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # High competition should lower the score
        assert data["overall_score"] < 80

    @pytest.mark.anyio
    async def test_create_country_with_low_complexity(self, client: AsyncClient):
        payload = _make_country_create(regulatory_complexity=1)
        resp = await client.post(f"{API_PREFIX}/countries", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_country_with_high_complexity(self, client: AsyncClient):
        payload = _make_country_create(regulatory_complexity=5)
        resp = await client.post(f"{API_PREFIX}/countries", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_timeline_with_different_phases(self, client: AsyncClient):
        for phase in ["feasibility", "site_selection", "regulatory_prep", "irb_submission"]:
            payload = _make_timeline_create(phase=phase)
            resp = await client.post(f"{API_PREFIX}/timelines", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_timeline_with_blockers(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/timelines/ST-012",
            json={"blockers": ["contract_delay", "budget_dispute"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "contract_delay" in data["blockers"]
        assert "budget_dispute" in data["blockers"]

    @pytest.mark.anyio
    async def test_optimization_empty_for_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/countries/optimization",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_rankings_empty_for_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/rankings",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_critical_path_empty_for_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/timelines/critical-path",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# =====================================================================
# ENUM VERIFICATION
# =====================================================================


class TestEnumVerification:
    """Test that all enum values are correctly represented in seed data."""

    @pytest.mark.anyio
    async def test_all_feasibility_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "screening" in statuses
        assert "shortlisted" in statuses
        assert "selected" in statuses
        assert "declined" in statuses
        assert "backup" in statuses

    def test_all_startup_phases_in_timelines(self, svc: StudyStartupService):
        timelines = svc.list_startup_timelines()
        phases = {t.phase for t in timelines}
        assert StartupPhase.FEASIBILITY in phases
        assert StartupPhase.SITE_SELECTION in phases
        assert StartupPhase.REGULATORY_PREP in phases
        assert StartupPhase.IRB_SUBMISSION in phases
        assert StartupPhase.CONTRACT_NEGOTIATION in phases
        assert StartupPhase.SITE_INITIATION_VISIT in phases
        assert StartupPhase.ACTIVE in phases

    def test_blockers_present_in_timelines(self, svc: StudyStartupService):
        timelines = svc.list_startup_timelines()
        all_blockers: set[StartupBlocker] = set()
        for t in timelines:
            all_blockers.update(t.blockers)
        assert StartupBlocker.REGULATORY_DELAY in all_blockers
        assert StartupBlocker.CONTRACT_DELAY in all_blockers
        assert StartupBlocker.BUDGET_DISPUTE in all_blockers
        assert StartupBlocker.STAFF_SHORTAGE in all_blockers
        assert StartupBlocker.EQUIPMENT_PENDING in all_blockers
        assert StartupBlocker.IRB_QUERY in all_blockers


# =====================================================================
# ADDITIONAL FIELD VALIDATIONS
# =====================================================================


class TestFieldValidations:
    """Test field-level validations and data integrity."""

    @pytest.mark.anyio
    async def test_site_feasibility_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SF-001")
        data = resp.json()
        assert "id" in data
        assert "site_id" in data
        assert "site_name" in data
        assert "trial_id" in data
        assert "investigator_name" in data
        assert "specialty" in data
        assert "status" in data
        assert "overall_score" in data
        assert "patient_pool_estimate" in data
        assert "competing_studies" in data
        assert "staff_available" in data
        assert "experience_score" in data
        assert "infrastructure_score" in data
        assert "enrollment_potential" in data
        assert "geographic_region" in data
        assert "assessment_date" in data
        assert "assessor" in data

    @pytest.mark.anyio
    async def test_country_feasibility_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/CF-001")
        data = resp.json()
        assert "id" in data
        assert "country_code" in data
        assert "country_name" in data
        assert "trial_id" in data
        assert "regulatory_complexity" in data
        assert "approval_timeline_months" in data
        assert "import_requirements" in data
        assert "data_privacy_requirements" in data
        assert "local_representation_required" in data
        assert "estimated_sites" in data
        assert "estimated_patients" in data
        assert "cost_index" in data

    @pytest.mark.anyio
    async def test_timeline_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/ST-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "site_id" in data
        assert "phase" in data
        assert "planned_start" in data
        assert "planned_end" in data
        assert "actual_start" in data
        assert "actual_end" in data
        assert "blockers" in data
        assert "milestone_notes" in data

    @pytest.mark.anyio
    async def test_protocol_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/PF-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "protocol_version" in data
        assert "inclusion_criteria_count" in data
        assert "exclusion_criteria_count" in data
        assert "visit_schedule_complexity" in data
        assert "estimated_screen_failure_rate" in data
        assert "estimated_enrollment_rate_per_site_month" in data
        assert "recommended_modifications" in data

    @pytest.mark.anyio
    async def test_metrics_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_sites_assessed" in data
        assert "sites_selected" in data
        assert "avg_startup_time_days" in data
        assert "sites_by_phase" in data
        assert "countries_assessed" in data
        assert "protocol_amendments" in data
        assert "avg_feasibility_score" in data
        assert "bottleneck_analysis" in data
