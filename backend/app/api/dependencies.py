"""Common API dependencies and request context.

This module provides consolidated dependencies for API endpoints:
- RequestContext: Bundles common dependencies (db, user) into one injection
- Permission and role checking utilities
- Service factory functions with context

Benefits:
- Reduces boilerplate from ~4 lines per endpoint to ~1 line
- Consistent access pattern across all endpoints
- Easier testing (mock one context vs multiple dependencies)
- Type-safe access to request resources

Usage:
    from app.api.dependencies import get_authenticated_context, RequestContext

    @router.get("/items")
    async def get_items(ctx: RequestContext = Depends(get_authenticated_context)):
        # Access db via ctx.db
        # Access user via ctx.user
        items = await ctx.db.execute(select(Item))
        return items.scalars().all()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth_middleware import (
    CurrentUser,
    get_current_user,
    get_current_user_optional,
)
from app.core.database import get_db


@dataclass
class RequestContext:
    """Consolidated request context with common dependencies.

    Bundles database session and authenticated user into a single
    dependency for cleaner endpoint signatures.

    Attributes:
        db: Async database session for ORM operations
        user: Authenticated user (CurrentUser) or None for public endpoints
    """

    db: AsyncSession
    user: CurrentUser | None = None

    @property
    def user_id(self) -> str | None:
        """Get current user's ID, or None if not authenticated."""
        return self.user.id if self.user else None

    @property
    def is_authenticated(self) -> bool:
        """Check if request has an authenticated user."""
        return self.user is not None

    @property
    def is_admin(self) -> bool:
        """Check if current user has admin role."""
        return self.user is not None and self.user.is_admin()

    def require_auth(self) -> CurrentUser:
        """Get user, raising 401 if not authenticated.

        Use this in endpoints that use optional auth but need
        auth for specific operations.

        Returns:
            CurrentUser: The authenticated user

        Raises:
            HTTPException: 401 if not authenticated
        """
        if not self.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return self.user

    def require_permission(self, resource: str, action: str) -> None:
        """Check permission, raising 403 if denied.

        Args:
            resource: Resource name (e.g., "documents", "patients")
            action: Action name (e.g., "read", "write", "delete")

        Raises:
            HTTPException: 401 if not authenticated, 403 if no permission
        """
        user = self.require_auth()
        if not user.has_permission(resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}",
            )

    def require_role(self, role_name: str) -> None:
        """Check role, raising 403 if not in role.

        Args:
            role_name: Required role name

        Raises:
            HTTPException: 401 if not authenticated, 403 if not in role
        """
        user = self.require_auth()
        if not user.has_role(role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role_name}",
            )

    def require_admin(self) -> None:
        """Check admin role, raising 403 if not admin.

        Raises:
            HTTPException: 401 if not authenticated, 403 if not admin
        """
        self.require_role("admin")


async def get_authenticated_context(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RequestContext:
    """Dependency for authenticated endpoints.

    Use this for endpoints that require authentication.

    Args:
        db: Database session from get_db
        user: Authenticated user from get_current_user

    Returns:
        RequestContext with db and authenticated user
    """
    return RequestContext(db=db, user=user)


async def get_public_context(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser | None = Depends(get_current_user_optional),
) -> RequestContext:
    """Dependency for public endpoints with optional auth.

    Use this for endpoints that work both authenticated and
    unauthenticated, but may provide enhanced features when
    authenticated.

    Args:
        db: Database session from get_db
        user: Optional authenticated user

    Returns:
        RequestContext with db and optional user
    """
    return RequestContext(db=db, user=user)


async def get_db_only_context(
    db: AsyncSession = Depends(get_db),
) -> RequestContext:
    """Dependency for internal/service endpoints needing only DB.

    Use this for endpoints that don't need authentication
    (e.g., health checks, public data endpoints).

    Args:
        db: Database session from get_db

    Returns:
        RequestContext with db only (no user)
    """
    return RequestContext(db=db, user=None)


# Type aliases for cleaner endpoint signatures
AuthenticatedContext = Annotated[RequestContext, Depends(get_authenticated_context)]
PublicContext = Annotated[RequestContext, Depends(get_public_context)]
DbContext = Annotated[RequestContext, Depends(get_db_only_context)]

# Re-export commonly used types for convenience
DbSession = Annotated[AsyncSession, Depends(get_db)]

__all__ = [
    "RequestContext",
    "get_authenticated_context",
    "get_public_context",
    "get_db_only_context",
    "AuthenticatedContext",
    "PublicContext",
    "DbContext",
    "DbSession",
    "CurrentUser",
]
