"""Tests for Production Infrastructure Service (VPE-6).

Covers:
- Service health tracking: status transitions, consecutive failure counting
- Dependency graph: correct ordering, circular dependency detection
- Configuration validation: missing vars, port conflicts
- Deployment readiness: all-pass and failure scenarios
- Compose analysis: valid and invalid configurations
- Resource limits check: present vs missing
- Restart policy validation
- Health check presence
- Logging configuration
- Security directive validation
- Image pinning check
- Compliance score calculation
- API endpoint responses
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.infrastructure import (
    AllServicesHealth,
    ComplianceScore,
    ComplianceSeverity,
    ComposeAnalysis,
    ComposeServiceAnalysis,
    ConfigValidationResult,
    DeploymentReadiness,
    DependencyGraph,
    HealthCheckResult,
    InfrastructureRecommendation,
    ReadinessCheck,
    ReadinessStatus,
    ResourceUtilization,
    ServiceDependency,
    ServiceHealth,
    ServiceStatus,
)
from app.services.compose_analyzer_service import (
    ComposeAnalyzerService,
    get_compose_analyzer,
    reset_compose_analyzer,
)
from app.services.infrastructure_service import (
    InfrastructureService,
    get_infrastructure_service,
    reset_infrastructure_service,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def infra_service() -> InfrastructureService:
    """Create a fresh InfrastructureService."""
    return InfrastructureService()


@pytest.fixture
def small_infra_service() -> InfrastructureService:
    """Create a small InfrastructureService with 3 services."""
    services = {
        "postgres": {
            "version": "16-alpine",
            "port": 5432,
            "protocol": "tcp",
            "required_env": ["POSTGRES_PASSWORD"],
            "resource_limits": {"cpu": "2", "memory": "4G"},
        },
        "redis": {
            "version": "7-alpine",
            "port": 6379,
            "protocol": "tcp",
            "required_env": [],
            "resource_limits": {"cpu": "1", "memory": "1G"},
        },
        "backend": {
            "version": "prod",
            "port": 8000,
            "protocol": "http",
            "required_env": ["DATABASE_URL", "API_KEY"],
            "resource_limits": {"cpu": "2", "memory": "2G"},
        },
    }
    deps = [
        {"source": "backend", "target": "postgres", "type": "required", "port": 5432},
        {"source": "backend", "target": "redis", "type": "required", "port": 6379},
    ]
    return InfrastructureService(services=services, dependencies=deps)


@pytest.fixture
def analyzer() -> ComposeAnalyzerService:
    """Create a fresh ComposeAnalyzerService."""
    return ComposeAnalyzerService()


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before each test."""
    reset_infrastructure_service()
    reset_compose_analyzer()
    yield
    reset_infrastructure_service()
    reset_compose_analyzer()


# ===========================================================================
# Valid compose data fixtures
# ===========================================================================


