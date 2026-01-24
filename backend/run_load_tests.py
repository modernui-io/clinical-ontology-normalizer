#!/usr/bin/env python3
"""Standalone test runner for KG Load Testing Service tests."""

import sys
import os
import importlib.util
import traceback
import time
import threading
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create comprehensive mocks for dependencies
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock the problematic modules before any imports
sys.modules["sentence_transformers"] = MockModule()
sys.modules["sentence_transformers"].SentenceTransformer = MockModule()
sys.modules["neo4j"] = MockModule()
sys.modules["neo4j"].GraphDatabase = MockModule()

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_load_testing_service",
    "app/services/kg_load_testing_service.py",
    submodule_search_locations=[]
)
load_test_module = importlib.util.module_from_spec(spec)
load_test_module.__package__ = "app.services"
sys.modules["app.services.kg_load_testing_service"] = load_test_module
spec.loader.exec_module(load_test_module)

# Import the module under test
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


def run_test(name, test_func):
    """Run a single test."""
    try:
        test_func()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


# RequestResult tests
def test_create_success_result():
    result = RequestResult(
        success=True,
        latency_ms=50.5,
        status_code=200,
        response_size_bytes=1024,
    )
    assert result.success is True
    assert result.latency_ms == 50.5
    assert result.status_code == 200


def test_create_failure_result():
    result = RequestResult(
        success=False,
        latency_ms=100.0,
        error="Connection timeout",
    )
    assert result.success is False
    assert result.error == "Connection timeout"


def test_result_to_dict():
    result = RequestResult(success=True, latency_ms=50.5)
    d = result.to_dict()
    assert d["success"] is True
    assert d["latency_ms"] == 50.5


# LatencyStats tests
def test_latency_stats_empty():
    stats = LatencyStats.calculate([])
    assert stats.min_ms == 0
    assert stats.max_ms == 0
    assert stats.mean_ms == 0


def test_latency_stats_single():
    stats = LatencyStats.calculate([50.0])
    assert stats.min_ms == 50.0
    assert stats.max_ms == 50.0
    assert stats.mean_ms == 50.0


def test_latency_stats_multiple():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    stats = LatencyStats.calculate(latencies)
    assert stats.min_ms == 10.0
    assert stats.max_ms == 100.0
    assert stats.mean_ms == 55.0
    assert stats.p50_ms == 50.0
    assert stats.p90_ms == 90.0


def test_latency_stats_to_dict():
    stats = LatencyStats.calculate([10.0, 20.0, 30.0])
    d = stats.to_dict()
    assert "min_ms" in d
    assert "max_ms" in d
    assert "p95_ms" in d


# ThroughputStats tests
def test_throughput_stats_create():
    stats = ThroughputStats(
        requests_per_second=100.5,
        successful_per_second=95.0,
        failed_per_second=5.5,
        bytes_per_second=10240.0,
    )
    assert stats.requests_per_second == 100.5
    assert stats.successful_per_second == 95.0


def test_throughput_stats_to_dict():
    stats = ThroughputStats(
        requests_per_second=100.0,
        successful_per_second=95.0,
        failed_per_second=5.0,
        bytes_per_second=10240.0,
    )
    d = stats.to_dict()
    assert d["requests_per_second"] == 100.0


# LoadTestConfig tests
def test_default_config():
    config = LoadTestConfig(name="test")
    assert config.total_requests == 100
    assert config.concurrency == 10
    assert config.load_pattern == LoadPattern.CONSTANT


def test_custom_config():
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


def test_config_to_dict():
    config = LoadTestConfig(name="test")
    d = config.to_dict()
    assert d["name"] == "test"
    assert d["total_requests"] == 100


# LoadTestResult tests
def test_create_result():
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


def test_result_to_dict():
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


# LoadTestScenario tests
def test_create_scenario():
    def request_func():
        return RequestResult(success=True, latency_ms=10.0)

    scenario = LoadTestScenario(name="test", request_func=request_func)
    assert scenario.name == "test"


def test_execute_request():
    def request_func():
        time.sleep(0.01)
        return RequestResult(success=True, latency_ms=0)

    scenario = LoadTestScenario(name="test", request_func=request_func)
    result = scenario.execute_request()
    assert result.success is True
    assert result.latency_ms > 0


def test_execute_request_with_error():
    def request_func():
        raise ValueError("Test error")

    scenario = LoadTestScenario(name="test", request_func=request_func)
    result = scenario.execute_request()
    assert result.success is False
    assert "Test error" in result.error


# KGLoadTestRunner tests
def test_run_simple_test():
    runner = KGLoadTestRunner(max_workers=10)
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


def test_run_with_failures():
    runner = KGLoadTestRunner(max_workers=10)
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


def test_run_with_warmup():
    runner = KGLoadTestRunner(max_workers=10)
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
    assert counter[0] == 15


