#!/usr/bin/env python3
"""Standalone test runner for KG API Key Service tests."""

import sys
import os
import importlib.util
import traceback
import time
from datetime import datetime, timedelta

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

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_api_key_service",
    "app/services/kg_api_key_service.py",
    submodule_search_locations=[]
)
api_key_module = importlib.util.module_from_spec(spec)
api_key_module.__package__ = "app.services"
sys.modules["app.services.kg_api_key_service"] = api_key_module
spec.loader.exec_module(api_key_module)

# Import the module under test
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


def run_test(name, test_func):
    """Run a single test."""
    try:
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


# APIKeyScope tests
def test_scope_values():
    assert APIKeyScope.READ_CONCEPTS.value == "read:concepts"
    assert APIKeyScope.WRITE_PATIENTS.value == "write:patients"
    assert APIKeyScope.ADMIN_KEYS.value == "admin:keys"
    assert APIKeyScope.FULL_ACCESS.value == "*"


def test_scope_presets():
    assert APIKeyScope.READ_CONCEPTS in SCOPE_PRESETS["readonly"]
    assert APIKeyScope.WRITE_CONCEPTS in SCOPE_PRESETS["full"]
    assert APIKeyScope.FULL_ACCESS in SCOPE_PRESETS["admin"]


# APIKeyRateLimit tests
def test_default_limits():
    rate_limit = APIKeyRateLimit()
    assert rate_limit.requests_per_minute == 60
    assert rate_limit.requests_per_hour == 1000
    assert rate_limit.requests_per_day == 10000
    assert rate_limit.burst_limit == 10


def test_check_and_increment_allowed():
    rate_limit = APIKeyRateLimit()
    allowed, error, retry_after = rate_limit.check_and_increment()
    assert allowed is True
    assert error is None
    assert retry_after is None
    assert rate_limit.minute_count == 1


def test_check_and_increment_burst_exceeded():
    rate_limit = APIKeyRateLimit(burst_limit=2)
    rate_limit.check_and_increment()
    rate_limit.check_and_increment()
    allowed, error, retry_after = rate_limit.check_and_increment()
    assert allowed is False
    assert "Burst rate limit" in error
    assert retry_after is not None


def test_check_and_increment_minute_exceeded():
    rate_limit = APIKeyRateLimit(requests_per_minute=2, burst_limit=10)
    rate_limit.check_and_increment()
    rate_limit.check_and_increment()
    allowed, error, retry_after = rate_limit.check_and_increment()
    assert allowed is False
    assert "Per-minute rate limit" in error


def test_get_remaining():
    rate_limit = APIKeyRateLimit(burst_limit=10, requests_per_minute=60)
    rate_limit.check_and_increment()
    rate_limit.check_and_increment()
    remaining = rate_limit.get_remaining()
    assert remaining["burst"] == 8
    assert remaining["minute"] == 58


def test_counter_reset_after_window():
    rate_limit = APIKeyRateLimit(burst_limit=2)
    rate_limit.check_and_increment()
    rate_limit.check_and_increment()
    rate_limit.last_burst_reset = time.time() - 2
    allowed, error, retry_after = rate_limit.check_and_increment()
    assert allowed is True


# APIKey tests
def test_create_api_key():
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


def test_is_valid_active():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
    )
    is_valid, error = api_key.is_valid()
    assert is_valid is True
    assert error is None


def test_is_valid_revoked():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
        status=APIKeyStatus.REVOKED,
    )
    is_valid, error = api_key.is_valid()
    assert is_valid is False
    assert "revoked" in error


def test_is_valid_suspended():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
        status=APIKeyStatus.SUSPENDED,
    )
    is_valid, error = api_key.is_valid()
    assert is_valid is False
    assert "suspended" in error


def test_is_valid_expired():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    is_valid, error = api_key.is_valid()
    assert is_valid is False
    assert "expired" in error
    assert api_key.status == APIKeyStatus.EXPIRED


def test_has_scope():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
        scopes={APIKeyScope.READ_CONCEPTS, APIKeyScope.READ_PATIENTS},
    )
    assert api_key.has_scope(APIKeyScope.READ_CONCEPTS) is True
    assert api_key.has_scope(APIKeyScope.WRITE_CONCEPTS) is False


def test_has_scope_full_access():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
        scopes={APIKeyScope.FULL_ACCESS},
    )
    assert api_key.has_scope(APIKeyScope.READ_CONCEPTS) is True
    assert api_key.has_scope(APIKeyScope.ADMIN_SYSTEM) is True


