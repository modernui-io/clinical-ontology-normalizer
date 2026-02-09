"""API Gateway & Caching Strategy endpoints (CTO-10).

Provides endpoints for gateway route management, cache management,
rate limiting, circuit breaker state, health checking, and
gateway-level observability.

Endpoints:
    GET    /api/v1/api-gateway/routes                              - List all routes
    POST   /api/v1/api-gateway/routes                              - Create a route
    GET    /api/v1/api-gateway/routes/{route_id}                   - Get route detail
    PUT    /api/v1/api-gateway/routes/{route_id}                   - Update a route
    DELETE /api/v1/api-gateway/routes/{route_id}                   - Delete a route
    GET    /api/v1/api-gateway/cache/configs                       - List cache configs
    GET    /api/v1/api-gateway/cache/configs/{config_id}           - Get cache config
    GET    /api/v1/api-gateway/cache/entries                       - List cache entries
    GET    /api/v1/api-gateway/cache/lookup/{cache_key}            - Look up cache entry
    POST   /api/v1/api-gateway/cache/set                           - Set cache entry
    POST   /api/v1/api-gateway/cache/invalidate                    - Invalidate cache
    POST   /api/v1/api-gateway/cache/flush                         - Flush cache
    GET    /api/v1/api-gateway/cache/metrics                       - Cache metrics
    POST   /api/v1/api-gateway/cache/warm                          - Warm cache
    POST   /api/v1/api-gateway/rate-limit/check                    - Check rate limit
    POST   /api/v1/api-gateway/rate-limit/consume                  - Consume rate limit
    GET    /api/v1/api-gateway/rate-limit/states                   - List rate limit states
    GET    /api/v1/api-gateway/health/routes                       - Route health status
    GET    /api/v1/api-gateway/health/routes/{route_id}            - Single route health
    GET    /api/v1/api-gateway/circuit-breakers                    - List circuit breakers
    POST   /api/v1/api-gateway/circuit-breakers/{route_id}/reset   - Reset circuit breaker
    GET    /api/v1/api-gateway/metrics                             - Gateway metrics
    GET    /api/v1/api-gateway/stats                               - Gateway stats
    GET    /api/v1/api-gateway/documentation                       - API documentation
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.api_gateway import (
    APIDocumentationResponse,
    AuthMethod,
    CacheConfig,
    CacheConfigListResponse,
    CacheEntry,
    CacheEntryListResponse,
    CacheFlushRequest,
    CacheInvalidateRequest,
    CacheMetrics,
    CacheSetRequest,
    CacheStatus,
    CacheWarmRequest,
    CacheWarmResponse,
    CircuitBreakerListResponse,
    CircuitBreakerStatus,
    GatewayMetrics,
    GatewayRoute,
    GatewayRouteCreateRequest,
    GatewayRouteListResponse,
    GatewayRouteStatus,
    GatewayRouteUpdateRequest,
    GatewayStatsResponse,
    RateLimitCheckRequest,
    RateLimitCheckResponse,
    RateLimitConsumeRequest,
    RateLimitState,
    RouteHealth,
    RouteHealthListResponse,
)
from app.services.api_gateway_service import get_api_gateway_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-gateway",
    tags=["API Gateway"],
)


# ============================================================================
# Route CRUD Endpoints
# ============================================================================


@router.get(
    "/routes",
    response_model=GatewayRouteListResponse,
    summary="List gateway routes",
    description="List all registered gateway routes with optional filtering.",
)
async def list_routes(
    status_filter: Optional[GatewayRouteStatus] = Query(None, alias="status", description="Filter by status"),
    auth_method: Optional[AuthMethod] = Query(None, description="Filter by auth method"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
) -> GatewayRouteListResponse:
    """List all gateway routes with optional filtering."""
    service = get_api_gateway_service()
    return service.list_routes(
        status=status_filter,
        auth_method=auth_method,
        tag=tag,
        method=method,
    )


@router.post(
    "/routes",
    response_model=GatewayRoute,
    status_code=status.HTTP_201_CREATED,
    summary="Create a gateway route",
    description="Register a new route in the API gateway.",
)
async def create_route(request: GatewayRouteCreateRequest) -> GatewayRoute:
    """Create a new gateway route."""
    service = get_api_gateway_service()
    return service.create_route(request)


@router.get(
    "/routes/{route_id}",
    response_model=GatewayRoute,
    summary="Get route detail",
    description="Get detailed information about a specific gateway route.",
)
async def get_route(route_id: str) -> GatewayRoute:
    """Get a single route by ID."""
    service = get_api_gateway_service()
    route = service.get_route(route_id)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found",
        )
    return route


@router.put(
    "/routes/{route_id}",
    response_model=GatewayRoute,
    summary="Update a gateway route",
    description="Update configuration for an existing gateway route.",
)
async def update_route(route_id: str, request: GatewayRouteUpdateRequest) -> GatewayRoute:
    """Update a gateway route."""
    service = get_api_gateway_service()
    route = service.update_route(route_id, request)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found",
        )
    return route


@router.delete(
    "/routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a gateway route",
    description="Remove a route from the API gateway.",
)
async def delete_route(route_id: str) -> None:
    """Delete a gateway route."""
    service = get_api_gateway_service()
    deleted = service.delete_route(route_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found",
        )


# ============================================================================
# Cache Management Endpoints
# ============================================================================


@router.get(
    "/cache/configs",
    response_model=CacheConfigListResponse,
    summary="List cache configurations",
    description="List all cache pool configurations.",
)
async def list_cache_configs() -> CacheConfigListResponse:
    """List all cache configurations."""
    service = get_api_gateway_service()
    configs = service.list_cache_configs()
    return CacheConfigListResponse(configs=configs, total=len(configs))


@router.get(
    "/cache/configs/{config_id}",
    response_model=CacheConfig,
    summary="Get cache configuration",
    description="Get a specific cache pool configuration.",
)
async def get_cache_config(config_id: str) -> CacheConfig:
    """Get a cache config by ID."""
    service = get_api_gateway_service()
    config = service.get_cache_config(config_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cache config '{config_id}' not found",
        )
    return config


@router.get(
    "/cache/entries",
    response_model=CacheEntryListResponse,
    summary="List cache entries",
    description="List cache entries with optional filtering.",
)
async def list_cache_entries(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    cache_status: Optional[CacheStatus] = Query(None, alias="status", description="Filter by status"),
) -> CacheEntryListResponse:
    """List cache entries."""
    service = get_api_gateway_service()
    return service.get_cache_entries(route_id=route_id, status=cache_status)


@router.get(
    "/cache/lookup/{cache_key:path}",
    response_model=CacheEntry,
    summary="Look up cache entry",
    description="Look up a cache entry by its key.",
)
async def lookup_cache_entry(cache_key: str) -> CacheEntry:
    """Look up a cache entry by key."""
    service = get_api_gateway_service()
    entry = service.get_cache_entry(cache_key)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cache entry '{cache_key}' not found",
        )
    return entry


@router.post(
    "/cache/set",
    response_model=CacheEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Set cache entry",
    description="Create or update a cache entry.",
)
async def set_cache_entry(request: CacheSetRequest) -> CacheEntry:
    """Set a cache entry."""
    service = get_api_gateway_service()
    return service.set_cache_entry(
        route_id=request.route_id,
        cache_key=request.cache_key,
        value_hash=request.value_hash,
        ttl_seconds=request.ttl_seconds,
        size_bytes=request.size_bytes,
    )


@router.post(
    "/cache/invalidate",
    summary="Invalidate cache entries",
    description="Invalidate cache entries matching a pattern.",
)
async def invalidate_cache(request: CacheInvalidateRequest) -> dict:
    """Invalidate cache entries by pattern."""
    service = get_api_gateway_service()
    count = service.invalidate_cache(pattern=request.pattern, route_id=request.route_id)
    return {"invalidated_count": count, "pattern": request.pattern}


@router.post(
    "/cache/flush",
    summary="Flush cache",
    description="Flush all or config-scoped cache entries.",
)
async def flush_cache(request: CacheFlushRequest) -> dict:
    """Flush cache entries."""
    service = get_api_gateway_service()
    count = service.flush_cache(config_id=request.config_id)
    return {"flushed_count": count, "config_id": request.config_id}


@router.get(
    "/cache/metrics",
    response_model=CacheMetrics,
    summary="Cache metrics",
    description="Get aggregate cache performance metrics.",
)
async def get_cache_metrics() -> CacheMetrics:
    """Get cache metrics."""
    service = get_api_gateway_service()
    return service.get_cache_metrics()


@router.post(
    "/cache/warm",
    response_model=CacheWarmResponse,
    summary="Warm cache",
    description="Pre-warm a cache pool by loading entries.",
)
async def warm_cache(request: CacheWarmRequest) -> CacheWarmResponse:
    """Warm a cache pool."""
    service = get_api_gateway_service()
    result = service.warm_cache(request.config_id)
    if result.entries_warmed == 0 and service.get_cache_config(request.config_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cache config '{request.config_id}' not found",
        )
    return result


# ============================================================================
# Rate Limiting Endpoints
# ============================================================================


@router.post(
    "/rate-limit/check",
    response_model=RateLimitCheckResponse,
    summary="Check rate limit",
    description="Check if a client is within rate limits for a route.",
)
async def check_rate_limit(request: RateLimitCheckRequest) -> RateLimitCheckResponse:
    """Check rate limit status."""
    service = get_api_gateway_service()
    return service.check_rate_limit(request.route_id, request.client_id)


@router.post(
    "/rate-limit/consume",
    response_model=RateLimitCheckResponse,
    summary="Consume rate limit tokens",
    description="Consume rate limit tokens for a client on a route.",
)
async def consume_rate_limit(request: RateLimitConsumeRequest) -> RateLimitCheckResponse:
    """Consume rate limit tokens."""
    service = get_api_gateway_service()
    return service.consume_rate_limit(request.route_id, request.client_id, request.tokens)


@router.get(
    "/rate-limit/states",
    response_model=list[RateLimitState],
    summary="List rate limit states",
    description="List current rate limit states across routes and clients.",
)
async def list_rate_limit_states(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
) -> list[RateLimitState]:
    """List rate limit states."""
    service = get_api_gateway_service()
    return service.get_rate_limit_states(route_id=route_id)


# ============================================================================
# Health Check Endpoints
# ============================================================================


@router.get(
    "/health/routes",
    response_model=RouteHealthListResponse,
    summary="Route health status",
    description="Get health status for all registered routes.",
)
async def get_all_route_health() -> RouteHealthListResponse:
    """Get health status for all routes."""
    service = get_api_gateway_service()
    return service.get_all_route_health()


@router.get(
    "/health/routes/{route_id}",
    response_model=RouteHealth,
    summary="Single route health",
    description="Get health status for a specific route.",
)
async def get_route_health(route_id: str) -> RouteHealth:
    """Get health status for a route."""
    service = get_api_gateway_service()
    health = service.get_route_health(route_id)
    if health is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found",
        )
    return health


# ============================================================================
# Circuit Breaker Endpoints
# ============================================================================


@router.get(
    "/circuit-breakers",
    response_model=CircuitBreakerListResponse,
    summary="List circuit breakers",
    description="List circuit breaker states for all routes.",
)
async def list_circuit_breakers() -> CircuitBreakerListResponse:
    """List all circuit breaker states."""
    service = get_api_gateway_service()
    return service.get_circuit_breakers()


@router.post(
    "/circuit-breakers/{route_id}/reset",
    response_model=CircuitBreakerStatus,
    summary="Reset circuit breaker",
    description="Reset a circuit breaker to CLOSED state.",
)
async def reset_circuit_breaker(route_id: str) -> CircuitBreakerStatus:
    """Reset a circuit breaker."""
    service = get_api_gateway_service()
    result = service.reset_circuit_breaker(route_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker for route '{route_id}' not found",
        )
    return result


# ============================================================================
# Metrics & Documentation Endpoints
# ============================================================================


@router.get(
    "/metrics",
    response_model=GatewayMetrics,
    summary="Gateway metrics",
    description="Get aggregate gateway performance metrics.",
)
async def get_gateway_metrics() -> GatewayMetrics:
    """Get gateway metrics."""
    service = get_api_gateway_service()
    return service.get_gateway_metrics()


@router.get(
    "/stats",
    response_model=GatewayStatsResponse,
    summary="Gateway statistics",
    description="Get comprehensive gateway statistics including cache and uptime.",
)
async def get_gateway_stats() -> GatewayStatsResponse:
    """Get gateway statistics."""
    service = get_api_gateway_service()
    return service.get_gateway_stats()


@router.get(
    "/documentation",
    response_model=APIDocumentationResponse,
    summary="API documentation",
    description="Aggregate API documentation from registered routes.",
)
async def get_api_documentation(
    version: Optional[str] = Query(None, description="Filter by API version"),
) -> APIDocumentationResponse:
    """Get API documentation."""
    service = get_api_gateway_service()
    return service.get_api_documentation(version=version)
