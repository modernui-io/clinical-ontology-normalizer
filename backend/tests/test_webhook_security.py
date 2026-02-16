"""CISO-6: Webhook HMAC Verification Hardening Tests.

Tests cover:
- HMAC signature verification (valid, invalid, missing key, missing signature)
- Timestamp validation (fresh, stale, future, missing, malformed)
- TTL-based LRU deduplication cache (basic dedup, TTL expiry, LRU eviction)
- Redis-based deduplication (when Redis available)
- Rate limiting awareness (threshold warnings)
- Production config enforcement (webhook key required)
- End-to-end webhook security flow
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.metriport_webhook import (
    _DEDUP_TTL_SECONDS,
    _RATE_WARN_THRESHOLD,
    _RATE_WINDOW_SECONDS,
    _WEBHOOK_MAX_AGE_SECONDS,
    _RateTracker,
    _TTLLRUCache,
    _dedup_cache,
    _rate_tracker,
    _validate_webhook_timestamp,
    _verify_webhook_signature,
)
from app.main import app


# ==============================================================================
# Helpers
# ==============================================================================


def _make_signature(body: bytes, key: str) -> str:
    """Create a valid HMAC-SHA256 signature for the given body and key."""
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def _make_webhook_payload(
    message_id: str = "msg-001",
    msg_type: str = "medical.consolidated-data",
    when: str | None = None,
    ping: str | None = None,
    patients: list | None = None,
) -> dict:
    """Create a well-formed Metriport webhook payload."""
    payload: dict = {
        "meta": {
            "messageId": message_id,
            "type": msg_type,
        },
    }
    if when is not None:
        payload["meta"]["when"] = when
    if ping is not None:
        payload["ping"] = ping
    if patients is not None:
        payload["patients"] = patients
    return payload


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _past_iso(seconds: int) -> str:
    """Return a time N seconds in the past as ISO 8601 string."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _future_iso(seconds: int) -> str:
    """Return a time N seconds in the future as ISO 8601 string."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(autouse=True)
def _clean_caches():
    """Reset module-level caches before each test."""
    _dedup_cache.clear()
    _rate_tracker.clear()
    yield
    _dedup_cache.clear()
    _rate_tracker.clear()


@pytest.fixture
def webhook_key() -> str:
    return "test-webhook-secret-key-12345"


@pytest.fixture
def client_no_key():
    """Test client with no webhook key configured and Redis dedup disabled."""
    with (
        patch("app.api.metriport_webhook.settings") as mock_settings,
        patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
    ):
        mock_settings.metriport_webhook_key = None
        mock_settings.debug = True
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture
def client_with_key(webhook_key):
    """Test client with webhook key configured and Redis dedup disabled."""
    with (
        patch("app.api.metriport_webhook.settings") as mock_settings,
        patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
    ):
        mock_settings.metriport_webhook_key = webhook_key
        mock_settings.debug = False
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ==============================================================================
# Unit Tests: HMAC Signature Verification
# ==============================================================================


class TestHMACSignatureVerification:
    """Tests for _verify_webhook_signature function."""

    def test_valid_signature(self, webhook_key: str):
        """Valid HMAC-SHA256 signature should pass verification."""
        body = b'{"meta": {"messageId": "1", "type": "ping"}, "ping": "hello"}'
        sig = _make_signature(body, webhook_key)
        assert _verify_webhook_signature(body, sig, webhook_key) is True

    def test_invalid_signature(self, webhook_key: str):
        """Tampered signature should fail verification."""
        body = b'{"meta": {"messageId": "1", "type": "ping"}, "ping": "hello"}'
        assert _verify_webhook_signature(body, "bad-signature", webhook_key) is False

    def test_missing_signature_with_key(self, webhook_key: str):
        """Missing signature header when key is configured should fail."""
        body = b'{"meta": {"messageId": "1", "type": "ping"}}'
        assert _verify_webhook_signature(body, None, webhook_key) is False

    def test_no_key_configured_skips_verification(self):
        """When no webhook key is set, verification is skipped (dev mode)."""
        body = b'{"meta": {"messageId": "1", "type": "ping"}}'
        assert _verify_webhook_signature(body, None, None) is True
        assert _verify_webhook_signature(body, "anything", None) is True

    def test_empty_key_skips_verification(self):
        """Empty string key should also skip verification."""
        body = b'{"meta": {"messageId": "1", "type": "ping"}}'
        assert _verify_webhook_signature(body, None, "") is True

    def test_tampered_body(self, webhook_key: str):
        """Signature computed on original body should fail on tampered body."""
        original = b'{"meta": {"messageId": "1", "type": "ping"}}'
        sig = _make_signature(original, webhook_key)
        tampered = b'{"meta": {"messageId": "1", "type": "ping"}, "evil": true}'
        assert _verify_webhook_signature(tampered, sig, webhook_key) is False

    def test_wrong_key(self, webhook_key: str):
        """Signature with a different key should fail."""
        body = b'{"meta": {"messageId": "1", "type": "ping"}}'
        sig = _make_signature(body, "wrong-key")
        assert _verify_webhook_signature(body, sig, webhook_key) is False

    def test_timing_safe_comparison(self, webhook_key: str):
        """Verify we use constant-time comparison (hmac.compare_digest)."""
        # This test verifies the function returns a bool -- the actual
        # timing safety comes from hmac.compare_digest usage in the code.
        body = b'{"test": true}'
        sig = _make_signature(body, webhook_key)
        result = _verify_webhook_signature(body, sig, webhook_key)
        assert isinstance(result, bool)
        assert result is True


# ==============================================================================
# Unit Tests: Timestamp Validation
# ==============================================================================


class TestTimestampValidation:
    """Tests for _validate_webhook_timestamp function."""

    def test_fresh_timestamp(self):
        """Timestamp within 5-minute window should pass."""
        assert _validate_webhook_timestamp(_now_iso()) is True

    def test_slightly_old_timestamp(self):
        """Timestamp a few seconds old should pass."""
        assert _validate_webhook_timestamp(_past_iso(30)) is True

    def test_stale_timestamp_rejected(self):
        """Timestamp older than 5 minutes should be rejected."""
        stale = _past_iso(_WEBHOOK_MAX_AGE_SECONDS + 60)
        assert _validate_webhook_timestamp(stale) is False

    def test_exactly_at_boundary(self):
        """Timestamp exactly at the 5-minute boundary should be rejected (> not >=)."""
        # Just over the boundary
        stale = _past_iso(_WEBHOOK_MAX_AGE_SECONDS + 1)
        assert _validate_webhook_timestamp(stale) is False

    def test_future_timestamp_small_drift_allowed(self):
        """Small future drift (< 60s) should be allowed (clock skew tolerance)."""
        future = _future_iso(30)
        assert _validate_webhook_timestamp(future) is True

    def test_future_timestamp_large_drift_rejected(self):
        """Timestamp more than 60s in the future should be rejected."""
        future = _future_iso(120)
        assert _validate_webhook_timestamp(future) is False

    def test_none_timestamp_allowed(self):
        """None timestamp should be allowed (some message types omit it)."""
        assert _validate_webhook_timestamp(None) is True

    def test_empty_string_allowed(self):
        """Empty string timestamp should be allowed."""
        assert _validate_webhook_timestamp("") is True

    def test_malformed_timestamp_dev_mode(self):
        """Malformed timestamp in debug mode should be allowed."""
        with patch("app.api.metriport_webhook.settings") as mock_settings:
            mock_settings.debug = True
            assert _validate_webhook_timestamp("not-a-date") is True

    def test_malformed_timestamp_prod_mode(self):
        """Malformed timestamp in production mode should be rejected."""
        with patch("app.api.metriport_webhook.settings") as mock_settings:
            mock_settings.debug = False
            assert _validate_webhook_timestamp("not-a-date") is False

    def test_z_suffix_parsed(self):
        """ISO 8601 timestamp with Z suffix should be parsed correctly."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert _validate_webhook_timestamp(ts) is True

    def test_offset_suffix_parsed(self):
        """ISO 8601 timestamp with +00:00 suffix should be parsed correctly."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        assert _validate_webhook_timestamp(ts) is True


# ==============================================================================
# Unit Tests: TTL LRU Deduplication Cache
# ==============================================================================


class TestTTLLRUCache:
    """Tests for _TTLLRUCache class."""

    def test_basic_dedup(self):
        """Adding and checking the same key should detect duplicate."""
        cache = _TTLLRUCache(max_size=100, ttl_seconds=60)
        assert cache.contains("msg-1") is False
        cache.add("msg-1")
        assert cache.contains("msg-1") is True

    def test_different_keys_not_duplicate(self):
        """Different keys should not be detected as duplicates."""
        cache = _TTLLRUCache(max_size=100, ttl_seconds=60)
        cache.add("msg-1")
        assert cache.contains("msg-2") is False

    def test_ttl_expiry(self):
        """Entries should expire after TTL."""
        cache = _TTLLRUCache(max_size=100, ttl_seconds=1)
        cache.add("msg-1")
        assert cache.contains("msg-1") is True
        # Simulate time passing by manipulating the stored timestamp
        cache._cache["msg-1"] = time.monotonic() - 2.0
        assert cache.contains("msg-1") is False

    def test_lru_eviction(self):
        """Oldest entries should be evicted when cache is full."""
        cache = _TTLLRUCache(max_size=3, ttl_seconds=60)
        cache.add("msg-1")
        cache.add("msg-2")
        cache.add("msg-3")
        # Cache is full. Adding a 4th should evict the oldest (msg-1).
        cache.add("msg-4")
        assert cache.contains("msg-1") is False
        assert cache.contains("msg-2") is True
        assert cache.contains("msg-3") is True
        assert cache.contains("msg-4") is True

    def test_access_refreshes_position(self):
        """Accessing an entry should move it to the end (most recent)."""
        cache = _TTLLRUCache(max_size=3, ttl_seconds=60)
        cache.add("msg-1")
        cache.add("msg-2")
        cache.add("msg-3")
        # Access msg-1 to refresh its position
        cache.contains("msg-1")
        # Add msg-4 -- should evict msg-2 (now the oldest)
        cache.add("msg-4")
        assert cache.contains("msg-1") is True
        assert cache.contains("msg-2") is False

    def test_clear(self):
        """Clear should remove all entries."""
        cache = _TTLLRUCache(max_size=100, ttl_seconds=60)
        cache.add("msg-1")
        cache.add("msg-2")
        assert len(cache) == 2
        cache.clear()
        assert len(cache) == 0
        assert cache.contains("msg-1") is False

    def test_expired_entries_evicted_on_add(self):
        """Expired entries should be cleaned up when adding new ones."""
        cache = _TTLLRUCache(max_size=100, ttl_seconds=1)
        cache.add("msg-1")
        cache.add("msg-2")
        # Make entries expire
        for key in list(cache._cache.keys()):
            cache._cache[key] = time.monotonic() - 2.0
        cache.add("msg-3")
        # Expired entries should have been cleaned up
        assert len(cache) == 1
        assert cache.contains("msg-3") is True


# ==============================================================================
# Unit Tests: Rate Tracker
# ==============================================================================


class TestRateTracker:
    """Tests for _RateTracker class."""

    def test_records_events(self):
        """Rate tracker should count events."""
        tracker = _RateTracker(window_seconds=60, threshold=100)
        tracker.record()
        tracker.record()
        tracker.record()
        assert tracker.current_rate == 3

    def test_warning_on_threshold_exceeded(self):
        """Should log warning when rate exceeds threshold."""
        tracker = _RateTracker(window_seconds=60, threshold=3)
        tracker.record()
        tracker.record()
        tracker.record()
        with patch("app.api.metriport_webhook.logger") as mock_logger:
            tracker.record()  # 4th event exceeds threshold of 3
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "CISO-6" in call_args
            assert "threshold" in call_args

    def test_no_warning_below_threshold(self):
        """Should not log warning when rate is below threshold."""
        tracker = _RateTracker(window_seconds=60, threshold=100)
        with patch("app.api.metriport_webhook.logger") as mock_logger:
            tracker.record()
            tracker.record()
            mock_logger.warning.assert_not_called()

    def test_window_expiry(self):
        """Old events outside the window should be pruned."""
        tracker = _RateTracker(window_seconds=60, threshold=100)
        # Simulate old events by directly inserting expired timestamps
        tracker._timestamps = [time.monotonic() - 120, time.monotonic() - 90]
        tracker.record()
        # Old events should be pruned, only the new one remains
        assert tracker.current_rate == 1

    def test_clear(self):
        """Clear should reset all state."""
        tracker = _RateTracker(window_seconds=60, threshold=100)
        tracker.record()
        tracker.record()
        tracker.clear()
        assert tracker.current_rate == 0


# ==============================================================================
# Unit Tests: Redis-based Deduplication
# ==============================================================================


class TestRedisDedup:
    """Tests for Redis-based message deduplication."""

    @pytest.mark.asyncio
    async def test_redis_dedup_new_message(self):
        """New message should not be a duplicate when Redis is available."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)  # NX set succeeded

        with patch("app.core.redis.get_async_redis", new_callable=AsyncMock, return_value=mock_redis):
            from app.api.metriport_webhook import _check_dedup
            result = await _check_dedup("new-msg-001")
            assert result is False
            mock_redis.set.assert_called_once_with(
                "webhook:dedup:new-msg-001", "1", nx=True, ex=_DEDUP_TTL_SECONDS
            )

    @pytest.mark.asyncio
    async def test_redis_dedup_duplicate_message(self):
        """Duplicate message should be detected when Redis is available."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)  # NX set failed (key exists)

        with patch("app.core.redis.get_async_redis", new_callable=AsyncMock, return_value=mock_redis):
            from app.api.metriport_webhook import _check_dedup
            result = await _check_dedup("existing-msg-001")
            assert result is True

    @pytest.mark.asyncio
    async def test_fallback_to_lru_when_redis_unavailable(self):
        """When Redis is unavailable, should fall back to LRU cache."""
        with patch("app.core.redis.get_async_redis", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            from app.api.metriport_webhook import _check_dedup
            # First call -- not duplicate
            result1 = await _check_dedup("fallback-msg-001")
            assert result1 is False
            # Second call -- duplicate (found in LRU cache)
            result2 = await _check_dedup("fallback-msg-001")
            assert result2 is True


# ==============================================================================
# Integration Tests: Webhook Endpoint
# ==============================================================================


class TestWebhookEndpointSecurity:
    """Integration tests for the webhook endpoint security checks."""

    def test_valid_signature_accepted(self, webhook_key: str):
        """Webhook with valid signature should be accepted."""
        payload = _make_webhook_payload(
            message_id="int-001",
            msg_type="ping",
            ping="hello",
        )
        body = json.dumps(payload).encode()
        sig = _make_signature(body, webhook_key)

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-metriport-signature": sig,
                    },
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pong"] == "hello"

    def test_invalid_signature_rejected(self, webhook_key: str):
        """Webhook with invalid signature should return 401."""
        payload = _make_webhook_payload(msg_type="ping", ping="test")
        body = json.dumps(payload).encode()

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-metriport-signature": "bad-sig",
                    },
                )
        assert resp.status_code == 401

    def test_missing_signature_rejected_when_key_set(self, webhook_key: str):
        """Missing signature header when key is configured should return 401."""
        payload = _make_webhook_payload(msg_type="ping", ping="test")
        body = json.dumps(payload).encode()

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )
        assert resp.status_code == 401

    def test_no_key_allows_unsigned_in_dev(self):
        """Without webhook key (dev mode), unsigned webhooks should be accepted."""
        payload = _make_webhook_payload(msg_type="ping", ping="dev-test")
        body = json.dumps(payload).encode()

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = None
            mock_settings.debug = True
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )
        assert resp.status_code == 200
        assert resp.json()["pong"] == "dev-test"

    def test_stale_timestamp_rejected(self, webhook_key: str):
        """Webhook with stale timestamp should return 401."""
        stale_when = _past_iso(_WEBHOOK_MAX_AGE_SECONDS + 120)
        payload = _make_webhook_payload(
            message_id="stale-001",
            msg_type="medical.document-download",
            when=stale_when,
        )
        body = json.dumps(payload).encode()
        sig = _make_signature(body, webhook_key)

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-metriport-signature": sig,
                    },
                )
        assert resp.status_code == 401

    def test_fresh_timestamp_accepted(self, webhook_key: str):
        """Webhook with fresh timestamp should be accepted."""
        payload = _make_webhook_payload(
            message_id="fresh-001",
            msg_type="medical.document-download",
            when=_now_iso(),
        )
        body = json.dumps(payload).encode()
        sig = _make_signature(body, webhook_key)

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-metriport-signature": sig,
                    },
                )
        assert resp.status_code == 200

    def test_duplicate_message_returns_ok(self, webhook_key: str):
        """Duplicate message should return 200 with dedup message."""
        payload = _make_webhook_payload(
            message_id="dup-001",
            msg_type="medical.document-download",
            when=_now_iso(),
        )
        body = json.dumps(payload).encode()
        sig = _make_signature(body, webhook_key)

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=True),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-metriport-signature": sig,
                    },
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Duplicate message ignored"

    def test_ping_bypasses_timestamp_check(self, webhook_key: str):
        """Ping messages should not be subject to timestamp validation."""
        # Ping with a stale timestamp -- should still succeed
        stale_when = _past_iso(_WEBHOOK_MAX_AGE_SECONDS + 120)
        payload = _make_webhook_payload(
            message_id="ping-stale",
            msg_type="ping",
            when=stale_when,
            ping="test-ping",
        )
        body = json.dumps(payload).encode()
        sig = _make_signature(body, webhook_key)

        with (
            patch("app.api.metriport_webhook.settings") as mock_settings,
            patch("app.api.metriport_webhook._check_dedup", new_callable=AsyncMock, return_value=False),
        ):
            mock_settings.metriport_webhook_key = webhook_key
            mock_settings.debug = False
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/metriport/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-metriport-signature": sig,
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["pong"] == "test-ping"


# ==============================================================================
# Config Validation Tests
# ==============================================================================


class TestProductionConfigValidation:
    """Tests for production environment config enforcement."""

    def test_production_requires_webhook_key(self):
        """In production, missing METRIPORT_WEBHOOK_KEY should fail startup."""
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="production",
                auth_enabled=True,
                jwt_secret_key="secure-jwt-secret-prod-only",
                api_key="secure-api-key-prod-only",
                metriport_webhook_key=None,
            )
        error_text = str(exc_info.value)
        assert "METRIPORT_WEBHOOK_KEY" in error_text

    def test_production_passes_with_all_keys(self):
        """In production, providing all required keys should succeed."""
        from app.core.config import Settings

        # Should not raise
        s = Settings(
            environment="production",
            auth_enabled=True,
            jwt_secret_key="secure-jwt-secret-prod-only",
            api_key="secure-api-key-prod-only",
            metriport_webhook_key="secure-webhook-key-prod-only",
        )
        assert s.metriport_webhook_key == "secure-webhook-key-prod-only"

    def test_development_allows_missing_webhook_key(self):
        """In development, missing webhook key should be fine."""
        from app.core.config import Settings

        # Should not raise
        s = Settings(
            environment="development",
            metriport_webhook_key=None,
        )
        assert s.metriport_webhook_key is None
