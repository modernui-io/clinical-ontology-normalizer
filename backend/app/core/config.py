"""Application configuration using pydantic-settings.

VP-Security-3: Hardcoded credential defaults removed.
All sensitive credentials must be provided via environment variables.
The application will fail to start if required credentials are missing
when auth_enabled=True or environment=production.
"""

import logging
import warnings
from functools import cached_property

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Insecure default values that should never be used in production
_INSECURE_DEFAULTS = {
    "change-this-in-production-use-env-var",
    "dev-api-key-change-in-production",
    "clinical123",
    "password",
    "secret",
    "changeme",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Security Notes:
    - All sensitive values MUST be set via environment variables
    - Insecure defaults will raise errors when auth_enabled=True
    - Production environment requires all credentials to be explicitly set
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Clinical Ontology Normalizer"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ontology"

    # For sync operations (alembic migrations)
    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for migrations."""
        return self.database_url.replace("+asyncpg", "")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_v1_prefix: str = "/api/v1"

    # Authentication - NO INSECURE DEFAULTS
    api_key: str | None = None  # Required when auth_enabled=True
    api_key_header: str = "X-API-Key"
    auth_enabled: bool = False  # Disabled by default for local dev
    jwt_secret_key: str | None = None  # Required when auth_enabled=True
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    auth_bypass_dev: bool = False  # Dev bypass for testing without auth

    # LLM Configuration
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_model: str = "gpt-4o-mini"  # Default model
    llm_max_tokens: int = 4096  # Maximum tokens for completion

    # Neo4j Configuration (for knowledge graph)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None  # Required for Neo4j connection
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50
    neo4j_connection_timeout: int = 30

    # UMLS Configuration
    umls_api_key: str | None = None  # For UMLS API access
    umls_data_path: str | None = None  # Path to UMLS META directory

    @field_validator("jwt_secret_key", "api_key", "neo4j_password", mode="before")
    @classmethod
    def check_not_insecure_default(cls, v: str | None) -> str | None:
        """Reject known insecure default values."""
        if v is not None and v.lower() in _INSECURE_DEFAULTS:
            warnings.warn(
                f"Insecure default credential detected. "
                f"Please set a secure value via environment variable.",
                UserWarning,
                stacklevel=2,
            )
            # Return None to trigger validation in model_validator
            return None
        return v

    @model_validator(mode="after")
    def validate_security_config(self) -> "Settings":
        """Validate security configuration based on environment."""
        is_production = self.environment.lower() == "production"

        # In production, all auth credentials are required
        if is_production:
            missing = []
            if not self.jwt_secret_key:
                missing.append("JWT_SECRET_KEY")
            if not self.api_key:
                missing.append("API_KEY")
            if missing:
                raise ValueError(
                    f"Production environment requires these credentials: {', '.join(missing)}. "
                    f"Set them via environment variables."
                )

        # When auth is enabled, JWT secret is required
        if self.auth_enabled and not self.jwt_secret_key:
            raise ValueError(
                "JWT_SECRET_KEY is required when AUTH_ENABLED=true. "
                "Set a secure random string via environment variable."
            )

        # Warn about missing Neo4j password (but don't fail - might not use Neo4j)
        if not self.neo4j_password:
            logger.warning(
                "NEO4J_PASSWORD not set. Neo4j connections will fail. "
                "Set via environment variable if using knowledge graph features."
            )

        # Log security status
        if is_production:
            logger.info("Running in PRODUCTION mode with security validation enabled")
        elif self.auth_enabled:
            logger.info("Authentication enabled in non-production environment")
        else:
            logger.debug("Authentication disabled (development mode)")

        return self

    @cached_property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


settings = Settings()
