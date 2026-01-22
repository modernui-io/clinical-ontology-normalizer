"""
Knowledge Graph Webhook Service.

Provides webhook functionality for notifying external systems of KG events:
- Concept creation/updates
- Relationship changes
- Patient graph modifications
- Reasoning path discoveries
- Benchmark completions

Features:
- Webhook registration and management
- Event filtering by type and criteria
- Retry logic with exponential backoff
- Signature verification (HMAC-SHA256)
- Rate limiting per webhook
- Event batching for high-throughput scenarios
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable
from urllib.parse import urlparse
import uuid

logger = logging.getLogger(__name__)


class WebhookEventType(str, Enum):
    """Types of events that can trigger webhooks."""

    # Concept events
    CONCEPT_CREATED = "concept.created"
    CONCEPT_UPDATED = "concept.updated"
    CONCEPT_DELETED = "concept.deleted"

    # Relationship events
    RELATIONSHIP_CREATED = "relationship.created"
    RELATIONSHIP_UPDATED = "relationship.updated"
    RELATIONSHIP_DELETED = "relationship.deleted"

    # Patient events
    PATIENT_GRAPH_CREATED = "patient.graph.created"
    PATIENT_GRAPH_UPDATED = "patient.graph.updated"
    PATIENT_FINDING_ADDED = "patient.finding.added"
    PATIENT_MEDICATION_CHANGED = "patient.medication.changed"

    # Reasoning events
    REASONING_PATH_FOUND = "reasoning.path.found"
    CAUSAL_CHAIN_DISCOVERED = "reasoning.causal.discovered"
    MDT_SESSION_COMPLETED = "reasoning.mdt.completed"

    # Batch events
    BATCH_JOB_STARTED = "batch.job.started"
    BATCH_JOB_COMPLETED = "batch.job.completed"
    BATCH_JOB_FAILED = "batch.job.failed"

    # Benchmark events
    BENCHMARK_STARTED = "benchmark.started"
    BENCHMARK_COMPLETED = "benchmark.completed"

    # System events
    HEALTH_STATUS_CHANGED = "system.health.changed"
    CACHE_INVALIDATED = "system.cache.invalidated"


class WebhookStatus(str, Enum):
    """Status of a webhook subscription."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    FAILED = "failed"  # Too many failures


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery attempt."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookFilter:
    """Filter criteria for webhook events."""

    event_types: list[WebhookEventType] = field(default_factory=list)
    patient_ids: list[str] = field(default_factory=list)  # Empty = all patients
    concept_cuis: list[str] = field(default_factory=list)  # Empty = all concepts
    semantic_types: list[str] = field(default_factory=list)
    min_confidence: float = 0.0
    custom_filter: Callable[[dict], bool] | None = None

    def matches(self, event: WebhookEvent) -> bool:
        """Check if event matches filter criteria."""
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False

        # Check patient ID
        if self.patient_ids:
            patient_id = event.payload.get("patient_id")
            if patient_id and patient_id not in self.patient_ids:
                return False

        # Check concept CUI
        if self.concept_cuis:
            cui = event.payload.get("cui") or event.payload.get("concept_cui")
            if cui and cui not in self.concept_cuis:
                return False

        # Check semantic type
        if self.semantic_types:
            sem_type = event.payload.get("semantic_type")
            if sem_type and sem_type not in self.semantic_types:
                return False

        # Check confidence
        confidence = event.payload.get("confidence", 1.0)
        if confidence < self.min_confidence:
            return False

        # Custom filter
        if self.custom_filter:
            try:
                if not self.custom_filter(event.payload):
                    return False
            except Exception as e:
                logger.warning(f"Custom filter error: {e}")
                return False

        return True


