"""Tests for API Versioning and Deprecation Policy (CTO-8).

Tests verify:
- API version lifecycle (CURRENT -> DEPRECATED -> SUNSET -> RETIRED)
- Version registration and retrieval
- Endpoint versioning and deprecation tracking
- Breaking change detection between versions
- Migration guide generation
- Client usage tracking
- Deprecation policy enforcement
- Deprecation timeline validation
- Response header generation for deprecated endpoints
- API endpoint integration tests
- Pre-populated sample data
- Edge cases and error handling
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.api_versioning import router as api_versioning_router
from app.schemas.api_versioning import (
    APIVersionListResponse,
    APIVersionRecord,
    APIVersionStatus,
    BreakingChangeReport,
    BreakingChangeType,
    ClientUsageRecord,
    ClientUsageResponse,
    DeprecatedEndpointResponse,
    DeprecationHeaders,
    DeprecationPolicy,
    EndpointVersionInfo,
    EndpointVersionListResponse,
    MigrationGuide,
)
from app.services.api_versioning_service import (
    MINIMUM_DEPRECATION_NOTICE_DAYS,
    MINIMUM_SUNSET_PERIOD_DAYS,
    APIVersioningService,
    get_api_versioning_service,
    reset_api_versioning_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_api_versioning_service()
    yield
    reset_api_versioning_service()


@pytest.fixture
def service() -> APIVersioningService:
    """Fresh APIVersioningService instance."""
    return APIVersioningService()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient with api versioning router mounted."""
    app = FastAPI()
    app.include_router(api_versioning_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# 1. Version Lifecycle Management
# ===========================================================================


class TestVersionLifecycle:
    """Test API version lifecycle state machine."""

    def test_initial_v1_is_current(self, service: APIVersioningService):
        """v1 should be pre-populated with CURRENT status."""
        record = service.get_version("v1")
        assert record is not None
        assert record.version == "v1"
        assert record.status == APIVersionStatus.CURRENT

    def test_list_versions_includes_v1(self, service: APIVersioningService):
        """list_versions should include the pre-populated v1."""
        result = service.list_versions()
        assert result.total >= 1
        assert result.current_version == "v1"
        versions = [v.version for v in result.versions]
        assert "v1" in versions

    def test_register_new_version(self, service: APIVersioningService):
        """Registering a new version creates it with CURRENT status."""
        now = datetime.now(timezone.utc)
        record = service.register_version(
            version="v2",
            release_date=now,
            changelog=["New patient search endpoint", "Enhanced NLP pipeline"],
        )
        assert record.version == "v2"
        assert record.status == APIVersionStatus.CURRENT
        assert len(record.changelog) == 2

    def test_register_duplicate_version_raises(self, service: APIVersioningService):
        """Registering a duplicate version should raise ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            service.register_version(
                version="v1",
                release_date=datetime.now(timezone.utc),
            )

    def test_deprecate_version(self, service: APIVersioningService):
        """Deprecating a CURRENT version transitions to DEPRECATED."""
        future_sunset = datetime.now(timezone.utc) + timedelta(days=200)
        record = service.deprecate_version("v1", sunset_date=future_sunset)
        assert record.status == APIVersionStatus.DEPRECATED
        assert record.deprecation_date is not None
        assert record.sunset_date is not None

    def test_deprecate_version_default_sunset(self, service: APIVersioningService):
        """Deprecating without explicit sunset uses policy minimum."""
        record = service.deprecate_version("v1")
        assert record.status == APIVersionStatus.DEPRECATED
        # Sunset should be at least MINIMUM_DEPRECATION_NOTICE_DAYS from now
        assert record.sunset_date is not None
        days_until_sunset = (record.sunset_date - record.deprecation_date).days
        assert days_until_sunset >= MINIMUM_DEPRECATION_NOTICE_DAYS

    def test_deprecate_with_short_notice_raises(self, service: APIVersioningService):
        """Deprecating with too short a notice period should raise."""
        short_sunset = datetime.now(timezone.utc) + timedelta(days=30)
        with pytest.raises(ValueError, match="at least"):
            service.deprecate_version("v1", sunset_date=short_sunset)

    def test_deprecate_non_current_raises(self, service: APIVersioningService):
        """Only CURRENT versions can be deprecated."""
        service.deprecate_version("v1")
        with pytest.raises(ValueError, match="Only CURRENT"):
            service.deprecate_version("v1")

    def test_sunset_version(self, service: APIVersioningService):
        """Sunset transitions DEPRECATED -> SUNSET."""
        service.deprecate_version("v1")
        record = service.sunset_version("v1")
        assert record.status == APIVersionStatus.SUNSET
        assert record.retirement_date is not None

    def test_sunset_non_deprecated_raises(self, service: APIVersioningService):
        """Only DEPRECATED versions can be sunset."""
        with pytest.raises(ValueError, match="Only DEPRECATED"):
            service.sunset_version("v1")

    def test_retire_version(self, service: APIVersioningService):
        """Retire transitions SUNSET -> RETIRED."""
        service.deprecate_version("v1")
        service.sunset_version("v1")
        record = service.retire_version("v1")
        assert record.status == APIVersionStatus.RETIRED
        assert record.retirement_date is not None

    def test_retire_non_sunset_raises(self, service: APIVersioningService):
        """Only SUNSET versions can be retired."""
        with pytest.raises(ValueError, match="Only SUNSET"):
            service.retire_version("v1")

    def test_full_lifecycle(self, service: APIVersioningService):
        """Test full lifecycle: CURRENT -> DEPRECATED -> SUNSET -> RETIRED."""
        # CURRENT -> DEPRECATED
        record = service.deprecate_version("v1")
        assert record.status == APIVersionStatus.DEPRECATED

        # DEPRECATED -> SUNSET
        record = service.sunset_version("v1")
        assert record.status == APIVersionStatus.SUNSET

        # SUNSET -> RETIRED
        record = service.retire_version("v1")
        assert record.status == APIVersionStatus.RETIRED

    def test_get_nonexistent_version(self, service: APIVersioningService):
        """Getting a nonexistent version returns None."""
        result = service.get_version("v99")
        assert result is None

    def test_deprecate_nonexistent_version_raises(self, service: APIVersioningService):
        """Deprecating a nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.deprecate_version("v99")

    def test_sunset_nonexistent_version_raises(self, service: APIVersioningService):
        """Sunsetting a nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.sunset_version("v99")

    def test_retire_nonexistent_version_raises(self, service: APIVersioningService):
        """Retiring a nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.retire_version("v99")


# ===========================================================================
# 2. Endpoint Versioning
# ===========================================================================


class TestEndpointVersioning:
    """Test per-endpoint versioning and deprecation tracking."""

    def test_get_v1_endpoints(self, service: APIVersioningService):
        """v1 should have pre-populated endpoints."""
        result = service.get_version_endpoints("v1")
        assert result.version == "v1"
        assert result.total > 0
        assert all(ep.introduced_in == "v1" for ep in result.endpoints)

    def test_register_new_endpoint(self, service: APIVersioningService):
        """Registering a new endpoint adds it to the version."""
        ep = service.register_endpoint("v1", "/api/v1/new-endpoint", "POST")
        assert ep.endpoint_path == "/api/v1/new-endpoint"
        assert ep.http_method == "POST"
        assert ep.introduced_in == "v1"

    def test_register_duplicate_endpoint_raises(self, service: APIVersioningService):
        """Registering a duplicate endpoint raises ValueError."""
        service.register_endpoint("v1", "/api/v1/unique-ep", "GET")
        with pytest.raises(ValueError, match="already exists"):
            service.register_endpoint("v1", "/api/v1/unique-ep", "GET")

    def test_register_endpoint_nonexistent_version_raises(self, service: APIVersioningService):
        """Registering in a nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.register_endpoint("v99", "/api/v99/test", "GET")

    def test_deprecate_endpoint(self, service: APIVersioningService):
        """Deprecating an endpoint sets deprecation metadata."""
        sunset = datetime.now(timezone.utc) + timedelta(days=180)
        ep = service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
            replacement_path="/api/v2/patients/search",
            replacement_method="GET",
            reason="Use new search endpoint with pagination",
            sunset_date=sunset,
        )
        assert ep.deprecated_in == "v2"
        assert ep.replacement_path == "/api/v2/patients/search"
        assert ep.deprecation_reason == "Use new search endpoint with pagination"
        assert ep.sunset_date == sunset

    def test_deprecate_nonexistent_endpoint_raises(self, service: APIVersioningService):
        """Deprecating a nonexistent endpoint raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.deprecate_endpoint(
                version="v1",
                endpoint_path="/api/v1/nonexistent",
                http_method="GET",
                deprecated_in="v2",
            )

    def test_get_all_deprecated_endpoints(self, service: APIVersioningService):
        """Get all deprecated endpoints across versions."""
        # Initially no deprecated endpoints
        result = service.get_all_deprecated_endpoints()
        assert result.total == 0

        # Deprecate one
        service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
        )
        result = service.get_all_deprecated_endpoints()
        assert result.total == 1
        assert result.endpoints[0].endpoint_path == "/api/v1/patients"

    def test_endpoint_version_list_deprecated_count(self, service: APIVersioningService):
        """deprecated_count is correctly calculated."""
        result = service.get_version_endpoints("v1")
        assert result.deprecated_count == 0

        service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
        )
        result = service.get_version_endpoints("v1")
        assert result.deprecated_count == 1

    def test_get_endpoints_nonexistent_version_raises(self, service: APIVersioningService):
        """Getting endpoints for nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.get_version_endpoints("v99")


# ===========================================================================
# 3. Deprecation Headers
# ===========================================================================


class TestDeprecationHeaders:
    """Test RFC 8594 deprecation header generation."""

    def test_no_headers_for_non_deprecated(self, service: APIVersioningService):
        """Non-deprecated endpoints return no headers."""
        headers = service.get_deprecation_headers("/api/v1/patients", "GET")
        assert headers is None

    def test_headers_for_deprecated_endpoint(self, service: APIVersioningService):
        """Deprecated endpoints return RFC 8594 headers."""
        sunset = datetime(2025, 7, 1, tzinfo=timezone.utc)
        service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
            replacement_path="/api/v2/patients/search",
            sunset_date=sunset,
        )
        headers = service.get_deprecation_headers("/api/v1/patients", "GET")
        assert headers is not None
        assert headers.deprecation == "true"
        assert headers.sunset is not None
        assert "2025" in headers.sunset
        assert headers.link is not None
        assert "/api/v2/patients/search" in headers.link
        assert 'rel="successor-version"' in headers.link

    def test_headers_without_sunset(self, service: APIVersioningService):
        """Deprecated endpoint without sunset has no sunset header."""
        service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
        )
        headers = service.get_deprecation_headers("/api/v1/patients", "GET")
        assert headers is not None
        assert headers.deprecation == "true"
        assert headers.sunset is None


# ===========================================================================
# 4. Breaking Change Detection
# ===========================================================================


class TestBreakingChangeDetection:
    """Test breaking change detection between API versions."""

    def test_no_breaking_changes_same_version(self, service: APIVersioningService):
        """Comparing a version to itself should find no breaking changes."""
        report = service.detect_breaking_changes("v1", "v1")
        assert report.is_compatible is True
        assert report.total_breaking == 0

    def test_detect_removed_endpoints(self, service: APIVersioningService):
        """Endpoints in v1 but not in v2 are flagged as removed."""
        # Register v2 with fewer endpoints
        service.register_version(
            version="v2",
            release_date=datetime.now(timezone.utc),
        )
        service.register_endpoint("v2", "/api/v2/patients", "GET")
        # v1 has many endpoints, v2 has only 1 -> many removed

        report = service.detect_breaking_changes("v1", "v2")
        assert report.is_compatible is False
        assert report.total_breaking > 0

        removed = [
            c for c in report.breaking_changes
            if c.change_type == BreakingChangeType.ENDPOINT_REMOVED
        ]
        assert len(removed) > 0

    def test_detect_added_endpoints_non_breaking(self, service: APIVersioningService):
        """New endpoints in v2 are non-breaking changes."""
        service.register_version(
            version="v2",
            release_date=datetime.now(timezone.utc),
        )
        # Copy all v1 endpoints to v2 and add extra
        v1_result = service.get_version_endpoints("v1")
        for ep in v1_result.endpoints:
            service.register_endpoint("v2", ep.endpoint_path, ep.http_method)
        service.register_endpoint("v2", "/api/v2/new-feature", "POST")

        report = service.detect_breaking_changes("v1", "v2")
        assert report.is_compatible is True
        assert report.total_non_breaking >= 1
        assert any("/api/v2/new-feature" in nb for nb in report.non_breaking_changes)

    def test_detect_schema_changes_for_deprecated_endpoints(self, service: APIVersioningService):
        """Deprecated endpoints with replacements flag potential schema changes."""
        service.register_version(
            version="v2",
            release_date=datetime.now(timezone.utc),
        )
        # Deprecate an endpoint and point to replacement in v2
        service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
            replacement_path="/api/v2/patients/search",
            replacement_method="GET",
        )
        service.register_endpoint("v2", "/api/v2/patients/search", "GET")

        report = service.detect_breaking_changes("v1", "v2")
        schema_changes = [
            c for c in report.breaking_changes
            if c.change_type == BreakingChangeType.REQUEST_SCHEMA_CHANGED
        ]
        assert len(schema_changes) >= 1

    def test_breaking_changes_nonexistent_version_raises(self, service: APIVersioningService):
        """Checking breaking changes with nonexistent version raises."""
        with pytest.raises(ValueError, match="not found"):
            service.detect_breaking_changes("v1", "v99")

    def test_report_recommendation_compatible(self, service: APIVersioningService):
        """Compatible migration should get appropriate recommendation."""
        report = service.detect_breaking_changes("v1", "v1")
        assert "compatible" in report.recommendation.lower()

    def test_report_recommendation_breaking(self, service: APIVersioningService):
        """Breaking migration should get appropriate recommendation."""
        service.register_version("v2", release_date=datetime.now(timezone.utc))
        report = service.detect_breaking_changes("v1", "v2")
        # v2 has no endpoints, so everything from v1 is removed
        assert "breaking" in report.recommendation.lower()


# ===========================================================================
# 5. Migration Guide Generation
# ===========================================================================


class TestMigrationGuide:
    """Test migration guide generation."""

    def test_migration_guide_same_version(self, service: APIVersioningService):
        """Migration guide for same version should be straightforward."""
        guide = service.generate_migration_guide("v1", "v1")
        assert guide.from_version == "v1"
        assert guide.to_version == "v1"
        assert guide.estimated_effort == "LOW"
        assert len(guide.steps) >= 2  # At least inventory + testing steps

    def test_migration_guide_with_breaking_changes(self, service: APIVersioningService):
        """Migration guide with breaking changes should list migration steps."""
        service.register_version("v2", release_date=datetime.now(timezone.utc))
        service.register_endpoint("v2", "/api/v2/patients/search", "GET")

        guide = service.generate_migration_guide("v1", "v2")
        assert guide.breaking_changes_count > 0
        assert guide.estimated_effort in ("MEDIUM", "HIGH")
        assert len(guide.steps) >= 3  # inventory + breaking changes + testing

    def test_migration_guide_includes_deprecation_warnings(self, service: APIVersioningService):
        """Migration guide includes deprecation warnings."""
        service.deprecate_endpoint(
            version="v1",
            endpoint_path="/api/v1/patients",
            http_method="GET",
            deprecated_in="v2",
            replacement_path="/api/v2/patients/search",
        )
        service.register_version("v2", release_date=datetime.now(timezone.utc))

        guide = service.generate_migration_guide("v1", "v2")
        assert len(guide.deprecation_warnings) >= 1
        assert any("/api/v1/patients" in w for w in guide.deprecation_warnings)

    def test_migration_guide_has_rollback_instructions(self, service: APIVersioningService):
        """Migration guide always includes rollback instructions."""
        guide = service.generate_migration_guide("v1", "v1")
        assert guide.rollback_instructions is not None
        assert len(guide.rollback_instructions) > 0

    def test_migration_guide_nonexistent_version_raises(self, service: APIVersioningService):
        """Migration guide with nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.generate_migration_guide("v1", "v99")

    def test_migration_guide_step_ordering(self, service: APIVersioningService):
        """Migration steps should be sequentially numbered."""
        guide = service.generate_migration_guide("v1", "v1")
        for i, step in enumerate(guide.steps):
            assert step.step_number == i + 1


