"""
Tests for KG Authentication Middleware.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.middleware.kg_auth_middleware import (
    AuthErrorCode,
    AuthResult,
    EndpointAuthConfig,
    AuthMiddlewareConfig,
    ScopeRegistry,
    RateLimitTracker,
    MockAPIKeyService,
    KGAuthMiddleware,
    get_current_auth,
    require_scope,
    require_any_scope,
    require_all_scopes,
    create_kg_auth_middleware,
)


# ============================================================
# AuthResult Tests
# ============================================================

class TestAuthResult:
    """Tests for AuthResult dataclass."""

    def test_success_result(self):
        """Test successful auth result."""
        result = AuthResult(
            success=True,
            key_id="key123",
            key_name="Test Key",
            scopes=["read:concepts", "read:patients"],
            metadata={"org": "test"}
        )

        assert result.success is True
        assert result.key_id == "key123"
        assert result.key_name == "Test Key"
        assert len(result.scopes) == 2
        assert result.error_code is None

    def test_failure_result(self):
        """Test failed auth result."""
        result = AuthResult(
            success=False,
            error_code=AuthErrorCode.INVALID_API_KEY,
            error_message="Invalid API key"
        )

        assert result.success is False
        assert result.error_code == AuthErrorCode.INVALID_API_KEY
        assert result.key_id is None

    def test_rate_limit_info(self):
        """Test rate limit info in result."""
        reset_time = datetime.now() + timedelta(hours=1)
        result = AuthResult(
            success=True,
            key_id="key123",
            rate_limit_remaining=500,
            rate_limit_reset=reset_time
        )

        assert result.rate_limit_remaining == 500
        assert result.rate_limit_reset == reset_time


# ============================================================
# EndpointAuthConfig Tests
# ============================================================

class TestEndpointAuthConfig:
    """Tests for EndpointAuthConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = EndpointAuthConfig()

        assert config.required_scopes == []
        assert config.require_any_scope is False
        assert config.rate_limit_override is None
        assert config.allow_unauthenticated is False
        assert config.audit_access is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = EndpointAuthConfig(
            required_scopes=["read:concepts", "read:patients"],
            require_any_scope=True,
            rate_limit_override=50,
            allow_unauthenticated=False,
            audit_access=True
        )

        assert config.required_scopes == ["read:concepts", "read:patients"]
        assert config.require_any_scope is True
        assert config.rate_limit_override == 50


# ============================================================
# ScopeRegistry Tests
# ============================================================

class TestScopeRegistry:
    """Tests for ScopeRegistry."""

    def test_default_scopes_initialized(self):
        """Test default scopes are initialized."""
        registry = ScopeRegistry()

        # Health endpoints should allow unauthenticated
        config = registry.get_config("/kg/health/liveness", "GET")
        assert config.allow_unauthenticated is True

    def test_register_endpoint(self):
        """Test registering exact endpoint."""
        registry = ScopeRegistry()
        config = EndpointAuthConfig(required_scopes=["custom:scope"])

        registry.register_endpoint("/custom/endpoint", config)

        result = registry.get_config("/custom/endpoint", "GET")
        assert result.required_scopes == ["custom:scope"]

    def test_register_endpoint_with_method(self):
        """Test registering endpoint with specific method."""
        registry = ScopeRegistry()

        registry.register_endpoint(
            "/api/resource",
            EndpointAuthConfig(required_scopes=["read:resource"]),
            methods=["GET"]
        )
        registry.register_endpoint(
            "/api/resource",
            EndpointAuthConfig(required_scopes=["write:resource"]),
            methods=["POST"]
        )

        get_config = registry.get_config("/api/resource", "GET")
        post_config = registry.get_config("/api/resource", "POST")

        assert get_config.required_scopes == ["read:resource"]
        assert post_config.required_scopes == ["write:resource"]

    def test_register_pattern(self):
        """Test registering URL pattern."""
        registry = ScopeRegistry()
        config = EndpointAuthConfig(required_scopes=["admin:*"])

        registry.register_pattern("/admin", config)

        # All admin paths should match
        assert registry.get_config("/admin/users", "GET").required_scopes == ["admin:*"]
        assert registry.get_config("/admin/settings", "GET").required_scopes == ["admin:*"]

    def test_set_default_config(self):
        """Test setting default config."""
        registry = ScopeRegistry()
        default = EndpointAuthConfig(required_scopes=["default:scope"])

        registry.set_default_config(default)

        # Unknown path should return default
        config = registry.get_config("/unknown/path", "GET")
        assert config.required_scopes == ["default:scope"]


