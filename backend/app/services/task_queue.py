"""Background task queue for long-running KG operations.

This module provides an async task queue for operations like:
- Large graph traversals
- Batch concept lookups
- UMLS updates
- Graph exports
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

# VP-Resilience-3: Exponential backoff configuration
DEFAULT_RETRY_BASE_DELAY = 1.0  # Base delay in seconds
DEFAULT_RETRY_MAX_DELAY = 60.0  # Maximum delay
DEFAULT_RETRY_JITTER = 0.25  # Random jitter factor (0.25 = ±25%)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    max_delay: float = DEFAULT_RETRY_MAX_DELAY,
    jitter: float = DEFAULT_RETRY_JITTER,
) -> float:
    """Calculate exponential backoff delay with jitter.

    VP-Resilience-3: Implements exponential backoff: delay = base * 2^attempt

    Args:
        attempt: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap
        jitter: Random jitter factor (0.25 = ±25%)

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential: 1s, 2s, 4s, 8s, 16s, 32s...
    delay = min(base_delay * (2 ** attempt), max_delay)

    # Add jitter to prevent thundering herd
    if jitter > 0:
        jitter_amount = delay * jitter
        delay = delay + random.uniform(-jitter_amount, jitter_amount)

    return max(0.0, delay)

T = TypeVar("T")


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """Task priority levels (lower = higher priority)."""

    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100
    BACKGROUND = 200


@dataclass
class TaskProgress:
    """Progress tracking for a task."""

    current: int = 0
    total: int = 0
    message: str = ""
    percentage: float = 0.0

    def update(self, current: int, total: int = 0, message: str = "") -> None:
        """Update progress."""
        self.current = current
        if total > 0:
            self.total = total
        if message:
            self.message = message
        if self.total > 0:
            self.percentage = min(100.0, (self.current / self.total) * 100)


@dataclass
class TaskResult:
    """Result of a task execution."""

    success: bool
    value: Any = None
    error: str | None = None
    error_type: str | None = None
    traceback: str | None = None