# ===========================================================================
# 6. Client Usage Tracking
# ===========================================================================


class TestClientUsageTracking:
    """Test client API version usage tracking."""

    def test_track_new_client(self, service: APIVersioningService):
        """Tracking a new client creates a usage record."""
        record = service.track_client_usage("client-001", "v1")
        assert record.client_id == "client-001"
        assert record.api_version == "v1"
        assert record.request_count == 1
        assert record.using_deprecated is False

    def test_track_existing_client_increments_count(self, service: APIVersioningService):
        """Tracking an existing client increments request count."""
        service.track_client_usage("client-001", "v1")
        record = service.track_client_usage("client-001", "v1")
        assert record.request_count == 2

    def test_track_client_on_deprecated_version(self, service: APIVersioningService):
        """Clients on deprecated versions are flagged."""
        service.deprecate_version("v1")
        record = service.track_client_usage("client-001", "v1")
        assert record.using_deprecated is True

    def test_get_client_usage_stats(self, service: APIVersioningService):
        """Client usage stats aggregate correctly."""
        service.track_client_usage("client-001", "v1")
        service.track_client_usage("client-002", "v1")
        service.track_client_usage("client-003", "v1")

        stats = service.get_client_usage()
        assert stats.total_clients == 3
        assert stats.clients_on_current == 3
        assert stats.version_distribution["v1"] == 3

    def test_get_client_usage_version_distribution(self, service: APIVersioningService):
        """Version distribution shows clients per version."""
        service.register_version("v2", release_date=datetime.now(timezone.utc))
        service.track_client_usage("client-001", "v1")
        service.track_client_usage("client-002", "v2")

        stats = service.get_client_usage()
        assert "v1" in stats.version_distribution
        assert "v2" in stats.version_distribution

    def test_get_clients_on_deprecated(self, service: APIVersioningService):
        """Can retrieve only clients on deprecated versions."""
        service.deprecate_version("v1")
        service.track_client_usage("client-001", "v1")

        deprecated_clients = service.get_clients_on_deprecated_versions()
        assert len(deprecated_clients) == 1
        assert deprecated_clients[0].client_id == "client-001"

    def test_empty_client_usage(self, service: APIVersioningService):
        """Empty client usage returns zero stats."""
        stats = service.get_client_usage()
        assert stats.total_clients == 0
        assert stats.clients_on_deprecated == 0
        assert stats.clients_on_current == 0


