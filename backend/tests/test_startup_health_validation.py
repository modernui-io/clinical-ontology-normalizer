"""Tests for P1-020 (startup credential validation) and P1-021 (dependency classification).

Covers:
- Missing credentials in production mode blocks startup
- Missing credentials in dev mode only warns
- Placeholder/default credentials detected
- Critical dependency down -> not ready
- Non-critical dependency down -> ready but degraded
- All dependencies up -> fully ready
"""

from __future__ import annotations

import pytest

from app.core.dependency_classifier import (
    ClassifiedHealthResult,
    DependencyClass,
    classify_health_results,
    get_all_dependency_classes,
    get_dependency_class,
)
from app.core.startup_validator import (
    StartupValidationResult,
    _is_placeholder,
    validate_production_credentials,
    run_startup_validation,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_settings(**overrides):
    """Create a Settings-like object with sensible test defaults.

    Uses a SimpleNamespace so we don't trigger pydantic validators
    that would raise on incomplete production configs.
    """
    from types import SimpleNamespace

    defaults = {
        "environment": "development",
        "database_url": "postgresql+asyncpg://postgres@localhost:5432/test",
        "redis_url": "redis://localhost:6379/0",
        "auth_enabled": False,
        "jwt_secret_key": None,
        "api_key": None,
        "neo4j_password": None,
        "llm_provider": "openai",
        "openai_api_key": None,
        "anthropic_api_key": None,
        "etl_encryption_key": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# =============================================================================
# P1-020: Startup credential validation
# =============================================================================


class TestPlaceholderDetection:
    """_is_placeholder catches common dummy values."""

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "changeme",
            "CHANGEME",
            "secret",
            "password",
            "your-api-key-here",
            "replace-this",
            "TODO",
            "placeholder-value",
            "example-key",
            "change-this-in-production-use-env-var",
            "dev-api-key-change-in-production",
        ],
    )
    def test_detects_placeholders(self, value: str | None):
        assert _is_placeholder(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "a8f3b2c1d4e5f6a7b8c9d0e1f2a3b4c5",
            "sk-realkey1234567890abcdef",
            "my-production-jwt-secret-k3y!@#",
        ],
    )
    def test_accepts_real_credentials(self, value: str):
        assert _is_placeholder(value) is False


