"""
Tests for KG API Versioning Support.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.middleware.kg_versioning import (
    VersionStatus,
    APIVersion,
    VersionInfo,
    VersionedRoute,
    RequestTransform,
    ResponseTransform,
    VersionRegistry,
    VersionNegotiator,
    KGVersioningMiddleware,
    get_api_version,
    require_min_version,
    require_max_version,
    create_kg_version_registry,
    create_kg_versioning_middleware,
    VersionedAPIRouter,
)


# ============================================================
# APIVersion Tests
# ============================================================

class TestAPIVersion:
    """Tests for APIVersion class."""

    def test_create_version(self):
        """Test creating a version."""
        version = APIVersion(1, 0, 0)

        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0

    def test_str_format(self):
        """Test string format."""
        assert str(APIVersion(1, 0)) == "v1.0"
        assert str(APIVersion(2, 1)) == "v2.1"
        assert str(APIVersion(1, 0, 1)) == "v1.0.1"

    def test_parse_version(self):
        """Test parsing version strings."""
        assert APIVersion.parse("v1.0") == APIVersion(1, 0)
        assert APIVersion.parse("v2.1") == APIVersion(2, 1)
        assert APIVersion.parse("1.0.0") == APIVersion(1, 0, 0)
        assert APIVersion.parse("V1.2.3") == APIVersion(1, 2, 3)

    def test_parse_invalid_version(self):
        """Test parsing invalid version strings."""
        with pytest.raises(ValueError):
            APIVersion.parse("invalid")

        with pytest.raises(ValueError):
            APIVersion.parse("v1")

        with pytest.raises(ValueError):
            APIVersion.parse("abc.def")

    def test_version_comparison(self):
        """Test version comparison operators."""
        v1_0 = APIVersion(1, 0)
        v1_1 = APIVersion(1, 1)
        v2_0 = APIVersion(2, 0)

        assert v1_0 < v1_1
        assert v1_1 < v2_0
        assert v2_0 > v1_1
        assert v1_0 <= v1_0
        assert v1_0 >= v1_0
        assert v1_0 == APIVersion(1, 0)
        assert v1_0 != v1_1

    def test_version_equality(self):
        """Test version equality."""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(1, 0, 0)
        v3 = APIVersion(1, 0, 1)

        assert v1 == v2
        assert v1 != v3
        assert v1 != "v1.0"  # Different type

    def test_version_hash(self):
        """Test version can be used as dict key."""
        versions = {
            APIVersion(1, 0): "one",
            APIVersion(2, 0): "two"
        }

        assert versions[APIVersion(1, 0)] == "one"
        assert versions[APIVersion(2, 0)] == "two"

    def test_is_compatible_with(self):
        """Test version compatibility check."""
        v1_0 = APIVersion(1, 0)
        v1_1 = APIVersion(1, 1)
        v2_0 = APIVersion(2, 0)

        assert v1_0.is_compatible_with(v1_1)
        assert not v1_0.is_compatible_with(v2_0)


# ============================================================
# VersionInfo Tests
# ============================================================

class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_create_version_info(self):
        """Test creating version info."""
        info = VersionInfo(
            version=APIVersion(1, 0),
            status=VersionStatus.CURRENT,
            released_at=date(2024, 1, 1)
        )

        assert info.version == APIVersion(1, 0)
        assert info.status == VersionStatus.CURRENT
        assert info.deprecated_at is None

    def test_version_info_with_deprecation(self):
        """Test version info with deprecation."""
        info = VersionInfo(
            version=APIVersion(1, 0),
            status=VersionStatus.DEPRECATED,
            released_at=date(2024, 1, 1),
            deprecated_at=date(2024, 6, 1),
            sunset_at=date(2025, 1, 1),
            deprecation_message="Please upgrade"
        )

        assert info.status == VersionStatus.DEPRECATED
        assert info.sunset_at == date(2025, 1, 1)
        assert info.deprecation_message == "Please upgrade"


# ============================================================
# VersionRegistry Tests
# ============================================================

class TestVersionRegistry:
    """Tests for VersionRegistry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VersionRegistry()

    def test_register_version(self):
        """Test registering a version."""
        self.registry.register_version(
            APIVersion(1, 0),
            status=VersionStatus.CURRENT,
            released_at=date(2024, 1, 1)
        )

        info = self.registry.get_version_info(APIVersion(1, 0))
        assert info is not None
        assert info.status == VersionStatus.CURRENT

    def test_register_version_sets_current(self):
        """Test registering current version sets it automatically."""
        self.registry.register_version(
            APIVersion(1, 0),
            status=VersionStatus.CURRENT
        )

        assert self.registry.get_current_version() == APIVersion(1, 0)

    def test_set_current_version(self):
        """Test setting current version."""
        self.registry.register_version(APIVersion(1, 0))
        self.registry.register_version(APIVersion(2, 0))

        self.registry.set_current_version(APIVersion(2, 0))

        assert self.registry.get_current_version() == APIVersion(2, 0)
        # Old current should now be supported
        info = self.registry.get_version_info(APIVersion(1, 0))
        assert info.status == VersionStatus.SUPPORTED

    def test_set_default_version(self):
        """Test setting default version."""
        self.registry.register_version(APIVersion(1, 0))
        self.registry.set_default_version(APIVersion(1, 0))

        assert self.registry.get_default_version() == APIVersion(1, 0)

    def test_get_supported_versions(self):
        """Test getting supported versions."""
        self.registry.register_version(APIVersion(1, 0), VersionStatus.DEPRECATED)
        self.registry.register_version(APIVersion(2, 0), VersionStatus.CURRENT)
        self.registry.register_version(APIVersion(3, 0), VersionStatus.SUPPORTED)

        supported = self.registry.get_supported_versions()

        assert len(supported) == 2  # Current and Supported
        assert APIVersion(2, 0) in supported
        assert APIVersion(3, 0) in supported

    def test_get_all_versions(self):
        """Test getting all versions sorted."""
        self.registry.register_version(APIVersion(1, 0))
        self.registry.register_version(APIVersion(2, 0))
        self.registry.register_version(APIVersion(1, 5))

        versions = self.registry.get_all_versions()

        # Should be sorted descending
        assert versions[0].version == APIVersion(2, 0)
        assert versions[1].version == APIVersion(1, 5)
        assert versions[2].version == APIVersion(1, 0)

    def test_is_version_supported(self):
        """Test checking if version is supported."""
        self.registry.register_version(APIVersion(1, 0), VersionStatus.CURRENT)
        self.registry.register_version(APIVersion(0, 9), VersionStatus.RETIRED)

        assert self.registry.is_version_supported(APIVersion(1, 0)) is True
        assert self.registry.is_version_supported(APIVersion(0, 9)) is False
        assert self.registry.is_version_supported(APIVersion(9, 9)) is False

    def test_is_version_deprecated(self):
        """Test checking if version is deprecated."""
        self.registry.register_version(APIVersion(1, 0), VersionStatus.DEPRECATED)
        self.registry.register_version(APIVersion(2, 0), VersionStatus.CURRENT)

        assert self.registry.is_version_deprecated(APIVersion(1, 0)) is True
        assert self.registry.is_version_deprecated(APIVersion(2, 0)) is False

    def test_deprecate_version(self):
        """Test deprecating a version."""
        self.registry.register_version(APIVersion(1, 0), VersionStatus.SUPPORTED)

        self.registry.deprecate_version(
            APIVersion(1, 0),
            sunset_at=date(2025, 1, 1),
            message="Upgrade to v2"
        )

        info = self.registry.get_version_info(APIVersion(1, 0))
        assert info.status == VersionStatus.DEPRECATED
        assert info.sunset_at == date(2025, 1, 1)

    def test_retire_version(self):
        """Test retiring a version."""
        self.registry.register_version(APIVersion(1, 0))

        self.registry.retire_version(APIVersion(1, 0))

        info = self.registry.get_version_info(APIVersion(1, 0))
        assert info.status == VersionStatus.RETIRED

    def test_register_route(self):
        """Test registering versioned route."""
        self.registry.register_route(
            "/api/test",
            "GET",
            min_version=APIVersion(1, 0),
            max_version=APIVersion(2, 0)
        )

        assert "/api/test" in self.registry._routes

    def test_is_route_available(self):
        """Test checking route availability."""
        self.registry.register_route(
            "/api/v1/endpoint",
            "GET",
            min_version=APIVersion(1, 0),
            max_version=APIVersion(1, 9)
        )

        available, warning = self.registry.is_route_available(
            "/api/v1/endpoint", "GET", APIVersion(1, 5)
        )
        assert available is True

        available, warning = self.registry.is_route_available(
            "/api/v1/endpoint", "GET", APIVersion(2, 0)
        )
        assert available is False

    def test_is_route_deprecated(self):
        """Test route deprecation warning."""
        self.registry.register_route(
            "/api/old",
            "GET",
            deprecated_in=APIVersion(1, 5),
            replacement_path="/api/new"
        )

        available, warning = self.registry.is_route_available(
            "/api/old", "GET", APIVersion(2, 0)
        )

        assert available is True
        assert "deprecated" in warning.lower()
        assert "/api/new" in warning

    def test_is_route_removed(self):
        """Test route removal."""
        self.registry.register_route(
            "/api/removed",
            "GET",
            removed_in=APIVersion(2, 0),
            replacement_path="/api/replacement"
        )

        available, warning = self.registry.is_route_available(
            "/api/removed", "GET", APIVersion(2, 0)
        )

        assert available is False
        assert "removed" in warning.lower()

    def test_unregistered_route_available(self):
        """Test unregistered routes are available."""
        available, warning = self.registry.is_route_available(
            "/api/unregistered", "GET", APIVersion(1, 0)
        )

        assert available is True
        assert warning is None


