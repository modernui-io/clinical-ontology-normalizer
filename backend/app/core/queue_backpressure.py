"""P1-023: Queue depth SLOs and intake throttling/backpressure policy.

Provides queue depth monitoring with SLO-based classification and
backpressure decisions so callers can reject or delay work before
the queue becomes dangerously deep.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Configurable thresholds via environment variables
QUEUE_WARNING_DEPTH: int = int(os.environ.get("QUEUE_WARNING_DEPTH", "100"))
QUEUE_CRITICAL_DEPTH: int = int(os.environ.get("QUEUE_CRITICAL_DEPTH", "500"))
QUEUE_MAX_DEPTH: int = int(os.environ.get("QUEUE_MAX_DEPTH", "1000"))


class QueueStatus(str, Enum):
    """SLO-based queue depth classification."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    REJECTED = "rejected"


@dataclass(frozen=True)
class QueueDepthResult:
    """Result of a queue depth check."""

    queue_name: str
    depth: int
    status: QueueStatus
    max_depth: int

    @property
    def ok(self) -> bool:
        return self.status in (QueueStatus.NORMAL, QueueStatus.WARNING)


@dataclass(frozen=True)
class ThrottleDecision:
    """Whether to throttle or reject new work for a queue."""

    throttle: bool
    reject: bool
    reason: str
    queue_name: str
    depth: int
    status: QueueStatus


class QueueSLO:
    """Queue depth SLO policy with configurable thresholds.

    Classifies queue depth into SLO tiers and provides throttle/reject decisions.
    """

    def __init__(
        self,
        warning_depth: int = QUEUE_WARNING_DEPTH,
        critical_depth: int = QUEUE_CRITICAL_DEPTH,
        max_depth: int = QUEUE_MAX_DEPTH,
    ) -> None:
        if not (0 < warning_depth < critical_depth < max_depth):
            raise ValueError(
                f"Thresholds must be 0 < warning ({warning_depth}) "
                f"< critical ({critical_depth}) < max ({max_depth})"
            )
        self.warning_depth = warning_depth
        self.critical_depth = critical_depth
        self.max_depth = max_depth

    def classify(self, depth: int) -> QueueStatus:
        """Classify queue depth into an SLO tier."""
        if depth >= self.max_depth:
            return QueueStatus.REJECTED
        if depth >= self.critical_depth:
            return QueueStatus.CRITICAL
        if depth >= self.warning_depth:
            return QueueStatus.WARNING
        return QueueStatus.NORMAL


# Module-level default SLO instance
_default_slo = QueueSLO()


def _get_queue_length(queue_name: str) -> int:
    """Get current queue length from Redis/RQ.

    Returns 0 if queue or Redis is unavailable.
    """
    try:
        from app.core.queue import get_queue
        q = get_queue(queue_name)
        return len(q)
    except Exception as e:
        logger.warning("Failed to read queue depth for %s: %s", queue_name, e)
        return 0


def check_queue_depth(
    queue_name: str,
    slo: QueueSLO | None = None,
) -> QueueDepthResult:
    """Check current queue depth and classify against SLO thresholds.

    Args:
        queue_name: Name of the RQ queue to check.
        slo: Optional custom SLO instance (uses module default if None).

    Returns:
        QueueDepthResult with depth, status, and max_depth.
    """
    slo = slo or _default_slo
    depth = _get_queue_length(queue_name)
    status = slo.classify(depth)

    if status in (QueueStatus.CRITICAL, QueueStatus.REJECTED):
        logger.warning(
            "Queue %s depth=%d status=%s (max=%d)",
            queue_name,
            depth,
            status.value,
            slo.max_depth,
        )

    return QueueDepthResult(
        queue_name=queue_name,
        depth=depth,
        status=status,
        max_depth=slo.max_depth,
    )


def should_throttle(
    queue_name: str,
    slo: QueueSLO | None = None,
) -> ThrottleDecision:
    """Decide whether to throttle or reject new work for a queue.

    - NORMAL: no throttle, no reject
    - WARNING: throttle (caller should delay), no reject
    - CRITICAL: throttle, no reject (but caller should shed low-priority work)
    - REJECTED: throttle + reject (queue full, refuse new intake)

    Args:
        queue_name: Name of the RQ queue.
        slo: Optional custom SLO instance.

    Returns:
        ThrottleDecision with throttle/reject booleans and reason.
    """
    result = check_queue_depth(queue_name, slo)
    slo = slo or _default_slo

    if result.status == QueueStatus.NORMAL:
        return ThrottleDecision(
            throttle=False,
            reject=False,
            reason="Queue depth normal",
            queue_name=queue_name,
            depth=result.depth,
            status=result.status,
        )
    elif result.status == QueueStatus.WARNING:
        return ThrottleDecision(
            throttle=True,
            reject=False,
            reason=f"Queue depth {result.depth} exceeds warning threshold {slo.warning_depth}",
            queue_name=queue_name,
            depth=result.depth,
            status=result.status,
        )
    elif result.status == QueueStatus.CRITICAL:
        return ThrottleDecision(
            throttle=True,
            reject=False,
            reason=f"Queue depth {result.depth} exceeds critical threshold {slo.critical_depth}",
            queue_name=queue_name,
            depth=result.depth,
            status=result.status,
        )
    else:  # REJECTED
        return ThrottleDecision(
            throttle=True,
            reject=True,
            reason=f"Queue depth {result.depth} exceeds max depth {slo.max_depth}; rejecting intake",
            queue_name=queue_name,
            depth=result.depth,
            status=result.status,
        )


def enqueue_with_backpressure(
    func: object,
    *args: object,
    queue_name: str = "default",
    job_timeout: int = 600,
    **kwargs: object,
) -> object:
    """Enqueue a job only if the queue is not at max depth.

    Wraps app.core.queue.enqueue_job with a backpressure gate.

    Args:
        func: The function to enqueue.
        *args: Positional arguments for the function.
        queue_name: RQ queue name.
        job_timeout: Job timeout in seconds.
        **kwargs: Keyword arguments for the function.

    Returns:
        RQ Job instance.

    Raises:
        QueueBackpressureError: If queue is at or above max depth.
    """
    decision = should_throttle(queue_name)
    if decision.reject:
        raise QueueBackpressureError(decision.reason, queue_name, decision.depth)

    from app.core.queue import enqueue_job
    return enqueue_job(func, *args, queue_name=queue_name, job_timeout=job_timeout, **kwargs)


class QueueBackpressureError(Exception):
    """Raised when a queue rejects new work due to backpressure."""

    def __init__(self, reason: str, queue_name: str, depth: int) -> None:
        self.reason = reason
        self.queue_name = queue_name
        self.depth = depth
        super().__init__(reason)
