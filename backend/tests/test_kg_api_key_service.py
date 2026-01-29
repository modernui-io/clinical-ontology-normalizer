"""Tests for KG API Key Service."""

import pytest
import time
from datetime import datetime, timedelta, timezone

from app.services.kg_api_key_service import (
    APIKeyScope,
    APIKeyStatus,
    APIKeyRateLimit,
    APIKey,
    AuthenticationResult,
    KGAPIKeyService,
    SCOPE_PRESETS,
    get_api_key_service,
    reset_api_key_service,
)


class TestAPIKeyScope:
    """Tests for APIKeyScope enum."""

    def test_scope_values(self):
        """Verify scope values."""
        assert APIKeyScope.READ_CONCEPTS.value == "read:concepts"
        assert APIKeyScope.WRITE_PATIENTS.value == "write:patients"
        assert APIKeyScope.ADMIN_KEYS.value == "admin:keys"
        assert APIKeyScope.FULL_ACCESS.value == "*"

    def test_scope_presets(self):
        """Verify scope presets."""
        assert APIKeyScope.READ_CONCEPTS in SCOPE_PRESETS["readonly"]
        assert APIKeyScope.WRITE_CONCEPTS in SCOPE_PRESETS["full"]
        assert APIKeyScope.FULL_ACCESS in SCOPE_PRESETS["admin"]


class TestAPIKeyRateLimit:
    """Tests for APIKeyRateLimit."""

    def test_default_limits(self):
        """Test default rate limits."""
        rate_limit = APIKeyRateLimit()
        assert rate_limit.requests_per_minute == 60
        assert rate_limit.requests_per_hour == 1000
        assert rate_limit.requests_per_day == 10000
        assert rate_limit.burst_limit == 10

    def test_check_and_increment_allowed(self):
        """Test that requests within limits are allowed."""
        rate_limit = APIKeyRateLimit()
        allowed, error, retry_after = rate_limit.check_and_increment()
        assert allowed is True
        assert error is None
        assert retry_after is None
        assert rate_limit.minute_count == 1

    def test_check_and_increment_burst_exceeded(self):
        """Test burst limit exceeded."""
        rate_limit = APIKeyRateLimit(burst_limit=2)
        rate_limit.check_and_increment()
        rate_limit.check_and_increment()
        allowed, error, retry_after = rate_limit.check_and_increment()
        assert allowed is False
        assert "Burst rate limit" in error
        assert retry_after is not None

    def test_check_and_increment_minute_exceeded(self):
        """Test per-minute limit exceeded."""
        rate_limit = APIKeyRateLimit(requests_per_minute=2, burst_limit=10)
        rate_limit.check_and_increment()
        rate_limit.check_and_increment()
        allowed, error, retry_after = rate_limit.check_and_increment()
        assert allowed is False
        assert "Per-minute rate limit" in error

    def test_get_remaining(self):
        """Test getting remaining requests."""
        rate_limit = APIKeyRateLimit(burst_limit=10, requests_per_minute=60)
        rate_limit.check_and_increment()
        rate_limit.check_and_increment()
        remaining = rate_limit.get_remaining()
        assert remaining["burst"] == 8
        assert remaining["minute"] == 58

    def test_counter_reset_after_window(self):
        """Test that counters reset after time window."""
        rate_limit = APIKeyRateLimit(burst_limit=2)
        rate_limit.check_and_increment()
        rate_limit.check_and_increment()

        # Simulate time passing
        rate_limit.last_burst_reset = time.time() - 2

        allowed, error, retry_after = rate_limit.check_and_increment()
        assert allowed is True


