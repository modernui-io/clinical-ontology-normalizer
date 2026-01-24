#!/usr/bin/env python3
"""Standalone test runner for async query executor."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
import uuid
from datetime import datetime, timezone

# Add path first
sys.path.insert(0, ".")

# Set up mock module hierarchy BEFORE any imports
mock_app = types.ModuleType("app")
mock_app.__path__ = ["."]
sys.modules["app"] = mock_app

mock_services = types.ModuleType("app.services")
mock_services.__path__ = ["app/services"]
sys.modules["app.services"] = mock_services

# Create circuit breaker mock module
mock_cb = types.ModuleType("app.services.circuit_breaker")
mock_cb.__file__ = "app/services/circuit_breaker.py"


class MockCircuitBreaker:
    """Mock circuit breaker."""
    pass


class MockCircuitBreakerOpen(Exception):
    """Mock circuit breaker open exception."""
    pass


mock_cb.CircuitBreaker = MockCircuitBreaker
mock_cb.CircuitBreakerOpen = MockCircuitBreakerOpen
sys.modules["app.services.circuit_breaker"] = mock_cb

# Create retry handler mock module
mock_retry = types.ModuleType("app.services.retry_handler")
mock_retry.__file__ = "app/services/retry_handler.py"


class MockRetryConfig:
    """Mock retry config."""
    def __init__(self, **kwargs):
        pass


class MockRetryHandler:
    """Mock retry handler."""
    def __init__(self, *args, **kwargs):
        pass

    async def execute_async(self, fn, *args, **kwargs):
        return await fn(*args, **kwargs)


mock_retry.RetryConfig = MockRetryConfig
mock_retry.RetryHandler = MockRetryHandler
sys.modules["app.services.retry_handler"] = mock_retry

# Now use importlib to load the module properly
# This requires setting up the module spec correctly
import importlib.util

# Create a proper module spec
spec = importlib.util.spec_from_file_location(
    "app.services.async_query_executor",
    "app/services/async_query_executor.py",
    submodule_search_locations=[]
)

# Create the module and add it to sys.modules BEFORE loading
module = importlib.util.module_from_spec(spec)
module.__package__ = "app.services"
sys.modules["app.services.async_query_executor"] = module

# Now execute the module - dataclasses will work because module is in sys.modules
spec.loader.exec_module(module)

# Extract the classes we need
QueryStatus = module.QueryStatus
QueryType = module.QueryType
QueryProgress = module.QueryProgress
QueryResult = module.QueryResult
QueryContext = module.QueryContext
AsyncQueryExecutor = module.AsyncQueryExecutor
BatchQueryExecutor = module.BatchQueryExecutor

passed = 0
failed = 0


def test(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✓ {name}")
        passed += 1
    else:
        print(f"✗ {name}")
        failed += 1


async def async_test(name: str, test_fn) -> None:
    global passed, failed
    try:
        await test_fn()
        print(f"✓ {name}")
        passed += 1
    except AssertionError as e:
        print(f"✗ {name}: {e}")
        failed += 1
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")
        failed += 1


async def run_tests():
    # QueryStatus tests
    test("status_pending", QueryStatus.PENDING.value == "pending")
    test("status_executing", QueryStatus.EXECUTING.value == "executing")
    test("status_completed", QueryStatus.COMPLETED.value == "completed")
    test("status_failed", QueryStatus.FAILED.value == "failed")
    test("status_cancelled", QueryStatus.CANCELLED.value == "cancelled")
    test("status_timeout", QueryStatus.TIMEOUT.value == "timeout")

    # QueryType tests
    test("type_concept_lookup", QueryType.CONCEPT_LOOKUP.value == "concept_lookup")
    test("type_path_finding", QueryType.PATH_FINDING.value == "path_finding")
    test("type_reasoning", QueryType.REASONING.value == "reasoning")

    # QueryProgress tests
    progress = QueryProgress()
    test("progress_initial", progress.status == QueryStatus.PENDING)
    test("progress_initial_zero", progress.current_step == 0)

    progress2 = QueryProgress(records_processed=50, records_total=100)
    test("progress_percentage_records", progress2.percentage == 50.0)

    progress3 = QueryProgress(current_step=3, total_steps=10)
    test("progress_percentage_steps", progress3.percentage == 30.0)

    progress4 = QueryProgress(records_processed=150, records_total=100)
    test("progress_percentage_capped", progress4.percentage == 100.0)

    progress5 = QueryProgress()
    progress5.started_at = datetime.now(timezone.utc)
    progress5.update(current_step=5, message="Processing")
    test("progress_update", progress5.current_step == 5 and progress5.message == "Processing")

    data = progress3.to_dict()
    test("progress_to_dict", data["status"] == "pending" and data["percentage"] == 30.0)

    # QueryResult tests
    result1 = QueryResult(success=True, data={"concepts": []})
    test("result_success", result1.success and result1.data == {"concepts": []})

    result2 = QueryResult(success=False, error="Failed", error_type="RuntimeError")
    test("result_failure", not result2.success and result2.error == "Failed")

    result_dict = result1.to_dict()
    test("result_to_dict", "success" in result_dict and "progress" in result_dict)

    # QueryContext tests
    ctx = QueryContext(
        query_id="test-1",
        query_type=QueryType.CONCEPT_LOOKUP,
        parameters={"cui": "C0004096"},
    )
    test("context_creation", ctx.query_id == "test-1")
    test("context_not_cancelled", not ctx.is_cancelled())
    ctx.cancel_event.set()
    test("context_is_cancelled", ctx.is_cancelled())

    # Test context with progress callback
    callback_called = False

    def callback(p):
        nonlocal callback_called
        callback_called = True

    ctx2 = QueryContext(
        query_id="test-2",
        query_type=QueryType.CONCEPT_LOOKUP,
        progress_callback=callback,
    )
    ctx2.progress.started_at = datetime.now(timezone.utc)
    ctx2.update_progress(current_step=1)
    test("context_callback", callback_called)

    # AsyncQueryExecutor tests
    async def test_execute_success():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def successful_query(ctx):
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

    await async_test("execute_success", test_execute_success)

    async def test_execute_with_progress():
        executor = AsyncQueryExecutor(default_timeout=5.0)
        progress_updates = []

        async def query_with_progress(ctx):
            for i in range(5):
                ctx.update_progress(current_step=i + 1, total_steps=5)
                await asyncio.sleep(0.01)
            return "done"

        def callback(p):
            progress_updates.append(p.percentage)

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.PATH_FINDING,
            progress_callback=callback,
        )

        result = await executor.execute(query_with_progress, context)
        assert result.success is True
        assert len(progress_updates) > 0

    await async_test("execute_with_progress", test_execute_with_progress)

    async def test_execute_timeout():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def slow_query(ctx):
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

    await async_test("execute_timeout", test_execute_timeout)

    async def test_execute_failure():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def failing_query(ctx):
            raise ValueError("Query failed")

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.CONCEPT_SEARCH,
        )

        result = await executor.execute(failing_query, context)

        assert result.success is False
        assert result.error == "Query failed"
        assert result.error_type == "ValueError"

    await async_test("execute_failure", test_execute_failure)

    async def test_execute_cancellation():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def cancellable_query(ctx):
            for i in range(20):
                if ctx.is_cancelled():
                    return "cancelled"
                await asyncio.sleep(0.05)
            return "done"

        context = QueryContext(
            query_id=str(uuid.uuid4()),
            query_type=QueryType.GRAPH_TRAVERSAL,
        )

        async def cancel_after_delay():
            await asyncio.sleep(0.15)
            context.cancel_event.set()

        asyncio.create_task(cancel_after_delay())
        result = await executor.execute(cancellable_query, context)

        # Either returns "cancelled" or got cancelled status
        assert result.data == "cancelled" or result.progress.status == QueryStatus.CANCELLED, \
            f"Expected cancellation but got data={result.data}, status={result.progress.status}"

    await async_test("execute_cancellation", test_execute_cancellation)

    async def test_cancel_query():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def long_query(ctx):
            await asyncio.sleep(10.0)
            return "done"

        context = QueryContext(
            query_id="test-cancel",
            query_type=QueryType.EXPORT,
        )

        task = asyncio.create_task(executor.execute(long_query, context))
        await asyncio.sleep(0.1)

        cancelled = await executor.cancel_query("test-cancel")
        assert cancelled is True

        result = await task
        assert result.progress.status == QueryStatus.CANCELLED

    await async_test("cancel_query", test_cancel_query)

    async def test_get_progress():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def tracked_query(ctx):
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

    await async_test("get_progress", test_get_progress)

    async def test_get_active_queries():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def slow_query(ctx):
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

    await async_test("get_active_queries", test_get_active_queries)

    # Streaming tests
    async def test_streaming_success():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def streaming_query(ctx):
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

    await async_test("streaming_success", test_streaming_success)

    async def test_streaming_cancellation():
        executor = AsyncQueryExecutor(default_timeout=5.0)

        async def long_stream(ctx):
            for i in range(100):
                if ctx.is_cancelled():
                    break
                yield {"record": i}
                await asyncio.sleep(0.02)

        context = QueryContext(
            query_id="test-stream-cancel-" + str(uuid.uuid4())[:8],
            query_type=QueryType.EXPORT,
        )

        records = []

        async for record in executor.execute_streaming(long_stream, context):
            records.append(record)
            if len(records) >= 3:
                await executor.cancel_query(context.query_id)
                break  # Explicitly break after cancel to avoid race condition

        assert len(records) >= 3, f"Expected at least 3 records, got {len(records)}"
        # After breaking, status should be cancelled or completed
        assert context.progress.status in (QueryStatus.CANCELLED, QueryStatus.COMPLETED), \
            f"Expected CANCELLED or COMPLETED, got {context.progress.status}"

    await async_test("streaming_cancellation", test_streaming_cancellation)

    # BatchQueryExecutor tests
    async def test_batch_success():
        executor = AsyncQueryExecutor(default_timeout=5.0)
        batch_executor = BatchQueryExecutor(executor, max_concurrent=3)

        async def query(ctx):
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

    await async_test("batch_success", test_batch_success)

    async def test_batch_fail_fast():
        executor = AsyncQueryExecutor(default_timeout=5.0)
        batch_executor = BatchQueryExecutor(executor, max_concurrent=3)

        async def query(ctx):
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
        assert results[0].success is True
        assert results[1].success is True
        assert results[2].success is False

    await async_test("batch_fail_fast", test_batch_fail_fast)

    async def test_batch_concurrent_limit():
        executor = AsyncQueryExecutor(default_timeout=5.0)
        batch_executor = BatchQueryExecutor(executor, max_concurrent=3)

        concurrent_count = 0
        max_concurrent = 0

        async def tracked_query(ctx):
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
        assert max_concurrent <= 3

    await async_test("batch_concurrent_limit", test_batch_concurrent_limit)

    # Print summary
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed == 0:
        print("All tests passed!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