def test_has_any_scope():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
        scopes={APIKeyScope.READ_CONCEPTS},
    )
    assert api_key.has_any_scope({APIKeyScope.READ_CONCEPTS, APIKeyScope.WRITE_CONCEPTS}) is True
    assert api_key.has_any_scope({APIKeyScope.WRITE_CONCEPTS, APIKeyScope.ADMIN_KEYS}) is False


def test_to_dict():
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


def test_to_dict_include_sensitive():
    api_key = APIKey(
        key_id="key_123",
        key_hash="hash_abc",
        name="Test Key",
    )
    result = api_key.to_dict(include_sensitive=True)
    assert result["key_hash"] == "hash_abc"


# KGAPIKeyService tests
def test_generate_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Test Key",
        description="A test key",
    )
    assert raw_key.startswith("kg_")
    assert len(raw_key) > 64
    assert api_key.key_id.startswith("key_")
    assert api_key.name == "Test Key"
    assert api_key.status == APIKeyStatus.ACTIVE


def test_generate_key_with_scopes():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Test Key",
        scopes={APIKeyScope.READ_CONCEPTS, APIKeyScope.READ_PATIENTS},
    )
    assert APIKeyScope.READ_CONCEPTS in api_key.scopes
    assert APIKeyScope.READ_PATIENTS in api_key.scopes
    assert APIKeyScope.WRITE_CONCEPTS not in api_key.scopes


def test_generate_key_with_preset():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Admin Key",
        preset="admin",
    )
    assert APIKeyScope.FULL_ACCESS in api_key.scopes


def test_generate_key_with_expiry():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Expiring Key",
        expires_in_days=30,
    )
    assert api_key.expires_at is not None
    assert api_key.expires_at > datetime.utcnow()


def test_generate_key_with_rate_limit():
    service = KGAPIKeyService()
    rate_limit = APIKeyRateLimit(requests_per_minute=100)
    raw_key, api_key = service.generate_key(
        name="High Rate Key",
        rate_limit=rate_limit,
    )
    assert api_key.rate_limit.requests_per_minute == 100


def test_authenticate_valid_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    result = service.authenticate(raw_key)
    assert result.authenticated is True
    assert result.key is not None
    assert result.key.key_id == api_key.key_id


def test_authenticate_invalid_format():
    service = KGAPIKeyService()
    result = service.authenticate("invalid_key")
    assert result.authenticated is False
    assert "Invalid API key format" in result.error


def test_authenticate_invalid_key():
    service = KGAPIKeyService()
    result = service.authenticate("kg_" + "0" * 64)
    assert result.authenticated is False
    assert "Invalid API key" in result.error


def test_authenticate_revoked_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    service.revoke_key(api_key.key_id)
    result = service.authenticate(raw_key)
    assert result.authenticated is False
    assert "revoked" in result.error


def test_authenticate_rate_limited():
    service = KGAPIKeyService()
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


def test_authorize_with_scope():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Test Key",
        scopes={APIKeyScope.READ_CONCEPTS},
    )
    result = service.authorize(raw_key, APIKeyScope.READ_CONCEPTS)
    assert result.authenticated is True


def test_authorize_missing_scope():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Test Key",
        scopes={APIKeyScope.READ_CONCEPTS},
    )
    result = service.authorize(raw_key, APIKeyScope.WRITE_CONCEPTS)
    assert result.authenticated is False
    assert "Missing required scope" in result.error


def test_get_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    retrieved = service.get_key(api_key.key_id)
    assert retrieved is not None
    assert retrieved.key_id == api_key.key_id


def test_get_key_not_found():
    service = KGAPIKeyService()
    retrieved = service.get_key("nonexistent")
    assert retrieved is None


def test_list_keys():
    service = KGAPIKeyService()
    service.generate_key(name="Key 1")
    service.generate_key(name="Key 2")
    keys = service.list_keys()
    assert len(keys) == 2


def test_list_keys_filter_by_status():
    service = KGAPIKeyService()
    raw_key1, api_key1 = service.generate_key(name="Key 1")
    service.generate_key(name="Key 2")
    service.suspend_key(api_key1.key_id)
    active_keys = service.list_keys(status=APIKeyStatus.ACTIVE)
    assert len(active_keys) == 1


