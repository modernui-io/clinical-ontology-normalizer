"""Async query executor with progress tracking for KG operations.

This module provides async query execution capabilities:
- Query execution with progress callbacks
- Streaming results for large queries
- Query cancellation support
- Integration with task queue
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, TypeVar

from app.services.circuit_breaker import CircuitBreaker
from app.services.retry_handler import RetryConfig, RetryHandler

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueryStatus(str, Enum):
    """Query execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    TIMEOUT = "timeout"


class QueryType(str, Enum):
    """Types of KG queries."""

    CONCEPT_LOOKUP = "concept_lookup"
    CONCEPT_SEARCH = "concept_search"
    RELATIONSHIP_QUERY = "relationship_query"
    PATH_FINDING = "path_finding"
    REASONING = "reasoning"
    GRAPH_TRAVERSAL = "graph_traversal"
    AGGREGATION = "aggregation"
    EXPORT = "export"


@dataclass
class QueryProgress:
    """Progress information for a query."""

    status: QueryStatus = QueryStatus.PENDING
    current_step: int = 0
    total_steps: int = 0
    records_processed: int = 0
    records_total: int = 0
    message: str = ""
    started_at: datetime | None = None
    updated_at: datetime | None = None
    elapsed_ms: float = 0.0

    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.records_total > 0:
            return min(100.0, (self.records_processed / self.records_total) * 100)
        if self.total_steps > 0:
            return min(100.0, (self.current_step / self.total_steps) * 100)
        return 0.0

    def update(
        self,
        current_step: int | None = None,
        total_steps: int | None = None,
        records_processed: int | None = None,
        records_total: int | None = None,
        message: str | None = None,
    ) -> None:
        """Update progress."""
        if current_step is not None:
            self.current_step = current_step
        if total_steps is not None:
            self.total_steps = total_steps
        if records_processed is not None:
            self.records_processed = records_processed
        if records_total is not None:
            self.records_total = records_total
        if message is not None:
            self.message = message
        self.updated_at = datetime.now(timezone.utc)
        if self.started_at:
            self.elapsed_ms = (self.updated_at - self.started_at).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "records_processed": self.records_processed,
            "records_total": self.records_total,
            "percentage": round(self.percentage, 2),
            "message": self.message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


@dataclass
class QueryResult:
    """Result of a query execution."""

    success: bool
    data: Any = None
    error: str | None = None
    error_type: str | None = None
    progress: QueryProgress = field(default_factory=QueryProgress)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "progress": self.progress.to_dict(),
            "metadata": self.metadata,
        }


ProgressCallback = Callable[[QueryProgress], None]


@dataclass
class QueryContext:
    """Context for query execution."""

    query_id: str
    query_type: QueryType
    parameters: dict[str, Any] = field(default_factory=dict)
    progress: QueryProgress = field(default_factory=QueryProgress)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    progress_callback: ProgressCallback | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: float = 300.0
    retry_config: RetryConfig | None = None
    circuit_breaker: CircuitBreaker | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_cancelled(self) -> bool:
        """Check if query was cancelled."""
        return self.cancel_event.is_set()

    def update_progress(
        self,
        current_step: int | None = None,
        total_steps: int | None = None,
        records_processed: int | None = None,
        records_total: int | None = None,
        message: str | None = None,
    ) -> None:
        """Update and notify progress."""
        self.progress.update(
            current_step=current_step,
            total_steps=total_steps,
            records_processed=records_processed,
            records_total=records_total,
            message=message,
        )
        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")


