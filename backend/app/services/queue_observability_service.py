"""P3-008: Queue and worker observability dashboard service.

Provides richer queue and worker metrics for dashboards, including
queue depth, throughput rates, consumer counts, and worker status.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of rate samples to keep for rolling rate calculation
_MAX_RATE_SAMPLES = 120  # ~2 minutes at 1 sample/sec

# Health thresholds
_QUEUE_DEPTH_WARNING = 100
_QUEUE_DEPTH_CRITICAL = 500
_OLDEST_MESSAGE_WARNING_SECONDS = 300  # 5 minutes
_OLDEST_MESSAGE_CRITICAL_SECONDS = 900  # 15 minutes
_WORKER_FAILURE_RATE_WARNING = 0.05  # 5%
_WORKER_FAILURE_RATE_CRITICAL = 0.20  # 20%


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class HealthStatus(str, Enum):
    """Overall health assessment levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class WorkerStatus(str, Enum):
    """Worker lifecycle status."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    DRAINING = "draining"


@dataclass
class QueueMetrics:
    """Metrics for a single named queue."""

    queue_name: str
    depth: int = 0
    enqueue_rate_per_min: float = 0.0
    dequeue_rate_per_min: float = 0.0
    oldest_message_age_seconds: float = 0.0
    consumer_count: int = 0


@dataclass
class WorkerMetrics:
    """Metrics for a single worker process."""

    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    tasks_completed: int = 0
    tasks_failed: int = 0
    uptime_seconds: float = 0.0
    current_task: str | None = None


@dataclass
class QueueHealthSummary:
    """Overall health assessment across all queues and workers."""

    status: HealthStatus = HealthStatus.UNKNOWN
    total_queues: int = 0
    total_workers: int = 0
    total_depth: int = 0
    total_enqueue_rate_per_min: float = 0.0
    total_dequeue_rate_per_min: float = 0.0
    workers_busy: int = 0
    workers_idle: int = 0
    workers_offline: int = 0
    issues: list[str] = field(default_factory=list)


@dataclass
class QueueDashboard:
    """Complete dashboard payload with all queue and worker metrics."""

    queues: list[QueueMetrics] = field(default_factory=list)
    workers: list[WorkerMetrics] = field(default_factory=list)
    health: QueueHealthSummary = field(default_factory=QueueHealthSummary)
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Rate tracker (rolling window)
# ---------------------------------------------------------------------------


class _RateTracker:
    """Tracks event counts over a rolling time window for rate calculation."""

    def __init__(self, max_samples: int = _MAX_RATE_SAMPLES) -> None:
        self._samples: deque[tuple[float, int]] = deque(maxlen=max_samples)
        self._total: int = 0

    def record(self, count: int = 1) -> None:
        """Record events."""
        now = time.monotonic()
        self._samples.append((now, count))
        self._total += count

    def rate_per_minute(self) -> float:
        """Calculate events per minute over the sample window."""
        if len(self._samples) < 2:
            return 0.0
        oldest_ts = self._samples[0][0]
        newest_ts = self._samples[-1][0]
        window = newest_ts - oldest_ts
        if window <= 0:
            return 0.0
        total_in_window = sum(c for _, c in self._samples)
        return (total_in_window / window) * 60.0

    @property
    def total(self) -> int:
        return self._total


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class QueueObservabilityService:
    """Collects and exposes queue/worker observability metrics.

    This service maintains in-memory metrics that are updated by queue
    integrations (RQ, Celery, or custom). It provides a dashboard view
    and a health summary suitable for monitoring systems.
    """

    def __init__(self) -> None:
        # Queue state
        self._queue_depths: dict[str, int] = {}
        self._queue_consumers: dict[str, int] = {}
        self._queue_oldest_message: dict[str, float] = {}  # monotonic timestamp
        self._enqueue_rates: dict[str, _RateTracker] = {}
        self._dequeue_rates: dict[str, _RateTracker] = {}

        # Worker state
        self._workers: dict[str, WorkerMetrics] = {}
        self._worker_start_times: dict[str, float] = {}  # monotonic

    # -- Queue registration --------------------------------------------------

    def register_queue(self, queue_name: str) -> None:
        """Register a queue for monitoring."""
        if queue_name not in self._enqueue_rates:
            self._enqueue_rates[queue_name] = _RateTracker()
            self._dequeue_rates[queue_name] = _RateTracker()
            self._queue_depths[queue_name] = 0
            self._queue_consumers[queue_name] = 0
            self._queue_oldest_message[queue_name] = 0.0
            logger.info("Registered queue for observability: %s", queue_name)

    def update_queue_depth(self, queue_name: str, depth: int) -> None:
        """Update the current depth of a queue."""
        self.register_queue(queue_name)
        self._queue_depths[queue_name] = depth

    def update_consumer_count(self, queue_name: str, count: int) -> None:
        """Update the number of consumers for a queue."""
        self.register_queue(queue_name)
        self._queue_consumers[queue_name] = count

    def record_enqueue(self, queue_name: str, count: int = 1) -> None:
        """Record that messages were enqueued."""
        self.register_queue(queue_name)
        self._enqueue_rates[queue_name].record(count)
        # Update oldest message if queue was empty
        if self._queue_oldest_message.get(queue_name, 0.0) == 0.0:
            self._queue_oldest_message[queue_name] = time.monotonic()

    def record_dequeue(self, queue_name: str, count: int = 1) -> None:
        """Record that messages were dequeued."""
        self.register_queue(queue_name)
        self._dequeue_rates[queue_name].record(count)
        # Reset oldest message age if queue becomes empty
        depth = self._queue_depths.get(queue_name, 0)
        if depth <= count:
            self._queue_oldest_message[queue_name] = 0.0

    # -- Worker registration -------------------------------------------------

    def register_worker(self, worker_id: str) -> None:
        """Register a worker for monitoring."""
        if worker_id not in self._workers:
            self._workers[worker_id] = WorkerMetrics(worker_id=worker_id)
            self._worker_start_times[worker_id] = time.monotonic()
            logger.info("Registered worker for observability: %s", worker_id)

    def update_worker_status(
        self,
        worker_id: str,
        status: WorkerStatus,
        current_task: str | None = None,
    ) -> None:
        """Update worker status and optional current task."""
        self.register_worker(worker_id)
        self._workers[worker_id].status = status
        self._workers[worker_id].current_task = current_task

    def record_worker_task_complete(self, worker_id: str) -> None:
        """Record a successful task completion for a worker."""
        self.register_worker(worker_id)
        self._workers[worker_id].tasks_completed += 1

    def record_worker_task_failed(self, worker_id: str) -> None:
        """Record a task failure for a worker."""
        self.register_worker(worker_id)
        self._workers[worker_id].tasks_failed += 1

    def remove_worker(self, worker_id: str) -> None:
        """Remove a worker from monitoring."""
        self._workers.pop(worker_id, None)
        self._worker_start_times.pop(worker_id, None)

    # -- Dashboard -----------------------------------------------------------

    def get_queue_metrics(self) -> list[QueueMetrics]:
        """Get metrics for all registered queues."""
        now = time.monotonic()
        metrics: list[QueueMetrics] = []
        for name in sorted(self._enqueue_rates):
            oldest_ts = self._queue_oldest_message.get(name, 0.0)
            age = (now - oldest_ts) if oldest_ts > 0 else 0.0
            metrics.append(
                QueueMetrics(
                    queue_name=name,
                    depth=self._queue_depths.get(name, 0),
                    enqueue_rate_per_min=round(
                        self._enqueue_rates[name].rate_per_minute(), 2
                    ),
                    dequeue_rate_per_min=round(
                        self._dequeue_rates[name].rate_per_minute(), 2
                    ),
                    oldest_message_age_seconds=round(age, 2),
                    consumer_count=self._queue_consumers.get(name, 0),
                )
            )
        return metrics

    def get_worker_metrics(self) -> list[WorkerMetrics]:
        """Get metrics for all registered workers."""
        now = time.monotonic()
        metrics: list[WorkerMetrics] = []
        for wid in sorted(self._workers):
            w = self._workers[wid]
            start = self._worker_start_times.get(wid, now)
            w.uptime_seconds = round(now - start, 2)
            metrics.append(w)
        return metrics

    def get_queue_health_summary(self) -> QueueHealthSummary:
        """Compute an overall health assessment."""
        queue_metrics = self.get_queue_metrics()
        worker_metrics = self.get_worker_metrics()

        issues: list[str] = []
        status = HealthStatus.HEALTHY

        total_depth = 0
        total_enq = 0.0
        total_deq = 0.0

        for qm in queue_metrics:
            total_depth += qm.depth
            total_enq += qm.enqueue_rate_per_min
            total_deq += qm.dequeue_rate_per_min

            if qm.depth >= _QUEUE_DEPTH_CRITICAL:
                issues.append(f"Queue '{qm.queue_name}' depth {qm.depth} >= critical threshold {_QUEUE_DEPTH_CRITICAL}")
                status = HealthStatus.CRITICAL
            elif qm.depth >= _QUEUE_DEPTH_WARNING:
                issues.append(f"Queue '{qm.queue_name}' depth {qm.depth} >= warning threshold {_QUEUE_DEPTH_WARNING}")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING

            if qm.oldest_message_age_seconds >= _OLDEST_MESSAGE_CRITICAL_SECONDS:
                issues.append(
                    f"Queue '{qm.queue_name}' oldest message age "
                    f"{qm.oldest_message_age_seconds:.0f}s >= critical threshold "
                    f"{_OLDEST_MESSAGE_CRITICAL_SECONDS}s"
                )
                status = HealthStatus.CRITICAL
            elif qm.oldest_message_age_seconds >= _OLDEST_MESSAGE_WARNING_SECONDS:
                issues.append(
                    f"Queue '{qm.queue_name}' oldest message age "
                    f"{qm.oldest_message_age_seconds:.0f}s >= warning threshold "
                    f"{_OLDEST_MESSAGE_WARNING_SECONDS}s"
                )
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING

            if qm.consumer_count == 0 and qm.depth > 0:
                issues.append(f"Queue '{qm.queue_name}' has {qm.depth} messages but 0 consumers")
                status = HealthStatus.CRITICAL

        busy = sum(1 for w in worker_metrics if w.status == WorkerStatus.BUSY)
        idle = sum(1 for w in worker_metrics if w.status == WorkerStatus.IDLE)
        offline = sum(1 for w in worker_metrics if w.status == WorkerStatus.OFFLINE)

        # Check worker failure rates
        for w in worker_metrics:
            total_tasks = w.tasks_completed + w.tasks_failed
            if total_tasks > 0:
                fail_rate = w.tasks_failed / total_tasks
                if fail_rate >= _WORKER_FAILURE_RATE_CRITICAL:
                    issues.append(
                        f"Worker '{w.worker_id}' failure rate "
                        f"{fail_rate:.0%} >= critical threshold "
                        f"{_WORKER_FAILURE_RATE_CRITICAL:.0%}"
                    )
                    status = HealthStatus.CRITICAL
                elif fail_rate >= _WORKER_FAILURE_RATE_WARNING:
                    issues.append(
                        f"Worker '{w.worker_id}' failure rate "
                        f"{fail_rate:.0%} >= warning threshold "
                        f"{_WORKER_FAILURE_RATE_WARNING:.0%}"
                    )
                    if status == HealthStatus.HEALTHY:
                        status = HealthStatus.WARNING

        if not queue_metrics and not worker_metrics:
            status = HealthStatus.UNKNOWN
            issues.append("No queues or workers registered")

        return QueueHealthSummary(
            status=status,
            total_queues=len(queue_metrics),
            total_workers=len(worker_metrics),
            total_depth=total_depth,
            total_enqueue_rate_per_min=round(total_enq, 2),
            total_dequeue_rate_per_min=round(total_deq, 2),
            workers_busy=busy,
            workers_idle=idle,
            workers_offline=offline,
            issues=issues,
        )

    def get_queue_dashboard(self) -> QueueDashboard:
        """Build the full dashboard payload with metrics and health summary."""
        return QueueDashboard(
            queues=self.get_queue_metrics(),
            workers=self.get_worker_metrics(),
            health=self.get_queue_health_summary(),
            timestamp=time.time(),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_service: QueueObservabilityService | None = None


def get_queue_observability_service() -> QueueObservabilityService:
    """Get or create the module-level observability service singleton."""
    global _default_service
    if _default_service is None:
        _default_service = QueueObservabilityService()
    return _default_service


def reset_queue_observability_service() -> None:
    """Reset the singleton (for testing)."""
    global _default_service
    _default_service = None