def test_list_keys_filter_by_creator():
    service = KGAPIKeyService()
    service.generate_key(name="Key 1", created_by="user1")
    service.generate_key(name="Key 2", created_by="user2")
    user1_keys = service.list_keys(created_by="user1")
    assert len(user1_keys) == 1
    assert user1_keys[0].created_by == "user1"


def test_revoke_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    result = service.revoke_key(api_key.key_id, reason="Security concern")
    assert result is True
    retrieved = service.get_key(api_key.key_id)
    assert retrieved.status == APIKeyStatus.REVOKED
    assert "revocation_reason" in retrieved.metadata


def test_revoke_key_not_found():
    service = KGAPIKeyService()
    result = service.revoke_key("nonexistent")
    assert result is False


def test_suspend_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    result = service.suspend_key(api_key.key_id)
    assert result is True
    retrieved = service.get_key(api_key.key_id)
    assert retrieved.status == APIKeyStatus.SUSPENDED


def test_reactivate_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    service.suspend_key(api_key.key_id)
    result = service.reactivate_key(api_key.key_id)
    assert result is True
    retrieved = service.get_key(api_key.key_id)
    assert retrieved.status == APIKeyStatus.ACTIVE


def test_reactivate_non_suspended_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    result = service.reactivate_key(api_key.key_id)
    assert result is False


def test_rotate_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Original Key",
        scopes={APIKeyScope.READ_CONCEPTS},
    )
    new_raw_key, new_key = service.rotate_key(api_key.key_id, grace_period_hours=24)
    assert new_raw_key is not None
    assert new_key is not None
    assert new_key.key_id != api_key.key_id
    assert new_raw_key != raw_key
    old_key = service.get_key(api_key.key_id)
    assert old_key.expires_at is not None
    assert "rotated_to" in old_key.metadata


def test_rotate_key_preserves_scopes():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Original Key",
        scopes={APIKeyScope.READ_CONCEPTS, APIKeyScope.READ_PATIENTS},
    )
    new_raw_key, new_key = service.rotate_key(api_key.key_id)
    assert APIKeyScope.READ_CONCEPTS in new_key.scopes
    assert APIKeyScope.READ_PATIENTS in new_key.scopes


def test_rotate_key_not_found():
    service = KGAPIKeyService()
    new_raw_key, new_key = service.rotate_key("nonexistent")
    assert new_raw_key is None
    assert new_key is None


def test_update_scopes():
    service = KGAPIKeyService()
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


def test_update_rate_limit():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    new_limit = APIKeyRateLimit(requests_per_minute=200)
    result = service.update_rate_limit(api_key.key_id, new_limit)
    assert result is True
    retrieved = service.get_key(api_key.key_id)
    assert retrieved.rate_limit.requests_per_minute == 200


def test_get_usage_stats():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    service.authenticate(raw_key)
    service.authenticate(raw_key)
    stats = service.get_usage_stats(api_key.key_id)
    assert stats is not None
    assert stats["total_requests"] == 2
    assert stats["successful_requests"] == 2


def test_get_usage_stats_not_found():
    service = KGAPIKeyService()
    stats = service.get_usage_stats("nonexistent")
    assert stats is None


def test_get_service_stats():
    service = KGAPIKeyService()
    service.generate_key(name="Key 1")
    raw_key, api_key = service.generate_key(name="Key 2")
    service.authenticate(raw_key)
    stats = service.get_service_stats()
    assert stats["total_keys"] == 2
    assert stats["keys_created"] == 2
    assert stats["total_authentications"] >= 1


def test_add_listener():
    service = KGAPIKeyService()
    events = []

    def listener(event_type, key_id, api_key):
        events.append((event_type, key_id))

    service.add_listener(listener)
    raw_key, api_key = service.generate_key(name="Test Key")
    assert len(events) == 1
    assert events[0][0] == "created"


def test_remove_listener():
    service = KGAPIKeyService()
    events = []

    def listener(event_type, key_id, api_key):
        events.append(event_type)

    service.add_listener(listener)
    service.generate_key(name="Key 1")
    service.remove_listener(listener)
    service.generate_key(name="Key 2")
    assert len(events) == 1


def test_delete_key():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    result = service.delete_key(api_key.key_id)
    assert result is True
    retrieved = service.get_key(api_key.key_id)
    assert retrieved is None


def test_delete_key_not_found():
    service = KGAPIKeyService()
    result = service.delete_key("nonexistent")
    assert result is False