# ============================================================
# RateLimitTracker Tests
# ============================================================

class TestRateLimitTracker:
    """Tests for RateLimitTracker."""

    def test_first_request_allowed(self):
        """Test first request is always allowed."""
        tracker = RateLimitTracker(default_limit=100)

        allowed, remaining, reset = tracker.check_and_increment("key1")

        assert allowed is True
        assert remaining == 99

    def test_increments_correctly(self):
        """Test counter increments correctly."""
        tracker = RateLimitTracker(default_limit=100)

        for i in range(10):
            tracker.check_and_increment("key1")

        usage = tracker.get_usage("key1")
        assert usage["count"] == 10
        assert usage["remaining"] == 90

    def test_limit_exceeded(self):
        """Test rate limit is enforced."""
        tracker = RateLimitTracker(default_limit=5)

        # Use up the limit
        for i in range(5):
            allowed, _, _ = tracker.check_and_increment("key1")
            assert allowed is True

        # Next request should be denied
        allowed, remaining, reset = tracker.check_and_increment("key1")
        assert allowed is False
        assert remaining == 0

    def test_limit_override(self):
        """Test rate limit override."""
        tracker = RateLimitTracker(default_limit=100)

        # Use override limit of 3
        for i in range(3):
            allowed, _, _ = tracker.check_and_increment("key1", limit_override=3)
            assert allowed is True

        # Next should be denied
        allowed, _, _ = tracker.check_and_increment("key1", limit_override=3)
        assert allowed is False

    def test_window_reset(self):
        """Test window resets after expiry."""
        tracker = RateLimitTracker(default_limit=5, window_seconds=1)

        # Use up limit
        for i in range(5):
            tracker.check_and_increment("key1")

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        allowed, remaining, _ = tracker.check_and_increment("key1")
        assert allowed is True
        assert remaining == 4

    def test_reset_key(self):
        """Test manual key reset."""
        tracker = RateLimitTracker(default_limit=100)

        tracker.check_and_increment("key1")
        tracker.check_and_increment("key1")

        tracker.reset("key1")

        usage = tracker.get_usage("key1")
        assert usage["count"] == 0

    def test_cleanup_expired(self):
        """Test cleanup of expired counters."""
        tracker = RateLimitTracker(default_limit=100, window_seconds=1)

        tracker.check_and_increment("key1")
        tracker.check_and_increment("key2")

        # Wait for expiry
        time.sleep(2.1)

        tracker.cleanup_expired()

        # Keys should be cleaned up
        assert "key1" not in tracker._counters
        assert "key2" not in tracker._counters

    def test_independent_keys(self):
        """Test keys are tracked independently."""
        tracker = RateLimitTracker(default_limit=5)

        # Exhaust key1
        for i in range(5):
            tracker.check_and_increment("key1")

        # key2 should still be allowed
        allowed, _, _ = tracker.check_and_increment("key2")
        assert allowed is True


# ============================================================
# MockAPIKeyService Tests
# ============================================================

class TestMockAPIKeyService:
    """Tests for MockAPIKeyService."""

    def test_register_and_authenticate(self):
        """Test registering and authenticating a key."""
        service = MockAPIKeyService()

        service.register_key(
            key_id="key123",
            raw_key="kg_testkey12345",
            scopes=["read:concepts"],
            name="Test Key"
        )

        result = service.authenticate("kg_testkey12345")

        assert result.success is True
        assert result.key_id == "key123"
        assert result.key_name == "Test Key"
        assert "read:concepts" in result.scopes

    def test_invalid_key(self):
        """Test invalid key authentication."""
        service = MockAPIKeyService()

        result = service.authenticate("kg_invalid")

        assert result.success is False
        assert result.error_code == AuthErrorCode.INVALID_API_KEY

    def test_expired_key(self):
        """Test expired key authentication."""
        service = MockAPIKeyService()

        service.register_key(
            key_id="key123",
            raw_key="kg_expired",
            scopes=["read:concepts"]
        )
        service._keys["key123"]["status"] = "expired"

        result = service.authenticate("kg_expired")

        assert result.success is False
        assert result.error_code == AuthErrorCode.EXPIRED_API_KEY

    def test_suspended_key(self):
        """Test suspended key authentication."""
        service = MockAPIKeyService()

        service.register_key(
            key_id="key123",
            raw_key="kg_suspended",
            scopes=["read:concepts"]
        )
        service._keys["key123"]["status"] = "suspended"

        result = service.authenticate("kg_suspended")

        assert result.success is False
        assert result.error_code == AuthErrorCode.SUSPENDED_API_KEY

    def test_revoked_key(self):
        """Test revoked key authentication."""
        service = MockAPIKeyService()

        service.register_key(
            key_id="key123",
            raw_key="kg_revoked",
            scopes=["read:concepts"]
        )
        service._keys["key123"]["status"] = "revoked"

        result = service.authenticate("kg_revoked")

        assert result.success is False
        assert result.error_code == AuthErrorCode.REVOKED_API_KEY

    def test_has_scope_exact_match(self):
        """Test exact scope matching."""
        service = MockAPIKeyService()

        assert service.has_scope(["read:concepts"], "read:concepts") is True
        assert service.has_scope(["read:concepts"], "write:concepts") is False

    def test_has_scope_wildcard(self):
        """Test wildcard scope matching."""
        service = MockAPIKeyService()

        assert service.has_scope(["*"], "read:concepts") is True
        assert service.has_scope(["admin:*"], "admin:keys") is True
        assert service.has_scope(["read:*"], "read:concepts") is True
        assert service.has_scope(["read:*"], "write:concepts") is False


