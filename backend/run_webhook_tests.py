#!/usr/bin/env python3
"""Standalone test runner for KG Webhook Service tests."""

import sys
import os
import importlib.util

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create comprehensive mocks for dependencies
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock the problematic modules before any imports
sys.modules["sentence_transformers"] = MockModule()
sys.modules["sentence_transformers"].SentenceTransformer = MockModule()
sys.modules["neo4j"] = MockModule()
sys.modules["neo4j"].GraphDatabase = MockModule()

# Now import and run tests
import asyncio
import traceback
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

# Load the webhook service module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_webhook_service",
    "app/services/kg_webhook_service.py",
    submodule_search_locations=[]
)
webhook_module = importlib.util.module_from_spec(spec)
webhook_module.__package__ = "app.services"
sys.modules["app.services.kg_webhook_service"] = webhook_module
spec.loader.exec_module(webhook_module)

# Import the module under test
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


def run_test(name, test_func):
    """Run a single test."""
    try:
        if asyncio.iscoroutinefunction(test_func):
            asyncio.get_event_loop().run_until_complete(test_func())
        else:
            test_func()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def test_filter_matches_all_events_by_default():
    filter = WebhookFilter()
    event = WebhookEvent(
        id="test-1",
        event_type=WebhookEventType.CONCEPT_CREATED,
        payload={"cui": "C0001234"},
        created_at=datetime.utcnow()
    )
    assert filter.matches(event)


def test_filter_by_event_type():
    filter = WebhookFilter(
        event_types=[WebhookEventType.CONCEPT_CREATED, WebhookEventType.CONCEPT_UPDATED]
    )
    event1 = WebhookEvent(
        id="test-1",
        event_type=WebhookEventType.CONCEPT_CREATED,
        payload={},
        created_at=datetime.utcnow()
    )
    event2 = WebhookEvent(
        id="test-2",
        event_type=WebhookEventType.CONCEPT_DELETED,
        payload={},
        created_at=datetime.utcnow()
    )
    assert filter.matches(event1)
    assert not filter.matches(event2)


def test_filter_by_patient_id():
    filter = WebhookFilter(patient_ids=["P001", "P002"])
    event1 = WebhookEvent(
        id="test-1",
        event_type=WebhookEventType.PATIENT_FINDING_ADDED,
        payload={"patient_id": "P001"},
        created_at=datetime.utcnow()
    )
    event2 = WebhookEvent(
        id="test-2",
        event_type=WebhookEventType.PATIENT_FINDING_ADDED,
        payload={"patient_id": "P003"},
        created_at=datetime.utcnow()
    )
    assert filter.matches(event1)
    assert not filter.matches(event2)


def test_filter_by_semantic_type():
    filter = WebhookFilter(semantic_types=["T047", "T121"])
    event1 = WebhookEvent(
        id="test-1",
        event_type=WebhookEventType.CONCEPT_CREATED,
        payload={"semantic_type": "T047"},
        created_at=datetime.utcnow()
    )
    event2 = WebhookEvent(
        id="test-2",
        event_type=WebhookEventType.CONCEPT_CREATED,
        payload={"semantic_type": "T184"},
        created_at=datetime.utcnow()
    )
    assert filter.matches(event1)
    assert not filter.matches(event2)


def test_filter_by_min_confidence():
    filter = WebhookFilter(min_confidence=0.8)
    event1 = WebhookEvent(
        id="test-1",
        event_type=WebhookEventType.REASONING_PATH_FOUND,
        payload={"confidence": 0.9},
        created_at=datetime.utcnow()
    )
    event2 = WebhookEvent(
        id="test-2",
        event_type=WebhookEventType.REASONING_PATH_FOUND,
        payload={"confidence": 0.5},
        created_at=datetime.utcnow()
    )
    assert filter.matches(event1)
    assert not filter.matches(event2)


def test_filter_with_custom_function():
    filter = WebhookFilter(
        custom_filter=lambda p: p.get("severity") == "critical"
    )
    event1 = WebhookEvent(
        id="test-1",
        event_type=WebhookEventType.HEALTH_STATUS_CHANGED,
        payload={"severity": "critical"},
        created_at=datetime.utcnow()
    )
    event2 = WebhookEvent(
        id="test-2",
        event_type=WebhookEventType.HEALTH_STATUS_CHANGED,
        payload={"severity": "warning"},
        created_at=datetime.utcnow()
    )
    assert filter.matches(event1)
    assert not filter.matches(event2)


def test_event_to_dict():
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


def test_event_to_json():
    import json
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


def test_register_webhook():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        event_types=[WebhookEventType.CONCEPT_CREATED]
    )
    assert webhook.id is not None
    assert webhook.name == "Test Webhook"
    assert webhook.url == "https://example.com/webhook"
    assert webhook.status == WebhookStatus.ACTIVE
    assert len(webhook.secret) == 64


