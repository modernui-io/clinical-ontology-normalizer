"""Tests for Performance Benchmarking & SLA Management (CTO-9).

Tests cover:
- Benchmark recording, querying, retrieval
- SLA CRUD operations
- SLA compliance checks (individual and batch)
- Performance trend analysis
- Regression detection
- Benchmark suite creation, listing, running
- Version comparison
- Aggregate performance metrics
- API endpoint tests
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.performance_benchmarks import (
    BenchmarkCategory,
    Environment,
    SLATier,
    TrendDirection,
)
from app.services.performance_benchmark_service import (
    PerformanceBenchmarkService,
    get_performance_benchmark_service,
    reset_performance_benchmark_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_performance_benchmark_service()
    yield
    reset_performance_benchmark_service()


@pytest.fixture
def service() -> PerformanceBenchmarkService:
    return get_performance_benchmark_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests that seed data is properly populated."""

    def test_seed_slas_populated(self, service: PerformanceBenchmarkService):
        """Service should start with 18 SLA definitions."""
        slas = service.list_slas()
        assert len(slas) == 18

    def test_seed_benchmarks_populated(self, service: PerformanceBenchmarkService):
        """Service should start with 36 benchmark results."""
        benchmarks = service.get_benchmarks(limit=500)
        assert len(benchmarks) == 36

    def test_seed_suites_populated(self, service: PerformanceBenchmarkService):
        """Service should start with 2 benchmark suites."""
        suites = service.list_suites()
        assert len(suites) == 2

    def test_seed_sla_categories_covered(self, service: PerformanceBenchmarkService):
        """SLAs should cover all benchmark categories."""
        slas = service.list_slas()
        categories = {s.category for s in slas}
        assert BenchmarkCategory.API_LATENCY in categories
        assert BenchmarkCategory.DATABASE_QUERY in categories
        assert BenchmarkCategory.NLP_PIPELINE in categories
        assert BenchmarkCategory.FHIR_IMPORT in categories
        assert BenchmarkCategory.TRIAL_SCREENING in categories
        assert BenchmarkCategory.KG_QUERY in categories
        assert BenchmarkCategory.DOCUMENT_PROCESSING in categories
        assert BenchmarkCategory.BULK_EXPORT in categories

    def test_seed_suite_names(self, service: PerformanceBenchmarkService):
        """Suites should have expected names."""
        suites = service.list_suites()
        names = {s.name for s in suites}
        assert "Core API Suite" in names
        assert "Clinical Pipeline Suite" in names

    def test_seed_benchmarks_have_valid_fields(self, service: PerformanceBenchmarkService):
        """All seed benchmark results should have positive latency values."""
        benchmarks = service.get_benchmarks(limit=500)
        for b in benchmarks:
            assert b.p50_ms > 0
            assert b.p95_ms > 0
            assert b.p99_ms > 0
            assert b.p50_ms <= b.p95_ms
            assert b.p95_ms <= b.p99_ms
            assert b.sample_count > 0


# ============================================================================
# Benchmark CRUD Tests
# ============================================================================


