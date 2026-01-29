"""KG Load Testing Service.

This module provides load testing and performance benchmarking capabilities
for the Knowledge Graph API. Supports concurrent requests, latency measurement,
throughput calculation, and resource monitoring.
"""

import asyncio
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class LoadTestStatus(str, Enum):
    """Load test status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoadPattern(str, Enum):
    """Load pattern types."""

    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    STEP = "step"
    CUSTOM = "custom"


@dataclass
class RequestResult:
    """Result of a single request."""

    success: bool
    latency_ms: float
    status_code: int | None = None
    error: str | None = None
    response_size_bytes: int | None = None
    timestamp: float = field(default_factory=time.time)
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "error": self.error,
            "response_size_bytes": self.response_size_bytes,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
        }


@dataclass
class LatencyStats:
    """Latency statistics."""

    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p50_ms: float
    p75_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float

    @staticmethod
    def calculate(latencies: list[float]) -> "LatencyStats":
        """Calculate latency statistics from a list of latencies."""
        if not latencies:
            return LatencyStats(
                min_ms=0, max_ms=0, mean_ms=0, median_ms=0,
                p50_ms=0, p75_ms=0, p90_ms=0, p95_ms=0, p99_ms=0,
                std_dev_ms=0,
            )

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            index = int(p / 100 * (n - 1))
            return sorted_latencies[index]

        return LatencyStats(
            min_ms=min(latencies),
            max_ms=max(latencies),
            mean_ms=statistics.mean(latencies),
            median_ms=statistics.median(latencies),
            p50_ms=percentile(50),
            p75_ms=percentile(75),
            p90_ms=percentile(90),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            std_dev_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0,
        )

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p75_ms": round(self.p75_ms, 2),
            "p90_ms": round(self.p90_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
        }


@dataclass
class ThroughputStats:
    """Throughput statistics."""

    requests_per_second: float
    successful_per_second: float
    failed_per_second: float
    bytes_per_second: float

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "requests_per_second": round(self.requests_per_second, 2),
            "successful_per_second": round(self.successful_per_second, 2),
            "failed_per_second": round(self.failed_per_second, 2),
            "bytes_per_second": round(self.bytes_per_second, 2),
        }


@dataclass
class LoadTestConfig:
    """Configuration for a load test."""

    name: str
    description: str = ""
    total_requests: int = 100
    concurrency: int = 10
    duration_seconds: float | None = None  # If set, overrides total_requests
    load_pattern: LoadPattern = LoadPattern.CONSTANT
    ramp_up_seconds: float = 0
    warm_up_requests: int = 0
    timeout_seconds: float = 30.0
    think_time_ms: float = 0  # Delay between requests per worker
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "total_requests": self.total_requests,
            "concurrency": self.concurrency,
            "duration_seconds": self.duration_seconds,
            "load_pattern": self.load_pattern.value,
            "ramp_up_seconds": self.ramp_up_seconds,
            "warm_up_requests": self.warm_up_requests,
            "timeout_seconds": self.timeout_seconds,
            "think_time_ms": self.think_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class LoadTestResult:
    """Result of a load test."""

    config: LoadTestConfig
    status: LoadTestStatus
    start_time: datetime
    end_time: datetime | None = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_seconds: float = 0
    latency_stats: LatencyStats | None = None
    throughput_stats: ThroughputStats | None = None
    error_breakdown: dict[str, int] = field(default_factory=dict)
    results: list[RequestResult] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self, include_results: bool = False) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "config": self.config.to_dict(),
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests
                if self.total_requests > 0
                else 0
            ),
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "latency": self.latency_stats.to_dict() if self.latency_stats else None,
            "throughput": self.throughput_stats.to_dict() if self.throughput_stats else None,
            "error_breakdown": self.error_breakdown,
            "error_message": self.error_message,
        }
        if include_results:
            result["results"] = [r.to_dict() for r in self.results]
        return result


class LoadTestScenario:
    """A load test scenario that can be executed."""

    def __init__(
        self,
        name: str,
        request_func: Callable[[], RequestResult],
        config: LoadTestConfig | None = None,
    ):
        """Initialize the scenario.

        Args:
            name: Scenario name
            request_func: Function that makes a request and returns RequestResult
            config: Test configuration
        """
        self.name = name
        self.request_func = request_func
        self.config = config or LoadTestConfig(name=name)

    def execute_request(self) -> RequestResult:
        """Execute a single request."""
        start_time = time.time()
        try:
            result = self.request_func()
            if result.latency_ms == 0:
                result.latency_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            return RequestResult(
                success=False,
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )


class KGLoadTestRunner:
    """Load test runner for KG services.

    Features:
    - Concurrent request execution
    - Multiple load patterns
    - Latency percentile calculation
    - Throughput measurement
    - Progress tracking
    - Cancellation support
    """

    def __init__(self, max_workers: int = 100):
        """Initialize the runner.

        Args:
            max_workers: Maximum number of concurrent workers
        """
        self.max_workers = max_workers
        self._current_test: LoadTestResult | None = None
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

    def run(self, scenario: LoadTestScenario) -> LoadTestResult:
        """Run a load test scenario.

        Args:
            scenario: The scenario to run

        Returns:
            LoadTestResult with test results
        """
        config = scenario.config
        self._cancel_event.clear()

        # Initialize result
        result = LoadTestResult(
            config=config,
            status=LoadTestStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
        )

        with self._lock:
            self._current_test = result

        try:
            # Run warm-up requests
            if config.warm_up_requests > 0:
                self._run_warmup(scenario, config.warm_up_requests)

            # Run main test
            start_time = time.time()

            if config.duration_seconds:
                # Time-based test
                results = self._run_duration_based(
                    scenario,
                    config.duration_seconds,
                    config.concurrency,
                    config.think_time_ms,
                )
            else:
                # Request-count based test
                results = self._run_request_based(
                    scenario,
                    config.total_requests,
                    config.concurrency,
                    config.think_time_ms,
                    config.load_pattern,
                    config.ramp_up_seconds,
                )

            end_time = time.time()

            # Calculate statistics
            result.results = results
            result.total_requests = len(results)
            result.successful_requests = sum(1 for r in results if r.success)
            result.failed_requests = sum(1 for r in results if not r.success)
            result.total_duration_seconds = end_time - start_time

            # Calculate latency stats
            latencies = [r.latency_ms for r in results if r.success]
            if latencies:
                result.latency_stats = LatencyStats.calculate(latencies)

            # Calculate throughput
            if result.total_duration_seconds > 0:
                total_bytes = sum(
                    r.response_size_bytes or 0
                    for r in results
                    if r.success
                )
                result.throughput_stats = ThroughputStats(
                    requests_per_second=result.total_requests / result.total_duration_seconds,
                    successful_per_second=result.successful_requests / result.total_duration_seconds,
                    failed_per_second=result.failed_requests / result.total_duration_seconds,
                    bytes_per_second=total_bytes / result.total_duration_seconds,
                )

            # Error breakdown
            for r in results:
                if not r.success and r.error:
                    error_key = r.error[:50]  # Truncate long errors
                    result.error_breakdown[error_key] = result.error_breakdown.get(error_key, 0) + 1

            result.status = LoadTestStatus.COMPLETED
            result.end_time = datetime.now(timezone.utc)

        except Exception as e:
            result.status = LoadTestStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now(timezone.utc)

        with self._lock:
            self._current_test = None

        return result

    def _run_warmup(
        self,
        scenario: LoadTestScenario,
        count: int,
    ) -> None:
        """Run warm-up requests."""
        for _ in range(count):
            if self._cancel_event.is_set():
                break
            scenario.execute_request()

    def _run_request_based(
        self,
        scenario: LoadTestScenario,
        total_requests: int,
        concurrency: int,
        think_time_ms: float,
        load_pattern: LoadPattern,
        ramp_up_seconds: float,
    ) -> list[RequestResult]:
        """Run a request-count based load test."""
        results: list[RequestResult] = []
        workers = min(concurrency, self.max_workers, total_requests)

        if load_pattern == LoadPattern.RAMP_UP and ramp_up_seconds > 0:
            # Gradual ramp-up
            return self._run_ramp_up(
                scenario,
                total_requests,
                workers,
                think_time_ms,
                ramp_up_seconds,
            )

        # Constant load pattern
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for i in range(total_requests):
                if self._cancel_event.is_set():
                    break

                future = executor.submit(
                    self._execute_with_think_time,
                    scenario,
                    think_time_ms,
                )
                futures.append(future)

            for future in as_completed(futures):
                if self._cancel_event.is_set():
                    break
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(RequestResult(
                        success=False,
                        latency_ms=0,
                        error=str(e),
                    ))

        return results

    def _run_ramp_up(
        self,
        scenario: LoadTestScenario,
        total_requests: int,
        max_workers: int,
        think_time_ms: float,
        ramp_up_seconds: float,
    ) -> list[RequestResult]:
        """Run with gradual ramp-up of concurrency."""
        results: list[RequestResult] = []
        start_time = time.time()
        requests_sent = 0

        # Calculate ramp-up steps
        step_count = min(max_workers, 10)  # Max 10 ramp-up steps
        step_duration = ramp_up_seconds / step_count

        for step in range(step_count):
            if self._cancel_event.is_set():
                break

            # Calculate workers for this step
            step_workers = max(1, int((step + 1) / step_count * max_workers))

            # Calculate requests for this step
            remaining = total_requests - requests_sent
            step_requests = min(remaining, total_requests // step_count)

            if step_requests <= 0:
                break

            # Run this step
            step_start = time.time()
            with ThreadPoolExecutor(max_workers=step_workers) as executor:
                futures = []
                for _ in range(step_requests):
                    if self._cancel_event.is_set():
                        break
                    future = executor.submit(
                        self._execute_with_think_time,
                        scenario,
                        think_time_ms,
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    if self._cancel_event.is_set():
                        break
                    try:
                        result = future.result()
                        results.append(result)
                        requests_sent += 1
                    except Exception as e:
                        results.append(RequestResult(
                            success=False,
                            latency_ms=0,
                            error=str(e),
                        ))
                        requests_sent += 1

            # Wait for step duration if needed
            elapsed = time.time() - step_start
            if elapsed < step_duration:
                time.sleep(step_duration - elapsed)

        return results

    def _run_duration_based(
        self,
        scenario: LoadTestScenario,
        duration_seconds: float,
        concurrency: int,
        think_time_ms: float,
    ) -> list[RequestResult]:
        """Run a time-based load test."""
        results: list[RequestResult] = []
        workers = min(concurrency, self.max_workers)
        end_time = time.time() + duration_seconds
        results_lock = threading.Lock()
        stop_event = threading.Event()

        def worker():
            while not stop_event.is_set() and time.time() < end_time:
                if self._cancel_event.is_set():
                    break
                result = self._execute_with_think_time(scenario, think_time_ms)
                with results_lock:
                    results.append(result)

        threads = []
        for _ in range(workers):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        # Wait for duration
        while time.time() < end_time:
            if self._cancel_event.is_set():
                break
            time.sleep(0.1)

        stop_event.set()

        for t in threads:
            t.join(timeout=5.0)

        return results

    def _execute_with_think_time(
        self,
        scenario: LoadTestScenario,
        think_time_ms: float,
    ) -> RequestResult:
        """Execute a request with optional think time."""
        result = scenario.execute_request()
        if think_time_ms > 0:
            time.sleep(think_time_ms / 1000)
        return result

    def cancel(self) -> bool:
        """Cancel the currently running test."""
        self._cancel_event.set()
        return True

    def get_progress(self) -> dict[str, Any | None]:
        """Get progress of the current test."""
        with self._lock:
            if not self._current_test:
                return None

            return {
                "status": self._current_test.status.value,
                "total_requests": self._current_test.total_requests,
                "successful": self._current_test.successful_requests,
                "failed": self._current_test.failed_requests,
                "elapsed_seconds": (
                    datetime.now(timezone.utc) - self._current_test.start_time
                ).total_seconds(),
            }


class KGLoadTestSuite:
    """A suite of load test scenarios."""

    def __init__(self, name: str, description: str = ""):
        """Initialize the suite.

        Args:
            name: Suite name
            description: Suite description
        """
        self.name = name
        self.description = description
        self.scenarios: list[LoadTestScenario] = []

    def add_scenario(self, scenario: LoadTestScenario) -> None:
        """Add a scenario to the suite."""
        self.scenarios.append(scenario)

    def run(self, runner: KGLoadTestRunner) -> list[LoadTestResult]:
        """Run all scenarios in the suite.

        Args:
            runner: The load test runner

        Returns:
            List of results for each scenario
        """
        results = []
        for scenario in self.scenarios:
            result = runner.run(scenario)
            results.append(result)
        return results


# Pre-built test scenarios for KG operations

def create_concept_lookup_scenario(
    lookup_func: Callable[[str], Any],
    cuis: list[str],
    config: LoadTestConfig | None = None,
) -> LoadTestScenario:
    """Create a concept lookup load test scenario.

    Args:
        lookup_func: Function that looks up a concept by CUI
        cuis: List of CUIs to look up
        config: Test configuration

    Returns:
        LoadTestScenario
    """
    cui_index = [0]
    lock = threading.Lock()

    def request_func() -> RequestResult:
        with lock:
            cui = cuis[cui_index[0] % len(cuis)]
            cui_index[0] += 1

        start = time.time()
        try:
            result = lookup_func(cui)
            return RequestResult(
                success=True,
                latency_ms=(time.time() - start) * 1000,
                response_size_bytes=len(str(result)) if result else 0,
            )
        except Exception as e:
            return RequestResult(
                success=False,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    return LoadTestScenario(
        name="concept_lookup",
        request_func=request_func,
        config=config or LoadTestConfig(name="concept_lookup"),
    )


def create_path_finding_scenario(
    path_func: Callable[[str, str], Any],
    cui_pairs: list[tuple[str, str]],
    config: LoadTestConfig | None = None,
) -> LoadTestScenario:
    """Create a path finding load test scenario.

    Args:
        path_func: Function that finds paths between two CUIs
        cui_pairs: List of (source, target) CUI pairs
        config: Test configuration

    Returns:
        LoadTestScenario
    """
    pair_index = [0]
    lock = threading.Lock()

    def request_func() -> RequestResult:
        with lock:
            pair = cui_pairs[pair_index[0] % len(cui_pairs)]
            pair_index[0] += 1

        start = time.time()
        try:
            result = path_func(pair[0], pair[1])
            return RequestResult(
                success=True,
                latency_ms=(time.time() - start) * 1000,
                response_size_bytes=len(str(result)) if result else 0,
            )
        except Exception as e:
            return RequestResult(
                success=False,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    return LoadTestScenario(
        name="path_finding",
        request_func=request_func,
        config=config or LoadTestConfig(name="path_finding"),
    )


def create_search_scenario(
    search_func: Callable[[str], Any],
    queries: list[str],
    config: LoadTestConfig | None = None,
) -> LoadTestScenario:
    """Create a search load test scenario.

    Args:
        search_func: Function that performs a search
        queries: List of search queries
        config: Test configuration

    Returns:
        LoadTestScenario
    """
    query_index = [0]
    lock = threading.Lock()

    def request_func() -> RequestResult:
        with lock:
            query = queries[query_index[0] % len(queries)]
            query_index[0] += 1

        start = time.time()
        try:
            result = search_func(query)
            return RequestResult(
                success=True,
                latency_ms=(time.time() - start) * 1000,
                response_size_bytes=len(str(result)) if result else 0,
            )
        except Exception as e:
            return RequestResult(
                success=False,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    return LoadTestScenario(
        name="search",
        request_func=request_func,
        config=config or LoadTestConfig(name="search"),
    )


# Singleton instance
_load_test_runner: KGLoadTestRunner | None = None
_runner_lock = threading.Lock()


def get_load_test_runner() -> KGLoadTestRunner:
    """Get the singleton load test runner."""
    global _load_test_runner
    if _load_test_runner is None:
        with _runner_lock:
            if _load_test_runner is None:
                _load_test_runner = KGLoadTestRunner()
    return _load_test_runner


def reset_load_test_runner() -> None:
    """Reset the singleton instance (for testing)."""
    global _load_test_runner
    with _runner_lock:
        _load_test_runner = None