class AsyncQueryExecutor:
    """Executor for async KG queries with progress tracking."""

    def __init__(
        self,
        default_timeout: float = 300.0,
        default_retry_config: RetryConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """Initialize the query executor.

        Args:
            default_timeout: Default query timeout in seconds
            default_retry_config: Default retry configuration
            circuit_breaker: Optional circuit breaker
        """
        self._default_timeout = default_timeout
        self._default_retry_config = default_retry_config
        self._circuit_breaker = circuit_breaker
        self._active_queries: dict[str, QueryContext] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        query_func: Callable[..., Any],
        context: QueryContext,
    ) -> QueryResult:
        """Execute a query with progress tracking.

        Args:
            query_func: Async function to execute
            context: Query context with parameters and callbacks

        Returns:
            QueryResult with execution results
        """
        result = QueryResult(success=False, progress=context.progress)

        async with self._lock:
            self._active_queries[context.query_id] = context

        context.progress.started_at = datetime.now(timezone.utc)
        context.progress.status = QueryStatus.EXECUTING
        context.update_progress(message="Starting query execution")

        try:
            # Set up retry handler if configured
            retry_handler = None
            if context.retry_config:
                retry_handler = RetryHandler(
                    context.retry_config,
                    context.circuit_breaker or self._circuit_breaker,
                )

            # Execute with timeout
            timeout = context.timeout_seconds or self._default_timeout

            if retry_handler:
                data = await asyncio.wait_for(
                    retry_handler.execute_async(
                        query_func,
                        context,
                    ),
                    timeout=timeout,
                )
            else:
                data = await asyncio.wait_for(
                    query_func(context),
                    timeout=timeout,
                )

            # Check if cancelled during execution
            if context.is_cancelled():
                context.progress.status = QueryStatus.CANCELLED
                result.error = "Query was cancelled"
                return result

            # Success
            context.progress.status = QueryStatus.COMPLETED
            context.update_progress(message="Query completed successfully")
            result.success = True
            result.data = data

            logger.info(
                f"Query {context.query_id} completed in "
                f"{context.progress.elapsed_ms:.2f}ms"
            )

        except asyncio.TimeoutError:
            context.progress.status = QueryStatus.TIMEOUT
            result.error = f"Query timed out after {timeout}s"
            result.error_type = "TimeoutError"
            logger.warning(f"Query {context.query_id} timed out")

        except asyncio.CancelledError:
            context.progress.status = QueryStatus.CANCELLED
            result.error = "Query was cancelled"
            result.error_type = "CancelledError"
            logger.info(f"Query {context.query_id} cancelled")

        except Exception as e:
            context.progress.status = QueryStatus.FAILED
            result.error = str(e)
            result.error_type = type(e).__name__
            logger.error(f"Query {context.query_id} failed: {e}")

        finally:
            async with self._lock:
                self._active_queries.pop(context.query_id, None)

        return result

    async def execute_streaming(
        self,
        query_func: Callable[..., AsyncIterator[Any]],
        context: QueryContext,
        batch_size: int = 100,
    ) -> AsyncIterator[Any]:
        """Execute a streaming query with progress tracking.

        Args:
            query_func: Async generator function
            context: Query context
            batch_size: Records per batch for progress updates

        Yields:
            Query results as they become available
        """
        async with self._lock:
            self._active_queries[context.query_id] = context

        context.progress.started_at = datetime.now(timezone.utc)
        context.progress.status = QueryStatus.STREAMING
        context.update_progress(message="Starting streaming query")

        records_yielded = 0

        try:
            timeout = context.timeout_seconds or self._default_timeout
            deadline = time.time() + timeout

            async for record in query_func(context):
                # Check timeout
                if time.time() > deadline:
                    context.progress.status = QueryStatus.TIMEOUT
                    raise asyncio.TimeoutError(f"Stream timed out after {timeout}s")

                # Check cancellation
                if context.is_cancelled():
                    context.progress.status = QueryStatus.CANCELLED
                    break

                records_yielded += 1
                yield record

                # Update progress periodically
                if records_yielded % batch_size == 0:
                    context.update_progress(
                        records_processed=records_yielded,
                        message=f"Processed {records_yielded} records",
                    )

            # Final progress update
            context.progress.status = QueryStatus.COMPLETED
            context.update_progress(
                records_processed=records_yielded,
                message=f"Streaming complete: {records_yielded} records",
            )

            logger.info(
                f"Stream query {context.query_id} completed: "
                f"{records_yielded} records in {context.progress.elapsed_ms:.2f}ms"
            )

        except asyncio.TimeoutError:
            context.progress.status = QueryStatus.TIMEOUT
            logger.warning(f"Stream query {context.query_id} timed out")
            raise

        except asyncio.CancelledError:
            context.progress.status = QueryStatus.CANCELLED
            logger.info(f"Stream query {context.query_id} cancelled")
            raise

        except Exception as e:
            context.progress.status = QueryStatus.FAILED
            logger.error(f"Stream query {context.query_id} failed: {e}")
            raise

        finally:
            async with self._lock:
                self._active_queries.pop(context.query_id, None)

    async def cancel_query(self, query_id: str) -> bool:
        """Cancel an active query.

        Args:
            query_id: Query ID to cancel

        Returns:
            True if query was cancelled
        """
        async with self._lock:
            context = self._active_queries.get(query_id)
            if context:
                context.cancel_event.set()
                context.progress.status = QueryStatus.CANCELLED
                logger.info(f"Query {query_id} cancellation requested")
                return True
        return False

    async def get_progress(self, query_id: str) -> QueryProgress | None:
        """Get progress for an active query.

        Args:
            query_id: Query ID

        Returns:
            QueryProgress or None if not found
        """
        context = self._active_queries.get(query_id)
        return context.progress if context else None

    def get_active_queries(self) -> list[dict[str, Any]]:
        """Get information about active queries."""
        return [
            {
                "query_id": ctx.query_id,
                "query_type": ctx.query_type.value,
                "progress": ctx.progress.to_dict(),
                "created_at": ctx.created_at.isoformat(),
            }
            for ctx in self._active_queries.values()
        ]