def _valid_service_config() -> dict:
    """Return a fully compliant service configuration."""
    return {
        "image": "postgres:16-alpine",
        "read_only": True,
        "security_opt": ["no-new-privileges:true"],
        "cap_drop": ["ALL"],
        "deploy": {
            "resources": {
                "limits": {"cpus": "2", "memory": "4G"},
                "reservations": {"cpus": "0.5", "memory": "1G"},
            }
        },
        "restart": "unless-stopped",
        "healthcheck": {
            "test": ["CMD-SHELL", "pg_isready -U postgres"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
        },
        "logging": {
            "driver": "json-file",
            "options": {"max-size": "100m", "max-file": "5"},
        },
        "environment": {
            "POSTGRES_DB": "${POSTGRES_DB:-clinical}",
            "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD:?required}",
        },
    }


def _minimal_service_config() -> dict:
    """Return a bare-minimum service configuration with no hardening."""
    return {
        "image": "myapp:latest",
    }


# ===========================================================================
# 1. Service Health Tracking Tests
# ===========================================================================


class TestServiceHealthTracking:
    """Tests for service health status tracking and transitions."""

    def test_initial_status_is_unknown(self, small_infra_service: InfrastructureService):
        """All services should start as UNKNOWN."""
        health = small_infra_service.get_service_health("postgres")
        assert health.status == ServiceStatus.UNKNOWN

    def test_healthy_after_successful_check(self, small_infra_service: InfrastructureService):
        """A successful check should transition to HEALTHY."""
        result = small_infra_service.record_health_check(
            "postgres", healthy=True, response_time_ms=5.2
        )
        assert result.status == ServiceStatus.HEALTHY
        assert result.health_check.consecutive_failures == 0
        assert result.health_check.response_time_ms == 5.2

    def test_degraded_after_one_failure(self, small_infra_service: InfrastructureService):
        """One failure should transition to DEGRADED."""
        result = small_infra_service.record_health_check(
            "redis", healthy=False, message="Connection refused"
        )
        assert result.status == ServiceStatus.DEGRADED
        assert result.health_check.consecutive_failures == 1

    def test_degraded_after_two_failures(self, small_infra_service: InfrastructureService):
        """Two consecutive failures should remain DEGRADED."""
        small_infra_service.record_health_check("redis", healthy=False)
        result = small_infra_service.record_health_check("redis", healthy=False)
        assert result.status == ServiceStatus.DEGRADED
        assert result.health_check.consecutive_failures == 2

    def test_unhealthy_after_three_failures(self, small_infra_service: InfrastructureService):
        """Three consecutive failures should transition to UNHEALTHY."""
        small_infra_service.record_health_check("redis", healthy=False)
        small_infra_service.record_health_check("redis", healthy=False)
        result = small_infra_service.record_health_check("redis", healthy=False)
        assert result.status == ServiceStatus.UNHEALTHY
        assert result.health_check.consecutive_failures == 3

    def test_recovery_from_unhealthy(self, small_infra_service: InfrastructureService):
        """A successful check after failures should reset to HEALTHY."""
        for _ in range(4):
            small_infra_service.record_health_check("redis", healthy=False)
        result = small_infra_service.record_health_check("redis", healthy=True)
        assert result.status == ServiceStatus.HEALTHY
        assert result.health_check.consecutive_failures == 0

    def test_unknown_service_raises(self, small_infra_service: InfrastructureService):
        """Recording health for unknown service should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown service"):
            small_infra_service.record_health_check("nonexistent", healthy=True)

    def test_get_unknown_service_raises(self, small_infra_service: InfrastructureService):
        """Getting health for unknown service should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown service"):
            small_infra_service.get_service_health("nonexistent")

    def test_all_health_aggregation(self, small_infra_service: InfrastructureService):
        """All health should aggregate correctly."""
        small_infra_service.record_health_check("postgres", healthy=True)
        small_infra_service.record_health_check("redis", healthy=True)
        small_infra_service.record_health_check("backend", healthy=True)

        all_health = small_infra_service.get_all_health()
        assert all_health.overall_status == ServiceStatus.HEALTHY
        assert all_health.healthy_count == 3
        assert all_health.degraded_count == 0
        assert all_health.unhealthy_count == 0

    def test_all_health_worst_case_degraded(self, small_infra_service: InfrastructureService):
        """Overall status should be worst-case (degraded)."""
        small_infra_service.record_health_check("postgres", healthy=True)
        small_infra_service.record_health_check("redis", healthy=False)
        small_infra_service.record_health_check("backend", healthy=True)

        all_health = small_infra_service.get_all_health()
        assert all_health.overall_status == ServiceStatus.DEGRADED

    def test_all_health_worst_case_unhealthy(self, small_infra_service: InfrastructureService):
        """Overall status should be worst-case (unhealthy)."""
        small_infra_service.record_health_check("postgres", healthy=True)
        for _ in range(3):
            small_infra_service.record_health_check("redis", healthy=False)
        all_health = small_infra_service.get_all_health()
        assert all_health.overall_status == ServiceStatus.UNHEALTHY

    def test_health_check_message_preserved(self, small_infra_service: InfrastructureService):
        """Health check message should be preserved."""
        result = small_infra_service.record_health_check(
            "postgres", healthy=False, message="Connection timeout after 10s"
        )
        assert result.health_check.message == "Connection timeout after 10s"


# ===========================================================================
# 2. Dependency Graph Tests
# ===========================================================================


class TestDependencyGraph:
    """Tests for service dependency graph analysis."""

    def test_dependency_graph_services(self, small_infra_service: InfrastructureService):
        """Graph should include all services."""
        graph = small_infra_service.get_dependency_graph()
        assert set(graph.services) == {"postgres", "redis", "backend"}

    def test_dependency_graph_edges(self, small_infra_service: InfrastructureService):
        """Graph should include correct dependency edges."""
        graph = small_infra_service.get_dependency_graph()
        assert len(graph.dependencies) == 2
        sources = {d.source for d in graph.dependencies}
        targets = {d.target for d in graph.dependencies}
        assert "backend" in sources
        assert "postgres" in targets
        assert "redis" in targets

    def test_startup_order_deps_first(self, small_infra_service: InfrastructureService):
        """Startup order should have dependencies before dependents."""
        graph = small_infra_service.get_dependency_graph()
        order = graph.startup_order
        # postgres and redis should appear before backend
        postgres_idx = order.index("postgres")
        redis_idx = order.index("redis")
        backend_idx = order.index("backend")
        assert postgres_idx < backend_idx
        assert redis_idx < backend_idx

    def test_no_circular_dependencies_default(self, small_infra_service: InfrastructureService):
        """Default config should have no circular dependencies."""
        graph = small_infra_service.get_dependency_graph()
        assert graph.has_circular_dependencies is False
        assert graph.circular_chains == []

    def test_circular_dependency_detection(self):
        """Should detect circular dependencies."""
        services = {
            "a": {"version": "1", "port": 1, "required_env": [], "resource_limits": {}},
            "b": {"version": "1", "port": 2, "required_env": [], "resource_limits": {}},
            "c": {"version": "1", "port": 3, "required_env": [], "resource_limits": {}},
        }
        deps = [
            {"source": "a", "target": "b", "type": "required"},
            {"source": "b", "target": "c", "type": "required"},
            {"source": "c", "target": "a", "type": "required"},
        ]
        svc = InfrastructureService(services=services, dependencies=deps)
        graph = svc.get_dependency_graph()
        assert graph.has_circular_dependencies is True
        assert len(graph.circular_chains) > 0

    def test_full_dependency_graph(self, infra_service: InfrastructureService):
        """Full service should have all default dependencies."""
        graph = infra_service.get_dependency_graph()
        assert len(graph.services) == 9
        assert len(graph.dependencies) > 0
        assert graph.has_circular_dependencies is False


# ===========================================================================
# 3. Configuration Validation Tests
# ===========================================================================


class TestConfigurationValidation:
    """Tests for configuration validation."""

    def test_valid_configuration(self, small_infra_service: InfrastructureService):
        """Should pass with all required env vars provided."""
        env_vars = {
            "postgres": {"POSTGRES_PASSWORD": "secret123"},
            "backend": {"DATABASE_URL": "postgresql://...", "API_KEY": "key123"},
        }
        result = small_infra_service.validate_configuration(env_vars=env_vars)
        assert result.valid is True
        assert len(result.issues) == 0

    def test_missing_env_vars(self, small_infra_service: InfrastructureService):
        """Should fail when required env vars are missing."""
        env_vars = {
            "postgres": {},
            "backend": {"DATABASE_URL": "postgresql://..."},
        }
        result = small_infra_service.validate_configuration(env_vars=env_vars)
        assert result.valid is False
        missing = [i for i in result.issues if i.category == "env_vars"]
        assert len(missing) >= 2  # POSTGRES_PASSWORD + API_KEY

    def test_port_conflict_detection(self, small_infra_service: InfrastructureService):
        """Should detect port conflicts between services."""
        env_vars = {
            "postgres": {"POSTGRES_PASSWORD": "x"},
            "backend": {"DATABASE_URL": "x", "API_KEY": "x"},
        }
        port_bindings = {
            "postgres": 5432,
            "backend": 5432,  # conflict!
        }
        result = small_infra_service.validate_configuration(
            env_vars=env_vars, port_bindings=port_bindings
        )
        assert result.valid is False
        port_issues = [i for i in result.issues if i.category == "ports"]
        assert len(port_issues) == 1
        assert "5432" in port_issues[0].message

    def test_no_port_conflicts(self, small_infra_service: InfrastructureService):
        """Should pass with no port conflicts."""
        env_vars = {
            "postgres": {"POSTGRES_PASSWORD": "x"},
            "backend": {"DATABASE_URL": "x", "API_KEY": "x"},
        }
        port_bindings = {"postgres": 5432, "redis": 6379, "backend": 8000}
        result = small_infra_service.validate_configuration(
            env_vars=env_vars, port_bindings=port_bindings
        )
        assert result.valid is True

    def test_empty_env_var_value_counts_as_missing(self, small_infra_service: InfrastructureService):
        """Empty string values should count as missing."""
        env_vars = {
            "postgres": {"POSTGRES_PASSWORD": ""},
            "backend": {"DATABASE_URL": "x", "API_KEY": "x"},
        }
        result = small_infra_service.validate_configuration(env_vars=env_vars)
        assert result.valid is False


# ===========================================================================
# 4. Deployment Readiness Tests
# ===========================================================================


class TestDeploymentReadiness:
    """Tests for deployment readiness assessment."""

    def test_all_pass_readiness(self, small_infra_service: InfrastructureService):
        """Should be READY when all checks pass."""
        # Mark all services healthy
        for svc in ("postgres", "redis", "backend"):
            small_infra_service.record_health_check(svc, healthy=True)

        readiness = small_infra_service.check_deployment_readiness(
            migrations_applied=True,
            redis_connected=True,
            secrets_configured=True,
            tls_valid=True,
        )
        assert readiness.status == ReadinessStatus.READY
        assert readiness.failed_count == 0
        assert len(readiness.blocking_issues) == 0

    def test_not_ready_all_fail(self, small_infra_service: InfrastructureService):
        """Should be NOT_READY when all required checks fail."""
        # Make services unhealthy so all_services_healthy check also fails
        for svc in ("postgres", "redis", "backend"):
            for _ in range(3):
                small_infra_service.record_health_check(svc, healthy=False)

        readiness = small_infra_service.check_deployment_readiness(
            migrations_applied=False,
            redis_connected=False,
            secrets_configured=False,
            tls_valid=False,
        )
        assert readiness.status == ReadinessStatus.NOT_READY
        assert readiness.failed_count > 0
        assert len(readiness.blocking_issues) > 0

    def test_degraded_partial_failures(self, small_infra_service: InfrastructureService):
        """Should be DEGRADED with some required failures."""
        # Mark services as healthy
        for svc in ("postgres", "redis", "backend"):
            small_infra_service.record_health_check(svc, healthy=True)

        readiness = small_infra_service.check_deployment_readiness(
            migrations_applied=True,
            redis_connected=True,
            secrets_configured=False,  # This is required
            tls_valid=True,
        )
        assert readiness.status == ReadinessStatus.DEGRADED
        assert "secrets_configured" in readiness.blocking_issues

    def test_tls_optional(self, small_infra_service: InfrastructureService):
        """TLS check should be optional (not blocking)."""
        for svc in ("postgres", "redis", "backend"):
            small_infra_service.record_health_check(svc, healthy=True)

        readiness = small_infra_service.check_deployment_readiness(
            migrations_applied=True,
            redis_connected=True,
            secrets_configured=True,
            tls_valid=False,  # Optional, should not block
        )
        assert readiness.status == ReadinessStatus.READY
        assert "tls_certificates" not in readiness.blocking_issues

    def test_readiness_check_count(self, small_infra_service: InfrastructureService):
        """Should have exactly 5 checks."""
        readiness = small_infra_service.check_deployment_readiness()
        assert readiness.total_count == 5
        assert readiness.passed_count + readiness.failed_count == 5


# ===========================================================================
# 5. Compose Analysis Tests
# ===========================================================================


class TestComposeAnalysis:
    """Tests for Docker Compose file analysis."""

    def test_valid_compose_full_compliance(self, analyzer: ComposeAnalyzerService):
        """Fully compliant service should score 100."""
        compose_data = {"services": {"db": _valid_service_config()}}
        result = analyzer.analyze_dict(compose_data)
        assert result.services_analyzed == 1
        assert result.compliance.score == 100.0
        assert result.compliance.grade == "A"
        assert len(result.recommendations) == 0

    def test_minimal_compose_low_score(self, analyzer: ComposeAnalyzerService):
        """Minimal service should score low."""
        compose_data = {"services": {"app": _minimal_service_config()}}
        result = analyzer.analyze_dict(compose_data)
        assert result.compliance.score < 30.0
        assert result.compliance.grade in ("D", "F")
        assert len(result.recommendations) > 0

    def test_empty_compose(self, analyzer: ComposeAnalyzerService):
        """Empty compose should return zero score."""
        result = analyzer.analyze_dict({})
        assert result.services_analyzed == 0
        assert result.compliance.score == 0.0
        assert result.compliance.grade == "F"

    def test_multiple_services(self, analyzer: ComposeAnalyzerService):
        """Should analyze all services."""
        compose_data = {
            "services": {
                "db": _valid_service_config(),
                "app": _minimal_service_config(),
                "cache": _valid_service_config(),
            }
        }
        result = analyzer.analyze_dict(compose_data)
        assert result.services_analyzed == 3


# ===========================================================================
# 6. Resource Limits Check Tests
# ===========================================================================


class TestResourceLimitsCheck:
    """Tests for resource limits detection in compose analysis."""

    def test_resource_limits_present(self, analyzer: ComposeAnalyzerService):
        """Should detect resource limits when present."""
        config = {
            "deploy": {
                "resources": {
                    "limits": {"cpus": "2", "memory": "4G"},
                }
            }
        }
        assert analyzer._check_resource_limits(config) is True

    def test_resource_limits_missing(self, analyzer: ComposeAnalyzerService):
        """Should detect missing resource limits."""
        config = {}
        assert analyzer._check_resource_limits(config) is False

    def test_resource_limits_partial(self, analyzer: ComposeAnalyzerService):
        """Should reject partial limits (only CPU, no memory)."""
        config = {
            "deploy": {
                "resources": {
                    "limits": {"cpus": "2"},
                }
            }
        }
        assert analyzer._check_resource_limits(config) is False


# ===========================================================================
# 7. Restart Policy Tests
# ===========================================================================


class TestRestartPolicy:
    """Tests for restart policy validation."""

    def test_unless_stopped(self, analyzer: ComposeAnalyzerService):
        """Should accept 'unless-stopped'."""
        assert analyzer._check_restart_policy({"restart": "unless-stopped"}) is True

    def test_always(self, analyzer: ComposeAnalyzerService):
        """Should accept 'always'."""
        assert analyzer._check_restart_policy({"restart": "always"}) is True

    def test_on_failure(self, analyzer: ComposeAnalyzerService):
        """Should accept 'on-failure'."""
        assert analyzer._check_restart_policy({"restart": "on-failure"}) is True

    def test_no_restart(self, analyzer: ComposeAnalyzerService):
        """Should reject missing restart policy."""
        assert analyzer._check_restart_policy({}) is False

    def test_deploy_restart_policy(self, analyzer: ComposeAnalyzerService):
        """Should accept deploy-level restart policy."""
        config = {
            "deploy": {
                "restart_policy": {"condition": "on-failure"}
            }
        }
        assert analyzer._check_restart_policy(config) is True


# ===========================================================================
# 8. Health Check Tests
# ===========================================================================


class TestHealthCheckPresence:
    """Tests for health check presence detection."""

    def test_healthcheck_present(self, analyzer: ComposeAnalyzerService):
        """Should detect healthcheck when present."""
        config = {
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "http://localhost/health"],
                "interval": "30s",
            }
        }
        assert analyzer._check_health_check(config) is True

    def test_healthcheck_missing(self, analyzer: ComposeAnalyzerService):
        """Should detect missing healthcheck."""
        assert analyzer._check_health_check({}) is False

    def test_healthcheck_empty(self, analyzer: ComposeAnalyzerService):
        """Should reject empty healthcheck."""
        assert analyzer._check_health_check({"healthcheck": {}}) is False


