"""Kafka integration service for real-time streaming.

Provides producer/consumer management, topic configuration,
message serialization, and connection health monitoring.

When Kafka is unavailable, this service provides mock data
for development and testing purposes.
"""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class KafkaConfig(BaseModel):
    """Kafka configuration settings."""

    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers (comma-separated)",
    )
    client_id: str = Field(
        default="clinical-ontology-normalizer",
        description="Client identifier for Kafka connections",
    )
    consumer_group: str = Field(
        default="con-streaming-group",
        description="Default consumer group",
    )
    auto_offset_reset: str = Field(
        default="earliest",
        description="Auto offset reset policy",
    )
    enable_auto_commit: bool = Field(
        default=True,
        description="Enable auto commit for consumers",
    )
    session_timeout_ms: int = Field(
        default=30000,
        description="Session timeout in milliseconds",
    )
    heartbeat_interval_ms: int = Field(
        default=10000,
        description="Heartbeat interval in milliseconds",
    )
    max_poll_records: int = Field(
        default=500,
        description="Maximum records per poll",
    )


# =============================================================================
# Message Types and Schemas
# =============================================================================

class MessageType(str, Enum):
    """Types of streaming messages."""

    HL7V2_MESSAGE = "hl7v2_message"
    FHIR_RESOURCE = "fhir_resource"
    CLINICAL_DOCUMENT = "clinical_document"
    OMOP_RECORD = "omop_record"
    ALERT = "alert"
    METRIC = "metric"
    DEAD_LETTER = "dead_letter"


class TopicConfig(BaseModel):
    """Kafka topic configuration."""

    name: str
    partitions: int = 3
    replication_factor: int = 1
    retention_ms: int = 604800000  # 7 days
    cleanup_policy: str = "delete"