# ===========================================================================
# 7. Deprecation Policy
# ===========================================================================


class TestDeprecationPolicy:
    """Test deprecation policy configuration and validation."""

    def test_get_deprecation_policy(self, service: APIVersioningService):
        """Deprecation policy returns configured values."""
        policy = service.get_deprecation_policy()
        assert policy.minimum_deprecation_notice_days == 180
        assert policy.minimum_sunset_period_days == 90
        assert policy.breaking_change_requires_new_version is True
        assert policy.non_breaking_additions_allowed is True
        assert policy.sunset_mode_read_only is True
        assert policy.versioning_strategy == "URI"

    def test_validate_valid_timeline(self, service: APIVersioningService):
        """Valid deprecation timeline passes validation."""
        now = datetime.now(timezone.utc)
        result = service.validate_deprecation_timeline(
            deprecation_date=now,
            sunset_date=now + timedelta(days=200),
            retirement_date=now + timedelta(days=300),
        )
        assert result["valid"] is True

    def test_validate_short_deprecation_notice(self, service: APIVersioningService):
        """Too short deprecation notice fails validation."""
        now = datetime.now(timezone.utc)
        result = service.validate_deprecation_timeline(
            deprecation_date=now,
            sunset_date=now + timedelta(days=30),  # Too short
        )
        assert result["valid"] is False
        assert "less than" in str(result["errors"]).lower()

    def test_validate_short_sunset_period(self, service: APIVersioningService):
        """Too short sunset period fails validation."""
        now = datetime.now(timezone.utc)
        result = service.validate_deprecation_timeline(
            deprecation_date=now,
            sunset_date=now + timedelta(days=200),
            retirement_date=now + timedelta(days=210),  # Only 10 days sunset
        )
        assert result["valid"] is False
        assert "less than" in str(result["errors"]).lower()

    def test_validate_both_violations(self, service: APIVersioningService):
        """Both violations are reported."""
        now = datetime.now(timezone.utc)
        result = service.validate_deprecation_timeline(
            deprecation_date=now,
            sunset_date=now + timedelta(days=30),  # Too short notice
            retirement_date=now + timedelta(days=40),  # Too short sunset
        )
        assert result["valid"] is False
        errors = str(result["errors"])
        assert ";" in errors  # Multiple errors separated by semicolons


