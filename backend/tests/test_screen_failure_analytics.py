"""Tests for Screen Failure Analytics (VP-Product-3).

Covers:
- Screening outcome recording
- Failure analytics report generation
- Top failing criteria ranking
- Failure rate calculations
- Recruitment funnel stages
- Near-miss patient identification
- Criteria difficulty scoring
- Date range filtering
- API endpoint integration
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.screen_failure import (
    CriterionType,
    FailingCriterion,
    ScreeningOutcome,
)
from app.services.screen_failure_analytics_service import (
    ScreenFailureAnalyticsService,
    get_screen_failure_analytics_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TRIAL_ID = "trial-001"
TRIAL_ID_2 = "trial-002"


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    svc = get_screen_failure_analytics_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> ScreenFailureAnalyticsService:
    """Shorthand for the clean service."""
    return clean_service


def _fc(name: str, ctype: CriterionType = CriterionType.CONDITION, details: str | None = None) -> FailingCriterion:
    """Helper to create a FailingCriterion."""
    return FailingCriterion(criterion_name=name, criterion_type=ctype, details=details)


def _seed_basic(svc: ScreenFailureAnalyticsService) -> None:
    """Seed 10 screening records for TRIAL_ID with mixed outcomes."""
    now = datetime.now(timezone.utc)

    # 3 eligible
    for i in range(3):
        svc.record_screening_outcome(TRIAL_ID, f"P-E{i}", ScreeningOutcome.ELIGIBLE)

    # 5 ineligible with various failures
    svc.record_screening_outcome(
        TRIAL_ID, "P-F1", ScreeningOutcome.INELIGIBLE,
        failing_criteria=[_fc("Age", CriterionType.DEMOGRAPHIC)],
        match_score=0.8,
    )
    svc.record_screening_outcome(
        TRIAL_ID, "P-F2", ScreeningOutcome.INELIGIBLE,
        failing_criteria=[_fc("Age", CriterionType.DEMOGRAPHIC), _fc("HbA1c", CriterionType.MEASUREMENT)],
        match_score=0.5,
    )
    svc.record_screening_outcome(
        TRIAL_ID, "P-F3", ScreeningOutcome.INELIGIBLE,
        failing_criteria=[_fc("Atopic Dermatitis", CriterionType.CONDITION)],
        match_score=0.7,
    )
    svc.record_screening_outcome(
        TRIAL_ID, "P-F4", ScreeningOutcome.INELIGIBLE,
        failing_criteria=[_fc("Active Cancer", CriterionType.CONDITION)],
        match_score=0.0,
    )
    svc.record_screening_outcome(
        TRIAL_ID, "P-F5", ScreeningOutcome.INELIGIBLE,
        failing_criteria=[
            _fc("Age", CriterionType.DEMOGRAPHIC),
            _fc("Active Cancer", CriterionType.CONDITION),
            _fc("HbA1c", CriterionType.MEASUREMENT),
        ],
        match_score=0.2,
    )

    # 1 pending, 1 error
    svc.record_screening_outcome(TRIAL_ID, "P-PEND", ScreeningOutcome.PENDING)
    svc.record_screening_outcome(TRIAL_ID, "P-ERR", ScreeningOutcome.ERROR)


# ===========================================================================
# 1. Outcome Recording
# ===========================================================================


class TestOutcomeRecording:
    """Tests for record_screening_outcome."""

    def test_record_eligible(self, svc: ScreenFailureAnalyticsService):
        rec = svc.record_screening_outcome(TRIAL_ID, "P001", ScreeningOutcome.ELIGIBLE)
        assert rec.outcome == ScreeningOutcome.ELIGIBLE
        assert rec.trial_id == TRIAL_ID
        assert rec.patient_id == "P001"
        assert len(rec.failing_criteria) == 0
        assert rec.id  # non-empty UUID

    def test_record_ineligible_with_criteria(self, svc: ScreenFailureAnalyticsService):
        rec = svc.record_screening_outcome(
            TRIAL_ID, "P002", ScreeningOutcome.INELIGIBLE,
            failing_criteria=[_fc("Age", CriterionType.DEMOGRAPHIC, "Too young")],
            match_score=0.6,
        )
        assert rec.outcome == ScreeningOutcome.INELIGIBLE
        assert len(rec.failing_criteria) == 1
        assert rec.failing_criteria[0].criterion_name == "Age"
        assert rec.failing_criteria[0].criterion_type == CriterionType.DEMOGRAPHIC
        assert rec.match_score == 0.6

    def test_record_with_dict_criteria(self, svc: ScreenFailureAnalyticsService):
        rec = svc.record_screening_outcome(
            TRIAL_ID, "P003", "ineligible",
            failing_criteria=[{"criterion_name": "HbA1c", "criterion_type": "measurement"}],
        )
        assert rec.outcome == ScreeningOutcome.INELIGIBLE
        assert rec.failing_criteria[0].criterion_type == CriterionType.MEASUREMENT

    def test_record_with_metadata(self, svc: ScreenFailureAnalyticsService):
        rec = svc.record_screening_outcome(
            TRIAL_ID, "P004", ScreeningOutcome.ELIGIBLE,
            metadata={"site_id": "SITE-01", "screener": "auto"},
        )
        assert rec.metadata == {"site_id": "SITE-01", "screener": "auto"}

    def test_record_custom_timestamp(self, svc: ScreenFailureAnalyticsService):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        rec = svc.record_screening_outcome(
            TRIAL_ID, "P005", ScreeningOutcome.ELIGIBLE, timestamp=ts,
        )
        assert rec.timestamp == ts

    def test_records_isolated_by_trial(self, svc: ScreenFailureAnalyticsService):
        svc.record_screening_outcome(TRIAL_ID, "P001", ScreeningOutcome.ELIGIBLE)
        svc.record_screening_outcome(TRIAL_ID_2, "P002", ScreeningOutcome.INELIGIBLE)

        assert len(svc.get_records(TRIAL_ID)) == 1
        assert len(svc.get_records(TRIAL_ID_2)) == 1


# ===========================================================================
# 2. Failure Analytics Report
# ===========================================================================


class TestFailureAnalytics:
    """Tests for get_failure_analytics."""

    def test_basic_counts(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_failure_analytics(TRIAL_ID)

        assert report.trial_id == TRIAL_ID
        assert report.total_screened == 10
        assert report.total_eligible == 3
        assert report.total_ineligible == 5
        assert report.total_pending == 1
        assert report.total_error == 1
        assert report.failure_rate == pytest.approx(0.5, abs=0.01)

    def test_top_failing_criteria_ranking(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_failure_analytics(TRIAL_ID)

        # "Age" appears in P-F1, P-F2, P-F5 = 3 times
        # "Active Cancer" appears in P-F4, P-F5 = 2 times
        # "HbA1c" appears in P-F2, P-F5 = 2 times
        # "Atopic Dermatitis" appears in P-F3 = 1 time
        names = [c.criterion_name for c in report.top_failing_criteria]
        assert names[0] == "Age"
        assert report.top_failing_criteria[0].failure_count == 3

    def test_failure_by_type(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_failure_analytics(TRIAL_ID)

        type_map = {f.criterion_type: f for f in report.failure_by_type}
        assert CriterionType.DEMOGRAPHIC in type_map
        assert CriterionType.CONDITION in type_map
        assert CriterionType.MEASUREMENT in type_map

        # Total failure instances: Age(3) + Active Cancer(2) + HbA1c(2) + AD(1) = 8
        total = sum(f.failure_count for f in report.failure_by_type)
        assert total == 8

    def test_near_miss_count(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_failure_analytics(TRIAL_ID)
        # P-F1 (1 criterion), P-F3 (1 criterion), P-F4 (1 criterion) = 3 near misses
        assert report.near_miss_count == 3

    def test_daily_trend(self, svc: ScreenFailureAnalyticsService):
        now = datetime.now(timezone.utc)
        day1 = now.replace(hour=10, minute=0, second=0, microsecond=0)
        day2 = day1 + timedelta(days=1)

        svc.record_screening_outcome(TRIAL_ID, "P1", ScreeningOutcome.ELIGIBLE, timestamp=day1)
        svc.record_screening_outcome(TRIAL_ID, "P2", ScreeningOutcome.INELIGIBLE,
                                     failing_criteria=[_fc("X")], timestamp=day1)
        svc.record_screening_outcome(TRIAL_ID, "P3", ScreeningOutcome.INELIGIBLE,
                                     failing_criteria=[_fc("X")], timestamp=day2)

        report = svc.get_failure_analytics(TRIAL_ID)
        assert len(report.daily_trend) == 2

        d1 = report.daily_trend[0]
        assert d1.screened == 2
        assert d1.failed == 1
        assert d1.failure_rate == pytest.approx(0.5, abs=0.01)

        d2 = report.daily_trend[1]
        assert d2.screened == 1
        assert d2.failed == 1
        assert d2.failure_rate == pytest.approx(1.0, abs=0.01)

    def test_empty_trial(self, svc: ScreenFailureAnalyticsService):
        report = svc.get_failure_analytics("nonexistent-trial")
        assert report.total_screened == 0
        assert report.failure_rate == 0.0
        assert report.top_failing_criteria == []


# ===========================================================================
# 3. Date Range Filtering
# ===========================================================================


class TestDateRangeFiltering:
    """Tests for date_from / date_to filtering."""

    def test_filter_by_date_range(self, svc: ScreenFailureAnalyticsService):
        t1 = datetime(2025, 1, 10, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 20, tzinfo=timezone.utc)
        t3 = datetime(2025, 2, 5, tzinfo=timezone.utc)

        svc.record_screening_outcome(TRIAL_ID, "P1", ScreeningOutcome.ELIGIBLE, timestamp=t1)
        svc.record_screening_outcome(TRIAL_ID, "P2", ScreeningOutcome.INELIGIBLE,
                                     failing_criteria=[_fc("X")], timestamp=t2)
        svc.record_screening_outcome(TRIAL_ID, "P3", ScreeningOutcome.ELIGIBLE, timestamp=t3)

        report = svc.get_failure_analytics(
            TRIAL_ID,
            date_from=datetime(2025, 1, 15, tzinfo=timezone.utc),
            date_to=datetime(2025, 1, 25, tzinfo=timezone.utc),
        )
        assert report.total_screened == 1
        assert report.total_ineligible == 1


# ===========================================================================
# 4. Recruitment Funnel
# ===========================================================================


class TestRecruitmentFunnel:
    """Tests for get_trial_funnel."""

    def test_funnel_stages(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        funnel = svc.get_trial_funnel(TRIAL_ID, enrolled_count=2)

        assert funnel.trial_id == TRIAL_ID
        assert len(funnel.stages) == 5

        stage_names = [s.name for s in funnel.stages]
        assert stage_names == ["Screened", "Passed Inclusion", "Passed Exclusion", "Eligible", "Enrolled"]

        # Screened = 10
        assert funnel.stages[0].count == 10
        assert funnel.stages[0].conversion_rate is None  # first stage

        # Enrolled = 2
        assert funnel.stages[4].count == 2

    def test_funnel_empty_trial(self, svc: ScreenFailureAnalyticsService):
        funnel = svc.get_trial_funnel("empty-trial")
        assert funnel.stages[0].count == 0

    def test_funnel_conversion_rates(self, svc: ScreenFailureAnalyticsService):
        # 4 screened: 2 eligible, 2 fail inclusion
        svc.record_screening_outcome(TRIAL_ID, "P1", ScreeningOutcome.ELIGIBLE)
        svc.record_screening_outcome(TRIAL_ID, "P2", ScreeningOutcome.ELIGIBLE)
        svc.record_screening_outcome(
            TRIAL_ID, "P3", ScreeningOutcome.INELIGIBLE,
            failing_criteria=[_fc("Age", CriterionType.DEMOGRAPHIC)],
        )
        svc.record_screening_outcome(
            TRIAL_ID, "P4", ScreeningOutcome.INELIGIBLE,
            failing_criteria=[_fc("Condition X", CriterionType.CONDITION)],
        )

        funnel = svc.get_trial_funnel(TRIAL_ID, enrolled_count=1)

        # Screened: 4, Passed Inclusion: 2 (the 2 eligible), Eligible: 2, Enrolled: 1
        assert funnel.stages[0].count == 4
        assert funnel.stages[1].count == 2  # passed inclusion
        assert funnel.stages[1].conversion_rate == pytest.approx(0.5, abs=0.01)


# ===========================================================================
# 5. Criteria Difficulty
# ===========================================================================


class TestCriteriaDifficulty:
    """Tests for get_criteria_difficulty."""

    def test_difficulty_ranking(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_criteria_difficulty(TRIAL_ID)

        assert report.trial_id == TRIAL_ID
        assert len(report.criteria) > 0

        # Sorted by pass_rate ascending (hardest first)
        rates = [c.pass_rate for c in report.criteria]
        assert rates == sorted(rates)

    def test_pass_fail_counts(self, svc: ScreenFailureAnalyticsService):
        # 5 records, "Age" fails in 3 of them
        _seed_basic(svc)
        report = svc.get_criteria_difficulty(TRIAL_ID)

        age = next(c for c in report.criteria if c.criterion_name == "Age")
        assert age.fail_count == 3
        assert age.pass_count == 7  # 10 total - 3 fails
        assert age.pass_rate == pytest.approx(0.7, abs=0.01)

    def test_empty_criteria_difficulty(self, svc: ScreenFailureAnalyticsService):
        report = svc.get_criteria_difficulty("no-data")
        assert report.criteria == []


# ===========================================================================
# 6. Near-Miss Patients
# ===========================================================================


class TestNearMissPatients:
    """Tests for get_near_miss_patients."""

    def test_near_miss_default(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_near_miss_patients(TRIAL_ID)

        # max_failures=2 by default
        # P-F1 (1 fail), P-F2 (2 fails), P-F3 (1 fail), P-F4 (1 fail) = 4
        assert report.total == 4
        # Sorted: 1-fail first, then by match_score desc
        assert report.patients[0].num_failing == 1

    def test_near_miss_max_1(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_near_miss_patients(TRIAL_ID, max_failures=1)

        # P-F1 (1 fail), P-F3 (1 fail), P-F4 (1 fail) = 3
        assert report.total == 3
        assert all(p.num_failing == 1 for p in report.patients)

    def test_near_miss_sort_order(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_near_miss_patients(TRIAL_ID)

        # Within same num_failing, higher match_score first
        one_fail = [p for p in report.patients if p.num_failing == 1]
        scores = [p.match_score for p in one_fail]
        # Should be descending
        for i in range(len(scores) - 1):
            s1 = scores[i] if scores[i] is not None else 0.0
            s2 = scores[i + 1] if scores[i + 1] is not None else 0.0
            assert s1 >= s2

    def test_near_miss_failing_criteria_present(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        report = svc.get_near_miss_patients(TRIAL_ID, max_failures=1)

        for p in report.patients:
            assert len(p.failing_criteria) == 1
            assert p.failing_criteria[0].criterion_name

    def test_near_miss_empty(self, svc: ScreenFailureAnalyticsService):
        # Only eligible patients -> no near misses
        svc.record_screening_outcome(TRIAL_ID, "P1", ScreeningOutcome.ELIGIBLE)
        report = svc.get_near_miss_patients(TRIAL_ID)
        assert report.total == 0


# ===========================================================================
# 7. Service Stats
# ===========================================================================


class TestServiceStats:
    """Tests for utility methods."""

    def test_stats(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        stats = svc.get_stats()
        assert stats["total_records"] == 10
        assert stats["trials_tracked"] == 1

    def test_clear(self, svc: ScreenFailureAnalyticsService):
        _seed_basic(svc)
        svc.clear()
        assert svc.get_stats()["total_records"] == 0


# ===========================================================================
# 8. API Endpoint Integration
# ===========================================================================


@pytest.fixture
async def api_client():
    """Async client for API tests (no DB needed -- analytics is in-memory)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/api/v1",
    ) as ac:
        yield ac


