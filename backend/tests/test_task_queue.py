"""Tests for background task queue."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.services.task_queue import (
    Task,
    TaskPriority,
    TaskProgress,
    TaskQueue,
    TaskResult,
    TaskStatus,
    get_task_queue,
    init_task_queue,
    shutdown_task_queue,
)


# =============================================================================
# Task Status Tests
# =============================================================================


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.TIMEOUT.value == "timeout"


class TestTaskPriority:
    """Test TaskPriority enum."""

    def test_priority_ordering(self) -> None:
        """Test priority values are ordered correctly."""
        assert TaskPriority.CRITICAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.LOW.value
        assert TaskPriority.LOW.value < TaskPriority.BACKGROUND.value


# =============================================================================
# Task Progress Tests
# =============================================================================


class TestTaskProgress:
    """Test TaskProgress dataclass."""

    def test_initial_progress(self) -> None:
        """Test initial progress values."""
        progress = TaskProgress()
        assert progress.current == 0
        assert progress.total == 0
        assert progress.percentage == 0.0

    def test_update_progress(self) -> None:
        """Test progress update."""
        progress = TaskProgress()
        progress.update(50, total=100, message="Processing")

        assert progress.current == 50
        assert progress.total == 100
        assert progress.percentage == 50.0
        assert progress.message == "Processing"

    def test_percentage_capped(self) -> None:
        """Test percentage is capped at 100."""
        progress = TaskProgress()
        progress.update(150, total=100)

        assert progress.percentage == 100.0


# =============================================================================
# Task Result Tests
# =============================================================================


class TestTaskResult:
    """Test TaskResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = TaskResult(success=True, value={"data": "test"})

        assert result.success is True
        assert result.value == {"data": "test"}
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed result."""
        result = TaskResult(
            success=False,
            error="Something went wrong",
            error_type="ValueError",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.error_type == "ValueError"


# =============================================================================
# Task Tests
# =============================================================================


class TestTask:
    """Test Task dataclass."""

    def test_task_creation(self) -> None:
        """Test task creation."""

        async def dummy_task():
            return "result"

        task = Task(
            id="task-1",
            name="test-task",
            func=dummy_task,
        )

        assert task.id == "task-1"
        assert task.name == "test-task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL

    def test_task_priority_comparison(self) -> None:
        """Test task priority comparison."""

        async def dummy():
            pass

        high = Task(id="1", name="high", func=dummy, priority=TaskPriority.HIGH)
        low = Task(id="2", name="low", func=dummy, priority=TaskPriority.LOW)

        assert high < low

    def test_task_is_terminal(self) -> None:
        """Test terminal state detection."""

        async def dummy():
            pass

        task = Task(id="1", name="test", func=dummy)

        assert not task.is_terminal

        task.status = TaskStatus.COMPLETED
        assert task.is_terminal

        task.status = TaskStatus.FAILED
        assert task.is_terminal

    def test_task_duration_ms(self) -> None:
        """Test duration calculation."""

        async def dummy():
            pass

        task = Task(id="1", name="test", func=dummy)
        assert task.duration_ms is None

        task.started_at = datetime.now(timezone.utc)
        assert task.duration_ms is not None
        assert task.duration_ms >= 0

    def test_task_to_dict(self) -> None:
        """Test task serialization."""

        async def dummy():
            pass

        task = Task(id="1", name="test", func=dummy)
        data = task.to_dict()

        assert data["id"] == "1"
        assert data["name"] == "test"
        assert data["status"] == "pending"
        assert "progress" in data


# =============================================================================
# Task Queue Tests
# =============================================================================


class TestTaskQueue:
    """Test TaskQueue class."""

    @pytest.fixture
    async def queue(self):
        """Create a task queue for testing."""
        q = TaskQueue(max_workers=2)
        await q.start()
        yield q
        await q.stop(wait=True, timeout=5.0)

    @pytest.mark.asyncio
    async def test_queue_start_stop(self) -> None:
        """Test queue start and stop."""
        queue = TaskQueue(max_workers=2)

        assert not queue.is_running

        await queue.start()
        assert queue.is_running
        assert queue.active_workers == 2

        await queue.stop()
        assert not queue.is_running

    @pytest.mark.asyncio
    async def test_submit_simple_task(self, queue: TaskQueue) -> None:
        """Test submitting a simple task."""

        async def simple_task(x: int) -> int:
            return x * 2

        task_id = await queue.submit(simple_task, 5, name="multiply")
        assert task_id is not None

        task = await queue.wait_for_task(task_id, timeout=5.0)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.result.success is True
        assert task.result.value == 10

    @pytest.mark.asyncio
    async def test_submit_with_kwargs(self, queue: TaskQueue) -> None:
        """Test submitting task with kwargs."""

        async def greeting(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        task_id = await queue.submit(
            greeting,
            name="World",
            greeting="Hi",
        )

        task = await queue.wait_for_task(task_id, timeout=5.0)
        assert task.result.value == "Hi, World!"

    @pytest.mark.asyncio
    async def test_task_priority(self, queue: TaskQueue) -> None:
        """Test task priority ordering."""
        results = []

        async def record_task(name: str) -> None:
            await asyncio.sleep(0.01)
            results.append(name)

        # Stop queue to accumulate tasks
        await queue.stop()

        queue2 = TaskQueue(max_workers=1)

        # Submit in reverse priority order
        await queue2.submit(
            record_task, "low",
            priority=TaskPriority.LOW,
        )
        await queue2.submit(
            record_task, "high",
            priority=TaskPriority.HIGH,
        )
        await queue2.submit(
            record_task, "critical",
            priority=TaskPriority.CRITICAL,
        )

        await queue2.start()
        await asyncio.sleep(0.5)
        await queue2.stop()

        # Higher priority tasks should complete first
        assert results[0] == "critical"
        assert results[1] == "high"
        assert results[2] == "low"

    @pytest.mark.asyncio
    async def test_task_timeout(self, queue: TaskQueue) -> None:
        """Test task timeout."""

        async def slow_task() -> None:
            await asyncio.sleep(10.0)

        task_id = await queue.submit(
            slow_task,
            name="slow",
            timeout_seconds=0.1,
        )

        task = await queue.wait_for_task(task_id, timeout=5.0)
        assert task.status == TaskStatus.TIMEOUT
        assert task.result.error == "Task timed out"

    @pytest.mark.asyncio
    async def test_task_failure_and_retry(self, queue: TaskQueue) -> None:
        """Test task failure and retry."""
        attempts = 0

        async def failing_task() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("Not ready yet")
            return "success"

        task_id = await queue.submit(
            failing_task,
            name="retry-test",
            max_retries=3,
        )

        task = await queue.wait_for_task(task_id, timeout=5.0)
        assert task.status == TaskStatus.COMPLETED
        assert task.retries == 2
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_task_failure_exhausted_retries(self, queue: TaskQueue) -> None:
        """Test task failure after exhausting retries."""

        async def always_fails() -> None:
            raise ValueError("Always fails")

        task_id = await queue.submit(
            always_fails,
            name="fail-test",
            max_retries=2,
        )

        task = await queue.wait_for_task(task_id, timeout=5.0)
        assert task.status == TaskStatus.FAILED
        assert task.retries == 2

    @pytest.mark.asyncio
    async def test_cancel_task(self, queue: TaskQueue) -> None:
        """Test task cancellation."""

        async def long_task() -> None:
            await asyncio.sleep(10.0)

        task_id = await queue.submit(long_task, name="cancel-test")

        # Wait a bit then cancel
        await asyncio.sleep(0.1)
        cancelled = await queue.cancel_task(task_id)

        assert cancelled is True

        task = await queue.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_task_status(self, queue: TaskQueue) -> None:
        """Test getting task status."""

        async def quick_task() -> str:
            return "done"

        task_id = await queue.submit(quick_task)

        status = await queue.get_task_status(task_id)
        assert status is not None
        assert status["id"] == task_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, queue: TaskQueue) -> None:
        """Test getting non-existent task."""
        task = await queue.get_task("nonexistent")
        assert task is None

        status = await queue.get_task_status("nonexistent")
        assert status is None

    @pytest.mark.asyncio
    async def test_queue_stats(self, queue: TaskQueue) -> None:
        """Test queue statistics."""

        async def quick_task() -> str:
            return "done"

        await queue.submit(quick_task)
        await asyncio.sleep(0.5)

        stats = queue.get_stats()
        assert stats["tasks_submitted"] >= 1
        assert stats["is_running"] is True

    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, queue: TaskQueue) -> None:
        """Test getting pending tasks."""
        await queue.stop()

        queue2 = TaskQueue(max_workers=1)

        async def slow_task() -> None:
            await asyncio.sleep(1.0)

        # Submit tasks without starting workers
        for i in range(3):
            await queue2.submit(slow_task, name=f"task-{i}")

        pending = await queue2.get_pending_tasks()
        assert len(pending) == 3

        await queue2.start()
        await queue2.stop()

    @pytest.mark.asyncio
    async def test_get_running_tasks(self, queue: TaskQueue) -> None:
        """Test getting running tasks."""

        async def slow_task() -> None:
            await asyncio.sleep(1.0)

        await queue.submit(slow_task, name="slow-1")
        await asyncio.sleep(0.1)

        running = await queue.get_running_tasks()
        assert len(running) >= 1

    @pytest.mark.asyncio
    async def test_cleanup_old_tasks(self, queue: TaskQueue) -> None:
        """Test cleaning up old tasks."""

        async def quick_task() -> str:
            return "done"

        task_id = await queue.submit(quick_task)
        await queue.wait_for_task(task_id, timeout=5.0)

        # Clean up with 0 hour age (immediate)
        removed = await queue.cleanup_old_tasks(max_age_hours=0)
        assert removed >= 1

    @pytest.mark.asyncio
    async def test_submit_not_running(self) -> None:
        """Test submitting to stopped queue raises error."""
        queue = TaskQueue()

        async def task() -> None:
            pass

        with pytest.raises(RuntimeError, match="not running"):
            await queue.submit(task)

    @pytest.mark.asyncio
    async def test_task_metadata(self, queue: TaskQueue) -> None:
        """Test task metadata."""

        async def task() -> str:
            return "done"

        task_id = await queue.submit(
            task,
            metadata={"user_id": "123", "request_type": "export"},
        )

        task_obj = await queue.get_task(task_id)
        assert task_obj.metadata["user_id"] == "123"
        assert task_obj.metadata["request_type"] == "export"

    @pytest.mark.asyncio
    async def test_concurrent_tasks(self, queue: TaskQueue) -> None:
        """Test concurrent task execution."""
        results = []

        async def concurrent_task(idx: int) -> int:
            await asyncio.sleep(0.1)
            results.append(idx)
            return idx

        # Submit multiple tasks
        task_ids = []
        for i in range(5):
            tid = await queue.submit(concurrent_task, i, name=f"concurrent-{i}")
            task_ids.append(tid)

        # Wait for all
        for tid in task_ids:
            await queue.wait_for_task(tid, timeout=5.0)

        assert len(results) == 5


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton task queue functions."""

    @pytest.mark.asyncio
    async def test_get_task_queue(self) -> None:
        """Test getting singleton queue."""
        await shutdown_task_queue()

        queue1 = get_task_queue()
        queue2 = get_task_queue()

        assert queue1 is queue2

        await shutdown_task_queue()

    @pytest.mark.asyncio
    async def test_init_and_shutdown(self) -> None:
        """Test init and shutdown."""
        await shutdown_task_queue()

        queue = await init_task_queue(max_workers=2)
        assert queue.is_running is True

        await shutdown_task_queue()
        assert queue.is_running is False


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_empty_queue_stop(self) -> None:
        """Test stopping empty queue."""
        queue = TaskQueue()
        await queue.start()
        await queue.stop()

        assert not queue.is_running

    @pytest.mark.asyncio
    async def test_double_start(self) -> None:
        """Test starting queue twice."""
        queue = TaskQueue()
        await queue.start()
        await queue.start()  # Should be idempotent

        assert queue.is_running
        await queue.stop()

    @pytest.mark.asyncio
    async def test_double_stop(self) -> None:
        """Test stopping queue twice."""
        queue = TaskQueue()
        await queue.start()
        await queue.stop()
        await queue.stop()  # Should be idempotent

        assert not queue.is_running

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self) -> None:
        """Test cancelling non-existent task."""
        queue = TaskQueue()
        await queue.start()

        result = await queue.cancel_task("nonexistent")
        assert result is False

        await queue.stop()

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self) -> None:
        """Test cancelling completed task."""
        queue = TaskQueue()
        await queue.start()

        async def quick() -> str:
            return "done"

        task_id = await queue.submit(quick)
        await queue.wait_for_task(task_id, timeout=5.0)

        result = await queue.cancel_task(task_id)
        assert result is False

        await queue.stop()

    @pytest.mark.asyncio
    async def test_wait_timeout(self) -> None:
        """Test wait_for_task timeout."""
        queue = TaskQueue()
        await queue.start()

        async def slow() -> None:
            await asyncio.sleep(10.0)

        task_id = await queue.submit(slow)

        result = await queue.wait_for_task(task_id, timeout=0.1)
        assert result is None

        await queue.stop()