class TestBenchmarkCRUD:
    """Tests for benchmark recording and querying."""

    def test_record_benchmark(self, service: PerformanceBenchmarkService):
        """Recording a benchmark should return a valid result."""
        result = service.record_benchmark(
            category=BenchmarkCategory.API_LATENCY,
            operation_name="GET /test",
            results_dict={
                "p50_ms": 10,
                "p95_ms": 50,
                "p99_ms": 100,
                "max_ms": 200,
                "min_ms": 2,
                "mean_ms": 30,
                "std_dev_ms": 15,
                "throughput_rps": 500,
                "sample_count": 1000,
                "environment": "dev",
                "version": "2.0.0",
            },
        )
        assert result.id is not None
        assert result.category == BenchmarkCategory.API_LATENCY
        assert result.operation_name == "GET /test"
        assert result.p50_ms == 10
        assert result.p99_ms == 100
        assert result.version == "2.0.0"

    def test_record_increases_total(self, service: PerformanceBenchmarkService):
        """Recording a benchmark should increase total count."""
        initial = len(service.get_benchmarks(limit=500))
        service.record_benchmark(
            BenchmarkCategory.KG_QUERY,
            "test_op",
            {"p50_ms": 5, "p95_ms": 20, "p99_ms": 50, "max_ms": 100, "min_ms": 1, "mean_ms": 15},
        )
        assert len(service.get_benchmarks(limit=500)) == initial + 1

    def test_get_benchmark_by_id(self, service: PerformanceBenchmarkService):
        """Should retrieve a benchmark by its ID."""
        result = service.record_benchmark(
            BenchmarkCategory.NLP_PIPELINE,
            "test_retrieval",
            {"p50_ms": 100, "p95_ms": 300, "p99_ms": 800, "max_ms": 1500, "min_ms": 20, "mean_ms": 200},
        )
        fetched = service.get_benchmark(result.id)
        assert fetched is not None
        assert fetched.id == result.id
        assert fetched.operation_name == "test_retrieval"

    def test_get_benchmark_not_found(self, service: PerformanceBenchmarkService):
        """Should return None for nonexistent benchmark."""
        assert service.get_benchmark("nonexistent") is None

    def test_filter_by_category(self, service: PerformanceBenchmarkService):
        """Should filter benchmarks by category."""
        results = service.get_benchmarks(category=BenchmarkCategory.API_LATENCY)
        assert all(r.category == BenchmarkCategory.API_LATENCY for r in results)
        assert len(results) > 0

    def test_filter_by_operation(self, service: PerformanceBenchmarkService):
        """Should filter benchmarks by operation name."""
        results = service.get_benchmarks(operation_name="GET /patients")
        assert all(r.operation_name == "GET /patients" for r in results)
        assert len(results) > 0

    def test_filter_by_both(self, service: PerformanceBenchmarkService):
        """Should filter by both category and operation."""
        results = service.get_benchmarks(
            category=BenchmarkCategory.API_LATENCY,
            operation_name="GET /patients",
        )
        assert all(
            r.category == BenchmarkCategory.API_LATENCY and r.operation_name == "GET /patients"
            for r in results
        )

    def test_limit_results(self, service: PerformanceBenchmarkService):
        """Should respect the limit parameter."""
        results = service.get_benchmarks(limit=3)
        assert len(results) <= 3

    def test_results_ordered_most_recent_first(self, service: PerformanceBenchmarkService):
        """Results should be ordered newest first."""
        results = service.get_benchmarks(limit=10)
        for i in range(len(results) - 1):
            assert results[i].measured_at >= results[i + 1].measured_at


# ============================================================================
# SLA CRUD Tests
# ============================================================================


