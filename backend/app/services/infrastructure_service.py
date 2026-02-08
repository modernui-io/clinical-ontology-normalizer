"""Production Infrastructure Service (VPE-6).

Monitors deployment health, tracks service dependencies, validates
configuration, and assesses deployment readiness for the clinical
trial platform.

Usage:
    from app.services.infrastructure_service import get_infrastructure_service

    svc = get_infrastructure_service()
    health = svc.get_all_health()
    readiness = svc.check_deployment_readiness()
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.schemas.infrastructure import (
    AllServicesHealth,
    ComplianceSeverity,
    ConfigValidationIssue,
    ConfigValidationResult,
    ConnectionPoolStats,
    DeploymentReadiness,
    DependencyGraph,
    HealthCheckResult,
    InfrastructureRecommendation,
    ReadinessCheck,
    ReadinessStatus,
    ResourceUtilization,
    ServiceDependency,
    ServiceHealth,
    ServiceResourceUsage,
    ServiceStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service definitions: name -> metadata
# ---------------------------------------------------------------------------

DEFAULT_SERVICES: dict[str, dict[str, Any]] = {
    "postgres": {
        "version": "16-alpine",
        "port": 5432,
        "protocol": "tcp",
        "required_env": [
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        ],
        "resource_limits": {"cpu": "2", "memory": "4G"},
    },
    "redis": {
        "version": "7-alpine",
        "port": 6379,
        "protocol": "tcp",
        "required_env": [],
        "resource_limits": {"cpu": "1", "memory": "1G"},
    },
    "neo4j": {
        "version": "5",
        "port": 7687,
        "protocol": "bolt",
        "required_env": ["NEO4J_AUTH"],
        "resource_limits": {"cpu": "2", "memory": "4G"},
    },
    "kafka": {
        "version": "latest",
        "port": 9092,
        "protocol": "tcp",
        "required_env": [
            "KAFKA_BROKER_ID",
            "KAFKA_ZOOKEEPER_CONNECT",
        ],
        "resource_limits": {"cpu": "2", "memory": "2G"},
    },
    "zookeeper": {
        "version": "latest",
        "port": 2181,
        "protocol": "tcp",
        "required_env": [],
        "resource_limits": {"cpu": "0.5", "memory": "512M"},
    },
    "backend": {
        "version": "prod",
        "port": 8000,
        "protocol": "http",
        "required_env": [
            "DATABASE_URL",
            "REDIS_URL",
            "API_KEY",
        ],
        "resource_limits": {"cpu": "2", "memory": "2G"},
    },
    "worker": {
        "version": "prod",
        "port": None,
        "protocol": None,
        "required_env": [
            "DATABASE_URL",
            "REDIS_URL",
        ],
        "resource_limits": {"cpu": "1", "memory": "1G"},
    },
    "frontend": {
        "version": "prod",
        "port": 3000,
        "protocol": "http",
        "required_env": ["NODE_ENV", "NEXT_PUBLIC_API_URL"],
        "resource_limits": {"cpu": "1", "memory": "512M"},
    },
    "nginx": {
        "version": "alpine",
        "port": 80,
        "protocol": "http",
        "required_env": [],
        "resource_limits": {"cpu": "0.5", "memory": "256M"},
    },
}

# ---------------------------------------------------------------------------
# Dependency definitions
# ---------------------------------------------------------------------------

DEFAULT_DEPENDENCIES: list[dict[str, Any]] = [
    {"source": "backend", "target": "postgres", "type": "required", "port": 5432},
    {"source": "backend", "target": "redis", "type": "required", "port": 6379},
    {"source": "backend", "target": "neo4j", "type": "optional", "port": 7687},
    {"source": "backend", "target": "kafka", "type": "optional", "port": 9092},
    {"source": "worker", "target": "postgres", "type": "required", "port": 5432},
    {"source": "worker", "target": "redis", "type": "required", "port": 6379},
    {"source": "worker", "target": "neo4j", "type": "optional", "port": 7687},
    {"source": "worker", "target": "kafka", "type": "optional", "port": 9092},
    {"source": "frontend", "target": "backend", "type": "required", "port": 8000},
    {"source": "nginx", "target": "backend", "type": "required", "port": 8000},
    {"source": "nginx", "target": "frontend", "type": "required", "port": 3000},
    {"source": "kafka", "target": "zookeeper", "type": "required", "port": 2181},
]


class InfrastructureService:
    """Monitors and manages production infrastructure health.

    Tracks per-service health status, resource utilization (simulated),
    configuration validation, and deployment readiness.
    """

    def __init__(
        self,
        services: dict[str, dict[str, Any]] | None = None,
        dependencies: list[dict[str, Any]] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._services = services or dict(DEFAULT_SERVICES)
        self._raw_dependencies = dependencies if dependencies is not None else list(DEFAULT_DEPENDENCIES)

        # Per-service health state
        self._health: dict[str, ServiceHealth] = {}
        self._start_times: dict[str, float] = {}

        # Initialize all services as UNKNOWN
        now = datetime.now(timezone.utc)
        for name, meta in self._services.items():
            self._health[name] = ServiceHealth(
                name=name,
                status=ServiceStatus.UNKNOWN,
                version=meta.get("version"),
                health_check=HealthCheckResult(
                    last_check=now,
                    response_time_ms=0.0,
                    consecutive_failures=0,
                    message="Not yet checked",
                ),
            )
            self._start_times[name] = time.time()

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    def record_health_check(
        self,
        service: str,
        *,
        healthy: bool,
        response_time_ms: float = 0.0,
        message: str = "",
    ) -> ServiceHealth:
        """Record a health check result for a service.

        Transitions:
        - 3+ consecutive failures -> UNHEALTHY
        - 1-2 consecutive failures -> DEGRADED
        - 0 consecutive failures -> HEALTHY
        """
        with self._lock:
            if service not in self._health:
                raise ValueError(f"Unknown service: {service}")

            current = self._health[service]
            prev_failures = (
                current.health_check.consecutive_failures
                if current.health_check
                else 0
            )

            if healthy:
                consecutive_failures = 0
                status = ServiceStatus.HEALTHY
            else:
                consecutive_failures = prev_failures + 1
                if consecutive_failures >= 3:
                    status = ServiceStatus.UNHEALTHY
                else:
                    status = ServiceStatus.DEGRADED

            now = datetime.now(timezone.utc)
            check_result = HealthCheckResult(
                last_check=now,
                response_time_ms=response_time_ms,
                consecutive_failures=consecutive_failures,
                message=message,
            )

            uptime = time.time() - self._start_times.get(service, time.time())

            updated = ServiceHealth(
                name=service,
                status=status,
                health_check=check_result,
                version=current.version,
                uptime_seconds=uptime,
                metadata=current.metadata,
            )
            self._health[service] = updated
            return updated

    def get_service_health(self, service: str) -> ServiceHealth:
        """Get current health for a single service."""
        with self._lock:
            if service not in self._health:
                raise ValueError(f"Unknown service: {service}")
            return self._health[service]

    def get_all_health(self) -> AllServicesHealth:
        """Get aggregated health for all services."""
        with self._lock:
            services = list(self._health.values())

        healthy = sum(1 for s in services if s.status == ServiceStatus.HEALTHY)
        degraded = sum(1 for s in services if s.status == ServiceStatus.DEGRADED)
        unhealthy = sum(1 for s in services if s.status == ServiceStatus.UNHEALTHY)

        # Overall status is the worst status
        if unhealthy > 0:
            overall = ServiceStatus.UNHEALTHY
        elif degraded > 0:
            overall = ServiceStatus.DEGRADED
        elif healthy == len(services):
            overall = ServiceStatus.HEALTHY
        else:
            overall = ServiceStatus.UNKNOWN

        return AllServicesHealth(
            timestamp=datetime.now(timezone.utc),
            overall_status=overall,
            services=services,
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
        )

    # ------------------------------------------------------------------
    # Resource utilization (simulated)
    # ------------------------------------------------------------------

    def get_resource_utilization(self) -> ResourceUtilization:
        """Get simulated resource utilization for all services."""
        service_resources: list[ServiceResourceUsage] = []

        for name, meta in self._services.items():
            # Simulate realistic resource usage
            mem_limit_str = meta.get("resource_limits", {}).get("memory", "512M")
            mem_limit_mb = self._parse_memory_mb(mem_limit_str)

            usage = ServiceResourceUsage(
                service=name,
                cpu_percent=round(random.uniform(5, 60), 1),
                memory_mb=round(random.uniform(mem_limit_mb * 0.2, mem_limit_mb * 0.7), 1),
                memory_limit_mb=mem_limit_mb,
                memory_percent=0.0,
                disk_usage_mb=round(random.uniform(50, 500), 1),
                network_rx_bytes=random.randint(1000, 10_000_000),
                network_tx_bytes=random.randint(1000, 10_000_000),
            )
            usage.memory_percent = round(
                (usage.memory_mb / usage.memory_limit_mb * 100) if usage.memory_limit_mb > 0 else 0.0,
                1,
            )
            service_resources.append(usage)

        # Simulate connection pools
        pools = [
            ConnectionPoolStats(
                service="postgres",
                active_connections=random.randint(5, 50),
                idle_connections=random.randint(2, 20),
                max_connections=200,
                utilization_percent=round(random.uniform(10, 40), 1),
            ),
            ConnectionPoolStats(
                service="redis",
                active_connections=random.randint(2, 30),
                idle_connections=random.randint(1, 10),
                max_connections=100,
                utilization_percent=round(random.uniform(5, 25), 1),
            ),
        ]

        total_cpu = sum(r.cpu_percent for r in service_resources)
        total_mem = sum(r.memory_mb for r in service_resources)

        return ResourceUtilization(
            timestamp=datetime.now(timezone.utc),
            services=service_resources,
            connection_pools=pools,
            total_cpu_percent=round(total_cpu, 1),
            total_memory_mb=round(total_mem, 1),
        )

    @staticmethod
    def _parse_memory_mb(value: str) -> float:
        """Parse memory string like '4G' or '512M' to MB."""
        value = value.strip().upper()
        if value.endswith("G"):
            return float(value[:-1]) * 1024
        if value.endswith("M"):
            return float(value[:-1])
        if value.endswith("K"):
            return float(value[:-1]) / 1024
        try:
            return float(value)
        except ValueError:
            return 512.0

    # ------------------------------------------------------------------
    # Dependency graph
    # ------------------------------------------------------------------

    def get_dependency_graph(self) -> DependencyGraph:
        """Build and return the service dependency graph."""
        deps: list[ServiceDependency] = []
        for d in self._raw_dependencies:
            deps.append(
                ServiceDependency(
                    source=d["source"],
                    target=d["target"],
                    dependency_type=d.get("type", "required"),
                    port=d.get("port"),
                    protocol=d.get("protocol"),
                )
            )

        service_names = list(self._services.keys())
        has_circular, circular_chains = self._detect_circular_dependencies()
        startup_order = self._compute_startup_order()

        return DependencyGraph(
            services=service_names,
            dependencies=deps,
            startup_order=startup_order,
            has_circular_dependencies=has_circular,
            circular_chains=circular_chains,
        )

    def _detect_circular_dependencies(self) -> tuple[bool, list[list[str]]]:
        """Detect circular dependencies using DFS cycle detection."""
        # Build adjacency list
        adj: dict[str, list[str]] = {name: [] for name in self._services}
        for d in self._raw_dependencies:
            src = d["source"]
            tgt = d["target"]
            if src in adj:
                adj[src].append(tgt)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in adj}
        cycles: list[list[str]] = []
        path: list[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle: extract it
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for node in adj:
            if color[node] == WHITE:
                dfs(node)

        return (len(cycles) > 0, cycles)

    def _compute_startup_order(self) -> list[str]:
        """Compute topological startup order (dependencies first)."""
        # Build adjacency list: source depends on target, so target must start first
        adj: dict[str, list[str]] = {name: [] for name in self._services}
        in_degree: dict[str, int] = {name: 0 for name in self._services}

        for d in self._raw_dependencies:
            src = d["source"]
            tgt = d["target"]
            if src in adj and tgt in adj:
                adj[tgt].append(src)  # target -> source (target starts first)
                in_degree[src] = in_degree.get(src, 0) + 1

        # Kahn's algorithm
        queue = [n for n in self._services if in_degree.get(n, 0) == 0]
        order: list[str] = []

        while queue:
            queue.sort()  # deterministic ordering
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    # ------------------------------------------------------------------
    # Configuration validation
    # ------------------------------------------------------------------

    def validate_configuration(
        self,
        env_vars: dict[str, dict[str, str]] | None = None,
        port_bindings: dict[str, int] | None = None,
    ) -> ConfigValidationResult:
        """Validate service configuration.

        Args:
            env_vars: Per-service environment variables {service: {var: value}}.
            port_bindings: Service-to-port mappings for conflict detection.
        """
        issues: list[ConfigValidationIssue] = []
        env_vars = env_vars or {}
        port_bindings = port_bindings or {}

        # Check required environment variables
        for svc_name, meta in self._services.items():
            required = meta.get("required_env", [])
            provided = env_vars.get(svc_name, {})

            for var in required:
                if var not in provided or not provided[var]:
                    issues.append(
                        ConfigValidationIssue(
                            service=svc_name,
                            category="env_vars",
                            severity=ComplianceSeverity.CRITICAL,
                            message=f"Required environment variable {var} is missing",
                        )
                    )

        # Check port conflicts
        seen_ports: dict[int, str] = {}
        for svc_name, port in port_bindings.items():
            if port in seen_ports:
                issues.append(
                    ConfigValidationIssue(
                        service=svc_name,
                        category="ports",
                        severity=ComplianceSeverity.CRITICAL,
                        message=f"Port {port} conflicts with service {seen_ports[port]}",
                    )
                )
            else:
                seen_ports[port] = svc_name

        valid = not any(i.severity == ComplianceSeverity.CRITICAL for i in issues)

        return ConfigValidationResult(
            valid=valid,
            issues=issues,
            checked_services=list(self._services.keys()),
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Deployment readiness
    # ------------------------------------------------------------------

    def check_deployment_readiness(
        self,
        *,
        migrations_applied: bool = True,
        redis_connected: bool = True,
        secrets_configured: bool = True,
        tls_valid: bool = True,
    ) -> DeploymentReadiness:
        """Assess overall deployment readiness."""
        checks: list[ReadinessCheck] = []

        # 1. All services healthy
        health = self.get_all_health()
        all_healthy = health.unhealthy_count == 0
        checks.append(
            ReadinessCheck(
                name="all_services_healthy",
                passed=all_healthy,
                message=(
                    "All services reporting healthy"
                    if all_healthy
                    else f"{health.unhealthy_count} service(s) unhealthy"
                ),
                required=True,
            )
        )

        # 2. Database migrations
        checks.append(
            ReadinessCheck(
                name="database_migrations",
                passed=migrations_applied,
                message=(
                    "All migrations applied"
                    if migrations_applied
                    else "Pending migrations detected"
                ),
                required=True,
            )
        )

        # 3. Redis connectivity
        checks.append(
            ReadinessCheck(
                name="redis_connectivity",
                passed=redis_connected,
                message=(
                    "Redis connection established"
                    if redis_connected
                    else "Cannot connect to Redis"
                ),
                required=True,
            )
        )

        # 4. Secrets configured
        checks.append(
            ReadinessCheck(
                name="secrets_configured",
                passed=secrets_configured,
                message=(
                    "All required secrets configured"
                    if secrets_configured
                    else "Missing required secrets"
                ),
                required=True,
            )
        )

        # 5. TLS certificates
        checks.append(
            ReadinessCheck(
                name="tls_certificates",
                passed=tls_valid,
                message=(
                    "TLS certificates valid"
                    if tls_valid
                    else "TLS certificates expired or missing"
                ),
                required=False,
            )
        )

        passed = [c for c in checks if c.passed]
        failed = [c for c in checks if not c.passed]
        blocking = [c.name for c in failed if c.required]

        if not blocking:
            status = ReadinessStatus.READY
        elif len(blocking) == len([c for c in checks if c.required]):
            status = ReadinessStatus.NOT_READY
        else:
            status = ReadinessStatus.DEGRADED

        return DeploymentReadiness(
            status=status,
            timestamp=datetime.now(timezone.utc),
            checks=checks,
            passed_count=len(passed),
            failed_count=len(failed),
            total_count=len(checks),
            blocking_issues=blocking,
        )

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def get_recommendations(self) -> list[InfrastructureRecommendation]:
        """Generate infrastructure improvement recommendations."""
        recs: list[InfrastructureRecommendation] = []

        # Check for unhealthy services
        health = self.get_all_health()
        if health.unhealthy_count > 0:
            recs.append(
                InfrastructureRecommendation(
                    category="health",
                    priority="high",
                    title="Resolve unhealthy services",
                    description=(
                        f"{health.unhealthy_count} service(s) are unhealthy. "
                        "Investigate root cause and restore to healthy state."
                    ),
                    impact="Prevents production incidents and data loss",
                )
            )

        # Check dependency graph for circular deps
        graph = self.get_dependency_graph()
        if graph.has_circular_dependencies:
            recs.append(
                InfrastructureRecommendation(
                    category="architecture",
                    priority="high",
                    title="Resolve circular dependencies",
                    description=(
                        "Circular dependencies detected in service graph. "
                        "This can cause startup deadlocks and cascading failures."
                    ),
                    impact="Improves startup reliability and failure isolation",
                )
            )

        # Standard recommendations
        recs.extend([
            InfrastructureRecommendation(
                category="monitoring",
                priority="medium",
                title="Enable Prometheus metrics collection",
                description=(
                    "Configure Prometheus to scrape /metrics endpoints from all services. "
                    "Set up Grafana dashboards for visibility."
                ),
                impact="Proactive issue detection and trend analysis",
            ),
            InfrastructureRecommendation(
                category="backup",
                priority="high",
                title="Configure automated database backups",
                description=(
                    "Set up pg_dump or pgBackRest for PostgreSQL automated backups "
                    "with point-in-time recovery. Test restore procedures monthly."
                ),
                impact="Protects against data loss and enables disaster recovery",
            ),
            InfrastructureRecommendation(
                category="security",
                priority="high",
                title="Rotate secrets and API keys regularly",
                description=(
                    "Implement automated secret rotation for database passwords, "
                    "API keys, and TLS certificates. Use a secrets manager."
                ),
                impact="Reduces risk of credential compromise",
            ),
            InfrastructureRecommendation(
                category="networking",
                priority="medium",
                title="Implement network segmentation",
                description=(
                    "Create separate Docker networks for frontend, backend, and data tiers. "
                    "Restrict inter-service communication to required paths only."
                ),
                impact="Limits blast radius of security incidents",
            ),
        ])

        return recs

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service stats for prewarm logging."""
        health = self.get_all_health()
        return {
            "total_services": len(self._services),
            "healthy": health.healthy_count,
            "degraded": health.degraded_count,
            "unhealthy": health.unhealthy_count,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InfrastructureService | None = None
_lock = threading.Lock()


def get_infrastructure_service() -> InfrastructureService:
    """Get or create the singleton InfrastructureService."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = InfrastructureService()
    return _instance


def reset_infrastructure_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
