"""Unit tests for the load testing framework.

These tests validate the framework logic (config validation, percentile
calculations, ramp-up scheduling, SLA evaluation, regression detection,
and report generation) **without** making any real HTTP requests.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.tests.load.load_test_runner import (
    EndpointConfig,
    HttpResponse,
    LoadTestConfig,
    LoadTestResult,
    LoadTestRunner,
    aggregate_results,
    compute_percentile,
    compute_ramp_schedule,
    generate_markdown_report,
    results_to_json,
)
from backend.tests.load.performance_benchmarks import (
    DEFAULT_SLA_TARGETS,
    RegressionCheck,
    SLAEvaluation,
    SLATarget,
    detect_all_regressions,
    detect_regression,
    evaluate_all_slas,
    evaluate_sla,
    find_sla_target,
    load_baseline,
    regression_report_markdown,
    save_baseline,
)
from backend.tests.load.scenarios import (
    DEFAULT_ENDPOINTS,
    baseline_test,
    get_scenario,
    list_scenarios,
    smoke_test,
    spike_test,
    stress_test,
)


# ============================================================================
# Helpers
# ============================================================================

class MockHttpClient:
    """A fake HTTP client that records calls and returns configurable responses."""

    def __init__(
        self,
        status_code: int = 200,
        latency_ms: float = 10.0,
        error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.error = error
        self.requests: list[dict[str, Any]] = []
        self._closed = False

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        timeout: float = 30.0,
    ) -> HttpResponse:
        self.requests.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
        })
        if self.error:
            raise self.error
        return HttpResponse(status_code=self.status_code, elapsed_ms=self.latency_ms)

    async def aclose(self) -> None:
        self._closed = True


# ============================================================================
# 1. LoadTestConfig validation
# ============================================================================

class TestLoadTestConfigValidation:
    """Verify that invalid configurations are rejected early."""

    def test_valid_config(self) -> None:
        cfg = LoadTestConfig(
            base_url="http://localhost:8000",
            endpoints=[EndpointConfig()],
            concurrent_users=5,
            duration_seconds=10,
        )
        assert cfg.concurrent_users == 5

    def test_zero_users_rejected(self) -> None:
        with pytest.raises(ValueError, match="concurrent_users"):
            LoadTestConfig(concurrent_users=0)

    def test_negative_users_rejected(self) -> None:
        with pytest.raises(ValueError, match="concurrent_users"):
            LoadTestConfig(concurrent_users=-1)

    def test_zero_duration_rejected(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds"):
            LoadTestConfig(duration_seconds=0)

    def test_negative_ramp_up_rejected(self) -> None:
        with pytest.raises(ValueError, match="ramp_up_seconds"):
            LoadTestConfig(ramp_up_seconds=-1)

    def test_negative_think_time_rejected(self) -> None:
        with pytest.raises(ValueError, match="think_time_seconds"):
            LoadTestConfig(think_time_seconds=-1)

    def test_invalid_method_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            EndpointConfig(method="PATCH")

    def test_path_without_slash_rejected(self) -> None:
        with pytest.raises(ValueError, match="Path must start with"):
            EndpointConfig(path="api/v1/health")

    def test_endpoint_auto_name(self) -> None:
        ep = EndpointConfig(method="POST", path="/api/v1/trials")
        assert ep.name == "POST /api/v1/trials"

    def test_endpoint_custom_name(self) -> None:
        ep = EndpointConfig(method="GET", path="/api/v1/health", name="HealthCheck")
        assert ep.name == "HealthCheck"


# ============================================================================
# 2. Percentile calculation
# ============================================================================

class TestPercentileCalculation:
    """Verify p50, p95, p99 computations."""

    def test_empty_list(self) -> None:
        assert compute_percentile([], 50) == 0.0

    def test_single_value(self) -> None:
        assert compute_percentile([42.0], 50) == 42.0
        assert compute_percentile([42.0], 99) == 42.0

    def test_p50_even_count(self) -> None:
        data = sorted([10.0, 20.0, 30.0, 40.0])
        p50 = compute_percentile(data, 50)
        assert p50 == pytest.approx(25.0)

    def test_p95_large_set(self) -> None:
        # 100 values: 1..100
        data = [float(i) for i in range(1, 101)]
        p95 = compute_percentile(data, 95)
        # 95th percentile of 1..100 with linear interpolation
        assert 94.0 <= p95 <= 96.0

    def test_p99_large_set(self) -> None:
        data = [float(i) for i in range(1, 101)]
        p99 = compute_percentile(data, 99)
        assert 98.0 <= p99 <= 100.0


# ============================================================================
# 3. Result aggregation
# ============================================================================

class TestResultAggregation:
    """Test aggregate_results correctly summarises raw data."""

    def test_basic_aggregation(self) -> None:
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        codes = [200, 200, 200, 500, 200]
        errors = ["HTTP 500"]
        result = aggregate_results(
            "GET /health", latencies, codes, errors,
            elapsed_seconds=5.0, sla_target_ms=100.0,
        )
        assert result.total_requests == 5
        assert result.successful == 4
        assert result.failed == 1
        assert result.throughput_rps == 1.0
        assert result.error_rate == 20.0
        assert result.latency_min_ms == 10.0
        assert result.latency_max_ms == 50.0

    def test_all_successful(self) -> None:
        latencies = [5.0, 10.0, 15.0]
        codes = [200, 201, 204]
        result = aggregate_results(
            "ep", latencies, codes, [],
            elapsed_seconds=3.0, sla_target_ms=100.0,
        )
        assert result.successful == 3
        assert result.failed == 0
        assert result.error_rate == 0.0

    def test_empty_latencies(self) -> None:
        result = aggregate_results("ep", [], [], [], 1.0, 100.0)
        assert result.total_requests == 0
        assert result.latency_avg_ms == 0.0
        assert result.throughput_rps == 0.0


# ============================================================================
# 4. Throughput calculation
# ============================================================================

class TestThroughputCalculation:
    def test_throughput_rps(self) -> None:
        result = aggregate_results(
            "ep", [10.0] * 100, [200] * 100, [], 10.0, 500.0,
        )
        assert result.throughput_rps == pytest.approx(10.0)

    def test_zero_elapsed(self) -> None:
        result = aggregate_results("ep", [10.0], [200], [], 0.0, 500.0)
        assert result.throughput_rps == 0.0


# ============================================================================
# 5. Ramp-up schedule generation
# ============================================================================

class TestRampUpSchedule:
    def test_zero_ramp_up(self) -> None:
        schedule = compute_ramp_schedule(10, 0)
        assert len(schedule) == 1
        assert schedule[0] == (0.0, 10)

    def test_gradual_ramp_up(self) -> None:
        schedule = compute_ramp_schedule(5, 10.0)
        assert len(schedule) == 5
        # First user starts at t=0
        assert schedule[0][0] == 0.0
        # Each step adds 1 user
        assert all(count == 1 for _, count in schedule)
        # Delays are evenly spaced
        delays = [delay for delay, _ in schedule]
        assert delays[-1] == pytest.approx(8.0)  # (10/5)*4

    def test_zero_users(self) -> None:
        schedule = compute_ramp_schedule(0, 10.0)
        assert schedule == []

    def test_single_user(self) -> None:
        schedule = compute_ramp_schedule(1, 5.0)
        assert len(schedule) == 1
        assert schedule[0] == (0.0, 1)


# ============================================================================
# 6. SLA pass/fail evaluation
# ============================================================================

class TestSLAEvaluation:
    def test_sla_pass(self) -> None:
        result = LoadTestResult(
            endpoint="Health Check",
            latency_p95_ms=30.0,
            latency_p99_ms=45.0,
            error_rate=0.0,
        )
        ev = evaluate_sla(result)
        assert ev.overall_passed is True
        assert ev.p95_passed is True
        assert ev.p99_passed is True

    def test_sla_fail_p95(self) -> None:
        result = LoadTestResult(
            endpoint="Health Check",
            latency_p95_ms=80.0,
            latency_p99_ms=90.0,
            error_rate=0.0,
        )
        ev = evaluate_sla(result)
        assert ev.p95_passed is False
        assert ev.overall_passed is False

    def test_sla_fail_error_rate(self) -> None:
        result = LoadTestResult(
            endpoint="List Patients",
            latency_p95_ms=100.0,
            latency_p99_ms=200.0,
            error_rate=5.0,
        )
        ev = evaluate_sla(result)
        assert ev.error_rate_passed is False
        assert ev.overall_passed is False

    def test_no_matching_sla_passes(self) -> None:
        result = LoadTestResult(
            endpoint="Unknown Endpoint",
            latency_p95_ms=9999.0,
        )
        ev = evaluate_sla(result)
        assert ev.overall_passed is True
        assert "No SLA target defined" in ev.details

    def test_evaluate_all_slas(self) -> None:
        results = [
            LoadTestResult(endpoint="Health Check", latency_p95_ms=20.0, latency_p99_ms=30.0, error_rate=0.0),
            LoadTestResult(endpoint="List Patients", latency_p95_ms=800.0, latency_p99_ms=900.0, error_rate=0.0),
        ]
        evals = evaluate_all_slas(results)
        assert len(evals) == 2
        assert evals[0].overall_passed is True
        assert evals[1].overall_passed is False  # p95 800 > 500


# ============================================================================
# 7. Report generation
# ============================================================================

class TestReportGeneration:
    def test_markdown_report_contains_table(self) -> None:
        results = [
            LoadTestResult(
                endpoint="GET /health",
                total_requests=100,
                successful=98,
                failed=2,
                latency_p50_ms=10.0,
                latency_p95_ms=25.0,
                latency_p99_ms=40.0,
                throughput_rps=50.0,
                error_rate=2.0,
                sla_target_ms=50.0,
                sla_passed=True,
            ),
        ]
        config = LoadTestConfig(concurrent_users=10, duration_seconds=30)
        report = generate_markdown_report(results, config)
        assert "# Load Test Report" in report
        assert "GET /health" in report
        assert "PASS" in report
        assert "| Endpoint |" in report

    def test_report_shows_failures(self) -> None:
        results = [
            LoadTestResult(
                endpoint="GET /slow",
                sla_passed=False,
                sla_target_ms=100.0,
                latency_p95_ms=500.0,
            ),
        ]
        config = LoadTestConfig()
        report = generate_markdown_report(results, config)
        assert "FAIL" in report
        assert "FAILURES DETECTED" in report

    def test_json_serialization(self) -> None:
        results = [
            LoadTestResult(endpoint="ep1", total_requests=10, successful=9, failed=1),
        ]
        data = results_to_json(results)
        assert len(data) == 1
        assert data[0]["endpoint"] == "ep1"
        assert data[0]["total_requests"] == 10
        # Should be JSON-serializable
        json.dumps(data)


# ============================================================================
# 8. Regression detection
# ============================================================================

class TestRegressionDetection:
    def test_no_regression(self) -> None:
        current = LoadTestResult(endpoint="ep", latency_p95_ms=100.0)
        baseline = {"latency_p95_ms": 95.0}
        check = detect_regression(current, baseline)
        assert check.severity == "ok"

    def test_warning_regression(self) -> None:
        current = LoadTestResult(endpoint="ep", latency_p95_ms=130.0)
        baseline = {"latency_p95_ms": 100.0}
        check = detect_regression(current, baseline)
        assert check.severity == "warning"
        assert check.change_pct == pytest.approx(30.0)

    def test_failure_regression(self) -> None:
        current = LoadTestResult(endpoint="ep", latency_p95_ms=200.0)
        baseline = {"latency_p95_ms": 100.0}
        check = detect_regression(current, baseline)
        assert check.severity == "failure"
        assert check.change_pct == pytest.approx(100.0)

    def test_improvement_is_ok(self) -> None:
        current = LoadTestResult(endpoint="ep", latency_p95_ms=50.0)
        baseline = {"latency_p95_ms": 100.0}
        check = detect_regression(current, baseline)
        assert check.severity == "ok"
        assert check.change_pct < 0

    def test_no_baseline(self) -> None:
        current = LoadTestResult(endpoint="ep", latency_p95_ms=100.0)
        check = detect_regression(current, {})
        assert check.severity == "ok"
        assert "No baseline" in check.message

    def test_detect_all_regressions(self) -> None:
        results = [
            LoadTestResult(endpoint="a", latency_p95_ms=100.0),
            LoadTestResult(endpoint="b", latency_p95_ms=300.0),
        ]
        baselines = {
            "a": {"latency_p95_ms": 90.0},
            "b": {"latency_p95_ms": 100.0},
        }
        checks = detect_all_regressions(results, baselines)
        assert len(checks) == 2
        assert checks[0].severity == "ok"       # 100/90 = ~11% < 20%
        assert checks[1].severity == "failure"   # 300/100 = 200% > 50%

    def test_regression_report_markdown(self) -> None:
        checks = [
            RegressionCheck("ep1", 100.0, 110.0, 10.0, "ok", "OK"),
            RegressionCheck("ep2", 100.0, 200.0, 100.0, "failure", "Regression"),
        ]
        report = regression_report_markdown(checks)
        assert "REGRESSION DETECTED" in report
        assert "ep1" in report
        assert "ep2" in report


# ============================================================================
# 9. Baseline persistence
# ============================================================================

class TestBaselinePersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        results = [
            LoadTestResult(endpoint="ep1", latency_p95_ms=42.0, total_requests=100),
        ]
        p = tmp_path / "baseline.json"
        save_baseline(results, p)
        loaded = load_baseline(p)
        assert "ep1" in loaded
        assert loaded["ep1"]["latency_p95_ms"] == 42.0

    def test_load_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.json"
        loaded = load_baseline(p)
        assert loaded == {}


# ============================================================================
# 10. Runner with mock HTTP client
# ============================================================================

class TestLoadTestRunnerWithMock:
    """Test the async runner using a mock HTTP client (no real network)."""

    def test_runner_collects_results(self) -> None:
        mock_client = MockHttpClient(status_code=200, latency_ms=15.0)
        config = LoadTestConfig(
            endpoints=[EndpointConfig(path="/api/v1/health", sla_ms=50.0)],
            concurrent_users=2,
            duration_seconds=0.3,
            ramp_up_seconds=0,
        )
        runner = LoadTestRunner(config, http_client=mock_client)
        results = asyncio.run(runner.run())
        assert len(results) == 1
        assert results[0].total_requests > 0
        assert results[0].successful > 0
        assert results[0].latency_p95_ms == pytest.approx(15.0)

    def test_runner_handles_errors(self) -> None:
        mock_client = MockHttpClient(error=ConnectionError("refused"))
        config = LoadTestConfig(
            endpoints=[EndpointConfig(path="/api/v1/health")],
            concurrent_users=1,
            duration_seconds=0.2,
            ramp_up_seconds=0,
        )
        runner = LoadTestRunner(config, http_client=mock_client)
        results = asyncio.run(runner.run())
        assert results[0].failed > 0
        assert "ConnectionError" in results[0].errors

    def test_runner_sends_auth_header(self) -> None:
        mock_client = MockHttpClient(status_code=200, latency_ms=5.0)
        config = LoadTestConfig(
            endpoints=[EndpointConfig(path="/api/v1/health")],
            concurrent_users=1,
            duration_seconds=0.2,
            ramp_up_seconds=0,
            auth_token="test-token-abc",
        )
        runner = LoadTestRunner(config, http_client=mock_client)
        asyncio.run(runner.run())
        # At least one request should have been made with the auth header
        assert any(
            r.get("headers", {}).get("Authorization") == "Bearer test-token-abc"
            for r in mock_client.requests
        )

    def test_runner_multiple_endpoints(self) -> None:
        mock_client = MockHttpClient(status_code=200, latency_ms=10.0)
        config = LoadTestConfig(
            endpoints=[
                EndpointConfig(path="/api/v1/health", name="Health"),
                EndpointConfig(path="/api/v1/patients", name="Patients"),
            ],
            concurrent_users=1,
            duration_seconds=0.3,
            ramp_up_seconds=0,
        )
        runner = LoadTestRunner(config, http_client=mock_client)
        results = asyncio.run(runner.run())
        assert len(results) == 2
        names = {r.endpoint for r in results}
        assert names == {"Health", "Patients"}


# ============================================================================
# 11. Scenario registry
# ============================================================================

class TestScenarios:
    def test_list_scenarios(self) -> None:
        names = list_scenarios()
        assert "smoke" in names
        assert "baseline" in names
        assert "stress" in names
        assert "spike" in names

    def test_get_scenario(self) -> None:
        cfg = get_scenario("smoke", base_url="http://test:9000")
        assert cfg.base_url == "http://test:9000"
        assert cfg.concurrent_users == 5

    def test_unknown_scenario_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown scenario"):
            get_scenario("nonexistent")

    def test_smoke_config(self) -> None:
        cfg = smoke_test()
        assert cfg.concurrent_users == 5
        assert cfg.duration_seconds == 30

    def test_baseline_config(self) -> None:
        cfg = baseline_test()
        assert cfg.concurrent_users == 20

    def test_stress_config(self) -> None:
        cfg = stress_test()
        assert cfg.concurrent_users == 100

    def test_spike_config(self) -> None:
        cfg = spike_test()
        assert cfg.concurrent_users == 100
        assert cfg.ramp_up_seconds == 5

    def test_default_endpoints_defined(self) -> None:
        assert len(DEFAULT_ENDPOINTS) == 5
        methods = {ep.method for ep in DEFAULT_ENDPOINTS}
        assert "GET" in methods
        assert "POST" in methods
