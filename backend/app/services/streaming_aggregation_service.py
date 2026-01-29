"""Streaming aggregation service.

Provides real-time aggregations:
- Tumbling window patient counts (1min, 5min, 1hr)
- Rolling alert volume metrics
- Real-time data quality error rates
- Throughput and latency tracking
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.kafka_service import (
    KafkaService,
    MessageType,
    StreamingMessage,
    get_kafka_service,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Types and Schemas
# =============================================================================

class WindowType(str, Enum):
    """Types of time windows."""

    TUMBLING_1MIN = "tumbling_1min"
    TUMBLING_5MIN = "tumbling_5min"
    TUMBLING_1HR = "tumbling_1hr"
    SLIDING_5MIN = "sliding_5min"
    SESSION = "session"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(str, Enum):
    """Types of streaming alerts."""

    HIGH_LATENCY = "high_latency"
    HIGH_ERROR_RATE = "high_error_rate"
    CONSUMER_LAG = "consumer_lag"
    SCHEMA_DRIFT = "schema_drift"
    VALIDATION_ERROR = "validation_error"
    THROUGHPUT_DROP = "throughput_drop"
    DEAD_LETTER_SPIKE = "dead_letter_spike"
    CONNECTION_LOST = "connection_lost"


@dataclass
class TimeWindow:
    """A time-based window for aggregations."""

    window_type: WindowType
    start_time: datetime
    end_time: datetime
    count: int = 0
    sum_value: float = 0.0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def avg_value(self) -> float:
        """Get average value in the window."""
        return self.sum_value / self.count if self.count > 0 else 0.0

    def add_value(self, value: float) -> None:
        """Add a value to the window."""
        self.count += 1
        self.sum_value += value
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "window_type": self.window_type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "count": self.count,
            "sum_value": round(self.sum_value, 2),
            "avg_value": round(self.avg_value, 2),
            "min_value": round(self.min_value, 2) if self.min_value != float("inf") else None,
            "max_value": round(self.max_value, 2) if self.max_value != float("-inf") else None,
            "metadata": self.metadata,
        }


@dataclass
class StreamingAlert:
    """An alert from the streaming pipeline."""

    alert_id: str = field(default_factory=lambda: str(uuid4()))
    alert_type: AlertType = AlertType.HIGH_ERROR_RATE
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str = ""
    message: str = ""
    source: str = ""
    metric_value: float | None = None
    threshold_value: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass
class ThroughputMetric:
    """Throughput metric for a time point."""

    timestamp: datetime
    messages_per_second: float
    bytes_per_second: float
    topic: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "messages_per_second": round(self.messages_per_second, 2),
            "bytes_per_second": round(self.bytes_per_second, 2),
            "topic": self.topic,
        }


@dataclass
class LatencyMetric:
    """Latency metric for a time point."""

    timestamp: datetime
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
        }


@dataclass
class DataQualityMetric:
    """Data quality metric for a time window."""

    timestamp: datetime
    total_messages: int
    validation_errors: int
    schema_errors: int
    transformation_errors: int

    @property
    def error_rate(self) -> float:
        """Get overall error rate."""
        total_errors = self.validation_errors + self.schema_errors + self.transformation_errors
        return total_errors / self.total_messages * 100 if self.total_messages > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_messages": self.total_messages,
            "validation_errors": self.validation_errors,
            "schema_errors": self.schema_errors,
            "transformation_errors": self.transformation_errors,
            "error_rate": round(self.error_rate, 2),
        }


@dataclass
class AggregationStats:
    """Overall aggregation statistics."""

    # Throughput
    current_throughput: float = 0.0
    peak_throughput: float = 0.0
    avg_throughput: float = 0.0

    # Latency
    current_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Counts
    total_messages_1min: int = 0
    total_messages_5min: int = 0
    total_messages_1hr: int = 0

    # Errors
    error_rate_1min: float = 0.0
    error_rate_5min: float = 0.0

    # Alerts
    active_alerts: int = 0
    critical_alerts: int = 0

    # Consumer lag
    total_consumer_lag: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_throughput": round(self.current_throughput, 2),
            "peak_throughput": round(self.peak_throughput, 2),
            "avg_throughput": round(self.avg_throughput, 2),
            "current_latency_ms": round(self.current_latency_ms, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "total_messages_1min": self.total_messages_1min,
            "total_messages_5min": self.total_messages_5min,
            "total_messages_1hr": self.total_messages_1hr,
            "error_rate_1min": round(self.error_rate_1min, 2),
            "error_rate_5min": round(self.error_rate_5min, 2),
            "active_alerts": self.active_alerts,
            "critical_alerts": self.critical_alerts,
            "total_consumer_lag": self.total_consumer_lag,
        }


# =============================================================================
# Streaming Aggregation Service
# =============================================================================

class StreamingAggregationService:
    """Service for real-time streaming aggregations.

    Provides:
    - Tumbling window aggregations (1min, 5min, 1hr)
    - Rolling metrics and statistics
    - Alert management
    - Throughput and latency tracking
    """

    # Thresholds for alerts
    LATENCY_THRESHOLD_MS = 500
    ERROR_RATE_THRESHOLD = 5.0  # 5%
    CONSUMER_LAG_THRESHOLD = 10000
    THROUGHPUT_DROP_THRESHOLD = 0.5  # 50% drop

    def __init__(self, kafka_service: KafkaService | None = None) -> None:
        """Initialize the streaming aggregation service.

        Args:
            kafka_service: Kafka service instance. Uses singleton if not provided.
        """
        self._kafka = kafka_service or get_kafka_service()
        self._stats = AggregationStats()

        # Time-based windows
        self._windows_1min: deque[TimeWindow] = deque(maxlen=60)  # 1 hour of 1-min windows
        self._windows_5min: deque[TimeWindow] = deque(maxlen=24)  # 2 hours of 5-min windows
        self._windows_1hr: deque[TimeWindow] = deque(maxlen=24)  # 24 hours of 1-hr windows

        # Metrics history
        self._throughput_history: deque[ThroughputMetric] = deque(maxlen=300)  # 5 min at 1/sec
        self._latency_history: deque[LatencyMetric] = deque(maxlen=300)
        self._quality_history: deque[DataQualityMetric] = deque(maxlen=60)

        # Alerts
        self._alerts: list[StreamingAlert] = []

        # Current window tracking
        self._current_window_1min: TimeWindow | None = None
        self._current_window_5min: TimeWindow | None = None
        self._current_window_1hr: TimeWindow | None = None

        # Running state
        self._is_running = False
        self._aggregation_task: asyncio.Task | None = None
        self._start_time = datetime.now(timezone.utc)

        # Initialize windows
        self._init_windows()

        logger.info("StreamingAggregationService initialized")

    def _init_windows(self) -> None:
        """Initialize time windows."""
        now = datetime.now(timezone.utc)

        # 1-minute window
        window_start = now.replace(second=0, microsecond=0)
        self._current_window_1min = TimeWindow(
            window_type=WindowType.TUMBLING_1MIN,
            start_time=window_start,
            end_time=window_start + timedelta(minutes=1),
        )

        # 5-minute window
        minute = (now.minute // 5) * 5
        window_start = now.replace(minute=minute, second=0, microsecond=0)
        self._current_window_5min = TimeWindow(
            window_type=WindowType.TUMBLING_5MIN,
            start_time=window_start,
            end_time=window_start + timedelta(minutes=5),
        )

        # 1-hour window
        window_start = now.replace(minute=0, second=0, microsecond=0)
        self._current_window_1hr = TimeWindow(
            window_type=WindowType.TUMBLING_1HR,
            start_time=window_start,
            end_time=window_start + timedelta(hours=1),
        )

    async def start(self) -> None:
        """Start the aggregation service."""
        if self._is_running:
            return

        self._is_running = True
        self._start_time = datetime.now(timezone.utc)

        # Start aggregation loop
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())

        # Subscribe to Kafka topics
        self._kafka.subscribe("clinical.hl7v2.inbound", self._handle_message)
        self._kafka.subscribe("clinical.fhir.inbound", self._handle_message)
        self._kafka.subscribe("clinical.omop.outbound", self._handle_message)
        self._kafka.subscribe("clinical.alerts", self._handle_alert_message)

        logger.info("StreamingAggregationService started")

    async def stop(self) -> None:
        """Stop the aggregation service."""
        self._is_running = False

        if self._aggregation_task:
            self._aggregation_task.cancel()
            try:
                await self._aggregation_task
            except asyncio.CancelledError:
                pass
            self._aggregation_task = None

        logger.info("StreamingAggregationService stopped")

    async def _aggregation_loop(self) -> None:
        """Main aggregation loop."""
        import random

        while self._is_running:
            try:
                now = datetime.now(timezone.utc)

                # Check and rotate windows
                self._rotate_windows(now)

                # Update metrics (simulated for mock mode)
                if self._kafka.is_mock_mode():
                    self._generate_mock_metrics(now)

                # Check for alert conditions
                self._check_alert_conditions()

                # Update stats
                self._update_stats()

                await asyncio.sleep(1)  # Update every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(5)

    def _rotate_windows(self, now: datetime) -> None:
        """Rotate time windows if needed."""
        # Check 1-minute window
        if self._current_window_1min and now >= self._current_window_1min.end_time:
            self._windows_1min.append(self._current_window_1min)
            self._current_window_1min = TimeWindow(
                window_type=WindowType.TUMBLING_1MIN,
                start_time=self._current_window_1min.end_time,
                end_time=self._current_window_1min.end_time + timedelta(minutes=1),
            )

        # Check 5-minute window
        if self._current_window_5min and now >= self._current_window_5min.end_time:
            self._windows_5min.append(self._current_window_5min)
            self._current_window_5min = TimeWindow(
                window_type=WindowType.TUMBLING_5MIN,
                start_time=self._current_window_5min.end_time,
                end_time=self._current_window_5min.end_time + timedelta(minutes=5),
            )

        # Check 1-hour window
        if self._current_window_1hr and now >= self._current_window_1hr.end_time:
            self._windows_1hr.append(self._current_window_1hr)
            self._current_window_1hr = TimeWindow(
                window_type=WindowType.TUMBLING_1HR,
                start_time=self._current_window_1hr.end_time,
                end_time=self._current_window_1hr.end_time + timedelta(hours=1),
            )

    def _generate_mock_metrics(self, now: datetime) -> None:
        """Generate mock metrics for development."""
        import random

        # Throughput
        base_throughput = 50 + random.gauss(0, 10)
        throughput = ThroughputMetric(
            timestamp=now,
            messages_per_second=max(0, base_throughput),
            bytes_per_second=max(0, base_throughput * 1024),
            topic="all",
        )
        self._throughput_history.append(throughput)

        # Latency
        base_latency = 20 + random.gauss(0, 5)
        latency = LatencyMetric(
            timestamp=now,
            p50_ms=max(1, base_latency),
            p95_ms=max(1, base_latency * 2),
            p99_ms=max(1, base_latency * 3),
            avg_ms=max(1, base_latency * 1.2),
        )
        self._latency_history.append(latency)

        # Data quality (every minute)
        if now.second == 0:
            quality = DataQualityMetric(
                timestamp=now,
                total_messages=int(base_throughput * 60),
                validation_errors=random.randint(0, 5),
                schema_errors=random.randint(0, 2),
                transformation_errors=random.randint(0, 3),
            )
            self._quality_history.append(quality)

        # Update windows
        if self._current_window_1min:
            self._current_window_1min.count += int(base_throughput)
            self._current_window_1min.add_value(latency.avg_ms)

        if self._current_window_5min:
            self._current_window_5min.count += int(base_throughput)

        if self._current_window_1hr:
            self._current_window_1hr.count += int(base_throughput)

    async def _handle_message(self, message: StreamingMessage) -> None:
        """Handle an incoming message for aggregation.

        Args:
            message: The streaming message.
        """
        now = datetime.now(timezone.utc)

        # Update current windows
        if self._current_window_1min:
            self._current_window_1min.count += 1

        if self._current_window_5min:
            self._current_window_5min.count += 1

        if self._current_window_1hr:
            self._current_window_1hr.count += 1

    async def _handle_alert_message(self, message: StreamingMessage) -> None:
        """Handle an alert message.

        Args:
            message: The alert message.
        """
        alert_data = message.value

        alert = StreamingAlert(
            alert_type=AlertType(alert_data.get("alert_type", "high_error_rate")),
            severity=AlertSeverity(alert_data.get("severity", "warning")),
            title=alert_data.get("title", "Streaming Alert"),
            message=alert_data.get("message", ""),
            source=message.topic,
            metric_value=alert_data.get("metric_value"),
            threshold_value=alert_data.get("threshold_value"),
            metadata=alert_data.get("metadata", {}),
        )

        self._alerts.append(alert)

        # Keep only last 1000 alerts
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

    def _check_alert_conditions(self) -> None:
        """Check for alert conditions and create alerts."""
        import random

        # Check latency
        if self._latency_history:
            latest_latency = self._latency_history[-1]
            if latest_latency.p99_ms > self.LATENCY_THRESHOLD_MS:
                self._create_alert(
                    AlertType.HIGH_LATENCY,
                    AlertSeverity.WARNING,
                    "High Processing Latency",
                    f"P99 latency is {latest_latency.p99_ms:.0f}ms (threshold: {self.LATENCY_THRESHOLD_MS}ms)",
                    latest_latency.p99_ms,
                    self.LATENCY_THRESHOLD_MS,
                )

        # Check error rate
        if self._quality_history:
            latest_quality = self._quality_history[-1]
            if latest_quality.error_rate > self.ERROR_RATE_THRESHOLD:
                self._create_alert(
                    AlertType.HIGH_ERROR_RATE,
                    AlertSeverity.CRITICAL if latest_quality.error_rate > 10 else AlertSeverity.WARNING,
                    "High Error Rate",
                    f"Error rate is {latest_quality.error_rate:.1f}% (threshold: {self.ERROR_RATE_THRESHOLD}%)",
                    latest_quality.error_rate,
                    self.ERROR_RATE_THRESHOLD,
                )

        # Mock: Occasionally generate random alerts for demo
        if random.random() < 0.001:  # ~1 per 1000 seconds
            alert_configs = [
                (AlertType.SCHEMA_DRIFT, AlertSeverity.WARNING, "Schema Drift Detected", "Field 'patient_id' type changed"),
                (AlertType.CONSUMER_LAG, AlertSeverity.INFO, "Consumer Lag Increasing", "Lag is 5000 messages"),
                (AlertType.VALIDATION_ERROR, AlertSeverity.WARNING, "Validation Errors Spike", "10 validation errors in last minute"),
            ]
            config = random.choice(alert_configs)
            self._create_alert(config[0], config[1], config[2], config[3])

    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        metric_value: float | None = None,
        threshold_value: float | None = None,
    ) -> None:
        """Create a new alert if one doesn't already exist.

        Args:
            alert_type: Type of alert.
            severity: Alert severity.
            title: Alert title.
            message: Alert message.
            metric_value: Current metric value.
            threshold_value: Threshold that was exceeded.
        """
        # Check if similar alert already exists and is not acknowledged
        for alert in self._alerts:
            if (
                alert.alert_type == alert_type
                and not alert.acknowledged
                and not alert.resolved
                and (datetime.now(timezone.utc) - alert.created_at).total_seconds() < 300
            ):
                return  # Don't create duplicate

        alert = StreamingAlert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            source="streaming_aggregation",
            metric_value=metric_value,
            threshold_value=threshold_value,
        )

        self._alerts.append(alert)

        # Keep only last 1000 alerts
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

        logger.warning(f"Alert created: [{severity.value}] {title} - {message}")

    def _update_stats(self) -> None:
        """Update aggregation statistics."""
        # Throughput
        if self._throughput_history:
            latest = self._throughput_history[-1]
            self._stats.current_throughput = latest.messages_per_second
            self._stats.peak_throughput = max(
                m.messages_per_second for m in self._throughput_history
            )
            self._stats.avg_throughput = (
                sum(m.messages_per_second for m in self._throughput_history)
                / len(self._throughput_history)
            )

        # Latency
        if self._latency_history:
            latest = self._latency_history[-1]
            self._stats.current_latency_ms = latest.avg_ms
            self._stats.avg_latency_ms = (
                sum(m.avg_ms for m in self._latency_history)
                / len(self._latency_history)
            )
            self._stats.p99_latency_ms = latest.p99_ms

        # Window counts
        if self._current_window_1min:
            self._stats.total_messages_1min = self._current_window_1min.count

        if self._current_window_5min:
            self._stats.total_messages_5min = self._current_window_5min.count

        if self._current_window_1hr:
            self._stats.total_messages_1hr = self._current_window_1hr.count

        # Error rates
        if self._quality_history:
            latest = self._quality_history[-1]
            self._stats.error_rate_1min = latest.error_rate

            if len(self._quality_history) >= 5:
                recent = list(self._quality_history)[-5:]
                total_msgs = sum(q.total_messages for q in recent)
                total_errors = sum(
                    q.validation_errors + q.schema_errors + q.transformation_errors
                    for q in recent
                )
                self._stats.error_rate_5min = (
                    total_errors / total_msgs * 100 if total_msgs > 0 else 0.0
                )

        # Alerts
        active = [a for a in self._alerts if not a.acknowledged and not a.resolved]
        self._stats.active_alerts = len(active)
        self._stats.critical_alerts = len(
            [a for a in active if a.severity == AlertSeverity.CRITICAL]
        )

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: ID of the alert to acknowledge.
            acknowledged_by: User or system acknowledging.

        Returns:
            True if alert was acknowledged.
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now(timezone.utc)
                alert.acknowledged_by = acknowledged_by
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert.

        Args:
            alert_id: ID of the alert to resolve.

        Returns:
            True if alert was resolved.
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                logger.info(f"Alert {alert_id} resolved")
                return True
        return False

    def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        include_acknowledged: bool = False,
        limit: int = 100,
    ) -> list[StreamingAlert]:
        """Get alerts.

        Args:
            severity: Filter by severity.
            include_acknowledged: Include acknowledged alerts.
            limit: Maximum alerts to return.

        Returns:
            List of alerts.
        """
        alerts = self._alerts

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if not include_acknowledged:
            alerts = [a for a in alerts if not a.acknowledged]

        # Sort by created_at descending
        alerts = sorted(alerts, key=lambda a: a.created_at, reverse=True)

        return alerts[:limit]

    def get_throughput_history(self, minutes: int = 5) -> list[ThroughputMetric]:
        """Get throughput history.

        Args:
            minutes: Number of minutes of history.

        Returns:
            List of throughput metrics.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            m for m in self._throughput_history
            if m.timestamp > cutoff
        ]

    def get_latency_history(self, minutes: int = 5) -> list[LatencyMetric]:
        """Get latency history.

        Args:
            minutes: Number of minutes of history.

        Returns:
            List of latency metrics.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            m for m in self._latency_history
            if m.timestamp > cutoff
        ]

    def get_quality_history(self, minutes: int = 60) -> list[DataQualityMetric]:
        """Get data quality history.

        Args:
            minutes: Number of minutes of history.

        Returns:
            List of quality metrics.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            m for m in self._quality_history
            if m.timestamp > cutoff
        ]

    def get_windows(self, window_type: WindowType) -> list[TimeWindow]:
        """Get completed windows of a specific type.

        Args:
            window_type: Type of windows to get.

        Returns:
            List of completed windows.
        """
        if window_type == WindowType.TUMBLING_1MIN:
            return list(self._windows_1min)
        elif window_type == WindowType.TUMBLING_5MIN:
            return list(self._windows_5min)
        elif window_type == WindowType.TUMBLING_1HR:
            return list(self._windows_1hr)
        return []

    def get_stats(self) -> AggregationStats:
        """Get current aggregation statistics.

        Returns:
            Current statistics.
        """
        return self._stats


# =============================================================================
# Singleton Management
# =============================================================================

_streaming_aggregation_service: StreamingAggregationService | None = None
_streaming_aggregation_lock = threading.Lock()


def get_streaming_aggregation_service() -> StreamingAggregationService:
    """Get the singleton StreamingAggregation service instance.

    Returns:
        The StreamingAggregationService singleton.
    """
    global _streaming_aggregation_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _streaming_aggregation_service is None:
        with _streaming_aggregation_lock:
            if _streaming_aggregation_service is None:
                _streaming_aggregation_service = StreamingAggregationService()

    return _streaming_aggregation_service


def reset_streaming_aggregation_service() -> None:
    """Reset the singleton StreamingAggregation service (for testing)."""
    global _streaming_aggregation_service
    with _streaming_aggregation_lock:
        _streaming_aggregation_service = None