# ============================================================
# VersionNegotiator Tests
# ============================================================

class TestVersionNegotiator:
    """Tests for VersionNegotiator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VersionRegistry()
        self.registry.register_version(APIVersion(1, 0), VersionStatus.SUPPORTED)
        self.registry.register_version(APIVersion(2, 0), VersionStatus.CURRENT)
        self.registry.set_default_version(APIVersion(2, 0))

        self.negotiator = VersionNegotiator(self.registry)

    def _create_request(
        self,
        path: str = "/api/test",
        headers: dict = None,
        query_params: dict = None
    ):
        """Create mock request."""
        request = MagicMock()
        request.url.path = path
        request.headers = headers or {}
        request.query_params = query_params or {}
        return request

    def test_negotiate_from_url_path(self):
        """Test version negotiation from URL path."""
        request = self._create_request(path="/api/v1.0/concepts")

        version, source = self.negotiator.negotiate(request)

        assert version == APIVersion(1, 0)
        assert source == "url_path"

    def test_negotiate_from_query_param(self):
        """Test version negotiation from query parameter."""
        request = self._create_request(
            path="/api/concepts",
            query_params={"api_version": "v1.0"}
        )

        version, source = self.negotiator.negotiate(request)

        assert version == APIVersion(1, 0)
        assert source == "query_param"

    def test_negotiate_from_header(self):
        """Test version negotiation from header."""
        request = self._create_request(
            path="/api/concepts",
            headers={"X-API-Version": "v1.0"}
        )

        version, source = self.negotiator.negotiate(request)

        assert version == APIVersion(1, 0)
        assert source == "header"

    def test_negotiate_from_accept_header(self):
        """Test version negotiation from Accept header."""
        request = self._create_request(
            path="/api/concepts",
            headers={"Accept": "application/vnd.kg.api.v1.0+json"}
        )

        version, source = self.negotiator.negotiate(request)

        assert version == APIVersion(1, 0)
        assert source == "accept_header"

    def test_negotiate_fallback_to_default(self):
        """Test negotiation falls back to default."""
        request = self._create_request(path="/api/concepts")

        version, source = self.negotiator.negotiate(request)

        assert version == APIVersion(2, 0)
        assert source == "default"

    def test_negotiate_priority_order(self):
        """Test URL path has highest priority."""
        request = self._create_request(
            path="/api/v1.0/concepts",
            headers={"X-API-Version": "v2.0"},
            query_params={"api_version": "v1.1"}
        )

        version, source = self.negotiator.negotiate(request)

        # URL path should take priority
        assert version == APIVersion(1, 0)
        assert source == "url_path"


# ============================================================
# KGVersioningMiddleware Tests
# ============================================================

class TestKGVersioningMiddleware:
    """Tests for KGVersioningMiddleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VersionRegistry()
        self.registry.register_version(APIVersion(1, 0), VersionStatus.DEPRECATED)
        self.registry.register_version(APIVersion(2, 0), VersionStatus.CURRENT)
        self.registry.set_default_version(APIVersion(2, 0))

        self.app = MagicMock()
        self.middleware = KGVersioningMiddleware(
            self.app,
            registry=self.registry,
            enabled=True
        )

    def _create_request(self, path="/api/test", headers=None, method="GET"):
        """Create mock request."""
        request = MagicMock()
        request.url.path = path
        request.method = method
        request.headers = headers or {}
        request.query_params = {}
        request.state = MagicMock()
        return request

    @pytest.mark.asyncio
    async def test_middleware_disabled(self):
        """Test middleware when disabled."""
        middleware = KGVersioningMiddleware(
            self.app,
            registry=self.registry,
            enabled=False
        )

        request = self._create_request()
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(request, call_next)

        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_sets_version_in_state(self):
        """Test middleware sets version in request state."""
        request = self._create_request(headers={"X-API-Version": "v2.0"})

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        await self.middleware.dispatch(request, call_next)

        assert request.state.api_version == APIVersion(2, 0)

    @pytest.mark.asyncio
    async def test_middleware_adds_version_headers(self):
        """Test middleware adds version headers to response."""
        request = self._create_request(headers={"X-API-Version": "v2.0"})

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        assert "X-API-Version" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_deprecated_version_warning(self):
        """Test middleware adds deprecation warning for deprecated version."""
        self.registry.deprecate_version(
            APIVersion(1, 0),
            sunset_at=date(2025, 1, 1),
            message="Please upgrade"
        )

        request = self._create_request(headers={"X-API-Version": "v1.0"})

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        assert response.headers.get("Deprecation") == "true"
        assert "Sunset" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_retired_version_error(self):
        """Test middleware returns error for retired version."""
        self.registry.retire_version(APIVersion(1, 0))

        request = self._create_request(headers={"X-API-Version": "v1.0"})
        call_next = AsyncMock()

        response = await self.middleware.dispatch(request, call_next)

        assert response.status_code == 410
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_unsupported_version_error(self):
        """Test middleware returns error for unsupported version."""
        request = self._create_request(headers={"X-API-Version": "v9.9"})
        call_next = AsyncMock()

        response = await self.middleware.dispatch(request, call_next)

        assert response.status_code == 400


