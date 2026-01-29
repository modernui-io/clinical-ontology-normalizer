"""Tests for KG Webhook Service."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.services.kg_webhook_service import (
    KGWebhookService,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
    WebhookFilter,
    WebhookEvent,
    WebhookConfig,
    DeliveryAttempt,
    WebhookDeliveryResult,
    WebhookSignatureError,
    get_webhook_service,
)


class TestWebhookFilter:
    """Tests for WebhookFilter."""

    def test_filter_matches_all_events_by_default(self):
        """Empty filter matches all events."""
        filter = WebhookFilter()
        event = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"cui": "C0001234"},
            created_at=datetime.now(timezone.utc)
        )
        assert filter.matches(event)

    def test_filter_by_event_type(self):
        """Filter by specific event types."""
        filter = WebhookFilter(
            event_types=[WebhookEventType.CONCEPT_CREATED, WebhookEventType.CONCEPT_UPDATED]
        )

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.CONCEPT_DELETED,
            payload={},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)

    def test_filter_by_patient_id(self):
        """Filter by patient IDs."""
        filter = WebhookFilter(patient_ids=["P001", "P002"])

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.PATIENT_FINDING_ADDED,
            payload={"patient_id": "P001"},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.PATIENT_FINDING_ADDED,
            payload={"patient_id": "P003"},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)

    def test_filter_by_concept_cui(self):
        """Filter by concept CUIs."""
        filter = WebhookFilter(concept_cuis=["C0001234", "C0005678"])

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"cui": "C0001234"},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"cui": "C9999999"},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)

    def test_filter_by_semantic_type(self):
        """Filter by semantic types."""
        filter = WebhookFilter(semantic_types=["T047", "T121"])

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"semantic_type": "T047"},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"semantic_type": "T184"},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)

    def test_filter_by_min_confidence(self):
        """Filter by minimum confidence."""
        filter = WebhookFilter(min_confidence=0.8)

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.REASONING_PATH_FOUND,
            payload={"confidence": 0.9},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.REASONING_PATH_FOUND,
            payload={"confidence": 0.5},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)

    def test_filter_with_custom_function(self):
        """Filter with custom function."""
        filter = WebhookFilter(
            custom_filter=lambda p: p.get("severity") == "critical"
        )

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.HEALTH_STATUS_CHANGED,
            payload={"severity": "critical"},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.HEALTH_STATUS_CHANGED,
            payload={"severity": "warning"},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)

    def test_filter_combined_criteria(self):
        """Filter with multiple criteria."""
        filter = WebhookFilter(
            event_types=[WebhookEventType.PATIENT_FINDING_ADDED],
            patient_ids=["P001"],
            min_confidence=0.7
        )

        event1 = WebhookEvent(
            id="test-1",
            event_type=WebhookEventType.PATIENT_FINDING_ADDED,
            payload={"patient_id": "P001", "confidence": 0.9},
            created_at=datetime.now(timezone.utc)
        )
        event2 = WebhookEvent(
            id="test-2",
            event_type=WebhookEventType.PATIENT_FINDING_ADDED,
            payload={"patient_id": "P001", "confidence": 0.5},
            created_at=datetime.now(timezone.utc)
        )
        event3 = WebhookEvent(
            id="test-3",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"patient_id": "P001", "confidence": 0.9},
            created_at=datetime.now(timezone.utc)
        )

        assert filter.matches(event1)
        assert not filter.matches(event2)  # Low confidence
        assert not filter.matches(event3)  # Wrong event type


class TestWebhookEvent:
    """Tests for WebhookEvent."""

    def test_event_to_dict(self):
        """Convert event to dictionary."""
        event = WebhookEvent(
            id="event-123",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"cui": "C0001234", "name": "Test Concept"},
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            correlation_id="corr-456"
        )

        result = event.to_dict()

        assert result["id"] == "event-123"
        assert result["event_type"] == "concept.created"
        assert result["payload"]["cui"] == "C0001234"
        assert result["correlation_id"] == "corr-456"

    def test_event_to_json(self):
        """Convert event to JSON."""
        event = WebhookEvent(
            id="event-123",
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"cui": "C0001234"},
            created_at=datetime(2024, 1, 15, 10, 30, 0)
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["id"] == "event-123"
        assert parsed["event_type"] == "concept.created"


class TestKGWebhookService:
    """Tests for KGWebhookService."""

    @pytest.fixture
    def service(self):
        """Create a webhook service instance."""
        return KGWebhookService()

    def test_register_webhook(self, service):
        """Register a new webhook."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            event_types=[WebhookEventType.CONCEPT_CREATED]
        )

        assert webhook.id is not None
        assert webhook.name == "Test Webhook"
        assert webhook.url == "https://example.com/webhook"
        assert webhook.status == WebhookStatus.ACTIVE
        assert len(webhook.secret) == 64  # 32 bytes hex encoded

    def test_register_webhook_with_custom_secret(self, service):
        """Register webhook with custom secret."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="my-custom-secret"
        )

        assert webhook.secret == "my-custom-secret"

    def test_register_webhook_invalid_url(self, service):
        """Reject invalid URLs."""
        with pytest.raises(ValueError) as exc:
            service.register_webhook(
                name="Test",
                url="ftp://example.com/webhook"
            )
        assert "Invalid URL scheme" in str(exc.value)

    def test_register_webhook_with_filters(self, service):
        """Register webhook with filter criteria."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            event_types=[WebhookEventType.PATIENT_FINDING_ADDED],
            patient_ids=["P001", "P002"],
            min_confidence=0.8
        )

        assert WebhookEventType.PATIENT_FINDING_ADDED in webhook.filter.event_types
        assert "P001" in webhook.filter.patient_ids
        assert webhook.filter.min_confidence == 0.8

    def test_unregister_webhook(self, service):
        """Unregister a webhook."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )

        result = service.unregister_webhook(webhook.id)
        assert result is True
        assert service.get_webhook(webhook.id) is None

    def test_unregister_nonexistent_webhook(self, service):
        """Unregister nonexistent webhook returns False."""
        result = service.unregister_webhook("nonexistent-id")
        assert result is False

    def test_list_webhooks(self, service):
        """List all webhooks."""
        service.register_webhook("Webhook 1", "https://example.com/1")
        service.register_webhook("Webhook 2", "https://example.com/2")

        webhooks = service.list_webhooks()
        assert len(webhooks) == 2

    def test_list_webhooks_filter_by_status(self, service):
        """List webhooks filtered by status."""
        w1 = service.register_webhook("Webhook 1", "https://example.com/1")
        w2 = service.register_webhook("Webhook 2", "https://example.com/2")

        service.update_webhook_status(w1.id, WebhookStatus.PAUSED)

        active = service.list_webhooks(status=WebhookStatus.ACTIVE)
        paused = service.list_webhooks(status=WebhookStatus.PAUSED)

        assert len(active) == 1
        assert len(paused) == 1

    def test_update_webhook_status(self, service):
        """Update webhook status."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )

        result = service.update_webhook_status(webhook.id, WebhookStatus.PAUSED)
        assert result is True
        assert service.get_webhook(webhook.id).status == WebhookStatus.PAUSED

    def test_update_status_resets_failures(self, service):
        """Re-activating webhook resets failure count."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        webhook.consecutive_failures = 5

        service.update_webhook_status(webhook.id, WebhookStatus.ACTIVE)
        assert webhook.consecutive_failures == 0

    def test_create_event(self, service):
        """Create a webhook event."""
        event = service.create_event(
            event_type=WebhookEventType.CONCEPT_CREATED,
            payload={"cui": "C0001234", "name": "Diabetes"},
            correlation_id="corr-123"
        )

        assert event.id is not None
        assert event.event_type == WebhookEventType.CONCEPT_CREATED
        assert event.payload["cui"] == "C0001234"
        assert event.correlation_id == "corr-123"

    def test_generate_signature(self, service):
        """Generate HMAC signature."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"

        signature, timestamp = service.generate_signature(payload, secret)

        assert len(signature) == 64  # SHA256 hex
        assert timestamp > 0

    def test_generate_signature_with_timestamp(self, service):
        """Generate signature with specific timestamp."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        timestamp = 1705312200

        signature, returned_ts = service.generate_signature(payload, secret, timestamp)

        assert returned_ts == timestamp
        # Same input should produce same signature
        sig2, _ = service.generate_signature(payload, secret, timestamp)
        assert signature == sig2

    def test_verify_signature_valid(self, service):
        """Verify valid signature."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        signature, timestamp = service.generate_signature(payload, secret)

        result = service.verify_signature(payload, signature, timestamp, secret)
        assert result is True

    def test_verify_signature_invalid(self, service):
        """Reject invalid signature."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        _, timestamp = service.generate_signature(payload, secret)

        with pytest.raises(WebhookSignatureError) as exc:
            service.verify_signature(payload, "invalid-signature", timestamp, secret)
        assert "Invalid signature" in str(exc.value)

    def test_verify_signature_expired(self, service):
        """Reject expired timestamp."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        old_timestamp = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        signature, _ = service.generate_signature(payload, secret, old_timestamp)

        with pytest.raises(WebhookSignatureError) as exc:
            service.verify_signature(payload, signature, old_timestamp, secret)
        assert "too old" in str(exc.value)

    def test_rate_limiting(self, service):
        """Rate limiting respects max requests per minute."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            max_requests_per_minute=3
        )

        # First 3 should pass
        assert service._check_rate_limit(webhook.id) is True
        assert service._check_rate_limit(webhook.id) is True
        assert service._check_rate_limit(webhook.id) is True

        # 4th should fail
        assert service._check_rate_limit(webhook.id) is False

    @pytest.mark.asyncio
    async def test_emit_event(self, service):
        """Emit event to matching webhooks."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            event_types=[WebhookEventType.CONCEPT_CREATED]
        )

        event = await service.emit_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        assert event.id is not None
        assert event.event_type == WebhookEventType.CONCEPT_CREATED

    @pytest.mark.asyncio
    async def test_emit_event_filters_by_type(self, service):
        """Events not matching filter are not queued."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            event_types=[WebhookEventType.CONCEPT_CREATED]
        )

        # This event type doesn't match
        event = await service.emit_event(
            WebhookEventType.CONCEPT_DELETED,
            {"cui": "C0001234"}
        )

        # Queue should be empty (event didn't match)
        assert service._event_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_emit_event_skips_inactive_webhooks(self, service):
        """Inactive webhooks are skipped."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        service.update_webhook_status(webhook.id, WebhookStatus.PAUSED)

        event = await service.emit_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        assert service._event_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_deliver_event_success(self, service):
        """Deliver event successfully."""
        # Mock HTTP client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_client.post = AsyncMock(return_value=mock_response)
        service._http_client = mock_client

        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        result = await service.deliver_event(webhook.id, event)

        assert result.success is True
        assert result.status_code == 200
        assert webhook.total_deliveries == 1
        assert webhook.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_deliver_event_failure(self, service):
        """Handle delivery failure."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_client.post = AsyncMock(return_value=mock_response)
        service._http_client = mock_client

        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        result = await service.deliver_event(webhook.id, event)

        assert result.success is False
        assert result.status_code == 500
        assert result.retry_scheduled is True
        assert webhook.consecutive_failures == 1
        assert webhook.total_failures == 1

    @pytest.mark.asyncio
    async def test_deliver_event_exception(self, service):
        """Handle delivery exception."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))
        service._http_client = mock_client

        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        result = await service.deliver_event(webhook.id, event)

        assert result.success is False
        assert "Connection error" in result.error
        assert result.retry_scheduled is True

    @pytest.mark.asyncio
    async def test_deliver_event_disables_after_failures(self, service):
        """Webhook is disabled after too many failures."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Error'
        mock_client.post = AsyncMock(return_value=mock_response)
        service._http_client = mock_client

        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        # Fail 10 times
        for _ in range(10):
            await service.deliver_event(webhook.id, event)

        assert webhook.status == WebhookStatus.FAILED
        assert webhook.consecutive_failures == 10

    @pytest.mark.asyncio
    async def test_deliver_event_nonexistent_webhook(self, service):
        """Handle delivery to nonexistent webhook."""
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        result = await service.deliver_event("nonexistent-id", event)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_deliver_event_rate_limited(self, service):
        """Handle rate limited delivery."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            max_requests_per_minute=1
        )
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        # First delivery (consumes rate limit)
        await service.deliver_event(webhook.id, event)

        # Second delivery should be rate limited
        result = await service.deliver_event(webhook.id, event)

        assert result.success is False
        assert "Rate limit" in result.error

    @pytest.mark.asyncio
    async def test_deliver_with_retry(self, service):
        """Deliver with retry logic."""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count < 3:
                response.status_code = 500
                response.text = 'Error'
            else:
                response.status_code = 200
                response.text = '{"status": "ok"}'
            return response

        mock_client = MagicMock()
        mock_client.post = mock_post
        service._http_client = mock_client

        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            max_retries=5,
            retry_delay_seconds=0.01  # Fast retries for test
        )
        event = service.create_event(
            WebhookEventType.CONCEPT_CREATED,
            {"cui": "C0001234"}
        )

        result = await service.deliver_with_retry(webhook.id, event)

        assert result.success is True
        assert call_count == 3

    def test_get_delivery_history(self, service):
        """Get delivery history for webhook."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )

        # Add some attempts
        for i in range(5):
            attempt = DeliveryAttempt(
                id=f"attempt-{i}",
                webhook_id=webhook.id,
                event_id=f"event-{i}",
                status=DeliveryStatus.DELIVERED,
                attempted_at=datetime.now(timezone.utc) - timedelta(minutes=i)
            )
            service._delivery_attempts[webhook.id].append(attempt)

        history = service.get_delivery_history(webhook.id, limit=3)

        assert len(history) == 3
        # Should be sorted by most recent first
        assert history[0].id == "attempt-0"

    def test_get_webhook_stats(self, service):
        """Get webhook statistics."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook"
        )
        webhook.total_deliveries = 100
        webhook.total_failures = 5
        webhook.last_delivery_at = datetime.now(timezone.utc)

        # Add recent attempts
        for i in range(10):
            status = DeliveryStatus.DELIVERED if i < 8 else DeliveryStatus.FAILED
            attempt = DeliveryAttempt(
                id=f"attempt-{i}",
                webhook_id=webhook.id,
                event_id=f"event-{i}",
                status=status,
                attempted_at=datetime.now(timezone.utc) - timedelta(hours=i),
                duration_ms=100.0 + i * 10
            )
            service._delivery_attempts[webhook.id].append(attempt)

        stats = service.get_webhook_stats(webhook.id)

        assert stats["webhook_id"] == webhook.id
        assert stats["total_deliveries"] == 100
        assert stats["total_failures"] == 5
        assert stats["deliveries_24h"] == 10
        assert stats["success_rate_24h"] == 0.8

    def test_get_webhook_stats_nonexistent(self, service):
        """Get stats for nonexistent webhook."""
        stats = service.get_webhook_stats("nonexistent-id")
        assert stats is None

    def test_calculate_retry_delay(self, service):
        """Calculate exponential backoff delay."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            retry_delay_seconds=10.0,
            retry_backoff_multiplier=2.0
        )

        assert webhook.calculate_retry_delay(0) == 10.0
        assert webhook.calculate_retry_delay(1) == 20.0
        assert webhook.calculate_retry_delay(2) == 40.0
        assert webhook.calculate_retry_delay(3) == 80.0

    @pytest.mark.asyncio
    async def test_start_stop_service(self, service):
        """Start and stop webhook service."""
        await service.start()
        assert service._running is True
        assert service._worker_task is not None

        await service.stop()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_batch_events(self, service):
        """Batch events before delivery."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            batch_events=True,
            batch_max_size=3,
            batch_max_wait_seconds=10.0
        )

        # Add events
        for i in range(3):
            await service._add_to_batch(
                webhook.id,
                service.create_event(
                    WebhookEventType.CONCEPT_CREATED,
                    {"cui": f"C{i:07d}"}
                )
            )

        # Batch should have been flushed
        assert webhook.id not in service._pending_batches

    @pytest.mark.asyncio
    async def test_batch_timer_flushes(self, service):
        """Batch timer flushes pending events."""
        webhook = service.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            batch_events=True,
            batch_max_size=100,  # Won't hit this
            batch_max_wait_seconds=0.1  # Short wait
        )

        # Add one event
        await service._add_to_batch(
            webhook.id,
            service.create_event(
                WebhookEventType.CONCEPT_CREATED,
                {"cui": "C0001234"}
            )
        )

        # Wait for timer
        await asyncio.sleep(0.2)

        # Batch should have been flushed
        assert webhook.id not in service._pending_batches


