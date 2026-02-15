"""P2-017: SLO dashboard with p50/p95/p99 latency and error-rate tracking.

Records per-endpoint metrics in memory and evaluates them against SLO targets.
Designed to be fed from middleware (see record_request) and queried by a
dashboard API endpoint.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLO Targets (defaults)
# ---------------------------------------------------------------------------

DEFAULT_P95_TARGET_MS: float = 500.0
DEFAULT_P99_TARGET_MS: float = 2000.0
DEFAULT_ERROR_RATE_TARGET: float = 0.01  # 1%


@dataclass(frozen=True)
class SLOTarget:
    """Defines pass/fail thresholds for an SLO."""
    p95_ms: float = DEFAULT_P95_TARGET_MS
    p99_ms: float = DEFAULT_P99_TARGET_MS
    error_rate: float = DEFAULT_ERROR_RATE_TARGET


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EndpointMetrics:
    """Computed metrics for a single endpoint + method combination."""
    endpoint: str
    method: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    error_rate: float
    request_count: int
    period_start: float  # epoch
    period_end: float    # epoch


@dataclass(frozen=True)
class SLOViolation:
    """One specific SLO violation."""
    metric: str   # "p95_ms", "p99_ms", "error_rate"
    actual: float
    target: float


@dataclass(frozen=True)
class SLOComplianceResult:
    """SLO check result for a single endpoint."""
    endpoint: str
    method: str
    compliant: bool
    violations: list[SLOViolation]


# ---------------------------------------------------------------------------
# Internal accumulator
# ---------------------------------------------------------------------------

@dataclass
class _RequestRecord:
    latency_ms: float
    status_code: int
    timestamp: float


@dataclass
class _EndpointAccumulator:
    records: list[_RequestRecord] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, latency_ms: float, status_code: int) -> None:
        with self.lock:
            self.records.append(
                _RequestRecord(
                    latency_ms=latency_ms,
                    status_code=status_code,
                    timestamp=time.time(),
                )
            )

    def snapshot(self) -> list[_RequestRecord]:
        with self.lock:
            return list(self.records)


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Compute the given percentile from a pre-sorted list."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    idx = (pct / 100.0) * (n - 1)
    lower = int(math.floor(idx))
    upper = min(lower + 1, n - 1)
    frac = idx - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


# ---------------------------------------------------------------------------
# Dashboard Service
# ---------------------------------------------------------------------------

class SLODashboardService:
    """In-memory SLO metrics accumulator and dashboard."""

    def __init__(self, slo_target: SLOTarget | None = None) -> None:
        self._accumulators: dict[str, _EndpointAccumulator] = {}
        self._lock = threading.Lock()
        self.slo_target = slo_target or SLOTarget()

    @staticmethod
    def _key(endpoint: str, method: str) -> str:
        return f"{method.upper()}:{endpoint}"

    def _get_accumulator(self, endpoint: str, method: str) -> _EndpointAccumulator:
        key = self._key(endpoint, method)
        if key not in self._accumulators:
            with self._lock:
                if key not in self._accumulators:
                    self._accumulators[key] = _EndpointAccumulator()
        return self._accumulators[key]

    def record_request(
        self,
        endpoint: str,
        method: str,
        latency_ms: float,
        status_code: int,
    ) -> None:
        """Record a single request observation."""
        self._get_accumulator(endpoint, method).add(latency_ms, status_code)

    def get_endpoint_metrics(self, endpoint: str, method: str) -> EndpointMetrics | None:
        """Compute metrics for a single endpoint."""
        key = self._key(endpoint, method)
        acc = self._accumulators.get(key)
        if acc is None:
            return None
        records = acc.snapshot()
        if not records:
            return None
        return self._compute_metrics(endpoint, method, records)

    def get_slo_dashboard(self) -> list[EndpointMetrics]:
        """Return computed metrics for all recorded endpoints."""
        results: list[EndpointMetrics] = []
        with self._lock:
            keys = list(self._accumulators.keys())

        for key in keys:
            acc = self._accumulators[key]
            records = acc.snapshot()
            if not records:
                continue
            method, endpoint = key.split(":", 1)
            results.append(self._compute_metrics(endpoint, method, records))

        return sorted(results, key=lambda m: m.endpoint)

    def check_slo_compliance(self) -> list[SLOComplianceResult]:
        """Check all endpoints against SLO targets."""
        dashboard = self.get_slo_dashboard()
        results: list[SLOComplianceResult] = []
        for m in dashboard:
            violations: list[SLOViolation] = []
            if m.p95_ms > self.slo_target.p95_ms:
                violations.append(
                    SLOViolation(metric="p95_ms", actual=m.p95_ms, target=self.slo_target.p95_ms)
                )
            if m.p99_ms > self.slo_target.p99_ms:
                violations.append(
                    SLOViolation(metric="p99_ms", actual=m.p99_ms, target=self.slo_target.p99_ms)
                )
            if m.error_rate > self.slo_target.error_rate:
                violations.append(
                    SLOViolation(
                        metric="error_rate", actual=m.error_rate, target=self.slo_target.error_rate
                    )
                )
            results.append(
                SLOComplianceResult(
                    endpoint=m.endpoint,
                    method=m.method,
                    compliant=len(violations) == 0,
                    violations=violations,
                )
            )
        return results

    def reset(self) -> None:
        """Clear all accumulated data."""
        with self._lock:
            self._accumulators.clear()

    # ------------------------------------------------------------------
    @staticmethod
    def _compute_metrics(
        endpoint: str, method: str, records: list[_RequestRecord]
    ) -> EndpointMetrics:
        latencies = sorted(r.latency_ms for r in records)
        error_count = sum(1 for r in records if r.status_code >= 500)
        timestamps = [r.timestamp for r in records]
        return EndpointMetrics(
            endpoint=endpoint,
            method=method,
            p50_ms=round(_percentile(latencies, 50), 2),
            p95_ms=round(_percentile(latencies, 95), 2),
            p99_ms=round(_percentile(latencies, 99), 2),
            error_rate=round(error_count / len(records), 4) if records else 0.0,
            request_count=len(records),
            period_start=min(timestamps),
            period_end=max(timestamps),
        )
