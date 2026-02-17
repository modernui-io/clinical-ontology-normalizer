"""Comprehensive tests for Metriport webhook processing.

VPE-1: Tests covering webhook payload parsing, event type handling,
patient data flow, error handling, deduplication, rate tracking,
and background task kickoff.

Covers:
- Ping message handling (echo pong)
- Consolidated data webhook (medical.consolidated-data)
- Document download webhook (medical.document-download)
- Document conversion webhook (medical.document-conversion)
- Network query status updates
- ADT notification handling
- Unknown message type handling
- Malformed payload rejection
- Missing required fields
- Duplicate event deduplication (TTL LRU cache)
- Rate tracker behavior
- Signature verification logic
- Timestamp validation (replay protection)
- Background task scheduling for consolidated data
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.metriport_webhook import (
    MetriportWebhookPayload,
    WebhookMeta,
    PatientConsolidatedData,
    DocumentDownloadInfo,
    _TTLLRUCache,
    _RateTracker,
    _verify_webhook_signature,
    _validate_webhook_timestamp,
    _dedup_cache,
    _rate_tracker,
    router,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def webhook_app() -> FastAPI:
    """Create a minimal FastAPI app with the webhook router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
async def client(webhook_app) -> AsyncClient:
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=webhook_app),
        base_url="http://test/api/v1",
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear dedup cache and rate tracker before each test.

    Also patches Redis to ensure dedup falls back to the in-process
    cache (which *is* cleared here) rather than hitting an external
    Redis instance that may hold stale keys from previous runs.

    Patches metriport_webhook_key to None so signature verification is
    skipped (dev mode). Tests that explicitly test signature verification
    (TestSignatureVerification) override this by patching settings themselves.
    """
    _dedup_cache.clear()
    _rate_tracker.clear()
    with (
        patch("app.core.redis.get_async_redis", new_callable=AsyncMock, side_effect=Exception("no redis in tests")),
        patch("app.api.metriport_webhook.settings") as mock_settings,
    ):
        mock_settings.metriport_webhook_key = None
        mock_settings.debug = True
        yield
    _dedup_cache.clear()
    _rate_tracker.clear()


def _make_payload(
    msg_type: str = "medical.consolidated-data",
    message_id: str = "msg-001",
    ping: str | None = None,
    patients: list | None = None,
    documents: list | None = None,
    when: str | None = None,
) -> dict:
    """Build a valid Metriport webhook payload dict."""
    payload = {
        "meta": {
            "messageId": message_id,
            "type": msg_type,
        },
    }
    if when:
        payload["meta"]["when"] = when
    if ping is not None:
        payload["ping"] = ping
    if patients is not None:
        payload["patients"] = patients
    if documents is not None:
        payload["documents"] = documents
    return payload


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Ping Tests
# =============================================================================


class TestPingHandling:
    """Tests for Metriport ping/pong verification."""

    @pytest.mark.asyncio
    async def test_ping_via_ping_field(self, client):
        """Ping value in 'ping' field is echoed back as 'pong'."""
        payload = _make_payload(msg_type="ping", ping="abc123")
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["pong"] == "abc123"

    @pytest.mark.asyncio
    async def test_ping_via_type_field(self, client):
        """Ping detected via meta.type='ping' even without ping field."""
        payload = _make_payload(msg_type="ping")
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["pong"] == ""

    @pytest.mark.asyncio
    async def test_ping_bypasses_dedup(self, client):
        """Ping messages should not be blocked by dedup."""
        payload = _make_payload(msg_type="ping", ping="test", message_id="dup-ping")
        resp1 = await client.post("/metriport/webhook", json=payload)
        resp2 = await client.post("/metriport/webhook", json=payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["pong"] == "test"
        assert resp2.json()["pong"] == "test"


# =============================================================================
# Consolidated Data Tests
# =============================================================================


class TestConsolidatedData:
    """Tests for medical.consolidated-data webhook handling."""

    @pytest.mark.asyncio
    async def test_consolidated_data_queues_patient(self, client):
        """Valid consolidated-data webhook queues patients for processing."""
        payload = _make_payload(
            msg_type="medical.consolidated-data",
            when=_now_iso(),
            patients=[{
                "patientId": "p-001",
                "externalId": "ext-001",
                "status": "completed",
                "bundle": {
                    "resourceType": "Bundle",
                    "entry": [{"resource": {"resourceType": "Patient", "id": "p-001"}}],
                },
            }],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["patients_queued"] == 1

    @pytest.mark.asyncio
    async def test_consolidated_data_skips_non_completed(self, client):
        """Patients with status != 'completed' are skipped."""
        payload = _make_payload(
            msg_type="medical.consolidated-data",
            when=_now_iso(),
            patients=[{
                "patientId": "p-002",
                "status": "processing",
                "bundle": {"resourceType": "Bundle", "entry": []},
            }],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["patients_queued"] == 0

    @pytest.mark.asyncio
    async def test_consolidated_data_skips_no_bundle(self, client):
        """Patients with no bundle data are skipped."""
        payload = _make_payload(
            msg_type="medical.consolidated-data",
            when=_now_iso(),
            patients=[{
                "patientId": "p-003",
                "status": "completed",
            }],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["patients_queued"] == 0

    @pytest.mark.asyncio
    async def test_consolidated_data_multiple_patients(self, client):
        """Multiple completed patients in one webhook are all queued."""
        patients = [
            {
                "patientId": f"p-{i}",
                "status": "completed",
                "bundle": {
                    "resourceType": "Bundle",
                    "entry": [{"resource": {"resourceType": "Patient", "id": f"p-{i}"}}],
                },
            }
            for i in range(3)
        ]
        payload = _make_payload(
            msg_type="medical.consolidated-data",
            message_id="multi-patient",
            when=_now_iso(),
            patients=patients,
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["patients_queued"] == 3

    @pytest.mark.asyncio
    async def test_consolidated_data_empty_patients_list(self, client):
        """Empty patients list still returns ok with 0 queued."""
        payload = _make_payload(
            msg_type="medical.consolidated-data",
            message_id="empty-patients",
            when=_now_iso(),
            patients=[],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["patients_queued"] == 0


# =============================================================================
# Document Download / Conversion Tests
# =============================================================================


class TestDocumentEvents:
    """Tests for document-download and document-conversion webhooks."""

    @pytest.mark.asyncio
    async def test_document_download_acknowledged(self, client):
        """Document download webhook is acknowledged."""
        payload = _make_payload(
            msg_type="medical.document-download",
            message_id="doc-dl-001",
            when=_now_iso(),
            patients=[{"patientId": "p-010", "status": "completed"}],
            documents=[{
                "id": "doc-1",
                "fileName": "chart.pdf",
                "mimeType": "application/pdf",
                "status": "downloaded",
            }],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    @pytest.mark.asyncio
    async def test_document_conversion_acknowledged(self, client):
        """Document conversion webhook is acknowledged."""
        payload = _make_payload(
            msg_type="medical.document-conversion",
            message_id="doc-conv-001",
            when=_now_iso(),
            patients=[{"patientId": "p-011", "status": "completed"}],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"


# =============================================================================
# Network Query / ADT / Unknown Type Tests
# =============================================================================


class TestOtherEventTypes:
    """Tests for network-query, ADT, and unknown webhook types."""

    @pytest.mark.asyncio
    async def test_network_query_acknowledged(self, client):
        """Network query status updates are acknowledged."""
        payload = _make_payload(
            msg_type="network-query.hie",
            message_id="nq-001",
            when=_now_iso(),
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    @pytest.mark.asyncio
    async def test_patient_adt_acknowledged(self, client):
        """Patient ADT notifications are acknowledged."""
        payload = _make_payload(
            msg_type="patient.admit",
            message_id="adt-001",
            when=_now_iso(),
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_type_acknowledged(self, client):
        """Unknown webhook types are acknowledged with 200."""
        payload = _make_payload(
            msg_type="some.unknown.event",
            message_id="unk-001",
            when=_now_iso(),
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "Unknown type" in body["message"]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for malformed payloads and missing fields."""

    @pytest.mark.asyncio
    async def test_malformed_json_returns_400(self, client):
        """Non-JSON body returns 400."""
        resp = await client.post(
            "/metriport/webhook",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_meta_returns_400(self, client):
        """Payload without meta object returns 400."""
        resp = await client.post(
            "/metriport/webhook",
            json={"ping": "test"},
        )
        # Missing required 'meta' field
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_message_id_returns_400(self, client):
        """Payload without messageId in meta returns 400."""
        resp = await client.post(
            "/metriport/webhook",
            json={"meta": {"type": "ping"}},
        )
        assert resp.status_code == 400


# =============================================================================
# Deduplication Tests
# =============================================================================


class TestDeduplication:
    """Tests for webhook message deduplication."""

    @pytest.mark.asyncio
    async def test_duplicate_message_ignored(self, client):
        """Second webhook with same messageId is ignored."""
        payload = _make_payload(
            msg_type="medical.document-download",
            message_id="dedup-test-001",
            when=_now_iso(),
            patients=[{"patientId": "p-100", "status": "completed"}],
        )
        resp1 = await client.post("/metriport/webhook", json=payload)
        assert resp1.status_code == 200

        resp2 = await client.post("/metriport/webhook", json=payload)
        assert resp2.status_code == 200
        body = resp2.json()
        assert "Duplicate" in body.get("message", "")

    def test_ttl_lru_cache_add_and_contains(self):
        """TTL LRU cache correctly tracks entries."""
        cache = _TTLLRUCache(max_size=5, ttl_seconds=60)
        cache.add("key1")
        assert cache.contains("key1")
        assert not cache.contains("key2")

    def test_ttl_lru_cache_evicts_oldest_at_capacity(self):
        """Cache evicts oldest entries when at max capacity."""
        cache = _TTLLRUCache(max_size=3, ttl_seconds=60)
        cache.add("a")
        cache.add("b")
        cache.add("c")
        cache.add("d")  # Should evict "a"
        assert not cache.contains("a")
        assert cache.contains("b")
        assert cache.contains("d")

    def test_ttl_lru_cache_clear(self):
        """Cache clear removes all entries."""
        cache = _TTLLRUCache()
        cache.add("x")
        cache.add("y")
        cache.clear()
        assert len(cache) == 0
        assert not cache.contains("x")


# =============================================================================
# Rate Tracker Tests
# =============================================================================


class TestRateTracker:
    """Tests for webhook rate monitoring."""

    def test_rate_tracker_counts_events(self):
        """Rate tracker counts events within the window."""
        tracker = _RateTracker(window_seconds=60, threshold=100)
        for _ in range(5):
            tracker.record()
        assert tracker.current_rate == 5

    def test_rate_tracker_clear(self):
        """Rate tracker clears all entries."""
        tracker = _RateTracker()
        tracker.record()
        tracker.record()
        tracker.clear()
        assert tracker.current_rate == 0


# =============================================================================
# Signature Verification Tests
# =============================================================================


class TestSignatureVerification:
    """Tests for HMAC-SHA256 webhook signature verification."""

    def test_valid_signature_passes(self):
        """Valid HMAC-SHA256 signature is accepted."""
        key = "my-secret-key"
        body = b'{"meta":{"type":"ping","messageId":"1"},"ping":"test"}'
        sig = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_webhook_signature(body, sig, key) is True

    def test_invalid_signature_fails(self):
        """Invalid signature is rejected."""
        key = "my-secret-key"
        body = b'{"test": true}'
        assert _verify_webhook_signature(body, "bad-sig", key) is False

    def test_no_key_skips_verification(self):
        """No webhook key configured skips verification (dev mode)."""
        assert _verify_webhook_signature(b"anything", None, None) is True

    def test_key_but_no_signature_fails(self):
        """Key configured but no signature header -> fail."""
        assert _verify_webhook_signature(b"data", None, "key") is False

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self, client):
        """Request with invalid signature returns 401 when key is configured."""
        payload = _make_payload(msg_type="ping", ping="test")
        with patch("app.api.metriport_webhook.settings") as mock_settings:
            mock_settings.metriport_webhook_key = "secret-key"
            mock_settings.debug = False
            resp = await client.post(
                "/metriport/webhook",
                json=payload,
                headers={"x-metriport-signature": "wrong-sig"},
            )
            assert resp.status_code == 401


