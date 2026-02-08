"""RBAC Permission Framework (CISO-9 Phase 1).

Enum-based permission and role definitions with a FastAPI-compatible
PermissionChecker dependency. This module provides:

- Permission enum: fine-grained capabilities
- Role enum: named bundles of permissions
- ROLE_PERMISSIONS: canonical role-to-permission mapping
- PermissionChecker: FastAPI ``Depends`` class that enforces permissions
- require_permissions(): convenience wrapper for PermissionChecker

Design decisions:
    * Enforcement is **skipped** when auth is not active (demo / local-dev mode)
      so the existing demo flow is never broken.
    * Permission denials are logged at WARNING level for the audit trail.
    * The checker inspects ``request.state.user`` (set by the JWT auth
      middleware) for the user's role.  If no user is present *and* auth is
      disabled, the request is allowed through.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission enum
# ---------------------------------------------------------------------------

class Permission(str, Enum):
    """Fine-grained capability tokens.

    Each permission represents a single action that a user may or may not
    be allowed to perform.  Permissions are combined into roles via the
    ``ROLE_PERMISSIONS`` mapping below.
    """

    READ_PATIENTS = "read_patients"
    WRITE_PATIENTS = "write_patients"
    READ_TRIALS = "read_trials"
    WRITE_TRIALS = "write_trials"
    SCREEN_PATIENTS = "screen_patients"
    READ_DOCUMENTS = "read_documents"
    WRITE_DOCUMENTS = "write_documents"
    READ_AUDIT = "read_audit"
    ADMIN = "admin"
    READ_ANALYTICS = "read_analytics"
    MANAGE_USERS = "manage_users"
    READ_CLINICAL_FACTS = "read_clinical_facts"
    WRITE_CLINICAL_FACTS = "write_clinical_facts"
    EXPORT_DATA = "export_data"
    READ_LINEAGE = "read_lineage"


# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------

class Role(str, Enum):
    """Named bundles of permissions assigned to users."""

    ADMIN = "admin"
    PROVIDER = "provider"
    COORDINATOR = "coordinator"
    ANALYST = "analyst"
    VIEWER = "viewer"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Role -> Permission mapping
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),  # every permission

    Role.PROVIDER: frozenset({
        Permission.READ_PATIENTS,
        Permission.WRITE_PATIENTS,
        Permission.READ_TRIALS,
        Permission.WRITE_TRIALS,
        Permission.SCREEN_PATIENTS,
        Permission.READ_DOCUMENTS,
        Permission.WRITE_DOCUMENTS,
        Permission.READ_CLINICAL_FACTS,
        Permission.WRITE_CLINICAL_FACTS,
        Permission.READ_LINEAGE,
    }),

    Role.COORDINATOR: frozenset({
        Permission.READ_PATIENTS,
        Permission.READ_TRIALS,
        Permission.SCREEN_PATIENTS,
        Permission.READ_DOCUMENTS,
        Permission.READ_LINEAGE,
    }),

    Role.ANALYST: frozenset({
        Permission.READ_PATIENTS,
        Permission.READ_TRIALS,
        Permission.READ_ANALYTICS,
        Permission.READ_CLINICAL_FACTS,
        Permission.EXPORT_DATA,
        Permission.READ_LINEAGE,
    }),

    Role.VIEWER: frozenset({
        Permission.READ_PATIENTS,
        Permission.READ_TRIALS,
    }),

    Role.SYSTEM: frozenset(Permission),  # internal service calls get full access
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    """Check whether *role* includes *permission*.

    Args:
        role: The role to test.
        permission: The capability to look for.

    Returns:
        ``True`` if the role grants the permission.
    """
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def get_role_permissions(role: Role) -> frozenset[Permission]:
    """Return all permissions granted to *role*.

    Args:
        role: The role to query.

    Returns:
        Frozen set of permissions (possibly empty for unknown roles).
    """
    return ROLE_PERMISSIONS.get(role, frozenset())


# ---------------------------------------------------------------------------
# Helpers - resolve user role from request
# ---------------------------------------------------------------------------

def _is_auth_active() -> bool:
    """Return ``True`` when authentication is actually enforced.

    We import ``settings`` lazily to avoid circular-import issues at
    module load time.
    """
    from app.core.config import settings

    # auth is active when explicitly enabled *or* when API keys are present
    if settings.auth_enabled:
        return True
    if settings.api_key or settings.api_keys:
        return True
    return False


def _resolve_user_role(request: Request) -> Role | None:
    """Extract the user's RBAC role from the request.

    The JWT auth middleware stores a user object in ``request.state.user``.
    We try several attribute paths to find the role string and map it to
    our ``Role`` enum.

    Returns:
        The ``Role`` if found, or ``None`` when no user/role is available.
    """
    user: Any = getattr(request.state, "user", None)
    if user is None:
        return None

    # The user object may store roles in different shapes depending on
    # which auth middleware populated it.
    role_str: str | None = None

    # 1. Attribute ``role`` (single role - our preferred convention)
    if hasattr(user, "role"):
        role_str = getattr(user, "role", None)

    # 2. ``roles`` list - pick the first one
    if role_str is None and hasattr(user, "roles"):
        roles = getattr(user, "roles", None)
        if roles and isinstance(roles, (list, tuple)) and len(roles) > 0:
            role_str = roles[0]

    # 3. dict-style access (e.g. request.state.user is a plain dict)
    if role_str is None and isinstance(user, dict):
        role_str = user.get("role") or (user.get("roles", [None]) or [None])[0]

    if role_str is None:
        return None

    # Normalise to our Role enum
    try:
        return Role(role_str.lower())
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# PermissionChecker - FastAPI dependency
# ---------------------------------------------------------------------------

class PermissionChecker:
    """FastAPI dependency that enforces RBAC permissions on a route.

    Usage::

        @router.get("/patients")
        async def list_patients(
            request: Request,
            _perm: None = Depends(PermissionChecker([Permission.READ_PATIENTS])),
        ):
            ...

    When auth is disabled (demo/dev mode) the checker is a no-op so that
    existing workflows are not broken.
    """

    def __init__(self, required_permissions: list[Permission]) -> None:
        self.required_permissions = required_permissions

    async def __call__(self, request: Request) -> None:  # noqa: D401
        """Enforce permission check.

        Raises:
            HTTPException 403: when the user's role lacks any of the
                required permissions.
        """
        # ---- Skip enforcement in demo / dev mode ----
        if not _is_auth_active():
            return

        role = _resolve_user_role(request)

        if role is None:
            # No user/role on the request but auth is ostensibly active.
            # In a pure-API-key auth setup there is no role info; allow
            # the request through (API-key already validated upstream).
            logger.debug(
                "PermissionChecker: no role on request for %s %s - allowing "
                "(API-key auth only?)",
                request.method,
                request.url.path,
            )
            return

        # Check every required permission
        granted = ROLE_PERMISSIONS.get(role, frozenset())
        missing = [p for p in self.required_permissions if p not in granted]

        if missing:
            missing_names = ", ".join(p.value for p in missing)
            logger.warning(
                "RBAC denial: role=%s path=%s method=%s missing=[%s]",
                role.value,
                request.url.path,
                request.method,
                missing_names,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. "
                    f"Missing: {missing_names}"
                ),
            )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def require_permissions(*perms: Permission) -> PermissionChecker:
    """Shorthand to create a ``PermissionChecker`` dependency.

    Usage::

        @router.post("/screen")
        async def screen(
            request: Request,
            _p: None = Depends(require_permissions(Permission.SCREEN_PATIENTS)),
        ):
            ...
    """
    return PermissionChecker(list(perms))