# ============================================================
# Dependency Injection Tests
# ============================================================

class TestDependencyInjection:
    """Tests for FastAPI dependency injection helpers."""

    def test_get_api_version(self):
        """Test getting API version from request."""
        request = MagicMock()
        request.state.api_version = APIVersion(1, 0)

        version = get_api_version(request)

        assert version == APIVersion(1, 0)

    def test_get_api_version_not_set(self):
        """Test error when version not set."""
        request = MagicMock()
        del request.state.api_version

        with pytest.raises(Exception) as exc_info:
            get_api_version(request)

        assert exc_info.value.status_code == 500

    def test_require_min_version_success(self):
        """Test require_min_version with sufficient version."""
        request = MagicMock()
        request.state.api_version = APIVersion(2, 0)

        dependency = require_min_version("v1.0")
        version = dependency(request)

        assert version == APIVersion(2, 0)

    def test_require_min_version_failure(self):
        """Test require_min_version with insufficient version."""
        request = MagicMock()
        request.state.api_version = APIVersion(1, 0)

        dependency = require_min_version("v2.0")

        with pytest.raises(Exception) as exc_info:
            dependency(request)

        assert exc_info.value.status_code == 400

    def test_require_max_version_success(self):
        """Test require_max_version with allowed version."""
        request = MagicMock()
        request.state.api_version = APIVersion(1, 0)

        dependency = require_max_version("v2.0")
        version = dependency(request)

        assert version == APIVersion(1, 0)

    def test_require_max_version_failure(self):
        """Test require_max_version with exceeded version."""
        request = MagicMock()
        request.state.api_version = APIVersion(3, 0)

        dependency = require_max_version("v2.0")

        with pytest.raises(Exception) as exc_info:
            dependency(request)

        assert exc_info.value.status_code == 400


