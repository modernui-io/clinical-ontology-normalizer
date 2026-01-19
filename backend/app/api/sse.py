"""Server-Sent Events (SSE) API endpoints for real-time processing updates.

Provides SSE endpoints for streaming processing events to clients that
prefer SSE over WebSocket. SSE is unidirectional (server to client only)
and works over standard HTTP, making it simpler to use with load balancers
and proxies.

Usage:
    GET /sse/documents/{document_id}/processing
    GET /sse/jobs/{job_id}/status

Benefits of SSE over WebSocket:
- Works with standard HTTP infrastructure
- Automatic reconnection built into browsers
- Simpler protocol (text-based)
- Better compatibility with proxies and load balancers
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.services.event_stream import (
    EventType,
    ProcessingEvent,
    get_event_stream_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["Server-Sent Events"])

# Constants for SSE
SSE_CONTENT_TYPE = "text/event-stream"
SSE_CACHE_CONTROL = "no-cache"
SSE_CONNECTION = "keep-alive"
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_COMMENT = ": heartbeat\n\n"


async def event_generator(
    queue: asyncio.Queue,
    entity_id: UUID,
    entity_type: str,
    request: Request,
    terminal_events: set[EventType],
) -> AsyncGenerator[str, None]:
    """Generate SSE events from a queue.

    This generator yields SSE-formatted messages from the event queue,
    with periodic heartbeat comments to keep the connection alive.

    Args:
        queue: The event queue to read from.
        entity_id: UUID of the entity being monitored.
        entity_type: Type of entity ("document" or "job").
        request: The FastAPI request object for disconnect detection.
        terminal_events: Set of event types that should end the stream.

    Yields:
        SSE-formatted event strings.
    """
    # Send initial connection event
    yield f"event: connected\ndata: {{\"entity_id\": \"{entity_id}\", \"entity_type\": \"{entity_type}\"}}\n\n"

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected for {entity_type} {entity_id}")
                break

            try:
                # Wait for event with timeout for heartbeat
                event: ProcessingEvent = await asyncio.wait_for(
                    queue.get(),
                    timeout=HEARTBEAT_INTERVAL,
                )

                # Yield the event in SSE format
                yield event.to_sse()

                # Check for terminal events
                if event.event_type in terminal_events:
                    # Send a closing event
                    yield f"event: stream_end\ndata: {{\"reason\": \"{event.event_type.value}\"}}\n\n"
                    break

            except asyncio.TimeoutError:
                # Send heartbeat comment to keep connection alive
                # Comments start with : and are ignored by SSE clients
                yield HEARTBEAT_COMMENT

    except asyncio.CancelledError:
        logger.debug(f"SSE stream cancelled for {entity_type} {entity_id}")
    except Exception as e:
        logger.exception(f"SSE stream error for {entity_type} {entity_id}: {e}")
        # Send error event before closing
        yield f"event: error\ndata: {{\"message\": \"Stream error: {str(e)}\"}}\n\n"


@router.get(
    "/documents/{document_id}/processing",
    summary="Stream document processing events",
    description="""
    Stream real-time Server-Sent Events for document processing.

    Events include:
    - **connected**: Initial connection confirmation
    - **extraction_started**: Processing has begun
    - **mention_found**: A clinical mention was extracted
    - **extraction_complete**: All mentions extracted
    - **processing_complete**: Entire pipeline finished
    - **error**: An error occurred

    The stream will automatically close after processing_complete or error events.

    **Example usage (JavaScript):**
    ```javascript
    const evtSource = new EventSource('/sse/documents/123.../processing');

    evtSource.addEventListener('mention_found', (e) => {
        const data = JSON.parse(e.data);
        console.log('Found mention:', data.data.text);
    });

    evtSource.addEventListener('processing_complete', (e) => {
        console.log('Processing complete!');
        evtSource.close();
    });
    ```
    """,
    responses={
        200: {
            "description": "SSE event stream",
            "content": {"text/event-stream": {}},
        },
    },
)
async def sse_document_processing(
    document_id: UUID,
    request: Request,
) -> StreamingResponse:
    """Stream SSE events for document processing.

    Args:
        document_id: UUID of the document to monitor.
        request: The FastAPI request object.

    Returns:
        StreamingResponse with SSE content.
    """
    event_service = get_event_stream_service()

    # Subscribe to document events
    queue = await event_service.subscribe_document(document_id)

    async def cleanup_generator() -> AsyncGenerator[str, None]:
        """Wrapper generator that handles cleanup on completion."""
        try:
            async for event in event_generator(
                queue=queue,
                entity_id=document_id,
                entity_type="document",
                request=request,
                terminal_events={EventType.PROCESSING_COMPLETE, EventType.ERROR},
            ):
                yield event
        finally:
            # Clean up subscription
            await event_service.unsubscribe_document(document_id, queue)
            logger.debug(f"SSE cleanup complete for document {document_id}")

    return StreamingResponse(
        cleanup_generator(),
        media_type=SSE_CONTENT_TYPE,
        headers={
            "Cache-Control": SSE_CACHE_CONTROL,
            "Connection": SSE_CONNECTION,
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get(
    "/jobs/{job_id}/status",
    summary="Stream batch job status events",
    description="""
    Stream real-time Server-Sent Events for batch job status.

    Events include:
    - **connected**: Initial connection confirmation
    - **job_started**: Job processing has begun
    - **job_progress**: Progress update with percentage
    - **job_complete**: Job finished
    - **error**: A critical error occurred

    The stream will automatically close after job_complete or error events.

    **Example usage (JavaScript):**
    ```javascript
    const evtSource = new EventSource('/sse/jobs/123.../status');

    evtSource.addEventListener('job_progress', (e) => {
        const data = JSON.parse(e.data);
        console.log('Progress:', data.data.progress_percent + '%');
    });

    evtSource.addEventListener('job_complete', (e) => {
        console.log('Job complete!');
        evtSource.close();
    });
    ```
    """,
    responses={
        200: {
            "description": "SSE event stream",
            "content": {"text/event-stream": {}},
        },
    },
)
async def sse_job_status(
    job_id: UUID,
    request: Request,
) -> StreamingResponse:
    """Stream SSE events for batch job status.

    Args:
        job_id: UUID of the batch job to monitor.
        request: The FastAPI request object.

    Returns:
        StreamingResponse with SSE content.
    """
    event_service = get_event_stream_service()

    # Subscribe to job events
    queue = await event_service.subscribe_job(job_id)

    async def cleanup_generator() -> AsyncGenerator[str, None]:
        """Wrapper generator that handles cleanup on completion."""
        try:
            async for event in event_generator(
                queue=queue,
                entity_id=job_id,
                entity_type="job",
                request=request,
                terminal_events={EventType.JOB_COMPLETE, EventType.ERROR},
            ):
                yield event
        finally:
            await event_service.unsubscribe_job(job_id, queue)
            logger.debug(f"SSE cleanup complete for job {job_id}")

    return StreamingResponse(
        cleanup_generator(),
        media_type=SSE_CONTENT_TYPE,
        headers={
            "Cache-Control": SSE_CACHE_CONTROL,
            "Connection": SSE_CONNECTION,
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/stats",
    summary="Get SSE connection statistics",
    description="Returns statistics about active SSE connections and subscriptions.",
)
async def get_sse_stats() -> dict:
    """Get SSE connection statistics.

    Returns:
        Dictionary with subscription stats from the event stream service.
    """
    event_service = get_event_stream_service()
    return {
        "event_stream_stats": event_service.get_stats(),
    }