def test_register_webhook_with_custom_secret():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        secret="my-custom-secret"
    )
    assert webhook.secret == "my-custom-secret"


def test_register_webhook_invalid_url():
    service = KGWebhookService()
    try:
        service.register_webhook(
            name="Test",
            url="ftp://example.com/webhook"
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid URL scheme" in str(e)


def test_register_webhook_with_filters():
    service = KGWebhookService()
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


def test_unregister_webhook():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook"
    )
    result = service.unregister_webhook(webhook.id)
    assert result is True
    assert service.get_webhook(webhook.id) is None


def test_unregister_nonexistent_webhook():
    service = KGWebhookService()
    result = service.unregister_webhook("nonexistent-id")
    assert result is False


def test_list_webhooks():
    service = KGWebhookService()
    service.register_webhook("Webhook 1", "https://example.com/1")
    service.register_webhook("Webhook 2", "https://example.com/2")
    webhooks = service.list_webhooks()
    assert len(webhooks) == 2


def test_list_webhooks_filter_by_status():
    service = KGWebhookService()
    w1 = service.register_webhook("Webhook 1", "https://example.com/1")
    w2 = service.register_webhook("Webhook 2", "https://example.com/2")
    service.update_webhook_status(w1.id, WebhookStatus.PAUSED)
    active = service.list_webhooks(status=WebhookStatus.ACTIVE)
    paused = service.list_webhooks(status=WebhookStatus.PAUSED)
    assert len(active) == 1
    assert len(paused) == 1


def test_update_webhook_status():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook"
    )
    result = service.update_webhook_status(webhook.id, WebhookStatus.PAUSED)
    assert result is True
    assert service.get_webhook(webhook.id).status == WebhookStatus.PAUSED


def test_update_status_resets_failures():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook"
    )
    webhook.consecutive_failures = 5
    service.update_webhook_status(webhook.id, WebhookStatus.ACTIVE)
    assert webhook.consecutive_failures == 0


def test_create_event():
    service = KGWebhookService()
    event = service.create_event(
        event_type=WebhookEventType.CONCEPT_CREATED,
        payload={"cui": "C0001234", "name": "Diabetes"},
        correlation_id="corr-123"
    )
    assert event.id is not None
    assert event.event_type == WebhookEventType.CONCEPT_CREATED
    assert event.payload["cui"] == "C0001234"
    assert event.correlation_id == "corr-123"


def test_generate_signature():
    service = KGWebhookService()
    payload = '{"test": "data"}'
    secret = "my-secret-key"
    signature, timestamp = service.generate_signature(payload, secret)
    assert len(signature) == 64
    assert timestamp > 0


def test_generate_signature_with_timestamp():
    service = KGWebhookService()
    payload = '{"test": "data"}'
    secret = "my-secret-key"
    timestamp = 1705312200
    signature, returned_ts = service.generate_signature(payload, secret, timestamp)
    assert returned_ts == timestamp
    sig2, _ = service.generate_signature(payload, secret, timestamp)
    assert signature == sig2


def test_verify_signature_valid():
    service = KGWebhookService()
    payload = '{"test": "data"}'
    secret = "my-secret-key"
    signature, timestamp = service.generate_signature(payload, secret)
    result = service.verify_signature(payload, signature, timestamp, secret)
    assert result is True


def test_verify_signature_invalid():
    service = KGWebhookService()
    payload = '{"test": "data"}'
    secret = "my-secret-key"
    _, timestamp = service.generate_signature(payload, secret)
    try:
        service.verify_signature(payload, "invalid-signature", timestamp, secret)
        assert False, "Should have raised WebhookSignatureError"
    except WebhookSignatureError as e:
        assert "Invalid signature" in str(e)


def test_verify_signature_expired():
    service = KGWebhookService()
    payload = '{"test": "data"}'
    secret = "my-secret-key"
    old_timestamp = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
    signature, _ = service.generate_signature(payload, secret, old_timestamp)
    try:
        service.verify_signature(payload, signature, old_timestamp, secret)
        assert False, "Should have raised WebhookSignatureError"
    except WebhookSignatureError as e:
        assert "too old" in str(e)


def test_rate_limiting():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        max_requests_per_minute=3
    )
    assert service._check_rate_limit(webhook.id) is True
    assert service._check_rate_limit(webhook.id) is True
    assert service._check_rate_limit(webhook.id) is True
    assert service._check_rate_limit(webhook.id) is False


async def test_emit_event():
    service = KGWebhookService()
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


