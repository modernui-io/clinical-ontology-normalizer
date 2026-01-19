"""WebSocket API endpoints for real-time document processing updates.

Provides WebSocket endpoints for streaming processing events to clients.
Supports document processing, batch job status updates, and general notifications.

Usage:
    ws://localhost:8000/ws - General WebSocket for notifications and subscriptions
    ws://localhost:8000/ws/documents/{document_id}/processing
    ws://localhost:8000/ws/jobs/{job_id}/status
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
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


# Event types for the general WebSocket endpoint
class GeneralEventType:
    """Event types for the general WebSocket endpoint."""
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    NOTIFICATION = "notification"
    CONNECTED = "connected"
    PING = "ping"
    PONG = "pong"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"


class ConnectionManager:
    """Manages WebSocket connections and provides utilities for connection handling.

    This class provides connection lifecycle management, heartbeat support,
    broadcast capabilities, and graceful disconnection handling.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._active_connections: set[WebSocket] = set()
        self._general_connections: set[WebSocket] = set()
        self._job_subscriptions: dict[str, set[WebSocket]] = {}
        self._heartbeat_interval = 30  # seconds

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self._active_connections.add(websocket)
        logger.debug(f"WebSocket connected, active={len(self._active_connections)}")

    async def connect_general(self, websocket: WebSocket) -> None:
        """Accept a general WebSocket connection for broadcasts.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self._active_connections.add(websocket)
        self._general_connections.add(websocket)
        logger.debug(f"General WebSocket connected, active={len(self._general_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self._active_connections.discard(websocket)
        self._general_connections.discard(websocket)
        # Remove from all job subscriptions
        for job_id in list(self._job_subscriptions.keys()):
            self._job_subscriptions[job_id].discard(websocket)
            if not self._job_subscriptions[job_id]:
                del self._job_subscriptions[job_id]
        logger.debug(f"WebSocket disconnected, active={len(self._active_connections)}")

    def subscribe_to_job(self, websocket: WebSocket, job_id: str) -> None:
        """Subscribe a WebSocket to a specific job's updates.

        Args:
            websocket: The WebSocket connection.
            job_id: The job ID to subscribe to.
        """
        if job_id not in self._job_subscriptions:
            self._job_subscriptions[job_id] = set()
        self._job_subscriptions[job_id].add(websocket)
        logger.debug(f"WebSocket subscribed to job {job_id}")

    def unsubscribe_from_job(self, websocket: WebSocket, job_id: str) -> None:
        """Unsubscribe a WebSocket from a specific job's updates.

        Args:
            websocket: The WebSocket connection.
            job_id: The job ID to unsubscribe from.
        """
        if job_id in self._job_subscriptions:
            self._job_subscriptions[job_id].discard(websocket)
            if not self._job_subscriptions[job_id]:
                del self._job_subscriptions[job_id]
        logger.debug(f"WebSocket unsubscribed from job {job_id}")

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

    async def send_json(self, websocket: WebSocket, data: dict[str, Any]) -> bool:
        """Send JSON data to a WebSocket connection.

        Args:
            websocket: The WebSocket to send to.
            data: The data to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            await websocket.send_json(data)
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
            await websocket.send_json({
                "type": GeneralEventType.PING,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            return True
        except Exception:
            return False

    async def broadcast(self, data: dict[str, Any]) -> int:
        """Broadcast a message to all general connections.

        Args:
            data: The data to broadcast.

        Returns:
            Number of connections the message was sent to.
        """
        sent_count = 0
        disconnected = []

        for websocket in self._general_connections:
            if await self.send_json(websocket, data):
                sent_count += 1
            else:
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

        return sent_count

    async def broadcast_to_job(self, job_id: str, data: dict[str, Any]) -> int:
        """Broadcast a message to all connections subscribed to a job.

        Args:
            job_id: The job ID to broadcast to.
            data: The data to broadcast.

        Returns:
            Number of connections the message was sent to.
        """
        if job_id not in self._job_subscriptions:
            return 0

        sent_count = 0
        disconnected = []

        for websocket in self._job_subscriptions[job_id]:
            if await self.send_json(websocket, data):
                sent_count += 1
            else:
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

        return sent_count

    async def send_notification(
        self,
        title: str,
        message: str,
        notification_type: str = "info",
        job_id: str | None = None,
    ) -> int:
        """Send a notification to clients.

        Args:
            title: Notification title.
            message: Notification message.
            notification_type: Type of notification (success, error, info, warning).
            job_id: Optional job ID to scope the notification.

        Returns:
            Number of connections the message was sent to.
        """
        data = {
            "type": GeneralEventType.NOTIFICATION,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "job_id": job_id,
            },
        }

        if job_id:
            return await self.broadcast_to_job(job_id, data)
        return await self.broadcast(data)

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._active_connections)

    @property
    def general_connection_count(self) -> int:
        """Get the number of general connections."""
        return len(self._general_connections)

    def get_job_subscriptions(self) -> dict[str, int]:
        """Get a summary of job subscriptions."""
        return {job_id: len(subs) for job_id, subs in self._job_subscriptions.items()}