# ===========================================================================
# 9. Logging Configuration Tests
# ===========================================================================


class TestLoggingConfig:
    """Tests for logging configuration validation."""

    def test_valid_logging(self, analyzer: ComposeAnalyzerService):
        """Should accept json-file driver with limits."""
        config = {
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "100m", "max-file": "5"},
            }
        }
        assert analyzer._check_logging_config(config) is True

    def test_missing_logging(self, analyzer: ComposeAnalyzerService):
        """Should reject missing logging config."""
        assert analyzer._check_logging_config({}) is False

    def test_wrong_driver(self, analyzer: ComposeAnalyzerService):
        """Should reject non-json-file driver."""
        config = {"logging": {"driver": "syslog"}}
        assert analyzer._check_logging_config(config) is False

    def test_missing_rotation_limits(self, analyzer: ComposeAnalyzerService):
        """Should reject json-file without rotation limits."""
        config = {"logging": {"driver": "json-file", "options": {}}}
        assert analyzer._check_logging_config(config) is False


# ===========================================================================
# 10. Security Directive Tests
# ===========================================================================


class TestSecurityDirectives:
    """Tests for security directive validation."""

    def test_no_new_privileges(self, analyzer: ComposeAnalyzerService):
        """Should accept no-new-privileges."""
        config = {"security_opt": ["no-new-privileges:true"]}
        assert analyzer._check_security_directives(config) is True

    def test_cap_drop_all(self, analyzer: ComposeAnalyzerService):
        """Should accept cap_drop ALL."""
        config = {"cap_drop": ["ALL"]}
        assert analyzer._check_security_directives(config) is True

    def test_no_security(self, analyzer: ComposeAnalyzerService):
        """Should reject no security directives."""
        assert analyzer._check_security_directives({}) is False