async def test_emit_event_filters_by_type():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        event_types=[WebhookEventType.CONCEPT_CREATED]
    )
    event = await service.emit_event(
        WebhookEventType.CONCEPT_DELETED,
        {"cui": "C0001234"}
    )
    assert service._event_queue.qsize() == 0


async def test_emit_event_skips_inactive_webhooks():
    service = KGWebhookService()
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


async def test_deliver_event_success():
    service = KGWebhookService()
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


async def test_deliver_event_failure():
    service = KGWebhookService()
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


async def test_deliver_event_exception():
    service = KGWebhookService()
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


async def test_deliver_event_disables_after_failures():
    service = KGWebhookService()
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
    for _ in range(10):
        await service.deliver_event(webhook.id, event)
    assert webhook.status == WebhookStatus.FAILED
    assert webhook.consecutive_failures == 10


async def test_deliver_event_nonexistent_webhook():
    service = KGWebhookService()
    event = service.create_event(
        WebhookEventType.CONCEPT_CREATED,
        {"cui": "C0001234"}
    )
    result = await service.deliver_event("nonexistent-id", event)
    assert result.success is False
    assert "not found" in result.error.lower()


async def test_deliver_event_rate_limited():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        max_requests_per_minute=1
    )
    event = service.create_event(
        WebhookEventType.CONCEPT_CREATED,
        {"cui": "C0001234"}
    )
    await service.deliver_event(webhook.id, event)
    result = await service.deliver_event(webhook.id, event)
    assert result.success is False
    assert "Rate limit" in result.error


async def test_deliver_with_retry():
    service = KGWebhookService()
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
        retry_delay_seconds=0.01
    )
    event = service.create_event(
        WebhookEventType.CONCEPT_CREATED,
        {"cui": "C0001234"}
    )
    result = await service.deliver_with_retry(webhook.id, event)
    assert result.success is True
    assert call_count == 3


def test_get_delivery_history():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook"
    )
    for i in range(5):
        attempt = DeliveryAttempt(
            id=f"attempt-{i}",
            webhook_id=webhook.id,
            event_id=f"event-{i}",
            status=DeliveryStatus.DELIVERED,
            attempted_at=datetime.utcnow() - timedelta(minutes=i)
        )
        service._delivery_attempts[webhook.id].append(attempt)
    history = service.get_delivery_history(webhook.id, limit=3)
    assert len(history) == 3
    assert history[0].id == "attempt-0"


def test_get_webhook_stats():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook"
    )
    webhook.total_deliveries = 100
    webhook.total_failures = 5
    webhook.last_delivery_at = datetime.utcnow()

    for i in range(10):
        status = DeliveryStatus.DELIVERED if i < 8 else DeliveryStatus.FAILED
        attempt = DeliveryAttempt(
            id=f"attempt-{i}",
            webhook_id=webhook.id,
            event_id=f"event-{i}",
            status=status,
            attempted_at=datetime.utcnow() - timedelta(hours=i),
            duration_ms=100.0 + i * 10
        )
        service._delivery_attempts[webhook.id].append(attempt)
    stats = service.get_webhook_stats(webhook.id)
    assert stats["webhook_id"] == webhook.id
    assert stats["total_deliveries"] == 100
    assert stats["total_failures"] == 5
    assert stats["deliveries_24h"] == 10
    assert stats["success_rate_24h"] == 0.8


def test_get_webhook_stats_nonexistent():
    service = KGWebhookService()
    stats = service.get_webhook_stats("nonexistent-id")
    assert stats is None


def test_calculate_retry_delay():
    service = KGWebhookService()
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


async def test_start_stop_service():
    service = KGWebhookService()
    await service.start()
    assert service._running is True
    assert service._worker_task is not None
    await service.stop()
    assert service._running is False


async def test_batch_events():
    service = KGWebhookService()
    webhook = service.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        batch_events=True,
        batch_max_size=3,
        batch_max_wait_seconds=10.0
    )
    for i in range(3):
        await service._add_to_batch(
            webhook.id,
            service.create_event(
                WebhookEventType.CONCEPT_CREATED,
                {"cui": f"C{i:07d}"}
            )
        )
    assert webhook.id not in service._pending_batches


def test_event_types_concept():
    assert WebhookEventType.CONCEPT_CREATED.value == "concept.created"
    assert WebhookEventType.CONCEPT_UPDATED.value == "concept.updated"
    assert WebhookEventType.CONCEPT_DELETED.value == "concept.deleted"


def test_event_types_relationship():
    assert WebhookEventType.RELATIONSHIP_CREATED.value == "relationship.created"
    assert WebhookEventType.RELATIONSHIP_UPDATED.value == "relationship.updated"
    assert WebhookEventType.RELATIONSHIP_DELETED.value == "relationship.deleted"