def test_run_duration_based():
    runner = KGLoadTestRunner(max_workers=10)

    def request_func():
        time.sleep(0.01)
        return RequestResult(success=True, latency_ms=10.0)

    scenario = LoadTestScenario(
        name="duration",
        request_func=request_func,
        config=LoadTestConfig(
            name="duration",
            duration_seconds=0.3,
            concurrency=2,
        ),
    )

    result = runner.run(scenario)
    assert result.status == LoadTestStatus.COMPLETED
    assert result.total_requests > 0
    assert result.total_duration_seconds >= 0.2


def test_run_with_think_time():
    runner = KGLoadTestRunner(max_workers=10)
    counter = [0]

    def request_func():
        counter[0] += 1
        return RequestResult(success=True, latency_ms=5.0)

    scenario = LoadTestScenario(
        name="think_time",
        request_func=request_func,
        config=LoadTestConfig(
            name="think_time",
            total_requests=3,
            concurrency=1,
            think_time_ms=50.0,
        ),
    )

    start = time.time()
    result = runner.run(scenario)
    elapsed = time.time() - start

    assert result.status == LoadTestStatus.COMPLETED
    assert elapsed >= 0.15


def test_run_ramp_up():
    runner = KGLoadTestRunner(max_workers=10)

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
            ramp_up_seconds=0.3,
        ),
    )

    result = runner.run(scenario)
    assert result.status == LoadTestStatus.COMPLETED
    assert result.total_requests > 0


def test_latency_stats_calculated():
    runner = KGLoadTestRunner(max_workers=10)
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


def test_throughput_stats_calculated():
    runner = KGLoadTestRunner(max_workers=10)

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


def test_error_breakdown():
    runner = KGLoadTestRunner(max_workers=10)
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


# KGLoadTestSuite tests
def test_create_suite():
    suite = KGLoadTestSuite(name="test_suite", description="A test suite")
    assert suite.name == "test_suite"
    assert len(suite.scenarios) == 0


def test_add_scenario():
    suite = KGLoadTestSuite(name="suite")

    def request_func():
        return RequestResult(success=True, latency_ms=5.0)

    scenario = LoadTestScenario(name="test", request_func=request_func)
    suite.add_scenario(scenario)

    assert len(suite.scenarios) == 1


def test_run_suite():
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


# Scenario factory tests
def test_concept_lookup_scenario():
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


def test_path_finding_scenario():
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


def test_search_scenario():
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


def test_scenario_handles_exceptions():
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


# Singleton tests
def test_singleton_returns_same_instance():
    reset_load_test_runner()
    r1 = get_load_test_runner()
    r2 = get_load_test_runner()
    assert r1 is r2
    reset_load_test_runner()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Load Testing Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # RequestResult tests
        ("create_success_result", test_create_success_result),
        ("create_failure_result", test_create_failure_result),
        ("result_to_dict", test_result_to_dict),

        # LatencyStats tests
        ("latency_stats_empty", test_latency_stats_empty),
        ("latency_stats_single", test_latency_stats_single),
        ("latency_stats_multiple", test_latency_stats_multiple),
        ("latency_stats_to_dict", test_latency_stats_to_dict),

        # ThroughputStats tests
        ("throughput_stats_create", test_throughput_stats_create),
        ("throughput_stats_to_dict", test_throughput_stats_to_dict),

        # LoadTestConfig tests
        ("default_config", test_default_config),
        ("custom_config", test_custom_config),
        ("config_to_dict", test_config_to_dict),

        # LoadTestResult tests
        ("create_result", test_create_result),
        ("result_to_dict", test_result_to_dict),

        # LoadTestScenario tests
        ("create_scenario", test_create_scenario),
        ("execute_request", test_execute_request),
        ("execute_request_with_error", test_execute_request_with_error),

        # KGLoadTestRunner tests
        ("run_simple_test", test_run_simple_test),
        ("run_with_failures", test_run_with_failures),
        ("run_with_warmup", test_run_with_warmup),
        ("run_duration_based", test_run_duration_based),
        ("run_with_think_time", test_run_with_think_time),
        ("run_ramp_up", test_run_ramp_up),
        ("latency_stats_calculated", test_latency_stats_calculated),
        ("throughput_stats_calculated", test_throughput_stats_calculated),
        ("error_breakdown", test_error_breakdown),

        # KGLoadTestSuite tests
        ("create_suite", test_create_suite),
        ("add_scenario", test_add_scenario),
        ("run_suite", test_run_suite),

        # Scenario factory tests
        ("concept_lookup_scenario", test_concept_lookup_scenario),
        ("path_finding_scenario", test_path_finding_scenario),
        ("search_scenario", test_search_scenario),
        ("scenario_handles_exceptions", test_scenario_handles_exceptions),

        # Singleton tests
        ("singleton_returns_same_instance", test_singleton_returns_same_instance),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        if run_test(name, test):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