def test_cleanup_expired():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(
        name="Expired Key",
        expires_in_days=0,
    )
    api_key.expires_at = datetime.utcnow() - timedelta(hours=1)
    service.generate_key(name="Valid Key")
    removed = service.cleanup_expired()
    assert removed == 1
    assert len(service.list_keys(include_expired=True)) == 1


def test_authentication_updates_usage():
    service = KGAPIKeyService()
    raw_key, api_key = service.generate_key(name="Test Key")
    assert api_key.total_requests == 0
    assert api_key.last_used_at is None
    service.authenticate(raw_key)
    retrieved = service.get_key(api_key.key_id)
    assert retrieved.total_requests == 1
    assert retrieved.successful_requests == 1
    assert retrieved.last_used_at is not None


def test_singleton_returns_same_instance():
    reset_api_key_service()
    s1 = get_api_key_service()
    s2 = get_api_key_service()
    assert s1 is s2
    reset_api_key_service()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG API Key Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # APIKeyScope tests
        ("scope_values", test_scope_values),
        ("scope_presets", test_scope_presets),

        # APIKeyRateLimit tests
        ("default_limits", test_default_limits),
        ("check_and_increment_allowed", test_check_and_increment_allowed),
        ("check_and_increment_burst_exceeded", test_check_and_increment_burst_exceeded),
        ("check_and_increment_minute_exceeded", test_check_and_increment_minute_exceeded),
        ("get_remaining", test_get_remaining),
        ("counter_reset_after_window", test_counter_reset_after_window),

        # APIKey tests
        ("create_api_key", test_create_api_key),
        ("is_valid_active", test_is_valid_active),
        ("is_valid_revoked", test_is_valid_revoked),
        ("is_valid_suspended", test_is_valid_suspended),
        ("is_valid_expired", test_is_valid_expired),
        ("has_scope", test_has_scope),
        ("has_scope_full_access", test_has_scope_full_access),
        ("has_any_scope", test_has_any_scope),
        ("to_dict", test_to_dict),
        ("to_dict_include_sensitive", test_to_dict_include_sensitive),

        # KGAPIKeyService tests
        ("generate_key", test_generate_key),
        ("generate_key_with_scopes", test_generate_key_with_scopes),
        ("generate_key_with_preset", test_generate_key_with_preset),
        ("generate_key_with_expiry", test_generate_key_with_expiry),
        ("generate_key_with_rate_limit", test_generate_key_with_rate_limit),
        ("authenticate_valid_key", test_authenticate_valid_key),
        ("authenticate_invalid_format", test_authenticate_invalid_format),
        ("authenticate_invalid_key", test_authenticate_invalid_key),
        ("authenticate_revoked_key", test_authenticate_revoked_key),
        ("authenticate_rate_limited", test_authenticate_rate_limited),
        ("authorize_with_scope", test_authorize_with_scope),
        ("authorize_missing_scope", test_authorize_missing_scope),
        ("get_key", test_get_key),
        ("get_key_not_found", test_get_key_not_found),
        ("list_keys", test_list_keys),
        ("list_keys_filter_by_status", test_list_keys_filter_by_status),
        ("list_keys_filter_by_creator", test_list_keys_filter_by_creator),
        ("revoke_key", test_revoke_key),
        ("revoke_key_not_found", test_revoke_key_not_found),
        ("suspend_key", test_suspend_key),
        ("reactivate_key", test_reactivate_key),
        ("reactivate_non_suspended_key", test_reactivate_non_suspended_key),
        ("rotate_key", test_rotate_key),
        ("rotate_key_preserves_scopes", test_rotate_key_preserves_scopes),
        ("rotate_key_not_found", test_rotate_key_not_found),
        ("update_scopes", test_update_scopes),
        ("update_rate_limit", test_update_rate_limit),
        ("get_usage_stats", test_get_usage_stats),
        ("get_usage_stats_not_found", test_get_usage_stats_not_found),
        ("get_service_stats", test_get_service_stats),
        ("add_listener", test_add_listener),
        ("remove_listener", test_remove_listener),
        ("delete_key", test_delete_key),
        ("delete_key_not_found", test_delete_key_not_found),
        ("cleanup_expired", test_cleanup_expired),
        ("authentication_updates_usage", test_authentication_updates_usage),
        ("singleton_returns_same_instance", test_singleton_returns_same_instance),
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
