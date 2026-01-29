"""Tests for security and authentication (Phase 10.1, 10.2)."""

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import TenantContext, get_api_keys, verify_api_key


@pytest.fixture(autouse=True)
def reset_api_keys_cache():
    """Reset the API keys cache before each test."""
    get_api_keys.cache_clear()
    # Also clear the cached_property for api_keys_set
    if "api_keys_set" in settings.__dict__:
        del settings.__dict__["api_keys_set"]
    yield
    get_api_keys.cache_clear()
    if "api_keys_set" in settings.__dict__:
        del settings.__dict__["api_keys_set"]


class TestAPIKeyAuthentication:
    """Tests for API key authentication middleware."""

    def test_verify_api_key_disabled_returns_none(self, monkeypatch) -> None:
        """When auth is disabled, verify_api_key returns None."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", set())
        get_api_keys.cache_clear()
        result = verify_api_key(api_key=None)
        assert result is None

    def test_verify_api_key_disabled_ignores_key(self, monkeypatch) -> None:
        """When auth is disabled, any key is ignored."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", set())
        get_api_keys.cache_clear()
        result = verify_api_key(api_key="any-key")
        assert result is None

    def test_verify_api_key_enabled_missing_raises_401(self, monkeypatch) -> None:
        """When auth is enabled, missing key raises 401."""
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "api_keys_set", {"correct-key"})
        get_api_keys.cache_clear()
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(api_key=None)
        assert exc_info.value.status_code == 401

    def test_verify_api_key_enabled_invalid_raises_403(self, monkeypatch) -> None:
        """When auth is enabled, invalid key raises 403."""
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "api_keys_set", {"correct-key"})
        get_api_keys.cache_clear()
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(api_key="wrong-key")
        assert exc_info.value.status_code == 403

    def test_verify_api_key_enabled_valid_returns_key(self, monkeypatch) -> None:
        """When auth is enabled, valid key returns the key."""
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "api_keys_set", {"correct-key"})
        get_api_keys.cache_clear()
        result = verify_api_key(api_key="correct-key")
        assert result == "correct-key"


class TestTenantContext:
    """Tests for tenant/patient isolation (task 10.2)."""

    def test_tenant_context_no_restriction(self) -> None:
        """TenantContext with no tenant_id allows all access."""
        ctx = TenantContext(tenant_id=None)
        assert ctx.is_authorized_for("P001")
        assert ctx.is_authorized_for("P002")
        assert ctx.is_authorized_for("any-patient")

    def test_tenant_context_with_restriction(self) -> None:
        """TenantContext with tenant_id restricts to that tenant."""
        ctx = TenantContext(tenant_id="P001")
        assert ctx.is_authorized_for("P001")
        assert not ctx.is_authorized_for("P002")
        assert not ctx.is_authorized_for("other")

    def test_tenant_context_exact_match_required(self) -> None:
        """Tenant authorization requires exact match."""
        ctx = TenantContext(tenant_id="P001")
        assert not ctx.is_authorized_for("P0011")  # Suffix doesn't match
        assert not ctx.is_authorized_for("p001")  # Case sensitive
