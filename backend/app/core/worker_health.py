"""P1-022: Worker liveness checks based on process and queue health.

Monitors worker health using real signals (PID, task recency, queue connection)
instead of simple HTTP pings that can't detect stuck or zombie workers.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default: 5 minutes with no completed task = stuck worker
WORKER_STUCK_THRESHOLD_SECONDS: int = int(
    os.environ.get("WORKER_STUCK_THRESHOLD_SECONDS", "300")
)


@dataclass
class WorkerHealthResult:
    """Result of a worker health check."""

    alive: bool
    stuck: bool
    queue_connected: bool
    last_heartbeat: float | None
    pid: int | None = None
    memory_mb: float | None = None
    error: str | None = None

    @property
    def healthy(self) -> bool:
        """Worker is healthy if alive, not stuck, and queue is connected."""
        return self.alive and not self.stuck and self.queue_connected


class WorkerHealthCheck:
    """Monitor worker health using process-level and queue-level signals.

    Tracks heartbeats from task completions and checks Redis connectivity
    to determine if a worker is alive, stuck, or disconnected.
    """

    def __init__(self) -> None:
        self._started_at = time.monotonic()
        self._last_task_completed: float | None = None

    def record_task_completed(self) -> None:
        """Record that a task just completed (heartbeat)."""
        self._last_task_completed = time.monotonic()

    def record_heartbeat(self) -> None:
        """Alias for record_task_completed for generic heartbeat use."""
        self.record_task_completed()

    def check_process_alive(self) -> bool:
        """Check if the current worker process is alive via PID."""
        pid = os.getpid()
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def check_queue_connected(self) -> bool:
        """Check if Redis (queue backend) is reachable."""
        try:
            from app.core.redis import ping_redis
            return ping_redis()
        except Exception as e:
            logger.warning("Queue connection check failed: %s", e)
            return False

    def is_stuck(self) -> bool:
        """Check if the worker is stuck (no task completed within threshold).

        A worker that just started and hasn't completed any task yet is not
        considered stuck until the threshold elapses from startup.
        """
        reference_time = self._last_task_completed or self._started_at
        elapsed = time.monotonic() - reference_time
        return elapsed > WORKER_STUCK_THRESHOLD_SECONDS

    def get_memory_mb(self) -> float | None:
        """Get current process memory usage in MB (best-effort)."""
        try:
            import resource
            # maxrss is in KB on Linux, bytes on macOS
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            maxrss_kb = rusage.ru_maxrss
            # macOS reports bytes, Linux reports KB
            import sys
            if sys.platform == "darwin":
                return maxrss_kb / (1024 * 1024)
            return maxrss_kb / 1024
        except Exception:
            return None

    def check(self) -> WorkerHealthResult:
        """Run all health checks and return a combined result."""
        pid = os.getpid()
        alive = self.check_process_alive()
        queue_connected = self.check_queue_connected()
        stuck = self.is_stuck()
        memory_mb = self.get_memory_mb()

        last_heartbeat: float | None = None
        if self._last_task_completed is not None:
            last_heartbeat = self._last_task_completed

        result = WorkerHealthResult(
            alive=alive,
            stuck=stuck,
            queue_connected=queue_connected,
            last_heartbeat=last_heartbeat,
            pid=pid,
            memory_mb=memory_mb,
        )

        if not result.healthy:
            logger.warning(
                "Worker health check UNHEALTHY: alive=%s stuck=%s queue=%s pid=%s",
                alive,
                stuck,
                queue_connected,
                pid,
            )
        else:
            logger.debug("Worker health check OK: pid=%s", pid)

        return result


# Module-level singleton for use by worker processes
_worker_health: WorkerHealthCheck | None = None


def get_worker_health() -> WorkerHealthCheck:
    """Get or create the module-level WorkerHealthCheck singleton."""
    global _worker_health
    if _worker_health is None:
        _worker_health = WorkerHealthCheck()
    return _worker_health


def check_worker_health() -> WorkerHealthResult:
    """Convenience function: run worker health check and return result."""
    return get_worker_health().check()
