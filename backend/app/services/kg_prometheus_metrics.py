"""Prometheus Metrics Exporter for Knowledge Graph Services.

This module provides comprehensive Prometheus metrics collection and export
for all Knowledge Graph components, following Prometheus best practices:
- Counter, Gauge, Histogram, Summary metric types
- Labels for multi-dimensional data
- Pre-defined KG-specific metrics for monitoring
- Integration with FastAPI for /metrics endpoint
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union
import asyncio
import re


class MetricType(str, Enum):
    """Prometheus metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricDefinition:
    """Definition of a Prometheus metric."""

    name: str
    type: MetricType
    help: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms
    quantiles: Optional[List[float]] = None  # For summaries

    def __post_init__(self):
        # Validate metric name
        if not re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', self.name):
            raise ValueError(f"Invalid metric name: {self.name}")

        # Validate label names
        for label in self.labels:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', label):
                raise ValueError(f"Invalid label name: {label}")


@dataclass
class LabelSet:
    """A set of label values for a metric."""

    labels: Dict[str, str]

    def __hash__(self):
        return hash(tuple(sorted(self.labels.items())))

    def __eq__(self, other):
        if not isinstance(other, LabelSet):
            return False
        return self.labels == other.labels


@dataclass
class MetricValue:
    """Current value(s) of a metric."""

    value: float = 0.0
    timestamp: Optional[float] = None
    # For histograms
    bucket_counts: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0
    # For summaries
    observations: List[float] = field(default_factory=list)


class Counter:
    """Prometheus Counter metric.

    A counter is a cumulative metric that represents a single monotonically
    increasing counter whose value can only increase or be reset to zero.
    """

    def __init__(self, definition: MetricDefinition):
        self.definition = definition
        self._values: Dict[LabelSet, MetricValue] = defaultdict(MetricValue)
        self._lock = threading.RLock()

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment the counter."""
        if value < 0:
            raise ValueError("Counter can only increase")

        label_set = LabelSet(labels or {})
        with self._lock:
            self._values[label_set].value += value
            self._values[label_set].timestamp = time.time()

    def labels(self, **kwargs) -> "Counter":
        """Return a child counter with the given labels."""
        child = Counter(self.definition)
        child._values = self._values
        child._lock = self._lock
        child._default_labels = kwargs
        return child

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        label_set = LabelSet(labels or {})
        with self._lock:
            return self._values[label_set].value

    def get_all(self) -> Dict[LabelSet, float]:
        """Get all counter values with labels."""
        with self._lock:
            return {ls: mv.value for ls, mv in self._values.items()}


class Gauge:
    """Prometheus Gauge metric.

    A gauge is a metric that represents a single numerical value that can
    arbitrarily go up and down.
    """

    def __init__(self, definition: MetricDefinition):
        self.definition = definition
        self._values: Dict[LabelSet, MetricValue] = defaultdict(MetricValue)
        self._lock = threading.RLock()

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Set the gauge to a value."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._values[label_set].value = value
            self._values[label_set].timestamp = time.time()

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment the gauge."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._values[label_set].value += value
            self._values[label_set].timestamp = time.time()

    def dec(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Decrement the gauge."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._values[label_set].value -= value
            self._values[label_set].timestamp = time.time()

    def set_to_current_time(self, labels: Optional[Dict[str, str]] = None):
        """Set gauge to current Unix timestamp."""
        self.set(time.time(), labels)

    def labels(self, **kwargs) -> "Gauge":
        """Return a child gauge with the given labels."""
        child = Gauge(self.definition)
        child._values = self._values
        child._lock = self._lock
        child._default_labels = kwargs
        return child

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        label_set = LabelSet(labels or {})
        with self._lock:
            return self._values[label_set].value

    def get_all(self) -> Dict[LabelSet, float]:
        """Get all gauge values with labels."""
        with self._lock:
            return {ls: mv.value for ls, mv in self._values.items()}


class Histogram:
    """Prometheus Histogram metric.

    A histogram samples observations and counts them in configurable buckets.
    It also provides a sum of all observed values.
    """

    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')]

    def __init__(self, definition: MetricDefinition):
        self.definition = definition
        self.buckets = definition.buckets or self.DEFAULT_BUCKETS
        self._values: Dict[LabelSet, MetricValue] = {}
        self._lock = threading.RLock()

    def _init_label_set(self, label_set: LabelSet):
        """Initialize bucket counts for a label set."""
        if label_set not in self._values:
            self._values[label_set] = MetricValue(
                bucket_counts={b: 0 for b in self.buckets},
                sum=0.0,
                count=0
            )

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._init_label_set(label_set)
            mv = self._values[label_set]
            mv.sum += value
            mv.count += 1
            # Increment all buckets where value <= bucket (Prometheus buckets are cumulative)
            for bucket in self.buckets:
                if value <= bucket:
                    mv.bucket_counts[bucket] += 1
            mv.timestamp = time.time()

    def time(self):
        """Context manager to time a block of code."""
        return HistogramTimer(self)

    def labels(self, **kwargs) -> "Histogram":
        """Return a child histogram with the given labels."""
        child = Histogram(self.definition)
        child.buckets = self.buckets
        child._values = self._values
        child._lock = self._lock
        child._default_labels = kwargs
        return child

    def get(self, labels: Optional[Dict[str, str]] = None) -> Tuple[Dict[float, int], float, int]:
        """Get current histogram value (buckets, sum, count)."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._init_label_set(label_set)
            mv = self._values[label_set]
            return mv.bucket_counts.copy(), mv.sum, mv.count

    def get_all(self) -> Dict[LabelSet, Tuple[Dict[float, int], float, int]]:
        """Get all histogram values with labels."""
        with self._lock:
            return {ls: (mv.bucket_counts.copy(), mv.sum, mv.count) for ls, mv in self._values.items()}


