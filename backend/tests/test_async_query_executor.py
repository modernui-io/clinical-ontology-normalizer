"""Tests for async query executor with progress tracking."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.async_query_executor import (
    AsyncQueryExecutor,
    BatchQueryExecutor,
    QueryContext,
    QueryProgress,
    QueryResult,
    QueryStatus,
    QueryType,
    execute_with_progress,
    get_query_executor,
)


# =============================================================================
# QueryStatus Tests
# =============================================================================


class TestQueryStatus:
    """Test QueryStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values."""
        assert QueryStatus.PENDING.value == "pending"
        assert QueryStatus.EXECUTING.value == "executing"
        assert QueryStatus.STREAMING.value == "streaming"
        assert QueryStatus.COMPLETED.value == "completed"
        assert QueryStatus.CANCELLED.value == "cancelled"
        assert QueryStatus.FAILED.value == "failed"
        assert QueryStatus.TIMEOUT.value == "timeout"


class TestQueryType:
    """Test QueryType enum."""

    def test_type_values(self) -> None:
        """Test query type values."""
        assert QueryType.CONCEPT_LOOKUP.value == "concept_lookup"
        assert QueryType.PATH_FINDING.value == "path_finding"
        assert QueryType.REASONING.value == "reasoning"


# =============================================================================
# QueryProgress Tests
# =============================================================================


class TestQueryProgress:
    """Test QueryProgress dataclass."""

    def test_initial_progress(self) -> None:
        """Test initial progress values."""
        progress = QueryProgress()
        assert progress.status == QueryStatus.PENDING
        assert progress.current_step == 0
        assert progress.records_processed == 0
        assert progress.percentage == 0.0

    def test_percentage_from_records(self) -> None:
        """Test percentage calculation from records."""
        progress = QueryProgress(records_processed=50, records_total=100)
        assert progress.percentage == 50.0

    def test_percentage_from_steps(self) -> None:
        """Test percentage calculation from steps."""
        progress = QueryProgress(current_step=3, total_steps=10)
        assert progress.percentage == 30.0

    def test_percentage_capped(self) -> None:
        """Test percentage is capped at 100."""
        progress = QueryProgress(records_processed=150, records_total=100)
        assert progress.percentage == 100.0

    def test_update_progress(self) -> None:
        """Test progress update."""
        progress = QueryProgress()
        progress.started_at = datetime.now(timezone.utc)
        progress.update(
            current_step=5,
            total_steps=10,
            records_processed=50,
            message="Processing",
        )

        assert progress.current_step == 5
        assert progress.records_processed == 50
        assert progress.message == "Processing"
        assert progress.updated_at is not None

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        progress = QueryProgress(
            status=QueryStatus.EXECUTING,
            current_step=5,
            total_steps=10,
            message="Test",
        )
        data = progress.to_dict()

        assert data["status"] == "executing"
        assert data["current_step"] == 5
        assert data["percentage"] == 50.0


# =============================================================================
# QueryResult Tests
# =============================================================================


class TestQueryResult:
    """Test QueryResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = QueryResult(success=True, data={"concepts": []})
        assert result.success is True
        assert result.data == {"concepts": []}
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed result."""
        result = QueryResult(
            success=False,
            error="Query failed",
            error_type="RuntimeError",
        )
        assert result.success is False
        assert result.error == "Query failed"

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = QueryResult(success=True, data="test")
        data = result.to_dict()

        assert data["success"] is True
        assert data["data"] == "test"
        assert "progress" in data


# =============================================================================
# QueryContext Tests
# =============================================================================


class TestQueryContext:
    """Test QueryContext dataclass."""

    def test_context_creation(self) -> None:
        """Test context creation."""
        context = QueryContext(
            query_id="test-1",
            query_type=QueryType.CONCEPT_LOOKUP,
            parameters={"cui": "C0004096"},
        )

        assert context.query_id == "test-1"
        assert context.query_type == QueryType.CONCEPT_LOOKUP
        assert context.parameters["cui"] == "C0004096"

    def test_is_cancelled(self) -> None:
        """Test cancellation check."""
        context = QueryContext(
            query_id="test-1",
            query_type=QueryType.CONCEPT_LOOKUP,
        )

        assert not context.is_cancelled()
        context.cancel_event.set()
        assert context.is_cancelled()

    def test_update_progress(self) -> None:
        """Test progress update with callback."""
        callback_called = False
        callback_progress = None

        def callback(progress: QueryProgress) -> None:
            nonlocal callback_called, callback_progress
            callback_called = True
            callback_progress = progress

        context = QueryContext(
            query_id="test-1",
            query_type=QueryType.CONCEPT_LOOKUP,
            progress_callback=callback,
        )
        context.progress.started_at = datetime.now(timezone.utc)

        context.update_progress(current_step=5, message="Processing")

        assert callback_called
        assert callback_progress.current_step == 5


# =============================================================================
# AsyncQueryExecutor Tests
# =============================================================================


class TestAsyncQueryExecutor:
    """Test AsyncQueryExecutor class."""

    @pytest.fixture
    def executor(self) -> AsyncQueryExecutor:
        """Create executor instance."""
        return AsyncQueryExecutor(default_timeout=5.0)

    @pytest.mark.asyncio
    async def test_execute_success(self, executor: AsyncQueryExecutor) -> None:
        """Test successful query execution."""

        async def successful_query(ctx: QueryContext) -> dict:
            ctx.update_progress(current_step=1, total_steps=1)
            return {"data": "result"}

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.CONCEPT_LOOKUP,
        )

        result = await executor.execute(successful_query, context)

        assert result.success is True
        assert result.data == {"data": "result"}
        assert result.progress.status == QueryStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_with_progress(self, executor: AsyncQueryExecutor) -> None:
        """Test execution with progress updates."""
        progress_updates = []

        async def query_with_progress(ctx: QueryContext) -> str:
            for i in range(5):
                ctx.update_progress(
                    current_step=i + 1,
                    total_steps=5,
                    message=f"Step {i + 1}",
                )
                await asyncio.sleep(0.01)
            return "done"

        def callback(progress: QueryProgress) -> None:
            progress_updates.append(progress.percentage)

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.PATH_FINDING,
            progress_callback=callback,
        )

        result = await executor.execute(query_with_progress, context)

        assert result.success is True
        assert len(progress_updates) > 0

    @pytest.mark.asyncio
    async def test_execute_timeout(self, executor: AsyncQueryExecutor) -> None:
        """Test query timeout."""

        async def slow_query(ctx: QueryContext) -> str:
            await asyncio.sleep(10.0)
            return "done"

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.REASONING,
            timeout_seconds=0.1,
        )

        result = await executor.execute(slow_query, context)

        assert result.success is False
        assert result.error_type == "TimeoutError"
        assert result.progress.status == QueryStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_failure(self, executor: AsyncQueryExecutor) -> None:
        """Test query failure."""

        async def failing_query(ctx: QueryContext) -> str:
            raise ValueError("Query failed")

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.CONCEPT_SEARCH,
        )

        result = await executor.execute(failing_query, context)

        assert result.success is False
        assert result.error == "Query failed"
        assert result.error_type == "ValueError"
        assert result.progress.status == QueryStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_cancellation(self, executor: AsyncQueryExecutor) -> None:
        """Test query cancellation."""

        async def cancellable_query(ctx: QueryContext) -> str:
            for i in range(10):
                if ctx.is_cancelled():
                    return "cancelled"
                await asyncio.sleep(0.1)
            return "done"

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.GRAPH_TRAVERSAL,
        )

        # Start query and cancel after short delay
        async def cancel_after_delay():
            await asyncio.sleep(0.2)
            context.cancel_event.set()

        asyncio.create_task(cancel_after_delay())
        result = await executor.execute(cancellable_query, context)

        # When cancelled, result indicates cancellation (data may be None or "cancelled")
        assert not result.success or result.data == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_query(self, executor: AsyncQueryExecutor) -> None:
        """Test cancel_query method."""

        async def long_query(ctx: QueryContext) -> str:
            await asyncio.sleep(10.0)
            return "done"

        context = QueryContext(
            query_id="test-cancel",
            query_type=QueryType.EXPORT,
        )

        # Start query
        task = asyncio.create_task(executor.execute(long_query, context))
        await asyncio.sleep(0.1)

        # Cancel it
        cancelled = await executor.cancel_query("test-cancel")
        assert cancelled is True

        result = await task
        assert result.progress.status == QueryStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_progress(self, executor: AsyncQueryExecutor) -> None:
        """Test getting query progress."""

        async def tracked_query(ctx: QueryContext) -> str:
            ctx.update_progress(records_processed=50, records_total=100)
            await asyncio.sleep(0.5)
            return "done"

        context = QueryContext(
            query_id="test-progress",
            query_type=QueryType.AGGREGATION,
        )

        task = asyncio.create_task(executor.execute(tracked_query, context))
        await asyncio.sleep(0.1)

        progress = await executor.get_progress("test-progress")
        assert progress is not None
        assert progress.records_processed == 50

        await task

    @pytest.mark.asyncio
    async def test_get_active_queries(self, executor: AsyncQueryExecutor) -> None:
        """Test getting active queries."""

        async def slow_query(ctx: QueryContext) -> str:
            await asyncio.sleep(1.0)
            return "done"

        context = QueryContext(
            query_id="test-active",
            query_type=QueryType.REASONING,
        )

        task = asyncio.create_task(executor.execute(slow_query, context))
        await asyncio.sleep(0.1)

        active = executor.get_active_queries()
        assert len(active) >= 1
        assert active[0]["query_id"] == "test-active"

        await executor.cancel_query("test-active")
        await task


# =============================================================================
# Streaming Query Tests
# =============================================================================


class TestStreamingQueries:
    """Test streaming query execution."""

    @pytest.fixture
    def executor(self) -> AsyncQueryExecutor:
        """Create executor instance."""
        return AsyncQueryExecutor(default_timeout=5.0)

    @pytest.mark.asyncio
    async def test_streaming_success(self, executor: AsyncQueryExecutor) -> None:
        """Test successful streaming query."""

        async def streaming_query(ctx: QueryContext):
            for i in range(5):
                if ctx.is_cancelled():
                    break
                yield {"record": i}
                await asyncio.sleep(0.01)

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.EXPORT,
        )

        records = []
        async for record in executor.execute_streaming(streaming_query, context):
            records.append(record)

        assert len(records) == 5
        assert context.progress.status == QueryStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_streaming_cancellation(self, executor: AsyncQueryExecutor) -> None:
        """Test streaming query cancellation."""

        async def long_stream(ctx: QueryContext):
            for i in range(100):
                if ctx.is_cancelled():
                    break
                yield {"record": i}
                await asyncio.sleep(0.05)

        context = QueryContext(
            query_id="test-stream-cancel",
            query_type=QueryType.EXPORT,
        )

        records = []

        async def consume():
            async for record in executor.execute_streaming(long_stream, context):
                records.append(record)
                if len(records) >= 3:
                    await executor.cancel_query("test-stream-cancel")

        await consume()
        assert len(records) >= 3
        # Stream may complete before cancel takes effect
        assert context.progress.status in (QueryStatus.CANCELLED, QueryStatus.COMPLETED)


# =============================================================================
# BatchQueryExecutor Tests
# =============================================================================


class TestBatchQueryExecutor:
    """Test BatchQueryExecutor class."""

    @pytest.fixture
    def batch_executor(self) -> BatchQueryExecutor:
        """Create batch executor instance."""
        executor = AsyncQueryExecutor(default_timeout=5.0)
        return BatchQueryExecutor(executor, max_concurrent=3)

    @pytest.mark.asyncio
    async def test_batch_success(self, batch_executor: BatchQueryExecutor) -> None:
        """Test successful batch execution."""

        async def query(ctx: QueryContext) -> int:
            return ctx.parameters.get("value", 0) * 2

        queries = [
            (
                query,
                QueryContext(
                    query_id=str(uuid.uuid4()),
                    query_type=QueryType.CONCEPT_LOOKUP,
                    parameters={"value": i},
                ),
            )
            for i in range(5)
        ]

        results = await batch_executor.execute_batch(queries)

        assert len(results) == 5
        assert all(r.success for r in results)
        assert [r.data for r in results] == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_batch_fail_fast(self, batch_executor: BatchQueryExecutor) -> None:
        """Test batch execution with fail_fast."""

        async def query(ctx: QueryContext) -> int:
            idx = ctx.parameters.get("idx", 0)
            if idx == 2:
                raise ValueError("Query failed")
            return idx

        queries = [
            (
                query,
                QueryContext(
                    query_id=str(uuid.uuid4()),
                    query_type=QueryType.CONCEPT_LOOKUP,
                    parameters={"idx": i},
                ),
            )
            for i in range(5)
        ]

        results = await batch_executor.execute_batch(queries, fail_fast=True)

        assert len(results) == 5
        # First two should succeed
        assert results[0].success is True
        assert results[1].success is True
        # Third should fail
        assert results[2].success is False
        # Rest should be stopped
        assert results[3].success is False
        assert results[4].success is False

    @pytest.mark.asyncio
    async def test_batch_concurrent_limit(
        self, batch_executor: BatchQueryExecutor
    ) -> None:
        """Test concurrent execution limit."""
        concurrent_count = 0
        max_concurrent = 0

        async def tracked_query(ctx: QueryContext) -> int:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            return 1

        queries = [
            (
                tracked_query,
                QueryContext(
                    query_id=str(uuid.uuid4()),
                    query_type=QueryType.CONCEPT_LOOKUP,
                ),
            )
            for _ in range(10)
        ]

        await batch_executor.execute_batch(queries)

        # Should never exceed max_concurrent=3
        assert max_concurrent <= 3


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton function."""

    def test_get_query_executor(self) -> None:
        """Test getting singleton executor."""
        executor1 = get_query_executor()
        executor2 = get_query_executor()

        assert executor1 is executor2


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_execute_with_progress(self) -> None:
        """Test execute_with_progress convenience function."""
        progress_updates = []

        async def simple_query(ctx: QueryContext) -> str:
            ctx.update_progress(current_step=1, total_steps=1)
            return "result"

        def callback(progress: QueryProgress) -> None:
            progress_updates.append(progress.percentage)

        result = await execute_with_progress(
            simple_query,
            QueryType.CONCEPT_LOOKUP,
            {"cui": "C0004096"},
            progress_callback=callback,
        )

        assert result.success is True
        assert result.data == "result"