class BatchQueryExecutor:
    """Executor for batch queries with parallel execution."""

    def __init__(
        self,
        executor: AsyncQueryExecutor,
        max_concurrent: int = 10,
    ) -> None:
        """Initialize batch executor.

        Args:
            executor: Underlying query executor
            max_concurrent: Maximum concurrent queries
        """
        self._executor = executor
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute_batch(
        self,
        queries: list[tuple[Callable[..., Any], QueryContext]],
        fail_fast: bool = False,
    ) -> list[QueryResult]:
        """Execute multiple queries in parallel.

        Args:
            queries: List of (query_func, context) tuples
            fail_fast: Stop on first failure

        Returns:
            List of QueryResult in same order as input
        """
        async def execute_with_semaphore(
            query_func: Callable[..., Any],
            context: QueryContext,
        ) -> QueryResult:
            async with self._semaphore:
                return await self._executor.execute(query_func, context)

        if fail_fast:
            # Use gather with return_exceptions=False
            results = []
            for query_func, context in queries:
                result = await execute_with_semaphore(query_func, context)
                results.append(result)
                if not result.success:
                    # Fill remaining with failed placeholders
                    for _ in range(len(queries) - len(results)):
                        results.append(QueryResult(
                            success=False,
                            error="Batch execution stopped due to previous failure",
                        ))
                    break
            return results
        else:
            # Execute all in parallel
            tasks = [
                execute_with_semaphore(query_func, context)
                for query_func, context in queries
            ]
            return await asyncio.gather(*tasks)


# Singleton instance
_query_executor: AsyncQueryExecutor | None = None


def get_query_executor(
    default_timeout: float = 300.0,
    default_retry_config: RetryConfig | None = None,
) -> AsyncQueryExecutor:
    """Get the singleton query executor instance."""
    global _query_executor
    if _query_executor is None:
        _query_executor = AsyncQueryExecutor(
            default_timeout=default_timeout,
            default_retry_config=default_retry_config,
        )
    return _query_executor


# Utility functions for common query patterns
async def execute_with_progress(
    query_func: Callable[..., Any],
    query_type: QueryType,
    parameters: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
    timeout_seconds: float = 300.0,
) -> QueryResult:
    """Convenience function to execute a query with progress tracking.

    Args:
        query_func: Query function to execute
        query_type: Type of query
        parameters: Query parameters
        progress_callback: Optional progress callback
        timeout_seconds: Query timeout

    Returns:
        QueryResult
    """
    import uuid

    executor = get_query_executor()
    context = QueryContext(
        query_id=str(uuid.uuid4()),
        query_type=query_type,
        parameters=parameters,
        progress_callback=progress_callback,
        timeout_seconds=timeout_seconds,
    )

    return await executor.execute(query_func, context)