# ============================================================
# Factory Function Tests
# ============================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_kg_version_registry(self):
        """Test creating pre-configured registry."""
        registry = create_kg_version_registry()

        assert registry.get_current_version() == APIVersion(2, 0)
        assert registry.get_default_version() == APIVersion(2, 0)

        # Should have versions configured
        versions = registry.get_all_versions()
        assert len(versions) >= 3

    def test_create_kg_versioning_middleware(self):
        """Test creating versioning middleware."""
        app = MagicMock()

        middleware = create_kg_versioning_middleware(app)

        assert middleware.enabled is True
        assert middleware.registry is not None

    def test_create_middleware_disabled(self):
        """Test creating disabled middleware."""
        app = MagicMock()

        middleware = create_kg_versioning_middleware(app, enabled=False)

        assert middleware.enabled is False

    def test_create_middleware_strict_mode(self):
        """Test creating middleware in strict mode."""
        app = MagicMock()

        middleware = create_kg_versioning_middleware(app, strict_mode=True)

        assert middleware.strict_mode is True


# ============================================================
# Transform Tests
# ============================================================

class TestTransforms:
    """Tests for request/response transforms."""

    def test_request_transform_dataclass(self):
        """Test RequestTransform dataclass."""
        transform = RequestTransform(
            source_path="/api/v1/old",
            target_path="/api/v2/new",
            param_mappings={"old_param": "new_param"},
            added_params={"format": "json"},
            removed_params=["deprecated"]
        )

        assert transform.source_path == "/api/v1/old"
        assert transform.param_mappings["old_param"] == "new_param"

    def test_response_transform_dataclass(self):
        """Test ResponseTransform dataclass."""
        transform = ResponseTransform(
            field_mappings={"oldField": "newField"},
            added_fields={"version": "2.0"},
            removed_fields=["deprecated_field"],
            wrapper="data"
        )

        assert transform.field_mappings["oldField"] == "newField"
        assert transform.wrapper == "data"

    def test_register_request_transform(self):
        """Test registering request transform."""
        registry = VersionRegistry()
        transform = RequestTransform(
            source_path="/old",
            target_path="/new"
        )

        registry.register_request_transform(
            APIVersion(1, 0),
            "/old",
            transform
        )

        result = registry.get_request_transform(APIVersion(1, 0), "/old")
        assert result is not None
        assert result.target_path == "/new"

    def test_register_response_transform(self):
        """Test registering response transform."""
        registry = VersionRegistry()
        transform = ResponseTransform(
            field_mappings={"a": "b"}
        )

        registry.register_response_transform(
            APIVersion(1, 0),
            "/endpoint",
            transform
        )

        result = registry.get_response_transform(APIVersion(1, 0), "/endpoint")
        assert result is not None
        assert result.field_mappings["a"] == "b"


# ============================================================
# VersionedAPIRouter Tests
# ============================================================

class TestVersionedAPIRouter:
    """Tests for VersionedAPIRouter."""

    def test_create_versioned_router(self):
        """Test creating versioned router."""
        router = VersionedAPIRouter(
            prefix="/api",
            min_version=APIVersion(1, 0)
        )

        assert router.min_version == APIVersion(1, 0)

    def test_add_versioned_route(self):
        """Test adding versioned route."""
        router = VersionedAPIRouter()

        @router.get("/test")
        def test_endpoint():
            pass

        # Should have the route
        assert len(router.routes) > 0


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
