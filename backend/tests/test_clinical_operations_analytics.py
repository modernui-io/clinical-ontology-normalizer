"""Tests for Clinical Operations Analytics (COA).

Covers:
- Seed data verification (enrollment velocities, site performance scorecards,
  protocol deviation trends, resource utilizations, milestone achievements)
- Enrollment velocity CRUD (create, read, update, delete, list, filter by trial/trend)
- Site performance scorecard CRUD (create, read, update, delete, list, filter by trial/tier)
- Protocol deviation trend CRUD (create, read, update, delete, list, filter by trial/category)
- Resource utilization CRUD (create, read, update, delete, list, filter by trial/type)
- Milestone achievement CRUD (create, read, update, delete, list, filter by trial/category)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_operations_analytics import (
    VelocityTrend,
    PerformanceTier,
    DeviationCategory,
    ResourceType,
    MilestoneCategory,
)
from app.services.clinical_operations_analytics_service import (
    ClinicalOperationsAnalyticsService,
    get_clinical_operations_analytics_service,
    reset_clinical_operations_analytics_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-operations-analytics"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_operations_analytics_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalOperationsAnalyticsService:
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


def _make_enrollment_velocity_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "period_days": 30,
        "patients_enrolled": 15,
        "patients_screened": 25,
        "target_enrollment": 200,
        "analyzed_by": "Dr. Test Analyst",
    }
    defaults.update(overrides)
    return defaults


def _make_site_performance_scorecard_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "site_name": "Test Clinical Site",
        "enrollment_score": 75.0,
        "data_quality_score": 80.0,
        "evaluated_by": "Dr. Test Evaluator",
    }
    defaults.update(overrides)
    return defaults


def _make_protocol_deviation_trend_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "reporting_period": "2025-Q3",
        "deviation_category": "informed_consent",
        "total_deviations": 10,
        "major_deviations": 2,
        "analyzed_by": "Dr. Test Analyst",
    }
    defaults.update(overrides)
    return defaults


def _make_resource_utilization_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "resource_type": "cra",
        "reporting_period": "2025-Q3",
        "total_fte_allocated": 10.0,
        "total_fte_utilized": 8.5,
        "managed_by": "Dr. Test Manager",
    }
    defaults.update(overrides)
    return defaults


def _make_milestone_achievement_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "milestone_name": "Test Milestone",
        "milestone_category": "enrollment",
        "planned_date": "2025-06-30T00:00:00Z",
        "owner": "Dr. Test Owner",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    # --- Enrollment Velocities ---

    def test_seed_enrollment_velocities_count(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_enrollment_velocities()
        assert len(items) == 12

    def test_seed_enrollment_velocity_ids(self, svc: ClinicalOperationsAnalyticsService):
        for i in range(1, 11):
            ev = svc.get_enrollment_velocity(f"EV-{i:03d}")
            assert ev is not None

    def test_seed_enrollment_velocity_ev001(self, svc: ClinicalOperationsAnalyticsService):
        ev = svc.get_enrollment_velocity("EV-001")
        assert ev is not None
        assert ev.trial_id == EYLEA_TRIAL
        assert ev.velocity_trend == VelocityTrend.ACCELERATING

    def test_seed_enrollment_velocity_ev005(self, svc: ClinicalOperationsAnalyticsService):
        ev = svc.get_enrollment_velocity("EV-005")
        assert ev is not None
        assert ev.trial_id == DUPIXENT_TRIAL
        assert ev.velocity_trend == VelocityTrend.DECELERATING

    def test_seed_enrollment_velocity_ev010(self, svc: ClinicalOperationsAnalyticsService):
        ev = svc.get_enrollment_velocity("EV-010")
        assert ev is not None
        assert ev.trial_id == LIBTAYO_TRIAL
        assert ev.velocity_trend == VelocityTrend.STALLED

    def test_seed_enrollment_velocity_trends_present(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_enrollment_velocities()
        trends = {v.velocity_trend for v in items}
        assert VelocityTrend.ACCELERATING in trends
        assert VelocityTrend.STEADY in trends
        assert VelocityTrend.DECELERATING in trends
        assert VelocityTrend.RECOVERING in trends
        assert VelocityTrend.STALLED in trends

    # --- Site Performance Scorecards ---

    def test_seed_scorecards_count(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_site_performance_scorecards()
        assert len(items) == 12

    def test_seed_scorecard_ids(self, svc: ClinicalOperationsAnalyticsService):
        for i in range(1, 13):
            sc = svc.get_site_performance_scorecard(f"SPS-{i:03d}")
            assert sc is not None

    def test_seed_scorecard_sps001(self, svc: ClinicalOperationsAnalyticsService):
        sc = svc.get_site_performance_scorecard("SPS-001")
        assert sc is not None
        assert sc.trial_id == EYLEA_TRIAL
        assert sc.performance_tier == PerformanceTier.TOP_PERFORMER

    def test_seed_scorecard_sps007(self, svc: ClinicalOperationsAnalyticsService):
        sc = svc.get_site_performance_scorecard("SPS-007")
        assert sc is not None
        assert sc.trial_id == DUPIXENT_TRIAL
        assert sc.performance_tier == PerformanceTier.UNDERPERFORMING

    def test_seed_scorecard_sps008(self, svc: ClinicalOperationsAnalyticsService):
        sc = svc.get_site_performance_scorecard("SPS-008")
        assert sc is not None
        assert sc.performance_tier == PerformanceTier.NEW_SITE

    def test_seed_scorecard_tiers_present(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_site_performance_scorecards()
        tiers = {s.performance_tier for s in items}
        assert PerformanceTier.TOP_PERFORMER in tiers
        assert PerformanceTier.ABOVE_AVERAGE in tiers
        assert PerformanceTier.AVERAGE in tiers
        assert PerformanceTier.BELOW_AVERAGE in tiers
        assert PerformanceTier.UNDERPERFORMING in tiers
        assert PerformanceTier.NEW_SITE in tiers

    # --- Protocol Deviation Trends ---

    def test_seed_deviation_trends_count(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_protocol_deviation_trends()
        assert len(items) == 12

    def test_seed_deviation_trend_ids(self, svc: ClinicalOperationsAnalyticsService):
        for i in range(1, 11):
            pdt = svc.get_protocol_deviation_trend(f"PDT-{i:03d}")
            assert pdt is not None

    def test_seed_deviation_trend_pdt001(self, svc: ClinicalOperationsAnalyticsService):
        pdt = svc.get_protocol_deviation_trend("PDT-001")
        assert pdt is not None
        assert pdt.trial_id == EYLEA_TRIAL
        assert pdt.deviation_category == DeviationCategory.INFORMED_CONSENT

    def test_seed_deviation_trend_pdt005(self, svc: ClinicalOperationsAnalyticsService):
        pdt = svc.get_protocol_deviation_trend("PDT-005")
        assert pdt is not None
        assert pdt.trial_id == DUPIXENT_TRIAL
        assert pdt.deviation_category == DeviationCategory.INCLUSION_EXCLUSION

    def test_seed_deviation_categories_present(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_protocol_deviation_trends()
        cats = {d.deviation_category for d in items}
        assert DeviationCategory.INFORMED_CONSENT in cats
        assert DeviationCategory.VISIT_WINDOW in cats
        assert DeviationCategory.STUDY_PROCEDURES in cats
        assert DeviationCategory.DOSING in cats
        assert DeviationCategory.INCLUSION_EXCLUSION in cats
        assert DeviationCategory.SAFETY_REPORTING in cats

    # --- Resource Utilizations ---

    def test_seed_resource_utilizations_count(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_resource_utilizations()
        assert len(items) == 12

    def test_seed_resource_utilization_ids(self, svc: ClinicalOperationsAnalyticsService):
        for i in range(1, 11):
            ru = svc.get_resource_utilization(f"RU-{i:03d}")
            assert ru is not None

    def test_seed_resource_utilization_ru001(self, svc: ClinicalOperationsAnalyticsService):
        ru = svc.get_resource_utilization("RU-001")
        assert ru is not None
        assert ru.trial_id == EYLEA_TRIAL
        assert ru.resource_type == ResourceType.CRA

    def test_seed_resource_utilization_ru007(self, svc: ClinicalOperationsAnalyticsService):
        ru = svc.get_resource_utilization("RU-007")
        assert ru is not None
        assert ru.trial_id == DUPIXENT_TRIAL
        assert ru.resource_type == ResourceType.BIOSTATISTICIAN

    def test_seed_resource_types_present(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_resource_utilizations()
        types = {r.resource_type for r in items}
        assert ResourceType.CRA in types
        assert ResourceType.DATA_MANAGER in types
        assert ResourceType.PROJECT_MANAGER in types
        assert ResourceType.MEDICAL_MONITOR in types
        assert ResourceType.BIOSTATISTICIAN in types
        assert ResourceType.REGULATORY_SPECIALIST in types

    # --- Milestone Achievements ---

    def test_seed_milestones_count(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_milestone_achievements()
        assert len(items) == 12

    def test_seed_milestone_ids(self, svc: ClinicalOperationsAnalyticsService):
        for i in range(1, 13):
            ma = svc.get_milestone_achievement(f"MA-{i:03d}")
            assert ma is not None

    def test_seed_milestone_ma001(self, svc: ClinicalOperationsAnalyticsService):
        ma = svc.get_milestone_achievement("MA-001")
        assert ma is not None
        assert ma.trial_id == EYLEA_TRIAL
        assert ma.achieved is True
        assert ma.milestone_category == MilestoneCategory.ENROLLMENT

    def test_seed_milestone_ma005(self, svc: ClinicalOperationsAnalyticsService):
        ma = svc.get_milestone_achievement("MA-005")
        assert ma is not None
        assert ma.trial_id == DUPIXENT_TRIAL
        assert ma.milestone_category == MilestoneCategory.REGULATORY

    def test_seed_milestone_ma007_escalated(self, svc: ClinicalOperationsAnalyticsService):
        ma = svc.get_milestone_achievement("MA-007")
        assert ma is not None
        assert ma.escalated is True
        assert ma.on_track is False

    def test_seed_milestone_categories_present(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_milestone_achievements()
        cats = {m.milestone_category for m in items}
        assert MilestoneCategory.REGULATORY in cats
        assert MilestoneCategory.SITE_ACTIVATION in cats
        assert MilestoneCategory.ENROLLMENT in cats
        assert MilestoneCategory.DATABASE_LOCK in cats
        assert MilestoneCategory.ANALYSIS in cats
        assert MilestoneCategory.SUBMISSION in cats


# =====================================================================
# ENROLLMENT VELOCITY CRUD
# =====================================================================


class TestEnrollmentVelocityCRUD:
    """Test enrollment velocity CRUD operations via API."""

    @pytest.mark.anyio
    async def test_list_enrollment_velocities(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-velocities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trend_accelerating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"velocity_trend": "accelerating"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["velocity_trend"] == "accelerating"

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trend_steady(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"velocity_trend": "steady"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["velocity_trend"] == "steady"

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trend_decelerating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"velocity_trend": "decelerating"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["velocity_trend"] == "decelerating"

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trend_stalled(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"velocity_trend": "stalled"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["velocity_trend"] == "stalled"

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_filter_by_trend_recovering(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities", params={"velocity_trend": "recovering"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["velocity_trend"] == "recovering"

    @pytest.mark.anyio
    async def test_list_enrollment_velocities_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities",
            params={"trial_id": EYLEA_TRIAL, "velocity_trend": "accelerating"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["velocity_trend"] == "accelerating"

    @pytest.mark.anyio
    async def test_get_enrollment_velocity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-velocities/EV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EV-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["velocity_trend"] == "accelerating"

    @pytest.mark.anyio
    async def test_get_enrollment_velocity_ev012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-velocities/EV-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EV-012"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_enrollment_velocity_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-velocities/EV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_enrollment_velocity(self, client: AsyncClient):
        payload = _make_enrollment_velocity_create()
        resp = await client.post(f"{API_PREFIX}/enrollment-velocities", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("EV-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["patients_enrolled"] == 15
        assert data["patients_screened"] == 25
        assert data["target_enrollment"] == 200
        assert data["analyzed_by"] == "Dr. Test Analyst"
        assert data["velocity_trend"] == "not_started"

    @pytest.mark.anyio
    async def test_create_enrollment_velocity_screen_fail_computed(self, client: AsyncClient):
        payload = _make_enrollment_velocity_create(patients_enrolled=10, patients_screened=20)
        resp = await client.post(f"{API_PREFIX}/enrollment-velocities", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["screen_fail_rate_pct"] == 50.0

    @pytest.mark.anyio
    async def test_create_enrollment_velocity_increases_count(self, client: AsyncClient):
        payload = _make_enrollment_velocity_create()
        resp = await client.post(f"{API_PREFIX}/enrollment-velocities", json=payload)
        assert resp.status_code == 201
        list_resp = await client.get(f"{API_PREFIX}/enrollment-velocities")
        assert list_resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_enrollment_velocity(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/enrollment-velocities/EV-001",
            json={"velocity_trend": "decelerating", "notes": "Updated trend"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["velocity_trend"] == "decelerating"
        assert data["notes"] == "Updated trend"

    @pytest.mark.anyio
    async def test_update_enrollment_velocity_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/enrollment-velocities/EV-002",
            json={"pct_target_achieved": 99.9},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pct_target_achieved"] == 99.9
        assert data["id"] == "EV-002"

    @pytest.mark.anyio
    async def test_update_enrollment_velocity_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/enrollment-velocities/EV-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_enrollment_velocity(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/enrollment-velocities/EV-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/enrollment-velocities/EV-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_enrollment_velocity_decreases_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/enrollment-velocities/EV-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/enrollment-velocities")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_enrollment_velocity_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/enrollment-velocities/EV-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_enrollment_velocities_no_filters(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_enrollment_velocities()
        assert len(items) == 12

    def test_service_list_enrollment_velocities_filter_trial(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_enrollment_velocities(trial_id=DUPIXENT_TRIAL)
        assert len(items) == 4
        for v in items:
            assert v.trial_id == DUPIXENT_TRIAL

    def test_service_list_enrollment_velocities_filter_trend(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_enrollment_velocities(velocity_trend=VelocityTrend.STALLED)
        assert len(items) >= 1
        for v in items:
            assert v.velocity_trend == VelocityTrend.STALLED

    def test_service_list_enrollment_velocities_empty_result(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_enrollment_velocities(velocity_trend=VelocityTrend.NOT_STARTED)
        assert len(items) == 0


# =====================================================================
# SITE PERFORMANCE SCORECARD CRUD
# =====================================================================


class TestSitePerformanceScorecardCRUD:
    """Test site performance scorecard CRUD operations via API."""

    @pytest.mark.anyio
    async def test_list_scorecards(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-performance-scorecards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_tier_top_performer(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"performance_tier": "top_performer"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["performance_tier"] == "top_performer"

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_tier_above_average(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"performance_tier": "above_average"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["performance_tier"] == "above_average"

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_tier_average(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"performance_tier": "average"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["performance_tier"] == "average"

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_tier_below_average(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"performance_tier": "below_average"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["performance_tier"] == "below_average"

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_tier_underperforming(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards",
            params={"performance_tier": "underperforming"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        for item in data["items"]:
            assert item["performance_tier"] == "underperforming"

    @pytest.mark.anyio
    async def test_list_scorecards_filter_by_tier_new_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards", params={"performance_tier": "new_site"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        for item in data["items"]:
            assert item["performance_tier"] == "new_site"

    @pytest.mark.anyio
    async def test_list_scorecards_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards",
            params={"trial_id": EYLEA_TRIAL, "performance_tier": "top_performer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["performance_tier"] == "top_performer"

    @pytest.mark.anyio
    async def test_get_scorecard(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-performance-scorecards/SPS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SPS-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["performance_tier"] == "top_performer"
        assert data["overall_score"] == 95.3

    @pytest.mark.anyio
    async def test_get_scorecard_sps012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-performance-scorecards/SPS-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SPS-012"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_scorecard_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-performance-scorecards/SPS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_scorecard(self, client: AsyncClient):
        payload = _make_site_performance_scorecard_create()
        resp = await client.post(f"{API_PREFIX}/site-performance-scorecards", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SPS-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["site_id"] == "SITE-TEST-001"
        assert data["site_name"] == "Test Clinical Site"
        assert data["performance_tier"] == "new_site"
        assert data["enrollment_score"] == 75.0
        assert data["data_quality_score"] == 80.0

    @pytest.mark.anyio
    async def test_create_scorecard_overall_computed(self, client: AsyncClient):
        payload = _make_site_performance_scorecard_create(
            enrollment_score=90.0, data_quality_score=80.0
        )
        resp = await client.post(f"{API_PREFIX}/site-performance-scorecards", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # overall = (90 + 80 + 50 + 50) / 4 = 67.5
        assert data["overall_score"] == 67.5

    @pytest.mark.anyio
    async def test_create_scorecard_increases_count(self, client: AsyncClient):
        payload = _make_site_performance_scorecard_create()
        resp = await client.post(f"{API_PREFIX}/site-performance-scorecards", json=payload)
        assert resp.status_code == 201
        list_resp = await client.get(f"{API_PREFIX}/site-performance-scorecards")
        assert list_resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_scorecard(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-performance-scorecards/SPS-001",
            json={"performance_tier": "above_average", "notes": "Tier adjusted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["performance_tier"] == "above_average"
        assert data["notes"] == "Tier adjusted"

    @pytest.mark.anyio
    async def test_update_scorecard_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-performance-scorecards/SPS-002",
            json={"overall_score": 99.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 99.0
        assert data["id"] == "SPS-002"

    @pytest.mark.anyio
    async def test_update_scorecard_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-performance-scorecards/SPS-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_scorecard(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-performance-scorecards/SPS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-performance-scorecards/SPS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_scorecard_decreases_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-performance-scorecards/SPS-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/site-performance-scorecards")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_scorecard_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-performance-scorecards/SPS-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_scorecards_no_filters(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_site_performance_scorecards()
        assert len(items) == 12

    def test_service_list_scorecards_filter_trial(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_site_performance_scorecards(trial_id=LIBTAYO_TRIAL)
        assert len(items) == 4
        for s in items:
            assert s.trial_id == LIBTAYO_TRIAL

    def test_service_list_scorecards_filter_tier(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_site_performance_scorecards(performance_tier=PerformanceTier.TOP_PERFORMER)
        assert len(items) == 3
        for s in items:
            assert s.performance_tier == PerformanceTier.TOP_PERFORMER


# =====================================================================
# PROTOCOL DEVIATION TREND CRUD
# =====================================================================


class TestProtocolDeviationTrendCRUD:
    """Test protocol deviation trend CRUD operations via API."""

    @pytest.mark.anyio
    async def test_list_deviation_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocol-deviation-trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_category_informed_consent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"deviation_category": "informed_consent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deviation_category"] == "informed_consent"

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_category_visit_window(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"deviation_category": "visit_window"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deviation_category"] == "visit_window"

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_category_study_procedures(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"deviation_category": "study_procedures"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deviation_category"] == "study_procedures"

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_category_dosing(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"deviation_category": "dosing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["deviation_category"] == "dosing"

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_category_inclusion_exclusion(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"deviation_category": "inclusion_exclusion"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deviation_category"] == "inclusion_exclusion"

    @pytest.mark.anyio
    async def test_list_deviation_trends_filter_by_category_safety_reporting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"deviation_category": "safety_reporting"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deviation_category"] == "safety_reporting"

    @pytest.mark.anyio
    async def test_list_deviation_trends_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"trial_id": DUPIXENT_TRIAL, "deviation_category": "inclusion_exclusion"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL
            assert item["deviation_category"] == "inclusion_exclusion"

    @pytest.mark.anyio
    async def test_get_deviation_trend(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocol-deviation-trends/PDT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PDT-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["deviation_category"] == "informed_consent"

    @pytest.mark.anyio
    async def test_get_deviation_trend_pdt012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocol-deviation-trends/PDT-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PDT-012"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_deviation_trend_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocol-deviation-trends/PDT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_deviation_trend(self, client: AsyncClient):
        payload = _make_protocol_deviation_trend_create()
        resp = await client.post(f"{API_PREFIX}/protocol-deviation-trends", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PDT-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["deviation_category"] == "informed_consent"
        assert data["total_deviations"] == 10
        assert data["major_deviations"] == 2
        assert data["minor_deviations"] == 8  # total - major

    @pytest.mark.anyio
    async def test_create_deviation_trend_increases_count(self, client: AsyncClient):
        payload = _make_protocol_deviation_trend_create()
        resp = await client.post(f"{API_PREFIX}/protocol-deviation-trends", json=payload)
        assert resp.status_code == 201
        list_resp = await client.get(f"{API_PREFIX}/protocol-deviation-trends")
        assert list_resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_deviation_trend(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocol-deviation-trends/PDT-001",
            json={"trend_direction": "decreasing", "notes": "Improvement noted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trend_direction"] == "decreasing"
        assert data["notes"] == "Improvement noted"

    @pytest.mark.anyio
    async def test_update_deviation_trend_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocol-deviation-trends/PDT-002",
            json={"corrective_actions_initiated": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["corrective_actions_initiated"] == 10
        assert data["id"] == "PDT-002"

    @pytest.mark.anyio
    async def test_update_deviation_trend_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocol-deviation-trends/PDT-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deviation_trend(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/protocol-deviation-trends/PDT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/protocol-deviation-trends/PDT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deviation_trend_decreases_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/protocol-deviation-trends/PDT-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/protocol-deviation-trends")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_deviation_trend_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/protocol-deviation-trends/PDT-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_deviation_trends_no_filters(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_protocol_deviation_trends()
        assert len(items) == 12

    def test_service_list_deviation_trends_filter_trial(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_protocol_deviation_trends(trial_id=EYLEA_TRIAL)
        assert len(items) == 4
        for d in items:
            assert d.trial_id == EYLEA_TRIAL

    def test_service_list_deviation_trends_filter_category(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_protocol_deviation_trends(deviation_category=DeviationCategory.DOSING)
        assert len(items) >= 1
        for d in items:
            assert d.deviation_category == DeviationCategory.DOSING


# =====================================================================
# RESOURCE UTILIZATION CRUD
# =====================================================================


class TestResourceUtilizationCRUD:
    """Test resource utilization CRUD operations via API."""

    @pytest.mark.anyio
    async def test_list_resource_utilizations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-utilizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_type_cra(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"resource_type": "cra"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["resource_type"] == "cra"

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_type_data_manager(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"resource_type": "data_manager"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resource_type"] == "data_manager"

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_type_project_manager(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"resource_type": "project_manager"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resource_type"] == "project_manager"

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_type_medical_monitor(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"resource_type": "medical_monitor"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resource_type"] == "medical_monitor"

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_type_biostatistician(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations", params={"resource_type": "biostatistician"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resource_type"] == "biostatistician"

    @pytest.mark.anyio
    async def test_list_resource_utilizations_filter_by_type_regulatory_specialist(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations",
            params={"resource_type": "regulatory_specialist"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["resource_type"] == "regulatory_specialist"

    @pytest.mark.anyio
    async def test_list_resource_utilizations_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations",
            params={"trial_id": EYLEA_TRIAL, "resource_type": "cra"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["resource_type"] == "cra"

    @pytest.mark.anyio
    async def test_get_resource_utilization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-utilizations/RU-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RU-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["resource_type"] == "cra"

    @pytest.mark.anyio
    async def test_get_resource_utilization_ru012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-utilizations/RU-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RU-012"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_resource_utilization_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-utilizations/RU-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_resource_utilization(self, client: AsyncClient):
        payload = _make_resource_utilization_create()
        resp = await client.post(f"{API_PREFIX}/resource-utilizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RU-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["resource_type"] == "cra"
        assert data["total_fte_allocated"] == 10.0
        assert data["total_fte_utilized"] == 8.5
        assert data["utilization_pct"] == 85.0  # 8.5/10.0 * 100

    @pytest.mark.anyio
    async def test_create_resource_utilization_utilization_pct_computed(self, client: AsyncClient):
        payload = _make_resource_utilization_create(
            total_fte_allocated=4.0, total_fte_utilized=3.0
        )
        resp = await client.post(f"{API_PREFIX}/resource-utilizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["utilization_pct"] == 75.0

    @pytest.mark.anyio
    async def test_create_resource_utilization_increases_count(self, client: AsyncClient):
        payload = _make_resource_utilization_create()
        resp = await client.post(f"{API_PREFIX}/resource-utilizations", json=payload)
        assert resp.status_code == 201
        list_resp = await client.get(f"{API_PREFIX}/resource-utilizations")
        assert list_resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_resource_utilization(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resource-utilizations/RU-001",
            json={"utilization_pct": 95.0, "notes": "High workload"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["utilization_pct"] == 95.0
        assert data["notes"] == "High workload"

    @pytest.mark.anyio
    async def test_update_resource_utilization_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resource-utilizations/RU-002",
            json={"vacancy_count": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vacancy_count"] == 3
        assert data["id"] == "RU-002"

    @pytest.mark.anyio
    async def test_update_resource_utilization_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resource-utilizations/RU-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_resource_utilization(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resource-utilizations/RU-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/resource-utilizations/RU-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_resource_utilization_decreases_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resource-utilizations/RU-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/resource-utilizations")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_resource_utilization_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resource-utilizations/RU-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_resource_utilizations_no_filters(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_resource_utilizations()
        assert len(items) == 12

    def test_service_list_resource_utilizations_filter_trial(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_resource_utilizations(trial_id=LIBTAYO_TRIAL)
        assert len(items) == 4
        for r in items:
            assert r.trial_id == LIBTAYO_TRIAL

    def test_service_list_resource_utilizations_filter_type(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_resource_utilizations(resource_type=ResourceType.CRA)
        assert len(items) == 3
        for r in items:
            assert r.resource_type == ResourceType.CRA


# =====================================================================
# MILESTONE ACHIEVEMENT CRUD
# =====================================================================


class TestMilestoneAchievementCRUD:
    """Test milestone achievement CRUD operations via API."""

    @pytest.mark.anyio
    async def test_list_milestones(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestone-achievements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_category_enrollment(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"milestone_category": "enrollment"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["milestone_category"] == "enrollment"

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_category_regulatory(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"milestone_category": "regulatory"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["milestone_category"] == "regulatory"

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_category_site_activation(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements",
            params={"milestone_category": "site_activation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["milestone_category"] == "site_activation"

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_category_database_lock(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements",
            params={"milestone_category": "database_lock"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["milestone_category"] == "database_lock"

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_category_analysis(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"milestone_category": "analysis"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["milestone_category"] == "analysis"

    @pytest.mark.anyio
    async def test_list_milestones_filter_by_category_submission(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements", params={"milestone_category": "submission"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["milestone_category"] == "submission"

    @pytest.mark.anyio
    async def test_list_milestones_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements",
            params={"trial_id": LIBTAYO_TRIAL, "milestone_category": "regulatory"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["milestone_category"] == "regulatory"

    @pytest.mark.anyio
    async def test_get_milestone(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestone-achievements/MA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MA-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["achieved"] is True
        assert data["milestone_category"] == "enrollment"

    @pytest.mark.anyio
    async def test_get_milestone_ma007(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestone-achievements/MA-007")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MA-007"
        assert data["escalated"] is True
        assert data["on_track"] is False

    @pytest.mark.anyio
    async def test_get_milestone_ma012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestone-achievements/MA-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MA-012"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_milestone_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestone-achievements/MA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_milestone(self, client: AsyncClient):
        payload = _make_milestone_achievement_create()
        resp = await client.post(f"{API_PREFIX}/milestone-achievements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("MA-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["milestone_name"] == "Test Milestone"
        assert data["milestone_category"] == "enrollment"
        assert data["achieved"] is False
        assert data["on_track"] is True
        assert data["escalated"] is False

    @pytest.mark.anyio
    async def test_create_milestone_with_critical_path(self, client: AsyncClient):
        payload = _make_milestone_achievement_create(critical_path=True)
        resp = await client.post(f"{API_PREFIX}/milestone-achievements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["critical_path"] is True

    @pytest.mark.anyio
    async def test_create_milestone_increases_count(self, client: AsyncClient):
        payload = _make_milestone_achievement_create()
        resp = await client.post(f"{API_PREFIX}/milestone-achievements", json=payload)
        assert resp.status_code == 201
        list_resp = await client.get(f"{API_PREFIX}/milestone-achievements")
        assert list_resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_milestone(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestone-achievements/MA-003",
            json={"achieved": True, "actual_date": "2026-02-01T00:00:00Z", "notes": "Completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["achieved"] is True
        assert data["actual_date"] is not None
        assert data["notes"] == "Completed"

    @pytest.mark.anyio
    async def test_update_milestone_escalate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestone-achievements/MA-003",
            json={"escalated": True, "on_track": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["escalated"] is True
        assert data["on_track"] is False

    @pytest.mark.anyio
    async def test_update_milestone_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestone-achievements/MA-004",
            json={"notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated note"
        assert data["id"] == "MA-004"

    @pytest.mark.anyio
    async def test_update_milestone_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestone-achievements/MA-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_milestone(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestone-achievements/MA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/milestone-achievements/MA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_milestone_decreases_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestone-achievements/MA-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/milestone-achievements")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_milestone_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestone-achievements/MA-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_milestones_no_filters(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_milestone_achievements()
        assert len(items) == 12

    def test_service_list_milestones_filter_trial(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_milestone_achievements(trial_id=DUPIXENT_TRIAL)
        assert len(items) == 4
        for m in items:
            assert m.trial_id == DUPIXENT_TRIAL

    def test_service_list_milestones_filter_category(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_milestone_achievements(milestone_category=MilestoneCategory.ENROLLMENT)
        assert len(items) >= 3
        for m in items:
            assert m.milestone_category == MilestoneCategory.ENROLLMENT

    def test_service_list_milestones_filter_category_submission(self, svc: ClinicalOperationsAnalyticsService):
        items = svc.list_milestone_achievements(milestone_category=MilestoneCategory.SUBMISSION)
        assert len(items) == 2
        for m in items:
            assert m.milestone_category == MilestoneCategory.SUBMISSION


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_velocity_records"] == 12
        assert data["total_scorecards"] == 12
        assert data["total_deviation_trends"] == 12
        assert data["total_resource_records"] == 12
        assert data["total_milestones"] == 12

    @pytest.mark.anyio
    async def test_metrics_velocity_by_trend(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        vbt = data["velocity_by_trend"]
        total = sum(vbt.values())
        assert total == 12
        assert "accelerating" in vbt
        assert "steady" in vbt

    @pytest.mark.anyio
    async def test_metrics_scorecards_by_tier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        sbt = data["scorecards_by_tier"]
        total = sum(sbt.values())
        assert total == 12
        assert "top_performer" in sbt
        assert "underperforming" in sbt

    @pytest.mark.anyio
    async def test_metrics_deviations_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        dbc = data["deviations_by_category"]
        total = sum(dbc.values())
        assert total == 12

    @pytest.mark.anyio
    async def test_metrics_resources_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        rbt = data["resources_by_type"]
        total = sum(rbt.values())
        assert total == 12

    @pytest.mark.anyio
    async def test_metrics_milestones_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        mbc = data["milestones_by_category"]
        total = sum(mbc.values())
        assert total == 12

    @pytest.mark.anyio
    async def test_metrics_avg_enrollment_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_enrollment_rate"] > 0

    @pytest.mark.anyio
    async def test_metrics_avg_overall_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_overall_score"] > 0

    @pytest.mark.anyio
    async def test_metrics_avg_utilization_pct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_utilization_pct"] > 0

    @pytest.mark.anyio
    async def test_metrics_total_major_deviations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_major_deviations"] > 0

    @pytest.mark.anyio
    async def test_metrics_milestones_achieved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["milestones_achieved"] > 0

    @pytest.mark.anyio
    async def test_metrics_milestones_overdue(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["milestones_overdue"] >= 0

    # --- Service-level metrics tests ---

    def test_service_metrics_velocity_by_trend_sums(self, svc: ClinicalOperationsAnalyticsService):
        metrics = svc.get_metrics()
        total = sum(metrics.velocity_by_trend.values())
        assert total == metrics.total_velocity_records

    def test_service_metrics_scorecards_by_tier_sums(self, svc: ClinicalOperationsAnalyticsService):
        metrics = svc.get_metrics()
        total = sum(metrics.scorecards_by_tier.values())
        assert total == metrics.total_scorecards

    def test_service_metrics_deviations_by_category_sums(self, svc: ClinicalOperationsAnalyticsService):
        metrics = svc.get_metrics()
        total = sum(metrics.deviations_by_category.values())
        assert total == metrics.total_deviation_trends

    def test_service_metrics_resources_by_type_sums(self, svc: ClinicalOperationsAnalyticsService):
        metrics = svc.get_metrics()
        total = sum(metrics.resources_by_type.values())
        assert total == metrics.total_resource_records

    def test_service_metrics_milestones_by_category_sums(self, svc: ClinicalOperationsAnalyticsService):
        metrics = svc.get_metrics()
        total = sum(metrics.milestones_by_category.values())
        assert total == metrics.total_milestones

    def test_service_metrics_milestones_achieved_count(self, svc: ClinicalOperationsAnalyticsService):
        metrics = svc.get_metrics()
        # Count manually: MA-001, MA-002, MA-005, MA-006, MA-009, MA-010 are achieved
        assert metrics.milestones_achieved == 6

    def test_service_metrics_after_create(self, svc: ClinicalOperationsAnalyticsService):
        """Metrics should update after creating new records."""
        from app.schemas.clinical_operations_analytics import EnrollmentVelocityCreate

        before = svc.get_metrics()
        svc.create_enrollment_velocity(
            EnrollmentVelocityCreate(
                trial_id=EYLEA_TRIAL,
                patients_enrolled=10,
                patients_screened=20,
                target_enrollment=100,
                analyzed_by="Test",
            )
        )
        after = svc.get_metrics()
        assert after.total_velocity_records == before.total_velocity_records + 1

    def test_service_metrics_after_delete(self, svc: ClinicalOperationsAnalyticsService):
        """Metrics should update after deleting records."""
        before = svc.get_metrics()
        svc.delete_enrollment_velocity("EV-001")
        after = svc.get_metrics()
        assert after.total_velocity_records == before.total_velocity_records - 1


# =====================================================================
# SINGLETON
# =====================================================================


class TestSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_operations_analytics_service()
        svc2 = get_clinical_operations_analytics_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_operations_analytics_service()
        svc2 = reset_clinical_operations_analytics_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_operations_analytics_service()
        # Delete an enrollment velocity
        svc.delete_enrollment_velocity("EV-001")
        assert svc.get_enrollment_velocity("EV-001") is None
        # Reset should bring it back
        svc2 = reset_clinical_operations_analytics_service()
        assert svc2.get_enrollment_velocity("EV-001") is not None

    def test_reset_reseeds_scorecards(self):
        svc = get_clinical_operations_analytics_service()
        svc.delete_site_performance_scorecard("SPS-001")
        assert svc.get_site_performance_scorecard("SPS-001") is None
        svc2 = reset_clinical_operations_analytics_service()
        assert svc2.get_site_performance_scorecard("SPS-001") is not None

    def test_reset_reseeds_deviation_trends(self):
        svc = get_clinical_operations_analytics_service()
        svc.delete_protocol_deviation_trend("PDT-001")
        assert svc.get_protocol_deviation_trend("PDT-001") is None
        svc2 = reset_clinical_operations_analytics_service()
        assert svc2.get_protocol_deviation_trend("PDT-001") is not None

    def test_reset_reseeds_resource_utilizations(self):
        svc = get_clinical_operations_analytics_service()
        svc.delete_resource_utilization("RU-001")
        assert svc.get_resource_utilization("RU-001") is None
        svc2 = reset_clinical_operations_analytics_service()
        assert svc2.get_resource_utilization("RU-001") is not None

    def test_reset_reseeds_milestones(self):
        svc = get_clinical_operations_analytics_service()
        svc.delete_milestone_achievement("MA-001")
        assert svc.get_milestone_achievement("MA-001") is None
        svc2 = reset_clinical_operations_analytics_service()
        assert svc2.get_milestone_achievement("MA-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        svc1 = get_clinical_operations_analytics_service()
        reset_clinical_operations_analytics_service()
        svc2 = get_clinical_operations_analytics_service()
        assert svc1 is not svc2


# =====================================================================
# ADDITIONAL EDGE CASES AND DATA VALIDATION
# =====================================================================


class TestEdgeCasesAndValidation:
    """Additional edge cases and data validation tests."""

    # --- Create-then-read-back ---

    @pytest.mark.anyio
    async def test_create_and_read_back_enrollment_velocity(self, client: AsyncClient):
        payload = _make_enrollment_velocity_create(trial_id=DUPIXENT_TRIAL)
        resp = await client.post(f"{API_PREFIX}/enrollment-velocities", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/enrollment-velocities/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_create_and_read_back_scorecard(self, client: AsyncClient):
        payload = _make_site_performance_scorecard_create(trial_id=LIBTAYO_TRIAL)
        resp = await client.post(f"{API_PREFIX}/site-performance-scorecards", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/site-performance-scorecards/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_create_and_read_back_deviation_trend(self, client: AsyncClient):
        payload = _make_protocol_deviation_trend_create(
            trial_id=LIBTAYO_TRIAL, deviation_category="dosing"
        )
        resp = await client.post(f"{API_PREFIX}/protocol-deviation-trends", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/protocol-deviation-trends/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["trial_id"] == LIBTAYO_TRIAL
        assert resp2.json()["deviation_category"] == "dosing"

    @pytest.mark.anyio
    async def test_create_and_read_back_resource_utilization(self, client: AsyncClient):
        payload = _make_resource_utilization_create(
            trial_id=DUPIXENT_TRIAL, resource_type="biostatistician"
        )
        resp = await client.post(f"{API_PREFIX}/resource-utilizations", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/resource-utilizations/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["trial_id"] == DUPIXENT_TRIAL
        assert resp2.json()["resource_type"] == "biostatistician"

    @pytest.mark.anyio
    async def test_create_and_read_back_milestone(self, client: AsyncClient):
        payload = _make_milestone_achievement_create(
            trial_id=LIBTAYO_TRIAL, milestone_category="regulatory"
        )
        resp = await client.post(f"{API_PREFIX}/milestone-achievements", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/milestone-achievements/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["trial_id"] == LIBTAYO_TRIAL
        assert resp2.json()["milestone_category"] == "regulatory"

    # --- Seed data field validation ---

    def test_seed_ev_screen_fail_rate_range(self, svc: ClinicalOperationsAnalyticsService):
        for ev in svc.list_enrollment_velocities():
            assert 0.0 <= ev.screen_fail_rate_pct <= 100.0

    def test_seed_scorecard_overall_score_range(self, svc: ClinicalOperationsAnalyticsService):
        for sc in svc.list_site_performance_scorecards():
            assert 0.0 <= sc.overall_score <= 100.0

    def test_seed_resource_utilization_pct_range(self, svc: ClinicalOperationsAnalyticsService):
        for ru in svc.list_resource_utilizations():
            assert 0.0 <= ru.utilization_pct <= 100.0

    def test_seed_milestone_achieved_has_actual_date(self, svc: ClinicalOperationsAnalyticsService):
        for ma in svc.list_milestone_achievements():
            if ma.achieved:
                assert ma.actual_date is not None

    def test_seed_milestone_not_achieved_may_lack_actual_date(self, svc: ClinicalOperationsAnalyticsService):
        unachieved = [m for m in svc.list_milestone_achievements() if not m.achieved]
        assert len(unachieved) > 0
        for ma in unachieved:
            assert ma.actual_date is None

    def test_seed_deviation_minor_equals_total_minus_major(self, svc: ClinicalOperationsAnalyticsService):
        for pdt in svc.list_protocol_deviation_trends():
            assert pdt.minor_deviations == pdt.total_deviations - pdt.major_deviations

    # --- Empty filter results ---

    @pytest.mark.anyio
    async def test_list_velocities_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-velocities",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_scorecards_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-performance-scorecards",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_deviations_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/protocol-deviation-trends",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_resources_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-utilizations",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_milestones_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestone-achievements",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