def test_event_types_patient():
    assert WebhookEventType.PATIENT_GRAPH_CREATED.value == "patient.graph.created"
    assert WebhookEventType.PATIENT_GRAPH_UPDATED.value == "patient.graph.updated"
    assert WebhookEventType.PATIENT_FINDING_ADDED.value == "patient.finding.added"
    assert WebhookEventType.PATIENT_MEDICATION_CHANGED.value == "patient.medication.changed"


def test_event_types_reasoning():
    assert WebhookEventType.REASONING_PATH_FOUND.value == "reasoning.path.found"
    assert WebhookEventType.CAUSAL_CHAIN_DISCOVERED.value == "reasoning.causal.discovered"
    assert WebhookEventType.MDT_SESSION_COMPLETED.value == "reasoning.mdt.completed"


def test_event_types_batch():
    assert WebhookEventType.BATCH_JOB_STARTED.value == "batch.job.started"
    assert WebhookEventType.BATCH_JOB_COMPLETED.value == "batch.job.completed"
    assert WebhookEventType.BATCH_JOB_FAILED.value == "batch.job.failed"


def test_event_types_benchmark():
    assert WebhookEventType.BENCHMARK_STARTED.value == "benchmark.started"
    assert WebhookEventType.BENCHMARK_COMPLETED.value == "benchmark.completed"


def test_event_types_system():
    assert WebhookEventType.HEALTH_STATUS_CHANGED.value == "system.health.changed"
    assert WebhookEventType.CACHE_INVALIDATED.value == "system.cache.invalidated"


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Webhook Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # Filter tests
        ("filter_matches_all_events_by_default", test_filter_matches_all_events_by_default),
        ("filter_by_event_type", test_filter_by_event_type),
        ("filter_by_patient_id", test_filter_by_patient_id),
        ("filter_by_semantic_type", test_filter_by_semantic_type),
        ("filter_by_min_confidence", test_filter_by_min_confidence),
        ("filter_with_custom_function", test_filter_with_custom_function),

        # Event tests
        ("event_to_dict", test_event_to_dict),
        ("event_to_json", test_event_to_json),

        # Service registration tests
        ("register_webhook", test_register_webhook),
        ("register_webhook_with_custom_secret", test_register_webhook_with_custom_secret),
        ("register_webhook_invalid_url", test_register_webhook_invalid_url),
        ("register_webhook_with_filters", test_register_webhook_with_filters),
        ("unregister_webhook", test_unregister_webhook),
        ("unregister_nonexistent_webhook", test_unregister_nonexistent_webhook),
        ("list_webhooks", test_list_webhooks),
        ("list_webhooks_filter_by_status", test_list_webhooks_filter_by_status),
        ("update_webhook_status", test_update_webhook_status),
        ("update_status_resets_failures", test_update_status_resets_failures),
        ("create_event", test_create_event),

        # Signature tests
        ("generate_signature", test_generate_signature),
        ("generate_signature_with_timestamp", test_generate_signature_with_timestamp),
        ("verify_signature_valid", test_verify_signature_valid),
        ("verify_signature_invalid", test_verify_signature_invalid),
        ("verify_signature_expired", test_verify_signature_expired),

        # Rate limiting tests
        ("rate_limiting", test_rate_limiting),

        # Async event tests
        ("emit_event", test_emit_event),
        ("emit_event_filters_by_type", test_emit_event_filters_by_type),
        ("emit_event_skips_inactive_webhooks", test_emit_event_skips_inactive_webhooks),

        # Delivery tests
        ("deliver_event_success", test_deliver_event_success),
        ("deliver_event_failure", test_deliver_event_failure),
        ("deliver_event_exception", test_deliver_event_exception),
        ("deliver_event_disables_after_failures", test_deliver_event_disables_after_failures),
        ("deliver_event_nonexistent_webhook", test_deliver_event_nonexistent_webhook),
        ("deliver_event_rate_limited", test_deliver_event_rate_limited),
        ("deliver_with_retry", test_deliver_with_retry),

        # History and stats tests
        ("get_delivery_history", test_get_delivery_history),
        ("get_webhook_stats", test_get_webhook_stats),
        ("get_webhook_stats_nonexistent", test_get_webhook_stats_nonexistent),
        ("calculate_retry_delay", test_calculate_retry_delay),

        # Service lifecycle tests
        ("start_stop_service", test_start_stop_service),
        ("batch_events", test_batch_events),

        # Event type tests
        ("event_types_concept", test_event_types_concept),
        ("event_types_relationship", test_event_types_relationship),
        ("event_types_patient", test_event_types_patient),
        ("event_types_reasoning", test_event_types_reasoning),
        ("event_types_batch", test_event_types_batch),
        ("event_types_benchmark", test_event_types_benchmark),
        ("event_types_system", test_event_types_system),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        if run_test(name, test):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