# ===========================================================================
# 11. Image Pinning Tests
# ===========================================================================


class TestImagePinning:
    """Tests for image pinning validation."""

    def test_pinned_image(self, analyzer: ComposeAnalyzerService):
        """Should accept pinned image."""
        assert analyzer._check_image_pinning({"image": "postgres:16-alpine"}) is True

    def test_latest_tag(self, analyzer: ComposeAnalyzerService):
        """Should reject :latest tag."""
        assert analyzer._check_image_pinning({"image": "postgres:latest"}) is False

    def test_no_tag(self, analyzer: ComposeAnalyzerService):
        """Should reject image with no tag (defaults to :latest)."""
        assert analyzer._check_image_pinning({"image": "postgres"}) is False

    def test_build_context(self, analyzer: ComposeAnalyzerService):
        """Should accept build context (no image tag)."""
        config = {"build": {"context": "./backend", "dockerfile": "Dockerfile.prod"}}
        assert analyzer._check_image_pinning(config) is True


# ===========================================================================
# 12. Compliance Score Calculation Tests
# ===========================================================================


class TestComplianceScore:
    """Tests for compliance score calculation."""

    def test_perfect_score(self, analyzer: ComposeAnalyzerService):
        """Fully compliant service should get 100 score."""
        analyses = [
            ComposeServiceAnalysis(
                service="db",
                has_resource_limits=True,
                has_restart_policy=True,
                has_health_check=True,
                has_logging_config=True,
                has_security_directives=True,
                has_network_isolation=True,
                has_host_volume_mounts=False,
                uses_env_secrets=True,
                image_pinned=True,
            )
        ]
        score = analyzer._calculate_compliance(analyses)
        assert score.score == 100.0
        assert score.grade == "A"

    def test_zero_score(self, analyzer: ComposeAnalyzerService):
        """Fully non-compliant service should get 0 score."""
        analyses = [
            ComposeServiceAnalysis(
                service="bad",
                has_resource_limits=False,
                has_restart_policy=False,
                has_health_check=False,
                has_logging_config=False,
                has_security_directives=False,
                has_network_isolation=False,
                has_host_volume_mounts=True,
                uses_env_secrets=False,
                image_pinned=False,
            )
        ]
        score = analyzer._calculate_compliance(analyses)
        assert score.score == 0.0
        assert score.grade == "F"

    def test_empty_analyses(self, analyzer: ComposeAnalyzerService):
        """Empty analyses should return zero score."""
        score = analyzer._calculate_compliance([])
        assert score.score == 0.0
        assert score.grade == "F"

    def test_mixed_score(self, analyzer: ComposeAnalyzerService):
        """Mixed compliance should produce intermediate score."""
        analyses = [
            ComposeServiceAnalysis(
                service="good",
                has_resource_limits=True,
                has_restart_policy=True,
                has_health_check=True,
                has_logging_config=True,
                has_security_directives=True,
                has_network_isolation=True,
                has_host_volume_mounts=False,
                uses_env_secrets=True,
                image_pinned=True,
            ),
            ComposeServiceAnalysis(
                service="bad",
                has_resource_limits=False,
                has_restart_policy=False,
                has_health_check=False,
                has_logging_config=False,
                has_security_directives=False,
                has_network_isolation=True,
                has_host_volume_mounts=False,
                uses_env_secrets=True,
                image_pinned=True,
            ),
        ]
        score = analyzer._calculate_compliance(analyses)
        assert 40.0 < score.score < 80.0
        assert score.grade in ("C", "D")