# =============================================================================
# Timestamp Validation Tests
# =============================================================================


class TestTimestampValidation:
    """Tests for webhook timestamp replay protection."""

    def test_recent_timestamp_valid(self):
        """Timestamp within 5 minutes is valid."""
        now = datetime.now(timezone.utc).isoformat()
        assert _validate_webhook_timestamp(now) is True

    def test_old_timestamp_invalid(self):
        """Timestamp older than 5 minutes is invalid."""
        old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        assert _validate_webhook_timestamp(old) is False

    def test_no_timestamp_valid(self):
        """No timestamp at all is valid (some events omit it)."""
        assert _validate_webhook_timestamp(None) is True

    @pytest.mark.asyncio
    async def test_expired_timestamp_returns_401(self, client):
        """Webhook with expired timestamp returns 401."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        payload = _make_payload(
            msg_type="medical.document-download",
            message_id="ts-old-001",
            when=old_time,
            patients=[{"patientId": "p-999", "status": "completed"}],
        )
        resp = await client.post("/metriport/webhook", json=payload)
        assert resp.status_code == 401


# =============================================================================
# Payload Model Tests
# =============================================================================


class TestPayloadModels:
    """Tests for Pydantic webhook payload models."""

    def test_webhook_meta_required_fields(self):
        """WebhookMeta requires messageId and type."""
        meta = WebhookMeta(messageId="m1", type="ping")
        assert meta.messageId == "m1"
        assert meta.type == "ping"

    def test_patient_consolidated_data_defaults(self):
        """PatientConsolidatedData has sensible defaults."""
        data = PatientConsolidatedData(patientId="p-1")
        assert data.status == "completed"
        assert data.bundle is None
        assert data.externalId is None

    def test_document_download_info_optional_fields(self):
        """DocumentDownloadInfo fields are all optional."""
        doc = DocumentDownloadInfo()
        assert doc.id is None
        assert doc.fileName is None

    def test_full_payload_round_trip(self):
        """Full payload can be serialized and deserialized."""
        raw = _make_payload(
            msg_type="medical.consolidated-data",
            when=_now_iso(),
            patients=[{
                "patientId": "p-42",
                "status": "completed",
                "bundle": {"resourceType": "Bundle", "entry": []},
            }],
        )
        payload = MetriportWebhookPayload(**raw)
        assert payload.meta.type == "medical.consolidated-data"
        assert len(payload.patients) == 1
        assert payload.patients[0].patientId == "p-42"
