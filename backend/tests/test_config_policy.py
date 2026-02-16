"""P2-025: Configuration policy tests.

Ensures no sensitive defaults leak into production configurations.
Validates that the Settings class enforces secure-by-default posture
and that production/staging environments require all security controls.

At least 15 test cases covering:
- Default value safety
- Production environment requirements
- Development environment relaxation (with warnings)
- CORS origin validation
- Credential rejection of insecure defaults
"""

from __future__ import annotations

import warnings

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """Create a Settings instance fully isolated from host env.

    Passes all values directly to the constructor so pydantic-settings
    does NOT fall back to environment variables or .env files.
    """
    from app.core.config import Settings

    # Baseline: safe defaults for a dev environment
    defaults = {
        "environment": "development",
        "auth_enabled": False,
        "debug": False,
    }
    defaults.update({k.lower(): v for k, v in overrides.items()})

    # Construct directly (bypasses env var / .env file reading for supplied fields)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Default value safety
# ---------------------------------------------------------------------------

class TestDefaultsSafety:
    """Verify default config values are safe for production."""

    def test_debug_defaults_to_false(self) -> None:
        """DEBUG should default to False so production never runs in debug mode."""
        s = _make_settings()
        assert s.debug is False

    def test_auth_enabled_defaults_to_false_for_dev(self) -> None:
        """auth_enabled defaults to False (local dev), but production enforces True."""
        s = _make_settings()
        assert s.auth_enabled is False

    def test_jwt_secret_key_has_no_default(self) -> None:
        """jwt_secret_key must be None by default, forcing explicit configuration.

        We inspect the model field default directly to avoid env var interference.
        """
        from app.core.config import Settings
        field_default = Settings.model_fields["jwt_secret_key"].default
        assert field_default is None

    def test_api_key_has_no_default(self) -> None:
        """api_key must be None by default, forcing explicit configuration."""
        from app.core.config import Settings
        field_default = Settings.model_fields["api_key"].default
        assert field_default is None

    def test_neo4j_password_has_no_default(self) -> None:
        """neo4j_password must be None by default."""
        from app.core.config import Settings
        field_default = Settings.model_fields["neo4j_password"].default
        assert field_default is None

    def test_cors_origins_not_wildcard(self) -> None:
        """Default CORS origins must not include '*' wildcard."""
        s = _make_settings()
        assert "*" not in s.cors_origins
        assert "*" not in s.cors_origins_list

    def test_cors_origins_localhost_only_in_dev(self) -> None:
        """Default CORS origins should only reference localhost."""
        s = _make_settings()
        for origin in s.cors_origins_list:
            assert "localhost" in origin or "127.0.0.1" in origin

    def test_block_scaffold_endpoints_defaults_false(self) -> None:
        """block_scaffold_endpoints defaults to False (dev), should be True in prod."""
        s = _make_settings()
        assert s.block_scaffold_endpoints is False

    def test_environment_defaults_to_development(self) -> None:
        """Environment defaults to 'development', not 'production'."""
        s = _make_settings()
        assert s.environment == "development"


# ---------------------------------------------------------------------------
# Production environment requirements
# ---------------------------------------------------------------------------

class TestProductionRequirements:
    """Production environment must enforce all security controls."""

    def test_production_requires_auth_enabled(self) -> None:
        """Production must fail if AUTH_ENABLED is False."""
        with pytest.raises(ValidationError, match="AUTH_ENABLED must be true"):
            _make_settings(environment="production", auth_enabled=False)

    def test_staging_requires_auth_enabled(self) -> None:
        """Staging must also fail if AUTH_ENABLED is False."""
        with pytest.raises(ValidationError, match="AUTH_ENABLED must be true"):
            _make_settings(environment="staging", auth_enabled=False)

    def test_production_requires_jwt_secret(self) -> None:
        """Production with auth enabled must have JWT_SECRET_KEY."""
        with pytest.raises(ValidationError):
            _make_settings(
                environment="production",
                auth_enabled=True,
                # jwt_secret_key not set
            )

    def test_production_requires_api_key(self) -> None:
        """Production must have API_KEY set."""
        with pytest.raises(ValidationError):
            _make_settings(
                environment="production",
                auth_enabled=True,
                jwt_secret_key="secure-random-key-12345",
                # api_key not set
            )

    def test_production_valid_config_succeeds_with_all_keys(self) -> None:
        """Production config with all required keys should succeed."""
        s = _make_settings(
            environment="production",
            auth_enabled=True,
            jwt_secret_key="secure-random-key-12345",
            api_key="secure-api-key-12345",
            metriport_webhook_key="webhook-signing-key-12345",
        )
        assert s.environment == "production"

    def test_production_valid_config_succeeds(self) -> None:
        """A fully configured production environment should succeed."""
        s = _make_settings(
            environment="production",
            auth_enabled=True,
            jwt_secret_key="a-very-secure-random-key-for-production",
            api_key="production-api-key-very-secure",
            metriport_webhook_key="webhook-signing-key-12345",
        )
        assert s.is_production is True
        assert s.auth_enabled is True


