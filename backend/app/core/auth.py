"""Legacy authentication module - DEPRECATED.

This module is deprecated. Use app.core.security instead.

All functionality has been consolidated into app.core.security:
- verify_api_key: API key verification
- get_api_keys: Multi-key support from CON_API_KEYS env var
- is_auth_enabled: Check if auth is enabled
- optional_verify_api_key: Optional auth verification
- is_public_route: Check if route is public
- PUBLIC_ROUTES: Set of public route paths

This module re-exports from app.core.security for backwards compatibility.
"""

import warnings

from app.core.security import (
    PUBLIC_ROUTES,
    get_api_keys,
    is_auth_enabled,
    is_public_route,
    optional_verify_api_key,
    verify_api_key_async as verify_api_key,
)

# Emit deprecation warning when this module is imported
warnings.warn(
    "app.core.auth is deprecated. Use app.core.security instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backwards compatibility
__all__ = [
    "PUBLIC_ROUTES",
    "get_api_keys",
    "is_auth_enabled",
    "is_public_route",
    "optional_verify_api_key",
    "verify_api_key",
]


def require_api_key() -> None:
    """Dependency marker indicating route requires authentication.

    DEPRECATED: Use app.core.security.RequireAuth instead.

    Use this in route definitions to clearly mark protected routes:

        @router.get("/protected", dependencies=[Depends(require_api_key)])
        def protected_route():
            ...
    """
    pass
