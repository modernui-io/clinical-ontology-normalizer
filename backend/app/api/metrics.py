"""Prometheus-compatible metrics endpoint for Clinical Ontology Normalizer.

Provides metrics in Prometheus exposition format for monitoring and alerting.

Tracked Metrics:
- http_requests_total: Counter of total HTTP requests by method, endpoint, status
- http_request_duration_seconds: Histogram of request durations
- http_requests_in_flight: Gauge of currently active requests
- http_request_errors_total: Counter of request errors by type
- app_info: Info metric with application version

Usage:
    GET /api/v1/metrics - Prometheus metrics endpoint

The metrics are collected by the MetricsMiddleware and exposed here.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["Metrics"])


# =============================================================================
# Metric Types and Storage
# =============================================================================


@dataclass
class CounterMetric:
    """A monotonically increasing counter metric."""

    name: str
    help_text: str
    labels: list[str] = field(default_factory=list)
    values: dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    _lock: Lock = field(default_factory=Lock)

    def inc(self, labels: tuple | None = None, value: float = 1.0) -> None:
        """Increment the counter.

        Args:
            labels: Tuple of label values in order.
            value: Amount to increment by (must be positive).
        """
        if value < 0:
            raise ValueError("Counter can only be incremented")
        labels = labels or ()
        with self._lock:
            self.values[labels] += value

    def get(self, labels: tuple | None = None) -> float:
        """Get the current counter value.

        Args:
            labels: Tuple of label values.

        Returns:
            Current counter value.
        """
        labels = labels or ()
        with self._lock:
            return self.values[labels]


@dataclass
class GaugeMetric:
    """A metric that can go up and down."""

    name: str
    help_text: str
    labels: list[str] = field(default_factory=list)
    values: dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    _lock: Lock = field(default_factory=Lock)

    def set(self, value: float, labels: tuple | None = None) -> None:
        """Set the gauge to a specific value.

        Args:
            value: Value to set.
            labels: Tuple of label values.
        """
        labels = labels or ()
        with self._lock:
            self.values[labels] = value

    def inc(self, labels: tuple | None = None, value: float = 1.0) -> None:
        """Increment the gauge.

        Args:
            labels: Tuple of label values.
            value: Amount to increment by.
        """
        labels = labels or ()
        with self._lock:
            self.values[labels] += value

    def dec(self, labels: tuple | None = None, value: float = 1.0) -> None:
        """Decrement the gauge.

        Args:
            labels: Tuple of label values.
            value: Amount to decrement by.
        """
        labels = labels or ()
        with self._lock:
            self.values[labels] -= value

    def get(self, labels: tuple | None = None) -> float:
        """Get the current gauge value.

        Args:
            labels: Tuple of label values.

        Returns:
            Current gauge value.
        """
        labels = labels or ()
        with self._lock:
            return self.values[labels]


@dataclass
class HistogramMetric:
    """A histogram metric for distributions."""

    name: str
    help_text: str
    labels: list[str] = field(default_factory=list)
    buckets: list[float] = field(
        default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    bucket_counts: dict[tuple, list[int]] = field(default_factory=dict)
    sum_values: dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    count_values: dict[tuple, int] = field(default_factory=lambda: defaultdict(int))
    _lock: Lock = field(default_factory=Lock)

    def observe(self, value: float, labels: tuple | None = None) -> None:
        """Record an observation.

        Args:
            value: Value to observe (e.g., request duration).
            labels: Tuple of label values.
        """
        labels = labels or ()
        with self._lock:
            # Initialize bucket counts if needed
            if labels not in self.bucket_counts:
                self.bucket_counts[labels] = [0] * len(self.buckets)

            # Update bucket counts
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self.bucket_counts[labels][i] += 1

            # Update sum and count
            self.sum_values[labels] += value
            self.count_values[labels] += 1

    def get_buckets(self, labels: tuple | None = None) -> list[tuple[float, int]]:
        """Get bucket counts.

        Args:
            labels: Tuple of label values.

        Returns:
            List of (bucket_boundary, count) tuples.
        """
        labels = labels or ()
        with self._lock:
            counts = self.bucket_counts.get(labels, [0] * len(self.buckets))
            # Calculate cumulative counts
            cumulative = []
            running_total = 0
            for i, count in enumerate(counts):
                running_total += count
                cumulative.append((self.buckets[i], running_total))
            return cumulative

    def get_sum(self, labels: tuple | None = None) -> float:
        """Get sum of all observations.

        Args:
            labels: Tuple of label values.

        Returns:
            Sum of observed values.
        """
        labels = labels or ()
        with self._lock:
            return self.sum_values[labels]

    def get_count(self, labels: tuple | None = None) -> int:
        """Get count of all observations.

        Args:
            labels: Tuple of label values.

        Returns:
            Count of observations.
        """
        labels = labels or ()
        with self._lock:
            return self.count_values[labels]


# =============================================================================
# Metrics Registry
# =============================================================================


class MetricsRegistry:
    """Central registry for all application metrics."""

    def __init__(self) -> None:
        """Initialize the metrics registry."""
        self._lock = Lock()
        self._start_time = time.time()

        # Request metrics
        self.http_requests_total = CounterMetric(
            name="http_requests_total",
            help_text="Total number of HTTP requests",
            labels=["method", "endpoint", "status"],
        )

        self.http_request_duration_seconds = HistogramMetric(
            name="http_request_duration_seconds",
            help_text="HTTP request duration in seconds",
            labels=["method", "endpoint"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        self.http_requests_in_flight = GaugeMetric(
            name="http_requests_in_flight",
            help_text="Number of HTTP requests currently being processed",
            labels=[],
        )

        self.http_request_errors_total = CounterMetric(
            name="http_request_errors_total",
            help_text="Total number of HTTP request errors",
            labels=["method", "endpoint", "error_type"],
        )

        # Connection metrics
        self.active_connections = GaugeMetric(
            name="active_connections",
            help_text="Number of active connections",
            labels=["type"],
        )

        # Application metrics
        self.app_uptime_seconds = GaugeMetric(
            name="app_uptime_seconds",
            help_text="Application uptime in seconds",
            labels=[],
        )

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record metrics for a completed request.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: Request endpoint/path.
            status_code: HTTP response status code.
            duration_seconds: Request duration in seconds.
        """
        # Normalize endpoint for metrics (remove IDs, etc.)
        normalized_endpoint = self._normalize_endpoint(endpoint)

        # Increment request counter
        self.http_requests_total.inc(
            labels=(method.upper(), normalized_endpoint, str(status_code))
        )

        # Record duration
        self.http_request_duration_seconds.observe(
            duration_seconds, labels=(method.upper(), normalized_endpoint)
        )

        # Record errors (4xx and 5xx)
        if status_code >= 400:
            error_type = "client_error" if status_code < 500 else "server_error"
            self.http_request_errors_total.inc(
                labels=(method.upper(), normalized_endpoint, error_type)
            )

    def request_started(self) -> None:
        """Record that a request has started (for in-flight tracking)."""
        self.http_requests_in_flight.inc()

    def request_finished(self) -> None:
        """Record that a request has finished (for in-flight tracking)."""
        self.http_requests_in_flight.dec()

    def _normalize_endpoint(self, endpoint: str) -> str:
        """Normalize an endpoint path for metrics grouping.

        Replaces dynamic path segments (UUIDs, IDs) with placeholders.

        Args:
            endpoint: Raw endpoint path.

        Returns:
            Normalized endpoint path.
        """
        import re

        # Replace UUIDs
        endpoint = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            endpoint,
            flags=re.IGNORECASE,
        )

        # Replace numeric IDs
        endpoint = re.sub(r"/\d+(?=/|$)", "/{id}", endpoint)

        # Remove query strings
        endpoint = endpoint.split("?")[0]

        return endpoint

    def format_prometheus(self) -> str:
        """Format all metrics in Prometheus exposition format.

        Returns:
            String in Prometheus text format.
        """
        lines = []

        # Update uptime
        self.app_uptime_seconds.set(time.time() - self._start_time)

        # App info
        lines.append("# HELP app_info Application information")
        lines.append("# TYPE app_info gauge")
        lines.append('app_info{version="1.0.0",service="clinical-ontology-normalizer"} 1')
        lines.append("")

        # Format each metric type
        lines.extend(self._format_counter(self.http_requests_total))
        lines.extend(self._format_counter(self.http_request_errors_total))
        lines.extend(self._format_histogram(self.http_request_duration_seconds))
        lines.extend(self._format_gauge(self.http_requests_in_flight))
        lines.extend(self._format_gauge(self.active_connections))
        lines.extend(self._format_gauge(self.app_uptime_seconds))

        return "\n".join(lines)

    def _format_counter(self, metric: CounterMetric) -> list[str]:
        """Format a counter metric for Prometheus.

        Args:
            metric: Counter metric to format.

        Returns:
            List of formatted lines.
        """
        lines = [
            f"# HELP {metric.name} {metric.help_text}",
            f"# TYPE {metric.name} counter",
        ]

        with metric._lock:
            for labels, value in metric.values.items():
                if labels:
                    label_str = ",".join(
                        f'{metric.labels[i]}="{labels[i]}"'
                        for i in range(len(labels))
                    )
                    lines.append(f"{metric.name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{metric.name} {value}")

        lines.append("")
        return lines

    def _format_gauge(self, metric: GaugeMetric) -> list[str]:
        """Format a gauge metric for Prometheus.

        Args:
            metric: Gauge metric to format.

        Returns:
            List of formatted lines.
        """
        lines = [
            f"# HELP {metric.name} {metric.help_text}",
            f"# TYPE {metric.name} gauge",
        ]

        with metric._lock:
            if not metric.values:
                # Output default value if no values recorded
                lines.append(f"{metric.name} 0")
            else:
                for labels, value in metric.values.items():
                    if labels:
                        label_str = ",".join(
                            f'{metric.labels[i]}="{labels[i]}"'
                            for i in range(len(labels))
                        )
                        lines.append(f"{metric.name}{{{label_str}}} {value}")
                    else:
                        lines.append(f"{metric.name} {value}")

        lines.append("")
        return lines

    def _format_histogram(self, metric: HistogramMetric) -> list[str]:
        """Format a histogram metric for Prometheus.

        Args:
            metric: Histogram metric to format.

        Returns:
            List of formatted lines.
        """
        lines = [
            f"# HELP {metric.name} {metric.help_text}",
            f"# TYPE {metric.name} histogram",
        ]

        with metric._lock:
            # Group by labels
            all_labels = set(metric.bucket_counts.keys()) | set(metric.sum_values.keys())

            for labels in all_labels:
                # Format label string (without 'le')
                if labels and metric.labels:
                    base_label_str = ",".join(
                        f'{metric.labels[i]}="{labels[i]}"'
                        for i in range(len(labels))
                    )
                else:
                    base_label_str = ""

                # Get cumulative bucket counts
                counts = metric.bucket_counts.get(labels, [0] * len(metric.buckets))
                running_total = 0

                for i, bucket in enumerate(metric.buckets):
                    running_total += counts[i]
                    if base_label_str:
                        lines.append(
                            f'{metric.name}_bucket{{{base_label_str},le="{bucket}"}} {running_total}'
                        )
                    else:
                        lines.append(f'{metric.name}_bucket{{le="{bucket}"}} {running_total}')

                # +Inf bucket
                total_count = metric.count_values.get(labels, 0)
                if base_label_str:
                    lines.append(
                        f'{metric.name}_bucket{{{base_label_str},le="+Inf"}} {total_count}'
                    )
                else:
                    lines.append(f'{metric.name}_bucket{{le="+Inf"}} {total_count}')

                # Sum
                sum_value = metric.sum_values.get(labels, 0.0)
                if base_label_str:
                    lines.append(f"{metric.name}_sum{{{base_label_str}}} {sum_value}")
                else:
                    lines.append(f"{metric.name}_sum {sum_value}")

                # Count
                if base_label_str:
                    lines.append(f"{metric.name}_count{{{base_label_str}}} {total_count}")
                else:
                    lines.append(f"{metric.name}_count {total_count}")

        lines.append("")
        return lines

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics for internal use.

        Returns:
            Dictionary with summary stats.
        """
        total_requests = sum(self.http_requests_total.values.values())
        total_errors = sum(self.http_request_errors_total.values.values())

        return {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "uptime_seconds": time.time() - self._start_time,
            "in_flight_requests": self.http_requests_in_flight.get(),
        }


# =============================================================================
# Global Registry Singleton
# =============================================================================

_metrics_registry: MetricsRegistry | None = None


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry singleton.

    Returns:
        The MetricsRegistry singleton instance.
    """
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


def reset_metrics_registry() -> None:
    """Reset the metrics registry (for testing)."""
    global _metrics_registry
    _metrics_registry = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_class=PlainTextResponse,
    summary="Prometheus metrics",
    description="Returns all application metrics in Prometheus exposition format.",
    responses={
        200: {
            "description": "Prometheus metrics",
            "content": {"text/plain": {"schema": {"type": "string"}}},
        }
    },
)
async def get_metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint.

    Returns all collected metrics in Prometheus text exposition format.
    This endpoint is designed to be scraped by Prometheus.

    Response time should be <10ms as this is called frequently.
    """
    registry = get_metrics_registry()
    content = registry.format_prometheus()

    return PlainTextResponse(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get(
    "/json",
    summary="Metrics summary (JSON)",
    description="Returns a JSON summary of key metrics for debugging.",
)
async def get_metrics_json() -> dict[str, Any]:
    """JSON metrics summary endpoint.

    Returns key metrics in JSON format for debugging and dashboards.
    Not intended for Prometheus scraping.
    """
    registry = get_metrics_registry()
    return registry.get_stats()