# ===========================================================================
# 8. Service Stats
# ===========================================================================


class TestServiceStats:
    """Test service statistics."""

    def test_get_stats(self, service: APIVersioningService):
        """Service stats return expected keys."""
        stats = service.get_stats()
        assert "total_versions" in stats
        assert "total_endpoints" in stats
        assert "deprecated_endpoints" in stats
        assert "tracked_clients" in stats
        assert "policy_version" in stats
        assert stats["total_versions"] >= 1
        assert stats["total_endpoints"] >= 1

    def test_stats_update_after_tracking(self, service: APIVersioningService):
        """Stats update after tracking clients."""
        service.track_client_usage("test-client", "v1")
        stats = service.get_stats()
        assert stats["tracked_clients"] == 1


# ===========================================================================
# 9. Singleton Pattern
# ===========================================================================


class TestSingleton:
    """Test singleton pattern for service."""

    def test_singleton_returns_same_instance(self):
        """get_api_versioning_service returns the same instance."""
        svc1 = get_api_versioning_service()
        svc2 = get_api_versioning_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset_api_versioning_service clears the singleton."""
        svc1 = get_api_versioning_service()
        reset_api_versioning_service()
        svc2 = get_api_versioning_service()
        assert svc1 is not svc2


# ===========================================================================
# 10. API Endpoint Integration Tests
# ===========================================================================


class TestAPIEndpoints:
    """Integration tests for API versioning endpoints."""

    def test_list_versions_endpoint(self, client: TestClient):
        """GET /api-management/versions returns version list."""
        resp = client.get("/api/v1/api-management/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert "current_version" in data
        assert data["total"] >= 1

    def test_get_version_detail_endpoint(self, client: TestClient):
        """GET /api-management/versions/v1 returns version detail."""
        resp = client.get("/api/v1/api-management/versions/v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1"
        assert data["status"] == "CURRENT"

    def test_get_version_detail_not_found(self, client: TestClient):
        """GET /api-management/versions/v99 returns 404."""
        resp = client.get("/api/v1/api-management/versions/v99")
        assert resp.status_code == 404

    def test_get_version_endpoints_endpoint(self, client: TestClient):
        """GET /api-management/versions/v1/endpoints returns endpoint list."""
        resp = client.get("/api/v1/api-management/versions/v1/endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1"
        assert data["total"] > 0

    def test_get_version_endpoints_not_found(self, client: TestClient):
        """GET /api-management/versions/v99/endpoints returns 404."""
        resp = client.get("/api/v1/api-management/versions/v99/endpoints")
        assert resp.status_code == 404

    def test_deprecated_endpoints_endpoint(self, client: TestClient):
        """GET /api-management/deprecated returns deprecated list."""
        resp = client.get("/api/v1/api-management/deprecated")
        assert resp.status_code == 200
        data = resp.json()
        assert "endpoints" in data
        assert "total" in data

    def test_migration_guide_endpoint(self, client: TestClient):
        """GET /api-management/migration-guide/v1/v1 returns guide."""
        resp = client.get("/api/v1/api-management/migration-guide/v1/v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_version"] == "v1"
        assert data["to_version"] == "v1"
        assert "steps" in data

    def test_migration_guide_not_found(self, client: TestClient):
        """GET /api-management/migration-guide/v1/v99 returns 404."""
        resp = client.get("/api/v1/api-management/migration-guide/v1/v99")
        assert resp.status_code == 404

    def test_client_usage_endpoint(self, client: TestClient):
        """GET /api-management/client-usage returns usage stats."""
        resp = client.get("/api/v1/api-management/client-usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "clients" in data
        assert "total_clients" in data

    def test_check_breaking_changes_endpoint(self, client: TestClient):
        """POST /api-management/check-breaking-changes returns report."""
        resp = client.post(
            "/api/v1/api-management/check-breaking-changes",
            json={"from_version": "v1", "to_version": "v1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_compatible"] is True
        assert data["total_breaking"] == 0

    def test_check_breaking_changes_not_found(self, client: TestClient):
        """POST /api-management/check-breaking-changes with bad version returns 404."""
        resp = client.post(
            "/api/v1/api-management/check-breaking-changes",
            json={"from_version": "v1", "to_version": "v99"},
        )
        assert resp.status_code == 404

    def test_deprecation_policy_endpoint(self, client: TestClient):
        """GET /api-management/deprecation-policy returns policy."""
        resp = client.get("/api/v1/api-management/deprecation-policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["minimum_deprecation_notice_days"] == 180
        assert data["minimum_sunset_period_days"] == 90
        assert data["versioning_strategy"] == "URI"

    def test_version_detail_has_changelog(self, client: TestClient):
        """Version detail includes changelog entries."""
        resp = client.get("/api/v1/api-management/versions/v1")
        assert resp.status_code == 200
        data = resp.json()
        assert "changelog" in data
        assert len(data["changelog"]) > 0

    def test_endpoints_have_http_methods(self, client: TestClient):
        """All endpoints include HTTP method info."""
        resp = client.get("/api/v1/api-management/versions/v1/endpoints")
        assert resp.status_code == 200
        data = resp.json()
        for ep in data["endpoints"]:
            assert "http_method" in ep
            assert ep["http_method"] in ("GET", "POST", "PUT", "DELETE", "PATCH")
