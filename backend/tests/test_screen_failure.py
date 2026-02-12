"""Tests for Screen Failure Analytics module.

Covers:
- Seed data verification (24 screening records across 3 trials)
- Screening record CRUD (create, read, update, delete, list, filter)
- Failure analytics report (top criteria, failure by type, daily trend, near-miss count)
- Recruitment funnel stages and conversion rates
- Criteria difficulty report with pass rates
- Near-miss patient identification
- Filtering by trial_id and outcome
- Error handling (404 for missing records)
- Edge cases (empty trial, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.screen_failure import (
    CriterionType,
    ScreeningOutcome,
)
from app.services.screen_failure_service import (
    ScreenFailureService,
    get_screen_failure_service,
    reset_screen_failure_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/screen-failure"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_screen_failure_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ScreenFailureService:
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


def _make_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "patient_id": "PAT-TEST-001",
        "outcome": "eligible",
        "failing_criteria": [],
        "match_score": 0.85,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_total_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records()
        assert len(records) == 24

    def test_seed_eylea_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(trial_id=EYLEA_TRIAL)
        assert len(records) == 10

    def test_seed_dupixent_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(trial_id=DUPIXENT_TRIAL)
        assert len(records) == 8

    def test_seed_libtayo_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(trial_id=LIBTAYO_TRIAL)
        assert len(records) == 6

    def test_seed_has_eligible_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(outcome=ScreeningOutcome.ELIGIBLE)
        assert len(records) >= 6

    def test_seed_has_ineligible_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(outcome=ScreeningOutcome.INELIGIBLE)
        assert len(records) >= 10

    def test_seed_has_pending_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(outcome=ScreeningOutcome.PENDING)
        assert len(records) >= 1

    def test_seed_has_error_records(self, svc: ScreenFailureService):
        records = svc.list_screening_records(outcome=ScreeningOutcome.ERROR)
        assert len(records) >= 1

    def test_seed_records_have_failing_criteria(self, svc: ScreenFailureService):
        records = svc.list_screening_records(outcome=ScreeningOutcome.INELIGIBLE)
        for r in records:
            assert len(r.failing_criteria) >= 1

    def test_seed_eligible_records_have_no_failures(self, svc: ScreenFailureService):
        records = svc.list_screening_records(outcome=ScreeningOutcome.ELIGIBLE)
        for r in records:
            assert len(r.failing_criteria) == 0


# =====================================================================
# SCREENING RECORD CRUD
# =====================================================================


class TestScreeningRecordCrud:
    """Test screening record create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 24
        assert len(data["items"]) == 24

    @pytest.mark.anyio
    async def test_list_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_records_filter_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records", params={"outcome": "eligible"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 6
        for item in data["items"]:
            assert item["outcome"] == "eligible"

    @pytest.mark.anyio
    async def test_list_records_filter_both(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/records",
            params={"trial_id": EYLEA_TRIAL, "outcome": "ineligible"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["outcome"] == "ineligible"

    @pytest.mark.anyio
    async def test_get_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records/SCR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["outcome"] == "eligible"

    @pytest.mark.anyio
    async def test_get_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records/SCR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_record(self, client: AsyncClient):
        payload = _make_record_create()
        resp = await client.post(f"{API_PREFIX}/records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["patient_id"] == "PAT-TEST-001"
        assert data["outcome"] == "eligible"
        assert data["id"].startswith("SCR-")

    @pytest.mark.anyio
    async def test_create_record_ineligible(self, client: AsyncClient):
        payload = _make_record_create(
            outcome="ineligible",
            patient_id="PAT-TEST-002",
            match_score=0.35,
            failing_criteria=[
                {
                    "criterion_name": "BMI < 40",
                    "criterion_type": "measurement",
                    "details": "BMI is 42",
                },
            ],
        )
        resp = await client.post(f"{API_PREFIX}/records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "ineligible"
        assert len(data["failing_criteria"]) == 1
        assert data["failing_criteria"][0]["criterion_name"] == "BMI < 40"

    @pytest.mark.anyio
    async def test_create_record_with_metadata(self, client: AsyncClient):
        payload = _make_record_create(
            metadata={"site": "SITE-999", "screener": "Dr. Smith"},
        )
        resp = await client.post(f"{API_PREFIX}/records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["metadata"]["site"] == "SITE-999"

    @pytest.mark.anyio
    async def test_update_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/records/SCR-008",
            json={"outcome": "eligible", "match_score": 0.90},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "eligible"
        assert data["match_score"] == 0.90

    @pytest.mark.anyio
    async def test_update_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/records/SCR-NONEXISTENT",
            json={"outcome": "eligible"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/records/SCR-010")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/records/SCR-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/records/SCR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_records_sorted_by_timestamp_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records")
        data = resp.json()
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True)


# =====================================================================
# FAILURE ANALYTICS REPORT
# =====================================================================


class TestFailureAnalytics:
    """Test failure analytics report generation."""

    @pytest.mark.anyio
    async def test_get_analytics_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_screened"] == 10
        assert data["total_eligible"] == 3
        assert data["total_ineligible"] == 5
        assert data["total_pending"] == 1
        assert data["total_error"] == 1
        assert 0.0 < data["failure_rate"] < 1.0

    @pytest.mark.anyio
    async def test_analytics_has_top_failing_criteria(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        data = resp.json()
        assert len(data["top_failing_criteria"]) > 0
        for crit in data["top_failing_criteria"]:
            assert crit["failure_count"] > 0
            assert 0.0 < crit["failure_rate"] <= 1.0

    @pytest.mark.anyio
    async def test_analytics_has_failure_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        data = resp.json()
        assert len(data["failure_by_type"]) > 0
        total_pct = sum(fbt["percentage"] for fbt in data["failure_by_type"])
        assert abs(total_pct - 100.0) < 0.1

    @pytest.mark.anyio
    async def test_analytics_has_daily_trend(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        data = resp.json()
        assert len(data["daily_trend"]) > 0
        for trend in data["daily_trend"]:
            assert trend["screened"] >= trend["failed"]

    @pytest.mark.anyio
    async def test_analytics_near_miss_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        data = resp.json()
        # EYLEA has patients failing exactly 1 criterion
        assert data["near_miss_count"] >= 1

    @pytest.mark.anyio
    async def test_analytics_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/nonexistent-trial/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_screened"] == 0
        assert data["failure_rate"] == 0.0

    @pytest.mark.anyio
    async def test_analytics_top_n(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/{EYLEA_TRIAL}/analytics",
            params={"top_n": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["top_failing_criteria"]) <= 2

    @pytest.mark.anyio
    async def test_analytics_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{DUPIXENT_TRIAL}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_screened"] == 8
        assert data["total_ineligible"] == 4

    @pytest.mark.anyio
    async def test_analytics_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{LIBTAYO_TRIAL}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_screened"] == 6
        assert data["total_ineligible"] == 4


# =====================================================================
# RECRUITMENT FUNNEL
# =====================================================================


class TestRecruitmentFunnel:
    """Test recruitment funnel generation."""

    @pytest.mark.anyio
    async def test_funnel_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/funnel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert len(data["stages"]) == 4

    @pytest.mark.anyio
    async def test_funnel_stage_names(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/funnel")
        data = resp.json()
        stage_names = [s["name"] for s in data["stages"]]
        assert "Screened" in stage_names
        assert "Passed Inclusion" in stage_names
        assert "Eligible" in stage_names
        assert "Enrolled" in stage_names

    @pytest.mark.anyio
    async def test_funnel_screened_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/funnel")
        data = resp.json()
        screened_stage = data["stages"][0]
        assert screened_stage["name"] == "Screened"
        assert screened_stage["count"] == 10
        assert screened_stage["conversion_rate"] is None  # First stage

    @pytest.mark.anyio
    async def test_funnel_decreasing_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/funnel")
        data = resp.json()
        counts = [s["count"] for s in data["stages"]]
        # Each stage should be <= the previous (except enrolled which defaults to 0)
        assert counts[1] <= counts[0]
        assert counts[2] <= counts[1]

    @pytest.mark.anyio
    async def test_funnel_with_enrolled_count(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/{EYLEA_TRIAL}/funnel",
            params={"enrolled_count": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        enrolled_stage = [s for s in data["stages"] if s["name"] == "Enrolled"][0]
        assert enrolled_stage["count"] == 2

    @pytest.mark.anyio
    async def test_funnel_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/nonexistent-trial/funnel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stages"][0]["count"] == 0


# =====================================================================
# CRITERIA DIFFICULTY
# =====================================================================


class TestCriteriaDifficulty:
    """Test criteria difficulty report."""

    @pytest.mark.anyio
    async def test_criteria_difficulty_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/criteria-difficulty")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert len(data["criteria"]) > 0

    @pytest.mark.anyio
    async def test_criteria_sorted_by_pass_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/criteria-difficulty")
        data = resp.json()
        pass_rates = [c["pass_rate"] for c in data["criteria"]]
        assert pass_rates == sorted(pass_rates)

    @pytest.mark.anyio
    async def test_criteria_pass_rate_valid_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/criteria-difficulty")
        data = resp.json()
        for c in data["criteria"]:
            assert 0.0 <= c["pass_rate"] <= 1.0
            assert c["pass_count"] >= 0
            assert c["fail_count"] >= 0

    @pytest.mark.anyio
    async def test_criteria_pass_plus_fail_equals_total(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/criteria-difficulty")
        data = resp.json()
        for c in data["criteria"]:
            assert c["pass_count"] + c["fail_count"] == 10  # total EYLEA records

    @pytest.mark.anyio
    async def test_criteria_difficulty_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/nonexistent-trial/criteria-difficulty")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["criteria"]) == 0

    @pytest.mark.anyio
    async def test_criteria_has_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/criteria-difficulty")
        data = resp.json()
        valid_types = {t.value for t in CriterionType}
        for c in data["criteria"]:
            assert c["criterion_type"] in valid_types


# =====================================================================
# NEAR-MISS PATIENTS
# =====================================================================


class TestNearMissPatients:
    """Test near-miss patient identification."""

    @pytest.mark.anyio
    async def test_near_miss_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/near-miss")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["max_failures"] == 2
        assert data["total"] >= 1
        assert len(data["patients"]) == data["total"]

    @pytest.mark.anyio
    async def test_near_miss_max_failures(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/near-miss")
        data = resp.json()
        for p in data["patients"]:
            assert 1 <= p["num_failing"] <= 2

    @pytest.mark.anyio
    async def test_near_miss_custom_max_failures(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/{EYLEA_TRIAL}/near-miss",
            params={"max_failures": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        for p in data["patients"]:
            assert p["num_failing"] == 1

    @pytest.mark.anyio
    async def test_near_miss_sorted_by_fewest_failures(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/near-miss")
        data = resp.json()
        if len(data["patients"]) > 1:
            num_failings = [p["num_failing"] for p in data["patients"]]
            assert num_failings == sorted(num_failings)

    @pytest.mark.anyio
    async def test_near_miss_has_criteria(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/near-miss")
        data = resp.json()
        for p in data["patients"]:
            assert len(p["failing_criteria"]) == p["num_failing"]

    @pytest.mark.anyio
    async def test_near_miss_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/nonexistent-trial/near-miss")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["patients"]) == 0

    @pytest.mark.anyio
    async def test_near_miss_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/{LIBTAYO_TRIAL}/near-miss")
        assert resp.status_code == 200
        data = resp.json()
        # LIBTAYO has patients with 1 failing criterion (SCR-021, SCR-023)
        assert data["total"] >= 2


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_screen_failure_service()
        svc2 = get_screen_failure_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_screen_failure_service()
        svc2 = reset_screen_failure_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_screen_failure_service()
        svc.delete_screening_record("SCR-001")
        assert svc.get_screening_record("SCR-001") is None
        svc2 = reset_screen_failure_service()
        assert svc2.get_screening_record("SCR-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_records_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/records")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_record_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "patient_id": "PAT-MINIMAL",
            "outcome": "pending",
        }
        resp = await client.post(f"{API_PREFIX}/records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["failing_criteria"] == []
        assert data["match_score"] is None
        assert data["metadata"] is None

    @pytest.mark.anyio
    async def test_analytics_all_trials(self, client: AsyncClient):
        """Verify analytics work for all three seeded trials."""
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            resp = await client.get(f"{API_PREFIX}/{trial_id}/analytics")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_screened"] > 0

    @pytest.mark.anyio
    async def test_create_then_analytics_updates(self, client: AsyncClient):
        """Creating a new record should update analytics."""
        resp1 = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        original_screened = resp1.json()["total_screened"]

        payload = _make_record_create(patient_id="PAT-NEW-ANALYTICS")
        await client.post(f"{API_PREFIX}/records", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        assert resp2.json()["total_screened"] == original_screened + 1

    @pytest.mark.anyio
    async def test_delete_then_analytics_updates(self, client: AsyncClient):
        """Deleting a record should update analytics."""
        resp1 = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        original_screened = resp1.json()["total_screened"]

        await client.delete(f"{API_PREFIX}/records/SCR-001")

        resp2 = await client.get(f"{API_PREFIX}/{EYLEA_TRIAL}/analytics")
        assert resp2.json()["total_screened"] == original_screened - 1

    @pytest.mark.anyio
    async def test_near_miss_max_failures_3(self, client: AsyncClient):
        """max_failures=3 should include patients with 3 failures too."""
        resp = await client.get(
            f"{API_PREFIX}/{EYLEA_TRIAL}/near-miss",
            params={"max_failures": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        # SCR-007 has 3 failing criteria, should be included now
        patient_ids = [p["patient_id"] for p in data["patients"]]
        assert "PAT-1007" in patient_ids

    @pytest.mark.anyio
    async def test_record_with_metadata_field(self, client: AsyncClient):
        """Verify metadata is preserved on the record."""
        resp = await client.get(f"{API_PREFIX}/records/SCR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"] == {"site": "SITE-101"}

    @pytest.mark.anyio
    async def test_update_record_metadata(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/records/SCR-001",
            json={"metadata": {"site": "SITE-999", "updated": True}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["site"] == "SITE-999"
        assert data["metadata"]["updated"] is True

    @pytest.mark.anyio
    async def test_funnel_all_trials(self, client: AsyncClient):
        """Verify funnel works for all three seeded trials."""
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            resp = await client.get(f"{API_PREFIX}/{trial_id}/funnel")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["stages"]) >= 3

    @pytest.mark.anyio
    async def test_criteria_difficulty_all_trials(self, client: AsyncClient):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            resp = await client.get(f"{API_PREFIX}/{trial_id}/criteria-difficulty")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["criteria"]) > 0