class TestSLACRUD:
    """Tests for SLA definition management."""

    def test_create_sla(self, service: PerformanceBenchmarkService):
        """Should create a new SLA definition."""
        sla = service.create_sla(
            category=BenchmarkCategory.API_LATENCY,
            operation_name="GET /new-endpoint",
            tier=SLATier.GOLD,
            target_p50_ms=30,
            target_p95_ms=100,
            target_p99_ms=400,
            target_throughput_rps=500,
        )
        assert sla.id is not None
        assert sla.category == BenchmarkCategory.API_LATENCY
        assert sla.tier == SLATier.GOLD
        assert sla.target_p99_ms == 400

    def test_get_sla_by_id(self, service: PerformanceBenchmarkService):
        """Should retrieve an SLA by ID."""
        sla = service.create_sla(
            BenchmarkCategory.KG_QUERY, "test_sla_get", SLATier.SILVER, 50, 200, 1000
        )
        fetched = service.get_sla(sla.id)
        assert fetched is not None
        assert fetched.id == sla.id

    def test_get_sla_not_found(self, service: PerformanceBenchmarkService):
        """Should return None for nonexistent SLA."""
        assert service.get_sla("nonexistent") is None

    def test_update_sla(self, service: PerformanceBenchmarkService):
        """Should update SLA fields."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY, "test_update", SLATier.SILVER, 50, 200, 1000
        )
        updated = service.update_sla(sla.id, {"tier": SLATier.GOLD, "target_p99_ms": 400})
        assert updated is not None
        assert updated.tier == SLATier.GOLD
        assert updated.target_p99_ms == 400
        # Unchanged fields preserved
        assert updated.target_p50_ms == 50

    def test_update_sla_not_found(self, service: PerformanceBenchmarkService):
        """Should return None when updating nonexistent SLA."""
        assert service.update_sla("nonexistent", {"tier": SLATier.GOLD}) is None

    def test_delete_sla(self, service: PerformanceBenchmarkService):
        """Should delete an SLA definition."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY, "test_delete", SLATier.BRONZE, 100, 500, 5000
        )
        assert service.delete_sla(sla.id) is True
        assert service.get_sla(sla.id) is None

    def test_delete_sla_not_found(self, service: PerformanceBenchmarkService):
        """Should return False when deleting nonexistent SLA."""
        assert service.delete_sla("nonexistent") is False

    def test_list_slas_all(self, service: PerformanceBenchmarkService):
        """Should list all SLAs."""
        slas = service.list_slas()
        assert len(slas) == 18  # seed data

    def test_list_slas_by_category(self, service: PerformanceBenchmarkService):
        """Should filter SLAs by category."""
        slas = service.list_slas(category=BenchmarkCategory.API_LATENCY)
        assert all(s.category == BenchmarkCategory.API_LATENCY for s in slas)
        assert len(slas) >= 3

    def test_sla_tiers_present(self, service: PerformanceBenchmarkService):
        """SLA seed data should include all tier levels."""
        slas = service.list_slas()
        tiers = {s.tier for s in slas}
        assert SLATier.PLATINUM in tiers
        assert SLATier.GOLD in tiers
        assert SLATier.SILVER in tiers
        assert SLATier.BRONZE in tiers


# ============================================================================
# SLA Compliance Tests
# ============================================================================


class TestSLACompliance:
    """Tests for SLA compliance checking."""

    def test_check_compliance_existing_sla(self, service: PerformanceBenchmarkService):
        """Should return compliance status for an existing SLA."""
        slas = service.list_slas()
        status = service.check_sla_compliance(slas[0].id)
        assert status is not None
        assert status.sla_id == slas[0].id
        assert isinstance(status.p50_met, bool)
        assert isinstance(status.overall_compliance, bool)
        assert 0 <= status.compliance_pct_30d <= 100

    def test_check_compliance_not_found(self, service: PerformanceBenchmarkService):
        """Should return None for nonexistent SLA."""
        assert service.check_sla_compliance("nonexistent") is None

    def test_check_compliance_no_benchmarks(self, service: PerformanceBenchmarkService):
        """SLA with no matching benchmarks should be compliant by default."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY,
            "no_data_operation",
            SLATier.GOLD,
            30, 100, 400,
        )
        status = service.check_sla_compliance(sla.id)
        assert status is not None
        assert status.overall_compliance is True
        assert status.compliance_pct_30d == 100.0

    def test_check_compliance_met(self, service: PerformanceBenchmarkService):
        """SLA should be met when benchmarks are within targets."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY,
            "fast_op",
            SLATier.GOLD,
            100, 400, 900,
            target_throughput_rps=10,
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "fast_op",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 5, "mean_ms": 100, "throughput_rps": 50},
        )
        status = service.check_sla_compliance(sla.id)
        assert status is not None
        assert status.p50_met is True
        assert status.p95_met is True
        assert status.p99_met is True
        assert status.throughput_met is True
        assert status.overall_compliance is True

    def test_check_compliance_breached(self, service: PerformanceBenchmarkService):
        """SLA should be breached when benchmarks exceed targets."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY,
            "slow_op",
            SLATier.PLATINUM,
            10, 40, 80,
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "slow_op",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 5, "mean_ms": 100},
        )
        status = service.check_sla_compliance(sla.id)
        assert status is not None
        assert status.p50_met is False
        assert status.p99_met is False
        assert status.overall_compliance is False

    def test_check_compliance_throughput_breached(self, service: PerformanceBenchmarkService):
        """SLA should be breached when throughput is below target."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY,
            "low_tput_op",
            SLATier.GOLD,
            100, 400, 900,
            target_throughput_rps=1000,
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "low_tput_op",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 5, "mean_ms": 100, "throughput_rps": 50},
        )
        status = service.check_sla_compliance(sla.id)
        assert status is not None
        assert status.throughput_met is False
        assert status.overall_compliance is False

    def test_batch_compliance_check(self, service: PerformanceBenchmarkService):
        """Batch compliance check should cover all SLAs."""
        summary = service.check_all_sla_compliance()
        assert summary.total_slas == 18
        assert summary.compliant + summary.non_compliant == summary.total_slas
        assert 0 <= summary.compliance_rate <= 100

    def test_breach_count_tracking(self, service: PerformanceBenchmarkService):
        """Should track breach count and last breach timestamp."""
        sla = service.create_sla(
            BenchmarkCategory.API_LATENCY,
            "breach_tracking_op",
            SLATier.PLATINUM,
            10, 40, 80,
        )
        # Record a breaching benchmark
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "breach_tracking_op",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 5, "mean_ms": 100},
        )
        status = service.check_sla_compliance(sla.id)
        assert status is not None
        assert status.breach_count_30d >= 1
        assert status.last_breach is not None