# Global connection manager
manager = ConnectionManager()


@router.websocket("")
async def websocket_general(websocket: WebSocket) -> None:
    """General WebSocket endpoint for real-time updates and notifications.

    This endpoint supports:
    - Receiving notifications and broadcasts
    - Subscribing/unsubscribing to specific job updates
    - Ping/pong for connection health

    Client messages:
    - {"type": "ping"} - Request a pong response
    - {"type": "subscribe", "job_id": "uuid"} - Subscribe to job updates
    - {"type": "unsubscribe", "job_id": "uuid"} - Unsubscribe from job updates

    Server messages:
    - {"type": "connected", ...} - Connection established
    - {"type": "ping", ...} - Server heartbeat
    - {"type": "pong", ...} - Response to client ping
    - {"type": "subscribed", "job_id": "uuid"} - Subscription confirmed
    - {"type": "unsubscribed", "job_id": "uuid"} - Unsubscription confirmed
    - {"type": "job_started", ...} - Job started event
    - {"type": "job_progress", ...} - Job progress event
    - {"type": "job_completed", ...} - Job completed event
    - {"type": "job_failed", ...} - Job failed event
    - {"type": "notification", ...} - General notification

    Example client connection (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws');
        ws.onopen = () => {
            ws.send(JSON.stringify({ type: 'subscribe', job_id: '123...' }));
        };
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Event:', data.type, data);
        };
    """
    await manager.connect_general(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": GeneralEventType.CONNECTED,
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Connected to WebSocket server",
        })

        async def receive_client_messages() -> None:
            """Handle messages from the client."""
            while True:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": GeneralEventType.PONG,
                            "timestamp": datetime.now(UTC).isoformat(),
                        })

                    elif msg_type == "subscribe":
                        job_id = message.get("job_id")
                        if job_id:
                            manager.subscribe_to_job(websocket, job_id)
                            await websocket.send_json({
                                "type": GeneralEventType.SUBSCRIBED,
                                "job_id": job_id,
                                "timestamp": datetime.now(UTC).isoformat(),
                            })

                    elif msg_type == "unsubscribe":
                        job_id = message.get("job_id")
                        if job_id:
                            manager.unsubscribe_from_job(websocket, job_id)
                            await websocket.send_json({
                                "type": GeneralEventType.UNSUBSCRIBED,
                                "job_id": job_id,
                                "timestamp": datetime.now(UTC).isoformat(),
                            })

                    elif msg_type == "close":
                        break

                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    logger.debug("Invalid JSON received from client")
                except Exception as e:
                    logger.debug(f"Error receiving client message: {e}")
                    break

        async def send_heartbeats() -> None:
            """Send periodic heartbeats to keep connection alive."""
            while True:
                await asyncio.sleep(manager._heartbeat_interval)
                if not await manager.send_heartbeat(websocket):
                    break

        # Run both tasks concurrently
        client_task = asyncio.create_task(receive_client_messages())
        heartbeat_task = asyncio.create_task(send_heartbeats())

        done, pending = await asyncio.wait(
            [client_task, heartbeat_task],
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
        logger.debug("General WebSocket disconnected")
    except Exception as e:
        logger.exception(f"General WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


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
        "general_connections": manager.general_connection_count,
        "job_subscriptions": manager.get_job_subscriptions(),
        "event_stream_stats": event_service.get_stats(),
    }


# Convenience functions for broadcasting events from anywhere in the application


async def broadcast_job_started(
    job_id: str,
    total_items: int,
    job_type: str = "batch",
) -> int:
    """Broadcast a job_started event to all subscribers.

    Args:
        job_id: The job ID.
        total_items: Total number of items in the job.
        job_type: Type of job.

    Returns:
        Number of connections the message was sent to.
    """
    data = {
        "type": GeneralEventType.JOB_STARTED,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "job_id": job_id,
            "total_items": total_items,
            "job_type": job_type,
        },
    }
    # Broadcast to both job subscribers and all general connections
    job_count = await manager.broadcast_to_job(job_id, data)
    general_count = await manager.broadcast(data)
    return job_count + general_count