# ===========================================================================
# 13. Resource Utilization Tests
# ===========================================================================


class TestResourceUtilization:
    """Tests for resource utilization tracking."""

    def test_resource_utilization_all_services(self, small_infra_service: InfrastructureService):
        """Should return utilization for all services."""
        util = small_infra_service.get_resource_utilization()
        assert len(util.services) == 3
        assert util.total_cpu_percent > 0
        assert util.total_memory_mb > 0

    def test_connection_pools_included(self, infra_service: InfrastructureService):
        """Should include connection pool stats."""
        util = infra_service.get_resource_utilization()
        assert len(util.connection_pools) > 0
        pool_services = {p.service for p in util.connection_pools}
        assert "postgres" in pool_services
        assert "redis" in pool_services

    def test_memory_parse_gigabytes(self):
        """Should parse memory in gigabytes."""
        assert InfrastructureService._parse_memory_mb("4G") == 4096.0

    def test_memory_parse_megabytes(self):
        """Should parse memory in megabytes."""
        assert InfrastructureService._parse_memory_mb("512M") == 512.0

    def test_memory_parse_kilobytes(self):
        """Should parse memory in kilobytes."""
        assert InfrastructureService._parse_memory_mb("1024K") == 1.0


# ===========================================================================
# 14. Recommendations Tests
# ===========================================================================