@pytest.mark.anyio
async def test_api_get_failures(api_client: AsyncClient, svc: ScreenFailureAnalyticsService):
    _seed_basic(svc)
    resp = await api_client.get(f"/analytics/screening/{TRIAL_ID}/failures")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trial_id"] == TRIAL_ID
    assert body["total_screened"] == 10
    assert body["total_ineligible"] == 5
    assert len(body["top_failing_criteria"]) > 0


@pytest.mark.anyio
async def test_api_get_funnel(api_client: AsyncClient, svc: ScreenFailureAnalyticsService):
    _seed_basic(svc)
    resp = await api_client.get(f"/analytics/screening/{TRIAL_ID}/funnel?enrolled_count=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trial_id"] == TRIAL_ID
    assert len(body["stages"]) == 5
    assert body["stages"][4]["count"] == 2  # enrolled


@pytest.mark.anyio
async def test_api_get_criteria_difficulty(api_client: AsyncClient, svc: ScreenFailureAnalyticsService):
    _seed_basic(svc)
    resp = await api_client.get(f"/analytics/screening/{TRIAL_ID}/criteria-difficulty")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trial_id"] == TRIAL_ID
    assert len(body["criteria"]) > 0


@pytest.mark.anyio
async def test_api_get_near_misses(api_client: AsyncClient, svc: ScreenFailureAnalyticsService):
    _seed_basic(svc)
    resp = await api_client.get(f"/analytics/screening/{TRIAL_ID}/near-misses?max_failures=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trial_id"] == TRIAL_ID
    assert body["max_failures"] == 1
    assert body["total"] == 3
    assert all(p["num_failing"] == 1 for p in body["patients"])


@pytest.mark.anyio
async def test_api_failures_date_range(api_client: AsyncClient, svc: ScreenFailureAnalyticsService):
    t1 = datetime(2025, 3, 1, tzinfo=timezone.utc)
    t2 = datetime(2025, 3, 15, tzinfo=timezone.utc)
    svc.record_screening_outcome(TRIAL_ID, "PA", ScreeningOutcome.ELIGIBLE, timestamp=t1)
    svc.record_screening_outcome(TRIAL_ID, "PB", ScreeningOutcome.INELIGIBLE,
                                 failing_criteria=[_fc("X")], timestamp=t2)

    resp = await api_client.get(
        f"/analytics/screening/{TRIAL_ID}/failures",
        params={
            "date_from": "2025-03-10T00:00:00Z",
            "date_to": "2025-03-20T00:00:00Z",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_screened"] == 1
    assert body["total_ineligible"] == 1