# ============================================================
# KGAuthMiddleware Tests (Unit)
# ============================================================

class TestKGAuthMiddlewareUnit:
    """Unit tests for KGAuthMiddleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.config = AuthMiddlewareConfig(enabled=True)
        self.api_key_service = MockAPIKeyService()

        self.api_key_service.register_key(
            key_id="test123",
            raw_key="kg_validkey1234567890",
            scopes=["read:concepts", "read:patients"],
            name="Test Key"
        )

        self.middleware = KGAuthMiddleware(
            self.app,
            config=self.config,
            api_key_service=self.api_key_service
        )

    def test_extract_api_key_from_header(self):
        """Test extracting API key from header."""
        request = MagicMock()
        request.headers = {"X-API-Key": "kg_testkey"}
        request.query_params = {}

        key = self.middleware._extract_api_key(request)

        assert key == "kg_testkey"

    def test_extract_api_key_from_query(self):
        """Test extracting API key from query param."""
        request = MagicMock()
        request.headers = {}
        request.query_params = {"api_key": "kg_querykey"}

        key = self.middleware._extract_api_key(request)

        assert key == "kg_querykey"

    def test_extract_api_key_header_priority(self):
        """Test header takes priority over query param."""
        request = MagicMock()
        request.headers = {"X-API-Key": "kg_headerkey"}
        request.query_params = {"api_key": "kg_querykey"}

        key = self.middleware._extract_api_key(request)

        assert key == "kg_headerkey"

    def test_get_client_ip_forwarded(self):
        """Test getting client IP from X-Forwarded-For."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = None

        ip = self.middleware._get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_real_ip(self):
        """Test getting client IP from X-Real-IP."""
        request = MagicMock()
        request.headers = {"X-Real-IP": "192.168.1.100"}
        request.client = None

        ip = self.middleware._get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_get_client_ip_client(self):
        """Test getting client IP from request client."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "10.0.0.50"

        ip = self.middleware._get_client_ip(request)

        assert ip == "10.0.0.50"

    def test_check_ip_allowed_no_restrictions(self):
        """Test IP check with no restrictions."""
        assert self.middleware._check_ip_allowed("192.168.1.1") is True

    def test_check_ip_blacklisted(self):
        """Test IP check with blacklist."""
        self.middleware.config.ip_blacklist = ["192.168.1.1"]

        assert self.middleware._check_ip_allowed("192.168.1.1") is False
        assert self.middleware._check_ip_allowed("192.168.1.2") is True

    def test_check_ip_whitelisted(self):
        """Test IP check with whitelist."""
        self.middleware.config.ip_whitelist = ["10.0.0.1", "10.0.0.2"]

        assert self.middleware._check_ip_allowed("10.0.0.1") is True
        assert self.middleware._check_ip_allowed("192.168.1.1") is False

    def test_error_response_format(self):
        """Test error response format."""
        response = self.middleware._error_response(
            AuthErrorCode.INVALID_API_KEY,
            "Invalid key",
            status_code=401
        )

        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_error_response_with_headers(self):
        """Test error response with custom headers."""
        response = self.middleware._error_response(
            AuthErrorCode.RATE_LIMIT_EXCEEDED,
            "Rate limit exceeded",
            status_code=429,
            headers={"Retry-After": "3600"}
        )

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "3600"


# ============================================================
# Middleware Integration Tests (Async)
# ============================================================

class TestKGAuthMiddlewareAsync:
    """Async integration tests for middleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.api_key_service = MockAPIKeyService()

        self.api_key_service.register_key(
            key_id="test123",
            raw_key="kg_validkey1234567890",
            scopes=["read:concepts", "read:patients", "*"],
            name="Admin Key"
        )

        self.middleware = KGAuthMiddleware(
            self.app,
            api_key_service=self.api_key_service
        )

    @pytest.mark.asyncio
    async def test_dispatch_skipped_pattern(self):
        """Test dispatch skips configured patterns."""
        request = MagicMock()
        request.url.path = "/health/live"
        request.method = "GET"

        call_next = AsyncMock(return_value=MagicMock())

        await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_missing_key(self):
        """Test dispatch with missing API key."""
        request = MagicMock()
        request.url.path = "/kg/concepts"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        call_next = AsyncMock()

        response = await self.middleware.dispatch(request, call_next)

        assert response.status_code == 401
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_invalid_key_prefix(self):
        """Test dispatch with invalid key prefix."""
        request = MagicMock()
        request.url.path = "/kg/concepts"
        request.method = "GET"
        request.headers = {"X-API-Key": "invalid_key123"}
        request.query_params = {}

        call_next = AsyncMock()

        response = await self.middleware.dispatch(request, call_next)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_dispatch_valid_key(self):
        """Test dispatch with valid API key."""
        request = MagicMock()
        request.url.path = "/kg/concepts"
        request.method = "GET"
        request.headers = {"X-API-Key": "kg_validkey1234567890"}
        request.query_params = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once()
        assert request.state.auth.key_id == "test123"

    @pytest.mark.asyncio
    async def test_dispatch_disabled_middleware(self):
        """Test dispatch when middleware is disabled."""
        self.middleware.config.enabled = False

        request = MagicMock()
        request.url.path = "/kg/concepts"
        request.headers = {}

        call_next = AsyncMock(return_value=MagicMock())

        await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)


