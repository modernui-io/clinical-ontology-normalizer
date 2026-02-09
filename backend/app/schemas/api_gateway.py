"""Pydantic schemas for API Gateway & Caching Strategy (CTO-10).

Provides models for API gateway route management, caching strategies,
rate limiting, circuit breaker patterns, request/response transformations,
and gateway-level observability metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class GatewayRouteStatus(str, Enum):
    """Lifecycle status of a gateway route."""

    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"
    RATE_LIMITED = "RATE_LIMITED"


class AuthMethod(str, Enum):
    """Authentication method required for a route."""

    API_KEY = "API_KEY"
    JWT = "JWT"
    OAUTH2 = "OAUTH2"
    MTLS = "MTLS"
    BASIC = "BASIC"
    NONE = "NONE"


class CacheStrategy(str, Enum):
    """Caching strategy for a route or config."""

    NO_CACHE = "NO_CACHE"
    READ_THROUGH = "READ_THROUGH"
    WRITE_THROUGH = "WRITE_THROUGH"
    WRITE_BEHIND = "WRITE_BEHIND"
    CACHE_ASIDE = "CACHE_ASIDE"
    TTL_BASED = "TTL_BASED"


class CacheStatus(str, Enum):
    """Status of a cache entry lookup."""

    HIT = "HIT"
    MISS = "MISS"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    BYPASS = "BYPASS"


class RateLimitAlgorithm(str, Enum):
    """Algorithm used for rate limiting."""

    TOKEN_BUCKET = "TOKEN_BUCKET"
    SLIDING_WINDOW = "SLIDING_WINDOW"
    FIXED_WINDOW = "FIXED_WINDOW"
    LEAKY_BUCKET = "LEAKY_BUCKET"


class TransformationType(str, Enum):
    """Type of request/response transformation."""

    REQUEST_HEADER = "REQUEST_HEADER"
    RESPONSE_HEADER = "RESPONSE_HEADER"
    REQUEST_BODY = "REQUEST_BODY"
    RESPONSE_BODY = "RESPONSE_BODY"
    URL_REWRITE = "URL_REWRITE"


class EvictionPolicy(str, Enum):
    """Cache eviction policy."""

    LRU = "LRU"
    LFU = "LFU"
    FIFO = "FIFO"
    TTL = "TTL"
    RANDOM = "RANDOM"


class CircuitBreakerState(str, Enum):
    """State of a circuit breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class RouteHealthStatus(str, Enum):
    """Health status of a gateway route."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Route Transformation
# ---------------------------------------------------------------------------


class RouteTransformation(BaseModel):
    """A single transformation applied to a request or response."""

    transformation_type: TransformationType = Field(
        description="Type of transformation to apply",
    )
    key: str = Field(
        description="Header name, body path, or URL pattern to transform",
    )
    value: str = Field(
        description="Target value or replacement pattern",
    )
    condition: str | None = Field(
        default=None,
        description="Optional condition for applying the transformation",
    )


# ---------------------------------------------------------------------------
# Gateway Route
# ---------------------------------------------------------------------------


class GatewayRoute(BaseModel):
    """Full record of a gateway route with routing, auth, caching, and resiliency config."""

    id: str = Field(
        description="Unique route identifier",
    )
    path_pattern: str = Field(
        description="URL path pattern (e.g., /api/v1/patients/*)",
    )
    target_service: str = Field(
        description="Downstream service name or URL",
    )
    method: str = Field(
        default="GET",
        description="HTTP method (GET, POST, PUT, DELETE, PATCH, *)",
    )
    auth_method: AuthMethod = Field(
        default=AuthMethod.JWT,
        description="Required authentication method",
    )
    rate_limit_rpm: int = Field(
        default=600,
        description="Rate limit in requests per minute",
    )
    rate_limit_algorithm: RateLimitAlgorithm = Field(
        default=RateLimitAlgorithm.TOKEN_BUCKET,
        description="Algorithm used for rate limiting",
    )
    status: GatewayRouteStatus = Field(
        default=GatewayRouteStatus.ACTIVE,
        description="Current route status",
    )
    cache_strategy: CacheStrategy = Field(
        default=CacheStrategy.NO_CACHE,
        description="Caching strategy for this route",
    )
    cache_ttl_seconds: int = Field(
        default=0,
        description="Cache TTL in seconds (0 = no caching)",
    )
    timeout_ms: int = Field(
        default=30000,
        description="Request timeout in milliseconds",
    )
    retry_count: int = Field(
        default=3,
        description="Number of retry attempts on failure",
    )
    retry_delay_ms: int = Field(
        default=1000,
        description="Delay between retries in milliseconds",
    )
    circuit_breaker_threshold: int = Field(
        default=5,
        description="Number of failures before circuit opens",
    )
    circuit_breaker_timeout_seconds: int = Field(
        default=60,
        description="Seconds before circuit half-opens for retry",
    )
    transformations: list[RouteTransformation] = Field(
        default_factory=list,
        description="Request/response transformations",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization and filtering",
    )
    created_at: datetime = Field(
        description="Route creation timestamp",
    )
    updated_at: datetime = Field(
        description="Last update timestamp",
    )
    version: str = Field(
        default="v1",
        description="API version this route belongs to",
    )
    deprecated_date: datetime | None = Field(
        default=None,
        description="Date the route was deprecated",
    )
    replacement_route: str | None = Field(
        default=None,
        description="Path to the replacement route if deprecated",
    )


# ---------------------------------------------------------------------------
# Cache Models
# ---------------------------------------------------------------------------


class CacheEntry(BaseModel):
    """A single entry in the gateway cache."""

    id: str = Field(
        description="Unique cache entry identifier",
    )
    route_id: str = Field(
        description="Route this cache entry belongs to",
    )
    cache_key: str = Field(
        description="Cache lookup key",
    )
    value_hash: str = Field(
        description="Hash of the cached value",
    )
    status: CacheStatus = Field(
        default=CacheStatus.HIT,
        description="Current status of this cache entry",
    )
    created_at: datetime = Field(
        description="When the entry was cached",
    )
    expires_at: datetime = Field(
        description="When the entry expires",
    )
    last_accessed: datetime = Field(
        description="Last access timestamp",
    )
    hit_count: int = Field(
        default=0,
        description="Number of cache hits",
    )
    size_bytes: int = Field(
        default=0,
        description="Size of cached value in bytes",
    )


class CacheConfig(BaseModel):
    """Configuration for a cache pool."""

    id: str = Field(
        description="Unique config identifier",
    )
    name: str = Field(
        description="Human-readable cache config name",
    )
    strategy: CacheStrategy = Field(
        description="Caching strategy",
    )
    default_ttl_seconds: int = Field(
        default=300,
        description="Default TTL in seconds",
    )
    max_entries: int = Field(
        default=10000,
        description="Maximum number of cache entries",
    )
    max_size_mb: float = Field(
        default=512.0,
        description="Maximum cache size in MB",
    )
    eviction_policy: EvictionPolicy = Field(
        default=EvictionPolicy.LRU,
        description="Eviction policy when cache is full",
    )
    warm_on_startup: bool = Field(
        default=False,
        description="Whether to pre-warm this cache on startup",
    )
    invalidation_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for cache invalidation",
    )


class CacheMetrics(BaseModel):
    """Aggregate cache performance metrics."""

    total_entries: int = Field(
        default=0,
        description="Total number of cache entries",
    )
    total_size_mb: float = Field(
        default=0.0,
        description="Total cache size in MB",
    )
    hit_count: int = Field(
        default=0,
        description="Total cache hits",
    )
    miss_count: int = Field(
        default=0,
        description="Total cache misses",
    )
    hit_rate_percent: float = Field(
        default=0.0,
        description="Cache hit rate as percentage",
    )
    eviction_count: int = Field(
        default=0,
        description="Total evictions",
    )
    avg_ttl_seconds: float = Field(
        default=0.0,
        description="Average TTL across entries",
    )
    warm_entries: int = Field(
        default=0,
        description="Number of pre-warmed entries",
    )
    stale_entries: int = Field(
        default=0,
        description="Number of stale entries",
    )


# ---------------------------------------------------------------------------
# Rate Limit State
# ---------------------------------------------------------------------------


class RateLimitState(BaseModel):
    """Current rate limit state for a client on a route."""

    route_id: str = Field(
        description="Route being rate-limited",
    )
    client_id: str = Field(
        description="Client identifier",
    )
    requests_remaining: int = Field(
        description="Requests remaining in current window",
    )
    limit: int = Field(
        description="Total request limit per window",
    )
    window_seconds: int = Field(
        default=60,
        description="Window duration in seconds",
    )
    reset_at: datetime = Field(
        description="When the current window resets",
    )


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitBreakerStatus(BaseModel):
    """Current state of a circuit breaker for a route."""

    route_id: str = Field(
        description="Route this circuit breaker protects",
    )
    state: CircuitBreakerState = Field(
        default=CircuitBreakerState.CLOSED,
        description="Current circuit breaker state",
    )
    failure_count: int = Field(
        default=0,
        description="Current failure count",
    )
    success_count: int = Field(
        default=0,
        description="Current success count (in half-open state)",
    )
    threshold: int = Field(
        default=5,
        description="Failure threshold before opening",
    )
    last_failure_at: datetime | None = Field(
        default=None,
        description="Timestamp of last failure",
    )
    opens_at: datetime | None = Field(
        default=None,
        description="When circuit opened (for timeout calculation)",
    )
    half_open_at: datetime | None = Field(
        default=None,
        description="When circuit transitions to half-open",
    )


# ---------------------------------------------------------------------------
# Route Health
# ---------------------------------------------------------------------------


class RouteHealth(BaseModel):
    """Health check result for a single route."""

    route_id: str = Field(
        description="Route identifier",
    )
    path_pattern: str = Field(
        description="Route path pattern",
    )
    status: RouteHealthStatus = Field(
        description="Health status",
    )
    latency_ms: float = Field(
        default=0.0,
        description="Average latency in ms",
    )
    error_rate_percent: float = Field(
        default=0.0,
        description="Error rate as percentage",
    )
    circuit_breaker_state: CircuitBreakerState = Field(
        default=CircuitBreakerState.CLOSED,
        description="Circuit breaker state",
    )
    last_checked: datetime = Field(
        description="Last health check timestamp",
    )


# ---------------------------------------------------------------------------
# Gateway Metrics
# ---------------------------------------------------------------------------


class GatewayMetrics(BaseModel):
    """Aggregate gateway performance metrics."""

    total_routes: int = Field(
        default=0,
        description="Total registered routes",
    )
    active_routes: int = Field(
        default=0,
        description="Active routes",
    )
    deprecated_routes: int = Field(
        default=0,
        description="Deprecated routes",
    )
    total_requests_24h: int = Field(
        default=0,
        description="Total requests in last 24 hours",
    )
    avg_latency_ms: float = Field(
        default=0.0,
        description="Average latency across all routes in ms",
    )
    p99_latency_ms: float = Field(
        default=0.0,
        description="99th percentile latency in ms",
    )
    error_rate_percent: float = Field(
        default=0.0,
        description="Overall error rate as percentage",
    )
    cache_hit_rate: float = Field(
        default=0.0,
        description="Overall cache hit rate",
    )
    routes_by_auth_method: dict[str, int] = Field(
        default_factory=dict,
        description="Route count by auth method",
    )
    top_routes_by_traffic: list[dict[str, object]] = Field(
        default_factory=list,
        description="Top routes by traffic volume",
    )


# ---------------------------------------------------------------------------
# API Documentation
# ---------------------------------------------------------------------------


class APIDocumentationEntry(BaseModel):
    """Documentation entry for an API endpoint."""

    path: str = Field(
        description="Endpoint path",
    )
    method: str = Field(
        description="HTTP method",
    )
    description: str = Field(
        description="Endpoint description",
    )
    auth_required: bool = Field(
        default=True,
        description="Whether authentication is required",
    )
    rate_limit: int = Field(
        default=600,
        description="Rate limit in RPM",
    )
    deprecated: bool = Field(
        default=False,
        description="Whether the endpoint is deprecated",
    )
    version: str = Field(
        default="v1",
        description="API version",
    )
    request_schema: dict | None = Field(
        default=None,
        description="JSON Schema for request body",
    )
    response_schema: dict | None = Field(
        default=None,
        description="JSON Schema for response body",
    )


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class GatewayRouteCreateRequest(BaseModel):
    """Request to create a new gateway route."""

    path_pattern: str = Field(
        description="URL path pattern",
    )
    target_service: str = Field(
        description="Downstream service name",
    )
    method: str = Field(
        default="GET",
        description="HTTP method",
    )
    auth_method: AuthMethod = Field(
        default=AuthMethod.JWT,
        description="Authentication method",
    )
    rate_limit_rpm: int = Field(
        default=600,
        description="Rate limit RPM",
    )
    rate_limit_algorithm: RateLimitAlgorithm = Field(
        default=RateLimitAlgorithm.TOKEN_BUCKET,
        description="Rate limit algorithm",
    )
    cache_strategy: CacheStrategy = Field(
        default=CacheStrategy.NO_CACHE,
        description="Cache strategy",
    )
    cache_ttl_seconds: int = Field(
        default=0,
        description="Cache TTL seconds",
    )
    timeout_ms: int = Field(
        default=30000,
        description="Timeout ms",
    )
    retry_count: int = Field(
        default=3,
        description="Retry count",
    )
    retry_delay_ms: int = Field(
        default=1000,
        description="Retry delay ms",
    )
    circuit_breaker_threshold: int = Field(
        default=5,
        description="Circuit breaker threshold",
    )
    circuit_breaker_timeout_seconds: int = Field(
        default=60,
        description="Circuit breaker timeout",
    )
    transformations: list[RouteTransformation] = Field(
        default_factory=list,
        description="Transformations",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags",
    )
    version: str = Field(
        default="v1",
        description="API version",
    )


class GatewayRouteUpdateRequest(BaseModel):
    """Request to update a gateway route."""

    path_pattern: str | None = Field(default=None, description="URL path pattern")
    target_service: str | None = Field(default=None, description="Target service")
    method: str | None = Field(default=None, description="HTTP method")
    auth_method: AuthMethod | None = Field(default=None, description="Auth method")
    rate_limit_rpm: int | None = Field(default=None, description="Rate limit RPM")
    rate_limit_algorithm: RateLimitAlgorithm | None = Field(default=None, description="Rate limit algorithm")
    status: GatewayRouteStatus | None = Field(default=None, description="Route status")
    cache_strategy: CacheStrategy | None = Field(default=None, description="Cache strategy")
    cache_ttl_seconds: int | None = Field(default=None, description="Cache TTL")
    timeout_ms: int | None = Field(default=None, description="Timeout ms")
    retry_count: int | None = Field(default=None, description="Retry count")
    retry_delay_ms: int | None = Field(default=None, description="Retry delay ms")
    circuit_breaker_threshold: int | None = Field(default=None, description="CB threshold")
    circuit_breaker_timeout_seconds: int | None = Field(default=None, description="CB timeout")
    transformations: list[RouteTransformation] | None = Field(default=None, description="Transformations")
    tags: list[str] | None = Field(default=None, description="Tags")
    version: str | None = Field(default=None, description="API version")


class GatewayRouteListResponse(BaseModel):
    """Response containing a list of gateway routes."""

    routes: list[GatewayRoute] = Field(
        default_factory=list,
        description="List of gateway routes",
    )
    total: int = Field(
        default=0,
        description="Total number of routes",
    )


class CacheConfigListResponse(BaseModel):
    """Response containing a list of cache configs."""

    configs: list[CacheConfig] = Field(
        default_factory=list,
        description="List of cache configurations",
    )
    total: int = Field(
        default=0,
        description="Total number of configs",
    )


class CacheEntryListResponse(BaseModel):
    """Response containing a list of cache entries."""

    entries: list[CacheEntry] = Field(
        default_factory=list,
        description="List of cache entries",
    )
    total: int = Field(
        default=0,
        description="Total number of entries",
    )


class CacheSetRequest(BaseModel):
    """Request to set a cache entry."""

    route_id: str = Field(description="Route to cache for")
    cache_key: str = Field(description="Cache key")
    value_hash: str = Field(description="Hash of the value to cache")
    ttl_seconds: int | None = Field(default=None, description="Optional TTL override")
    size_bytes: int = Field(default=0, description="Size of cached value")


class CacheInvalidateRequest(BaseModel):
    """Request to invalidate cache entries."""

    pattern: str = Field(
        description="Glob pattern for cache key invalidation",
    )
    route_id: str | None = Field(
        default=None,
        description="Optional route ID to scope invalidation",
    )


class CacheFlushRequest(BaseModel):
    """Request to flush a cache pool."""

    config_id: str | None = Field(
        default=None,
        description="Optional config ID to flush (None = all)",
    )


class RateLimitCheckRequest(BaseModel):
    """Request to check rate limit status."""

    route_id: str = Field(description="Route to check")
    client_id: str = Field(description="Client identifier")


class RateLimitCheckResponse(BaseModel):
    """Response to rate limit check."""

    allowed: bool = Field(description="Whether the request is allowed")
    state: RateLimitState = Field(description="Current rate limit state")


class RateLimitConsumeRequest(BaseModel):
    """Request to consume a rate limit token."""

    route_id: str = Field(description="Route to consume from")
    client_id: str = Field(description="Client identifier")
    tokens: int = Field(default=1, description="Number of tokens to consume")


class RouteHealthListResponse(BaseModel):
    """Response containing health status of all routes."""

    routes: list[RouteHealth] = Field(
        default_factory=list,
        description="Health status of each route",
    )
    total: int = Field(default=0, description="Total routes")
    healthy: int = Field(default=0, description="Healthy routes")
    degraded: int = Field(default=0, description="Degraded routes")
    unhealthy: int = Field(default=0, description="Unhealthy routes")


class CacheWarmRequest(BaseModel):
    """Request to warm a cache pool."""

    config_id: str = Field(description="Cache config to warm")


class CacheWarmResponse(BaseModel):
    """Response from a cache warm operation."""

    config_id: str = Field(description="Cache config warmed")
    entries_warmed: int = Field(description="Number of entries warmed")
    duration_ms: float = Field(description="Duration in ms")


class APIDocumentationResponse(BaseModel):
    """Response containing API documentation entries."""

    endpoints: list[APIDocumentationEntry] = Field(
        default_factory=list,
        description="API documentation entries",
    )
    total: int = Field(default=0, description="Total endpoints documented")
    versions: list[str] = Field(
        default_factory=list,
        description="Available API versions",
    )


class CircuitBreakerResetRequest(BaseModel):
    """Request to reset a circuit breaker."""

    route_id: str = Field(description="Route whose circuit breaker to reset")


class CircuitBreakerListResponse(BaseModel):
    """Response listing circuit breaker states."""

    circuit_breakers: list[CircuitBreakerStatus] = Field(
        default_factory=list,
        description="Circuit breaker states",
    )
    total: int = Field(default=0, description="Total circuit breakers")
    open_count: int = Field(default=0, description="Number of open circuit breakers")


class GatewayStatsResponse(BaseModel):
    """Summary statistics for the API gateway."""

    metrics: GatewayMetrics = Field(description="Gateway metrics")
    cache_metrics: CacheMetrics = Field(description="Cache metrics")
    uptime_seconds: float = Field(default=0.0, description="Gateway uptime")
