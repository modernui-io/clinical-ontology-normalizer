"""Prometheus-Compatible Metrics Collector Service (DEVOPS-2).

Pure-Python implementation of Prometheus metric types (counter, gauge,
histogram) with text exposition format export.  No external dependencies
required.

Usage:
    from app.services.metrics_collector_service import get_metrics_collector

    mc = get_metrics_collector()
    mc.counter_inc("screening_requests_total", labels={"trial_id": "T1", "result": "eligible"})
    mc.histogram_observe("screening_duration_seconds", 1.23, labels={"trial_id": "T1"})
    print(mc.export_prometheus())
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.schemas.observability import (
    HistogramBucket,
    HistogramData,
    MetricLabelSet,
    MetricSchema,
    MetricType,
)

# ---------------------------------------------------------------------------
# Internal data containers
# ---------------------------------------------------------------------------

_LABEL_KEY = tuple[tuple[str, str], ...]


def _label_key(labels: dict[str, str] | None) -> _LABEL_KEY:
    """Convert a label dict to a hashable key."""
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _label_dict(key: _LABEL_KEY) -> dict[str, str]:
    """Convert a hashable key back to a label dict."""
    return dict(key)


# ---------------------------------------------------------------------------
# Metric storage types
# ---------------------------------------------------------------------------


class _CounterStore:
    """Thread-safe counter storage."""

    def __init__(self) -> None:
        self.values: dict[_LABEL_KEY, float] = defaultdict(float)
        self.timestamps: dict[_LABEL_KEY, list[float]] = defaultdict(list)

    def inc(self, labels: _LABEL_KEY, value: float = 1.0) -> None:
        self.values[labels] += value
        self.timestamps[labels].append(time.monotonic())

    def get(self, labels: _LABEL_KEY) -> float:
        return self.values[labels]


class _GaugeStore:
    """Thread-safe gauge storage."""

    def __init__(self) -> None:
        self.values: dict[_LABEL_KEY, float] = defaultdict(float)

    def set(self, labels: _LABEL_KEY, value: float) -> None:
        self.values[labels] = value

    def inc(self, labels: _LABEL_KEY, value: float = 1.0) -> None:
        self.values[labels] += value

    def dec(self, labels: _LABEL_KEY, value: float = 1.0) -> None:
        self.values[labels] -= value

    def get(self, labels: _LABEL_KEY) -> float:
        return self.values[labels]


class _HistogramStore:
    """Thread-safe histogram storage."""

    def __init__(self, buckets: list[float]) -> None:
        # Ensure +Inf is always present
        self.bucket_bounds = sorted(set(buckets))
        if not self.bucket_bounds or self.bucket_bounds[-1] != float("inf"):
            self.bucket_bounds.append(float("inf"))
        self.bucket_counts: dict[_LABEL_KEY, list[int]] = defaultdict(
            lambda: [0] * len(self.bucket_bounds)
        )
        self.sums: dict[_LABEL_KEY, float] = defaultdict(float)
        self.counts: dict[_LABEL_KEY, int] = defaultdict(int)
        self.observations: dict[_LABEL_KEY, list[float]] = defaultdict(list)

    def observe(self, labels: _LABEL_KEY, value: float) -> None:
        self.sums[labels] += value
        self.counts[labels] += 1
        self.observations[labels].append(value)
        for i, bound in enumerate(self.bucket_bounds):
            if value <= bound:
                self.bucket_counts[labels][i] += 1

    def percentile(self, labels: _LABEL_KEY, p: float) -> float | None:
        """Compute the p-th percentile (0-100) from observations."""
        obs = self.observations.get(labels, [])
        if not obs:
            return None
        sorted_obs = sorted(obs)
        k = (p / 100.0) * (len(sorted_obs) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_obs[int(k)]
        return sorted_obs[f] * (c - k) + sorted_obs[c] * (k - f)


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------


class _MetricDef:
    """Internal representation of a registered metric."""

    def __init__(
        self,
        name: str,
        metric_type: MetricType,
        help_text: str = "",
        label_names: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> None:
        self.name = name
        self.metric_type = metric_type
        self.help_text = help_text
        self.label_names = label_names or []

        if metric_type == MetricType.COUNTER:
            self.store: _CounterStore | _GaugeStore | _HistogramStore = _CounterStore()
        elif metric_type == MetricType.GAUGE:
            self.store = _GaugeStore()
        elif metric_type == MetricType.HISTOGRAM:
            default_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
            self.store = _HistogramStore(buckets or default_buckets)


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Prometheus-compatible metrics collector with counter, gauge, histogram types.

    Thread-safe: all mutations guarded by ``_lock``.
    """

    DEFAULT_HISTOGRAM_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

    def __init__(self) -> None:
        self._metrics: dict[str, _MetricDef] = {}
        self._lock = threading.Lock()
        self._rate_window_seconds: float = 60.0

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_counter(
        self,
        name: str,
        help_text: str = "",
        label_names: list[str] | None = None,
    ) -> None:
        """Register a counter metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = _MetricDef(
                    name, MetricType.COUNTER, help_text, label_names
                )

    def register_gauge(
        self,
        name: str,
        help_text: str = "",
        label_names: list[str] | None = None,
    ) -> None:
        """Register a gauge metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = _MetricDef(
                    name, MetricType.GAUGE, help_text, label_names
                )

    def register_histogram(
        self,
        name: str,
        help_text: str = "",
        label_names: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> None:
        """Register a histogram metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = _MetricDef(
                    name, MetricType.HISTOGRAM, help_text, label_names, buckets
                )

    # ------------------------------------------------------------------
    # Counter operations
    # ------------------------------------------------------------------

    def counter_inc(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.COUNTER:
                return
            assert isinstance(m.store, _CounterStore)
            m.store.inc(_label_key(labels), value)

    def counter_get(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Get current counter value."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.COUNTER:
                return 0.0
            assert isinstance(m.store, _CounterStore)
            return m.store.get(_label_key(labels))

    # ------------------------------------------------------------------
    # Gauge operations
    # ------------------------------------------------------------------

    def gauge_set(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge to an arbitrary value."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.GAUGE:
                return
            assert isinstance(m.store, _GaugeStore)
            m.store.set(_label_key(labels), value)

    def gauge_inc(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a gauge."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.GAUGE:
                return
            assert isinstance(m.store, _GaugeStore)
            m.store.inc(_label_key(labels), value)

    def gauge_dec(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Decrement a gauge."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.GAUGE:
                return
            assert isinstance(m.store, _GaugeStore)
            m.store.dec(_label_key(labels), value)

    def gauge_get(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Get current gauge value."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.GAUGE:
                return 0.0
            assert isinstance(m.store, _GaugeStore)
            return m.store.get(_label_key(labels))

    # ------------------------------------------------------------------
    # Histogram operations
    # ------------------------------------------------------------------

    def histogram_observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record an observation in a histogram."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.HISTOGRAM:
                return
            assert isinstance(m.store, _HistogramStore)
            m.store.observe(_label_key(labels), value)

    def histogram_get_count(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> int:
        """Get the total observation count for a histogram."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.HISTOGRAM:
                return 0
            assert isinstance(m.store, _HistogramStore)
            return m.store.counts[_label_key(labels)]

    def histogram_get_sum(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Get the sum of observed values for a histogram."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.HISTOGRAM:
                return 0.0
            assert isinstance(m.store, _HistogramStore)
            return m.store.sums[_label_key(labels)]

    def histogram_percentile(
        self,
        name: str,
        percentile: float,
        labels: dict[str, str] | None = None,
    ) -> float | None:
        """Get a percentile value from histogram observations."""
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.HISTOGRAM:
                return None
            assert isinstance(m.store, _HistogramStore)
            return m.store.percentile(_label_key(labels), percentile)

    # ------------------------------------------------------------------
    # Rate calculation
    # ------------------------------------------------------------------

    def counter_rate(
        self,
        name: str,
        window_seconds: float | None = None,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Calculate requests per second for a counter over a time window.

        Uses the monotonic timestamp recorded with each increment.
        """
        window = window_seconds or self._rate_window_seconds
        with self._lock:
            m = self._metrics.get(name)
            if m is None or m.metric_type != MetricType.COUNTER:
                return 0.0
            assert isinstance(m.store, _CounterStore)
            key = _label_key(labels)
            timestamps = m.store.timestamps.get(key, [])
            if not timestamps:
                return 0.0

            now = time.monotonic()
            cutoff = now - window
            count_in_window = sum(1 for t in timestamps if t >= cutoff)
            return count_in_window / window

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_all_metrics(self) -> list[MetricSchema]:
        """Return all metrics as Pydantic schemas."""
        with self._lock:
            result: list[MetricSchema] = []
            for name, m in sorted(self._metrics.items()):
                schema = MetricSchema(
                    name=name,
                    metric_type=m.metric_type,
                    help_text=m.help_text,
                    label_names=m.label_names,
                )

                if m.metric_type in (MetricType.COUNTER, MetricType.GAUGE):
                    store = m.store
                    assert isinstance(store, (_CounterStore, _GaugeStore))
                    for key, value in store.values.items():
                        schema.values.append(
                            MetricLabelSet(labels=_label_dict(key), value=value)
                        )
                elif m.metric_type == MetricType.HISTOGRAM:
                    store = m.store
                    assert isinstance(store, _HistogramStore)
                    all_keys = set(store.counts.keys()) | set(store.sums.keys())
                    for key in all_keys:
                        buckets = []
                        for i, bound in enumerate(store.bucket_bounds):
                            counts = store.bucket_counts.get(key, [0] * len(store.bucket_bounds))
                            buckets.append(
                                HistogramBucket(le=bound, count=counts[i])
                            )
                        schema.histograms.append(
                            HistogramData(
                                labels=_label_dict(key),
                                buckets=buckets,
                                count=store.counts[key],
                                sum=store.sums[key],
                            )
                        )

                result.append(schema)
            return result

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text exposition format."""
        with self._lock:
            lines: list[str] = []
            for name, m in sorted(self._metrics.items()):
                # HELP line
                if m.help_text:
                    lines.append(f"# HELP {name} {m.help_text}")
                # TYPE line
                lines.append(f"# TYPE {name} {m.metric_type.value}")

                if m.metric_type in (MetricType.COUNTER, MetricType.GAUGE):
                    store = m.store
                    assert isinstance(store, (_CounterStore, _GaugeStore))
                    if not store.values:
                        lines.append(f"{name} 0")
                    else:
                        for key, value in sorted(store.values.items()):
                            label_str = self._format_labels(key)
                            lines.append(f"{name}{label_str} {self._format_value(value)}")

                elif m.metric_type == MetricType.HISTOGRAM:
                    store = m.store
                    assert isinstance(store, _HistogramStore)
                    all_keys = set(store.counts.keys()) | set(store.sums.keys())
                    if not all_keys:
                        all_keys = {()}
                    for key in sorted(all_keys):
                        label_str_base = self._format_labels(key)
                        # Cumulative bucket counts
                        cumulative = 0
                        bucket_counts = store.bucket_counts.get(
                            key, [0] * len(store.bucket_bounds)
                        )
                        for i, bound in enumerate(store.bucket_bounds):
                            cumulative += bucket_counts[i]
                            if bound == float("inf"):
                                le_str = "+Inf"
                            else:
                                le_str = self._format_value(bound)
                            if key:
                                # Insert le inside existing labels
                                labels_dict = _label_dict(key)
                                labels_dict["le"] = le_str
                                bucket_label_str = self._format_labels(
                                    _label_key(labels_dict)
                                )
                            else:
                                bucket_label_str = f'{{le="{le_str}"}}'
                            lines.append(
                                f"{name}_bucket{bucket_label_str} {cumulative}"
                            )
                        # _count and _sum
                        lines.append(
                            f"{name}_count{label_str_base} {store.counts.get(key, 0)}"
                        )
                        lines.append(
                            f"{name}_sum{label_str_base} {self._format_value(store.sums.get(key, 0.0))}"
                        )

            return "\n".join(lines) + "\n" if lines else ""

    @staticmethod
    def _format_labels(key: _LABEL_KEY) -> str:
        """Format label key as Prometheus label string."""
        if not key:
            return ""
        parts = [f'{k}="{v}"' for k, v in key]
        return "{" + ",".join(parts) + "}"

    @staticmethod
    def _format_value(value: float) -> str:
        """Format a numeric value for Prometheus exposition."""
        if value == float("inf"):
            return "+Inf"
        if value == float("-inf"):
            return "-Inf"
        if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return str(value)

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()

    def get_metric_names(self) -> list[str]:
        """Return all registered metric names."""
        with self._lock:
            return sorted(self._metrics.keys())


# ---------------------------------------------------------------------------
# Singleton + default metrics registration
# ---------------------------------------------------------------------------

_metrics_collector: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Return the global MetricsCollector singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        with _collector_lock:
            if _metrics_collector is None:
                _metrics_collector = MetricsCollector()
                _register_default_metrics(_metrics_collector)
    return _metrics_collector


def _register_default_metrics(mc: MetricsCollector) -> None:
    """Register pre-defined clinical trial metrics."""
    # Screening
    mc.register_counter(
        "screening_requests_total",
        help_text="Total number of trial screening requests",
        label_names=["trial_id", "result"],
    )
    mc.register_histogram(
        "screening_duration_seconds",
        help_text="Duration of screening operations in seconds",
        label_names=["trial_id"],
        buckets=[0.1, 0.5, 1, 2, 5, 10],
    )

    # FHIR
    mc.register_counter(
        "fhir_imports_total",
        help_text="Total number of FHIR import operations",
        label_names=["resource_type", "status"],
    )
    mc.register_histogram(
        "fhir_import_duration_seconds",
        help_text="Duration of FHIR import operations in seconds",
        label_names=["resource_type"],
    )

    # NLP
    mc.register_counter(
        "nlp_extractions_total",
        help_text="Total number of NLP extraction operations",
        label_names=["pipeline", "status"],
    )

    # Patients / facts
    mc.register_gauge(
        "active_patients",
        help_text="Number of active patients in the system",
    )
    mc.register_gauge(
        "clinical_facts_total",
        help_text="Total number of clinical facts",
    )

    # API request metrics
    mc.register_histogram(
        "api_request_duration_seconds",
        help_text="Duration of API requests in seconds",
        label_names=["method", "endpoint", "status"],
    )


def reset_metrics_collector() -> None:
    """Reset the singleton for testing."""
    global _metrics_collector
    with _collector_lock:
        _metrics_collector = None