async def broadcast_job_progress(
    job_id: str,
    processed_count: int,
    total_count: int,
    current_item: str | None = None,
) -> int:
    """Broadcast a job_progress event to subscribers.

    Args:
        job_id: The job ID.
        processed_count: Number of items processed.
        total_count: Total number of items.
        current_item: Optional current item being processed.

    Returns:
        Number of connections the message was sent to.
    """
    progress_percent = (processed_count / total_count * 100) if total_count > 0 else 0

    data = {
        "type": GeneralEventType.JOB_PROGRESS,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "job_id": job_id,
            "processed_count": processed_count,
            "total_count": total_count,
            "progress_percent": round(progress_percent, 1),
            "current_item": current_item,
        },
    }
    return await manager.broadcast_to_job(job_id, data)


async def broadcast_job_completed(
    job_id: str,
    total_items: int,
    successful_count: int,
    failed_count: int,
    duration_ms: float = 0.0,
) -> int:
    """Broadcast a job_completed event to all subscribers.

    Args:
        job_id: The job ID.
        total_items: Total number of items.
        successful_count: Number of successful items.
        failed_count: Number of failed items.
        duration_ms: Duration in milliseconds.

    Returns:
        Number of connections the message was sent to.
    """
    data = {
        "type": GeneralEventType.JOB_COMPLETED,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "job_id": job_id,
            "total_items": total_items,
            "successful_count": successful_count,
            "failed_count": failed_count,
            "duration_ms": duration_ms,
        },
    }
    job_count = await manager.broadcast_to_job(job_id, data)
    general_count = await manager.broadcast(data)
    return job_count + general_count


async def broadcast_job_failed(
    job_id: str,
    error_message: str,
    error_code: str | None = None,
) -> int:
    """Broadcast a job_failed event to all subscribers.

    Args:
        job_id: The job ID.
        error_message: Error description.
        error_code: Optional error code.

    Returns:
        Number of connections the message was sent to.
    """
    data = {
        "type": GeneralEventType.JOB_FAILED,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "job_id": job_id,
            "error_message": error_message,
            "error_code": error_code,
        },
    }
    job_count = await manager.broadcast_to_job(job_id, data)
    general_count = await manager.broadcast(data)
    return job_count + general_count


async def broadcast_notification(
    title: str,
    message: str,
    notification_type: str = "info",
    job_id: str | None = None,
) -> int:
    """Broadcast a notification to clients.

    Args:
        title: Notification title.
        message: Notification message.
        notification_type: Type (success, error, info, warning).
        job_id: Optional job ID to scope the notification.

    Returns:
        Number of connections the message was sent to.
    """
    return await manager.send_notification(title, message, notification_type, job_id)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance.

    Returns:
        The global ConnectionManager instance.
    """
    return manager
