"""Tests for transport encryption configuration and production validators.

Tests SSL/TLS settings for PostgreSQL, Redis, and Neo4j, plus
production environment validation gates.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestTransportEncryptionSettings:
    """Tests for transport encryption configuration fields."""

    def test_default_ssl_mode_is_prefer(self) -> None:
        """Test that default database SSL mode is 'prefer'."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost/test",
        )
        assert s.database_ssl_mode == "prefer"

    def test_default_neo4j_encrypted_is_false(self) -> None:
        """Test that default neo4j_encrypted is False."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost/test",
        )
        assert s.neo4j_encrypted is False

    def test_ssl_ca_cert_defaults_to_none(self) -> None:
        """Test that SSL CA cert paths default to None."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost/test",
        )
        assert s.database_ssl_ca_cert is None
        assert s.redis_ssl_ca_cert is None


class TestProductionTransportValidation:
    """Tests for production transport encryption validators."""

    def _make_production_settings(self, **overrides) -> dict:
        """Build kwargs for a production Settings instance."""
        defaults = {
            "_env_file": None,
            "environment": "production",
            "auth_enabled": True,
            "jwt_secret_key": "super-secret-jwt-key-32chars!!",
            "api_key": "prod-api-key-12345",
            "metriport_webhook_key": "webhook-key-prod",
            "database_url": "postgresql+asyncpg://prod-host/db",
            "redis_url": "rediss://prod-redis:6380",
            "database_ssl_mode": "require",
            "neo4j_encrypted": True,
            "phi_encryption_key": "test-phi-encryption-key-for-testing",
        }
        defaults.update(overrides)
        return defaults

    def test_production_rejects_ssl_mode_disable(self) -> None:
        """Test that production rejects database_ssl_mode=disable."""
        from app.core.config import Settings

        with pytest.raises(ValueError, match="DATABASE_SSL_MODE"):
            Settings(**self._make_production_settings(database_ssl_mode="disable"))

    def test_production_rejects_ssl_mode_prefer(self) -> None:
        """Test that production rejects database_ssl_mode=prefer."""
        from app.core.config import Settings

        with pytest.raises(ValueError, match="DATABASE_SSL_MODE"):
            Settings(**self._make_production_settings(database_ssl_mode="prefer"))

    def test_production_accepts_ssl_mode_require(self) -> None:
        """Test that production accepts database_ssl_mode=require."""
        from app.core.config import Settings

        s = Settings(**self._make_production_settings(database_ssl_mode="require"))
        assert s.database_ssl_mode == "require"

    def test_production_accepts_ssl_mode_verify_full(self) -> None:
        """Test that production accepts database_ssl_mode=verify-full."""
        from app.core.config import Settings

        s = Settings(**self._make_production_settings(database_ssl_mode="verify-full"))
        assert s.database_ssl_mode == "verify-full"

    def test_production_rejects_redis_without_tls(self) -> None:
        """Test that production rejects redis:// (non-TLS) URLs."""
        from app.core.config import Settings

        with pytest.raises(ValueError, match="rediss://"):
            Settings(
                **self._make_production_settings(redis_url="redis://redis:6379")
            )

    def test_production_accepts_rediss_url(self) -> None:
        """Test that production accepts rediss:// URLs."""
        from app.core.config import Settings

        s = Settings(
            **self._make_production_settings(redis_url="rediss://redis:6380")
        )
        assert s.redis_url.startswith("rediss://")

    def test_production_rejects_neo4j_unencrypted(self) -> None:
        """Test that production rejects neo4j_encrypted=False."""
        from app.core.config import Settings

        with pytest.raises(ValueError, match="NEO4J_ENCRYPTED"):
            Settings(**self._make_production_settings(neo4j_encrypted=False))

    def test_production_accepts_neo4j_encrypted(self) -> None:
        """Test that production accepts neo4j_encrypted=True."""
        from app.core.config import Settings

        s = Settings(**self._make_production_settings(neo4j_encrypted=True))
        assert s.neo4j_encrypted is True

    def test_production_rejects_missing_phi_key(self) -> None:
        """Test that production rejects missing PHI encryption key."""
        from app.core.config import Settings

        with pytest.raises(ValueError, match="PHI_ENCRYPTION_KEY"):
            Settings(**self._make_production_settings(phi_encryption_key=None))

    def test_dev_allows_insecure_transport(self) -> None:
        """Test that development allows insecure transport settings."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            environment="development",
            database_ssl_mode="disable",
            neo4j_encrypted=False,
            redis_url="redis://localhost:6379",
        )
        assert s.database_ssl_mode == "disable"
        assert s.neo4j_encrypted is False


class TestStartupValidatorPHIKey:
    """Tests for PHI encryption key in startup validator."""

    def test_production_errors_on_missing_phi_key(self) -> None:
        """Test that startup validator errors on missing PHI key in production."""
        from app.core.config import Settings
        from app.core.startup_validator import validate_production_credentials

        # Create a settings object that bypasses model_validator for testing
        config = Settings(
            _env_file=None,
            environment="development",
            auth_enabled=True,
            jwt_secret_key="test-jwt-secret-key-32chars!!!",
            api_key="test-api-key-12345",
            phi_encryption_key=None,
        )
        # Manually set environment for validator
        object.__setattr__(config, "environment", "production")

        result = validate_production_credentials(config)
        phi_errors = [e for e in result.errors if "PHI_ENCRYPTION_KEY" in e]
        assert len(phi_errors) > 0

    def test_dev_does_not_error_on_missing_phi_key(self) -> None:
        """Test that dev mode does not error on missing PHI key."""
        from app.core.config import Settings
        from app.core.startup_validator import validate_production_credentials

        config = Settings(
            _env_file=None,
            environment="development",
            phi_encryption_key=None,
        )

        result = validate_production_credentials(config)
        phi_errors = [e for e in result.errors if "PHI_ENCRYPTION_KEY" in e]
        assert len(phi_errors) == 0