class TestWebhookEventTypes:
    """Tests for webhook event type coverage."""

    def test_concept_events(self):
        """Verify concept event types exist."""
        assert WebhookEventType.CONCEPT_CREATED.value == "concept.created"
        assert WebhookEventType.CONCEPT_UPDATED.value == "concept.updated"
        assert WebhookEventType.CONCEPT_DELETED.value == "concept.deleted"

    def test_relationship_events(self):
        """Verify relationship event types exist."""
        assert WebhookEventType.RELATIONSHIP_CREATED.value == "relationship.created"
        assert WebhookEventType.RELATIONSHIP_UPDATED.value == "relationship.updated"
        assert WebhookEventType.RELATIONSHIP_DELETED.value == "relationship.deleted"

    def test_patient_events(self):
        """Verify patient event types exist."""
        assert WebhookEventType.PATIENT_GRAPH_CREATED.value == "patient.graph.created"
        assert WebhookEventType.PATIENT_GRAPH_UPDATED.value == "patient.graph.updated"
        assert WebhookEventType.PATIENT_FINDING_ADDED.value == "patient.finding.added"
        assert WebhookEventType.PATIENT_MEDICATION_CHANGED.value == "patient.medication.changed"

    def test_reasoning_events(self):
        """Verify reasoning event types exist."""
        assert WebhookEventType.REASONING_PATH_FOUND.value == "reasoning.path.found"
        assert WebhookEventType.CAUSAL_CHAIN_DISCOVERED.value == "reasoning.causal.discovered"
        assert WebhookEventType.MDT_SESSION_COMPLETED.value == "reasoning.mdt.completed"

    def test_batch_events(self):
        """Verify batch event types exist."""
        assert WebhookEventType.BATCH_JOB_STARTED.value == "batch.job.started"
        assert WebhookEventType.BATCH_JOB_COMPLETED.value == "batch.job.completed"
        assert WebhookEventType.BATCH_JOB_FAILED.value == "batch.job.failed"

    def test_benchmark_events(self):
        """Verify benchmark event types exist."""
        assert WebhookEventType.BENCHMARK_STARTED.value == "benchmark.started"
        assert WebhookEventType.BENCHMARK_COMPLETED.value == "benchmark.completed"

    def test_system_events(self):
        """Verify system event types exist."""
        assert WebhookEventType.HEALTH_STATUS_CHANGED.value == "system.health.changed"
        assert WebhookEventType.CACHE_INVALIDATED.value == "system.cache.invalidated"


class TestSingletonInstance:
    """Tests for singleton pattern."""

    def test_get_webhook_service_returns_same_instance(self):
        """Singleton returns same instance."""
        service1 = get_webhook_service()
        service2 = get_webhook_service()
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
