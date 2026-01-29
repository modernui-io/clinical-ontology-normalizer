"""
API Versioning Support for Knowledge Graph Endpoints.

This module provides comprehensive API versioning including:
- Version routing via URL path or headers
- Version negotiation (Accept-Version, X-API-Version)
- Deprecation warnings and sunset headers
- Version-specific request/response transformation
- Changelog generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Callable

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware


class VersionStatus(str, Enum):
    """API version lifecycle status."""
    CURRENT = "current"
    SUPPORTED = "supported"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class APIVersion:
    """Represents an API version."""
    major: int
    minor: int
    patch: int = 0

    def __str__(self) -> str:
        if self.patch:
            return f"v{self.major}.{self.minor}.{self.patch}"
        return f"v{self.major}.{self.minor}"

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, APIVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: "APIVersion") -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: "APIVersion") -> bool:
        return self == other or self < other

    def __gt__(self, other: "APIVersion") -> bool:
        return not self <= other

    def __ge__(self, other: "APIVersion") -> bool:
        return not self < other

    @classmethod
    def parse(cls, version_str: str) -> "APIVersion":
        """Parse version string like 'v1.0' or '1.0.0'."""
        version_str = version_str.lower().lstrip("v")
        parts = version_str.split(".")

        if len(parts) < 2:
            raise ValueError(f"Invalid version format: {version_str}")

        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2]) if len(parts) > 2 else 0
            return cls(major=major, minor=minor, patch=patch)
        except ValueError:
            raise ValueError(f"Invalid version format: {version_str}")

    def is_compatible_with(self, other: "APIVersion") -> bool:
        """Check if this version is compatible with another (same major version)."""
        return self.major == other.major


@dataclass
class VersionInfo:
    """Information about an API version."""
    version: APIVersion
    status: VersionStatus
    released_at: date
    deprecated_at: date | None = None
    sunset_at: date | None = None
    changelog: list[str] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    deprecation_message: str | None = None


@dataclass
class VersionedRoute:
    """A route with version-specific configuration."""
    path: str
    method: str
    min_version: APIVersion | None = None
    max_version: APIVersion | None = None
    deprecated_in: APIVersion | None = None
    removed_in: APIVersion | None = None
    replacement_path: str | None = None
    transformer: Callable | None = None


@dataclass
class RequestTransform:
    """Transform request for a specific version."""
    source_path: str
    target_path: str
    param_mappings: dict[str, str] = field(default_factory=dict)
    body_mappings: dict[str, str] = field(default_factory=dict)
    added_params: dict[str, Any] = field(default_factory=dict)
    removed_params: list[str] = field(default_factory=list)


@dataclass
class ResponseTransform:
    """Transform response for a specific version."""
    field_mappings: dict[str, str] = field(default_factory=dict)
    added_fields: dict[str, Any] = field(default_factory=dict)
    removed_fields: list[str] = field(default_factory=list)
    wrapper: str | None = None


class VersionRegistry:
    """Registry of API versions and their configurations."""

    def __init__(self):
        self._versions: dict[APIVersion, VersionInfo] = {}
        self._routes: dict[str, list[VersionedRoute]] = {}  # path -> routes
        self._request_transforms: dict[tuple[APIVersion, str], RequestTransform] = {}
        self._response_transforms: dict[tuple[APIVersion, str], ResponseTransform] = {}
        self._current_version: APIVersion | None = None
        self._default_version: APIVersion | None = None

    def register_version(
        self,
        version: APIVersion,
        status: VersionStatus = VersionStatus.SUPPORTED,
        released_at: date | None = None,
        deprecated_at: date | None = None,
        sunset_at: date | None = None,
        changelog: list[str | None] = None,
        breaking_changes: list[str | None] = None,
        deprecation_message: str | None = None
    ):
        """Register an API version."""
        info = VersionInfo(
            version=version,
            status=status,
            released_at=released_at or date.today(),
            deprecated_at=deprecated_at,
            sunset_at=sunset_at,
            changelog=changelog or [],
            breaking_changes=breaking_changes or [],
            deprecation_message=deprecation_message
        )
        self._versions[version] = info

        if status == VersionStatus.CURRENT:
            self._current_version = version

        if self._default_version is None:
            self._default_version = version

    def set_current_version(self, version: APIVersion):
        """Set the current (latest) version."""
        if version in self._versions:
            # Update old current to supported
            if self._current_version and self._current_version in self._versions:
                self._versions[self._current_version].status = VersionStatus.SUPPORTED

            self._current_version = version
            self._versions[version].status = VersionStatus.CURRENT

    def set_default_version(self, version: APIVersion):
        """Set the default version for unspecified requests."""
        self._default_version = version

    def get_version_info(self, version: APIVersion) -> VersionInfo | None:
        """Get information about a version."""
        return self._versions.get(version)

    def get_current_version(self) -> APIVersion | None:
        """Get the current (latest) version."""
        return self._current_version

    def get_default_version(self) -> APIVersion | None:
        """Get the default version."""
        return self._default_version

    def get_supported_versions(self) -> list[APIVersion]:
        """Get list of all supported versions."""
        return [
            v for v, info in self._versions.items()
            if info.status in [VersionStatus.CURRENT, VersionStatus.SUPPORTED]
        ]

    def get_all_versions(self) -> list[VersionInfo]:
        """Get information about all versions."""
        return sorted(self._versions.values(), key=lambda x: x.version, reverse=True)

    def is_version_supported(self, version: APIVersion) -> bool:
        """Check if a version is supported."""
        if version not in self._versions:
            return False
        return self._versions[version].status in [
            VersionStatus.CURRENT,
            VersionStatus.SUPPORTED,
            VersionStatus.DEPRECATED
        ]

    def is_version_deprecated(self, version: APIVersion) -> bool:
        """Check if a version is deprecated."""
        if version not in self._versions:
            return False
        return self._versions[version].status == VersionStatus.DEPRECATED

    def deprecate_version(
        self,
        version: APIVersion,
        deprecated_at: date | None = None,
        sunset_at: date | None = None,
        message: str | None = None
    ):
        """Mark a version as deprecated."""
        if version in self._versions:
            info = self._versions[version]
            info.status = VersionStatus.DEPRECATED
            info.deprecated_at = deprecated_at or date.today()
            info.sunset_at = sunset_at
            info.deprecation_message = message

    def retire_version(self, version: APIVersion):
        """Mark a version as retired (no longer available)."""
        if version in self._versions:
            self._versions[version].status = VersionStatus.RETIRED

    def register_route(
        self,
        path: str,
        method: str,
        min_version: APIVersion | None = None,
        max_version: APIVersion | None = None,
        deprecated_in: APIVersion | None = None,
        removed_in: APIVersion | None = None,
        replacement_path: str | None = None
    ):
        """Register a versioned route."""
        route = VersionedRoute(
            path=path,
            method=method.upper(),
            min_version=min_version,
            max_version=max_version,
            deprecated_in=deprecated_in,
            removed_in=removed_in,
            replacement_path=replacement_path
        )

        if path not in self._routes:
            self._routes[path] = []
        self._routes[path].append(route)

    def is_route_available(
        self,
        path: str,
        method: str,
        version: APIVersion
    ) -> tuple[bool, str | None]:
        """
        Check if a route is available for a version.
        Returns (available, deprecation_warning).
        """
        if path not in self._routes:
            return True, None  # Route not versioned, assume available

        for route in self._routes[path]:
            if route.method != method.upper():
                continue

            # Check version bounds
            if route.min_version and version < route.min_version:
                return False, f"Route requires version >= {route.min_version}"

            if route.max_version and version > route.max_version:
                return False, f"Route only available up to version {route.max_version}"

            if route.removed_in and version >= route.removed_in:
                msg = f"Route was removed in version {route.removed_in}"
                if route.replacement_path:
                    msg += f". Use {route.replacement_path} instead."
                return False, msg

            # Check deprecation
            if route.deprecated_in and version >= route.deprecated_in:
                msg = f"Route is deprecated since version {route.deprecated_in}"
                if route.replacement_path:
                    msg += f". Use {route.replacement_path} instead."
                return True, msg

            return True, None

        return True, None

    def register_request_transform(
        self,
        version: APIVersion,
        path: str,
        transform: RequestTransform
    ):
        """Register a request transformation for a specific version."""
        self._request_transforms[(version, path)] = transform

    def register_response_transform(
        self,
        version: APIVersion,
        path: str,
        transform: ResponseTransform
    ):
        """Register a response transformation for a specific version."""
        self._response_transforms[(version, path)] = transform

    def get_request_transform(
        self,
        version: APIVersion,
        path: str
    ) -> RequestTransform | None:
        """Get request transformation for a version and path."""
        return self._request_transforms.get((version, path))

    def get_response_transform(
        self,
        version: APIVersion,
        path: str
    ) -> ResponseTransform | None:
        """Get response transformation for a version and path."""
        return self._response_transforms.get((version, path))


class VersionNegotiator:
    """Negotiate API version from request."""

    def __init__(
        self,
        registry: VersionRegistry,
        url_path_prefix: str = "/api",
        header_name: str = "X-API-Version",
        accept_header_prefix: str = "application/vnd.kg.api",
        query_param: str = "api_version"
    ):
        self.registry = registry
        self.url_path_prefix = url_path_prefix
        self.header_name = header_name
        self.accept_header_prefix = accept_header_prefix
        self.query_param = query_param

    def negotiate(self, request: Request) -> tuple[APIVersion, str]:
        """
        Negotiate version from request.
        Returns (version, source) where source is how version was determined.
        """
        # Priority 1: URL path (e.g., /api/v1/concepts)
        version, source = self._from_url_path(request)
        if version:
            return version, source

        # Priority 2: Query parameter
        version, source = self._from_query_param(request)
        if version:
            return version, source

        # Priority 3: X-API-Version header
        version, source = self._from_header(request)
        if version:
            return version, source

        # Priority 4: Accept header
        version, source = self._from_accept_header(request)
        if version:
            return version, source

        # Fallback to default
        default = self.registry.get_default_version()
        if default:
            return default, "default"

        raise HTTPException(
            status_code=400,
            detail="Unable to determine API version"
        )

    def _from_url_path(self, request: Request) -> tuple[APIVersion | None, str]:
        """Extract version from URL path."""
        path = request.url.path

        if path.startswith(self.url_path_prefix):
            # Look for /v{major}.{minor} pattern
            remaining = path[len(self.url_path_prefix):]
            if remaining.startswith("/v"):
                parts = remaining[1:].split("/", 1)
                version_str = parts[0]
                try:
                    version = APIVersion.parse(version_str)
                    return version, "url_path"
                except ValueError:
                    pass

        return None, ""

    def _from_query_param(self, request: Request) -> tuple[APIVersion | None, str]:
        """Extract version from query parameter."""
        version_str = request.query_params.get(self.query_param)
        if version_str:
            try:
                return APIVersion.parse(version_str), "query_param"
            except ValueError:
                pass
        return None, ""

    def _from_header(self, request: Request) -> tuple[APIVersion | None, str]:
        """Extract version from X-API-Version header."""
        version_str = request.headers.get(self.header_name)
        if version_str:
            try:
                return APIVersion.parse(version_str), "header"
            except ValueError:
                pass
        return None, ""

    def _from_accept_header(self, request: Request) -> tuple[APIVersion | None, str]:
        """Extract version from Accept header."""
        accept = request.headers.get("Accept", "")

        # Look for application/vnd.kg.api.v1+json pattern
        if self.accept_header_prefix in accept:
            # Extract version from accept header
            for part in accept.split(","):
                part = part.strip()
                if part.startswith(self.accept_header_prefix):
                    # Extract vX.Y from the media type
                    remaining = part[len(self.accept_header_prefix):]
                    if remaining.startswith(".v"):
                        version_part = remaining[1:].split("+")[0]
                        try:
                            return APIVersion.parse(version_part), "accept_header"
                        except ValueError:
                            pass

        return None, ""


class KGVersioningMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for API versioning."""

    def __init__(
        self,
        app,
        registry: VersionRegistry,
        negotiator: VersionNegotiator | None = None,
        enabled: bool = True,
        strict_mode: bool = False
    ):
        super().__init__(app)
        self.registry = registry
        self.negotiator = negotiator or VersionNegotiator(registry)
        self.enabled = enabled
        self.strict_mode = strict_mode

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through versioning middleware."""
        if not self.enabled:
            return await call_next(request)

        # Negotiate version
        try:
            version, source = self.negotiator.negotiate(request)
        except HTTPException as e:
            if self.strict_mode:
                raise
            version = self.registry.get_default_version()
            source = "fallback"

        # Check if version is supported
        if not self.registry.is_version_supported(version):
            version_info = self.registry.get_version_info(version)
            if version_info and version_info.status == VersionStatus.RETIRED:
                return self._version_error_response(
                    410,
                    f"API version {version} has been retired",
                    version
                )
            return self._version_error_response(
                400,
                f"API version {version} is not supported",
                version
            )

        # Check route availability
        path = request.url.path
        method = request.method
        available, warning = self.registry.is_route_available(path, method, version)

        if not available:
            return self._version_error_response(404, warning, version)

        # Store version in request state
        request.state.api_version = version
        request.state.api_version_source = source

        # Apply request transformation if needed
        transform = self.registry.get_request_transform(version, path)
        if transform:
            request = self._apply_request_transform(request, transform)

        # Call the actual endpoint
        response = await call_next(request)

        # Add version headers
        response.headers["X-API-Version"] = str(version)
        response.headers["X-API-Version-Source"] = source

        # Add deprecation warnings
        version_info = self.registry.get_version_info(version)
        if version_info:
            if version_info.status == VersionStatus.DEPRECATED:
                response.headers["Deprecation"] = "true"
                if version_info.sunset_at:
                    response.headers["Sunset"] = version_info.sunset_at.isoformat()
                if version_info.deprecation_message:
                    response.headers["X-Deprecation-Warning"] = version_info.deprecation_message

        # Add route-level deprecation warning
        if warning:
            response.headers["X-Route-Warning"] = warning

        # Apply response transformation if needed
        resp_transform = self.registry.get_response_transform(version, path)
        if resp_transform:
            response = await self._apply_response_transform(response, resp_transform)

        return response

    def _version_error_response(
        self,
        status_code: int,
        message: str,
        version: APIVersion
    ) -> Response:
        """Create error response for version issues."""
        from fastapi.responses import JSONResponse

        supported = [str(v) for v in self.registry.get_supported_versions()]

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": "version_error",
                    "message": message,
                    "requested_version": str(version),
                    "supported_versions": supported
                }
            },
            headers={
                "X-API-Version": str(version),
                "X-Supported-Versions": ", ".join(supported)
            }
        )

    def _apply_request_transform(
        self,
        request: Request,
        transform: RequestTransform
    ) -> Request:
        """Apply request transformation (placeholder for actual implementation)."""
        # In a real implementation, this would modify the request
        # based on the transformation rules
        return request

    async def _apply_response_transform(
        self,
        response: Response,
        transform: ResponseTransform
    ) -> Response:
        """Apply response transformation (placeholder for actual implementation)."""
        # In a real implementation, this would modify the response
        # based on the transformation rules
        return response


# Dependency injection helpers

def get_api_version(request: Request) -> APIVersion:
    """FastAPI dependency to get current API version."""
    if not hasattr(request.state, "api_version"):
        raise HTTPException(
            status_code=500,
            detail="API version not set. Is versioning middleware enabled?"
        )
    return request.state.api_version


def require_min_version(min_version: str | APIVersion):
    """FastAPI dependency factory to require minimum version."""
    if isinstance(min_version, str):
        min_version = APIVersion.parse(min_version)

    def dependency(request: Request) -> APIVersion:
        version = get_api_version(request)
        if version < min_version:
            raise HTTPException(
                status_code=400,
                detail=f"This endpoint requires API version >= {min_version}"
            )
        return version

    return dependency


def require_max_version(max_version: str | APIVersion):
    """FastAPI dependency factory to require maximum version."""
    if isinstance(max_version, str):
        max_version = APIVersion.parse(max_version)

    def dependency(request: Request) -> APIVersion:
        version = get_api_version(request)
        if version > max_version:
            raise HTTPException(
                status_code=400,
                detail=f"This endpoint is only available up to version {max_version}"
            )
        return version

    return dependency


# Factory functions

def create_kg_version_registry() -> VersionRegistry:
    """Create a pre-configured version registry for KG API."""
    registry = VersionRegistry()

    # Register KG API versions
    registry.register_version(
        APIVersion(1, 0),
        status=VersionStatus.DEPRECATED,
        released_at=date(2024, 1, 1),
        deprecated_at=date(2024, 6, 1),
        sunset_at=date(2025, 1, 1),
        changelog=[
            "Initial KG API release",
            "Basic concept lookup",
            "Path finding"
        ],
        deprecation_message="Please upgrade to v2.0 for improved functionality"
    )

    registry.register_version(
        APIVersion(1, 1),
        status=VersionStatus.DEPRECATED,
        released_at=date(2024, 3, 1),
        deprecated_at=date(2024, 9, 1),
        sunset_at=date(2025, 3, 1),
        changelog=[
            "Added batch operations",
            "Improved path scoring"
        ],
        deprecation_message="Please upgrade to v2.0"
    )

    registry.register_version(
        APIVersion(2, 0),
        status=VersionStatus.CURRENT,
        released_at=date(2024, 6, 1),
        changelog=[
            "New reasoning engine",
            "Multi-hop path finding",
            "Vector similarity search",
            "FHIR export support"
        ],
        breaking_changes=[
            "Changed response format for /concepts endpoint",
            "Renamed 'similarity' to 'semantic_similarity'",
            "Removed deprecated 'simple_search' endpoint"
        ]
    )

    registry.set_current_version(APIVersion(2, 0))
    registry.set_default_version(APIVersion(2, 0))

    # Register versioned routes
    registry.register_route(
        "/kg/concepts/simple_search",
        "GET",
        max_version=APIVersion(1, 1),
        removed_in=APIVersion(2, 0),
        replacement_path="/kg/concepts/search"
    )

    registry.register_route(
        "/kg/concepts/vector_search",
        "GET",
        min_version=APIVersion(2, 0)
    )

    registry.register_route(
        "/kg/reasoning/multi_hop",
        "POST",
        min_version=APIVersion(2, 0)
    )

    return registry


def create_kg_versioning_middleware(
    app,
    enabled: bool = True,
    strict_mode: bool = False,
    registry: VersionRegistry | None = None
) -> KGVersioningMiddleware:
    """Factory function to create versioning middleware."""
    if registry is None:
        registry = create_kg_version_registry()

    return KGVersioningMiddleware(
        app,
        registry=registry,
        enabled=enabled,
        strict_mode=strict_mode
    )


# Versioned router helper

class VersionedAPIRouter(APIRouter):
    """APIRouter with version awareness."""

    def __init__(self, *args, min_version: APIVersion | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_version = min_version

    def add_api_route(
        self,
        path: str,
        endpoint: Callable,
        *args,
        min_version: APIVersion | None = None,
        max_version: APIVersion | None = None,
        deprecated_in: APIVersion | None = None,
        **kwargs
    ):
        """Add a route with version constraints."""
        # Store version metadata
        endpoint._version_info = {
            "min_version": min_version or self.min_version,
            "max_version": max_version,
            "deprecated_in": deprecated_in
        }
        return super().add_api_route(path, endpoint, *args, **kwargs)
