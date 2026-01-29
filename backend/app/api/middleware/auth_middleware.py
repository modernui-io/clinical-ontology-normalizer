"""Authentication and authorization middleware for JWT-based access control.

This module provides:
- JWT authentication middleware for validating access tokens
- Permission checking decorators (@require_permission, @require_role)
- Current user dependency for FastAPI routes
- Request context for storing authenticated user information

Security features:
- Bearer token extraction from Authorization header
- Token validation and expiration checking
- Permission-based access control
- Role-based access control
- Integration with RBAC service
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    get_db,
    get_db_request_context,
    set_db_request_context,
)
from app.services.auth import AuthService, TokenPayload, get_auth_service
from app.services.rbac_service import RBACService, get_rbac_service

logger = logging.getLogger(__name__)

# Context variable to store current user in request context
_current_user_ctx: ContextVar[TokenPayload | None] = ContextVar(
    "current_user", default=None
)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """Authenticated user information from JWT token."""

    id: str
    email: str
    name: str | None
    roles: list[str]
    permissions: list[str]

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return role_name in self.roles

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has a specific permission."""
        return f"{resource}:{action}" in self.permissions

    def has_any_permission(self, permissions: list[str]) -> bool:
        """Check if user has any of the specified permissions."""
        return bool(set(permissions) & set(self.permissions))

    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return "admin" in self.roles


def get_current_user_context() -> TokenPayload | None:
    """Get the current user from request context.

    Returns:
        TokenPayload if authenticated, None otherwise
    """
    return _current_user_ctx.get()


