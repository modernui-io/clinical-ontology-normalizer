"""Event streaming service for real-time processing updates.

Provides a unified interface for publishing and subscribing to processing events
via both WebSocket and Server-Sent Events (SSE) transports.

Event Types:
- extraction_started: Document processing has begun
- mention_found: A clinical mention was extracted
- extraction_complete: All mentions extracted successfully
- mapping_started: Concept mapping phase has begun
- mapping_complete: All concepts mapped
- fact_created: A clinical fact was created
- processing_complete: Entire document processing finished
- error: An error occurred during processing
- job_started: Batch job has begun
- job_progress: Batch job progress update
- job_complete: Batch job finished
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be published."""

    # Document processing events
    EXTRACTION_STARTED = "extraction_started"
    MENTION_FOUND = "mention_found"
    EXTRACTION_COMPLETE = "extraction_complete"
    MAPPING_STARTED = "mapping_started"
    MAPPING_COMPLETE = "mapping_complete"
    FACT_CREATED = "fact_created"
    PROCESSING_COMPLETE = "processing_complete"
    ERROR = "error"

    # Batch job events
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETE = "job_complete"


@dataclass
class ProcessingEvent:
    """Represents a processing event to be streamed to clients.

    Attributes:
        event_type: Type of event (from EventType enum).
        entity_id: UUID of the document or job this event relates to.
        entity_type: Either "document" or "job".
        data: Event-specific payload data.
        timestamp: When the event occurred.
        sequence: Monotonically increasing sequence number for ordering.
    """

    event_type: EventType
    entity_id: UUID
    entity_type: str  # "document" or "job"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "event": self.event_type.value,
            "entity_id": str(self.entity_id),
            "entity_type": self.entity_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())

    def to_sse(self) -> str:
        """Format event as Server-Sent Events message.

        SSE format:
        event: <event_type>
        data: <json_payload>

        """
        return f"event: {self.event_type.value}\ndata: {self.to_json()}\n\n"