class TestRecommendations:
    """Tests for infrastructure recommendations."""

    def test_recommendations_always_present(self, small_infra_service: InfrastructureService):
        """Should always return some standard recommendations."""
        recs = small_infra_service.get_recommendations()
        assert len(recs) >= 4  # At least the standard recs
        categories = {r.category for r in recs}
        assert "monitoring" in categories
        assert "backup" in categories
        assert "security" in categories

    def test_unhealthy_generates_recommendation(self, small_infra_service: InfrastructureService):
        """Should recommend fixing unhealthy services."""
        for _ in range(3):
            small_infra_service.record_health_check("redis", healthy=False)
        recs = small_infra_service.get_recommendations()
        health_recs = [r for r in recs if r.category == "health"]
        assert len(health_recs) >= 1


# ===========================================================================
# 15. Host Volume Mount Tests
# ===========================================================================


class TestHostVolumeMounts:
    """Tests for host volume mount detection."""

    def test_no_volumes(self, analyzer: ComposeAnalyzerService):
        """Should return False when no volumes."""
        assert analyzer._check_host_volume_mounts({}) is False

    def test_empty_volumes(self, analyzer: ComposeAnalyzerService):
        """Should return False for empty volumes list."""
        assert analyzer._check_host_volume_mounts({"volumes": []}) is False

    def test_host_bind_mount(self, analyzer: ComposeAnalyzerService):
        """Should detect host bind mounts."""
        config = {"volumes": ["./data:/var/lib/data"]}
        assert analyzer._check_host_volume_mounts(config) is True

    def test_named_volume(self, analyzer: ComposeAnalyzerService):
        """Should not flag named volumes."""
        config = {"volumes": ["pgdata:/var/lib/postgresql/data"]}
        assert analyzer._check_host_volume_mounts(config) is False

    def test_absolute_host_path(self, analyzer: ComposeAnalyzerService):
        """Should detect absolute host path mounts."""
        config = {"volumes": ["/host/path:/container/path"]}
        assert analyzer._check_host_volume_mounts(config) is True