@dataclass
class Task:
    """A task in the queue.

    VP-Resilience-3: Enhanced with exponential backoff retry scheduling.
    """

    id: str
    name: str
    func: Callable[..., Coroutine[Any, Any, Any]]
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: TaskProgress = field(default_factory=TaskProgress)
    result: TaskResult | None = None
    timeout_seconds: float = 300.0  # 5 minute default
    retries: int = 0
    max_retries: int = 3
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    metadata: dict[str, Any] = field(default_factory=dict)
    # VP-Resilience-3: Scheduled execution time for delayed retries
    scheduled_at: datetime | None = None
    last_error: str | None = None

    def __lt__(self, other: "Task") -> bool:
        """Compare tasks by priority for queue ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at

    @property
    def duration_ms(self) -> float | None:
        """Get task duration in milliseconds."""
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds() * 1000

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.name,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "progress": {
                "current": self.progress.current,
                "total": self.progress.total,
                "message": self.progress.message,
                "percentage": round(self.progress.percentage, 2),
            },
            "result": (
                {
                    "success": self.result.success,
                    "error": self.result.error,
                    "error_type": self.result.error_type,
                }
                if self.result
                else None
            ),
            "retries": self.retries,
            "metadata": self.metadata,
        }


class TaskQueue:
    """Async task queue with priority support."""

    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 1000,
    ) -> None:
        """Initialize the task queue.

        Args:
            max_workers: Maximum concurrent workers
            max_queue_size: Maximum tasks in queue
        """
        self._max_workers = max_workers
        self._max_queue_size = max_queue_size
        self._queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue(max_queue_size)
        self._tasks: dict[str, Task] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_cancelled": 0,
            "tasks_retried": 0,  # VP-Resilience-3: Track retry count
            "total_processing_ms": 0.0,
        }

    @property
    def is_running(self) -> bool:
        """Check if queue is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    @property
    def active_workers(self) -> int:
        """Get number of active workers."""
        return sum(1 for w in self._workers if not w.done())

    async def start(self) -> None:
        """Start the task queue workers."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start workers
        for i in range(self._max_workers):
            worker = asyncio.create_task(
                self._worker(f"worker-{i}"),
                name=f"task-queue-worker-{i}",
            )
            self._workers.append(worker)

        logger.info(
            f"Task queue started with {self._max_workers} workers"
        )

    async def stop(self, wait: bool = True, timeout: float = 30.0) -> None:
        """Stop the task queue.

        Args:
            wait: Whether to wait for pending tasks
            timeout: Maximum time to wait for shutdown
        """
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        if wait:
            # Wait for workers to finish
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Task queue shutdown timed out")
                for worker in self._workers:
                    worker.cancel()

        self._workers.clear()
        logger.info("Task queue stopped")

    async def submit(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: float = 300.0,
        max_retries: int = 3,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Submit a task to the queue.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            name: Task name for identification
            priority: Task priority level
            timeout_seconds: Task timeout
            max_retries: Maximum retry attempts
            metadata: Additional task metadata
            **kwargs: Keyword arguments for function

        Returns:
            Task ID

        Raises:
            RuntimeError: If queue is not running
            asyncio.QueueFull: If queue is full
        """
        if not self._running:
            raise RuntimeError("Task queue is not running")

        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            metadata=metadata or {},
        )

        async with self._lock:
            self._tasks[task_id] = task
            self._stats["tasks_submitted"] += 1

        await self._queue.put(task)
        logger.debug(f"Task {task_id} ({task.name}) submitted")

        return task_id

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status as dictionary."""
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if task was cancelled
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False

        if task.is_terminal:
            return False

        task.cancel_event.set()
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        self._stats["tasks_cancelled"] += 1

        logger.info(f"Task {task_id} cancelled")
        return True

    async def wait_for_task(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> Task | None:
        """Wait for a task to complete.

        Args:
            task_id: Task ID to wait for
            timeout: Maximum wait time

        Returns:
            Completed task or None if not found/timeout
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None

        if task.is_terminal:
            return task

        # Poll for completion
        start = datetime.now(timezone.utc)
        while not task.is_terminal:
            if timeout:
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                if elapsed >= timeout:
                    return None
            await asyncio.sleep(0.1)

        return task

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            **self._stats,
            "queue_size": self.queue_size,
            "active_workers": self.active_workers,
            "max_workers": self._max_workers,
            "is_running": self._running,
        }

    async def get_pending_tasks(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get pending tasks."""
        tasks = [
            t.to_dict()
            for t in self._tasks.values()
            if t.status == TaskStatus.PENDING
        ]
        return sorted(tasks, key=lambda t: t["created_at"])[:limit]

    async def get_running_tasks(self) -> list[dict[str, Any]]:
        """Get currently running tasks."""
        return [
            t.to_dict()
            for t in self._tasks.values()
            if t.status == TaskStatus.RUNNING
        ]

    async def cleanup_old_tasks(
        self,
        max_age_hours: int = 24,
    ) -> int:
        """Remove old completed/failed tasks.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of tasks removed
        """
        now = datetime.now(timezone.utc)
        to_remove = []

        async with self._lock:
            for task_id, task in self._tasks.items():
                if task.is_terminal and task.completed_at:
                    age_hours = (now - task.completed_at).total_seconds() / 3600
                    if age_hours >= max_age_hours:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")

        return len(to_remove)

    async def _worker(self, worker_id: str) -> None:
        """Worker coroutine that processes tasks.

        VP-Resilience-3: Handles scheduled tasks with exponential backoff.
        """
        logger.debug(f"{worker_id} started")

        while self._running or not self._queue.empty():
            try:
                # Wait for a task with timeout
                try:
                    task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    if self._shutdown_event.is_set():
                        break
                    continue

                # Skip cancelled tasks
                if task.cancel_event.is_set():
                    self._queue.task_done()
                    continue

                # VP-Resilience-3: Check if task is scheduled for future execution
                if task.scheduled_at:
                    now = datetime.now(timezone.utc)
                    if task.scheduled_at > now:
                        # Re-queue and wait for the scheduled time
                        wait_seconds = (task.scheduled_at - now).total_seconds()
                        if wait_seconds > 0.1:
                            # Re-queue and let another worker handle it later
                            await self._queue.put(task)
                            self._queue.task_done()
                            # Short sleep to avoid tight loop
                            await asyncio.sleep(min(wait_seconds, 1.0))
                            continue

                await self._execute_task(task, worker_id)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"{worker_id} unexpected error: {e}")

        logger.debug(f"{worker_id} stopped")

    async def _execute_task(self, task: Task, worker_id: str) -> None:
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        logger.info(f"{worker_id} executing task {task.id} ({task.name})")

        try:
            # Run with timeout
            result = await asyncio.wait_for(
                task.func(*task.args, **task.kwargs),
                timeout=task.timeout_seconds,
            )

            task.result = TaskResult(success=True, value=result)
            task.status = TaskStatus.COMPLETED
            self._stats["tasks_completed"] += 1

            logger.info(
                f"Task {task.id} completed in {task.duration_ms:.2f}ms"
            )

        except asyncio.TimeoutError:
            task.result = TaskResult(
                success=False,
                error="Task timed out",
                error_type="TimeoutError",
            )
            task.status = TaskStatus.TIMEOUT
            self._stats["tasks_failed"] += 1

            logger.warning(
                f"Task {task.id} timed out after {task.timeout_seconds}s"
            )

        except asyncio.CancelledError:
            task.result = TaskResult(
                success=False,
                error="Task cancelled",
                error_type="CancelledError",
            )
            task.status = TaskStatus.CANCELLED
            self._stats["tasks_cancelled"] += 1

            logger.info(f"Task {task.id} cancelled")

        except Exception as e:
            import traceback

            error_msg = str(e)
            task.result = TaskResult(
                success=False,
                error=error_msg,
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            task.last_error = error_msg

            # VP-Resilience-3: Check if we should retry with exponential backoff
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.PENDING

                # Calculate backoff delay
                delay = calculate_backoff_delay(
                    attempt=task.retries - 1,  # 0-indexed
                    base_delay=DEFAULT_RETRY_BASE_DELAY,
                    max_delay=DEFAULT_RETRY_MAX_DELAY,
                )
                task.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

                await self._queue.put(task)
                self._stats["tasks_retried"] += 1
                logger.warning(
                    f"Task {task.id} failed, scheduling retry {task.retries}/{task.max_retries} "
                    f"in {delay:.1f}s (exponential backoff)"
                )
            else:
                task.status = TaskStatus.FAILED
                self._stats["tasks_failed"] += 1
                logger.error(
                    f"Task {task.id} permanently failed after {task.max_retries} retries: {e}"
                )

        finally:
            task.completed_at = datetime.now(timezone.utc)
            if task.duration_ms:
                self._stats["total_processing_ms"] += task.duration_ms


# Singleton instance
_task_queue: TaskQueue | None = None


def get_task_queue(
    max_workers: int = 4,
    max_queue_size: int = 1000,
) -> TaskQueue:
    """Get the singleton task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(
            max_workers=max_workers,
            max_queue_size=max_queue_size,
        )
    return _task_queue


async def init_task_queue(
    max_workers: int = 4,
    max_queue_size: int = 1000,
) -> TaskQueue:
    """Initialize and start the task queue."""
    queue = get_task_queue(max_workers, max_queue_size)
    await queue.start()
    return queue


async def shutdown_task_queue(wait: bool = True) -> None:
    """Shutdown the task queue."""
    global _task_queue
    if _task_queue:
        await _task_queue.stop(wait=wait)
        _task_queue = None
