"""Lightweight async load testing framework.

Uses only stdlib + httpx (already a project dependency) to simulate
concurrent users hitting API endpoints and collect latency / throughput
metrics.

Usage (CLI)::

    python -m backend.tests.load.load_test_runner \\
        --base-url http://localhost:8000 \\
        --users 20 --duration 60 --ramp-up 10

Or programmatically::

    from tests.load.load_test_runner import LoadTestRunner, LoadTestConfig, EndpointConfig

    cfg = LoadTestConfig(
        base_url="http://localhost:8000",
        endpoints=[EndpointConfig(method="GET", path="/api/v1/health")],
        concurrent_users=20,
        duration_seconds=60,
    )
    runner = LoadTestRunner(cfg)
    results = asyncio.run(runner.run())
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


@dataclass
class EndpointConfig:
    """Description of a single endpoint to test."""

    method: str = "GET"
    path: str = "/api/v1/health"
    body: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    sla_ms: float = 500.0  # target latency SLA in milliseconds
    name: str | None = None  # human-readable label

    def __post_init__(self) -> None:
        if self.method not in {m.value for m in HttpMethod}:
            raise ValueError(f"Unsupported HTTP method: {self.method}")
        if not self.path.startswith("/"):
            raise ValueError(f"Path must start with '/': {self.path}")
        if self.name is None:
            self.name = f"{self.method} {self.path}"


@dataclass
class LoadTestConfig:
    """Top-level configuration for a load test run."""

    base_url: str = "http://localhost:8000"
    endpoints: list[EndpointConfig] = field(default_factory=list)
    concurrent_users: int = 10
    duration_seconds: float = 30.0
    ramp_up_seconds: float = 5.0
    think_time_seconds: float = 0.0
    auth_token: str | None = None
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.concurrent_users < 1:
            raise ValueError("concurrent_users must be >= 1")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        if self.ramp_up_seconds < 0:
            raise ValueError("ramp_up_seconds must be >= 0")
        if self.think_time_seconds < 0:
            raise ValueError("think_time_seconds must be >= 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class LoadTestResult:
    """Aggregated result for a single endpoint."""

    endpoint: str
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    latency_min_ms: float = 0.0
    latency_max_ms: float = 0.0
    latency_avg_ms: float = 0.0
    throughput_rps: float = 0.0
    error_rate: float = 0.0
    sla_target_ms: float = 500.0
    sla_passed: bool = True
    errors: dict[str, int] = field(default_factory=dict)


def compute_percentile(sorted_values: list[float], pct: float) -> float:
    """Return the *pct*-th percentile from an already-sorted list.

    Uses the *interpolation* method consistent with NumPy's default
    (linear interpolation between enclosing observations).
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    fraction = rank - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def aggregate_results(
    endpoint_name: str,
    latencies: list[float],
    status_codes: list[int],
    errors: list[str],
    elapsed_seconds: float,
    sla_target_ms: float,
) -> LoadTestResult:
    """Build a :class:`LoadTestResult` from raw per-request data."""
    total = len(latencies)
    successful = sum(1 for sc in status_codes if 200 <= sc < 400)
    failed = total - successful

    sorted_lat = sorted(latencies) if latencies else []
    p50 = compute_percentile(sorted_lat, 50)
    p95 = compute_percentile(sorted_lat, 95)
    p99 = compute_percentile(sorted_lat, 99)

    error_counts: dict[str, int] = {}
    for e in errors:
        error_counts[e] = error_counts.get(e, 0) + 1

    rps = total / elapsed_seconds if elapsed_seconds > 0 else 0.0
    error_rate = (failed / total * 100.0) if total > 0 else 0.0

    return LoadTestResult(
        endpoint=endpoint_name,
        total_requests=total,
        successful=successful,
        failed=failed,
        latency_p50_ms=round(p50, 2),
        latency_p95_ms=round(p95, 2),
        latency_p99_ms=round(p99, 2),
        latency_min_ms=round(sorted_lat[0], 2) if sorted_lat else 0.0,
        latency_max_ms=round(sorted_lat[-1], 2) if sorted_lat else 0.0,
        latency_avg_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
        throughput_rps=round(rps, 2),
        error_rate=round(error_rate, 2),
        sla_target_ms=sla_target_ms,
        sla_passed=p95 <= sla_target_ms,
        errors=error_counts,
    )


# ---------------------------------------------------------------------------
# Ramp-up schedule
# ---------------------------------------------------------------------------

def compute_ramp_schedule(
    total_users: int,
    ramp_up_seconds: float,
) -> list[tuple[float, int]]:
    """Return a list of ``(delay_seconds, users_to_add)`` pairs.

    The schedule distributes user starts evenly across the ramp-up window.
    If *ramp_up_seconds* is 0, all users start immediately.
    """
    if total_users <= 0:
        return []
    if ramp_up_seconds <= 0:
        return [(0.0, total_users)]

    schedule: list[tuple[float, int]] = []
    # We'll launch users in at most `total_users` steps.
    interval = ramp_up_seconds / total_users
    for i in range(total_users):
        schedule.append((round(interval * i, 4), 1))
    return schedule