# ============================================================
# Dependency Injection Tests
# ============================================================

class TestDependencyInjection:
    """Tests for FastAPI dependency injection helpers."""

    def test_get_current_auth_success(self):
        """Test getting current auth from request."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:concepts"]
        )

        auth = get_current_auth(request)

        assert auth.key_id == "key123"

    def test_get_current_auth_not_authenticated(self):
        """Test getting auth when not authenticated."""
        request = MagicMock()
        del request.state.auth  # Remove auth attribute

        with pytest.raises(Exception) as exc_info:
            get_current_auth(request)

        assert exc_info.value.status_code == 401

    def test_require_scope_success(self):
        """Test require_scope with valid scope."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:concepts", "read:patients"]
        )

        dependency = require_scope("read:concepts")
        auth = dependency(request)

        assert auth.key_id == "key123"

    def test_require_scope_wildcard(self):
        """Test require_scope with wildcard scope."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["*"]
        )

        dependency = require_scope("read:concepts")
        auth = dependency(request)

        assert auth.key_id == "key123"

    def test_require_scope_insufficient(self):
        """Test require_scope with insufficient scope."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:concepts"]
        )

        dependency = require_scope("write:concepts")

        with pytest.raises(Exception) as exc_info:
            dependency(request)

        assert exc_info.value.status_code == 403

    def test_require_any_scope_success(self):
        """Test require_any_scope with one matching scope."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:concepts"]
        )

        dependency = require_any_scope("read:concepts", "write:concepts")
        auth = dependency(request)

        assert auth.key_id == "key123"

    def test_require_any_scope_failure(self):
        """Test require_any_scope with no matching scope."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:patients"]
        )

        dependency = require_any_scope("read:concepts", "write:concepts")

        with pytest.raises(Exception) as exc_info:
            dependency(request)

        assert exc_info.value.status_code == 403

    def test_require_all_scopes_success(self):
        """Test require_all_scopes with all matching scopes."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:concepts", "write:concepts", "read:patients"]
        )

        dependency = require_all_scopes("read:concepts", "write:concepts")
        auth = dependency(request)

        assert auth.key_id == "key123"

    def test_require_all_scopes_failure(self):
        """Test require_all_scopes with missing scope."""
        request = MagicMock()
        request.state.auth = AuthResult(
            success=True,
            key_id="key123",
            scopes=["read:concepts"]
        )

        dependency = require_all_scopes("read:concepts", "write:concepts")

        with pytest.raises(Exception) as exc_info:
            dependency(request)

        assert exc_info.value.status_code == 403


# ============================================================
# Factory Function Tests
# ============================================================

class TestCreateKGAuthMiddleware:
    """Tests for factory function."""

    def test_create_with_defaults(self):
        """Test creating middleware with defaults."""
        app = MagicMock()

        middleware = create_kg_auth_middleware(app)

        assert middleware.config.enabled is True
        assert middleware.config.default_rate_limit == 1000

    def test_create_with_custom_config(self):
        """Test creating middleware with custom config."""
        app = MagicMock()

        middleware = create_kg_auth_middleware(
            app,
            enabled=True,
            rate_limit=500,
            include_debug=True,
            ip_whitelist=["10.0.0.1"],
            ip_blacklist=["192.168.1.1"]
        )

        assert middleware.config.default_rate_limit == 500
        assert middleware.config.include_debug_info is True
        assert "10.0.0.1" in middleware.config.ip_whitelist
        assert "192.168.1.1" in middleware.config.ip_blacklist

    def test_create_with_audit_callback(self):
        """Test creating middleware with audit callback."""
        app = MagicMock()
        callback = MagicMock()

        middleware = create_kg_auth_middleware(
            app,
            audit_callback=callback
        )

        assert middleware._audit_callback == callback

    def test_create_disabled(self):
        """Test creating disabled middleware."""
        app = MagicMock()

        middleware = create_kg_auth_middleware(app, enabled=False)

        assert middleware.config.enabled is False


# ============================================================
# Audit Logging Tests
# ============================================================

class TestAuditLogging:
    """Tests for audit logging integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.audit_events = []

        def audit_callback(**kwargs):
            self.audit_events.append(kwargs)

        self.api_key_service = MockAPIKeyService()
        self.api_key_service.register_key(
            key_id="test123",
            raw_key="kg_auditkey123",
            scopes=["read:concepts"]
        )

        self.middleware = KGAuthMiddleware(
            self.app,
            api_key_service=self.api_key_service
        )
        self.middleware.set_audit_callback(audit_callback)

    def test_audit_callback_set(self):
        """Test audit callback is properly set."""
        assert self.middleware._audit_callback is not None

    @pytest.mark.asyncio
    async def test_audit_logged_on_request(self):
        """Test audit event logged on request."""
        request = MagicMock()
        request.url.path = "/kg/concepts"
        request.method = "GET"
        request.headers = {"X-API-Key": "kg_auditkey123"}
        request.query_params = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        await self.middleware.dispatch(request, call_next)

        # Should have logged access event
        access_events = [e for e in self.audit_events if e.get("event_type") == "api_access"]
        assert len(access_events) >= 1
        assert access_events[0]["key_id"] == "test123"