class TestAPIKey:
    """Tests for APIKey dataclass."""

    def test_create_api_key(self):
        """Test API key creation."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            description="A test key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )
        assert api_key.key_id == "key_123"
        assert api_key.name == "Test Key"
        assert api_key.status == APIKeyStatus.ACTIVE

    def test_is_valid_active(self):
        """Test validity check for active key."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
        )
        is_valid, error = api_key.is_valid()
        assert is_valid is True
        assert error is None

    def test_is_valid_revoked(self):
        """Test validity check for revoked key."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            status=APIKeyStatus.REVOKED,
        )
        is_valid, error = api_key.is_valid()
        assert is_valid is False
        assert "revoked" in error

    def test_is_valid_suspended(self):
        """Test validity check for suspended key."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            status=APIKeyStatus.SUSPENDED,
        )
        is_valid, error = api_key.is_valid()
        assert is_valid is False
        assert "suspended" in error

    def test_is_valid_expired(self):
        """Test validity check for expired key."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        is_valid, error = api_key.is_valid()
        assert is_valid is False
        assert "expired" in error
        assert api_key.status == APIKeyStatus.EXPIRED

    def test_has_scope(self):
        """Test scope checking."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS, APIKeyScope.READ_PATIENTS},
        )
        assert api_key.has_scope(APIKeyScope.READ_CONCEPTS) is True
        assert api_key.has_scope(APIKeyScope.WRITE_CONCEPTS) is False

    def test_has_scope_full_access(self):
        """Test that FULL_ACCESS grants all scopes."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            scopes={APIKeyScope.FULL_ACCESS},
        )
        assert api_key.has_scope(APIKeyScope.READ_CONCEPTS) is True
        assert api_key.has_scope(APIKeyScope.ADMIN_SYSTEM) is True

    def test_has_any_scope(self):
        """Test checking for any of multiple scopes."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )
        assert api_key.has_any_scope({APIKeyScope.READ_CONCEPTS, APIKeyScope.WRITE_CONCEPTS}) is True
        assert api_key.has_any_scope({APIKeyScope.WRITE_CONCEPTS, APIKeyScope.ADMIN_KEYS}) is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )
        result = api_key.to_dict()
        assert result["key_id"] == "key_123"
        assert result["name"] == "Test Key"
        assert "read:concepts" in result["scopes"]
        assert "key_hash" not in result

    def test_to_dict_include_sensitive(self):
        """Test dictionary includes sensitive data when requested."""
        api_key = APIKey(
            key_id="key_123",
            key_hash="hash_abc",
            name="Test Key",
        )
        result = api_key.to_dict(include_sensitive=True)
        assert result["key_hash"] == "hash_abc"