# ---------------------------------------------------------------------------
# HTTP client protocol (enables mocking in tests)
# ---------------------------------------------------------------------------

class HttpClient(Protocol):
    """Minimal async HTTP interface consumed by the runner."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        timeout: float = 30.0,
    ) -> "HttpResponse": ...

    async def aclose(self) -> None: ...


@dataclass
class HttpResponse:
    status_code: int
    elapsed_ms: float


class HttpxClientAdapter:
    """Wraps :class:`httpx.AsyncClient` to satisfy :class:`HttpClient`."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        import httpx as _httpx

        self._client = _httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        timeout: float = 30.0,
    ) -> HttpResponse:
        start = time.monotonic()
        resp = await self._client.request(method, url, headers=headers, json=json, timeout=timeout)
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return HttpResponse(status_code=resp.status_code, elapsed_ms=elapsed_ms)

    async def aclose(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class LoadTestRunner:
    """Orchestrates a load test against a set of endpoints."""

    def __init__(
        self,
        config: LoadTestConfig,
        *,
        http_client: HttpClient | None = None,
        progress_callback: Any | None = None,
    ) -> None:
        self.config = config
        self._http_client = http_client
        self._owns_client = http_client is None
        self._progress_callback = progress_callback

        # Per-endpoint accumulators
        self._latencies: dict[str, list[float]] = {}
        self._status_codes: dict[str, list[int]] = {}
        self._errors: dict[str, list[str]] = {}

    # -- public API ---------------------------------------------------------

    async def run(self) -> list[LoadTestResult]:
        """Execute the load test and return per-endpoint results."""
        client = self._http_client or HttpxClientAdapter(
            self.config.base_url, timeout=self.config.timeout_seconds
        )

        for ep in self.config.endpoints:
            name = ep.name or f"{ep.method} {ep.path}"
            self._latencies[name] = []
            self._status_codes[name] = []
            self._errors[name] = []

        schedule = compute_ramp_schedule(
            self.config.concurrent_users, self.config.ramp_up_seconds
        )

        start_time = time.monotonic()
        tasks: list[asyncio.Task[None]] = []

        for delay, count in schedule:
            if delay > 0:
                await asyncio.sleep(delay)
            for _ in range(count):
                t = asyncio.create_task(
                    self._user_loop(client, start_time)
                )
                tasks.append(t)

        # Wait for all virtual users to finish
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.monotonic() - start_time

        if self._owns_client:
            await client.aclose()

        return self._build_results(elapsed)

    # -- internal -----------------------------------------------------------

    async def _user_loop(
        self,
        client: HttpClient,
        start_time: float,
    ) -> None:
        """Simulate one virtual user making requests until duration expires."""
        cfg = self.config
        end_time = start_time + cfg.duration_seconds

        auth_headers: dict[str, str] = {}
        if cfg.auth_token:
            auth_headers["Authorization"] = f"Bearer {cfg.auth_token}"

        while time.monotonic() < end_time:
            for ep in cfg.endpoints:
                if time.monotonic() >= end_time:
                    break

                name = ep.name or f"{ep.method} {ep.path}"
                merged_headers = {**auth_headers, **(ep.headers or {})}

                try:
                    resp = await client.request(
                        ep.method,
                        ep.path,
                        headers=merged_headers if merged_headers else None,
                        json=ep.body,
                        timeout=cfg.timeout_seconds,
                    )
                    self._latencies[name].append(resp.elapsed_ms)
                    self._status_codes[name].append(resp.status_code)
                    if resp.status_code >= 400:
                        self._errors[name].append(f"HTTP {resp.status_code}")
                except Exception as exc:
                    self._latencies[name].append(cfg.timeout_seconds * 1000)
                    self._status_codes[name].append(0)
                    self._errors[name].append(type(exc).__name__)

                if cfg.think_time_seconds > 0:
                    await asyncio.sleep(cfg.think_time_seconds)

        if self._progress_callback:
            self._progress_callback("user_done")

    def _build_results(self, elapsed: float) -> list[LoadTestResult]:
        results: list[LoadTestResult] = []
        ep_map = {
            (ep.name or f"{ep.method} {ep.path}"): ep for ep in self.config.endpoints
        }
        for name in self._latencies:
            ep = ep_map.get(name)
            sla = ep.sla_ms if ep else 500.0
            results.append(
                aggregate_results(
                    endpoint_name=name,
                    latencies=self._latencies[name],
                    status_codes=self._status_codes[name],
                    errors=self._errors[name],
                    elapsed_seconds=elapsed,
                    sla_target_ms=sla,
                )
            )
        return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def generate_markdown_report(
    results: list[LoadTestResult],
    config: LoadTestConfig,
) -> str:
    """Produce a Markdown summary table with pass/fail column."""
    lines: list[str] = []
    lines.append("# Load Test Report")
    lines.append("")
    lines.append(f"- **Base URL:** {config.base_url}")
    lines.append(f"- **Concurrent Users:** {config.concurrent_users}")
    lines.append(f"- **Duration:** {config.duration_seconds}s (ramp-up {config.ramp_up_seconds}s)")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append(
        "| Endpoint | Reqs | OK | Fail | p50 (ms) | p95 (ms) | p99 (ms) | RPS | Err% | SLA | Status |"
    )
    lines.append(
        "|----------|------|----|------|----------|----------|----------|-----|------|-----|--------|"
    )

    all_passed = True
    for r in results:
        status = "PASS" if r.sla_passed else "FAIL"
        if not r.sla_passed:
            all_passed = False
        lines.append(
            f"| {r.endpoint} | {r.total_requests} | {r.successful} | {r.failed} "
            f"| {r.latency_p50_ms} | {r.latency_p95_ms} | {r.latency_p99_ms} "
            f"| {r.throughput_rps} | {r.error_rate}% | {r.sla_target_ms}ms | {status} |"
        )
    lines.append("")
    overall = "ALL PASSED" if all_passed else "FAILURES DETECTED"
    lines.append(f"**Overall: {overall}**")
    lines.append("")

    # Error breakdown
    has_errors = any(r.errors for r in results)
    if has_errors:
        lines.append("## Errors")
        lines.append("")
        for r in results:
            if r.errors:
                lines.append(f"### {r.endpoint}")
                for err, count in sorted(r.errors.items(), key=lambda x: -x[1]):
                    lines.append(f"- {err}: {count}")
                lines.append("")

    return "\n".join(lines)


def results_to_json(results: list[LoadTestResult]) -> list[dict[str, Any]]:
    """Serialize results to JSON-compatible dicts."""
    out: list[dict[str, Any]] = []
    for r in results:
        out.append({
            "endpoint": r.endpoint,
            "total_requests": r.total_requests,
            "successful": r.successful,
            "failed": r.failed,
            "latency_p50_ms": r.latency_p50_ms,
            "latency_p95_ms": r.latency_p95_ms,
            "latency_p99_ms": r.latency_p99_ms,
            "latency_min_ms": r.latency_min_ms,
            "latency_max_ms": r.latency_max_ms,
            "latency_avg_ms": r.latency_avg_ms,
            "throughput_rps": r.throughput_rps,
            "error_rate": r.error_rate,
            "sla_target_ms": r.sla_target_ms,
            "sla_passed": r.sla_passed,
            "errors": r.errors,
        })
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run load tests against API endpoints")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Target base URL")
    parser.add_argument("--users", type=int, default=10, help="Concurrent virtual users")
    parser.add_argument("--duration", type=float, default=30, help="Test duration in seconds")
    parser.add_argument("--ramp-up", type=float, default=5, help="Ramp-up period in seconds")
    parser.add_argument("--think-time", type=float, default=0, help="Think time between requests (seconds)")
    parser.add_argument("--token", default=None, help="Bearer auth token")
    parser.add_argument("--scenario", default=None, help="Named scenario from scenarios.py")
    parser.add_argument("--output", default=None, help="Write markdown report to file")
    parser.add_argument("--json-output", default=None, help="Write JSON results to file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # If a named scenario is given, import and use it
    if args.scenario:
        from tests.load.scenarios import get_scenario

        config = get_scenario(args.scenario, base_url=args.base_url, auth_token=args.token)
    else:
        from tests.load.scenarios import DEFAULT_ENDPOINTS

        config = LoadTestConfig(
            base_url=args.base_url,
            endpoints=DEFAULT_ENDPOINTS,
            concurrent_users=args.users,
            duration_seconds=args.duration,
            ramp_up_seconds=args.ramp_up,
            think_time_seconds=args.think_time,
            auth_token=args.token,
        )

    print(f"Starting load test: {config.concurrent_users} users, {config.duration_seconds}s")
    print(f"Target: {config.base_url}")
    print(f"Endpoints: {len(config.endpoints)}")
    print()

    runner = LoadTestRunner(config)
    results = asyncio.run(runner.run())

    report = generate_markdown_report(results, config)
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")

    if args.json_output:
        Path(args.json_output).write_text(
            json.dumps(results_to_json(results), indent=2), encoding="utf-8"
        )
        print(f"JSON results written to {args.json_output}")

    # Exit with non-zero if any SLA failed
    if any(not r.sla_passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