# ============================================================
# Edge Cases Tests
# ============================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_scopes_list(self):
        """Test with empty scopes list."""
        service = MockAPIKeyService()
        service.register_key(
            key_id="key1",
            raw_key="kg_emptykey",
            scopes=[]
        )

        result = service.authenticate("kg_emptykey")
        assert result.success is True
        assert result.scopes == []
        assert service.has_scope([], "read:concepts") is False

    def test_metadata_preservation(self):
        """Test metadata is preserved through auth."""
        service = MockAPIKeyService()
        service.register_key(
            key_id="key1",
            raw_key="kg_metakey",
            scopes=["read:concepts"],
            metadata={"org_id": "org123", "tier": "premium"}
        )

        result = service.authenticate("kg_metakey")
        assert result.metadata["org_id"] == "org123"
        assert result.metadata["tier"] == "premium"

    def test_scope_with_colon(self):
        """Test scope matching with colons."""
        service = MockAPIKeyService()

        assert service.has_scope(["admin:*"], "admin:keys:rotate") is True
        assert service.has_scope(["read:concepts"], "read:concepts:details") is False

    def test_concurrent_rate_limit_tracking(self):
        """Test rate limiting tracks concurrently."""
        tracker = RateLimitTracker(default_limit=100)

        # Simulate concurrent access
        results = []
        for i in range(50):
            allowed, remaining, _ = tracker.check_and_increment(f"key{i % 5}")
            results.append((i % 5, allowed, remaining))

        # Each key should have 10 requests
        for key_num in range(5):
            usage = tracker.get_usage(f"key{key_num}")
            assert usage["count"] == 10


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