# ===========================================================================
# 16. Environment Secrets Tests
# ===========================================================================


class TestEnvSecrets:
    """Tests for environment variable secret handling."""

    def test_env_substitution_safe(self, analyzer: ComposeAnalyzerService):
        """Should accept env var substitution for secrets."""
        config = {
            "environment": {
                "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD:?required}",
            }
        }
        assert analyzer._check_env_secrets(config) is True

    def test_hardcoded_password(self, analyzer: ComposeAnalyzerService):
        """Should reject hardcoded passwords."""
        config = {
            "environment": {
                "POSTGRES_PASSWORD": "mysecret123",
            }
        }
        assert analyzer._check_env_secrets(config) is False

    def test_no_sensitive_keys(self, analyzer: ComposeAnalyzerService):
        """Should accept env vars without sensitive keys."""
        config = {
            "environment": {
                "NODE_ENV": "production",
                "PORT": "3000",
            }
        }
        assert analyzer._check_env_secrets(config) is True

    def test_list_form_env(self, analyzer: ComposeAnalyzerService):
        """Should handle list-form environment variables."""
        config = {
            "environment": ["DB_PASSWORD=hardcoded"]
        }
        assert analyzer._check_env_secrets(config) is False


# ===========================================================================
# 17. Network Isolation Tests
# ===========================================================================


