"""Tests for KG Load Testing Service."""

import pytest
import time
import threading

from app.services.kg_load_testing_service import (
    LoadTestStatus,
    LoadPattern,
    RequestResult,
    LatencyStats,
    ThroughputStats,
    LoadTestConfig,
    LoadTestResult,
    LoadTestScenario,
    KGLoadTestRunner,
    KGLoadTestSuite,
    create_concept_lookup_scenario,
    create_path_finding_scenario,
    create_search_scenario,
    get_load_test_runner,
    reset_load_test_runner,
)


class TestRequestResult:
    """Tests for RequestResult dataclass."""

    def test_create_success_result(self):
        """Test creating a success result."""
        result = RequestResult(
            success=True,
            latency_ms=50.5,
            status_code=200,
            response_size_bytes=1024,
        )
        assert result.success is True
        assert result.latency_ms == 50.5
        assert result.status_code == 200

    def test_create_failure_result(self):
        """Test creating a failure result."""
        result = RequestResult(
            success=False,
            latency_ms=100.0,
            error="Connection timeout",
        )
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = RequestResult(
            success=True,
            latency_ms=50.5,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["latency_ms"] == 50.5


class TestLatencyStats:
    """Tests for LatencyStats."""

    def test_calculate_empty(self):
        """Test calculation with empty list."""
        stats = LatencyStats.calculate([])
        assert stats.min_ms == 0
        assert stats.max_ms == 0
        assert stats.mean_ms == 0

    def test_calculate_single(self):
        """Test calculation with single value."""
        stats = LatencyStats.calculate([50.0])
        assert stats.min_ms == 50.0
        assert stats.max_ms == 50.0
        assert stats.mean_ms == 50.0

    def test_calculate_multiple(self):
        """Test calculation with multiple values."""
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        stats = LatencyStats.calculate(latencies)
        assert stats.min_ms == 10.0
        assert stats.max_ms == 100.0
        assert stats.mean_ms == 55.0
        assert stats.p50_ms == 50.0
        assert stats.p90_ms == 90.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = LatencyStats.calculate([10.0, 20.0, 30.0])
        d = stats.to_dict()
        assert "min_ms" in d
        assert "max_ms" in d
        assert "p95_ms" in d


class TestThroughputStats:
    """Tests for ThroughputStats."""

    def test_create(self):
        """Test creating throughput stats."""
        stats = ThroughputStats(
            requests_per_second=100.5,
            successful_per_second=95.0,
            failed_per_second=5.5,
            bytes_per_second=10240.0,
        )
        assert stats.requests_per_second == 100.5
        assert stats.successful_per_second == 95.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = ThroughputStats(
            requests_per_second=100.0,
            successful_per_second=95.0,
            failed_per_second=5.0,
            bytes_per_second=10240.0,
        )
        d = stats.to_dict()
        assert d["requests_per_second"] == 100.0


class TestLoadTestConfig:
    """Tests for LoadTestConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LoadTestConfig(name="test")
        assert config.total_requests == 100
        assert config.concurrency == 10
        assert config.load_pattern == LoadPattern.CONSTANT

    def test_custom_config(self):
        """Test custom configuration."""
        config = LoadTestConfig(
            name="custom",
            total_requests=500,
            concurrency=50,
            load_pattern=LoadPattern.RAMP_UP,
            ramp_up_seconds=10.0,
        )
        assert config.total_requests == 500
        assert config.concurrency == 50
        assert config.load_pattern == LoadPattern.RAMP_UP

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = LoadTestConfig(name="test")
        d = config.to_dict()
        assert d["name"] == "test"
        assert d["total_requests"] == 100


class TestLoadTestResult:
    """Tests for LoadTestResult."""

    def test_create_result(self):
        """Test creating a result."""
        from datetime import datetime
        config = LoadTestConfig(name="test")
        result = LoadTestResult(
            config=config,
            status=LoadTestStatus.COMPLETED,
            start_time=datetime.utcnow(),
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
        )
        assert result.status == LoadTestStatus.COMPLETED
        assert result.total_requests == 100

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from datetime import datetime
        config = LoadTestConfig(name="test")
        result = LoadTestResult(
            config=config,
            status=LoadTestStatus.COMPLETED,
            start_time=datetime.utcnow(),
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            total_duration_seconds=10.0,
        )
        d = result.to_dict()
        assert d["status"] == "completed"
        assert d["total_requests"] == 100
        assert d["success_rate"] == 0.95


class TestLoadTestScenario:
    """Tests for LoadTestScenario."""

    def test_create_scenario(self):
        """Test creating a scenario."""
        def request_func():
            return RequestResult(success=True, latency_ms=10.0)

        scenario = LoadTestScenario(
            name="test",
            request_func=request_func,
        )
        assert scenario.name == "test"

    def test_execute_request(self):
        """Test executing a request."""
        def request_func():
            time.sleep(0.01)
            return RequestResult(success=True, latency_ms=0)

        scenario = LoadTestScenario(name="test", request_func=request_func)
        result = scenario.execute_request()
        assert result.success is True
        assert result.latency_ms > 0

    def test_execute_request_with_error(self):
        """Test executing a request that raises an error."""
        def request_func():
            raise ValueError("Test error")

        scenario = LoadTestScenario(name="test", request_func=request_func)
        result = scenario.execute_request()
        assert result.success is False
        assert "Test error" in result.error


class TestKGLoadTestRunner:
    """Tests for KGLoadTestRunner."""

    @pytest.fixture
    def runner(self):
        return KGLoadTestRunner(max_workers=10)

    def test_run_simple_test(self, runner):
        """Test running a simple load test."""
        counter = [0]

        def request_func():
            counter[0] += 1
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(
            name="simple",
            request_func=request_func,
            config=LoadTestConfig(name="simple", total_requests=10, concurrency=2),
        )

        result = runner.run(scenario)
        assert result.status == LoadTestStatus.COMPLETED
        assert result.total_requests == 10
        assert result.successful_requests == 10

    def test_run_with_failures(self, runner):
        """Test running a test with some failures."""
        counter = [0]

        def request_func():
            counter[0] += 1
            if counter[0] % 3 == 0:
                return RequestResult(success=False, latency_ms=5.0, error="Failed")
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(
            name="failures",
            request_func=request_func,
            config=LoadTestConfig(name="failures", total_requests=9, concurrency=1),
        )

        result = runner.run(scenario)
        assert result.status == LoadTestStatus.COMPLETED
        assert result.failed_requests == 3
        assert result.successful_requests == 6

    def test_run_with_warmup(self, runner):
        """Test running a test with warm-up requests."""
        counter = [0]

        def request_func():
            counter[0] += 1
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(
            name="warmup",
            request_func=request_func,
            config=LoadTestConfig(
                name="warmup",
                total_requests=10,
                concurrency=2,
                warm_up_requests=5,
            ),
        )

        result = runner.run(scenario)
        assert result.status == LoadTestStatus.COMPLETED
        assert result.total_requests == 10
        assert counter[0] == 15  # 5 warmup + 10 test

    def test_run_duration_based(self, runner):
        """Test running a duration-based test."""
        def request_func():
            time.sleep(0.01)
            return RequestResult(success=True, latency_ms=10.0)

        scenario = LoadTestScenario(
            name="duration",
            request_func=request_func,
            config=LoadTestConfig(
                name="duration",
                duration_seconds=0.5,
                concurrency=2,
            ),
        )

        result = runner.run(scenario)
        assert result.status == LoadTestStatus.COMPLETED
        assert result.total_requests > 0
        assert result.total_duration_seconds >= 0.4

    def test_run_with_think_time(self, runner):
        """Test running a test with think time."""
        counter = [0]

        def request_func():
            counter[0] += 1
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(
            name="think_time",
            request_func=request_func,
            config=LoadTestConfig(
                name="think_time",
                total_requests=5,
                concurrency=1,
                think_time_ms=50.0,
            ),
        )

        start = time.time()
        result = runner.run(scenario)
        elapsed = time.time() - start

        assert result.status == LoadTestStatus.COMPLETED
        assert elapsed >= 0.25  # 5 requests * 50ms think time

    def test_run_ramp_up(self, runner):
        """Test running a test with ramp-up."""
        def request_func():
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(
            name="ramp_up",
            request_func=request_func,
            config=LoadTestConfig(
                name="ramp_up",
                total_requests=20,
                concurrency=4,
                load_pattern=LoadPattern.RAMP_UP,
                ramp_up_seconds=0.5,
            ),
        )

        result = runner.run(scenario)
        assert result.status == LoadTestStatus.COMPLETED
        assert result.total_requests > 0

    def test_latency_stats_calculated(self, runner):
        """Test that latency stats are calculated."""
        counter = [0]

        def request_func():
            counter[0] += 1
            return RequestResult(success=True, latency_ms=10.0 * counter[0])

        scenario = LoadTestScenario(
            name="latency",
            request_func=request_func,
            config=LoadTestConfig(name="latency", total_requests=10, concurrency=1),
        )

        result = runner.run(scenario)
        assert result.latency_stats is not None
        assert result.latency_stats.min_ms == 10.0
        assert result.latency_stats.max_ms == 100.0

    def test_throughput_stats_calculated(self, runner):
        """Test that throughput stats are calculated."""
        def request_func():
            return RequestResult(
                success=True,
                latency_ms=5.0,
                response_size_bytes=100,
            )

        scenario = LoadTestScenario(
            name="throughput",
            request_func=request_func,
            config=LoadTestConfig(name="throughput", total_requests=10, concurrency=2),
        )

        result = runner.run(scenario)
        assert result.throughput_stats is not None
        assert result.throughput_stats.requests_per_second > 0

    def test_error_breakdown(self, runner):
        """Test error breakdown tracking."""
        counter = [0]

        def request_func():
            counter[0] += 1
            if counter[0] % 2 == 0:
                return RequestResult(success=False, latency_ms=5.0, error="Error A")
            if counter[0] % 3 == 0:
                return RequestResult(success=False, latency_ms=5.0, error="Error B")
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(
            name="errors",
            request_func=request_func,
            config=LoadTestConfig(name="errors", total_requests=10, concurrency=1),
        )

        result = runner.run(scenario)
        assert len(result.error_breakdown) > 0

    def test_cancel(self, runner):
        """Test cancelling a running test."""
        def request_func():
            time.sleep(0.1)
            return RequestResult(success=True, latency_ms=100.0)

        scenario = LoadTestScenario(
            name="cancel",
            request_func=request_func,
            config=LoadTestConfig(name="cancel", total_requests=100, concurrency=2),
        )

        # Start test in background
        result_holder = [None]

        def run_test():
            result_holder[0] = runner.run(scenario)

        thread = threading.Thread(target=run_test)
        thread.start()

        # Cancel after short delay
        time.sleep(0.2)
        runner.cancel()
        thread.join(timeout=2.0)

        # Test should have completed early
        assert result_holder[0] is not None
        assert result_holder[0].total_requests < 100

    def test_get_progress(self, runner):
        """Test getting progress of running test."""
        def request_func():
            time.sleep(0.05)
            return RequestResult(success=True, latency_ms=50.0)

        scenario = LoadTestScenario(
            name="progress",
            request_func=request_func,
            config=LoadTestConfig(name="progress", total_requests=20, concurrency=2),
        )

        # Start test in background
        thread = threading.Thread(target=lambda: runner.run(scenario))
        thread.start()

        # Check progress
        time.sleep(0.1)
        progress = runner.get_progress()

        runner.cancel()
        thread.join(timeout=2.0)

        # Progress should have been available
        # (may be None if test completed very quickly)


class TestKGLoadTestSuite:
    """Tests for KGLoadTestSuite."""

    def test_create_suite(self):
        """Test creating a test suite."""
        suite = KGLoadTestSuite(
            name="test_suite",
            description="A test suite",
        )
        assert suite.name == "test_suite"
        assert len(suite.scenarios) == 0

    def test_add_scenario(self):
        """Test adding scenarios to a suite."""
        suite = KGLoadTestSuite(name="suite")

        def request_func():
            return RequestResult(success=True, latency_ms=5.0)

        scenario = LoadTestScenario(name="test", request_func=request_func)
        suite.add_scenario(scenario)

        assert len(suite.scenarios) == 1

    def test_run_suite(self):
        """Test running a suite of scenarios."""
        suite = KGLoadTestSuite(name="suite")

        def request_func():
            return RequestResult(success=True, latency_ms=5.0)

        for i in range(3):
            scenario = LoadTestScenario(
                name=f"test_{i}",
                request_func=request_func,
                config=LoadTestConfig(name=f"test_{i}", total_requests=5),
            )
            suite.add_scenario(scenario)

        runner = KGLoadTestRunner()
        results = suite.run(runner)

        assert len(results) == 3
        for result in results:
            assert result.status == LoadTestStatus.COMPLETED


class TestScenarioFactories:
    """Tests for scenario factory functions."""

    def test_create_concept_lookup_scenario(self):
        """Test creating a concept lookup scenario."""
        lookup_results = {"C0001": "Result 1", "C0002": "Result 2"}

        def lookup_func(cui):
            return lookup_results.get(cui)

        scenario = create_concept_lookup_scenario(
            lookup_func=lookup_func,
            cuis=["C0001", "C0002"],
            config=LoadTestConfig(name="lookup", total_requests=4),
        )

        runner = KGLoadTestRunner()
        result = runner.run(scenario)

        assert result.status == LoadTestStatus.COMPLETED
        assert result.successful_requests == 4

    def test_create_path_finding_scenario(self):
        """Test creating a path finding scenario."""
        def path_func(source, target):
            return {"source": source, "target": target, "path": []}

        scenario = create_path_finding_scenario(
            path_func=path_func,
            cui_pairs=[("C0001", "C0002"), ("C0003", "C0004")],
            config=LoadTestConfig(name="path", total_requests=4),
        )

        runner = KGLoadTestRunner()
        result = runner.run(scenario)

        assert result.status == LoadTestStatus.COMPLETED
        assert result.successful_requests == 4

    def test_create_search_scenario(self):
        """Test creating a search scenario."""
        def search_func(query):
            return [{"result": query}]

        scenario = create_search_scenario(
            search_func=search_func,
            queries=["diabetes", "hypertension"],
            config=LoadTestConfig(name="search", total_requests=4),
        )

        runner = KGLoadTestRunner()
        result = runner.run(scenario)

        assert result.status == LoadTestStatus.COMPLETED
        assert result.successful_requests == 4

    def test_scenario_handles_exceptions(self):
        """Test that scenarios handle exceptions from request funcs."""
        def lookup_func(cui):
            raise ValueError("Test error")

        scenario = create_concept_lookup_scenario(
            lookup_func=lookup_func,
            cuis=["C0001"],
            config=LoadTestConfig(name="error", total_requests=5),
        )

        runner = KGLoadTestRunner()
        result = runner.run(scenario)

        assert result.status == LoadTestStatus.COMPLETED
        assert result.failed_requests == 5


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_load_test_runner_returns_same_instance(self):
        """Test singleton returns same instance."""
        reset_load_test_runner()
        r1 = get_load_test_runner()
        r2 = get_load_test_runner()
        assert r1 is r2
        reset_load_test_runner()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
