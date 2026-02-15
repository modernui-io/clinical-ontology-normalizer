"""Application configuration using pydantic-settings.

VP-Security-3: Hardcoded credential defaults removed.
All sensitive credentials must be provided via environment variables.
The application will fail to start if required credentials are missing
when auth_enabled=True or environment=production.
"""

from __future__ import annotations

import logging
import warnings
from functools import cached_property
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Insecure default values that should never be used in production
_INSECURE_DEFAULTS = {
    "change-this-in-production-use-env-var",
    "dev-api-key-change-in-production",
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
        extra="ignore",
    )

    # Application
    app_name: str = "Clinical Ontology Normalizer"
    debug: bool = False
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"  # CTO-6: DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Database
    database_url: str = "postgresql+asyncpg://postgres@localhost:5432/clinical_ontology"

    # For sync operations (alembic migrations)
    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for migrations."""
        return self.database_url.replace("+asyncpg", "")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_v1_prefix: str = "/api/v1"

    # VP-Security-3: CORS Configuration - environment-based origins
    # Comma-separated list of allowed origins, e.g., "https://app.example.com,https://admin.example.com"
    # Defaults to localhost for development; MUST be set explicitly for production
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"
    cors_allow_credentials: bool = True

    @cached_property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string.

        VP-Security-3: Validates that all origins are absolute URLs.
        Returns empty list if validation fails (secure default).
        """
        if not self.cors_origins:
            return []

        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        validated = []

        for origin in origins:
            # Validate absolute URL format
            if origin.startswith(("http://", "https://")):
                # Remove trailing slashes for consistency
                validated.append(origin.rstrip("/"))
            else:
                logger.warning(
                    f"Invalid CORS origin '{origin}' ignored. "
                    f"Origins must be absolute URLs (http:// or https://)"
                )

        return validated

    # Authentication - NO INSECURE DEFAULTS
    api_key: str | None = None  # Required when auth_enabled=True
    api_keys: str = ""  # Comma-separated list for multi-key support (VP-Round60)
    api_key_header: str = "X-API-Key"
    auth_enabled: bool = False  # Disabled by default for local dev

    @cached_property
    def api_keys_set(self) -> set[str]:
        """Parse API keys from comma-separated string.

        VP-Round60: Centralized multi-key support. Falls back to single api_key.
        """
        if self.api_keys:
            return {k.strip() for k in self.api_keys.split(",") if k.strip()}
        if self.api_key:
            return {self.api_key}
        return set()
    jwt_secret_key: str | None = None  # Required when auth_enabled=True
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    auth_bypass_dev: bool = False  # Dev bypass for testing without auth

    # Readiness probe: comma-separated list of services that must be real (not mock) to pass.
    # In production, set to "database,neo4j,kafka,redis" to fail-closed on mock dependencies.
    # P0-001/002/003: Ensures mock mode is never treated as production-ready.
    required_services: str = "database"  # dev default; production must include neo4j,kafka,redis

    # API Maturity Gating (CTO-2)
    block_scaffold_endpoints: bool = False  # Block SCAFFOLD-tier endpoints (enable in production)

    # P0-012: Encryption-at-rest attestation flag.
    # Set to true once host/volume encryption is verified for PHI stores.
    encryption_at_rest_verified: bool = False

    # P0-013: TLS configuration flag.
    # Set to true once TLS termination is confirmed for production ingress.
    tls_enabled: bool = False

    # LLM Configuration
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_model: str = "gpt-4o-mini"  # Default model
    llm_max_tokens: int = 4096  # Maximum tokens for completion

    # P0-017: Approved external LLM providers for PHI-carrying routes.
    # Comma-separated list. Only providers on this list may receive PHI data.
    # If empty, all configured providers are allowed (dev default).
    approved_llm_providers: str = ""

    @cached_property
    def approved_llm_providers_set(self) -> set[str]:
        """Parse approved LLM providers from comma-separated string."""
        if not self.approved_llm_providers:
            return set()
        return {p.strip().lower() for p in self.approved_llm_providers.split(",") if p.strip()}

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

    # Ontology Feature Flags (Phase 2-4 rollout)
    enable_concept_mapping: bool = False  # Phase 2: Map entities to OMOP concept_ids
    use_ontology_edges: bool = False  # Phase 3: Use OMOP relationships for edges
    enable_temporal_extraction: bool = True  # Phase 4: Extract dates from text

    # Narrative Extraction Feature Flags
    enable_narrative_extraction: bool = True  # Extract clinical narratives (admission, course, discharge)
    narrative_extraction_model: str = "claude"  # Model to use: "claude" or "openai"

    # FHIR Configuration (VP-Round51: Centralized from fhir.py)
    # Comma-separated list of allowed FHIR servers for SSRF prevention
    # If not set, all public URLs are allowed (with private IP blocking)
    allowed_fhir_servers: str = ""
    allow_localhost_fhir: bool = True  # Allow localhost in development

    # Metriport Integration
    metriport_api_key: str | None = None  # Metriport Medical API key
    metriport_webhook_key: str | None = None  # Webhook signing key for HMAC verification
    metriport_base_url: str = "https://api.sandbox.metriport.com"  # Sandbox by default
    metriport_facility_id: str | None = None  # Metriport facility UUID

    # Medidata Rave EDC Integration
    medidata_rave_base_url: str = ""  # Rave Web Services URL (e.g., https://rave.example.com)
    medidata_rave_username: str = ""  # Rave API username
    medidata_rave_password: str = ""  # Rave API password
    medidata_rave_default_env: str = "Prod"  # Default study environment

    # Veeva Vault CDMS Integration
    veeva_vault_url: str = ""  # Vault CDMS URL (e.g., https://myvault.veevavault.com)
    veeva_vault_username: str = ""  # Vault API username
    veeva_vault_password: str = ""  # Vault API password

    # ETL Configuration (VP-Round60)
    # Encryption key for storing data source credentials
    # IMPORTANT: Set this in production - otherwise each restart generates new key
    etl_encryption_key: str | None = None

    @cached_property
    def allowed_fhir_servers_set(self) -> set[str]:
        """Parse allowed FHIR servers from comma-separated string.

        Returns normalized set of server URLs (lowercase, no trailing slash).
        """
        if not self.allowed_fhir_servers:
            return set()
        return {
            s.strip().lower().rstrip("/")
            for s in self.allowed_fhir_servers.split(",")
            if s.strip()
        }

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
        is_staging = self.environment.lower() == "staging"

        # P0-009: Hard-fail if production/staging runs without auth
        if (is_production or is_staging) and not self.auth_enabled:
            raise ValueError(
                f"AUTH_ENABLED must be true when ENVIRONMENT={self.environment}. "
                f"Running production/staging without authentication is not allowed."
            )

        # In production, all auth credentials are required
        if is_production:
            missing = []
            if not self.jwt_secret_key:
                missing.append("JWT_SECRET_KEY")
            if not self.api_key:
                missing.append("API_KEY")
            # CISO-6: Webhook signing key required in production
            if not self.metriport_webhook_key:
                missing.append("METRIPORT_WEBHOOK_KEY")
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

        # P0-012: Warn if encryption-at-rest is not verified in production
        if is_production and not self.encryption_at_rest_verified:
            logger.warning(
                "ENCRYPTION_AT_REST_VERIFIED is not set. HIPAA requires "
                "encryption-at-rest for all PHI stores (PostgreSQL, Neo4j, Redis). "
                "Set ENCRYPTION_AT_REST_VERIFIED=true after verifying host/volume encryption."
            )

        # P0-013: Warn if TLS is not configured in production
        if is_production and not self.tls_enabled:
            logger.warning(
                "TLS_ENABLED is not set. HIPAA requires TLS for all PHI transport. "
                "Set TLS_ENABLED=true after confirming TLS termination at ingress."
            )

        # P0-017: Validate LLM provider is on approved list in production
        if is_production and self.approved_llm_providers:
            approved = {
                p.strip().lower()
                for p in self.approved_llm_providers.split(",")
                if p.strip()
            }
            active_provider = self.llm_provider.lower()
            if active_provider not in approved:
                raise ValueError(
                    f"LLM_PROVIDER '{self.llm_provider}' is not in "
                    f"APPROVED_LLM_PROVIDERS ({self.approved_llm_providers}). "
                    f"Only approved providers may handle PHI in production."
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