# ============================================================================
# Trend Analysis Tests
# ============================================================================


class TestTrendAnalysis:
    """Tests for performance trend analysis."""

    def test_trend_for_existing_operation(self, service: PerformanceBenchmarkService):
        """Should return trend data for operations with benchmarks."""
        trend = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "GET /patients", days=30
        )
        assert trend.category == BenchmarkCategory.API_LATENCY
        assert trend.operation_name == "GET /patients"
        assert len(trend.data_points) > 0

    def test_trend_for_nonexistent_operation(self, service: PerformanceBenchmarkService):
        """Should return empty trend for unknown operations."""
        trend = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "nonexistent", days=30
        )
        assert len(trend.data_points) == 0
        assert trend.trend_direction == TrendDirection.STABLE
        assert trend.regression_detected is False

    def test_trend_data_points_chronological(self, service: PerformanceBenchmarkService):
        """Data points should be in chronological order."""
        trend = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "GET /patients", days=365
        )
        for i in range(len(trend.data_points) - 1):
            assert trend.data_points[i].timestamp <= trend.data_points[i + 1].timestamp

    def test_trend_degrading_detected(self, service: PerformanceBenchmarkService):
        """Should detect degradation when p99 increases significantly."""
        # Record an initial fast result
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "degrading_test",
            {"p50_ms": 10, "p95_ms": 40, "p99_ms": 80, "max_ms": 150, "min_ms": 2, "mean_ms": 25},
        )
        # Record a much slower result
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "degrading_test",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 10, "mean_ms": 100},
        )
        trend = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "degrading_test", days=30
        )
        assert trend.trend_direction == TrendDirection.DEGRADING
        assert trend.regression_detected is True

    def test_trend_improving_detected(self, service: PerformanceBenchmarkService):
        """Should detect improvement when p99 decreases significantly."""
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "improving_test",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 10, "mean_ms": 100},
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "improving_test",
            {"p50_ms": 10, "p95_ms": 40, "p99_ms": 80, "max_ms": 150, "min_ms": 2, "mean_ms": 25},
        )
        trend = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "improving_test", days=30
        )
        assert trend.trend_direction == TrendDirection.IMPROVING

    def test_trend_stable_detected(self, service: PerformanceBenchmarkService):
        """Should detect stability when p99 remains similar."""
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "stable_test",
            {"p50_ms": 10, "p95_ms": 40, "p99_ms": 100, "max_ms": 150, "min_ms": 2, "mean_ms": 25},
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "stable_test",
            {"p50_ms": 11, "p95_ms": 42, "p99_ms": 105, "max_ms": 155, "min_ms": 3, "mean_ms": 26},
        )
        trend = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "stable_test", days=30
        )
        assert trend.trend_direction == TrendDirection.STABLE
        assert trend.regression_detected is False

    def test_trend_window_filtering(self, service: PerformanceBenchmarkService):
        """Should only include data points within the specified window."""
        trend_1d = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "GET /patients", days=1
        )
        trend_365d = service.get_performance_trends(
            BenchmarkCategory.API_LATENCY, "GET /patients", days=365
        )
        assert len(trend_365d.data_points) >= len(trend_1d.data_points)


