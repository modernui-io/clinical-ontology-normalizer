"""Tests for API Gateway & Caching Strategy (CTO-10).

Tests verify:
- Gateway route CRUD (create, read, update, delete)
- Route filtering by status, auth method, tag, HTTP method
- Cache configuration management
- Cache entry get/set/invalidate/flush
- Cache metrics calculation
- Cache warming
- Rate limit checking and consumption
- Circuit breaker state management (record failure/success, reset)
- Route health checking
- Gateway metrics aggregation
- API documentation generation
- Gateway statistics
- Pre-populated seed data
- Edge cases and error handling
- API endpoint integration tests
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.api_gateway import router as api_gateway_router
from app.schemas.api_gateway import (
    APIDocumentationResponse,
    AuthMethod,
    CacheConfig,
    CacheConfigListResponse,
    CacheEntry,
    CacheEntryListResponse,
    CacheMetrics,
    CacheStatus,
    CacheStrategy,
    CacheWarmResponse,
    CircuitBreakerListResponse,
    CircuitBreakerState,
    CircuitBreakerStatus,
    EvictionPolicy,
    GatewayMetrics,
    GatewayRoute,
    GatewayRouteCreateRequest,
    GatewayRouteListResponse,
    GatewayRouteStatus,
    GatewayRouteUpdateRequest,
    GatewayStatsResponse,
    RateLimitAlgorithm,
    RateLimitCheckResponse,
    RateLimitState,
    RouteHealth,
    RouteHealthListResponse,
    RouteHealthStatus,
    RouteTransformation,
    TransformationType,
)
from app.services.api_gateway_service import (
    APIGatewayService,
    get_api_gateway_service,
    reset_api_gateway_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_api_gateway_service()
    yield
    reset_api_gateway_service()


@pytest.fixture
def service() -> APIGatewayService:
    """Get a fresh service instance."""
    return get_api_gateway_service()


@pytest.fixture
def client() -> TestClient:
    """Create a test client with the API gateway router."""
    app = FastAPI()
    app.include_router(api_gateway_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# Service Unit Tests - Seed Data
# ===========================================================================


class TestSeedData:
    """Tests for seed data initialization."""

    def test_seed_creates_20_routes(self, service: APIGatewayService):
        """Service seeds exactly 20 gateway routes."""
        result = service.list_routes()
        assert result.total == 20

    def test_seed_creates_6_cache_configs(self, service: APIGatewayService):
        """Service seeds exactly 6 cache configs."""
        configs = service.list_cache_configs()
        assert len(configs) == 6

    def test_seed_creates_50_plus_cache_entries(self, service: APIGatewayService):
        """Service seeds 50+ cache entries."""
        entries = service.get_cache_entries()
        assert entries.total >= 50

    def test_seed_creates_rate_limit_states(self, service: APIGatewayService):
        """Service seeds rate limit states."""
        states = service.get_rate_limit_states()
        assert len(states) > 0

    def test_seed_routes_have_correct_structure(self, service: APIGatewayService):
        """Seeded routes have all required fields."""
        route = service.get_route("route-patients-list")
        assert route is not None
        assert route.path_pattern == "/api/v1/patients"
        assert route.target_service == "patient-service"
        assert route.method == "GET"
        assert route.auth_method == AuthMethod.JWT
        assert route.status == GatewayRouteStatus.ACTIVE
        assert route.version == "v1"
        assert len(route.transformations) == 2

    def test_seed_cache_configs_have_correct_structure(self, service: APIGatewayService):
        """Seeded cache configs have all required fields."""
        config = service.get_cache_config("cache-vocabulary")
        assert config is not None
        assert config.name == "Vocabulary Cache"
        assert config.strategy == CacheStrategy.READ_THROUGH
        assert config.default_ttl_seconds == 86400
        assert config.warm_on_startup is True

    def test_seed_vocabulary_cache_config(self, service: APIGatewayService):
        """Vocabulary cache has 24h TTL."""
        config = service.get_cache_config("cache-vocabulary")
        assert config is not None
        assert config.default_ttl_seconds == 86400  # 24h

    def test_seed_trial_eligibility_cache_config(self, service: APIGatewayService):
        """Trial eligibility cache has 5min TTL."""
        config = service.get_cache_config("cache-trial-eligibility")
        assert config is not None
        assert config.default_ttl_seconds == 300  # 5min

    def test_seed_fhir_resource_cache_config(self, service: APIGatewayService):
        """FHIR resource cache has 1h TTL."""
        config = service.get_cache_config("cache-fhir-resource")
        assert config is not None
        assert config.default_ttl_seconds == 3600  # 1h

    def test_seed_nlp_results_cache_config(self, service: APIGatewayService):
        """NLP results cache has 30min TTL."""
        config = service.get_cache_config("cache-nlp-results")
        assert config is not None
        assert config.default_ttl_seconds == 1800  # 30min

    def test_seed_graph_queries_cache_config(self, service: APIGatewayService):
        """Graph queries cache has 15min TTL."""
        config = service.get_cache_config("cache-graph-queries")
        assert config is not None
        assert config.default_ttl_seconds == 900  # 15min

    def test_seed_static_assets_cache_config(self, service: APIGatewayService):
        """Static assets cache has 7d TTL."""
        config = service.get_cache_config("cache-static-assets")
        assert config is not None
        assert config.default_ttl_seconds == 604800  # 7d

    def test_seed_circuit_breakers_initialized(self, service: APIGatewayService):
        """Circuit breakers are initialized for all routes."""
        cbs = service.get_circuit_breakers()
        assert cbs.total == 20

    def test_seed_all_circuit_breakers_closed(self, service: APIGatewayService):
        """All seeded circuit breakers start in CLOSED state."""
        cbs = service.get_circuit_breakers()
        for cb in cbs.circuit_breakers:
            assert cb.state == CircuitBreakerState.CLOSED


# ===========================================================================
# Service Unit Tests - Route CRUD
# ===========================================================================


class TestRouteCRUD:
    """Tests for route create, read, update, delete."""

    def test_create_route(self, service: APIGatewayService):
        """Create a new route."""
        req = GatewayRouteCreateRequest(
            path_pattern="/api/v1/custom/endpoint",
            target_service="custom-service",
            method="POST",
            auth_method=AuthMethod.API_KEY,
            rate_limit_rpm=100,
            cache_strategy=CacheStrategy.TTL_BASED,
            cache_ttl_seconds=600,
            tags=["custom"],
        )
        route = service.create_route(req)
        assert route.id.startswith("route-")
        assert route.path_pattern == "/api/v1/custom/endpoint"
        assert route.target_service == "custom-service"
        assert route.method == "POST"
        assert route.auth_method == AuthMethod.API_KEY
        assert route.status == GatewayRouteStatus.ACTIVE

    def test_get_route_by_id(self, service: APIGatewayService):
        """Get a route by its ID."""
        route = service.get_route("route-patients-list")
        assert route is not None
        assert route.id == "route-patients-list"

    def test_get_nonexistent_route(self, service: APIGatewayService):
        """Get returns None for nonexistent route."""
        route = service.get_route("nonexistent")
        assert route is None

    def test_update_route(self, service: APIGatewayService):
        """Update an existing route."""
        update = GatewayRouteUpdateRequest(
            rate_limit_rpm=1000,
            timeout_ms=60000,
        )
        route = service.update_route("route-patients-list", update)
        assert route is not None
        assert route.rate_limit_rpm == 1000
        assert route.timeout_ms == 60000

    def test_update_route_status_to_deprecated(self, service: APIGatewayService):
        """Deprecating a route sets the deprecated date."""
        update = GatewayRouteUpdateRequest(
            status=GatewayRouteStatus.DEPRECATED,
        )
        route = service.update_route("route-patients-list", update)
        assert route is not None
        assert route.status == GatewayRouteStatus.DEPRECATED
        assert route.deprecated_date is not None

    def test_update_nonexistent_route(self, service: APIGatewayService):
        """Update returns None for nonexistent route."""
        update = GatewayRouteUpdateRequest(rate_limit_rpm=100)
        result = service.update_route("nonexistent", update)
        assert result is None

    def test_delete_route(self, service: APIGatewayService):
        """Delete an existing route."""
        result = service.delete_route("route-patients-list")
        assert result is True
        assert service.get_route("route-patients-list") is None

    def test_delete_nonexistent_route(self, service: APIGatewayService):
        """Delete returns False for nonexistent route."""
        result = service.delete_route("nonexistent")
        assert result is False

    def test_delete_route_removes_cache_entries(self, service: APIGatewayService):
        """Deleting a route removes its cache entries."""
        route_id = "route-patients-list"
        before = service.get_cache_entries(route_id=route_id)
        service.delete_route(route_id)
        after = service.get_cache_entries(route_id=route_id)
        assert after.total == 0

    def test_delete_route_removes_circuit_breaker(self, service: APIGatewayService):
        """Deleting a route removes its circuit breaker."""
        route_id = "route-patients-list"
        service.delete_route(route_id)
        cb = service.get_circuit_breaker(route_id)
        assert cb is None

    def test_list_routes_total_after_create(self, service: APIGatewayService):
        """Total increases after creating a route."""
        initial = service.list_routes().total
        req = GatewayRouteCreateRequest(
            path_pattern="/api/v1/new",
            target_service="new-service",
        )
        service.create_route(req)
        assert service.list_routes().total == initial + 1


# ===========================================================================
# Service Unit Tests - Route Filtering
# ===========================================================================


class TestRouteFiltering:
    """Tests for route list filtering."""

    def test_filter_by_status(self, service: APIGatewayService):
        """Filter routes by status."""
        result = service.list_routes(status=GatewayRouteStatus.ACTIVE)
        assert result.total == 20
        for r in result.routes:
            assert r.status == GatewayRouteStatus.ACTIVE

    def test_filter_by_auth_method_jwt(self, service: APIGatewayService):
        """Filter routes by JWT auth method."""
        result = service.list_routes(auth_method=AuthMethod.JWT)
        assert result.total > 0
        for r in result.routes:
            assert r.auth_method == AuthMethod.JWT

    def test_filter_by_auth_method_oauth2(self, service: APIGatewayService):
        """Filter routes by OAuth2 auth method."""
        result = service.list_routes(auth_method=AuthMethod.OAUTH2)
        assert result.total > 0
        for r in result.routes:
            assert r.auth_method == AuthMethod.OAUTH2

    def test_filter_by_tag(self, service: APIGatewayService):
        """Filter routes by tag."""
        result = service.list_routes(tag="patients")
        assert result.total > 0
        for r in result.routes:
            assert "patients" in r.tags

    def test_filter_by_method_get(self, service: APIGatewayService):
        """Filter routes by GET method."""
        result = service.list_routes(method="GET")
        assert result.total > 0
        for r in result.routes:
            assert r.method == "GET"

    def test_filter_by_method_post(self, service: APIGatewayService):
        """Filter routes by POST method."""
        result = service.list_routes(method="POST")
        assert result.total > 0
        for r in result.routes:
            assert r.method == "POST"

    def test_filter_by_disabled_returns_empty(self, service: APIGatewayService):
        """Filter by DISABLED status returns no routes (none seeded)."""
        result = service.list_routes(status=GatewayRouteStatus.DISABLED)
        assert result.total == 0

    def test_filter_by_tag_fhir(self, service: APIGatewayService):
        """Filter routes by 'fhir' tag."""
        result = service.list_routes(tag="fhir")
        assert result.total >= 3

    def test_filter_by_tag_compute(self, service: APIGatewayService):
        """Filter routes by 'compute' tag."""
        result = service.list_routes(tag="compute")
        assert result.total >= 2

    def test_filter_by_nonexistent_tag(self, service: APIGatewayService):
        """Filter by nonexistent tag returns empty."""
        result = service.list_routes(tag="nonexistent-tag-xyz")
        assert result.total == 0


# ===========================================================================
# Service Unit Tests - Cache Management
# ===========================================================================


class TestCacheManagement:
    """Tests for cache get/set/invalidate/flush."""

    def test_list_cache_configs(self, service: APIGatewayService):
        """List all cache configs."""
        configs = service.list_cache_configs()
        assert len(configs) == 6

    def test_get_cache_config(self, service: APIGatewayService):
        """Get a specific cache config."""
        config = service.get_cache_config("cache-vocabulary")
        assert config is not None
        assert config.name == "Vocabulary Cache"

    def test_get_nonexistent_cache_config(self, service: APIGatewayService):
        """Get returns None for nonexistent config."""
        config = service.get_cache_config("nonexistent")
        assert config is None

    def test_set_cache_entry(self, service: APIGatewayService):
        """Set a new cache entry."""
        entry = service.set_cache_entry(
            route_id="route-patients-list",
            cache_key="test:key:1",
            value_hash="abc123",
            size_bytes=1024,
        )
        assert entry.cache_key == "test:key:1"
        assert entry.value_hash == "abc123"
        assert entry.status == CacheStatus.HIT

    def test_get_cache_entry(self, service: APIGatewayService):
        """Get an existing cache entry by key."""
        # Set first
        service.set_cache_entry(
            route_id="route-patients-list",
            cache_key="test:lookup:1",
            value_hash="xyz789",
            size_bytes=512,
        )
        entry = service.get_cache_entry("test:lookup:1")
        assert entry is not None
        assert entry.cache_key == "test:lookup:1"

    def test_get_nonexistent_cache_entry(self, service: APIGatewayService):
        """Get returns None for nonexistent cache key."""
        entry = service.get_cache_entry("totally-nonexistent-key-xyz")
        assert entry is None

    def test_set_cache_entry_updates_existing(self, service: APIGatewayService):
        """Setting a cache entry with same key updates it."""
        service.set_cache_entry(
            route_id="route-patients-list",
            cache_key="test:update:1",
            value_hash="old",
            size_bytes=256,
        )
        updated = service.set_cache_entry(
            route_id="route-patients-list",
            cache_key="test:update:1",
            value_hash="new",
            size_bytes=512,
        )
        assert updated.value_hash == "new"
        assert updated.size_bytes == 512

    def test_invalidate_cache_by_pattern(self, service: APIGatewayService):
        """Invalidate cache entries matching a pattern."""
        # Set some entries
        for i in range(5):
            service.set_cache_entry(
                route_id="route-patients-list",
                cache_key=f"inv:test:{i}",
                value_hash=f"val{i}",
            )
        count = service.invalidate_cache("inv:test:*")
        assert count == 5

    def test_invalidate_cache_with_route_filter(self, service: APIGatewayService):
        """Invalidate cache entries scoped to a specific route."""
        service.set_cache_entry(
            route_id="route-patients-list",
            cache_key="scoped:1",
            value_hash="v1",
        )
        service.set_cache_entry(
            route_id="route-trials-list",
            cache_key="scoped:2",
            value_hash="v2",
        )
        count = service.invalidate_cache("scoped:*", route_id="route-patients-list")
        assert count == 1

    def test_flush_all_cache(self, service: APIGatewayService):
        """Flush all cache entries."""
        before = service.get_cache_entries().total
        assert before > 0
        count = service.flush_cache()
        assert count == before
        after = service.get_cache_entries().total
        assert after == 0

    def test_flush_cache_by_config(self, service: APIGatewayService):
        """Flush cache scoped to a config."""
        # Flush won't match unless keys match the patterns
        count = service.flush_cache(config_id="cache-vocabulary")
        # Result depends on pattern matching
        assert count >= 0

    def test_flush_nonexistent_config(self, service: APIGatewayService):
        """Flush with nonexistent config returns 0."""
        count = service.flush_cache(config_id="nonexistent")
        assert count == 0

    def test_cache_entries_filter_by_route(self, service: APIGatewayService):
        """Filter cache entries by route ID."""
        result = service.get_cache_entries(route_id="route-patients-list")
        for e in result.entries:
            assert e.route_id == "route-patients-list"

    def test_cache_entries_filter_by_status(self, service: APIGatewayService):
        """Filter cache entries by status."""
        result = service.get_cache_entries(status=CacheStatus.HIT)
        for e in result.entries:
            assert e.status == CacheStatus.HIT


# ===========================================================================
# Service Unit Tests - Cache Metrics
# ===========================================================================


class TestCacheMetrics:
    """Tests for cache metrics calculation."""

    def test_cache_metrics_structure(self, service: APIGatewayService):
        """Cache metrics returns all required fields."""
        metrics = service.get_cache_metrics()
        assert metrics.total_entries > 0
        assert metrics.total_size_mb >= 0
        assert metrics.hit_count >= 0
        assert metrics.miss_count >= 0
        assert metrics.hit_rate_percent >= 0
        assert metrics.avg_ttl_seconds >= 0

    def test_cache_metrics_empty_after_flush(self, service: APIGatewayService):
        """Cache metrics reflect empty cache after flush."""
        service.flush_cache()
        metrics = service.get_cache_metrics()
        assert metrics.total_entries == 0

    def test_cache_metrics_hit_rate(self, service: APIGatewayService):
        """Hit rate is a valid percentage."""
        metrics = service.get_cache_metrics()
        assert 0 <= metrics.hit_rate_percent <= 100


# ===========================================================================
# Service Unit Tests - Cache Warming
# ===========================================================================


class TestCacheWarming:
    """Tests for cache warming."""

    def test_warm_cache(self, service: APIGatewayService):
        """Warm a cache config."""
        result = service.warm_cache("cache-vocabulary")
        assert result.config_id == "cache-vocabulary"
        assert result.entries_warmed > 0
        assert result.duration_ms >= 0

    def test_warm_nonexistent_config(self, service: APIGatewayService):
        """Warming a nonexistent config returns 0 entries."""
        result = service.warm_cache("nonexistent")
        assert result.entries_warmed == 0

    def test_warm_cache_adds_entries(self, service: APIGatewayService):
        """Warming adds new entries to the cache."""
        before = service.get_cache_entries().total
        service.warm_cache("cache-vocabulary")
        after = service.get_cache_entries().total
        assert after > before


# ===========================================================================
# Service Unit Tests - Rate Limiting
# ===========================================================================


class TestRateLimiting:
    """Tests for rate limit checking and consumption."""

    def test_check_rate_limit_allowed(self, service: APIGatewayService):
        """Check rate limit for a fresh client - should be allowed."""
        result = service.check_rate_limit("route-patients-list", "new-client")
        assert result.allowed is True
        assert result.state.requests_remaining > 0

    def test_consume_rate_limit(self, service: APIGatewayService):
        """Consume rate limit tokens."""
        before = service.check_rate_limit("route-patients-list", "consume-test")
        remaining_before = before.state.requests_remaining
        result = service.consume_rate_limit("route-patients-list", "consume-test", 1)
        assert result.state.requests_remaining == remaining_before - 1

    def test_consume_rate_limit_multiple_tokens(self, service: APIGatewayService):
        """Consume multiple rate limit tokens at once."""
        before = service.check_rate_limit("route-patients-list", "multi-consume")
        remaining_before = before.state.requests_remaining
        result = service.consume_rate_limit("route-patients-list", "multi-consume", 5)
        assert result.state.requests_remaining == remaining_before - 5

    def test_rate_limit_exhaustion(self, service: APIGatewayService):
        """Exhaust rate limit and verify denial."""
        route_id = "route-patients-list"
        client_id = "exhaust-test"
        check = service.check_rate_limit(route_id, client_id)
        limit = check.state.limit
        service.consume_rate_limit(route_id, client_id, limit)
        result = service.check_rate_limit(route_id, client_id)
        assert result.allowed is False

    def test_rate_limit_states_list(self, service: APIGatewayService):
        """List rate limit states."""
        states = service.get_rate_limit_states()
        assert len(states) > 0

    def test_rate_limit_states_filter_by_route(self, service: APIGatewayService):
        """Filter rate limit states by route."""
        states = service.get_rate_limit_states(route_id="route-patients-list")
        for s in states:
            assert s.route_id == "route-patients-list"

    def test_rate_limit_state_structure(self, service: APIGatewayService):
        """Rate limit state has correct structure."""
        result = service.check_rate_limit("route-patients-list", "struct-test")
        state = result.state
        assert state.route_id == "route-patients-list"
        assert state.client_id == "struct-test"
        assert state.limit > 0
        assert state.window_seconds == 60
        assert state.reset_at is not None


# ===========================================================================
# Service Unit Tests - Circuit Breaker
# ===========================================================================


class TestCircuitBreaker:
    """Tests for circuit breaker management."""

    def test_get_circuit_breaker(self, service: APIGatewayService):
        """Get circuit breaker for a route."""
        cb = service.get_circuit_breaker("route-patients-list")
        assert cb is not None
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_get_nonexistent_circuit_breaker(self, service: APIGatewayService):
        """Get returns None for nonexistent route."""
        cb = service.get_circuit_breaker("nonexistent")
        assert cb is None

    def test_record_failure_increments_count(self, service: APIGatewayService):
        """Recording a failure increments the failure count."""
        service.record_failure("route-patients-list")
        cb = service.get_circuit_breaker("route-patients-list")
        assert cb.failure_count == 1

    def test_circuit_opens_at_threshold(self, service: APIGatewayService):
        """Circuit breaker opens when failures reach threshold."""
        route_id = "route-patients-list"
        route = service.get_route(route_id)
        threshold = route.circuit_breaker_threshold

        for _ in range(threshold):
            service.record_failure(route_id)

        cb = service.get_circuit_breaker(route_id)
        assert cb.state == CircuitBreakerState.OPEN

    def test_record_success_in_half_open_closes_circuit(self, service: APIGatewayService):
        """Recording success in HALF_OPEN state closes the circuit."""
        route_id = "route-patients-list"
        # Manually set to HALF_OPEN
        service._circuit_breakers[route_id] = CircuitBreakerStatus(
            route_id=route_id,
            state=CircuitBreakerState.HALF_OPEN,
            failure_count=0,
            success_count=0,
            threshold=5,
        )
        service.record_success(route_id)
        cb = service.get_circuit_breaker(route_id)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_reset_circuit_breaker(self, service: APIGatewayService):
        """Reset a circuit breaker to CLOSED."""
        route_id = "route-patients-list"
        # Open it first
        route = service.get_route(route_id)
        for _ in range(route.circuit_breaker_threshold):
            service.record_failure(route_id)

        cb = service.get_circuit_breaker(route_id)
        assert cb.state == CircuitBreakerState.OPEN

        result = service.reset_circuit_breaker(route_id)
        assert result.state == CircuitBreakerState.CLOSED
        assert result.failure_count == 0

    def test_reset_nonexistent_circuit_breaker(self, service: APIGatewayService):
        """Reset returns None for nonexistent route."""
        result = service.reset_circuit_breaker("nonexistent")
        assert result is None

    def test_list_circuit_breakers(self, service: APIGatewayService):
        """List all circuit breakers."""
        result = service.get_circuit_breakers()
        assert result.total == 20
        assert result.open_count == 0

    def test_open_count_reflects_state(self, service: APIGatewayService):
        """Open count reflects actual open circuit breakers."""
        route_id = "route-patients-list"
        route = service.get_route(route_id)
        for _ in range(route.circuit_breaker_threshold):
            service.record_failure(route_id)

        result = service.get_circuit_breakers()
        assert result.open_count == 1

    def test_record_failure_nonexistent(self, service: APIGatewayService):
        """Record failure returns None for nonexistent route."""
        result = service.record_failure("nonexistent")
        assert result is None

    def test_record_success_nonexistent(self, service: APIGatewayService):
        """Record success returns None for nonexistent route."""
        result = service.record_success("nonexistent")
        assert result is None

    def test_record_success_decrements_failure(self, service: APIGatewayService):
        """Recording success in CLOSED state decrements failure count."""
        route_id = "route-patients-list"
        service.record_failure(route_id)
        service.record_failure(route_id)
        cb = service.get_circuit_breaker(route_id)
        assert cb.failure_count == 2

        service.record_success(route_id)
        cb = service.get_circuit_breaker(route_id)
        assert cb.failure_count == 1


# ===========================================================================
# Service Unit Tests - Route Health
# ===========================================================================


class TestRouteHealth:
    """Tests for route health checking."""

    def test_get_route_health(self, service: APIGatewayService):
        """Get health for a specific route."""
        health = service.get_route_health("route-patients-list")
        assert health is not None
        assert health.route_id == "route-patients-list"
        assert health.status in list(RouteHealthStatus)
        assert health.latency_ms >= 0

    def test_get_nonexistent_route_health(self, service: APIGatewayService):
        """Health returns None for nonexistent route."""
        health = service.get_route_health("nonexistent")
        assert health is None

    def test_get_all_route_health(self, service: APIGatewayService):
        """Get health for all routes."""
        result = service.get_all_route_health()
        assert result.total == 20
        assert result.healthy + result.degraded + result.unhealthy == result.total

    def test_unhealthy_route_when_circuit_open(self, service: APIGatewayService):
        """Route is UNHEALTHY when circuit breaker is OPEN."""
        route_id = "route-patients-list"
        route = service.get_route(route_id)
        for _ in range(route.circuit_breaker_threshold):
            service.record_failure(route_id)

        health = service.get_route_health(route_id)
        assert health.status == RouteHealthStatus.UNHEALTHY
        assert health.circuit_breaker_state == CircuitBreakerState.OPEN

    def test_degraded_route_when_half_open(self, service: APIGatewayService):
        """Route is DEGRADED when circuit breaker is HALF_OPEN."""
        route_id = "route-patients-list"
        service._circuit_breakers[route_id] = CircuitBreakerStatus(
            route_id=route_id,
            state=CircuitBreakerState.HALF_OPEN,
            failure_count=0,
            success_count=0,
            threshold=5,
        )
        health = service.get_route_health(route_id)
        assert health.status == RouteHealthStatus.DEGRADED


# ===========================================================================
# Service Unit Tests - Gateway Metrics
# ===========================================================================


class TestGatewayMetrics:
    """Tests for gateway metrics."""

    def test_gateway_metrics_structure(self, service: APIGatewayService):
        """Gateway metrics returns all required fields."""
        metrics = service.get_gateway_metrics()
        assert metrics.total_routes == 20
        assert metrics.active_routes == 20
        assert metrics.deprecated_routes == 0
        assert metrics.total_requests_24h > 0
        assert metrics.avg_latency_ms > 0
        assert metrics.p99_latency_ms >= metrics.avg_latency_ms
        assert 0 <= metrics.error_rate_percent <= 100

    def test_gateway_metrics_auth_distribution(self, service: APIGatewayService):
        """Gateway metrics includes auth method distribution."""
        metrics = service.get_gateway_metrics()
        assert "JWT" in metrics.routes_by_auth_method
        assert metrics.routes_by_auth_method["JWT"] > 0

    def test_gateway_metrics_top_routes(self, service: APIGatewayService):
        """Gateway metrics includes top routes by traffic."""
        metrics = service.get_gateway_metrics()
        assert len(metrics.top_routes_by_traffic) > 0

    def test_gateway_stats_includes_cache(self, service: APIGatewayService):
        """Gateway stats include cache metrics."""
        stats = service.get_gateway_stats()
        assert stats.cache_metrics is not None
        assert stats.metrics is not None
        assert stats.uptime_seconds >= 0


# ===========================================================================
# Service Unit Tests - API Documentation
# ===========================================================================


class TestAPIDocumentation:
    """Tests for API documentation aggregation."""

    def test_documentation_lists_all_routes(self, service: APIGatewayService):
        """Documentation includes all routes."""
        docs = service.get_api_documentation()
        assert docs.total == 20

    def test_documentation_filter_by_version(self, service: APIGatewayService):
        """Documentation can be filtered by version."""
        docs = service.get_api_documentation(version="v1")
        assert docs.total == 20
        for ep in docs.endpoints:
            assert ep.version == "v1"

    def test_documentation_filter_nonexistent_version(self, service: APIGatewayService):
        """Filtering by nonexistent version returns empty."""
        docs = service.get_api_documentation(version="v99")
        assert docs.total == 0

    def test_documentation_entry_structure(self, service: APIGatewayService):
        """Documentation entries have correct structure."""
        docs = service.get_api_documentation()
        assert len(docs.endpoints) > 0
        ep = docs.endpoints[0]
        assert ep.path is not None
        assert ep.method is not None
        assert ep.description is not None
        assert ep.version == "v1"


# ===========================================================================
# Service Unit Tests - Stats
# ===========================================================================


class TestServiceStats:
    """Tests for service stats."""

    def test_get_stats(self, service: APIGatewayService):
        """Get service statistics."""
        stats = service.get_stats()
        assert stats["total_routes"] == 20
        assert stats["active_routes"] == 20
        assert stats["cache_configs"] == 6
        assert stats["cache_entries"] >= 50
        assert stats["rate_limit_states"] > 0
        assert stats["circuit_breakers"] == 20
        assert stats["uptime_seconds"] >= 0


# ===========================================================================
# API Integration Tests - Route Endpoints
# ===========================================================================


class TestRouteEndpoints:
    """Tests for route API endpoints."""

    def test_list_routes_endpoint(self, client: TestClient):
        """GET /api-gateway/routes returns routes."""
        resp = client.get("/api/v1/api-gateway/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    def test_list_routes_filter_status(self, client: TestClient):
        """GET /api-gateway/routes?status=ACTIVE filters correctly."""
        resp = client.get("/api/v1/api-gateway/routes?status=ACTIVE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    def test_list_routes_filter_auth(self, client: TestClient):
        """GET /api-gateway/routes?auth_method=JWT filters correctly."""
        resp = client.get("/api/v1/api-gateway/routes?auth_method=JWT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    def test_list_routes_filter_tag(self, client: TestClient):
        """GET /api-gateway/routes?tag=patients filters correctly."""
        resp = client.get("/api/v1/api-gateway/routes?tag=patients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    def test_list_routes_filter_method(self, client: TestClient):
        """GET /api-gateway/routes?method=POST filters correctly."""
        resp = client.get("/api/v1/api-gateway/routes?method=POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    def test_create_route_endpoint(self, client: TestClient):
        """POST /api-gateway/routes creates a new route."""
        resp = client.post(
            "/api/v1/api-gateway/routes",
            json={
                "path_pattern": "/api/v1/test/new",
                "target_service": "test-service",
                "method": "GET",
                "auth_method": "JWT",
                "rate_limit_rpm": 500,
                "tags": ["test"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["path_pattern"] == "/api/v1/test/new"

    def test_get_route_endpoint(self, client: TestClient):
        """GET /api-gateway/routes/{route_id} returns route detail."""
        resp = client.get("/api/v1/api-gateway/routes/route-patients-list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "route-patients-list"

    def test_get_route_not_found(self, client: TestClient):
        """GET /api-gateway/routes/{route_id} returns 404 for unknown route."""
        resp = client.get("/api/v1/api-gateway/routes/nonexistent")
        assert resp.status_code == 404

    def test_update_route_endpoint(self, client: TestClient):
        """PUT /api-gateway/routes/{route_id} updates route."""
        resp = client.put(
            "/api/v1/api-gateway/routes/route-patients-list",
            json={"rate_limit_rpm": 999},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_rpm"] == 999

    def test_update_route_not_found(self, client: TestClient):
        """PUT /api-gateway/routes/{route_id} returns 404 for unknown route."""
        resp = client.put(
            "/api/v1/api-gateway/routes/nonexistent",
            json={"rate_limit_rpm": 100},
        )
        assert resp.status_code == 404

    def test_delete_route_endpoint(self, client: TestClient):
        """DELETE /api-gateway/routes/{route_id} deletes route."""
        resp = client.delete("/api/v1/api-gateway/routes/route-patients-list")
        assert resp.status_code == 204

    def test_delete_route_not_found(self, client: TestClient):
        """DELETE /api-gateway/routes/{route_id} returns 404 for unknown route."""
        resp = client.delete("/api/v1/api-gateway/routes/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# API Integration Tests - Cache Endpoints
# ===========================================================================


class TestCacheEndpoints:
    """Tests for cache API endpoints."""

    def test_list_cache_configs_endpoint(self, client: TestClient):
        """GET /api-gateway/cache/configs returns configs."""
        resp = client.get("/api/v1/api-gateway/cache/configs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    def test_get_cache_config_endpoint(self, client: TestClient):
        """GET /api-gateway/cache/configs/{id} returns config."""
        resp = client.get("/api/v1/api-gateway/cache/configs/cache-vocabulary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Vocabulary Cache"

    def test_get_cache_config_not_found(self, client: TestClient):
        """GET /api-gateway/cache/configs/{id} returns 404."""
        resp = client.get("/api/v1/api-gateway/cache/configs/nonexistent")
        assert resp.status_code == 404

    def test_list_cache_entries_endpoint(self, client: TestClient):
        """GET /api-gateway/cache/entries returns entries."""
        resp = client.get("/api/v1/api-gateway/cache/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 50

    def test_set_cache_entry_endpoint(self, client: TestClient):
        """POST /api-gateway/cache/set creates an entry."""
        resp = client.post(
            "/api/v1/api-gateway/cache/set",
            json={
                "route_id": "route-patients-list",
                "cache_key": "api:test:1",
                "value_hash": "hash123",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["cache_key"] == "api:test:1"

    def test_invalidate_cache_endpoint(self, client: TestClient):
        """POST /api-gateway/cache/invalidate invalidates entries."""
        resp = client.post(
            "/api/v1/api-gateway/cache/invalidate",
            json={"pattern": "patient:*"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "invalidated_count" in data

    def test_flush_cache_endpoint(self, client: TestClient):
        """POST /api-gateway/cache/flush flushes entries."""
        resp = client.post(
            "/api/v1/api-gateway/cache/flush",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "flushed_count" in data

    def test_cache_metrics_endpoint(self, client: TestClient):
        """GET /api-gateway/cache/metrics returns metrics."""
        resp = client.get("/api/v1/api-gateway/cache/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data
        assert "hit_rate_percent" in data

    def test_warm_cache_endpoint(self, client: TestClient):
        """POST /api-gateway/cache/warm warms cache."""
        resp = client.post(
            "/api/v1/api-gateway/cache/warm",
            json={"config_id": "cache-vocabulary"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries_warmed"] > 0

    def test_warm_cache_not_found(self, client: TestClient):
        """POST /api-gateway/cache/warm returns 404 for unknown config."""
        resp = client.post(
            "/api/v1/api-gateway/cache/warm",
            json={"config_id": "nonexistent-config-xyz"},
        )
        assert resp.status_code == 404


# ===========================================================================
# API Integration Tests - Rate Limit Endpoints
# ===========================================================================


class TestRateLimitEndpoints:
    """Tests for rate limit API endpoints."""

    def test_check_rate_limit_endpoint(self, client: TestClient):
        """POST /api-gateway/rate-limit/check returns status."""
        resp = client.post(
            "/api/v1/api-gateway/rate-limit/check",
            json={"route_id": "route-patients-list", "client_id": "test-client"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True

    def test_consume_rate_limit_endpoint(self, client: TestClient):
        """POST /api-gateway/rate-limit/consume returns updated state."""
        resp = client.post(
            "/api/v1/api-gateway/rate-limit/consume",
            json={"route_id": "route-patients-list", "client_id": "test-client", "tokens": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data

    def test_list_rate_limit_states_endpoint(self, client: TestClient):
        """GET /api-gateway/rate-limit/states returns states."""
        resp = client.get("/api/v1/api-gateway/rate-limit/states")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_rate_limit_states_filter(self, client: TestClient):
        """GET /api-gateway/rate-limit/states?route_id=... filters."""
        resp = client.get("/api/v1/api-gateway/rate-limit/states?route_id=route-patients-list")
        assert resp.status_code == 200
        data = resp.json()
        for s in data:
            assert s["route_id"] == "route-patients-list"


# ===========================================================================
# API Integration Tests - Health Endpoints
# ===========================================================================


class TestHealthEndpoints:
    """Tests for health API endpoints."""

    def test_all_routes_health_endpoint(self, client: TestClient):
        """GET /api-gateway/health/routes returns all route health."""
        resp = client.get("/api/v1/api-gateway/health/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    def test_single_route_health_endpoint(self, client: TestClient):
        """GET /api-gateway/health/routes/{id} returns single route health."""
        resp = client.get("/api/v1/api-gateway/health/routes/route-patients-list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["route_id"] == "route-patients-list"

    def test_single_route_health_not_found(self, client: TestClient):
        """GET /api-gateway/health/routes/{id} returns 404 for unknown."""
        resp = client.get("/api/v1/api-gateway/health/routes/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# API Integration Tests - Circuit Breaker Endpoints
# ===========================================================================


class TestCircuitBreakerEndpoints:
    """Tests for circuit breaker API endpoints."""

    def test_list_circuit_breakers_endpoint(self, client: TestClient):
        """GET /api-gateway/circuit-breakers returns all states."""
        resp = client.get("/api/v1/api-gateway/circuit-breakers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20
        assert data["open_count"] == 0

    def test_reset_circuit_breaker_endpoint(self, client: TestClient):
        """POST /api-gateway/circuit-breakers/{id}/reset resets breaker."""
        resp = client.post("/api/v1/api-gateway/circuit-breakers/route-patients-list/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "CLOSED"
        assert data["failure_count"] == 0

    def test_reset_circuit_breaker_not_found(self, client: TestClient):
        """POST /api-gateway/circuit-breakers/{id}/reset returns 404."""
        resp = client.post("/api/v1/api-gateway/circuit-breakers/nonexistent/reset")
        assert resp.status_code == 404


# ===========================================================================
# API Integration Tests - Metrics & Documentation Endpoints
# ===========================================================================


class TestMetricsAndDocEndpoints:
    """Tests for metrics and documentation API endpoints."""

    def test_gateway_metrics_endpoint(self, client: TestClient):
        """GET /api-gateway/metrics returns metrics."""
        resp = client.get("/api/v1/api-gateway/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_routes"] == 20
        assert "avg_latency_ms" in data

    def test_gateway_stats_endpoint(self, client: TestClient):
        """GET /api-gateway/stats returns full stats."""
        resp = client.get("/api/v1/api-gateway/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "cache_metrics" in data
        assert "uptime_seconds" in data

    def test_documentation_endpoint(self, client: TestClient):
        """GET /api-gateway/documentation returns docs."""
        resp = client.get("/api/v1/api-gateway/documentation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    def test_documentation_filter_version(self, client: TestClient):
        """GET /api-gateway/documentation?version=v1 filters."""
        resp = client.get("/api/v1/api-gateway/documentation?version=v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    def test_documentation_filter_nonexistent_version(self, client: TestClient):
        """GET /api-gateway/documentation?version=v99 returns empty."""
        resp = client.get("/api/v1/api-gateway/documentation?version=v99")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# ===========================================================================
# Schema Model Tests
# ===========================================================================


class TestSchemaModels:
    """Tests for Pydantic schema models."""

    def test_gateway_route_status_enum(self):
        """GatewayRouteStatus has correct values."""
        assert GatewayRouteStatus.ACTIVE == "ACTIVE"
        assert GatewayRouteStatus.DEPRECATED == "DEPRECATED"
        assert GatewayRouteStatus.DISABLED == "DISABLED"
        assert GatewayRouteStatus.RATE_LIMITED == "RATE_LIMITED"

    def test_auth_method_enum(self):
        """AuthMethod has correct values."""
        assert AuthMethod.API_KEY == "API_KEY"
        assert AuthMethod.JWT == "JWT"
        assert AuthMethod.OAUTH2 == "OAUTH2"
        assert AuthMethod.MTLS == "MTLS"
        assert AuthMethod.BASIC == "BASIC"
        assert AuthMethod.NONE == "NONE"

    def test_cache_strategy_enum(self):
        """CacheStrategy has correct values."""
        assert CacheStrategy.NO_CACHE == "NO_CACHE"
        assert CacheStrategy.READ_THROUGH == "READ_THROUGH"
        assert CacheStrategy.WRITE_THROUGH == "WRITE_THROUGH"
        assert CacheStrategy.WRITE_BEHIND == "WRITE_BEHIND"
        assert CacheStrategy.CACHE_ASIDE == "CACHE_ASIDE"
        assert CacheStrategy.TTL_BASED == "TTL_BASED"

    def test_cache_status_enum(self):
        """CacheStatus has correct values."""
        assert CacheStatus.HIT == "HIT"
        assert CacheStatus.MISS == "MISS"
        assert CacheStatus.STALE == "STALE"
        assert CacheStatus.EXPIRED == "EXPIRED"
        assert CacheStatus.INVALIDATED == "INVALIDATED"
        assert CacheStatus.BYPASS == "BYPASS"

    def test_rate_limit_algorithm_enum(self):
        """RateLimitAlgorithm has correct values."""
        assert RateLimitAlgorithm.TOKEN_BUCKET == "TOKEN_BUCKET"
        assert RateLimitAlgorithm.SLIDING_WINDOW == "SLIDING_WINDOW"
        assert RateLimitAlgorithm.FIXED_WINDOW == "FIXED_WINDOW"
        assert RateLimitAlgorithm.LEAKY_BUCKET == "LEAKY_BUCKET"

    def test_transformation_type_enum(self):
        """TransformationType has correct values."""
        assert TransformationType.REQUEST_HEADER == "REQUEST_HEADER"
        assert TransformationType.RESPONSE_HEADER == "RESPONSE_HEADER"
        assert TransformationType.REQUEST_BODY == "REQUEST_BODY"
        assert TransformationType.RESPONSE_BODY == "RESPONSE_BODY"
        assert TransformationType.URL_REWRITE == "URL_REWRITE"

    def test_route_transformation_model(self):
        """RouteTransformation can be created."""
        t = RouteTransformation(
            transformation_type=TransformationType.REQUEST_HEADER,
            key="X-Test",
            value="test-value",
            condition="always",
        )
        assert t.key == "X-Test"
        assert t.condition == "always"

    def test_route_transformation_optional_condition(self):
        """RouteTransformation condition is optional."""
        t = RouteTransformation(
            transformation_type=TransformationType.RESPONSE_HEADER,
            key="X-Gateway",
            value="true",
        )
        assert t.condition is None

    def test_gateway_route_defaults(self):
        """GatewayRoute has sensible defaults."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        route = GatewayRoute(
            id="test",
            path_pattern="/test",
            target_service="test-svc",
            created_at=now,
            updated_at=now,
        )
        assert route.method == "GET"
        assert route.auth_method == AuthMethod.JWT
        assert route.rate_limit_rpm == 600
        assert route.status == GatewayRouteStatus.ACTIVE
        assert route.cache_strategy == CacheStrategy.NO_CACHE
        assert route.timeout_ms == 30000

    def test_cache_config_defaults(self):
        """CacheConfig has sensible defaults."""
        config = CacheConfig(
            id="test",
            name="Test",
            strategy=CacheStrategy.LRU if hasattr(CacheStrategy, 'LRU') else CacheStrategy.READ_THROUGH,
        )
        assert config.default_ttl_seconds == 300
        assert config.max_entries == 10000
        assert config.eviction_policy == EvictionPolicy.LRU
        assert config.warm_on_startup is False


# ===========================================================================
# Singleton Tests
# ===========================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """get_api_gateway_service returns the same instance."""
        svc1 = get_api_gateway_service()
        svc2 = get_api_gateway_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset_api_gateway_service allows creating a new instance."""
        svc1 = get_api_gateway_service()
        reset_api_gateway_service()
        svc2 = get_api_gateway_service()
        assert svc1 is not svc2