class EventStreamService:
    """Service for managing event subscriptions and broadcasting.

    This service maintains a registry of active subscribers (WebSocket connections
    or SSE response streams) and distributes events to appropriate subscribers
    based on the entity they're interested in.

    Thread-safe using asyncio locks for subscription management.
    """

    def __init__(self) -> None:
        """Initialize the event stream service."""
        # Maps entity_id -> list of asyncio.Queue for subscribers
        self._document_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._job_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

        # Sequence counter per entity for ordering
        self._sequence_counters: dict[str, int] = defaultdict(int)

        # Lock for thread-safe subscription management
        self._lock = asyncio.Lock()

        # Track connection count for monitoring
        self._total_connections = 0
        self._active_connections = 0

        logger.info("EventStreamService initialized")

    async def subscribe_document(self, document_id: UUID) -> asyncio.Queue:
        """Subscribe to events for a specific document.

        Args:
            document_id: UUID of the document to subscribe to.

        Returns:
            An asyncio.Queue that will receive ProcessingEvent instances.
        """
        queue: asyncio.Queue = asyncio.Queue()
        key = str(document_id)

        async with self._lock:
            self._document_subscribers[key].append(queue)
            self._total_connections += 1
            self._active_connections += 1

        logger.debug(f"New document subscription for {document_id}, active={self._active_connections}")
        return queue

    async def unsubscribe_document(self, document_id: UUID, queue: asyncio.Queue) -> None:
        """Unsubscribe from document events.

        Args:
            document_id: UUID of the document.
            queue: The queue that was returned from subscribe_document.
        """
        key = str(document_id)

        async with self._lock:
            if key in self._document_subscribers:
                try:
                    self._document_subscribers[key].remove(queue)
                    self._active_connections -= 1

                    # Clean up empty subscriber lists
                    if not self._document_subscribers[key]:
                        del self._document_subscribers[key]

                    logger.debug(f"Removed document subscription for {document_id}")
                except ValueError:
                    pass  # Queue not in list

    async def subscribe_job(self, job_id: UUID) -> asyncio.Queue:
        """Subscribe to events for a specific batch job.

        Args:
            job_id: UUID of the job to subscribe to.

        Returns:
            An asyncio.Queue that will receive ProcessingEvent instances.
        """
        queue: asyncio.Queue = asyncio.Queue()
        key = str(job_id)

        async with self._lock:
            self._job_subscribers[key].append(queue)
            self._total_connections += 1
            self._active_connections += 1

        logger.debug(f"New job subscription for {job_id}, active={self._active_connections}")
        return queue

    async def unsubscribe_job(self, job_id: UUID, queue: asyncio.Queue) -> None:
        """Unsubscribe from job events.

        Args:
            job_id: UUID of the job.
            queue: The queue that was returned from subscribe_job.
        """
        key = str(job_id)

        async with self._lock:
            if key in self._job_subscribers:
                try:
                    self._job_subscribers[key].remove(queue)
                    self._active_connections -= 1

                    # Clean up empty subscriber lists
                    if not self._job_subscribers[key]:
                        del self._job_subscribers[key]

                    logger.debug(f"Removed job subscription for {job_id}")
                except ValueError:
                    pass  # Queue not in list

    async def publish_document_event(
        self,
        document_id: UUID,
        event_type: EventType,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event for a document.

        Args:
            document_id: UUID of the document.
            event_type: Type of event to publish.
            data: Optional event-specific data payload.
        """
        key = str(document_id)

        async with self._lock:
            subscribers = self._document_subscribers.get(key, [])
            if not subscribers:
                return  # No subscribers for this document

            # Increment sequence counter
            self._sequence_counters[key] += 1
            sequence = self._sequence_counters[key]

        event = ProcessingEvent(
            event_type=event_type,
            entity_id=document_id,
            entity_type="document",
            data=data or {},
            sequence=sequence,
        )

        # Broadcast to all subscribers
        await self._broadcast(subscribers, event)

        logger.debug(
            f"Published {event_type.value} for document {document_id} "
            f"to {len(subscribers)} subscribers"
        )

    async def publish_job_event(
        self,
        job_id: UUID,
        event_type: EventType,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event for a batch job.

        Args:
            job_id: UUID of the job.
            event_type: Type of event to publish.
            data: Optional event-specific data payload.
        """
        key = str(job_id)

        async with self._lock:
            subscribers = self._job_subscribers.get(key, [])
            if not subscribers:
                return  # No subscribers for this job

            # Increment sequence counter
            self._sequence_counters[key] += 1
            sequence = self._sequence_counters[key]

        event = ProcessingEvent(
            event_type=event_type,
            entity_id=job_id,
            entity_type="job",
            data=data or {},
            sequence=sequence,
        )

        # Broadcast to all subscribers
        await self._broadcast(subscribers, event)

        logger.debug(
            f"Published {event_type.value} for job {job_id} "
            f"to {len(subscribers)} subscribers"
        )

    async def _broadcast(
        self,
        subscribers: list[asyncio.Queue],
        event: ProcessingEvent,
    ) -> None:
        """Broadcast an event to all subscribers.

        Uses non-blocking put to avoid slowing down publishers if a subscriber
        queue is full.

        Args:
            subscribers: List of subscriber queues.
            event: The event to broadcast.
        """
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    f"Subscriber queue full, dropping event {event.event_type.value} "
                    f"for {event.entity_id}"
                )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics for monitoring.

        Returns:
            Dictionary with connection and subscription stats.
        """
        return {
            "total_connections": self._total_connections,
            "active_connections": self._active_connections,
            "document_subscriptions": len(self._document_subscribers),
            "job_subscriptions": len(self._job_subscribers),
            "total_subscribers": sum(
                len(subs) for subs in self._document_subscribers.values()
            ) + sum(len(subs) for subs in self._job_subscribers.values()),
        }

    async def cleanup_stale_subscriptions(self, max_age_seconds: int = 3600) -> int:
        """Clean up stale subscriptions that haven't received events.

        This is a maintenance method that should be called periodically
        to remove abandoned subscriptions.

        Args:
            max_age_seconds: Maximum age in seconds before a subscription
                           is considered stale.

        Returns:
            Number of subscriptions cleaned up.
        """
        # For now, this is a placeholder - in production you'd track
        # last activity time per subscription
        return 0


# Global singleton instance
_event_stream_service: EventStreamService | None = None


def get_event_stream_service() -> EventStreamService:
    """Get or create the global EventStreamService singleton.

    Returns:
        The global EventStreamService instance.
    """
    global _event_stream_service
    if _event_stream_service is None:
        _event_stream_service = EventStreamService()
    return _event_stream_service


def reset_event_stream_service() -> None:
    """Reset the global EventStreamService singleton.

    Useful for testing.
    """
    global _event_stream_service
    _event_stream_service = None


# Convenience functions for publishing events


async def publish_extraction_started(document_id: UUID, total_chars: int = 0) -> None:
    """Publish an extraction_started event.

    Args:
        document_id: UUID of the document.
        total_chars: Total character count of the document.
    """
    service = get_event_stream_service()
    await service.publish_document_event(
        document_id=document_id,
        event_type=EventType.EXTRACTION_STARTED,
        data={"total_chars": total_chars},
    )


async def publish_mention_found(
    document_id: UUID,
    mention_text: str,
    start_offset: int,
    end_offset: int,
    mention_count: int,
    confidence: float = 0.0,
) -> None:
    """Publish a mention_found event.

    Args:
        document_id: UUID of the document.
        mention_text: The extracted mention text.
        start_offset: Character offset where mention starts.
        end_offset: Character offset where mention ends.
        mention_count: Running count of mentions found.
        confidence: Confidence score of the extraction.
    """
    service = get_event_stream_service()
    await service.publish_document_event(
        document_id=document_id,
        event_type=EventType.MENTION_FOUND,
        data={
            "text": mention_text,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "mention_count": mention_count,
            "confidence": confidence,
        },
    )


async def publish_extraction_complete(
    document_id: UUID,
    mention_count: int,
    duration_ms: float = 0.0,
) -> None:
    """Publish an extraction_complete event.

    Args:
        document_id: UUID of the document.
        mention_count: Total number of mentions extracted.
        duration_ms: Time taken for extraction in milliseconds.
    """
    service = get_event_stream_service()
    await service.publish_document_event(
        document_id=document_id,
        event_type=EventType.EXTRACTION_COMPLETE,
        data={
            "mention_count": mention_count,
            "duration_ms": duration_ms,
        },
    )


async def publish_processing_complete(
    document_id: UUID,
    mention_count: int,
    fact_count: int,
    duration_ms: float = 0.0,
) -> None:
    """Publish a processing_complete event.

    Args:
        document_id: UUID of the document.
        mention_count: Total number of mentions extracted.
        fact_count: Total number of clinical facts created.
        duration_ms: Total processing time in milliseconds.
    """
    service = get_event_stream_service()
    await service.publish_document_event(
        document_id=document_id,
        event_type=EventType.PROCESSING_COMPLETE,
        data={
            "mention_count": mention_count,
            "fact_count": fact_count,
            "duration_ms": duration_ms,
        },
    )


async def publish_error(
    document_id: UUID,
    error_message: str,
    error_code: str | None = None,
) -> None:
    """Publish an error event.

    Args:
        document_id: UUID of the document.
        error_message: Human-readable error description.
        error_code: Optional error code for programmatic handling.
    """
    service = get_event_stream_service()
    await service.publish_document_event(
        document_id=document_id,
        event_type=EventType.ERROR,
        data={
            "message": error_message,
            "code": error_code,
        },
    )


async def publish_job_started(
    job_id: UUID,
    total_documents: int,
    job_type: str = "batch",
) -> None:
    """Publish a job_started event.

    Args:
        job_id: UUID of the batch job.
        total_documents: Total number of documents in the batch.
        job_type: Type of job (e.g., "batch", "import").
    """
    service = get_event_stream_service()
    await service.publish_job_event(
        job_id=job_id,
        event_type=EventType.JOB_STARTED,
        data={
            "total_documents": total_documents,
            "job_type": job_type,
        },
    )


async def publish_job_progress(
    job_id: UUID,
    processed_count: int,
    total_count: int,
    current_document_id: UUID | None = None,
) -> None:
    """Publish a job_progress event.

    Args:
        job_id: UUID of the batch job.
        processed_count: Number of documents processed so far.
        total_count: Total number of documents in the batch.
        current_document_id: UUID of the document currently being processed.
    """
    service = get_event_stream_service()
    progress_percent = (processed_count / total_count * 100) if total_count > 0 else 0

    await service.publish_job_event(
        job_id=job_id,
        event_type=EventType.JOB_PROGRESS,
        data={
            "processed_count": processed_count,
            "total_count": total_count,
            "progress_percent": round(progress_percent, 1),
            "current_document_id": str(current_document_id) if current_document_id else None,
        },
    )


async def publish_job_complete(
    job_id: UUID,
    total_documents: int,
    successful_count: int,
    failed_count: int,
    duration_ms: float = 0.0,
) -> None:
    """Publish a job_complete event.

    Args:
        job_id: UUID of the batch job.
        total_documents: Total number of documents in the batch.
        successful_count: Number of documents processed successfully.
        failed_count: Number of documents that failed processing.
        duration_ms: Total job duration in milliseconds.
    """
    service = get_event_stream_service()
    await service.publish_job_event(
        job_id=job_id,
        event_type=EventType.JOB_COMPLETE,
        data={
            "total_documents": total_documents,
            "successful_count": successful_count,
            "failed_count": failed_count,
            "duration_ms": duration_ms,
        },
    )
