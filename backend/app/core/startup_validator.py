"""Production-safe startup validation for dependency credentials.

P1-020: Validates that all required credentials are set and not placeholder/default
values before the application accepts traffic. In non-development environments,
validation errors prevent startup. In development, they are logged as warnings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import Settings, _INSECURE_DEFAULTS

logger = logging.getLogger(__name__)

# Placeholder patterns that indicate a credential was not intentionally set.
_PLACEHOLDER_PATTERNS = (
    "changeme",
    "CHANGEME",
    "change-me",
    "CHANGE-ME",
    "your-",
    "YOUR-",
    "replace-",
    "REPLACE-",
    "todo",
    "TODO",
    "xxx",
    "XXX",
    "placeholder",
    "PLACEHOLDER",
    "example",
    "EXAMPLE",
)


def _is_placeholder(value: str | None) -> bool:
    """Return True if the value looks like an unset placeholder or insecure default."""
    if value is None or value == "":
        return True
    lower = value.lower().strip()
    if lower in _INSECURE_DEFAULTS:
        return True
    for pat in _PLACEHOLDER_PATTERNS:
        if pat.lower() in lower:
            return True
    return False


@dataclass
class StartupValidationResult:
    """Outcome of credential / config validation at startup.

    Attributes:
        valid: True when there are zero errors.
        errors: Problems that should block startup in non-dev environments.
        warnings: Issues worth logging but not blocking.
    """

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_production_credentials(
    config: Settings | None = None,
) -> StartupValidationResult:
    """Check that all required credentials are present and not placeholders.

    Checks performed:
    - DATABASE_URL is set and not a localhost default in production
    - REDIS_URL is set
    - SECRET_KEY (jwt_secret_key) is set and not an insecure default
    - NEO4J_PASSWORD is set when neo4j features are expected
    - API keys for external services are set when those services are enabled
    - ETL_ENCRYPTION_KEY is set in production

    Args:
        config: Application settings. Defaults to the global singleton.

    Returns:
        StartupValidationResult with errors and warnings.
    """
    if config is None:
        from app.core.config import settings as _settings
        config = _settings

    result = StartupValidationResult()
    is_prod = config.environment.lower() == "production"
    is_staging = config.environment.lower() == "staging"
    is_strict = is_prod or is_staging

    # --- DATABASE_URL ---
    if not config.database_url:
        result.add_error("DATABASE_URL is not set")
    elif is_strict and "localhost" in config.database_url:
        result.add_error(
            "DATABASE_URL points to localhost in a production/staging environment"
        )

    # --- REDIS_URL ---
    if not config.redis_url:
        result.add_warning("REDIS_URL is not set; Redis-dependent features will fail")
    elif is_strict and "localhost" in config.redis_url:
        result.add_warning(
            "REDIS_URL points to localhost in a production/staging environment"
        )

    # --- JWT_SECRET_KEY ---
    if config.auth_enabled or is_strict:
        if _is_placeholder(config.jwt_secret_key):
            result.add_error(
                "JWT_SECRET_KEY is missing or set to a placeholder/insecure default"
            )

    # --- API_KEY ---
    if config.auth_enabled or is_strict:
        if _is_placeholder(config.api_key):
            result.add_error(
                "API_KEY is missing or set to a placeholder/insecure default"
            )

    # --- NEO4J_PASSWORD ---
    if _is_placeholder(config.neo4j_password):
        if is_strict:
            result.add_warning(
                "NEO4J_PASSWORD is not set; graph features will be unavailable"
            )
        else:
            result.add_warning("NEO4J_PASSWORD is not set")

    # --- LLM API Keys ---
    provider = config.llm_provider.lower()
    if provider == "openai" and _is_placeholder(config.openai_api_key):
        if is_strict:
            result.add_error(
                "OPENAI_API_KEY is not set but LLM_PROVIDER is 'openai'"
            )
        else:
            result.add_warning("OPENAI_API_KEY is not set for openai provider")
    if provider == "anthropic" and _is_placeholder(config.anthropic_api_key):
        if is_strict:
            result.add_error(
                "ANTHROPIC_API_KEY is not set but LLM_PROVIDER is 'anthropic'"
            )
        else:
            result.add_warning("ANTHROPIC_API_KEY is not set for anthropic provider")

    # --- ETL_ENCRYPTION_KEY ---
    if is_strict and _is_placeholder(config.etl_encryption_key):
        result.add_warning(
            "ETL_ENCRYPTION_KEY is not set; ETL credential storage will use ephemeral keys"
        )

    # --- PHI_ENCRYPTION_KEY ---
    if is_strict and _is_placeholder(config.phi_encryption_key):
        result.add_error(
            "PHI_ENCRYPTION_KEY is not set; field-level PHI encryption will not work"
        )

    return result


def run_startup_validation(config: Settings | None = None) -> StartupValidationResult:
    """Execute validation and log/raise based on environment.

    In development: logs warnings for all issues, never blocks.
    In staging/production: logs errors and raises RuntimeError if any errors found.

    Returns:
        The validation result (only reached if startup is not blocked).

    Raises:
        RuntimeError: In non-dev environments when validation errors are present.
    """
    if config is None:
        from app.core.config import settings as _settings
        config = _settings

    result = validate_production_credentials(config)
    is_dev = config.environment.lower() == "development"

    # Log all warnings
    for warning in result.warnings:
        logger.warning("Startup validation warning: %s", warning)

    if result.valid:
        logger.info("Startup credential validation passed")
        return result

    # There are errors
    for error in result.errors:
        if is_dev:
            logger.warning("Startup validation (dev mode, non-blocking): %s", error)
        else:
            logger.error("Startup validation error: %s", error)

    if not is_dev:
        raise RuntimeError(
            f"Startup blocked: {len(result.errors)} credential validation error(s). "
            f"Errors: {'; '.join(result.errors)}"
        )

    return result