class TestValidateProductionCredentials:
    """validate_production_credentials checks all required creds."""

    def test_dev_mode_no_errors_with_defaults(self):
        """Development mode with all defaults should have zero errors."""
        config = _make_settings(environment="development")
        result = validate_production_credentials(config)
        # Dev mode should not produce errors (only warnings)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_production_missing_database_url(self):
        """Production with empty DATABASE_URL is an error."""
        config = _make_settings(
            environment="production",
            database_url="",
            auth_enabled=True,
            jwt_secret_key="real-secret-key-123",
            api_key="real-api-key-456",
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("DATABASE_URL" in e for e in result.errors)

    def test_production_localhost_database_url(self):
        """Production pointing to localhost is an error."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://postgres@localhost:5432/prod",
            auth_enabled=True,
            jwt_secret_key="real-secret-key-123",
            api_key="real-api-key-456",
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("localhost" in e for e in result.errors)

    def test_production_missing_jwt_secret(self):
        """Production without JWT_SECRET_KEY is an error."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@db.prod:5432/prod",
            auth_enabled=True,
            jwt_secret_key=None,
            api_key="real-api-key-456",
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("JWT_SECRET_KEY" in e for e in result.errors)

    def test_production_placeholder_jwt_secret(self):
        """Production with placeholder JWT_SECRET_KEY is an error."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@db.prod:5432/prod",
            auth_enabled=True,
            jwt_secret_key="changeme",
            api_key="real-api-key-456",
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("JWT_SECRET_KEY" in e for e in result.errors)

    def test_production_missing_api_key(self):
        """Production without API_KEY is an error."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@db.prod:5432/prod",
            auth_enabled=True,
            jwt_secret_key="real-secret-key-123",
            api_key=None,
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("API_KEY" in e for e in result.errors)

    def test_production_valid_credentials(self):
        """Production with all real credentials should pass."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@db.prod.internal:5432/prod",
            redis_url="redis://redis.prod.internal:6379/0",
            auth_enabled=True,
            jwt_secret_key="a8f3b2c1d4e5f6a7b8c9d0e1f2a3b4c5",
            api_key="sk-prod-key-1234567890abcdef",
            neo4j_password="neo4j-prod-pass-xyz",
            llm_provider="openai",
            openai_api_key="sk-realkey1234567890abcdef",
            etl_encryption_key="etl-enc-key-abcdef123456",
        )
        result = validate_production_credentials(config)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_staging_treated_as_strict(self):
        """Staging should enforce the same rules as production."""
        config = _make_settings(
            environment="staging",
            database_url="postgresql+asyncpg://postgres@localhost:5432/staging",
            auth_enabled=True,
            jwt_secret_key="real-secret-key-123",
            api_key="real-api-key-456",
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("localhost" in e for e in result.errors)

    def test_dev_mode_warns_but_valid(self):
        """Development mode should produce warnings but remain valid."""
        config = _make_settings(
            environment="development",
            jwt_secret_key=None,
            api_key=None,
            neo4j_password=None,
        )
        result = validate_production_credentials(config)
        assert result.valid is True
        # Should have at least the neo4j warning
        assert len(result.warnings) > 0

    def test_production_missing_openai_key(self):
        """Production with openai provider but no key is an error."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@db.prod:5432/prod",
            auth_enabled=True,
            jwt_secret_key="real-secret-key-123",
            api_key="real-api-key-456",
            llm_provider="openai",
            openai_api_key=None,
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("OPENAI_API_KEY" in e for e in result.errors)

    def test_production_missing_anthropic_key(self):
        """Production with anthropic provider but no key is an error."""
        config = _make_settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@db.prod:5432/prod",
            auth_enabled=True,
            jwt_secret_key="real-secret-key-123",
            api_key="real-api-key-456",
            llm_provider="anthropic",
            anthropic_api_key=None,
        )
        result = validate_production_credentials(config)
        assert result.valid is False
        assert any("ANTHROPIC_API_KEY" in e for e in result.errors)


class TestRunStartupValidation:
    """run_startup_validation raises in production, warns in dev."""

    def test_dev_mode_does_not_raise(self):
        """Dev mode with missing creds logs warnings but does not raise."""
        config = _make_settings(environment="development")
        result = run_startup_validation(config)
        assert result.valid is True

    def test_production_raises_on_errors(self):
        """Production with missing creds raises RuntimeError."""
        config = _make_settings(
            environment="production",
            database_url="",
            auth_enabled=True,
            jwt_secret_key=None,
            api_key=None,
        )
        with pytest.raises(RuntimeError, match="Startup blocked"):
            run_startup_validation(config)

    def test_staging_raises_on_errors(self):
        """Staging with missing creds raises RuntimeError."""
        config = _make_settings(
            environment="staging",
            database_url="postgresql+asyncpg://postgres@localhost:5432/staging",
            auth_enabled=True,
            jwt_secret_key="real-key",
            api_key="real-key",
        )
        with pytest.raises(RuntimeError, match="Startup blocked"):
            run_startup_validation(config)


# =============================================================================
# P1-021: Dependency classification
# =============================================================================


class TestDependencyClassLookup:
    """get_dependency_class returns correct tiers."""

    def test_database_is_critical(self):
        assert get_dependency_class("database") == DependencyClass.CRITICAL

    def test_redis_is_critical(self):
        assert get_dependency_class("redis") == DependencyClass.CRITICAL

    def test_neo4j_is_non_critical(self):
        assert get_dependency_class("neo4j") == DependencyClass.NON_CRITICAL

    def test_kafka_is_non_critical(self):
        assert get_dependency_class("kafka") == DependencyClass.NON_CRITICAL

    def test_unknown_defaults_to_non_critical(self):
        assert get_dependency_class("some_future_service") == DependencyClass.NON_CRITICAL