class TestKGAPIKeyService:
    """Tests for KGAPIKeyService."""

    @pytest.fixture
    def service(self):
        return KGAPIKeyService()

    def test_generate_key(self, service):
        """Test key generation."""
        raw_key, api_key = service.generate_key(
            name="Test Key",
            description="A test key",
        )
        assert raw_key.startswith("kg_")
        assert len(raw_key) > 64
        assert api_key.key_id.startswith("key_")
        assert api_key.name == "Test Key"
        assert api_key.status == APIKeyStatus.ACTIVE

    def test_generate_key_with_scopes(self, service):
        """Test key generation with specific scopes."""
        raw_key, api_key = service.generate_key(
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS, APIKeyScope.READ_PATIENTS},
        )
        assert APIKeyScope.READ_CONCEPTS in api_key.scopes
        assert APIKeyScope.READ_PATIENTS in api_key.scopes
        assert APIKeyScope.WRITE_CONCEPTS not in api_key.scopes

    def test_generate_key_with_preset(self, service):
        """Test key generation with preset scopes."""
        raw_key, api_key = service.generate_key(
            name="Admin Key",
            preset="admin",
        )
        assert APIKeyScope.FULL_ACCESS in api_key.scopes

    def test_generate_key_with_expiry(self, service):
        """Test key generation with expiry."""
        raw_key, api_key = service.generate_key(
            name="Expiring Key",
            expires_in_days=30,
        )
        assert api_key.expires_at is not None
        assert api_key.expires_at > datetime.now(timezone.utc)

    def test_generate_key_with_rate_limit(self, service):
        """Test key generation with custom rate limit."""
        rate_limit = APIKeyRateLimit(requests_per_minute=100)
        raw_key, api_key = service.generate_key(
            name="High Rate Key",
            rate_limit=rate_limit,
        )
        assert api_key.rate_limit.requests_per_minute == 100

    def test_authenticate_valid_key(self, service):
        """Test successful authentication."""
        raw_key, api_key = service.generate_key(name="Test Key")
        result = service.authenticate(raw_key)
        assert result.authenticated is True
        assert result.key is not None
        assert result.key.key_id == api_key.key_id

    def test_authenticate_invalid_format(self, service):
        """Test authentication with invalid key format."""
        result = service.authenticate("invalid_key")
        assert result.authenticated is False
        assert "Invalid API key format" in result.error

    def test_authenticate_invalid_key(self, service):
        """Test authentication with non-existent key."""
        result = service.authenticate("kg_" + "0" * 64)
        assert result.authenticated is False
        assert "Invalid API key" in result.error

    def test_authenticate_revoked_key(self, service):
        """Test authentication with revoked key."""
        raw_key, api_key = service.generate_key(name="Test Key")
        service.revoke_key(api_key.key_id)
        result = service.authenticate(raw_key)
        assert result.authenticated is False
        assert "revoked" in result.error

    def test_authenticate_rate_limited(self, service):
        """Test authentication when rate limited."""
        rate_limit = APIKeyRateLimit(burst_limit=1)
        raw_key, api_key = service.generate_key(
            name="Test Key",
            rate_limit=rate_limit,
        )
        service.authenticate(raw_key)
        result = service.authenticate(raw_key)
        assert result.authenticated is False
        assert "rate limit" in result.error.lower()
        assert result.retry_after is not None

    def test_authorize_with_scope(self, service):
        """Test authorization with required scope."""
        raw_key, api_key = service.generate_key(
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )
        result = service.authorize(raw_key, APIKeyScope.READ_CONCEPTS)
        assert result.authenticated is True

    def test_authorize_missing_scope(self, service):
        """Test authorization with missing scope."""
        raw_key, api_key = service.generate_key(
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )
        result = service.authorize(raw_key, APIKeyScope.WRITE_CONCEPTS)
        assert result.authenticated is False
        assert "Missing required scope" in result.error

    def test_get_key(self, service):
        """Test getting a key by ID."""
        raw_key, api_key = service.generate_key(name="Test Key")
        retrieved = service.get_key(api_key.key_id)
        assert retrieved is not None
        assert retrieved.key_id == api_key.key_id

    def test_get_key_not_found(self, service):
        """Test getting non-existent key."""
        retrieved = service.get_key("nonexistent")
        assert retrieved is None

    def test_list_keys(self, service):
        """Test listing keys."""
        service.generate_key(name="Key 1")
        service.generate_key(name="Key 2")
        keys = service.list_keys()
        assert len(keys) == 2

    def test_list_keys_filter_by_status(self, service):
        """Test listing keys filtered by status."""
        raw_key1, api_key1 = service.generate_key(name="Key 1")
        service.generate_key(name="Key 2")
        service.suspend_key(api_key1.key_id)

        active_keys = service.list_keys(status=APIKeyStatus.ACTIVE)
        assert len(active_keys) == 1

    def test_list_keys_filter_by_creator(self, service):
        """Test listing keys filtered by creator."""
        service.generate_key(name="Key 1", created_by="user1")
        service.generate_key(name="Key 2", created_by="user2")

        user1_keys = service.list_keys(created_by="user1")
        assert len(user1_keys) == 1
        assert user1_keys[0].created_by == "user1"

    def test_revoke_key(self, service):
        """Test key revocation."""
        raw_key, api_key = service.generate_key(name="Test Key")
        result = service.revoke_key(api_key.key_id, reason="Security concern")
        assert result is True

        retrieved = service.get_key(api_key.key_id)
        assert retrieved.status == APIKeyStatus.REVOKED
        assert "revocation_reason" in retrieved.metadata

    def test_revoke_key_not_found(self, service):
        """Test revoking non-existent key."""
        result = service.revoke_key("nonexistent")
        assert result is False

    def test_suspend_key(self, service):
        """Test key suspension."""
        raw_key, api_key = service.generate_key(name="Test Key")
        result = service.suspend_key(api_key.key_id)
        assert result is True

        retrieved = service.get_key(api_key.key_id)
        assert retrieved.status == APIKeyStatus.SUSPENDED

    def test_reactivate_key(self, service):
        """Test key reactivation."""
        raw_key, api_key = service.generate_key(name="Test Key")
        service.suspend_key(api_key.key_id)
        result = service.reactivate_key(api_key.key_id)
        assert result is True

        retrieved = service.get_key(api_key.key_id)
        assert retrieved.status == APIKeyStatus.ACTIVE

    def test_reactivate_non_suspended_key(self, service):
        """Test reactivating a non-suspended key fails."""
        raw_key, api_key = service.generate_key(name="Test Key")
        result = service.reactivate_key(api_key.key_id)
        assert result is False

    def test_rotate_key(self, service):
        """Test key rotation."""
        raw_key, api_key = service.generate_key(
            name="Original Key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )

        new_raw_key, new_key = service.rotate_key(api_key.key_id, grace_period_hours=24)

        assert new_raw_key is not None
        assert new_key is not None
        assert new_key.key_id != api_key.key_id
        assert new_raw_key != raw_key

        # Old key should have expiry set
        old_key = service.get_key(api_key.key_id)
        assert old_key.expires_at is not None
        assert "rotated_to" in old_key.metadata

    def test_rotate_key_preserves_scopes(self, service):
        """Test that rotation preserves scopes."""
        raw_key, api_key = service.generate_key(
            name="Original Key",
            scopes={APIKeyScope.READ_CONCEPTS, APIKeyScope.READ_PATIENTS},
        )

        new_raw_key, new_key = service.rotate_key(api_key.key_id)
        assert APIKeyScope.READ_CONCEPTS in new_key.scopes
        assert APIKeyScope.READ_PATIENTS in new_key.scopes

    def test_rotate_key_not_found(self, service):
        """Test rotating non-existent key."""
        new_raw_key, new_key = service.rotate_key("nonexistent")
        assert new_raw_key is None
        assert new_key is None

    def test_update_scopes(self, service):
        """Test updating key scopes."""
        raw_key, api_key = service.generate_key(
            name="Test Key",
            scopes={APIKeyScope.READ_CONCEPTS},
        )

        result = service.update_scopes(
            api_key.key_id,
            {APIKeyScope.READ_CONCEPTS, APIKeyScope.WRITE_CONCEPTS},
        )
        assert result is True

        retrieved = service.get_key(api_key.key_id)
        assert APIKeyScope.WRITE_CONCEPTS in retrieved.scopes

    def test_update_rate_limit(self, service):
        """Test updating rate limit."""
        raw_key, api_key = service.generate_key(name="Test Key")
        new_limit = APIKeyRateLimit(requests_per_minute=200)

        result = service.update_rate_limit(api_key.key_id, new_limit)
        assert result is True

        retrieved = service.get_key(api_key.key_id)
        assert retrieved.rate_limit.requests_per_minute == 200

    def test_get_usage_stats(self, service):
        """Test getting usage statistics."""
        raw_key, api_key = service.generate_key(name="Test Key")
        service.authenticate(raw_key)
        service.authenticate(raw_key)

        stats = service.get_usage_stats(api_key.key_id)
        assert stats is not None
        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 2

    def test_get_usage_stats_not_found(self, service):
        """Test getting stats for non-existent key."""
        stats = service.get_usage_stats("nonexistent")
        assert stats is None

    def test_get_service_stats(self, service):
        """Test getting service-level statistics."""
        service.generate_key(name="Key 1")
        raw_key, api_key = service.generate_key(name="Key 2")
        service.authenticate(raw_key)

        stats = service.get_service_stats()
        assert stats["total_keys"] == 2
        assert stats["keys_created"] == 2
        assert stats["total_authentications"] >= 1

    def test_add_listener(self, service):
        """Test adding event listener."""
        events = []

        def listener(event_type, key_id, api_key):
            events.append((event_type, key_id))

        service.add_listener(listener)
        raw_key, api_key = service.generate_key(name="Test Key")

        assert len(events) == 1
        assert events[0][0] == "created"

    def test_remove_listener(self, service):
        """Test removing event listener."""
        events = []

        def listener(event_type, key_id, api_key):
            events.append(event_type)

        service.add_listener(listener)
        service.generate_key(name="Key 1")

        service.remove_listener(listener)
        service.generate_key(name="Key 2")

        assert len(events) == 1

    def test_delete_key(self, service):
        """Test permanent key deletion."""
        raw_key, api_key = service.generate_key(name="Test Key")
        result = service.delete_key(api_key.key_id)
        assert result is True

        retrieved = service.get_key(api_key.key_id)
        assert retrieved is None

    def test_delete_key_not_found(self, service):
        """Test deleting non-existent key."""
        result = service.delete_key("nonexistent")
        assert result is False

    def test_cleanup_expired(self, service):
        """Test cleanup of expired keys."""
        # Create expired key
        raw_key, api_key = service.generate_key(
            name="Expired Key",
            expires_in_days=0,
        )
        api_key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # Create valid key
        service.generate_key(name="Valid Key")

        removed = service.cleanup_expired()
        assert removed == 1
        assert len(service.list_keys(include_expired=True)) == 1

    def test_authentication_updates_usage(self, service):
        """Test that authentication updates usage tracking."""
        raw_key, api_key = service.generate_key(name="Test Key")

        assert api_key.total_requests == 0
        assert api_key.last_used_at is None

        service.authenticate(raw_key)

        retrieved = service.get_key(api_key.key_id)
        assert retrieved.total_requests == 1
        assert retrieved.successful_requests == 1
        assert retrieved.last_used_at is not None


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_api_key_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        reset_api_key_service()
        s1 = get_api_key_service()
        s2 = get_api_key_service()
        assert s1 is s2
        reset_api_key_service()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
