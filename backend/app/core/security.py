"""Security and authentication middleware.

This module provides:
- API key authentication (single key from settings)
- Tenant context for patient data isolation

For JWT-based authentication, use app.api.middleware.auth_middleware instead.
For multi-key API authentication, see get_api_keys() function.

Note: This is the canonical API key auth module. The legacy app.core.auth
module is deprecated and will be removed in a future version.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

logger = logging.getLogger(__name__)

# API Key header security scheme
api_key_header = APIKeyHeader(
    name=settings.api_key_header,
    auto_error=False,  # Don't auto-error, we handle it manually
)


# -------------------------------------------------------------------------
# Multi-Key API Authentication (consolidated from core.auth)
# -------------------------------------------------------------------------


@lru_cache
def get_api_keys() -> set[str]:
    """Get configured API keys from environment.

    API keys can be set via the CON_API_KEYS environment variable
    as a comma-separated list for multi-key support.

    Returns:
        Set of valid API keys
    """
    api_keys_str = os.environ.get("CON_API_KEYS", "")
    if not api_keys_str:
        # Fall back to single key from settings
        if settings.api_key:
            return {settings.api_key}
        logger.warning(
            "No API keys configured (CON_API_KEYS not set). "
            "Authentication is disabled for development."
        )
        return set()

    keys = {k.strip() for k in api_keys_str.split(",") if k.strip()}
    logger.info(f"Loaded {len(keys)} API key(s) for authentication")
    return keys


def is_auth_enabled() -> bool:
    """Check if authentication is enabled.

    Authentication is enabled when API keys are configured or
    when settings.auth_enabled is True.

    Returns:
        True if authentication is enabled
    """
    return settings.auth_enabled or len(get_api_keys()) > 0


# Public routes that don't require authentication
PUBLIC_ROUTES = frozenset({
    "/",
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
})


def is_public_route(path: str) -> bool:
    """Check if a route path is public (no auth required).

    Args:
        path: The request path

    Returns:
        True if the route is public
    """
    return path in PUBLIC_ROUTES


def verify_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
) -> str | None:
    """Verify API key if authentication is enabled.

    Supports both single key (from settings.api_key) and multi-key
    (from CON_API_KEYS env var) authentication.

    When auth is enabled:
    - Missing API key returns 401
    - Invalid API key returns 403

    When auth is disabled:
    - Returns None (no authentication required)

    Args:
        api_key: The API key from the request header

    Returns:
        The validated API key or None if auth disabled

    Raises:
        HTTPException: 401 if missing key, 403 if invalid key
    """
    if not is_auth_enabled():
        return None

    if api_key is None:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Check against all configured API keys
    valid_keys = get_api_keys()
    if api_key not in valid_keys:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


async def verify_api_key_async(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Async version of verify_api_key for compatibility.

    This provides the same functionality as verify_api_key but as an
    async function for use in async dependency chains.

    Args:
        api_key: API key from request header

    Returns:
        The verified API key if valid, None if auth disabled

    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    return verify_api_key(api_key)


async def optional_verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Optionally verify API key, returning None if auth is disabled.

    Unlike verify_api_key, this does not raise an error when authentication
    is disabled. Use this for routes that should work both with and without
    authentication.

    Args:
        api_key: API key from request header

    Returns:
        The verified API key, or None if auth is disabled
    """
    if not is_auth_enabled():
        return None
    return verify_api_key(api_key)


# Dependency for protected endpoints
RequireAuth = Annotated[str | None, Depends(verify_api_key)]


class TenantContext:
    """Context for tenant/patient isolation.

    Tracks the current tenant (patient) context for data access.
    Used to enforce isolation between patient data.
    """

    def __init__(self, tenant_id: str | None = None):
        """Initialize tenant context.

        Args:
            tenant_id: The tenant/patient ID for this request
        """
        self.tenant_id = tenant_id

    def is_authorized_for(self, patient_id: str) -> bool:
        """Check if current context is authorized to access patient data.

        Args:
            patient_id: The patient ID to check access for

        Returns:
            True if authorized, False otherwise
        """
        # If no tenant restriction, allow all (dev mode)
        if self.tenant_id is None:
            return True

        # Only allow access to own data
        return self.tenant_id == patient_id


def get_tenant_context() -> TenantContext:
    """Get tenant context for the current request.

    In a real implementation, this would extract tenant info
    from the authenticated user/token.

    Returns:
        TenantContext for isolation enforcement
    """
    # For now, return unrestricted context (dev mode)
    # In production, this would come from JWT claims or similar
    return TenantContext(tenant_id=None)


RequireTenant = Annotated[TenantContext, Depends(get_tenant_context)]