def set_current_user_context(user: TokenPayload | None) -> None:
    """Set the current user in request context.

    Args:
        user: TokenPayload to store, or None to clear
    """
    _current_user_ctx.set(user)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    """Dependency to get the current authenticated user.

    This dependency validates the JWT token from the Authorization header
    and returns the authenticated user information.

    Args:
        credentials: HTTP Bearer credentials from request
        auth_service: Authentication service instance

    Returns:
        CurrentUser with authenticated user information

    Raises:
        HTTPException: 401 if not authenticated
    """
    # Import settings here to avoid circular imports
    from app.core.config import settings

    # Dev auth bypass - return a mock admin user for development
    if settings.auth_bypass_dev and settings.debug:
        logger.warning("Auth bypass enabled - returning dev admin user")
        return CurrentUser(
            id="dev-admin-user",
            email="dev@local.test",
            name="Dev Admin",
            roles=["admin"],
            permissions=[
                "documents:read", "documents:write", "documents:delete", "documents:admin",
                "patients:read", "patients:write", "patients:delete", "patients:admin",
                "billing:read", "billing:write", "billing:delete", "billing:admin",
                "coding:read", "coding:write", "coding:delete", "coding:admin",
                "audit:read", "audit:write", "audit:export", "audit:admin",
                "admin:read", "admin:write", "admin:manage_users", "admin:manage_roles",
                "vocabulary:read", "vocabulary:write", "vocabulary:admin",
                "graphs:read", "graphs:write", "graphs:admin",
                "export:read", "export:write", "export:admin",
                "llm:read", "llm:write", "llm:admin",
            ],
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = auth_service.validate_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Store in context for middleware access
    set_current_user_context(payload)

    # VP-DevOps-3: Update database context with user_id for exception logging
    db_ctx = get_db_request_context()
    if db_ctx:
        db_ctx.user_id = payload.sub
        set_db_request_context(db_ctx)

    return CurrentUser(
        id=payload.sub,
        email=payload.email,
        name=None,  # Not stored in token
        roles=payload.roles,
        permissions=payload.permissions,
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUser | None:
    """Dependency to optionally get the current authenticated user.

    Unlike get_current_user, this does not raise an exception if
    the user is not authenticated. Useful for routes that allow
    both authenticated and anonymous access.

    Args:
        credentials: HTTP Bearer credentials from request
        auth_service: Authentication service instance

    Returns:
        CurrentUser if authenticated, None otherwise
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = auth_service.validate_access_token(token)

    if not payload:
        return None

    # Store in context
    set_current_user_context(payload)

    return CurrentUser(
        id=payload.sub,
        email=payload.email,
        name=None,
        roles=payload.roles,
        permissions=payload.permissions,
    )


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
) -> CurrentUser:
    """Dependency to get the current active user with fresh permissions.

    This refreshes permissions from the database to ensure we have
    the latest role/permission assignments.

    Args:
        current_user: Current authenticated user
        db: Database session
        rbac_service: RBAC service instance

    Returns:
        CurrentUser with fresh permissions

    Raises:
        HTTPException: 401 if user is inactive or not found
    """
    user_perms = await rbac_service.get_user_permissions(db, current_user.id)

    if not user_perms:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        id=current_user.id,
        email=user_perms.email,
        name=None,
        roles=user_perms.roles,
        permissions=list(user_perms.permissions),
    )


def require_permission(resource: str, action: str) -> Callable[..., Any]:
    """Decorator to require a specific permission for an endpoint.

    Usage:
        @router.get("/documents")
        @require_permission("documents", "read")
        async def get_documents(current_user: CurrentUser = Depends(get_current_user)):
            ...

    Args:
        resource: Resource type (e.g., 'documents', 'patients')
        action: Action type (e.g., 'read', 'write', 'delete')

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get current_user from kwargs (injected by FastAPI)
            current_user: CurrentUser | None = kwargs.get("current_user")

            if not current_user:
                # Try to find it in args (shouldn't happen with FastAPI)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Check permission
            permission_name = f"{resource}:{action}"
            if not current_user.has_permission(resource, action) and not current_user.is_admin():
                logger.warning(
                    f"Permission denied: {current_user.email} tried to access "
                    f"{permission_name}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission_name}' required",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_role(role_name: str) -> Callable[..., Any]:
    """Decorator to require a specific role for an endpoint.

    Usage:
        @router.post("/users")
        @require_role("admin")
        async def create_user(current_user: CurrentUser = Depends(get_current_user)):
            ...

    Args:
        role_name: Name of the required role

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get current_user from kwargs
            current_user: CurrentUser | None = kwargs.get("current_user")

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Check role
            if not current_user.has_role(role_name):
                logger.warning(
                    f"Role denied: {current_user.email} tried to access "
                    f"endpoint requiring role '{role_name}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{role_name}' required",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_role(*role_names: str) -> Callable[..., Any]:
    """Decorator to require any of the specified roles.

    Usage:
        @router.get("/billing")
        @require_any_role("admin", "biller")
        async def get_billing(current_user: CurrentUser = Depends(get_current_user)):
            ...

    Args:
        role_names: Names of acceptable roles

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_user: CurrentUser | None = kwargs.get("current_user")

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Check if user has any of the required roles
            if not any(current_user.has_role(role) for role in role_names):
                logger.warning(
                    f"Role denied: {current_user.email} tried to access "
                    f"endpoint requiring one of roles: {role_names}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of roles {list(role_names)} required",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(*permissions: str) -> Callable[..., Any]:
    """Decorator to require any of the specified permissions.

    Usage:
        @router.get("/data")
        @require_any_permission("documents:read", "patients:read")
        async def get_data(current_user: CurrentUser = Depends(get_current_user)):
            ...

    Args:
        permissions: Permission names (e.g., 'documents:read')

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_user: CurrentUser | None = kwargs.get("current_user")

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Admin always has access
            if current_user.is_admin():
                return await func(*args, **kwargs)

            # Check if user has any of the required permissions
            if not current_user.has_any_permission(list(permissions)):
                logger.warning(
                    f"Permission denied: {current_user.email} tried to access "
                    f"endpoint requiring one of: {permissions}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of permissions {list(permissions)} required",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


class PermissionChecker:
    """Dependency class for permission checking with FastAPI Depends.

    This provides a cleaner alternative to decorators when you need
    more control over permission checking.

    Usage:
        @router.get("/documents")
        async def get_documents(
            _: None = Depends(PermissionChecker("documents", "read")),
            current_user: CurrentUser = Depends(get_current_user),
        ):
            ...
    """

    def __init__(self, resource: str, action: str) -> None:
        """Initialize permission checker.

        Args:
            resource: Resource type to check
            action: Action type to check
        """
        self.resource = resource
        self.action = action

    async def __call__(
        self,
        current_user: CurrentUser = Depends(get_current_user),
    ) -> None:
        """Check permission and raise HTTPException if denied.

        Args:
            current_user: Current authenticated user

        Raises:
            HTTPException: 403 if permission denied
        """
        if current_user.is_admin():
            return

        if not current_user.has_permission(self.resource, self.action):
            permission_name = f"{self.resource}:{self.action}"
            logger.warning(
                f"Permission denied: {current_user.email} - {permission_name}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_name}' required",
            )


class RoleChecker:
    """Dependency class for role checking with FastAPI Depends.

    Usage:
        @router.post("/admin")
        async def admin_action(
            _: None = Depends(RoleChecker("admin")),
            current_user: CurrentUser = Depends(get_current_user),
        ):
            ...
    """

    def __init__(self, *role_names: str) -> None:
        """Initialize role checker.

        Args:
            role_names: Required role names (user must have at least one)
        """
        self.role_names = role_names

    async def __call__(
        self,
        current_user: CurrentUser = Depends(get_current_user),
    ) -> None:
        """Check role and raise HTTPException if denied.

        Args:
            current_user: Current authenticated user

        Raises:
            HTTPException: 403 if role denied
        """
        if not any(current_user.has_role(role) for role in self.role_names):
            logger.warning(
                f"Role denied: {current_user.email} - required: {self.role_names}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {list(self.role_names)} required",
            )


# Convenience functions for common permission checks

async def require_documents_read(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Require documents:read permission."""
    if not current_user.is_admin() and not current_user.has_permission("documents", "read"):
        raise HTTPException(status_code=403, detail="documents:read permission required")
    return current_user


async def require_documents_write(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Require documents:write permission."""
    if not current_user.is_admin() and not current_user.has_permission("documents", "write"):
        raise HTTPException(status_code=403, detail="documents:write permission required")
    return current_user


async def require_patients_read(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Require patients:read permission."""
    if not current_user.is_admin() and not current_user.has_permission("patients", "read"):
        raise HTTPException(status_code=403, detail="patients:read permission required")
    return current_user


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Require admin role."""
    if not current_user.is_admin():
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
