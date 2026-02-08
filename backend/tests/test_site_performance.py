"""Tests for Clinical Site Performance Analytics (CMO-8).

Covers:
- Schema validation (ClinicalSite, SitePerformanceScore, SiteBenchmark, etc.)
- Site CRUD operations (get, list, filter)
- Performance scoring (enrollment, quality, timeliness, compliance, overall)
- Benchmarking against cohort percentiles
- Head-to-head site comparison
- Recommendation generation
- Underperformer identification
- Program-wide aggregate metrics
- Enrollment trend generation
- Service singleton and reset
- API endpoint integration (12 endpoints)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.site_performance import (
    ClinicalSite,
    EnrollmentTrendResponse,
    MetricComparison,
    MonthlyEnrollment,
    Quartile,
    RecommendationType,
    SiteBenchmark,
    SiteBenchmarksResponse,
    SiteComparison,
    SiteListResponse,
    SiteMetrics,
    SitePerformanceScore,
    SiteRecommendation,
    SiteRecommendationsResponse,
    SiteScoresResponse,
    SiteStatus,
    UnderperformersResponse,
)
from app.services.site_performance_service import (
    SitePerformanceService,
    get_site_performance_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    svc = get_site_performance_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> SitePerformanceService:
    """Shorthand for the clean service."""
    return clean_service


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """Test Pydantic schema validation."""

    def test_site_status_enum_values(self):
        assert SiteStatus.ACTIVE == "active"
        assert SiteStatus.ENROLLING == "enrolling"
        assert SiteStatus.PAUSED == "paused"
        assert SiteStatus.CLOSED == "closed"
        assert SiteStatus.PENDING_ACTIVATION == "pending_activation"

    def test_recommendation_type_enum_values(self):
        assert RecommendationType.INCREASE_CAPACITY == "increase_capacity"
        assert RecommendationType.TRAINING_NEEDED == "training_needed"
        assert RecommendationType.PAUSE_ENROLLMENT == "pause_enrollment"
        assert RecommendationType.EXPAND_TRIALS == "expand_trials"
        assert RecommendationType.CLOSE == "close"

    def test_quartile_enum_values(self):
        assert Quartile.Q1 == "Q1"
        assert Quartile.Q2 == "Q2"
        assert Quartile.Q3 == "Q3"
        assert Quartile.Q4 == "Q4"

    def test_clinical_site_model(self):
        site = ClinicalSite(
            id="test-001",
            name="Test Site",
            institution="Test Hospital",
            location={"city": "TestCity", "state": "TS", "country": "US"},
            pi_name="Dr. Test",
            status=SiteStatus.ACTIVE,
            created_at="2024-01-01T00:00:00Z",
        )
        assert site.id == "test-001"
        assert site.status == SiteStatus.ACTIVE
        assert site.total_screened == 0
        assert site.total_enrolled == 0

    def test_site_performance_score_model(self):
        score = SitePerformanceScore(
            site_id="site-001",
            enrollment_score=85.0,
            quality_score=73.0,
            timeliness_score=90.0,
            compliance_score=95.0,
            overall_score=84.5,
            rank=1,
            quartile=Quartile.Q1,
            calculated_at="2024-01-01T00:00:00Z",
        )
        assert score.overall_score == 84.5
        assert score.quartile == Quartile.Q1

    def test_site_benchmark_model(self):
        bm = SiteBenchmark(
            metric_name="enrollment_rate_per_month",
            p25=5.0,
            p50=7.5,
            p75=10.0,
            p90=13.0,
            site_value=12.7,
            percentile_rank=85.0,
        )
        assert bm.p50 == 7.5
        assert bm.percentile_rank == 85.0

    def test_metric_comparison_model(self):
        mc = MetricComparison(
            metric="enrollment_rate_per_month",
            site_a_value=14.8,
            site_b_value=12.7,
            difference=2.1,
            better="a",
        )
        assert mc.better == "a"

    def test_site_comparison_model(self):
        comp = SiteComparison(
            site_a_id="site-001",
            site_b_id="site-002",
            metrics_comparison=[],
        )
        assert comp.site_a_id == "site-001"

    def test_site_metrics_model(self):
        metrics = SiteMetrics(
            total_sites=15,
            active_sites=10,
            avg_enrollment_rate=7.5,
            avg_screen_failure_rate=0.4,
            by_country={"US": 5, "DE": 2},
            total_enrolled_all_sites=1000,
        )
        assert metrics.total_sites == 15

    def test_site_recommendation_model(self):
        rec = SiteRecommendation(
            site_id="site-009",
            recommendation_type=RecommendationType.TRAINING_NEEDED,
            rationale="High screen failure rate",
            priority="high",
        )
        assert rec.recommendation_type == RecommendationType.TRAINING_NEEDED

    def test_monthly_enrollment_model(self):
        me = MonthlyEnrollment(month="2024-06", enrolled=12, screened=20)
        assert me.enrolled == 12

    def test_site_list_response_model(self):
        resp = SiteListResponse(sites=[], total=0)
        assert resp.total == 0

    def test_underperformers_response_model(self):
        resp = UnderperformersResponse(threshold=50.0, sites=[], total=0)
        assert resp.threshold == 50.0


# ---------------------------------------------------------------------------
# Service CRUD tests
# ---------------------------------------------------------------------------

class TestServiceCRUD:
    """Test site CRUD operations."""

    def test_seed_data_populated(self, svc: SitePerformanceService):
        result = svc.list_sites()
        assert result.total == 15

    def test_get_site_exists(self, svc: SitePerformanceService):
        site = svc.get_site("site-001")
        assert site is not None
        assert site.name == "Johns Hopkins Oncology Center"

    def test_get_site_not_found(self, svc: SitePerformanceService):
        site = svc.get_site("nonexistent")
        assert site is None

    def test_list_sites_no_filter(self, svc: SitePerformanceService):
        result = svc.list_sites()
        assert result.total == 15
        assert len(result.sites) == 15

    def test_list_sites_filter_by_status(self, svc: SitePerformanceService):
        result = svc.list_sites(status=SiteStatus.ENROLLING)
        assert result.total > 0
        for s in result.sites:
            assert s.status == SiteStatus.ENROLLING

    def test_list_sites_filter_by_status_string(self, svc: SitePerformanceService):
        result = svc.list_sites(status="paused")
        assert result.total > 0
        for s in result.sites:
            assert s.status == SiteStatus.PAUSED

    def test_list_sites_filter_by_country(self, svc: SitePerformanceService):
        result = svc.list_sites(country="US")
        assert result.total > 0
        for s in result.sites:
            assert s.location["country"] == "US"

    def test_list_sites_filter_by_country_case_insensitive(self, svc: SitePerformanceService):
        result = svc.list_sites(country="us")
        assert result.total > 0

    def test_list_sites_filter_by_trial_id(self, svc: SitePerformanceService):
        trial_id = "00000000-de00-0001-0000-000000000001"
        result = svc.list_sites(trial_id=trial_id)
        assert result.total > 0
        for s in result.sites:
            assert trial_id in s.trials

    def test_list_sites_combined_filters(self, svc: SitePerformanceService):
        result = svc.list_sites(status=SiteStatus.ENROLLING, country="US")
        for s in result.sites:
            assert s.status == SiteStatus.ENROLLING
            assert s.location["country"] == "US"

    def test_list_sites_no_match(self, svc: SitePerformanceService):
        result = svc.list_sites(country="ZZ")
        assert result.total == 0

    def test_site_has_required_fields(self, svc: SitePerformanceService):
        site = svc.get_site("site-001")
        assert site is not None
        assert site.id
        assert site.name
        assert site.institution
        assert site.pi_name
        assert site.location.get("city")
        assert site.location.get("country")
        assert site.created_at


# ---------------------------------------------------------------------------
# Performance scoring tests
# ---------------------------------------------------------------------------

class TestPerformanceScoring:
    """Test performance score calculations."""

    def test_scores_computed_for_all_scorable(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        # site-013 has 0 screened, so should be excluded
        assert len(result.scores) == 14

    def test_scores_have_valid_ranges(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        for score in result.scores:
            assert 0 <= score.enrollment_score <= 100
            assert 0 <= score.quality_score <= 100
            assert 0 <= score.timeliness_score <= 100
            assert 0 <= score.compliance_score <= 100
            assert 0 <= score.overall_score <= 100

    def test_scores_ranked(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        ranks = [s.rank for s in result.scores]
        assert ranks == sorted(ranks)
        assert ranks[0] == 1
        assert ranks[-1] == len(result.scores)

    def test_scores_descending_overall(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        overalls = [s.overall_score for s in result.scores]
        assert overalls == sorted(overalls, reverse=True)

    def test_quartiles_assigned(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        quartiles = {s.quartile for s in result.scores}
        # With 14 sites, should have multiple quartiles
        assert len(quartiles) >= 2

    def test_top_performer_in_q1(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        top = result.scores[0]
        assert top.quartile == Quartile.Q1

    def test_worst_performer_in_q4(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        worst = result.scores[-1]
        assert worst.quartile == Quartile.Q4

    def test_calculated_at_populated(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        assert result.calculated_at

    def test_top_sites_score_higher(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        scores_map = {s.site_id: s.overall_score for s in result.scores}
        # site-001 (top performer) should beat site-010 (underperformer)
        assert scores_map.get("site-001", 0) > scores_map.get("site-010", 0)


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------

class TestBenchmarks:
    """Test site benchmarking against cohort."""

    def test_benchmarks_for_valid_site(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("site-001")
        assert result is not None
        assert result.site_id == "site-001"
        assert len(result.benchmarks) > 0

    def test_benchmarks_not_found(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("nonexistent")
        assert result is None

    def test_benchmark_metrics_included(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("site-001")
        assert result is not None
        metric_names = {b.metric_name for b in result.benchmarks}
        assert "enrollment_rate_per_month" in metric_names
        assert "screen_failure_rate" in metric_names

    def test_benchmark_percentiles_ordered(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("site-001")
        assert result is not None
        for bm in result.benchmarks:
            assert bm.p25 <= bm.p50 <= bm.p75 <= bm.p90

    def test_benchmark_percentile_rank_valid(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("site-001")
        assert result is not None
        for bm in result.benchmarks:
            assert 0 <= bm.percentile_rank <= 100

    def test_top_performer_high_enrollment_percentile(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("site-001")
        assert result is not None
        enrollment_bm = next(
            (b for b in result.benchmarks if b.metric_name == "enrollment_rate_per_month"),
            None,
        )
        assert enrollment_bm is not None
        # Top performer should be in upper percentiles
        assert enrollment_bm.percentile_rank > 50


# ---------------------------------------------------------------------------
# Site comparison tests
# ---------------------------------------------------------------------------

class TestSiteComparison:
    """Test head-to-head site comparison."""

    def test_compare_two_valid_sites(self, svc: SitePerformanceService):
        result = svc.compare_sites("site-001", "site-002")
        assert result is not None
        assert result.site_a_id == "site-001"
        assert result.site_b_id == "site-002"
        assert len(result.metrics_comparison) > 0

    def test_compare_with_nonexistent_site(self, svc: SitePerformanceService):
        result = svc.compare_sites("site-001", "nonexistent")
        assert result is None

    def test_comparison_metrics_present(self, svc: SitePerformanceService):
        result = svc.compare_sites("site-001", "site-009")
        assert result is not None
        metric_names = {mc.metric for mc in result.metrics_comparison}
        assert "enrollment_rate_per_month" in metric_names
        assert "screen_failure_rate" in metric_names

    def test_comparison_better_field(self, svc: SitePerformanceService):
        result = svc.compare_sites("site-001", "site-010")
        assert result is not None
        for mc in result.metrics_comparison:
            assert mc.better in ("a", "b", "tie")

    def test_comparison_difference_sign(self, svc: SitePerformanceService):
        result = svc.compare_sites("site-001", "site-002")
        assert result is not None
        for mc in result.metrics_comparison:
            expected_diff = round(mc.site_a_value - mc.site_b_value, 4)
            assert abs(mc.difference - expected_diff) < 1e-3


# ---------------------------------------------------------------------------
# Recommendation tests
# ---------------------------------------------------------------------------

class TestRecommendations:
    """Test recommendation generation."""

    def test_recommendations_for_underperformer(self, svc: SitePerformanceService):
        # site-010 has high screen failure rate, low enrollment, high deviations
        result = svc.get_recommendations("site-010")
        assert result is not None
        assert result.site_id == "site-010"
        assert len(result.recommendations) > 0

    def test_recommendations_not_found(self, svc: SitePerformanceService):
        result = svc.get_recommendations("nonexistent")
        assert result is None

    def test_underperformer_gets_training_recommendation(self, svc: SitePerformanceService):
        result = svc.get_recommendations("site-010")
        assert result is not None
        rec_types = {r.recommendation_type for r in result.recommendations}
        assert RecommendationType.TRAINING_NEEDED in rec_types

    def test_underperformer_gets_pause_recommendation(self, svc: SitePerformanceService):
        result = svc.get_recommendations("site-010")
        assert result is not None
        rec_types = {r.recommendation_type for r in result.recommendations}
        assert RecommendationType.PAUSE_ENROLLMENT in rec_types

    def test_top_performer_gets_expand_recommendation(self, svc: SitePerformanceService):
        # site-001 is a top performer with only 2 trials
        result = svc.get_recommendations("site-001")
        assert result is not None
        rec_types = {r.recommendation_type for r in result.recommendations}
        assert RecommendationType.EXPAND_TRIALS in rec_types

    def test_recommendations_have_priority(self, svc: SitePerformanceService):
        result = svc.get_recommendations("site-009")
        assert result is not None
        for rec in result.recommendations:
            assert rec.priority in ("high", "medium", "low")

    def test_recommendations_have_rationale(self, svc: SitePerformanceService):
        result = svc.get_recommendations("site-009")
        assert result is not None
        for rec in result.recommendations:
            assert len(rec.rationale) > 10

    def test_average_site_gets_default_recommendation(self, svc: SitePerformanceService):
        # site-006 is average, should get at least one recommendation
        result = svc.get_recommendations("site-006")
        assert result is not None
        assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# Underperformer tests
# ---------------------------------------------------------------------------

class TestUnderperformers:
    """Test underperformer identification."""

    def test_underperformers_default_threshold(self, svc: SitePerformanceService):
        result = svc.get_underperformers()
        assert result.threshold == 50.0
        assert result.total >= 0

    def test_underperformers_custom_threshold(self, svc: SitePerformanceService):
        result = svc.get_underperformers(threshold=80.0)
        assert result.threshold == 80.0
        # With threshold=80, more sites should be below
        assert result.total > 0

    def test_underperformers_zero_threshold(self, svc: SitePerformanceService):
        result = svc.get_underperformers(threshold=0.0)
        assert result.total == 0

    def test_underperformers_100_threshold(self, svc: SitePerformanceService):
        result = svc.get_underperformers(threshold=100.0)
        # All scorable sites should be below 100
        assert result.total > 0


# ---------------------------------------------------------------------------
# Aggregate metrics tests
# ---------------------------------------------------------------------------

class TestAggregateMetrics:
    """Test program-wide aggregate metrics."""

    def test_metrics_total_sites(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert metrics.total_sites == 15

    def test_metrics_active_sites(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert metrics.active_sites > 0
        assert metrics.active_sites <= metrics.total_sites

    def test_metrics_enrollment_rate(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert metrics.avg_enrollment_rate > 0

    def test_metrics_screen_failure_rate(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_screen_failure_rate <= 1.0

    def test_metrics_by_country(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert len(metrics.by_country) > 0
        assert "US" in metrics.by_country
        assert sum(metrics.by_country.values()) == metrics.total_sites

    def test_metrics_top_performers(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert len(metrics.top_performers) > 0

    def test_metrics_total_enrolled(self, svc: SitePerformanceService):
        metrics = svc.get_metrics()
        assert metrics.total_enrolled_all_sites > 0


# ---------------------------------------------------------------------------
# Enrollment trend tests
# ---------------------------------------------------------------------------

class TestEnrollmentTrends:
    """Test enrollment trend generation."""

    def test_trends_for_valid_site(self, svc: SitePerformanceService):
        result = svc.get_enrollment_trends("site-001")
        assert result is not None
        assert result.site_id == "site-001"
        assert len(result.months) == 6  # default

    def test_trends_not_found(self, svc: SitePerformanceService):
        result = svc.get_enrollment_trends("nonexistent")
        assert result is None

    def test_trends_custom_months(self, svc: SitePerformanceService):
        result = svc.get_enrollment_trends("site-001", months=12)
        assert result is not None
        assert len(result.months) == 12

    def test_trends_monthly_data_valid(self, svc: SitePerformanceService):
        result = svc.get_enrollment_trends("site-001")
        assert result is not None
        for me in result.months:
            assert me.enrolled >= 0
            assert me.screened >= me.enrolled
            assert "-" in me.month  # YYYY-MM format

    def test_trends_deterministic(self, svc: SitePerformanceService):
        result1 = svc.get_enrollment_trends("site-001", months=6)
        result2 = svc.get_enrollment_trends("site-001", months=6)
        assert result1 is not None and result2 is not None
        # Same seed should produce same results
        for m1, m2 in zip(result1.months, result2.months):
            assert m1.enrolled == m2.enrolled


# ---------------------------------------------------------------------------
# Service lifecycle tests
# ---------------------------------------------------------------------------

class TestServiceLifecycle:
    """Test service singleton and reset behavior."""

    def test_singleton_returns_same_instance(self):
        svc1 = get_site_performance_service()
        svc2 = get_site_performance_service()
        assert svc1 is svc2

    def test_clear_re_seeds(self, svc: SitePerformanceService):
        svc.clear()
        result = svc.list_sites()
        assert result.total == 15

    def test_get_stats(self, svc: SitePerformanceService):
        stats = svc.get_stats()
        assert "total_sites" in stats
        assert "active_sites" in stats
        assert stats["total_sites"] == 15


# ---------------------------------------------------------------------------
# API endpoint integration tests
# ---------------------------------------------------------------------------

BASE_URL = "http://test"
PREFIX = "/api/v1/site-performance"


@pytest.mark.anyio
async def test_api_list_sites():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/sites")
    assert resp.status_code == 200
    data = resp.json()
    assert "sites" in data
    assert data["total"] == 15


@pytest.mark.anyio
async def test_api_list_sites_filter_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/sites", params={"status": "enrolling"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    for s in data["sites"]:
        assert s["status"] == "enrolling"


@pytest.mark.anyio
async def test_api_list_sites_filter_country():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/sites", params={"country": "US"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0


@pytest.mark.anyio
async def test_api_get_site():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/sites/site-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "site-001"
    assert data["name"] == "Johns Hopkins Oncology Center"


@pytest.mark.anyio
async def test_api_get_site_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/sites/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_get_all_scores():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/scores")
    assert resp.status_code == 200
    data = resp.json()
    assert "scores" in data
    assert len(data["scores"]) > 0


@pytest.mark.anyio
async def test_api_get_site_score():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/scores/site-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_id"] == "site-001"
    assert 0 <= data["overall_score"] <= 100


@pytest.mark.anyio
async def test_api_get_site_score_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/scores/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_get_benchmarks():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/benchmarks/site-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_id"] == "site-001"
    assert len(data["benchmarks"]) > 0


@pytest.mark.anyio
async def test_api_get_benchmarks_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/benchmarks/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_compare_sites():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/compare", params={"site_a": "site-001", "site_b": "site-002"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_a_id"] == "site-001"
    assert data["site_b_id"] == "site-002"
    assert len(data["metrics_comparison"]) > 0


@pytest.mark.anyio
async def test_api_compare_sites_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/compare", params={"site_a": "site-001", "site_b": "nonexistent"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_get_recommendations():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/recommendations/site-010")
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_id"] == "site-010"
    assert len(data["recommendations"]) > 0


@pytest.mark.anyio
async def test_api_get_recommendations_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/recommendations/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_get_underperformers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/underperformers", params={"threshold": 80.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["threshold"] == 80.0
    assert data["total"] > 0


@pytest.mark.anyio
async def test_api_get_metrics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sites"] == 15
    assert "by_country" in data


@pytest.mark.anyio
async def test_api_get_trends():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/trends/site-001", params={"months": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_id"] == "site-001"
    assert len(data["months"]) == 3


@pytest.mark.anyio
async def test_api_get_trends_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/trends/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_get_stats():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sites"] == 15


@pytest.mark.anyio
async def test_api_get_countries():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"{PREFIX}/countries")
    assert resp.status_code == 200
    data = resp.json()
    assert "by_country" in data
    assert data["total_countries"] > 0


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_pending_site_excluded_from_scores(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        scored_ids = {s.site_id for s in result.scores}
        assert "site-013" not in scored_ids  # pending, 0 screened

    def test_closed_site_included_in_scores(self, svc: SitePerformanceService):
        result = svc.calculate_performance_scores()
        scored_ids = {s.site_id for s in result.scores}
        assert "site-014" in scored_ids  # closed but has screened patients

    def test_pending_site_benchmarks(self, svc: SitePerformanceService):
        result = svc.get_site_benchmarks("site-013")
        assert result is not None
        # Pending site has 0 metrics, most benchmarks will have 0 values
        assert result.site_id == "site-013"

    def test_compare_site_with_itself(self, svc: SitePerformanceService):
        result = svc.compare_sites("site-001", "site-001")
        assert result is not None
        for mc in result.metrics_comparison:
            assert mc.difference == 0.0
            assert mc.better == "tie"

    def test_enrollment_trend_single_month(self, svc: SitePerformanceService):
        result = svc.get_enrollment_trends("site-001", months=1)
        assert result is not None
        assert len(result.months) == 1

    def test_close_recommendation_for_worst_site(self, svc: SitePerformanceService):
        result = svc.get_recommendations("site-010")
        assert result is not None
        rec_types = {r.recommendation_type for r in result.recommendations}
        assert RecommendationType.CLOSE in rec_types

    def test_all_sites_have_valid_location(self, svc: SitePerformanceService):
        result = svc.list_sites()
        for site in result.sites:
            assert "city" in site.location
            assert "country" in site.location

    def test_all_sites_have_trials(self, svc: SitePerformanceService):
        result = svc.list_sites()
        for site in result.sites:
            assert len(site.trials) > 0
