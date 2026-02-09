"""API Gateway & Caching Strategy service (CTO-10).

Manages gateway route configuration, caching strategies, rate limiting,
circuit breaker patterns, and gateway-level observability.

Usage:
    from app.services.api_gateway_service import get_api_gateway_service

    service = get_api_gateway_service()
    routes = service.list_routes()
    metrics = service.get_gateway_metrics()
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.api_gateway import (
    APIDocumentationEntry,
    APIDocumentationResponse,
    AuthMethod,
    CacheConfig,
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

logger = logging.getLogger(__name__)

# Singleton instance and lock
_api_gateway_instance: APIGatewayService | None = None
_api_gateway_lock = Lock()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class APIGatewayService:
    """In-memory API Gateway & Caching service.

    Provides route management, cache management, rate limiting,
    circuit breaker state, health checking, and observability.
    """

    def __init__(self) -> None:
        self._routes: dict[str, GatewayRoute] = {}
        self._cache_configs: dict[str, CacheConfig] = {}
        self._cache_entries: dict[str, CacheEntry] = {}
        self._rate_limit_states: dict[str, RateLimitState] = {}
        self._circuit_breakers: dict[str, CircuitBreakerStatus] = {}
        self._start_time = time.time()
        self._total_requests = 0
        self._request_latencies: list[float] = []
        self._error_count = 0

        self._seed_data()
        logger.info(
            "APIGatewayService initialized with %d routes, %d cache configs",
            len(self._routes),
            len(self._cache_configs),
        )

    # -----------------------------------------------------------------------
    # Seed Data
    # -----------------------------------------------------------------------

    def _seed_data(self) -> None:
        """Seed the gateway with realistic clinical trial platform data."""
        now = datetime.now(timezone.utc)
        base_time = now - timedelta(days=90)

        # --- 20 Gateway Routes ---
        routes_data = [
            {
                "id": "route-patients-list",
                "path_pattern": "/api/v1/patients",
                "target_service": "patient-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 600,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 300,
                "tags": ["patients", "core"],
                "description": "List and search patients",
            },
            {
                "id": "route-patients-detail",
                "path_pattern": "/api/v1/patients/{patient_id}",
                "target_service": "patient-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 1200,
                "cache_strategy": CacheStrategy.CACHE_ASIDE,
                "cache_ttl_seconds": 120,
                "tags": ["patients", "core"],
                "description": "Get patient detail by ID",
            },
            {
                "id": "route-patients-create",
                "path_pattern": "/api/v1/patients",
                "target_service": "patient-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 120,
                "cache_strategy": CacheStrategy.NO_CACHE,
                "cache_ttl_seconds": 0,
                "tags": ["patients", "core", "write"],
                "description": "Create a new patient record",
            },
            {
                "id": "route-trials-list",
                "path_pattern": "/api/v1/trials",
                "target_service": "trial-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 300,
                "cache_strategy": CacheStrategy.TTL_BASED,
                "cache_ttl_seconds": 600,
                "tags": ["trials", "core"],
                "description": "List clinical trials",
            },
            {
                "id": "route-trials-detail",
                "path_pattern": "/api/v1/trials/{trial_id}",
                "target_service": "trial-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 600,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 300,
                "tags": ["trials", "core"],
                "description": "Get trial details",
            },
            {
                "id": "route-screening-run",
                "path_pattern": "/api/v1/screening/run",
                "target_service": "screening-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 60,
                "rate_limit_algorithm": RateLimitAlgorithm.SLIDING_WINDOW,
                "cache_strategy": CacheStrategy.CACHE_ASIDE,
                "cache_ttl_seconds": 300,
                "timeout_ms": 60000,
                "tags": ["screening", "compute"],
                "description": "Run patient screening against trial criteria",
            },
            {
                "id": "route-screening-results",
                "path_pattern": "/api/v1/screening/results",
                "target_service": "screening-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 300,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 300,
                "tags": ["screening", "core"],
                "description": "List screening results",
            },
            {
                "id": "route-fhir-patient",
                "path_pattern": "/api/v1/fhir/Patient",
                "target_service": "fhir-service",
                "method": "GET",
                "auth_method": AuthMethod.OAUTH2,
                "rate_limit_rpm": 300,
                "cache_strategy": CacheStrategy.TTL_BASED,
                "cache_ttl_seconds": 3600,
                "tags": ["fhir", "interop"],
                "description": "FHIR Patient resource endpoint",
            },
            {
                "id": "route-fhir-condition",
                "path_pattern": "/api/v1/fhir/Condition",
                "target_service": "fhir-service",
                "method": "GET",
                "auth_method": AuthMethod.OAUTH2,
                "rate_limit_rpm": 300,
                "cache_strategy": CacheStrategy.TTL_BASED,
                "cache_ttl_seconds": 3600,
                "tags": ["fhir", "interop"],
                "description": "FHIR Condition resource endpoint",
            },
            {
                "id": "route-fhir-observation",
                "path_pattern": "/api/v1/fhir/Observation",
                "target_service": "fhir-service",
                "method": "GET",
                "auth_method": AuthMethod.OAUTH2,
                "rate_limit_rpm": 600,
                "cache_strategy": CacheStrategy.TTL_BASED,
                "cache_ttl_seconds": 1800,
                "tags": ["fhir", "interop"],
                "description": "FHIR Observation resource endpoint",
            },
            {
                "id": "route-documents-ingest",
                "path_pattern": "/api/v1/documents/ingest",
                "target_service": "document-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 30,
                "rate_limit_algorithm": RateLimitAlgorithm.LEAKY_BUCKET,
                "cache_strategy": CacheStrategy.NO_CACHE,
                "cache_ttl_seconds": 0,
                "timeout_ms": 120000,
                "retry_count": 1,
                "tags": ["documents", "ingest", "write"],
                "description": "Ingest clinical documents",
            },
            {
                "id": "route-documents-list",
                "path_pattern": "/api/v1/documents",
                "target_service": "document-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 600,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 180,
                "tags": ["documents", "core"],
                "description": "List clinical documents",
            },
            {
                "id": "route-nlp-extract",
                "path_pattern": "/api/v1/nlp/extract",
                "target_service": "nlp-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 60,
                "rate_limit_algorithm": RateLimitAlgorithm.SLIDING_WINDOW,
                "cache_strategy": CacheStrategy.CACHE_ASIDE,
                "cache_ttl_seconds": 1800,
                "timeout_ms": 90000,
                "tags": ["nlp", "compute"],
                "description": "Extract clinical entities via NLP",
            },
            {
                "id": "route-nlp-mentions",
                "path_pattern": "/api/v1/nlp/mentions",
                "target_service": "nlp-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 300,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 900,
                "tags": ["nlp", "core"],
                "description": "List NLP-extracted mentions",
            },
            {
                "id": "route-graph-query",
                "path_pattern": "/api/v1/graph/query",
                "target_service": "graph-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 120,
                "cache_strategy": CacheStrategy.CACHE_ASIDE,
                "cache_ttl_seconds": 900,
                "timeout_ms": 45000,
                "tags": ["graph", "compute"],
                "description": "Query knowledge graph",
            },
            {
                "id": "route-graph-nodes",
                "path_pattern": "/api/v1/graph/nodes",
                "target_service": "graph-service",
                "method": "GET",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 300,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 600,
                "tags": ["graph", "core"],
                "description": "List knowledge graph nodes",
            },
            {
                "id": "route-export-omop",
                "path_pattern": "/api/v1/export/omop",
                "target_service": "export-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 10,
                "rate_limit_algorithm": RateLimitAlgorithm.FIXED_WINDOW,
                "cache_strategy": CacheStrategy.NO_CACHE,
                "cache_ttl_seconds": 0,
                "timeout_ms": 300000,
                "retry_count": 1,
                "tags": ["export", "bulk"],
                "description": "Export data in OMOP CDM format",
            },
            {
                "id": "route-export-fhir",
                "path_pattern": "/api/v1/export/fhir",
                "target_service": "export-service",
                "method": "POST",
                "auth_method": AuthMethod.JWT,
                "rate_limit_rpm": 10,
                "rate_limit_algorithm": RateLimitAlgorithm.FIXED_WINDOW,
                "cache_strategy": CacheStrategy.NO_CACHE,
                "cache_ttl_seconds": 0,
                "timeout_ms": 300000,
                "retry_count": 1,
                "tags": ["export", "bulk"],
                "description": "Export data in FHIR bundle format",
            },
            {
                "id": "route-vocabulary-lookup",
                "path_pattern": "/api/v1/vocabulary/lookup",
                "target_service": "vocabulary-service",
                "method": "GET",
                "auth_method": AuthMethod.API_KEY,
                "rate_limit_rpm": 1200,
                "cache_strategy": CacheStrategy.READ_THROUGH,
                "cache_ttl_seconds": 86400,
                "tags": ["vocabulary", "reference"],
                "description": "Look up OMOP vocabulary concepts",
            },
            {
                "id": "route-health-check",
                "path_pattern": "/api/v1/health",
                "target_service": "health-service",
                "method": "GET",
                "auth_method": AuthMethod.NONE,
                "rate_limit_rpm": 3600,
                "cache_strategy": CacheStrategy.TTL_BASED,
                "cache_ttl_seconds": 10,
                "tags": ["health", "monitoring"],
                "description": "System health check endpoint",
            },
        ]

        for i, rd in enumerate(routes_data):
            route_id = rd["id"]
            route = GatewayRoute(
                id=route_id,
                path_pattern=rd["path_pattern"],
                target_service=rd["target_service"],
                method=rd.get("method", "GET"),
                auth_method=rd.get("auth_method", AuthMethod.JWT),
                rate_limit_rpm=rd.get("rate_limit_rpm", 600),
                rate_limit_algorithm=rd.get("rate_limit_algorithm", RateLimitAlgorithm.TOKEN_BUCKET),
                status=GatewayRouteStatus.ACTIVE,
                cache_strategy=rd.get("cache_strategy", CacheStrategy.NO_CACHE),
                cache_ttl_seconds=rd.get("cache_ttl_seconds", 0),
                timeout_ms=rd.get("timeout_ms", 30000),
                retry_count=rd.get("retry_count", 3),
                retry_delay_ms=rd.get("retry_delay_ms", 1000),
                circuit_breaker_threshold=rd.get("circuit_breaker_threshold", 5),
                circuit_breaker_timeout_seconds=rd.get("circuit_breaker_timeout_seconds", 60),
                transformations=[
                    RouteTransformation(
                        transformation_type=TransformationType.RESPONSE_HEADER,
                        key="X-Gateway-Route",
                        value=route_id,
                    ),
                    RouteTransformation(
                        transformation_type=TransformationType.REQUEST_HEADER,
                        key="X-Request-ID",
                        value="${uuid}",
                    ),
                ],
                tags=rd.get("tags", []),
                created_at=base_time + timedelta(days=i),
                updated_at=now - timedelta(hours=random.randint(1, 72)),
                version="v1",
            )
            self._routes[route_id] = route

            # Initialize circuit breaker for each route
            self._circuit_breakers[route_id] = CircuitBreakerStatus(
                route_id=route_id,
                state=CircuitBreakerState.CLOSED,
                failure_count=0,
                success_count=0,
                threshold=route.circuit_breaker_threshold,
            )

        # --- 6 Cache Configs ---
        cache_configs_data = [
            {
                "id": "cache-vocabulary",
                "name": "Vocabulary Cache",
                "strategy": CacheStrategy.READ_THROUGH,
                "default_ttl_seconds": 86400,
                "max_entries": 50000,
                "max_size_mb": 1024.0,
                "eviction_policy": EvictionPolicy.LFU,
                "warm_on_startup": True,
                "invalidation_patterns": ["/api/v1/vocabulary/*"],
            },
            {
                "id": "cache-trial-eligibility",
                "name": "Trial Eligibility Cache",
                "strategy": CacheStrategy.CACHE_ASIDE,
                "default_ttl_seconds": 300,
                "max_entries": 10000,
                "max_size_mb": 256.0,
                "eviction_policy": EvictionPolicy.LRU,
                "warm_on_startup": False,
                "invalidation_patterns": ["/api/v1/screening/*", "/api/v1/trials/*/criteria"],
            },
            {
                "id": "cache-fhir-resource",
                "name": "FHIR Resource Cache",
                "strategy": CacheStrategy.TTL_BASED,
                "default_ttl_seconds": 3600,
                "max_entries": 25000,
                "max_size_mb": 512.0,
                "eviction_policy": EvictionPolicy.LRU,
                "warm_on_startup": False,
                "invalidation_patterns": ["/api/v1/fhir/*"],
            },
            {
                "id": "cache-nlp-results",
                "name": "NLP Results Cache",
                "strategy": CacheStrategy.CACHE_ASIDE,
                "default_ttl_seconds": 1800,
                "max_entries": 5000,
                "max_size_mb": 256.0,
                "eviction_policy": EvictionPolicy.LRU,
                "warm_on_startup": False,
                "invalidation_patterns": ["/api/v1/nlp/*"],
            },
            {
                "id": "cache-graph-queries",
                "name": "Graph Query Cache",
                "strategy": CacheStrategy.CACHE_ASIDE,
                "default_ttl_seconds": 900,
                "max_entries": 3000,
                "max_size_mb": 128.0,
                "eviction_policy": EvictionPolicy.LFU,
                "warm_on_startup": False,
                "invalidation_patterns": ["/api/v1/graph/*"],
            },
            {
                "id": "cache-static-assets",
                "name": "Static Assets Cache",
                "strategy": CacheStrategy.READ_THROUGH,
                "default_ttl_seconds": 604800,
                "max_entries": 1000,
                "max_size_mb": 2048.0,
                "eviction_policy": EvictionPolicy.FIFO,
                "warm_on_startup": True,
                "invalidation_patterns": ["/static/*", "/assets/*"],
            },
        ]

        for cd in cache_configs_data:
            config = CacheConfig(
                id=cd["id"],
                name=cd["name"],
                strategy=cd["strategy"],
                default_ttl_seconds=cd["default_ttl_seconds"],
                max_entries=cd["max_entries"],
                max_size_mb=cd["max_size_mb"],
                eviction_policy=cd["eviction_policy"],
                warm_on_startup=cd["warm_on_startup"],
                invalidation_patterns=cd["invalidation_patterns"],
            )
            self._cache_configs[cd["id"]] = config

        # --- 50+ Cache Entries ---
        route_ids = list(self._routes.keys())
        sample_keys = [
            "patient:list:page=1",
            "patient:detail:P001",
            "patient:detail:P002",
            "patient:detail:P003",
            "patient:detail:P004",
            "patient:detail:P005",
            "trial:list:status=active",
            "trial:detail:T001",
            "trial:detail:T002",
            "trial:detail:T003",
            "trial:criteria:T001",
            "screening:result:S001",
            "screening:result:S002",
            "screening:result:S003",
            "fhir:Patient:P001",
            "fhir:Patient:P002",
            "fhir:Patient:P003",
            "fhir:Condition:C001",
            "fhir:Condition:C002",
            "fhir:Observation:O001",
            "fhir:Observation:O002",
            "fhir:Observation:O003",
            "fhir:Observation:O004",
            "doc:list:page=1",
            "doc:detail:D001",
            "doc:detail:D002",
            "nlp:mentions:D001",
            "nlp:mentions:D002",
            "nlp:extract:hash_abc123",
            "nlp:extract:hash_def456",
            "graph:nodes:type=Patient",
            "graph:nodes:type=Condition",
            "graph:nodes:type=Drug",
            "graph:query:q1_hash",
            "graph:query:q2_hash",
            "graph:query:q3_hash",
            "vocab:lookup:SNOMED:38341003",
            "vocab:lookup:SNOMED:73211009",
            "vocab:lookup:ICD10:E11",
            "vocab:lookup:ICD10:I10",
            "vocab:lookup:RxNorm:1049221",
            "vocab:lookup:RxNorm:866924",
            "vocab:lookup:LOINC:2160-0",
            "vocab:lookup:LOINC:1742-6",
            "health:status",
            "trial:list:page=2",
            "patient:list:page=2",
            "screening:result:S004",
            "fhir:Patient:P004",
            "fhir:Condition:C003",
            "graph:query:q4_hash",
            "vocab:lookup:SNOMED:44054006",
            "nlp:extract:hash_ghi789",
        ]

        for i, key in enumerate(sample_keys):
            route_id = route_ids[i % len(route_ids)]
            ttl = self._routes[route_id].cache_ttl_seconds or 300
            entry_time = now - timedelta(minutes=random.randint(1, 120))
            expires = entry_time + timedelta(seconds=ttl)
            status = CacheStatus.HIT if expires > now else CacheStatus.EXPIRED

            entry = CacheEntry(
                id=f"ce-{i+1:04d}",
                route_id=route_id,
                cache_key=key,
                value_hash=hashlib.sha256(f"{key}:{i}".encode()).hexdigest()[:16],
                status=status,
                created_at=entry_time,
                expires_at=expires,
                last_accessed=now - timedelta(minutes=random.randint(0, 30)),
                hit_count=random.randint(1, 500),
                size_bytes=random.randint(256, 65536),
            )
            self._cache_entries[entry.id] = entry

        # --- Rate Limit States ---
        clients = ["client-webapp", "client-mobile", "client-etl", "client-fhir-proxy", "client-admin"]
        for route_id in route_ids[:10]:
            for client_id in clients[:3]:
                state_key = f"{route_id}:{client_id}"
                route = self._routes[route_id]
                remaining = random.randint(
                    int(route.rate_limit_rpm * 0.3),
                    route.rate_limit_rpm,
                )
                self._rate_limit_states[state_key] = RateLimitState(
                    route_id=route_id,
                    client_id=client_id,
                    requests_remaining=remaining,
                    limit=route.rate_limit_rpm,
                    window_seconds=60,
                    reset_at=now + timedelta(seconds=random.randint(10, 60)),
                )

        # Seed some simulated traffic metrics
        self._total_requests = random.randint(50000, 200000)
        self._request_latencies = [random.uniform(5.0, 500.0) for _ in range(1000)]
        self._error_count = random.randint(100, 2000)

    # -----------------------------------------------------------------------
    # Route CRUD
    # -----------------------------------------------------------------------

    def list_routes(
        self,
        status: GatewayRouteStatus | None = None,
        auth_method: AuthMethod | None = None,
        tag: str | None = None,
        method: str | None = None,
    ) -> GatewayRouteListResponse:
        """List all gateway routes with optional filtering."""
        routes = list(self._routes.values())

        if status is not None:
            routes = [r for r in routes if r.status == status]
        if auth_method is not None:
            routes = [r for r in routes if r.auth_method == auth_method]
        if tag is not None:
            routes = [r for r in routes if tag in r.tags]
        if method is not None:
            routes = [r for r in routes if r.method == method.upper()]

        return GatewayRouteListResponse(routes=routes, total=len(routes))

    def get_route(self, route_id: str) -> GatewayRoute | None:
        """Get a single route by ID."""
        return self._routes.get(route_id)

    def create_route(self, request: GatewayRouteCreateRequest) -> GatewayRoute:
        """Create a new gateway route."""
        now = datetime.now(timezone.utc)
        route_id = f"route-{uuid.uuid4().hex[:12]}"

        route = GatewayRoute(
            id=route_id,
            path_pattern=request.path_pattern,
            target_service=request.target_service,
            method=request.method,
            auth_method=request.auth_method,
            rate_limit_rpm=request.rate_limit_rpm,
            rate_limit_algorithm=request.rate_limit_algorithm,
            status=GatewayRouteStatus.ACTIVE,
            cache_strategy=request.cache_strategy,
            cache_ttl_seconds=request.cache_ttl_seconds,
            timeout_ms=request.timeout_ms,
            retry_count=request.retry_count,
            retry_delay_ms=request.retry_delay_ms,
            circuit_breaker_threshold=request.circuit_breaker_threshold,
            circuit_breaker_timeout_seconds=request.circuit_breaker_timeout_seconds,
            transformations=request.transformations,
            tags=request.tags,
            created_at=now,
            updated_at=now,
            version=request.version,
        )

        self._routes[route_id] = route

        # Initialize circuit breaker
        self._circuit_breakers[route_id] = CircuitBreakerStatus(
            route_id=route_id,
            state=CircuitBreakerState.CLOSED,
            failure_count=0,
            success_count=0,
            threshold=route.circuit_breaker_threshold,
        )

        logger.info("Created gateway route %s -> %s", route_id, request.path_pattern)
        return route

    def update_route(self, route_id: str, request: GatewayRouteUpdateRequest) -> GatewayRoute | None:
        """Update an existing gateway route."""
        route = self._routes.get(route_id)
        if route is None:
            return None

        now = datetime.now(timezone.utc)
        update_data = request.model_dump(exclude_none=True)
        route_data = route.model_dump()
        route_data.update(update_data)
        route_data["updated_at"] = now

        # Handle deprecation
        if update_data.get("status") == GatewayRouteStatus.DEPRECATED and route.deprecated_date is None:
            route_data["deprecated_date"] = now

        updated_route = GatewayRoute(**route_data)
        self._routes[route_id] = updated_route
        logger.info("Updated gateway route %s", route_id)
        return updated_route

    def delete_route(self, route_id: str) -> bool:
        """Delete a gateway route."""
        if route_id not in self._routes:
            return False

        del self._routes[route_id]
        self._circuit_breakers.pop(route_id, None)

        # Remove associated cache entries
        to_remove = [eid for eid, e in self._cache_entries.items() if e.route_id == route_id]
        for eid in to_remove:
            del self._cache_entries[eid]

        # Remove rate limit states
        to_remove_rl = [k for k in self._rate_limit_states if k.startswith(f"{route_id}:")]
        for k in to_remove_rl:
            del self._rate_limit_states[k]

        logger.info("Deleted gateway route %s", route_id)
        return True

    # -----------------------------------------------------------------------
    # Cache Management
    # -----------------------------------------------------------------------

    def list_cache_configs(self) -> list[CacheConfig]:
        """List all cache configurations."""
        return list(self._cache_configs.values())

    def get_cache_config(self, config_id: str) -> CacheConfig | None:
        """Get a single cache config by ID."""
        return self._cache_configs.get(config_id)

    def get_cache_entry(self, cache_key: str) -> CacheEntry | None:
        """Get a cache entry by key."""
        now = datetime.now(timezone.utc)
        for entry in self._cache_entries.values():
            if entry.cache_key == cache_key:
                if entry.expires_at < now:
                    entry_data = entry.model_dump()
                    entry_data["status"] = CacheStatus.EXPIRED
                    updated = CacheEntry(**entry_data)
                    self._cache_entries[entry.id] = updated
                    return updated
                # Update hit count and last accessed
                entry_data = entry.model_dump()
                entry_data["hit_count"] = entry.hit_count + 1
                entry_data["last_accessed"] = now
                entry_data["status"] = CacheStatus.HIT
                updated = CacheEntry(**entry_data)
                self._cache_entries[entry.id] = updated
                return updated
        return None

    def set_cache_entry(
        self,
        route_id: str,
        cache_key: str,
        value_hash: str,
        ttl_seconds: int | None = None,
        size_bytes: int = 0,
    ) -> CacheEntry:
        """Set (create or update) a cache entry."""
        now = datetime.now(timezone.utc)
        route = self._routes.get(route_id)
        ttl = ttl_seconds or (route.cache_ttl_seconds if route else 300) or 300

        # Check if exists
        existing = None
        for entry in self._cache_entries.values():
            if entry.cache_key == cache_key and entry.route_id == route_id:
                existing = entry
                break

        entry_id = existing.id if existing else f"ce-{uuid.uuid4().hex[:8]}"
        entry = CacheEntry(
            id=entry_id,
            route_id=route_id,
            cache_key=cache_key,
            value_hash=value_hash,
            status=CacheStatus.HIT,
            created_at=existing.created_at if existing else now,
            expires_at=now + timedelta(seconds=ttl),
            last_accessed=now,
            hit_count=(existing.hit_count if existing else 0),
            size_bytes=size_bytes,
        )
        self._cache_entries[entry_id] = entry
        return entry

    def invalidate_cache(self, pattern: str, route_id: str | None = None) -> int:
        """Invalidate cache entries matching a pattern.

        Returns the number of entries invalidated.
        """
        import fnmatch

        count = 0
        now = datetime.now(timezone.utc)
        for eid, entry in list(self._cache_entries.items()):
            if route_id and entry.route_id != route_id:
                continue
            if fnmatch.fnmatch(entry.cache_key, pattern):
                entry_data = entry.model_dump()
                entry_data["status"] = CacheStatus.INVALIDATED
                entry_data["expires_at"] = now
                self._cache_entries[eid] = CacheEntry(**entry_data)
                count += 1
        logger.info("Invalidated %d cache entries matching pattern '%s'", count, pattern)
        return count

    def flush_cache(self, config_id: str | None = None) -> int:
        """Flush all cache entries, optionally filtered by config.

        Returns the number of entries flushed.
        """
        if config_id is None:
            count = len(self._cache_entries)
            self._cache_entries.clear()
            logger.info("Flushed all %d cache entries", count)
            return count

        # Flush by config - match invalidation patterns
        config = self._cache_configs.get(config_id)
        if config is None:
            return 0

        import fnmatch

        count = 0
        for eid, entry in list(self._cache_entries.items()):
            for pattern in config.invalidation_patterns:
                if fnmatch.fnmatch(entry.cache_key, pattern):
                    del self._cache_entries[eid]
                    count += 1
                    break
        logger.info("Flushed %d cache entries for config %s", count, config_id)
        return count

    def get_cache_entries(
        self,
        route_id: str | None = None,
        status: CacheStatus | None = None,
    ) -> CacheEntryListResponse:
        """List cache entries with optional filtering."""
        entries = list(self._cache_entries.values())

        if route_id is not None:
            entries = [e for e in entries if e.route_id == route_id]
        if status is not None:
            entries = [e for e in entries if e.status == status]

        return CacheEntryListResponse(entries=entries, total=len(entries))

    def get_cache_metrics(self) -> CacheMetrics:
        """Calculate aggregate cache metrics."""
        entries = list(self._cache_entries.values())
        if not entries:
            return CacheMetrics()

        now = datetime.now(timezone.utc)
        total_size = sum(e.size_bytes for e in entries) / (1024 * 1024)
        hit_count = sum(e.hit_count for e in entries)
        miss_count = max(1, len(entries))  # approximate
        stale_count = sum(1 for e in entries if e.status in (CacheStatus.EXPIRED, CacheStatus.STALE, CacheStatus.INVALIDATED))
        warm_count = sum(1 for e in entries if e.status == CacheStatus.HIT and e.hit_count > 10)

        # Average TTL
        ttls = []
        for e in entries:
            ttl = (e.expires_at - e.created_at).total_seconds()
            if ttl > 0:
                ttls.append(ttl)
        avg_ttl = sum(ttls) / len(ttls) if ttls else 0.0

        total = hit_count + miss_count
        hit_rate = (hit_count / total * 100) if total > 0 else 0.0

        return CacheMetrics(
            total_entries=len(entries),
            total_size_mb=round(total_size, 2),
            hit_count=hit_count,
            miss_count=miss_count,
            hit_rate_percent=round(hit_rate, 2),
            eviction_count=random.randint(10, 200),
            avg_ttl_seconds=round(avg_ttl, 1),
            warm_entries=warm_count,
            stale_entries=stale_count,
        )

    def warm_cache(self, config_id: str) -> CacheWarmResponse:
        """Warm a cache pool by pre-loading entries.

        In production this would fetch data from the backend services.
        Here we simulate it.
        """
        start = time.time()
        config = self._cache_configs.get(config_id)
        if config is None:
            return CacheWarmResponse(
                config_id=config_id,
                entries_warmed=0,
                duration_ms=0.0,
            )

        warmed = 0
        now = datetime.now(timezone.utc)
        # Simulate warming a few entries
        for i in range(min(10, config.max_entries)):
            key = f"warm:{config.name}:{i}"
            entry = CacheEntry(
                id=f"ce-warm-{uuid.uuid4().hex[:8]}",
                route_id=list(self._routes.keys())[0] if self._routes else "unknown",
                cache_key=key,
                value_hash=hashlib.sha256(key.encode()).hexdigest()[:16],
                status=CacheStatus.HIT,
                created_at=now,
                expires_at=now + timedelta(seconds=config.default_ttl_seconds),
                last_accessed=now,
                hit_count=0,
                size_bytes=random.randint(512, 4096),
            )
            self._cache_entries[entry.id] = entry
            warmed += 1

        duration = (time.time() - start) * 1000
        return CacheWarmResponse(
            config_id=config_id,
            entries_warmed=warmed,
            duration_ms=round(duration, 2),
        )

    # -----------------------------------------------------------------------
    # Rate Limiting
    # -----------------------------------------------------------------------

    def check_rate_limit(self, route_id: str, client_id: str) -> RateLimitCheckResponse:
        """Check if a client is within rate limits for a route."""
        state_key = f"{route_id}:{client_id}"
        now = datetime.now(timezone.utc)

        state = self._rate_limit_states.get(state_key)
        if state is None:
            route = self._routes.get(route_id)
            limit = route.rate_limit_rpm if route else 600
            state = RateLimitState(
                route_id=route_id,
                client_id=client_id,
                requests_remaining=limit,
                limit=limit,
                window_seconds=60,
                reset_at=now + timedelta(seconds=60),
            )
            self._rate_limit_states[state_key] = state

        # Check if window has reset
        if now >= state.reset_at:
            route = self._routes.get(route_id)
            limit = route.rate_limit_rpm if route else state.limit
            state = RateLimitState(
                route_id=route_id,
                client_id=client_id,
                requests_remaining=limit,
                limit=limit,
                window_seconds=60,
                reset_at=now + timedelta(seconds=60),
            )
            self._rate_limit_states[state_key] = state

        allowed = state.requests_remaining > 0
        return RateLimitCheckResponse(allowed=allowed, state=state)

    def consume_rate_limit(self, route_id: str, client_id: str, tokens: int = 1) -> RateLimitCheckResponse:
        """Consume rate limit tokens for a client on a route."""
        check = self.check_rate_limit(route_id, client_id)
        state_key = f"{route_id}:{client_id}"

        if not check.allowed:
            return check

        state = self._rate_limit_states[state_key]
        new_remaining = max(0, state.requests_remaining - tokens)
        updated = RateLimitState(
            route_id=route_id,
            client_id=client_id,
            requests_remaining=new_remaining,
            limit=state.limit,
            window_seconds=state.window_seconds,
            reset_at=state.reset_at,
        )
        self._rate_limit_states[state_key] = updated
        return RateLimitCheckResponse(
            allowed=new_remaining >= 0,
            state=updated,
        )

    def get_rate_limit_states(self, route_id: str | None = None) -> list[RateLimitState]:
        """Get rate limit states, optionally filtered by route."""
        states = list(self._rate_limit_states.values())
        if route_id is not None:
            states = [s for s in states if s.route_id == route_id]
        return states

    # -----------------------------------------------------------------------
    # Circuit Breaker
    # -----------------------------------------------------------------------

    def get_circuit_breaker(self, route_id: str) -> CircuitBreakerStatus | None:
        """Get circuit breaker status for a route."""
        return self._circuit_breakers.get(route_id)

    def get_circuit_breakers(self) -> CircuitBreakerListResponse:
        """Get all circuit breaker states."""
        cbs = list(self._circuit_breakers.values())
        open_count = sum(1 for cb in cbs if cb.state == CircuitBreakerState.OPEN)
        return CircuitBreakerListResponse(
            circuit_breakers=cbs,
            total=len(cbs),
            open_count=open_count,
        )

    def record_failure(self, route_id: str) -> CircuitBreakerStatus | None:
        """Record a failure for a route's circuit breaker."""
        cb = self._circuit_breakers.get(route_id)
        if cb is None:
            return None

        now = datetime.now(timezone.utc)
        new_failure_count = cb.failure_count + 1
        route = self._routes.get(route_id)
        threshold = route.circuit_breaker_threshold if route else cb.threshold

        if new_failure_count >= threshold and cb.state == CircuitBreakerState.CLOSED:
            timeout = route.circuit_breaker_timeout_seconds if route else 60
            updated = CircuitBreakerStatus(
                route_id=route_id,
                state=CircuitBreakerState.OPEN,
                failure_count=new_failure_count,
                success_count=0,
                threshold=threshold,
                last_failure_at=now,
                opens_at=now,
                half_open_at=now + timedelta(seconds=timeout),
            )
        else:
            updated = CircuitBreakerStatus(
                route_id=route_id,
                state=cb.state,
                failure_count=new_failure_count,
                success_count=cb.success_count,
                threshold=threshold,
                last_failure_at=now,
                opens_at=cb.opens_at,
                half_open_at=cb.half_open_at,
            )

        self._circuit_breakers[route_id] = updated
        return updated

    def record_success(self, route_id: str) -> CircuitBreakerStatus | None:
        """Record a success for a route's circuit breaker."""
        cb = self._circuit_breakers.get(route_id)
        if cb is None:
            return None

        if cb.state == CircuitBreakerState.HALF_OPEN:
            updated = CircuitBreakerStatus(
                route_id=route_id,
                state=CircuitBreakerState.CLOSED,
                failure_count=0,
                success_count=0,
                threshold=cb.threshold,
            )
        else:
            updated = CircuitBreakerStatus(
                route_id=route_id,
                state=cb.state,
                failure_count=max(0, cb.failure_count - 1),
                success_count=cb.success_count + 1,
                threshold=cb.threshold,
                last_failure_at=cb.last_failure_at,
                opens_at=cb.opens_at,
                half_open_at=cb.half_open_at,
            )

        self._circuit_breakers[route_id] = updated
        return updated

    def reset_circuit_breaker(self, route_id: str) -> CircuitBreakerStatus | None:
        """Reset a circuit breaker to CLOSED state."""
        if route_id not in self._circuit_breakers:
            return None

        route = self._routes.get(route_id)
        threshold = route.circuit_breaker_threshold if route else 5

        updated = CircuitBreakerStatus(
            route_id=route_id,
            state=CircuitBreakerState.CLOSED,
            failure_count=0,
            success_count=0,
            threshold=threshold,
        )
        self._circuit_breakers[route_id] = updated
        return updated

    # -----------------------------------------------------------------------
    # Route Health
    # -----------------------------------------------------------------------

    def get_route_health(self, route_id: str) -> RouteHealth | None:
        """Get health status for a single route."""
        route = self._routes.get(route_id)
        if route is None:
            return None

        cb = self._circuit_breakers.get(route_id)
        cb_state = cb.state if cb else CircuitBreakerState.CLOSED

        # Simulate health metrics
        latency = random.uniform(5.0, 200.0)
        error_rate = random.uniform(0.0, 5.0)

        if cb_state == CircuitBreakerState.OPEN:
            status = RouteHealthStatus.UNHEALTHY
            error_rate = random.uniform(20.0, 50.0)
        elif cb_state == CircuitBreakerState.HALF_OPEN:
            status = RouteHealthStatus.DEGRADED
            error_rate = random.uniform(5.0, 20.0)
        elif error_rate > 3.0:
            status = RouteHealthStatus.DEGRADED
        else:
            status = RouteHealthStatus.HEALTHY

        return RouteHealth(
            route_id=route_id,
            path_pattern=route.path_pattern,
            status=status,
            latency_ms=round(latency, 2),
            error_rate_percent=round(error_rate, 2),
            circuit_breaker_state=cb_state,
            last_checked=datetime.now(timezone.utc),
        )

    def get_all_route_health(self) -> RouteHealthListResponse:
        """Get health status for all routes."""
        health_list = []
        for route_id in self._routes:
            health = self.get_route_health(route_id)
            if health:
                health_list.append(health)

        healthy = sum(1 for h in health_list if h.status == RouteHealthStatus.HEALTHY)
        degraded = sum(1 for h in health_list if h.status == RouteHealthStatus.DEGRADED)
        unhealthy = sum(1 for h in health_list if h.status == RouteHealthStatus.UNHEALTHY)

        return RouteHealthListResponse(
            routes=health_list,
            total=len(health_list),
            healthy=healthy,
            degraded=degraded,
            unhealthy=unhealthy,
        )

    # -----------------------------------------------------------------------
    # Gateway Metrics
    # -----------------------------------------------------------------------

    def get_gateway_metrics(self) -> GatewayMetrics:
        """Calculate aggregate gateway metrics."""
        routes = list(self._routes.values())
        active = sum(1 for r in routes if r.status == GatewayRouteStatus.ACTIVE)
        deprecated = sum(1 for r in routes if r.status == GatewayRouteStatus.DEPRECATED)

        # Auth method distribution
        auth_dist: dict[str, int] = {}
        for r in routes:
            key = r.auth_method.value
            auth_dist[key] = auth_dist.get(key, 0) + 1

        # Latency stats
        latencies = self._request_latencies if self._request_latencies else [0.0]
        avg_latency = sum(latencies) / len(latencies)
        sorted_latencies = sorted(latencies)
        p99_idx = min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)
        p99_latency = sorted_latencies[p99_idx]

        total_reqs = self._total_requests
        error_rate = (self._error_count / max(1, total_reqs)) * 100

        # Cache hit rate
        cache_metrics = self.get_cache_metrics()

        # Top routes by traffic (simulated)
        top_routes = []
        for r in routes[:5]:
            top_routes.append({
                "route_id": r.id,
                "path": r.path_pattern,
                "requests_24h": random.randint(5000, 50000),
            })

        return GatewayMetrics(
            total_routes=len(routes),
            active_routes=active,
            deprecated_routes=deprecated,
            total_requests_24h=total_reqs,
            avg_latency_ms=round(avg_latency, 2),
            p99_latency_ms=round(p99_latency, 2),
            error_rate_percent=round(error_rate, 2),
            cache_hit_rate=cache_metrics.hit_rate_percent,
            routes_by_auth_method=auth_dist,
            top_routes_by_traffic=top_routes,
        )

    # -----------------------------------------------------------------------
    # API Documentation
    # -----------------------------------------------------------------------

    def get_api_documentation(self, version: str | None = None) -> APIDocumentationResponse:
        """Aggregate API documentation from registered routes."""
        entries = []
        versions_seen: set[str] = set()

        for route in self._routes.values():
            if version and route.version != version:
                continue

            versions_seen.add(route.version)
            entry = APIDocumentationEntry(
                path=route.path_pattern,
                method=route.method,
                description=f"Gateway route to {route.target_service}",
                auth_required=route.auth_method != AuthMethod.NONE,
                rate_limit=route.rate_limit_rpm,
                deprecated=route.status == GatewayRouteStatus.DEPRECATED,
                version=route.version,
            )
            entries.append(entry)

        return APIDocumentationResponse(
            endpoints=entries,
            total=len(entries),
            versions=sorted(versions_seen),
        )

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get service statistics for health check."""
        return {
            "total_routes": len(self._routes),
            "active_routes": sum(1 for r in self._routes.values() if r.status == GatewayRouteStatus.ACTIVE),
            "cache_configs": len(self._cache_configs),
            "cache_entries": len(self._cache_entries),
            "rate_limit_states": len(self._rate_limit_states),
            "circuit_breakers": len(self._circuit_breakers),
            "uptime_seconds": round(time.time() - self._start_time, 2),
        }

    def get_gateway_stats(self) -> GatewayStatsResponse:
        """Get full gateway statistics."""
        return GatewayStatsResponse(
            metrics=self.get_gateway_metrics(),
            cache_metrics=self.get_cache_metrics(),
            uptime_seconds=round(time.time() - self._start_time, 2),
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


def get_api_gateway_service() -> APIGatewayService:
    """Get or create the singleton APIGatewayService instance."""
    global _api_gateway_instance
    if _api_gateway_instance is None:
        with _api_gateway_lock:
            if _api_gateway_instance is None:
                _api_gateway_instance = APIGatewayService()
    return _api_gateway_instance


def reset_api_gateway_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _api_gateway_instance
    with _api_gateway_lock:
        _api_gateway_instance = None