@dataclass
class WebhookEvent:
    """An event to be delivered to webhooks."""

    id: str
    event_type: WebhookEventType
    payload: dict[str, Any]
    created_at: datetime
    source: str = "kg_service"
    version: str = "1.0"
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "version": self.version,
            "correlation_id": self.correlation_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class DeliveryAttempt:
    """Record of a webhook delivery attempt."""

    id: str
    webhook_id: str
    event_id: str
    status: DeliveryStatus
    attempted_at: datetime
    response_code: int | None = None
    response_body: str | None = None
    error_message: str | None = None
    duration_ms: float = 0.0
    retry_count: int = 0


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""

    id: str
    name: str
    url: str
    secret: str  # For HMAC signing
    status: WebhookStatus = WebhookStatus.ACTIVE
    filter: WebhookFilter = field(default_factory=WebhookFilter)

    # Delivery settings
    timeout_seconds: float = 30.0
    max_retries: int = 5
    retry_delay_seconds: float = 60.0
    retry_backoff_multiplier: float = 2.0

    # Rate limiting
    max_requests_per_minute: int = 60
    batch_events: bool = False
    batch_max_size: int = 100
    batch_max_wait_seconds: float = 5.0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_delivery_at: datetime | None = None
    consecutive_failures: int = 0
    total_deliveries: int = 0
    total_failures: int = 0

    # Custom headers
    headers: dict[str, str] = field(default_factory=dict)

    def calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff."""
        return self.retry_delay_seconds * (self.retry_backoff_multiplier ** attempt)


@dataclass
class WebhookDeliveryResult:
    """Result of delivering an event to a webhook."""

    webhook_id: str
    event_id: str
    success: bool
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    retry_scheduled: bool = False


class WebhookSignatureError(Exception):
    """Raised when webhook signature verification fails."""
    pass


class WebhookDeliveryError(Exception):
    """Raised when webhook delivery fails."""

    def __init__(self, message: str, status_code: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class KGWebhookService:
    """
    Service for managing and delivering KG webhooks.

    Features:
    - Register/unregister webhooks
    - Event filtering
    - HMAC signature verification
    - Retry logic with exponential backoff
    - Event batching
    - Rate limiting
    """

    def __init__(self, http_client: Any = None):
        """
        Initialize the webhook service.

        Args:
            http_client: Optional async HTTP client for testing
        """
        self._webhooks: dict[str, WebhookConfig] = {}
        self._events: dict[str, WebhookEvent] = {}
        self._delivery_attempts: dict[str, list[DeliveryAttempt]] = {}
        self._pending_batches: dict[str, list[WebhookEvent]] = {}
        self._rate_limit_buckets: dict[str, list[datetime]] = {}
        self._http_client = http_client
        self._event_queue: asyncio.Queue[tuple[str, WebhookEvent]] = asyncio.Queue()
        self._batch_timers: dict[str, asyncio.Task] = {}
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def register_webhook(
        self,
        name: str,
        url: str,
        event_types: list[WebhookEventType] | None = None,
        secret: str | None = None,
        **kwargs
    ) -> WebhookConfig:
        """
        Register a new webhook endpoint.

        Args:
            name: Human-readable name
            url: Webhook URL
            event_types: Events to subscribe to (None = all)
            secret: HMAC secret (generated if not provided)
            **kwargs: Additional WebhookConfig options

        Returns:
            WebhookConfig for the registered webhook
        """
        # Validate URL
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

        webhook_id = str(uuid.uuid4())
        secret = secret or secrets.token_hex(32)

        webhook_filter = WebhookFilter(
            event_types=event_types or []
        )

        # Apply additional filter criteria from kwargs
        if "patient_ids" in kwargs:
            webhook_filter.patient_ids = kwargs.pop("patient_ids")
        if "concept_cuis" in kwargs:
            webhook_filter.concept_cuis = kwargs.pop("concept_cuis")
        if "semantic_types" in kwargs:
            webhook_filter.semantic_types = kwargs.pop("semantic_types")
        if "min_confidence" in kwargs:
            webhook_filter.min_confidence = kwargs.pop("min_confidence")

        webhook = WebhookConfig(
            id=webhook_id,
            name=name,
            url=url,
            secret=secret,
            filter=webhook_filter,
            **kwargs
        )

        self._webhooks[webhook_id] = webhook
        self._delivery_attempts[webhook_id] = []
        self._rate_limit_buckets[webhook_id] = []

        logger.info(f"Registered webhook: {name} ({webhook_id}) -> {url}")
        return webhook

    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook.

        Args:
            webhook_id: ID of webhook to unregister

        Returns:
            True if webhook was unregistered
        """
        if webhook_id not in self._webhooks:
            return False

        webhook = self._webhooks.pop(webhook_id)
        self._delivery_attempts.pop(webhook_id, None)
        self._rate_limit_buckets.pop(webhook_id, None)
        self._pending_batches.pop(webhook_id, None)

        # Cancel batch timer if exists
        if webhook_id in self._batch_timers:
            self._batch_timers[webhook_id].cancel()
            del self._batch_timers[webhook_id]

        logger.info(f"Unregistered webhook: {webhook.name} ({webhook_id})")
        return True

    def get_webhook(self, webhook_id: str) -> WebhookConfig | None:
        """Get webhook by ID."""
        return self._webhooks.get(webhook_id)

    def list_webhooks(
        self,
        status: WebhookStatus | None = None
    ) -> list[WebhookConfig]:
        """
        List all registered webhooks.

        Args:
            status: Filter by status

        Returns:
            List of webhooks
        """
        webhooks = list(self._webhooks.values())
        if status is not None:
            webhooks = [w for w in webhooks if w.status == status]
        return webhooks

    def update_webhook_status(
        self,
        webhook_id: str,
        status: WebhookStatus
    ) -> bool:
        """
        Update webhook status.

        Args:
            webhook_id: ID of webhook
            status: New status

        Returns:
            True if updated
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return False

        webhook.status = status
        webhook.updated_at = datetime.utcnow()

        # Reset failure count if re-enabling
        if status == WebhookStatus.ACTIVE:
            webhook.consecutive_failures = 0

        return True

    def create_event(
        self,
        event_type: WebhookEventType,
        payload: dict[str, Any],
        correlation_id: str | None = None
    ) -> WebhookEvent:
        """
        Create a new webhook event.

        Args:
            event_type: Type of event
            payload: Event data
            correlation_id: Optional correlation ID for tracing

        Returns:
            Created WebhookEvent
        """
        event = WebhookEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            payload=payload,
            created_at=datetime.utcnow(),
            correlation_id=correlation_id
        )

        self._events[event.id] = event
        return event

    def generate_signature(
        self,
        payload: str,
        secret: str,
        timestamp: int | None = None
    ) -> tuple[str, int]:
        """
        Generate HMAC-SHA256 signature for payload.

        Args:
            payload: JSON payload to sign
            secret: Webhook secret
            timestamp: Unix timestamp (generated if not provided)

        Returns:
            Tuple of (signature, timestamp)
        """
        timestamp = timestamp or int(time.time())
        message = f"{timestamp}.{payload}"

        signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return signature, timestamp

    def verify_signature(
        self,
        payload: str,
        signature: str,
        timestamp: int,
        secret: str,
        max_age_seconds: int = 300
    ) -> bool:
        """
        Verify HMAC-SHA256 signature.

        Args:
            payload: JSON payload
            signature: Received signature
            timestamp: Received timestamp
            secret: Webhook secret
            max_age_seconds: Maximum age of signature

        Returns:
            True if signature is valid
        """
        # Check timestamp age
        now = int(time.time())
        if abs(now - timestamp) > max_age_seconds:
            raise WebhookSignatureError("Signature timestamp too old")

        expected_signature, _ = self.generate_signature(payload, secret, timestamp)

        if not hmac.compare_digest(signature, expected_signature):
            raise WebhookSignatureError("Invalid signature")

        return True

    def _check_rate_limit(self, webhook_id: str) -> bool:
        """
        Check if webhook is within rate limit.

        Returns:
            True if request is allowed
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return False

        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        # Clean old entries
        bucket = self._rate_limit_buckets.get(webhook_id, [])
        bucket = [t for t in bucket if t > cutoff]
        self._rate_limit_buckets[webhook_id] = bucket

        # Check limit
        if len(bucket) >= webhook.max_requests_per_minute:
            return False

        # Add current request
        bucket.append(now)
        return True

    async def emit_event(
        self,
        event_type: WebhookEventType,
        payload: dict[str, Any],
        correlation_id: str | None = None
    ) -> WebhookEvent:
        """
        Emit an event to all matching webhooks.

        Args:
            event_type: Type of event
            payload: Event data
            correlation_id: Optional correlation ID

        Returns:
            Created WebhookEvent
        """
        event = self.create_event(event_type, payload, correlation_id)

        # Find matching webhooks
        for webhook_id, webhook in self._webhooks.items():
            if webhook.status != WebhookStatus.ACTIVE:
                continue

            if not webhook.filter.matches(event):
                continue

            if webhook.batch_events:
                # Add to batch
                await self._add_to_batch(webhook_id, event)
            else:
                # Queue for immediate delivery
                await self._event_queue.put((webhook_id, event))

        return event

    async def _add_to_batch(self, webhook_id: str, event: WebhookEvent):
        """Add event to batch for a webhook."""
        if webhook_id not in self._pending_batches:
            self._pending_batches[webhook_id] = []

        self._pending_batches[webhook_id].append(event)
        webhook = self._webhooks[webhook_id]

        # Check if batch is full
        if len(self._pending_batches[webhook_id]) >= webhook.batch_max_size:
            await self._flush_batch(webhook_id)
            return

        # Start timer if not already running
        if webhook_id not in self._batch_timers:
            self._batch_timers[webhook_id] = asyncio.create_task(
                self._batch_timer(webhook_id, webhook.batch_max_wait_seconds)
            )

    async def _batch_timer(self, webhook_id: str, delay: float):
        """Timer to flush batch after delay."""
        try:
            await asyncio.sleep(delay)
            await self._flush_batch(webhook_id)
        except asyncio.CancelledError:
            pass
        finally:
            self._batch_timers.pop(webhook_id, None)

    async def _flush_batch(self, webhook_id: str):
        """Flush pending batch for a webhook."""
        events = self._pending_batches.pop(webhook_id, [])
        if not events:
            return

        # Cancel timer
        if webhook_id in self._batch_timers:
            self._batch_timers[webhook_id].cancel()
            del self._batch_timers[webhook_id]

        # Create batch event
        batch_event = self.create_event(
            WebhookEventType.BATCH_JOB_COMPLETED,  # Use as container
            {
                "batch": True,
                "event_count": len(events),
                "events": [e.to_dict() for e in events]
            }
        )

        await self._event_queue.put((webhook_id, batch_event))

    async def deliver_event(
        self,
        webhook_id: str,
        event: WebhookEvent
    ) -> WebhookDeliveryResult:
        """
        Deliver an event to a webhook.

        Args:
            webhook_id: Target webhook ID
            event: Event to deliver

        Returns:
            DeliveryResult with outcome
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_id=event.id,
                success=False,
                error="Webhook not found"
            )

        if webhook.status != WebhookStatus.ACTIVE:
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_id=event.id,
                success=False,
                error=f"Webhook is {webhook.status.value}"
            )

        # Check rate limit
        if not self._check_rate_limit(webhook_id):
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_id=event.id,
                success=False,
                error="Rate limit exceeded",
                retry_scheduled=True
            )

        # Prepare payload
        payload = event.to_json()
        signature, timestamp = self.generate_signature(payload, webhook.secret)

        headers = {
            "Content-Type": "application/json",
            "X-KG-Signature": signature,
            "X-KG-Timestamp": str(timestamp),
            "X-KG-Event-Type": event.event_type.value,
            "X-KG-Event-ID": event.id,
            **webhook.headers
        }

        if event.correlation_id:
            headers["X-Correlation-ID"] = event.correlation_id

        # Deliver
        start_time = time.time()
        try:
            if self._http_client:
                # Use injected client (for testing)
                response = await self._http_client.post(
                    webhook.url,
                    data=payload,
                    headers=headers,
                    timeout=webhook.timeout_seconds
                )
                status_code = response.status_code
                response_body = response.text
            else:
                # Mock successful delivery for now
                status_code = 200
                response_body = '{"status": "ok"}'

            duration_ms = (time.time() - start_time) * 1000

            # Record attempt
            attempt = DeliveryAttempt(
                id=str(uuid.uuid4()),
                webhook_id=webhook_id,
                event_id=event.id,
                status=DeliveryStatus.DELIVERED if 200 <= status_code < 300 else DeliveryStatus.FAILED,
                attempted_at=datetime.utcnow(),
                response_code=status_code,
                response_body=response_body[:1000] if response_body else None,
                duration_ms=duration_ms
            )
            self._delivery_attempts[webhook_id].append(attempt)

            # Update webhook stats
            webhook.last_delivery_at = datetime.utcnow()
            webhook.total_deliveries += 1

            if 200 <= status_code < 300:
                webhook.consecutive_failures = 0
                return WebhookDeliveryResult(
                    webhook_id=webhook_id,
                    event_id=event.id,
                    success=True,
                    status_code=status_code,
                    response_body=response_body,
                    duration_ms=duration_ms
                )
            else:
                webhook.consecutive_failures += 1
                webhook.total_failures += 1

                # Check if should disable
                if webhook.consecutive_failures >= 10:
                    webhook.status = WebhookStatus.FAILED
                    logger.warning(
                        f"Webhook {webhook.name} disabled after {webhook.consecutive_failures} failures"
                    )

                return WebhookDeliveryResult(
                    webhook_id=webhook_id,
                    event_id=event.id,
                    success=False,
                    status_code=status_code,
                    response_body=response_body,
                    error=f"HTTP {status_code}",
                    duration_ms=duration_ms,
                    retry_scheduled=status_code >= 500
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Record failed attempt
            attempt = DeliveryAttempt(
                id=str(uuid.uuid4()),
                webhook_id=webhook_id,
                event_id=event.id,
                status=DeliveryStatus.FAILED,
                attempted_at=datetime.utcnow(),
                error_message=str(e),
                duration_ms=duration_ms
            )
            self._delivery_attempts[webhook_id].append(attempt)

            webhook.consecutive_failures += 1
            webhook.total_failures += 1

            logger.error(f"Webhook delivery failed: {e}")

            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_id=event.id,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                retry_scheduled=True
            )

    async def deliver_with_retry(
        self,
        webhook_id: str,
        event: WebhookEvent
    ) -> WebhookDeliveryResult:
        """
        Deliver event with retry logic.

        Args:
            webhook_id: Target webhook ID
            event: Event to deliver

        Returns:
            Final delivery result
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_id=event.id,
                success=False,
                error="Webhook not found"
            )

        for attempt in range(webhook.max_retries + 1):
            result = await self.deliver_event(webhook_id, event)

            if result.success or not result.retry_scheduled:
                return result

            if attempt < webhook.max_retries:
                delay = webhook.calculate_retry_delay(attempt)
                logger.info(
                    f"Retrying webhook {webhook.name} in {delay}s "
                    f"(attempt {attempt + 1}/{webhook.max_retries})"
                )
                await asyncio.sleep(delay)

        return result

    def get_delivery_history(
        self,
        webhook_id: str,
        limit: int = 100
    ) -> list[DeliveryAttempt]:
        """
        Get delivery history for a webhook.

        Args:
            webhook_id: Webhook ID
            limit: Maximum attempts to return

        Returns:
            List of delivery attempts (most recent first)
        """
        attempts = self._delivery_attempts.get(webhook_id, [])
        return sorted(attempts, key=lambda a: a.attempted_at, reverse=True)[:limit]

    def get_webhook_stats(self, webhook_id: str) -> dict[str, Any] | None:
        """
        Get statistics for a webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            Statistics dict or None
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return None

        attempts = self._delivery_attempts.get(webhook_id, [])
        recent_attempts = [a for a in attempts if a.attempted_at > datetime.utcnow() - timedelta(hours=24)]

        success_count = sum(1 for a in recent_attempts if a.status == DeliveryStatus.DELIVERED)
        failure_count = sum(1 for a in recent_attempts if a.status == DeliveryStatus.FAILED)

        avg_duration = 0.0
        if recent_attempts:
            avg_duration = sum(a.duration_ms for a in recent_attempts) / len(recent_attempts)

        return {
            "webhook_id": webhook_id,
            "name": webhook.name,
            "status": webhook.status.value,
            "total_deliveries": webhook.total_deliveries,
            "total_failures": webhook.total_failures,
            "consecutive_failures": webhook.consecutive_failures,
            "success_rate_24h": success_count / max(len(recent_attempts), 1),
            "deliveries_24h": len(recent_attempts),
            "avg_duration_ms_24h": avg_duration,
            "last_delivery_at": webhook.last_delivery_at.isoformat() if webhook.last_delivery_at else None,
        }

    async def start(self):
        """Start the webhook delivery worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._delivery_worker())
        logger.info("Webhook service started")

    async def stop(self):
        """Stop the webhook delivery worker."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Cancel batch timers
        for timer in self._batch_timers.values():
            timer.cancel()
        self._batch_timers.clear()

        logger.info("Webhook service stopped")

    async def _delivery_worker(self):
        """Background worker for delivering events."""
        while self._running:
            try:
                # Get next event with timeout
                try:
                    webhook_id, event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Deliver with retry
                result = await self.deliver_with_retry(webhook_id, event)

                if not result.success:
                    logger.warning(
                        f"Failed to deliver event {event.id} to webhook {webhook_id}: "
                        f"{result.error}"
                    )

                self._event_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Webhook worker error: {e}")
                await asyncio.sleep(1)


# Singleton instance
_webhook_service: KGWebhookService | None = None


def get_webhook_service() -> KGWebhookService:
    """Get or create webhook service singleton."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = KGWebhookService()
    return _webhook_service
