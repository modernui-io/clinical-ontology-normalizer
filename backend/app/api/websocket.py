"""WebSocket API endpoints for real-time document processing updates.

Provides WebSocket endpoints for streaming processing events to clients.
Supports document processing and batch job status updates.

Usage:
    ws://localhost:8000/ws/documents/{document_id}/processing
    ws://localhost:8000/ws/jobs/{job_id}/status
"""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from app.services.event_stream import (
    EventType,
    ProcessingEvent,
    get_event_stream_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections and provides utilities for connection handling.

    This class provides connection lifecycle management, heartbeat support,
    and graceful disconnection handling.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._active_connections: set[WebSocket] = set()
        self._heartbeat_interval = 30  # seconds

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self._active_connections.add(websocket)
        logger.debug(f"WebSocket connected, active={len(self._active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self._active_connections.discard(websocket)
        logger.debug(f"WebSocket disconnected, active={len(self._active_connections)}")

    async def send_event(self, websocket: WebSocket, event: ProcessingEvent) -> bool:
        """Send an event to a WebSocket connection.

        Args:
            websocket: The WebSocket to send to.
            event: The event to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            await websocket.send_json(event.to_dict())
            return True
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            return False

    async def send_heartbeat(self, websocket: WebSocket) -> bool:
        """Send a heartbeat ping to keep connection alive.

        Args:
            websocket: The WebSocket to ping.

        Returns:
            True if ping sent successfully, False otherwise.
        """
        if websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            await websocket.send_json({"type": "ping", "timestamp": None})
            return True
        except Exception:
            return False

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._active_connections)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/documents/{document_id}/processing")
async def websocket_document_processing(
    websocket: WebSocket,
    document_id: UUID,
) -> None:
    """WebSocket endpoint for streaming document processing updates.

    Streams real-time events as the document is processed, including:
    - extraction_started: Processing has begun
    - mention_found: A clinical mention was extracted (multiple events)
    - extraction_complete: All mentions extracted
    - processing_complete: Entire pipeline finished
    - error: An error occurred

    Args:
        websocket: The WebSocket connection.
        document_id: UUID of the document to monitor.

    Example client connection (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws/documents/123e4567-e89b.../processing');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Event:', data.event, data.data);
        };
    """
    await manager.connect(websocket)
    event_service = get_event_stream_service()

    # Subscribe to document events
    queue = await event_service.subscribe_document(document_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "document_id": str(document_id),
            "message": "Subscribed to document processing events",
        })

        # Create tasks for receiving from queue and handling client messages
        async def receive_events() -> None:
            """Receive events from the queue and send to WebSocket."""
            while True:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=manager._heartbeat_interval,
                    )
                    if not await manager.send_event(websocket, event):
                        break

                    # Check for terminal events
                    if event.event_type in (
                        EventType.PROCESSING_COMPLETE,
                        EventType.ERROR,
                    ):
                        # Send close notification and exit
                        await websocket.send_json({
                            "type": "closing",
                            "reason": f"Processing {event.event_type.value}",
                        })
                        break

                except asyncio.TimeoutError:
                    # Send heartbeat
                    if not await manager.send_heartbeat(websocket):
                        break

        async def receive_client_messages() -> None:
            """Handle messages from the client (pings, close requests)."""
            while True:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == "close":
                        break

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.debug(f"Error receiving client message: {e}")
                    break

        # Run both tasks concurrently
        event_task = asyncio.create_task(receive_events())
        client_task = asyncio.create_task(receive_client_messages())

        # Wait for either task to complete (or fail)
        done, pending = await asyncio.wait(
            [event_task, client_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for document {document_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for document {document_id}: {e}")
    finally:
        # Clean up
        await event_service.unsubscribe_document(document_id, queue)
        manager.disconnect(websocket)


@router.websocket("/jobs/{job_id}/status")
async def websocket_job_status(
    websocket: WebSocket,
    job_id: UUID,
) -> None:
    """WebSocket endpoint for streaming batch job status updates.

    Streams real-time events as the batch job progresses, including:
    - job_started: Job processing has begun
    - job_progress: Progress update with count and percentage
    - job_complete: Job finished (success or with failures)
    - error: A critical error occurred

    Args:
        websocket: The WebSocket connection.
        job_id: UUID of the batch job to monitor.

    Example client connection (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws/jobs/123e4567-e89b.../status');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.event === 'job_progress') {
                console.log('Progress:', data.data.progress_percent + '%');
            }
        };
    """
    await manager.connect(websocket)
    event_service = get_event_stream_service()

    # Subscribe to job events
    queue = await event_service.subscribe_job(job_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "job_id": str(job_id),
            "message": "Subscribed to job status events",
        })

        async def receive_events() -> None:
            """Receive events from the queue and send to WebSocket."""
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=manager._heartbeat_interval,
                    )
                    if not await manager.send_event(websocket, event):
                        break

                    # Check for terminal events
                    if event.event_type in (
                        EventType.JOB_COMPLETE,
                        EventType.ERROR,
                    ):
                        await websocket.send_json({
                            "type": "closing",
                            "reason": f"Job {event.event_type.value}",
                        })
                        break

                except asyncio.TimeoutError:
                    if not await manager.send_heartbeat(websocket):
                        break

        async def receive_client_messages() -> None:
            """Handle messages from the client."""
            while True:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == "close":
                        break

                except WebSocketDisconnect:
                    break
                except Exception:
                    break

        event_task = asyncio.create_task(receive_events())
        client_task = asyncio.create_task(receive_client_messages())

        done, pending = await asyncio.wait(
            [event_task, client_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for job {job_id}: {e}")
    finally:
        await event_service.unsubscribe_job(job_id, queue)
        manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats() -> dict:
    """Get WebSocket connection statistics.

    Returns:
        Dictionary with connection stats.
    """
    event_service = get_event_stream_service()
    return {
        "websocket_connections": manager.connection_count,
        "event_stream_stats": event_service.get_stats(),
    }