# ============================================================================
# Regression Detection Tests
# ============================================================================


class TestRegressionDetection:
    """Tests for regression detection across all operations."""

    def test_detect_regressions_returns_report(self, service: PerformanceBenchmarkService):
        """Should return a regression report."""
        report = service.detect_regressions()
        assert report.total_operations_scanned > 0
        assert isinstance(report.regressions_found, int)
        assert isinstance(report.alerts, list)

    def test_regression_alert_fields(self, service: PerformanceBenchmarkService):
        """Regression alerts should have all required fields."""
        # Create a regression
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "regress_field_test",
            {"p50_ms": 10, "p95_ms": 40, "p99_ms": 80, "max_ms": 150, "min_ms": 2, "mean_ms": 25},
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "regress_field_test",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 10, "mean_ms": 100},
        )
        report = service.detect_regressions()
        matching = [a for a in report.alerts if a.operation_name == "regress_field_test"]
        assert len(matching) == 1
        alert = matching[0]
        assert alert.previous_p99 > 0
        assert alert.current_p99 > alert.previous_p99
        assert alert.change_pct > 20
        assert alert.detected_at is not None

    def test_no_regression_for_stable(self, service: PerformanceBenchmarkService):
        """Stable operations should not generate regression alerts."""
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "no_regress_test",
            {"p50_ms": 10, "p95_ms": 40, "p99_ms": 100, "max_ms": 150, "min_ms": 2, "mean_ms": 25},
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "no_regress_test",
            {"p50_ms": 11, "p95_ms": 42, "p99_ms": 105, "max_ms": 155, "min_ms": 3, "mean_ms": 26},
        )
        report = service.detect_regressions()
        matching = [a for a in report.alerts if a.operation_name == "no_regress_test"]
        assert len(matching) == 0


# ============================================================================
# Benchmark Suite Tests
# ============================================================================


