"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Clinical Ontology Normalizer"
    debug: bool = False

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

    # Authentication
    api_key: str = "dev-api-key-change-in-production"
    api_key_header: str = "X-API-Key"
    auth_enabled: bool = False  # Disabled by default for local dev

    # LLM Configuration
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_model: str = "gpt-4o-mini"  # Default model
    llm_max_tokens: int = 4096  # Maximum tokens for completion


settings = Settings()