class TestGetAllDependencyClasses:
    """get_all_dependency_classes returns a complete map."""

    def test_returns_all_registered(self):
        classes = get_all_dependency_classes()
        assert "database" in classes
        assert "redis" in classes
        assert "neo4j" in classes
        assert "kafka" in classes
        assert classes["database"] == "critical"
        assert classes["neo4j"] == "non_critical"


class TestClassifyHealthResults:
    """classify_health_results produces correct readiness decisions."""

    def test_all_up_is_ready(self):
        """All dependencies up -> ready, not degraded."""
        result = classify_health_results({
            "database": True,
            "redis": True,
            "neo4j": True,
            "kafka": True,
        })
        assert result.ready is True
        assert result.degraded is False
        assert result.critical_down == []
        assert result.non_critical_down == []

    def test_critical_down_not_ready(self):
        """Database down -> not ready."""
        result = classify_health_results({
            "database": False,
            "redis": True,
            "neo4j": True,
            "kafka": True,
        })
        assert result.ready is False
        assert "database" in result.critical_down

    def test_non_critical_down_ready_but_degraded(self):
        """Neo4j down, all critical up -> ready + degraded."""
        result = classify_health_results({
            "database": True,
            "redis": True,
            "neo4j": False,
            "kafka": True,
        })
        assert result.ready is True
        assert result.degraded is True
        assert "neo4j" in result.non_critical_down

    def test_multiple_non_critical_down(self):
        """Both neo4j and kafka down -> ready + degraded."""
        result = classify_health_results({
            "database": True,
            "redis": True,
            "neo4j": False,
            "kafka": False,
        })
        assert result.ready is True
        assert result.degraded is True
        assert set(result.non_critical_down) == {"neo4j", "kafka"}

    def test_critical_and_non_critical_down(self):
        """Database + Neo4j down -> not ready."""
        result = classify_health_results({
            "database": False,
            "redis": True,
            "neo4j": False,
            "kafka": True,
        })
        assert result.ready is False
        assert "database" in result.critical_down
        assert "neo4j" in result.non_critical_down

    def test_required_services_promotes_to_critical(self):
        """A non-critical dep in required_services becomes critical."""
        result = classify_health_results(
            {"database": True, "neo4j": False},
            required_services={"database", "neo4j"},
        )
        assert result.ready is False
        assert "neo4j" in result.critical_down
        assert result.dependency_classes["neo4j"] == "critical"

    def test_dependency_classes_in_result(self):
        """dependency_classes field is populated correctly."""
        result = classify_health_results({
            "database": True,
            "neo4j": True,
        })
        assert result.dependency_classes["database"] == "critical"
        assert result.dependency_classes["neo4j"] == "non_critical"

    def test_redis_critical_when_down(self):
        """Redis is critical by default; down -> not ready."""
        result = classify_health_results({
            "database": True,
            "redis": False,
        })
        assert result.ready is False
        assert "redis" in result.critical_down

    def test_empty_check_results(self):
        """No checks at all -> vacuously ready, not degraded."""
        result = classify_health_results({})
        assert result.ready is True
        assert result.degraded is False


class TestStartupValidationResult:
    """StartupValidationResult tracks errors and warnings."""

    def test_starts_valid(self):
        r = StartupValidationResult()
        assert r.valid is True
        assert r.errors == []
        assert r.warnings == []

    def test_add_error_invalidates(self):
        r = StartupValidationResult()
        r.add_error("missing DATABASE_URL")
        assert r.valid is False
        assert len(r.errors) == 1

    def test_add_warning_stays_valid(self):
        r = StartupValidationResult()
        r.add_warning("NEO4J_PASSWORD not set")
        assert r.valid is True
        assert len(r.warnings) == 1