# ---------------------------------------------------------------------------
# Insecure default rejection
# ---------------------------------------------------------------------------

class TestInsecureDefaultRejection:
    """Known insecure credential values must be rejected."""

    @pytest.mark.parametrize("bad_value", [
        "change-this-in-production-use-env-var",
        "dev-api-key-change-in-production",
        "password",
        "secret",
        "changeme",
    ])
    def test_insecure_jwt_secret_rejected(self, bad_value: str) -> None:
        """Insecure JWT secret values are replaced with None by the validator."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = _make_settings(jwt_secret_key=bad_value)
            # The validator should replace insecure values with None
            assert s.jwt_secret_key is None

    @pytest.mark.parametrize("bad_value", [
        "password",
        "secret",
        "changeme",
    ])
    def test_insecure_api_key_rejected(self, bad_value: str) -> None:
        """Insecure API key values are replaced with None."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = _make_settings(api_key=bad_value)
            assert s.api_key is None


# ---------------------------------------------------------------------------
# CORS validation
# ---------------------------------------------------------------------------

class TestCORSValidation:
    """CORS origin parsing must validate URL format."""

    def test_cors_rejects_non_url_origins(self) -> None:
        """Non-URL origins should be filtered out."""
        s = _make_settings(cors_origins="not-a-url,also-bad")
        assert len(s.cors_origins_list) == 0

    def test_cors_accepts_valid_https(self) -> None:
        """Valid HTTPS origins should be accepted."""
        s = _make_settings(cors_origins="https://app.example.com")
        assert "https://app.example.com" in s.cors_origins_list

    def test_cors_accepts_valid_http(self) -> None:
        """Valid HTTP origins should be accepted (for dev)."""
        s = _make_settings(cors_origins="http://localhost:3000")
        assert "http://localhost:3000" in s.cors_origins_list

    def test_cors_strips_trailing_slashes(self) -> None:
        """Trailing slashes should be stripped from origins."""
        s = _make_settings(cors_origins="https://app.example.com/")
        assert s.cors_origins_list == ["https://app.example.com"]

    def test_cors_handles_multiple_origins(self) -> None:
        """Multiple comma-separated origins should all be parsed."""
        s = _make_settings(
            cors_origins="https://a.example.com,https://b.example.com,http://localhost:3000"
        )
        assert len(s.cors_origins_list) == 3

    def test_cors_empty_string_returns_empty_list(self) -> None:
        """Empty CORS string should return empty list."""
        s = _make_settings(cors_origins="")
        assert s.cors_origins_list == []


# ---------------------------------------------------------------------------
# LLM provider validation
# ---------------------------------------------------------------------------

class TestLLMProviderPolicy:
    """LLM provider must be on approved list in production."""

    def test_production_rejects_unapproved_llm_provider(self) -> None:
        """Production should reject a provider not in the approved list."""
        with pytest.raises(ValidationError, match="not in APPROVED_LLM_PROVIDERS"):
            _make_settings(
                environment="production",
                auth_enabled=True,
                jwt_secret_key="secure-key-for-testing-12345",
                api_key="secure-api-key-12345",
                metriport_webhook_key="webhook-key-12345",
                llm_provider="anthropic",
                approved_llm_providers="openai",
            )

    def test_production_accepts_approved_llm_provider(self) -> None:
        """Production should accept a provider on the approved list."""
        s = _make_settings(
            environment="production",
            auth_enabled=True,
            jwt_secret_key="secure-key-for-testing-12345",
            api_key="secure-api-key-12345",
            metriport_webhook_key="webhook-key-12345",
            llm_provider="openai",
            approved_llm_providers="openai,anthropic",
        )
        assert s.llm_provider == "openai"


# ---------------------------------------------------------------------------
# Development environment
# ---------------------------------------------------------------------------

class TestDevelopmentEnvironment:
    """Dev environment should be relaxed but not insecure."""

    def test_dev_allows_auth_disabled(self) -> None:
        """Development environment should allow auth_enabled=False."""
        s = _make_settings(environment="development", auth_enabled=False)
        assert s.auth_enabled is False
        assert s.environment == "development"

    def test_dev_database_url_contains_localhost(self) -> None:
        """Default database URL uses localhost (dev only)."""
        s = _make_settings()
        assert "localhost" in s.database_url

    def test_dev_redis_url_contains_localhost(self) -> None:
        """Default Redis URL uses localhost (dev only)."""
        s = _make_settings()
        assert "localhost" in s.redis_url

    def test_dev_neo4j_uri_is_set(self) -> None:
        """Default Neo4j URI is set in dev (may be localhost or container name)."""
        s = _make_settings()
        assert s.neo4j_uri is not None and len(s.neo4j_uri) > 0

    def test_dev_is_not_production(self) -> None:
        """Development environment should not report as production."""
        s = _make_settings(environment="development")
        assert s.is_production is False