@dataclass
class StreamingMessage:
    """A message in the streaming pipeline."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    message_type: MessageType = MessageType.CLINICAL_DOCUMENT
    topic: str = ""
    key: str | None = None
    value: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    partition: int | None = None
    offset: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "topic": self.topic,
            "key": self.key,
            "value": self.value,
            "headers": self.headers,
            "timestamp": self.timestamp.isoformat(),
            "partition": self.partition,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamingMessage":
        """Create from dictionary."""
        return cls(
            message_id=data.get("message_id", str(uuid4())),
            message_type=MessageType(data.get("message_type", "clinical_document")),
            topic=data.get("topic", ""),
            key=data.get("key"),
            value=data.get("value", {}),
            headers=data.get("headers", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(UTC),
            partition=data.get("partition"),
            offset=data.get("offset"),
        )


@dataclass
class TopicStats:
    """Statistics for a Kafka topic."""

    name: str
    partitions: int = 0
    total_messages: int = 0
    messages_per_second: float = 0.0
    consumer_lag: int = 0
    last_message_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "partitions": self.partitions,
            "total_messages": self.total_messages,
            "messages_per_second": round(self.messages_per_second, 2),
            "consumer_lag": self.consumer_lag,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
        }


@dataclass
class ConnectionHealth:
    """Kafka connection health status."""

    connected: bool = False
    broker_count: int = 0
    topic_count: int = 0
    last_check: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connected": self.connected,
            "broker_count": self.broker_count,
            "topic_count": self.topic_count,
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message,
            "latency_ms": round(self.latency_ms, 2),
        }


# =============================================================================
# Kafka Service
# =============================================================================

class KafkaService:
    """Service for Kafka integration.

    Provides producer/consumer management, topic operations,
    and connection health monitoring.

    When Kafka is unavailable, this service operates in mock mode
    with simulated data for development and testing.
    """

    # Default topics for the clinical ontology normalizer
    DEFAULT_TOPICS: list[TopicConfig] = [
        TopicConfig(name="clinical.hl7v2.inbound", partitions=6, retention_ms=86400000),
        TopicConfig(name="clinical.fhir.inbound", partitions=6, retention_ms=86400000),
        TopicConfig(name="clinical.documents.processed", partitions=3, retention_ms=604800000),
        TopicConfig(name="clinical.omop.outbound", partitions=3, retention_ms=604800000),
        TopicConfig(name="clinical.alerts", partitions=1, retention_ms=604800000),
        TopicConfig(name="clinical.metrics", partitions=1, retention_ms=86400000),
        TopicConfig(name="clinical.dlq", partitions=1, retention_ms=2592000000),  # 30 days
    ]

    def __init__(self, config: KafkaConfig | None = None) -> None:
        """Initialize the Kafka service.

        Args:
            config: Kafka configuration. Uses defaults if not provided.
        """
        self._config = config or KafkaConfig()
        self._producer = None
        self._consumers: dict[str, Any] = {}
        self._is_connected = False
        self._mock_mode = False
        self._message_handlers: dict[str, list[Callable]] = {}
        self._mock_messages: list[StreamingMessage] = []
        self._mock_task: asyncio.Task | None = None
        self._stats: dict[str, TopicStats] = {}

        # Initialize topic stats
        for topic_config in self.DEFAULT_TOPICS:
            self._stats[topic_config.name] = TopicStats(
                name=topic_config.name,
                partitions=topic_config.partitions,
            )

        logger.info(
            f"KafkaService initialized with bootstrap servers: {self._config.bootstrap_servers}"
        )

    async def connect(self) -> bool:
        """Connect to Kafka brokers.

        Returns:
            True if connected successfully, False if in mock mode.
        """
        try:
            # Try to import kafka-python
            from kafka import KafkaProducer, KafkaAdminClient
            from kafka.errors import NoBrokersAvailable

            # Try to connect
            self._producer = KafkaProducer(
                bootstrap_servers=self._config.bootstrap_servers.split(","),
                client_id=self._config.client_id,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )

            # Get cluster metadata
            admin = KafkaAdminClient(
                bootstrap_servers=self._config.bootstrap_servers.split(","),
            )
            cluster_metadata = admin.describe_cluster()

            self._is_connected = True
            self._mock_mode = False

            logger.info(
                f"Connected to Kafka cluster with {len(cluster_metadata)} brokers"
            )
            return True

        except ImportError:
            logger.warning("kafka-python not installed, using mock mode")
            self._mock_mode = True
            self._is_connected = False
            await self._start_mock_producer()
            return False

        except Exception as e:
            logger.warning(f"Failed to connect to Kafka: {e}, using mock mode")
            self._mock_mode = True
            self._is_connected = False
            await self._start_mock_producer()
            return False

    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        if self._producer:
            self._producer.close()
            self._producer = None

        for consumer in self._consumers.values():
            consumer.close()
        self._consumers.clear()

        if self._mock_task:
            self._mock_task.cancel()
            try:
                await self._mock_task
            except asyncio.CancelledError:
                pass
            self._mock_task = None

        self._is_connected = False
        logger.info("Disconnected from Kafka")

    async def _start_mock_producer(self) -> None:
        """Start mock message producer for development."""
        if self._mock_task is not None:
            return

        self._mock_task = asyncio.create_task(self._mock_message_loop())
        logger.info("Started mock Kafka producer")

    async def _mock_message_loop(self) -> None:
        """Generate mock messages periodically."""
        import random

        message_templates = [
            {
                "type": MessageType.HL7V2_MESSAGE,
                "topic": "clinical.hl7v2.inbound",
                "value": {
                    "message_type": "ADT^A01",
                    "patient_id": "P{:05d}",
                    "event": "admission",
                    "facility": "Main Hospital",
                },
            },
            {
                "type": MessageType.FHIR_RESOURCE,
                "topic": "clinical.fhir.inbound",
                "value": {
                    "resourceType": "Patient",
                    "id": "fhir-{:05d}",
                    "active": True,
                },
            },
            {
                "type": MessageType.OMOP_RECORD,
                "topic": "clinical.omop.outbound",
                "value": {
                    "table": "person",
                    "person_id": "{:05d}",
                    "operation": "insert",
                },
            },
            {
                "type": MessageType.ALERT,
                "topic": "clinical.alerts",
                "value": {
                    "severity": random.choice(["critical", "warning", "info"]),
                    "alert_type": random.choice(["drug_interaction", "validation_error", "system_alert"]),
                    "message": "Sample alert message",
                },
            },
        ]

        counter = 0
        while True:
            try:
                await asyncio.sleep(random.uniform(0.5, 2.0))

                template = random.choice(message_templates)
                counter += 1

                # Format value with counter
                value = {}
                for k, v in template["value"].items():
                    if isinstance(v, str) and "{" in v:
                        value[k] = v.format(counter)
                    else:
                        value[k] = v

                message = StreamingMessage(
                    message_type=template["type"],
                    topic=template["topic"],
                    key=f"key-{counter}",
                    value=value,
                    partition=random.randint(0, 2),
                    offset=counter,
                )

                self._mock_messages.append(message)

                # Keep only last 1000 messages
                if len(self._mock_messages) > 1000:
                    self._mock_messages = self._mock_messages[-1000:]

                # Update stats
                topic = template["topic"]
                if topic in self._stats:
                    self._stats[topic].total_messages += 1
                    self._stats[topic].last_message_time = datetime.now(UTC)
                    self._stats[topic].messages_per_second = random.uniform(10, 100)

                # Notify handlers
                if topic in self._message_handlers:
                    for handler in self._message_handlers[topic]:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(message)
                            else:
                                handler(message)
                        except Exception as e:
                            logger.error(f"Error in message handler: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in mock message loop: {e}")
                await asyncio.sleep(5)

    async def send_message(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> StreamingMessage:
        """Send a message to a Kafka topic.

        Args:
            topic: Target topic name.
            value: Message value (will be JSON serialized).
            key: Optional message key.
            headers: Optional message headers.

        Returns:
            The sent message with metadata.
        """
        message = StreamingMessage(
            topic=topic,
            key=key,
            value=value,
            headers=headers or {},
        )

        if self._mock_mode:
            # Add to mock messages
            message.partition = 0
            message.offset = len(self._mock_messages)
            self._mock_messages.append(message)

            # Update stats
            if topic in self._stats:
                self._stats[topic].total_messages += 1
                self._stats[topic].last_message_time = datetime.now(UTC)

            return message

        if not self._producer:
            raise RuntimeError("Kafka producer not initialized")

        # Send message
        future = self._producer.send(
            topic,
            value=value,
            key=key,
            headers=[(k, v.encode("utf-8")) for k, v in (headers or {}).items()],
        )

        # Wait for acknowledgement
        record_metadata = future.get(timeout=10)

        message.partition = record_metadata.partition
        message.offset = record_metadata.offset

        return message

    def subscribe(
        self,
        topic: str,
        handler: Callable[[StreamingMessage], Any],
        consumer_group: str | None = None,
    ) -> str:
        """Subscribe to a Kafka topic.

        Args:
            topic: Topic to subscribe to.
            handler: Callback function for messages.
            consumer_group: Optional consumer group name.

        Returns:
            Subscription ID.
        """
        subscription_id = str(uuid4())

        if topic not in self._message_handlers:
            self._message_handlers[topic] = []

        self._message_handlers[topic].append(handler)

        logger.info(f"Subscribed to topic '{topic}' with subscription {subscription_id}")
        return subscription_id

    def unsubscribe(self, topic: str, handler: Callable) -> None:
        """Unsubscribe from a Kafka topic.

        Args:
            topic: Topic to unsubscribe from.
            handler: Handler function to remove.
        """
        if topic in self._message_handlers:
            self._message_handlers[topic] = [
                h for h in self._message_handlers[topic] if h != handler
            ]

    async def create_topic(self, config: TopicConfig) -> bool:
        """Create a Kafka topic.

        Args:
            config: Topic configuration.

        Returns:
            True if created successfully.
        """
        if self._mock_mode:
            # Add to stats
            self._stats[config.name] = TopicStats(
                name=config.name,
                partitions=config.partitions,
            )
            return True

        try:
            from kafka.admin import KafkaAdminClient, NewTopic

            admin = KafkaAdminClient(
                bootstrap_servers=self._config.bootstrap_servers.split(","),
            )

            topic = NewTopic(
                name=config.name,
                num_partitions=config.partitions,
                replication_factor=config.replication_factor,
            )

            admin.create_topics([topic])

            self._stats[config.name] = TopicStats(
                name=config.name,
                partitions=config.partitions,
            )

            logger.info(f"Created topic '{config.name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to create topic '{config.name}': {e}")
            return False

    def get_health(self) -> ConnectionHealth:
        """Get Kafka connection health.

        Returns:
            Connection health status.
        """
        return ConnectionHealth(
            connected=self._is_connected or self._mock_mode,
            broker_count=1 if self._mock_mode else (3 if self._is_connected else 0),
            topic_count=len(self._stats),
            last_check=datetime.now(UTC),
            error_message="Using mock mode - Kafka not available" if self._mock_mode else None,
            latency_ms=5.0 if self._mock_mode else 0.0,
        )

    def get_topic_stats(self) -> list[TopicStats]:
        """Get statistics for all topics.

        Returns:
            List of topic statistics.
        """
        return list(self._stats.values())

    def get_recent_messages(
        self,
        topic: str | None = None,
        limit: int = 100,
    ) -> list[StreamingMessage]:
        """Get recent messages (mock mode only).

        Args:
            topic: Optional topic filter.
            limit: Maximum messages to return.

        Returns:
            List of recent messages.
        """
        messages = self._mock_messages

        if topic:
            messages = [m for m in messages if m.topic == topic]

        return messages[-limit:]

    def is_mock_mode(self) -> bool:
        """Check if running in mock mode.

        Returns:
            True if in mock mode.
        """
        return self._mock_mode

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats.
        """
        return {
            "connected": self._is_connected,
            "mock_mode": self._mock_mode,
            "topic_count": len(self._stats),
            "message_handlers": {
                topic: len(handlers)
                for topic, handlers in self._message_handlers.items()
            },
            "mock_message_count": len(self._mock_messages) if self._mock_mode else 0,
        }


# =============================================================================
# Singleton Management
# =============================================================================

_kafka_service: KafkaService | None = None
_kafka_lock = threading.Lock()


def get_kafka_service() -> KafkaService:
    """Get the singleton Kafka service instance.

    Returns:
        The KafkaService singleton.
    """
    global _kafka_service

    # VP-ThreadSafety: Double-checked locking for thread safety
    if _kafka_service is None:
        with _kafka_lock:
            if _kafka_service is None:
                _kafka_service = KafkaService()

    return _kafka_service


def reset_kafka_service() -> None:
    """Reset the singleton Kafka service (for testing)."""
    global _kafka_service
    _kafka_service = None
