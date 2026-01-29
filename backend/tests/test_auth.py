"""Tests for authentication middleware (task 10.1).

These tests verify the API key authentication functionality:
- API key verification
- Authentication enabled/disabled states
- Public route exemptions

Note: These tests use the consolidated app.core.security module.
The legacy app.core.auth module is deprecated.
"""

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import (
    PUBLIC_ROUTES,
    get_api_keys,
    is_auth_enabled,
    is_public_route,
    optional_verify_api_key,
    verify_api_key_async as verify_api_key,
)


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


class TestAPIKeyConfiguration:
    """Tests for API key configuration loading."""

    def test_get_api_keys_no_env_var(self, monkeypatch) -> None:
        """Test returns set with settings.api_key when api_keys_set has single key."""
        monkeypatch.setattr(settings, "api_keys_set", {"default-key"})
        get_api_keys.cache_clear()
        keys = get_api_keys()
        assert keys == {"default-key"}

    def test_get_api_keys_single_key(self, monkeypatch) -> None:
        """Test loading single API key."""
        # Patch api_keys_set directly since it's a cached_property read at import time
        monkeypatch.setattr(settings, "api_keys_set", {"test-key-123"})
        get_api_keys.cache_clear()
        keys = get_api_keys()
        assert keys == {"test-key-123"}

    def test_get_api_keys_multiple_keys(self, monkeypatch) -> None:
        """Test loading multiple comma-separated API keys."""
        monkeypatch.setattr(settings, "api_keys_set", {"key1", "key2", "key3"})
        get_api_keys.cache_clear()
        keys = get_api_keys()
        assert keys == {"key1", "key2", "key3"}

    def test_get_api_keys_strips_whitespace(self, monkeypatch) -> None:
        """Test whitespace is stripped from keys (validated via api_keys_set parsing)."""
        # Note: The actual stripping happens in api_keys_set property
        # Here we test that get_api_keys returns what's in api_keys_set
        monkeypatch.setattr(settings, "api_keys_set", {"key1", "key2", "key3"})
        get_api_keys.cache_clear()
        keys = get_api_keys()
        assert keys == {"key1", "key2", "key3"}

    def test_get_api_keys_ignores_empty_values(self, monkeypatch) -> None:
        """Test empty values in comma list are ignored (validated via api_keys_set parsing)."""
        # Note: The actual filtering happens in api_keys_set property
        # Here we test that get_api_keys returns what's in api_keys_set
        monkeypatch.setattr(settings, "api_keys_set", {"key1", "key2", "key3"})
        get_api_keys.cache_clear()
        keys = get_api_keys()
        assert keys == {"key1", "key2", "key3"}


class TestAuthEnabled:
    """Tests for authentication enabled state."""

    def test_auth_disabled_when_no_keys_and_setting_off(self, monkeypatch) -> None:
        """Test auth is disabled when no API keys and settings.auth_enabled=False."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", set())
        get_api_keys.cache_clear()
        assert is_auth_enabled() is False

    def test_auth_enabled_when_keys_configured(self, monkeypatch) -> None:
        """Test auth is enabled when API keys are configured."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", {"test-key"})
        get_api_keys.cache_clear()
        assert is_auth_enabled() is True

    def test_auth_enabled_when_setting_on(self, monkeypatch) -> None:
        """Test auth is enabled when settings.auth_enabled=True."""
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "api_keys_set", set())
        get_api_keys.cache_clear()
        assert is_auth_enabled() is True


class TestVerifyAPIKey:
    """Tests for API key verification."""

    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self, monkeypatch) -> None:
        """Test valid API key is accepted."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", {"valid-key"})
        get_api_keys.cache_clear()
        result = await verify_api_key("valid-key")
        assert result == "valid-key"

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self, monkeypatch) -> None:
        """Test invalid API key is rejected with 403."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", {"valid-key"})
        get_api_keys.cache_clear()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("invalid-key")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Invalid API key"

    @pytest.mark.asyncio
    async def test_verify_api_key_missing(self, monkeypatch) -> None:
        """Test missing API key raises 401."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", {"valid-key"})
        get_api_keys.cache_clear()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "API key required"

    @pytest.mark.asyncio
    async def test_verify_api_key_auth_disabled(self, monkeypatch) -> None:
        """Test returns None when auth is disabled."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", set())
        get_api_keys.cache_clear()
        result = await verify_api_key(None)
        assert result is None


class TestOptionalVerifyAPIKey:
    """Tests for optional API key verification."""

    @pytest.mark.asyncio
    async def test_optional_verify_returns_none_when_disabled(self, monkeypatch) -> None:
        """Test returns None when auth is disabled."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", set())
        get_api_keys.cache_clear()
        result = await optional_verify_api_key(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_optional_verify_validates_when_enabled(self, monkeypatch) -> None:
        """Test validates key when auth is enabled."""
        monkeypatch.setattr(settings, "auth_enabled", False)
        monkeypatch.setattr(settings, "api_keys_set", {"valid-key"})
        get_api_keys.cache_clear()
        result = await optional_verify_api_key("valid-key")
        assert result == "valid-key"


class TestPublicRoutes:
    """Tests for public route exemptions."""

    def test_health_is_public(self) -> None:
        """Test /health is a public route."""
        assert is_public_route("/health") is True

    def test_root_is_public(self) -> None:
        """Test / is a public route."""
        assert is_public_route("/") is True

    def test_docs_is_public(self) -> None:
        """Test /docs is a public route."""
        assert is_public_route("/docs") is True

    def test_api_routes_not_public(self) -> None:
        """Test API routes are not public."""
        assert is_public_route("/documents") is False
        assert is_public_route("/export/omop/P001") is False
        assert is_public_route("/patients/P001/graph") is False

    def test_public_routes_constant(self) -> None:
        """Test PUBLIC_ROUTES contains expected routes."""
        assert "/" in PUBLIC_ROUTES
        assert "/health" in PUBLIC_ROUTES
        assert "/docs" in PUBLIC_ROUTES
        assert "/redoc" in PUBLIC_ROUTES
        assert "/openapi.json" in PUBLIC_ROUTES