class HistogramTimer:
    """Timer context manager for Histogram."""

    def __init__(self, histogram: Histogram, labels: Optional[Dict[str, str]] = None):
        self.histogram = histogram
        self.labels = labels
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.histogram.observe(duration, self.labels)
        return False


class Summary:
    """Prometheus Summary metric.

    Similar to a histogram, a summary samples observations over a sliding time window.
    """

    DEFAULT_QUANTILES = [0.5, 0.9, 0.95, 0.99]

    def __init__(self, definition: MetricDefinition, max_observations: int = 1000):
        self.definition = definition
        self.quantiles = definition.quantiles or self.DEFAULT_QUANTILES
        self.max_observations = max_observations
        self._values: Dict[LabelSet, MetricValue] = {}
        self._lock = threading.RLock()

    def _init_label_set(self, label_set: LabelSet):
        """Initialize for a label set."""
        if label_set not in self._values:
            self._values[label_set] = MetricValue(
                observations=[],
                sum=0.0,
                count=0
            )

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._init_label_set(label_set)
            mv = self._values[label_set]
            mv.observations.append(value)
            mv.sum += value
            mv.count += 1
            # Keep only recent observations
            if len(mv.observations) > self.max_observations:
                removed = mv.observations.pop(0)
                mv.sum -= removed
            mv.timestamp = time.time()

    def time(self):
        """Context manager to time a block of code."""
        return SummaryTimer(self)

    def get_quantile(self, quantile: float, labels: Optional[Dict[str, str]] = None) -> float:
        """Get a specific quantile value."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._init_label_set(label_set)
            observations = sorted(self._values[label_set].observations)
            if not observations:
                return 0.0
            # Use (len-1) for proper 0-indexed array quantile calculation
            index = int(quantile * (len(observations) - 1))
            index = min(index, len(observations) - 1)
            return observations[index]

    def labels(self, **kwargs) -> "Summary":
        """Return a child summary with the given labels."""
        child = Summary(self.definition, self.max_observations)
        child.quantiles = self.quantiles
        child._values = self._values
        child._lock = self._lock
        child._default_labels = kwargs
        return child

    def get(self, labels: Optional[Dict[str, str]] = None) -> Tuple[Dict[float, float], float, int]:
        """Get current summary value (quantiles, sum, count)."""
        label_set = LabelSet(labels or {})
        with self._lock:
            self._init_label_set(label_set)
            mv = self._values[label_set]
            quantile_values = {q: self.get_quantile(q, labels) for q in self.quantiles}
            return quantile_values, mv.sum, mv.count


class SummaryTimer:
    """Timer context manager for Summary."""

    def __init__(self, summary: Summary, labels: Optional[Dict[str, str]] = None):
        self.summary = summary
        self.labels = labels
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.summary.observe(duration, self.labels)
        return False


class KGPrometheusRegistry:
    """Registry for Prometheus metrics."""

    def __init__(self, prefix: str = "kg"):
        self.prefix = prefix
        self._metrics: Dict[str, Union[Counter, Gauge, Histogram, Summary]] = {}
        self._lock = threading.RLock()

    def _full_name(self, name: str) -> str:
        """Get full metric name with prefix."""
        return f"{self.prefix}_{name}"

    def counter(self, name: str, help: str, labels: Optional[List[str]] = None) -> Counter:
        """Create or get a counter metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                definition = MetricDefinition(
                    name=full_name,
                    type=MetricType.COUNTER,
                    help=help,
                    labels=labels or []
                )
                self._metrics[full_name] = Counter(definition)
            return self._metrics[full_name]

    def gauge(self, name: str, help: str, labels: Optional[List[str]] = None) -> Gauge:
        """Create or get a gauge metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                definition = MetricDefinition(
                    name=full_name,
                    type=MetricType.GAUGE,
                    help=help,
                    labels=labels or []
                )
                self._metrics[full_name] = Gauge(definition)
            return self._metrics[full_name]

    def histogram(
        self,
        name: str,
        help: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None
    ) -> Histogram:
        """Create or get a histogram metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                definition = MetricDefinition(
                    name=full_name,
                    type=MetricType.HISTOGRAM,
                    help=help,
                    labels=labels or [],
                    buckets=buckets
                )
                self._metrics[full_name] = Histogram(definition)
            return self._metrics[full_name]

    def summary(
        self,
        name: str,
        help: str,
        labels: Optional[List[str]] = None,
        quantiles: Optional[List[float]] = None
    ) -> Summary:
        """Create or get a summary metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                definition = MetricDefinition(
                    name=full_name,
                    type=MetricType.SUMMARY,
                    help=help,
                    labels=labels or [],
                    quantiles=quantiles
                )
                self._metrics[full_name] = Summary(definition)
            return self._metrics[full_name]

    def get_metric(self, name: str) -> Optional[Union[Counter, Gauge, Histogram, Summary]]:
        """Get a metric by name."""
        full_name = self._full_name(name)
        with self._lock:
            return self._metrics.get(full_name)

    def get_all_metrics(self) -> Dict[str, Union[Counter, Gauge, Histogram, Summary]]:
        """Get all registered metrics."""
        with self._lock:
            return self._metrics.copy()

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        label_strs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(label_strs) + "}"

    def export(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []

        with self._lock:
            for name, metric in sorted(self._metrics.items()):
                definition = metric.definition

                # Add HELP and TYPE
                lines.append(f"# HELP {name} {definition.help}")
                lines.append(f"# TYPE {name} {definition.type.value}")

                if isinstance(metric, Counter):
                    for label_set, value in metric.get_all().items():
                        labels_str = self._format_labels(label_set.labels)
                        lines.append(f"{name}{labels_str} {value}")

                elif isinstance(metric, Gauge):
                    for label_set, value in metric.get_all().items():
                        labels_str = self._format_labels(label_set.labels)
                        lines.append(f"{name}{labels_str} {value}")

                elif isinstance(metric, Histogram):
                    for label_set, (buckets, total, count) in metric.get_all().items():
                        base_labels = label_set.labels
                        # Buckets are already cumulative from observe()
                        for bucket, bucket_count in sorted(buckets.items()):
                            bucket_labels = {**base_labels, "le": str(bucket) if bucket != float('inf') else "+Inf"}
                            labels_str = self._format_labels(bucket_labels)
                            lines.append(f"{name}_bucket{labels_str} {bucket_count}")

                        labels_str = self._format_labels(base_labels)
                        lines.append(f"{name}_sum{labels_str} {total}")
                        lines.append(f"{name}_count{labels_str} {count}")

                elif isinstance(metric, Summary):
                    for label_set in metric._values.keys():
                        base_labels = label_set.labels
                        quantiles, total, count = metric.get(base_labels)

                        for quantile, value in quantiles.items():
                            q_labels = {**base_labels, "quantile": str(quantile)}
                            labels_str = self._format_labels(q_labels)
                            lines.append(f"{name}{labels_str} {value}")

                        labels_str = self._format_labels(base_labels)
                        lines.append(f"{name}_sum{labels_str} {total}")
                        lines.append(f"{name}_count{labels_str} {count}")

                lines.append("")

        return "\n".join(lines)


class KGMetricsService:
    """Knowledge Graph Prometheus Metrics Service.

    Provides pre-defined metrics for all KG components.
    """

    def __init__(self, prefix: str = "kg"):
        self.registry = KGPrometheusRegistry(prefix)
        self._setup_metrics()

    def _setup_metrics(self):
        """Setup all KG metrics."""

        # =============
        # Request metrics
        # =============
        self.requests_total = self.registry.counter(
            "requests_total",
            "Total number of requests",
            labels=["endpoint", "method", "status"]
        )

        self.request_duration_seconds = self.registry.histogram(
            "request_duration_seconds",
            "Request duration in seconds",
            labels=["endpoint", "method"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        self.requests_in_progress = self.registry.gauge(
            "requests_in_progress",
            "Number of requests currently in progress",
            labels=["endpoint"]
        )

        # =============
        # Neo4j metrics
        # =============
        self.neo4j_queries_total = self.registry.counter(
            "neo4j_queries_total",
            "Total number of Neo4j queries",
            labels=["query_type", "status"]
        )

        self.neo4j_query_duration_seconds = self.registry.histogram(
            "neo4j_query_duration_seconds",
            "Neo4j query duration in seconds",
            labels=["query_type"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
        )

        self.neo4j_pool_connections = self.registry.gauge(
            "neo4j_pool_connections",
            "Number of Neo4j pool connections",
            labels=["state"]  # active, idle, waiting
        )

        self.neo4j_nodes_created = self.registry.counter(
            "neo4j_nodes_created_total",
            "Total number of nodes created",
            labels=["label"]
        )

        self.neo4j_relationships_created = self.registry.counter(
            "neo4j_relationships_created_total",
            "Total number of relationships created",
            labels=["type"]
        )

        # =============
        # Reasoning metrics
        # =============
        self.reasoning_queries_total = self.registry.counter(
            "reasoning_queries_total",
            "Total number of reasoning queries",
            labels=["strategy", "status"]
        )

        self.reasoning_duration_seconds = self.registry.histogram(
            "reasoning_duration_seconds",
            "Reasoning query duration in seconds",
            labels=["strategy"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
        )

        self.reasoning_paths_found = self.registry.histogram(
            "reasoning_paths_found",
            "Number of paths found per query",
            labels=["strategy"],
            buckets=[0, 1, 5, 10, 25, 50, 100, 250, 500]
        )

        self.reasoning_hops = self.registry.histogram(
            "reasoning_hops",
            "Number of hops in reasoning paths",
            labels=["strategy"],
            buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        )

        # =============
        # Cache metrics
        # =============
        self.cache_hits_total = self.registry.counter(
            "cache_hits_total",
            "Total number of cache hits",
            labels=["cache_type"]
        )

        self.cache_misses_total = self.registry.counter(
            "cache_misses_total",
            "Total number of cache misses",
            labels=["cache_type"]
        )

        self.cache_evictions_total = self.registry.counter(
            "cache_evictions_total",
            "Total number of cache evictions",
            labels=["cache_type"]
        )

        self.cache_size = self.registry.gauge(
            "cache_size_bytes",
            "Current cache size in bytes",
            labels=["cache_type"]
        )

        self.cache_entries = self.registry.gauge(
            "cache_entries",
            "Number of entries in cache",
            labels=["cache_type"]
        )

        # =============
        # UMLS metrics
        # =============
        self.umls_concepts_total = self.registry.gauge(
            "umls_concepts_total",
            "Total number of UMLS concepts loaded",
            labels=["vocabulary"]
        )

        self.umls_relationships_total = self.registry.gauge(
            "umls_relationships_total",
            "Total number of UMLS relationships loaded",
            labels=["type"]
        )

        self.umls_lookups_total = self.registry.counter(
            "umls_lookups_total",
            "Total number of UMLS lookups",
            labels=["lookup_type", "status"]
        )

        self.umls_lookup_duration_seconds = self.registry.histogram(
            "umls_lookup_duration_seconds",
            "UMLS lookup duration in seconds",
            labels=["lookup_type"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
        )

        # =============
        # Embedding metrics
        # =============
        self.embeddings_generated_total = self.registry.counter(
            "embeddings_generated_total",
            "Total number of embeddings generated",
            labels=["model"]
        )

        self.embedding_generation_duration_seconds = self.registry.histogram(
            "embedding_generation_duration_seconds",
            "Embedding generation duration in seconds",
            labels=["model", "batch_size"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )

        self.similarity_searches_total = self.registry.counter(
            "similarity_searches_total",
            "Total number of similarity searches",
            labels=["strategy", "status"]
        )

        self.similarity_search_duration_seconds = self.registry.histogram(
            "similarity_search_duration_seconds",
            "Similarity search duration in seconds",
            labels=["strategy"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        )

        # =============
        # MDT metrics
        # =============
        self.mdt_sessions_total = self.registry.counter(
            "mdt_sessions_total",
            "Total number of MDT sessions",
            labels=["status"]
        )

        self.mdt_session_duration_seconds = self.registry.histogram(
            "mdt_session_duration_seconds",
            "MDT session duration in seconds",
            labels=[],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
        )

        self.mdt_agent_recommendations = self.registry.counter(
            "mdt_agent_recommendations_total",
            "Total number of agent recommendations",
            labels=["agent", "confidence_level"]
        )

        self.mdt_consensus_reached = self.registry.counter(
            "mdt_consensus_reached_total",
            "Total number of times consensus was reached",
            labels=["consensus_level"]
        )

        # =============
        # Batch processing metrics
        # =============
        self.batch_jobs_total = self.registry.counter(
            "batch_jobs_total",
            "Total number of batch jobs",
            labels=["operation", "status"]
        )

        self.batch_job_duration_seconds = self.registry.histogram(
            "batch_job_duration_seconds",
            "Batch job duration in seconds",
            labels=["operation"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
        )

        self.batch_items_processed = self.registry.counter(
            "batch_items_processed_total",
            "Total number of items processed in batch jobs",
            labels=["operation", "status"]
        )

        # =============
        # Circuit breaker metrics
        # =============
        self.circuit_breaker_state = self.registry.gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            labels=["service"]
        )

        self.circuit_breaker_failures = self.registry.counter(
            "circuit_breaker_failures_total",
            "Total number of circuit breaker failures",
            labels=["service"]
        )

        self.circuit_breaker_successes = self.registry.counter(
            "circuit_breaker_successes_total",
            "Total number of circuit breaker successes",
            labels=["service"]
        )

        self.circuit_breaker_opens = self.registry.counter(
            "circuit_breaker_opens_total",
            "Total number of times circuit breaker opened",
            labels=["service"]
        )

        # =============
        # Webhook metrics
        # =============
        self.webhook_deliveries_total = self.registry.counter(
            "webhook_deliveries_total",
            "Total number of webhook deliveries",
            labels=["event_type", "status"]
        )

        self.webhook_delivery_duration_seconds = self.registry.histogram(
            "webhook_delivery_duration_seconds",
            "Webhook delivery duration in seconds",
            labels=["event_type"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        self.webhook_retries = self.registry.counter(
            "webhook_retries_total",
            "Total number of webhook retries",
            labels=["event_type"]
        )

        # =============
        # Data export metrics
        # =============
        self.data_exports_total = self.registry.counter(
            "data_exports_total",
            "Total number of data exports",
            labels=["format", "status"]
        )

        self.data_export_duration_seconds = self.registry.histogram(
            "data_export_duration_seconds",
            "Data export duration in seconds",
            labels=["format"],
            buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]
        )

        self.data_export_records = self.registry.counter(
            "data_export_records_total",
            "Total number of records exported",
            labels=["format"]
        )

        # =============
        # Benchmark metrics
        # =============
        self.benchmark_runs_total = self.registry.counter(
            "benchmark_runs_total",
            "Total number of benchmark runs",
            labels=["suite", "status"]
        )

        self.benchmark_score = self.registry.gauge(
            "benchmark_score",
            "Latest benchmark score",
            labels=["suite", "metric"]
        )

        self.benchmark_duration_seconds = self.registry.histogram(
            "benchmark_duration_seconds",
            "Benchmark duration in seconds",
            labels=["suite"],
            buckets=[10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0]
        )

        # =============
        # System metrics
        # =============
        self.memory_usage_bytes = self.registry.gauge(
            "memory_usage_bytes",
            "Current memory usage in bytes",
            labels=["type"]  # heap, rss, etc.
        )

        self.cpu_usage_percent = self.registry.gauge(
            "cpu_usage_percent",
            "Current CPU usage percentage",
            labels=[]
        )

        self.active_threads = self.registry.gauge(
            "active_threads",
            "Number of active threads",
            labels=[]
        )

        self.uptime_seconds = self.registry.gauge(
            "uptime_seconds",
            "Service uptime in seconds",
            labels=[]
        )

        self._start_time = time.time()

    # ==================
    # Convenience methods
    # ==================

    def record_request(
        self,
        endpoint: str,
        method: str,
        status: int,
        duration: float
    ):
        """Record a request completion."""
        status_str = str(status)
        self.requests_total.inc(labels={
            "endpoint": endpoint,
            "method": method,
            "status": status_str
        })
        self.request_duration_seconds.observe(duration, labels={
            "endpoint": endpoint,
            "method": method
        })

    def record_neo4j_query(
        self,
        query_type: str,
        duration: float,
        success: bool = True
    ):
        """Record a Neo4j query."""
        status = "success" if success else "error"
        self.neo4j_queries_total.inc(labels={
            "query_type": query_type,
            "status": status
        })
        self.neo4j_query_duration_seconds.observe(duration, labels={
            "query_type": query_type
        })

    def record_reasoning_query(
        self,
        strategy: str,
        duration: float,
        paths_found: int,
        avg_hops: float,
        success: bool = True
    ):
        """Record a reasoning query."""
        status = "success" if success else "error"
        self.reasoning_queries_total.inc(labels={
            "strategy": strategy,
            "status": status
        })
        self.reasoning_duration_seconds.observe(duration, labels={
            "strategy": strategy
        })
        self.reasoning_paths_found.observe(paths_found, labels={
            "strategy": strategy
        })
        if avg_hops > 0:
            self.reasoning_hops.observe(avg_hops, labels={
                "strategy": strategy
            })

    def record_cache_hit(self, cache_type: str):
        """Record a cache hit."""
        self.cache_hits_total.inc(labels={"cache_type": cache_type})

    def record_cache_miss(self, cache_type: str):
        """Record a cache miss."""
        self.cache_misses_total.inc(labels={"cache_type": cache_type})

    def update_cache_stats(self, cache_type: str, size_bytes: int, entries: int):
        """Update cache statistics."""
        self.cache_size.set(size_bytes, labels={"cache_type": cache_type})
        self.cache_entries.set(entries, labels={"cache_type": cache_type})

    def record_webhook_delivery(
        self,
        event_type: str,
        duration: float,
        success: bool = True,
        retry_count: int = 0
    ):
        """Record a webhook delivery."""
        status = "success" if success else "failure"
        self.webhook_deliveries_total.inc(labels={
            "event_type": event_type,
            "status": status
        })
        self.webhook_delivery_duration_seconds.observe(duration, labels={
            "event_type": event_type
        })
        if retry_count > 0:
            for _ in range(retry_count):
                self.webhook_retries.inc(labels={"event_type": event_type})

    def record_data_export(
        self,
        format: str,
        duration: float,
        records: int,
        success: bool = True
    ):
        """Record a data export."""
        status = "success" if success else "failure"
        self.data_exports_total.inc(labels={
            "format": format,
            "status": status
        })
        self.data_export_duration_seconds.observe(duration, labels={
            "format": format
        })
        self.data_export_records.inc(records, labels={"format": format})

    def update_system_metrics(
        self,
        memory_bytes: Optional[int] = None,
        cpu_percent: Optional[float] = None,
        threads: Optional[int] = None
    ):
        """Update system metrics."""
        if memory_bytes is not None:
            self.memory_usage_bytes.set(memory_bytes, labels={"type": "rss"})
        if cpu_percent is not None:
            self.cpu_usage_percent.set(cpu_percent)
        if threads is not None:
            self.active_threads.set(threads)
        self.uptime_seconds.set(time.time() - self._start_time)

    def export(self) -> str:
        """Export all metrics in Prometheus text format."""
        return self.registry.export()


# Decorators for automatic metric collection

F = TypeVar('F', bound=Callable[..., Any])


def metrics_request(metrics: KGMetricsService, endpoint: str):
    """Decorator to automatically collect request metrics."""
    def decorator(func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            method = kwargs.get("method", "UNKNOWN")
            metrics.requests_in_progress.inc(labels={"endpoint": endpoint})
            start = time.time()
            status = 500
            try:
                result = func(*args, **kwargs)
                status = 200
                return result
            except Exception as e:
                status = getattr(e, "status_code", 500)
                raise
            finally:
                duration = time.time() - start
                metrics.requests_in_progress.dec(labels={"endpoint": endpoint})
                metrics.record_request(endpoint, method, status, duration)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            method = kwargs.get("method", "UNKNOWN")
            metrics.requests_in_progress.inc(labels={"endpoint": endpoint})
            start = time.time()
            status = 500
            try:
                result = await func(*args, **kwargs)
                status = 200
                return result
            except Exception as e:
                status = getattr(e, "status_code", 500)
                raise
            finally:
                duration = time.time() - start
                metrics.requests_in_progress.dec(labels={"endpoint": endpoint})
                metrics.record_request(endpoint, method, status, duration)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def metrics_neo4j(metrics: KGMetricsService, query_type: str):
    """Decorator to automatically collect Neo4j query metrics."""
    def decorator(func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            success = False
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                duration = time.time() - start
                metrics.record_neo4j_query(query_type, duration, success)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            success = False
            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            finally:
                duration = time.time() - start
                metrics.record_neo4j_query(query_type, duration, success)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# Singleton instance
_metrics_service: Optional[KGMetricsService] = None


def get_metrics_service() -> KGMetricsService:
    """Get the singleton metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = KGMetricsService()
    return _metrics_service


def reset_metrics_service():
    """Reset the metrics service (for testing)."""
    global _metrics_service
    _metrics_service = None