class TestNetworkIsolation:
    """Tests for network isolation checks."""

    def test_default_network(self, analyzer: ComposeAnalyzerService):
        """Should accept default bridge network."""
        assert analyzer._check_network_isolation({}) is True

    def test_host_network(self, analyzer: ComposeAnalyzerService):
        """Should reject host network mode."""
        config = {"network_mode": "host"}
        assert analyzer._check_network_isolation(config) is False


# ===========================================================================
# 18. Singleton Tests
# ===========================================================================


class TestSingletons:
    """Tests for singleton management."""

    def test_infrastructure_singleton(self):
        """Should return same instance."""
        svc1 = get_infrastructure_service()
        svc2 = get_infrastructure_service()
        assert svc1 is svc2

    def test_infrastructure_singleton_reset(self):
        """Should return new instance after reset."""
        svc1 = get_infrastructure_service()
        reset_infrastructure_service()
        svc2 = get_infrastructure_service()
        assert svc1 is not svc2

    def test_compose_analyzer_singleton(self):
        """Should return same instance."""
        a1 = get_compose_analyzer()
        a2 = get_compose_analyzer()
        assert a1 is a2

    def test_compose_analyzer_singleton_reset(self):
        """Should return new instance after reset."""
        a1 = get_compose_analyzer()
        reset_compose_analyzer()
        a2 = get_compose_analyzer()
        assert a1 is not a2


# ===========================================================================
# 19. Stats Tests
# ===========================================================================


class TestStats:
    """Tests for service stats."""

    def test_infra_stats(self, small_infra_service: InfrastructureService):
        """Should return stats dict."""
        stats = small_infra_service.get_stats()
        assert stats["total_services"] == 3
        assert "healthy" in stats
        assert "degraded" in stats
        assert "unhealthy" in stats

    def test_analyzer_stats(self, analyzer: ComposeAnalyzerService):
        """Should return stats dict."""
        stats = analyzer.get_stats()
        assert stats["status"] == "loaded"


# ===========================================================================
# 20. API Endpoint Tests
# ===========================================================================


@pytest.mark.asyncio
class TestInfrastructureAPI:
    """Tests for infrastructure API endpoints."""

    async def test_get_all_health(self):
        """GET /infrastructure/health should return all service health."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "services" in data
            assert "overall_status" in data

    async def test_get_service_health(self):
        """GET /infrastructure/health/postgres should return single service."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/health/postgres")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "postgres"

    async def test_get_service_health_404(self):
        """GET /infrastructure/health/nonexistent should return 404."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/health/nonexistent")
            assert resp.status_code == 404

    async def test_get_resources(self):
        """GET /infrastructure/resources should return resource utilization."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/resources")
            assert resp.status_code == 200
            data = resp.json()
            assert "services" in data
            assert "connection_pools" in data

    async def test_get_readiness(self):
        """GET /infrastructure/readiness should return readiness status."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/readiness")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "checks" in data

    async def test_get_dependencies(self):
        """GET /infrastructure/dependencies should return dependency graph."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/dependencies")
            assert resp.status_code == 200
            data = resp.json()
            assert "services" in data
            assert "dependencies" in data
            assert "startup_order" in data

    async def test_get_recommendations(self):
        """GET /infrastructure/recommendations should return recommendations."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/infrastructure/recommendations")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0

    async def test_validate_compose_endpoint(self):
        """POST /infrastructure/validate-compose should analyze compose data."""
        from app.main import app

        compose_data = {"services": {"db": _valid_service_config()}}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/infrastructure/validate-compose",
                json=compose_data,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["services_analyzed"] == 1
            assert "compliance" in data