class TestBenchmarkSuites:
    """Tests for benchmark suite management and execution."""

    def test_create_suite(self, service: PerformanceBenchmarkService):
        """Should create a new benchmark suite."""
        suite = service.create_suite(
            name="Test Suite",
            description="A test suite",
            benchmarks=[
                {"category": "api_latency", "operation_name": "GET /test"},
            ],
            schedule_cron="0 0 * * *",
        )
        assert suite.id is not None
        assert suite.name == "Test Suite"
        assert len(suite.benchmarks) == 1
        assert suite.schedule_cron == "0 0 * * *"

    def test_get_suite_by_id(self, service: PerformanceBenchmarkService):
        """Should retrieve a suite by ID."""
        suite = service.create_suite(name="Get Test", benchmarks=[])
        fetched = service.get_suite(suite.id)
        assert fetched is not None
        assert fetched.id == suite.id

    def test_get_suite_not_found(self, service: PerformanceBenchmarkService):
        """Should return None for nonexistent suite."""
        assert service.get_suite("nonexistent") is None

    def test_list_suites(self, service: PerformanceBenchmarkService):
        """Should list all suites including seed suites."""
        suites = service.list_suites()
        assert len(suites) >= 2

    def test_run_suite(self, service: PerformanceBenchmarkService):
        """Running a suite should produce results for each entry."""
        suites = service.list_suites()
        core_suite = [s for s in suites if s.name == "Core API Suite"][0]
        result = service.run_suite(core_suite.id)
        assert result is not None
        assert result.suite_id == core_suite.id
        assert len(result.results) == len(core_suite.benchmarks)
        assert result.started_at <= result.completed_at

    def test_run_suite_not_found(self, service: PerformanceBenchmarkService):
        """Running a nonexistent suite should return None."""
        assert service.run_suite("nonexistent") is None

    def test_run_suite_updates_last_run(self, service: PerformanceBenchmarkService):
        """Running a suite should update its last_run timestamp."""
        suites = service.list_suites()
        suite = suites[0]
        old_last_run = suite.last_run
        service.run_suite(suite.id)
        updated = service.get_suite(suite.id)
        assert updated is not None
        assert updated.last_run is not None
        if old_last_run is not None:
            assert updated.last_run >= old_last_run

    def test_run_suite_generates_valid_benchmarks(self, service: PerformanceBenchmarkService):
        """Suite run results should be valid benchmarks."""
        suites = service.list_suites()
        result = service.run_suite(suites[0].id)
        assert result is not None
        for r in result.results:
            assert r.p50_ms > 0
            assert r.p99_ms > 0
            assert r.sample_count > 0

    def test_run_suite_records_to_store(self, service: PerformanceBenchmarkService):
        """Suite run should record benchmarks to the global store."""
        initial = len(service.get_benchmarks(limit=1000))
        suites = service.list_suites()
        suite = suites[0]
        service.run_suite(suite.id)
        final = len(service.get_benchmarks(limit=1000))
        assert final == initial + len(suite.benchmarks)


# ============================================================================
# Version Comparison Tests
# ============================================================================


class TestVersionComparison:
    """Tests for version-to-version performance comparison."""

    def test_compare_existing_versions(self, service: PerformanceBenchmarkService):
        """Should compare performance between two versions from seed data."""
        comparison = service.compare_versions("1.0.0", "1.1.0")
        assert comparison.version_a == "1.0.0"
        assert comparison.version_b == "1.1.0"
        assert comparison.total_operations > 0
        assert comparison.improved + comparison.degraded + comparison.unchanged == comparison.total_operations

    def test_compare_has_entries(self, service: PerformanceBenchmarkService):
        """Comparison should include per-operation entries."""
        comparison = service.compare_versions("1.0.0", "1.1.0")
        assert len(comparison.entries) == comparison.total_operations
        for entry in comparison.entries:
            assert entry.operation_name is not None
            assert entry.category is not None

    def test_compare_delta_calculation(self, service: PerformanceBenchmarkService):
        """Delta values should be correctly calculated."""
        comparison = service.compare_versions("1.0.0", "1.1.0")
        for entry in comparison.entries:
            if entry.version_a_p99 > 0 and entry.version_b_p99 > 0:
                expected_delta = entry.version_b_p99 - entry.version_a_p99
                assert abs(entry.delta_p99_ms - expected_delta) < 0.1

    def test_compare_nonexistent_version(self, service: PerformanceBenchmarkService):
        """Comparing with a nonexistent version should return empty entries."""
        comparison = service.compare_versions("1.0.0", "99.99.99")
        # Should still return operations from version_a with zero for version_b
        assert comparison.total_operations > 0

    def test_compare_improvement_flag(self, service: PerformanceBenchmarkService):
        """Improvement flag should be correct."""
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "compare_imp_test",
            {"p50_ms": 50, "p95_ms": 200, "p99_ms": 500, "max_ms": 800, "min_ms": 10, "mean_ms": 100, "version": "a.0"},
        )
        service.record_benchmark(
            BenchmarkCategory.API_LATENCY,
            "compare_imp_test",
            {"p50_ms": 10, "p95_ms": 40, "p99_ms": 80, "max_ms": 150, "min_ms": 2, "mean_ms": 25, "version": "b.0"},
        )
        comparison = service.compare_versions("a.0", "b.0")
        matching = [e for e in comparison.entries if e.operation_name == "compare_imp_test"]
        assert len(matching) == 1
        assert matching[0].improved is True
        assert matching[0].delta_p99_ms < 0


