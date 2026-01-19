"""Streaming API endpoints for real-time pipeline monitoring.

Provides endpoints for:
- Kafka connection health
- Topic statistics
- Real-time throughput metrics
- Streaming alerts management
- Processing errors
- WebSocket for real-time event stream
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketState

from app.services.kafka_service import (
    ConnectionHealth,
    KafkaService,
    TopicStats,
    get_kafka_service,
)
from app.services.streaming_aggregation_service import (
    AlertSeverity,
    AggregationStats,
    StreamingAlert,
    WindowType,
    get_streaming_aggregation_service,
)
from app.services.streaming_etl_service import (
    DeadLetterEntry,
    StreamingETLStats,
    get_streaming_etl_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/streaming", tags=["Streaming"])


# =============================================================================
# Request/Response Models
# =============================================================================

class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(description="Overall status: healthy, degraded, or unhealthy")
    kafka: dict[str, Any] = Field(description="Kafka connection health details")
    etl: dict[str, Any] = Field(description="ETL processor health details")
    aggregation: dict[str, Any] = Field(description="Aggregation service health details")
    timestamp: str = Field(description="Timestamp of health check")


class TopicListResponse(BaseModel):
    """Response model for topic list."""

    topics: list[dict[str, Any]] = Field(description="List of topics with statistics")
    total_topics: int = Field(description="Total number of topics")
    mock_mode: bool = Field(description="Whether running in mock mode")


class MetricsResponse(BaseModel):
    """Response model for real-time metrics."""

    throughput: dict[str, Any] = Field(description="Throughput metrics")
    latency: dict[str, Any] = Field(description="Latency metrics")
    quality: dict[str, Any] = Field(description="Data quality metrics")
    windows: dict[str, Any] = Field(description="Window aggregation metrics")
    timestamp: str = Field(description="Timestamp of metrics")


class AlertListResponse(BaseModel):
    """Response model for alerts list."""

    alerts: list[dict[str, Any]] = Field(description="List of alerts")
    total_alerts: int = Field(description="Total alerts matching filter")
    active_alerts: int = Field(description="Number of active (unacknowledged) alerts")
    critical_count: int = Field(description="Number of critical alerts")


class AcknowledgeRequest(BaseModel):
    """Request model for acknowledging an alert."""

    acknowledged_by: str = Field(
        default="user",
        description="User or system acknowledging the alert",
    )


class AcknowledgeResponse(BaseModel):
    """Response model for alert acknowledgement."""

    success: bool = Field(description="Whether acknowledgement was successful")
    alert_id: str = Field(description="ID of the acknowledged alert")
    acknowledged_at: str | None = Field(description="Timestamp of acknowledgement")


class ErrorListResponse(BaseModel):
    """Response model for processing errors."""

    errors: list[dict[str, Any]] = Field(description="List of processing errors")
    total_errors: int = Field(description="Total errors in dead letter queue")
    error_rate: float = Field(description="Current error rate percentage")


# =============================================================================
# Health Endpoint
# =============================================================================

@router.get("/health", response_model=HealthResponse)
async def get_streaming_health() -> HealthResponse:
    """Get Kafka and streaming pipeline health status.

    Returns overall health status including Kafka connection,
    ETL processor, and aggregation service status.

    Returns:
        Health status for all streaming components.
    """
    kafka_service = get_kafka_service()
    etl_service = get_streaming_etl_service()
    aggregation_service = get_streaming_aggregation_service()

    # Get health from each component
    kafka_health = kafka_service.get_health()
    etl_stats = etl_service.get_stats()
    agg_stats = aggregation_service.get_stats()

    # Determine overall status
    if not kafka_health.connected and not kafka_service.is_mock_mode():
        overall_status = "unhealthy"
    elif kafka_service.is_mock_mode():
        overall_status = "degraded"
    elif agg_stats.critical_alerts > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthResponse(
        status=overall_status,
        kafka=kafka_health.to_dict(),
        etl={
            "messages_processed": etl_stats.messages_processed,
            "success_rate": (
                etl_stats.messages_succeeded / etl_stats.messages_processed * 100
                if etl_stats.messages_processed > 0 else 100.0
            ),
            "dead_letter_count": etl_stats.dead_letter_count,
        },
        aggregation={
            "current_throughput": agg_stats.current_throughput,
            "current_latency_ms": agg_stats.current_latency_ms,
            "active_alerts": agg_stats.active_alerts,
        },
        timestamp=datetime.now(UTC).isoformat(),
    )


# =============================================================================
# Topics Endpoint
# =============================================================================

@router.get("/topics", response_model=TopicListResponse)
async def get_topics() -> TopicListResponse:
    """Get list of Kafka topics with statistics.

    Returns all configured topics with their partition counts,
    message statistics, and health status.

    Returns:
        List of topics with statistics.
    """
    kafka_service = get_kafka_service()

    topics = kafka_service.get_topic_stats()
    topic_dicts = [t.to_dict() for t in topics]

    return TopicListResponse(
        topics=topic_dicts,
        total_topics=len(topics),
        mock_mode=kafka_service.is_mock_mode(),
    )


# =============================================================================
# Metrics Endpoint
# =============================================================================

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    minutes: int = Query(default=5, ge=1, le=60, description="Minutes of history to return"),
) -> MetricsResponse:
    """Get real-time throughput and latency metrics.

    Returns current and historical metrics for throughput,
    latency, and data quality.

    Args:
        minutes: Number of minutes of history to return.

    Returns:
        Real-time metrics.
    """
    aggregation_service = get_streaming_aggregation_service()
    etl_service = get_streaming_etl_service()

    # Get metrics history
    throughput_history = aggregation_service.get_throughput_history(minutes)
    latency_history = aggregation_service.get_latency_history(minutes)
    quality_history = aggregation_service.get_quality_history(minutes)

    # Get stats
    agg_stats = aggregation_service.get_stats()
    etl_stats = etl_service.get_stats()

    return MetricsResponse(
        throughput={
            "current": agg_stats.current_throughput,
            "peak": agg_stats.peak_throughput,
            "average": agg_stats.avg_throughput,
            "history": [t.to_dict() for t in throughput_history],
        },
        latency={
            "current_ms": agg_stats.current_latency_ms,
            "average_ms": agg_stats.avg_latency_ms,
            "p99_ms": agg_stats.p99_latency_ms,
            "history": [l.to_dict() for l in latency_history],
        },
        quality={
            "error_rate_1min": agg_stats.error_rate_1min,
            "error_rate_5min": agg_stats.error_rate_5min,
            "dead_letter_count": etl_stats.dead_letter_count,
            "history": [q.to_dict() for q in quality_history],
        },
        windows={
            "messages_1min": agg_stats.total_messages_1min,
            "messages_5min": agg_stats.total_messages_5min,
            "messages_1hr": agg_stats.total_messages_1hr,
        },
        timestamp=datetime.now(UTC).isoformat(),
    )


# =============================================================================
# Alerts Endpoints
# =============================================================================

@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    severity: AlertSeverity | None = Query(default=None, description="Filter by severity"),
    include_acknowledged: bool = Query(default=False, description="Include acknowledged alerts"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum alerts to return"),
) -> AlertListResponse:
    """Get recent streaming alerts.

    Returns alerts from the streaming pipeline, optionally filtered
    by severity and acknowledgement status.

    Args:
        severity: Filter by alert severity.
        include_acknowledged: Include acknowledged alerts.
        limit: Maximum alerts to return.

    Returns:
        List of streaming alerts.
    """
    aggregation_service = get_streaming_aggregation_service()

    alerts = aggregation_service.get_alerts(
        severity=severity,
        include_acknowledged=include_acknowledged,
        limit=limit,
    )

    # Count active and critical
    active_alerts = [a for a in alerts if not a.acknowledged and not a.resolved]
    critical_count = len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL])

    return AlertListResponse(
        alerts=[a.to_dict() for a in alerts],
        total_alerts=len(alerts),
        active_alerts=len(active_alerts),
        critical_count=critical_count,
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeRequest,
) -> AcknowledgeResponse:
    """Acknowledge a streaming alert.

    Marks an alert as acknowledged, removing it from active alerts.

    Args:
        alert_id: ID of the alert to acknowledge.
        request: Acknowledgement details.

    Returns:
        Acknowledgement result.

    Raises:
        HTTPException: If alert not found.
    """
    aggregation_service = get_streaming_aggregation_service()

    success = aggregation_service.acknowledge_alert(
        alert_id=alert_id,
        acknowledged_by=request.acknowledged_by,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    return AcknowledgeResponse(
        success=True,
        alert_id=alert_id,
        acknowledged_at=datetime.now(UTC).isoformat(),
    )


# =============================================================================
# Errors Endpoint
# =============================================================================

@router.get("/errors", response_model=ErrorListResponse)
async def get_errors(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum errors to return"),
) -> ErrorListResponse:
    """Get recent processing errors.

    Returns errors from the dead letter queue with details
    about the original message and failure reason.

    Args:
        limit: Maximum errors to return.

    Returns:
        List of processing errors.
    """
    etl_service = get_streaming_etl_service()
    aggregation_service = get_streaming_aggregation_service()

    dlq_entries = etl_service.get_dead_letter_queue(limit)
    etl_stats = etl_service.get_stats()
    agg_stats = aggregation_service.get_stats()

    return ErrorListResponse(
        errors=[e.to_dict() for e in dlq_entries],
        total_errors=etl_stats.dead_letter_count,
        error_rate=agg_stats.error_rate_1min,
    )


@router.post("/errors/{entry_id}/retry")
async def retry_error(entry_id: str) -> dict[str, Any]:
    """Retry a failed message from the dead letter queue.

    Attempts to reprocess a message that previously failed.

    Args:
        entry_id: ID of the DLQ entry to retry.

    Returns:
        Retry result.

    Raises:
        HTTPException: If entry not found or cannot be retried.
    """
    etl_service = get_streaming_etl_service()

    success = await etl_service.retry_dead_letter(entry_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not retry entry {entry_id}. Entry may not exist or max retries exceeded.",
        )

    return {
        "success": True,
        "entry_id": entry_id,
        "message": "Retry initiated",
    }


# =============================================================================
# WebSocket Endpoint
# =============================================================================

class StreamingWebSocketManager:
    """Manager for streaming WebSocket connections."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._broadcast_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.debug(f"Streaming WebSocket connected, total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self._connections.discard(websocket)
        logger.debug(f"Streaming WebSocket disconnected, total: {len(self._connections)}")

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast data to all connections."""
        disconnected = []

        for websocket in self._connections:
            if websocket.client_state != WebSocketState.CONNECTED:
                disconnected.append(websocket)
                continue

            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)


# Global WebSocket manager
streaming_ws_manager = StreamingWebSocketManager()


@router.websocket("/ws")
async def websocket_streaming(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time streaming events.

    Streams real-time metrics, alerts, and events to connected clients.
    Sends updates every second with current pipeline status.

    Client messages:
    - {"type": "ping"} - Request a pong response
    - {"type": "subscribe", "channels": ["metrics", "alerts"]} - Subscribe to channels

    Server messages:
    - {"type": "connected", ...} - Connection established
    - {"type": "metrics", ...} - Metrics update
    - {"type": "alert", ...} - New alert
    - {"type": "error", ...} - Processing error
    - {"type": "ping"} - Server heartbeat
    - {"type": "pong"} - Response to client ping
    """
    await streaming_ws_manager.connect(websocket)

    aggregation_service = get_streaming_aggregation_service()
    etl_service = get_streaming_etl_service()
    kafka_service = get_kafka_service()

    # Subscribed channels (default to all)
    subscribed_channels = {"metrics", "alerts", "errors", "topics"}

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Connected to streaming WebSocket",
            "mock_mode": kafka_service.is_mock_mode(),
        })

        async def send_updates() -> None:
            """Send periodic updates to the client."""
            last_alert_count = 0

            while True:
                try:
                    now = datetime.now(UTC)

                    # Send metrics update
                    if "metrics" in subscribed_channels:
                        agg_stats = aggregation_service.get_stats()
                        etl_stats = etl_service.get_stats()

                        await websocket.send_json({
                            "type": "metrics",
                            "timestamp": now.isoformat(),
                            "data": {
                                "throughput": agg_stats.current_throughput,
                                "latency_ms": agg_stats.current_latency_ms,
                                "error_rate": agg_stats.error_rate_1min,
                                "messages_processed": etl_stats.messages_processed,
                                "active_alerts": agg_stats.active_alerts,
                            },
                        })

                    # Check for new alerts
                    if "alerts" in subscribed_channels:
                        alerts = aggregation_service.get_alerts(
                            include_acknowledged=False,
                            limit=10,
                        )

                        if len(alerts) > last_alert_count:
                            # Send new alerts
                            new_alerts = alerts[:len(alerts) - last_alert_count]
                            for alert in new_alerts:
                                await websocket.send_json({
                                    "type": "alert",
                                    "timestamp": now.isoformat(),
                                    "data": alert.to_dict(),
                                })

                        last_alert_count = len(alerts)

                    await asyncio.sleep(1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error sending WebSocket update: {e}")
                    break

        async def receive_messages() -> None:
            """Handle messages from the client."""
            nonlocal subscribed_channels

            while True:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(UTC).isoformat(),
                        })

                    elif msg_type == "subscribe":
                        channels = message.get("channels", [])
                        if channels:
                            subscribed_channels = set(channels)
                            await websocket.send_json({
                                "type": "subscribed",
                                "channels": list(subscribed_channels),
                            })

                    elif msg_type == "close":
                        break

                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    logger.debug("Invalid JSON received from WebSocket client")
                except Exception as e:
                    logger.debug(f"Error receiving WebSocket message: {e}")
                    break

        # Run both tasks concurrently
        update_task = asyncio.create_task(send_updates())
        receive_task = asyncio.create_task(receive_messages())

        done, pending = await asyncio.wait(
            [update_task, receive_task],
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
        logger.debug("Streaming WebSocket disconnected")
    except Exception as e:
        logger.exception(f"Streaming WebSocket error: {e}")
    finally:
        streaming_ws_manager.disconnect(websocket)


# =============================================================================
# Stats Endpoint
# =============================================================================

@router.get("/stats")
async def get_streaming_stats() -> dict[str, Any]:
    """Get comprehensive streaming statistics.

    Returns detailed statistics from all streaming components
    including Kafka, ETL processor, and aggregation service.

    Returns:
        Complete streaming statistics.
    """
    kafka_service = get_kafka_service()
    etl_service = get_streaming_etl_service()
    aggregation_service = get_streaming_aggregation_service()

    return {
        "kafka": kafka_service.get_stats(),
        "etl": etl_service.get_stats().to_dict(),
        "aggregation": aggregation_service.get_stats().to_dict(),
        "websocket_connections": streaming_ws_manager.connection_count,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Startup Hook
# =============================================================================

async def start_streaming_services() -> None:
    """Start all streaming services.

    Called during application startup to initialize
    Kafka connections and start background processors.
    """
    kafka_service = get_kafka_service()
    etl_service = get_streaming_etl_service()
    aggregation_service = get_streaming_aggregation_service()

    # Connect to Kafka (will use mock mode if unavailable)
    await kafka_service.connect()

    # Start services
    await etl_service.start()
    await aggregation_service.start()

    logger.info("Streaming services started")


async def stop_streaming_services() -> None:
    """Stop all streaming services.

    Called during application shutdown to cleanly
    close connections and stop processors.
    """
    kafka_service = get_kafka_service()
    etl_service = get_streaming_etl_service()
    aggregation_service = get_streaming_aggregation_service()

    # Stop services
    await aggregation_service.stop()
    await etl_service.stop()

    # Disconnect from Kafka
    await kafka_service.disconnect()

    logger.info("Streaming services stopped")