# ============================================================================
# Performance Metrics Tests
# ============================================================================


class TestPerformanceMetrics:
    """Tests for aggregate performance metrics."""

    def test_metrics_structure(self, service: PerformanceBenchmarkService):
        """Metrics should have all expected fields."""
        metrics = service.get_metrics()
        assert metrics.total_slas == 18
        assert metrics.total_benchmarks >= 36
        assert metrics.categories_covered == 8
        assert metrics.mean_p99_across_all > 0

    def test_metrics_compliance_rate(self, service: PerformanceBenchmarkService):
        """Compliance rate should be between 0 and 100."""
        metrics = service.get_metrics()
        assert 0 <= metrics.sla_compliance_rate <= 100

    def test_metrics_top_performers(self, service: PerformanceBenchmarkService):
        """Should identify top-performing operations."""
        metrics = service.get_metrics()
        assert len(metrics.top_performers) > 0
        # Top performers should have lower p99 than worst
        if metrics.worst_performers:
            assert metrics.top_performers[0].latest_p99 <= metrics.worst_performers[-1].latest_p99

    def test_metrics_worst_performers(self, service: PerformanceBenchmarkService):
        """Should identify worst-performing operations."""
        metrics = service.get_metrics()
        assert len(metrics.worst_performers) > 0

    def test_metrics_categories_covered(self, service: PerformanceBenchmarkService):
        """All 8 categories should be covered."""
        metrics = service.get_metrics()
        assert metrics.categories_covered == 8


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestBenchmarkAPI:
    """Tests for benchmark API endpoints."""

    @pytest.mark.anyio
    async def test_list_benchmarks_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/benchmarks")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "results" in data
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_benchmarks_with_category_filter(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/performance-benchmarks/benchmarks",
            params={"category": "api_latency"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert r["category"] == "api_latency"

    @pytest.mark.anyio
    async def test_record_benchmark_endpoint(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/performance-benchmarks/benchmarks",
            json={
                "category": "api_latency",
                "operation_name": "POST /api-test",
                "p50_ms": 15,
                "p95_ms": 60,
                "p99_ms": 120,
                "max_ms": 250,
                "min_ms": 3,
                "mean_ms": 35,
                "std_dev_ms": 18,
                "throughput_rps": 800,
                "sample_count": 2000,
                "environment": "dev",
                "version": "2.0.0",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["operation_name"] == "POST /api-test"
        assert data["p99_ms"] == 120

    @pytest.mark.anyio
    async def test_get_benchmark_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/benchmarks/nonexistent")
        assert resp.status_code == 404


class TestSLAAPI:
    """Tests for SLA API endpoints."""

    @pytest.mark.anyio
    async def test_list_slas_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/slas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 18

    @pytest.mark.anyio
    async def test_create_sla_endpoint(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/performance-benchmarks/slas",
            json={
                "category": "kg_query",
                "operation_name": "new_traversal",
                "tier": "gold",
                "target_p50_ms": 25,
                "target_p95_ms": 100,
                "target_p99_ms": 350,
                "target_throughput_rps": 500,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["operation_name"] == "new_traversal"
        assert data["tier"] == "gold"

    @pytest.mark.anyio
    async def test_get_sla_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/slas/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_sla_endpoint(self, client: AsyncClient):
        # Create first
        create_resp = await client.post(
            "/api/v1/performance-benchmarks/slas",
            json={
                "category": "api_latency",
                "operation_name": "update_test",
                "tier": "silver",
                "target_p50_ms": 50,
                "target_p95_ms": 200,
                "target_p99_ms": 1000,
            },
        )
        sla_id = create_resp.json()["id"]
        # Update
        resp = await client.put(
            f"/api/v1/performance-benchmarks/slas/{sla_id}",
            json={"tier": "gold", "target_p99_ms": 400},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "gold"
        assert data["target_p99_ms"] == 400

    @pytest.mark.anyio
    async def test_delete_sla_endpoint(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/v1/performance-benchmarks/slas",
            json={
                "category": "api_latency",
                "operation_name": "delete_test",
                "tier": "bronze",
                "target_p50_ms": 100,
                "target_p95_ms": 500,
                "target_p99_ms": 5000,
            },
        )
        sla_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/performance-benchmarks/slas/{sla_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.anyio
    async def test_delete_sla_not_found(self, client: AsyncClient):
        resp = await client.delete("/api/v1/performance-benchmarks/slas/nonexistent")
        assert resp.status_code == 404


class TestComplianceAPI:
    """Tests for SLA compliance API endpoints."""

    @pytest.mark.anyio
    async def test_check_all_compliance(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_slas" in data
        assert "compliance_rate" in data
        assert "statuses" in data

    @pytest.mark.anyio
    async def test_check_single_sla_compliance(self, client: AsyncClient):
        # Get first SLA
        sla_resp = await client.get("/api/v1/performance-benchmarks/slas")
        sla_id = sla_resp.json()["slas"][0]["id"]
        resp = await client.get(f"/api/v1/performance-benchmarks/slas/{sla_id}/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sla_id"] == sla_id
        assert "overall_compliance" in data

    @pytest.mark.anyio
    async def test_compliance_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/slas/nonexistent/compliance")
        assert resp.status_code == 404


class TestTrendsAPI:
    """Tests for trend analysis API endpoints."""

    @pytest.mark.anyio
    async def test_get_trends(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/performance-benchmarks/trends",
            params={
                "category": "api_latency",
                "operation": "GET /patients",
                "days": 30,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "api_latency"
        assert data["operation_name"] == "GET /patients"
        assert "data_points" in data
        assert "trend_direction" in data

    @pytest.mark.anyio
    async def test_detect_regressions_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/regressions")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_operations_scanned" in data
        assert "regressions_found" in data
        assert "alerts" in data


class TestSuitesAPI:
    """Tests for benchmark suite API endpoints."""

    @pytest.mark.anyio
    async def test_list_suites(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/suites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_create_suite(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/performance-benchmarks/suites",
            json={
                "name": "API Test Suite",
                "description": "Suite created via API test",
                "benchmarks": [
                    {"category": "api_latency", "operation_name": "GET /patients"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API Test Suite"

    @pytest.mark.anyio
    async def test_get_suite_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/suites/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_run_suite_endpoint(self, client: AsyncClient):
        # Get first suite
        list_resp = await client.get("/api/v1/performance-benchmarks/suites")
        suite_id = list_resp.json()["suites"][0]["id"]
        resp = await client.post(f"/api/v1/performance-benchmarks/suites/{suite_id}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suite_id"] == suite_id
        assert len(data["results"]) > 0

    @pytest.mark.anyio
    async def test_run_suite_not_found(self, client: AsyncClient):
        resp = await client.post("/api/v1/performance-benchmarks/suites/nonexistent/run")
        assert resp.status_code == 404


class TestVersionComparisonAPI:
    """Tests for version comparison API endpoints."""

    @pytest.mark.anyio
    async def test_compare_versions_endpoint(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/performance-benchmarks/compare",
            params={"version_a": "1.0.0", "version_b": "1.1.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version_a"] == "1.0.0"
        assert data["version_b"] == "1.1.0"
        assert data["total_operations"] > 0


class TestMetricsAPI:
    """Tests for metrics API endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/performance-benchmarks/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_slas"] == 18
        assert data["total_benchmarks"] >= 36
        assert "sla_compliance_rate" in data
        assert "top_performers" in data
        assert "worst_performers" in data
