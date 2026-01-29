"""User management API endpoints.

This module provides REST API endpoints for:
- GET /users - List all users
- GET /users/{id} - Get user by ID
- PUT /users/{id}/roles - Update user roles
- DELETE /users/{id} - Deactivate user
- POST /users/{id}/reactivate - Reactivate user
- GET /users/{id}/permissions - Get user's effective permissions

These endpoints require admin role for access.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.middleware.auth_middleware import (
    CurrentUser,
    get_current_user,
    require_admin,
)
from app.core.database import get_db
from app.models.rbac import Role, User, UserRole
from app.services.auth import AuthService, get_auth_service
from app.services.rbac_service import RBACService, RoleInfo, get_rbac_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class UserSummary(BaseModel):
    """Brief user information for list responses."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User display name")
    is_active: bool = Field(..., description="Whether user is active")
    roles: list[str] = Field(..., description="Assigned role names")
    last_login: str | None = Field(None, description="Last login timestamp")


class UserDetail(BaseModel):
    """Detailed user information."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User display name")
    is_active: bool = Field(..., description="Whether user is active")
    roles: list[str] = Field(..., description="Assigned role names")
    permissions: list[str] = Field(..., description="Effective permissions")
    created_at: str = Field(..., description="Account creation timestamp")
    last_login: str | None = Field(None, description="Last login timestamp")
    failed_login_attempts: int = Field(0, description="Failed login attempts")
    is_locked: bool = Field(False, description="Whether account is locked")


class UserListResponse(BaseModel):
    """Paginated list of users."""

    users: list[UserSummary] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class UpdateRolesRequest(BaseModel):
    """Request to update user's roles."""

    roles: list[str] = Field(..., description="List of role names to assign")


class RoleResponse(BaseModel):
    """Role information."""

    id: str = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: str | None = Field(None, description="Role description")
    is_system_role: bool = Field(..., description="Whether this is a system role")
    permissions: list[str] = Field(..., description="Permissions in this role")
    user_count: int = Field(0, description="Number of users with this role")


class PermissionsResponse(BaseModel):
    """User permissions response."""

    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    roles: list[str] = Field(..., description="Assigned roles")
    permissions: list[str] = Field(..., description="Effective permissions")
    is_admin: bool = Field(..., description="Whether user has admin role")


# -------------------------------------------------------------------------
# User Endpoints
# -------------------------------------------------------------------------


@router.get(
    "",
    response_model=UserListResponse,
    summary="List all users",
    description="Get a paginated list of all users. Requires admin role.",
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include inactive users"),
    search: str | None = Query(None, description="Search by email or name"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> UserListResponse:
    """List all users with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        include_inactive: Whether to include deactivated users
        search: Optional search term for email or name
        db: Database session
        current_user: Current admin user

    Returns:
        Paginated list of users
    """
    # Build query
    stmt = select(User).options(
        selectinload(User.user_roles).selectinload(UserRole.role)
    )

    if not include_inactive:
        stmt = stmt.where(User.is_active == True)  # noqa: E712

    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            (User.email.ilike(search_filter)) | (User.name.ilike(search_filter))
        )

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size).order_by(User.email)

    result = await db.execute(stmt)
    users = result.scalars().all()

    # Convert to response
    user_summaries = []
    for user in users:
        roles = [ur.role.name for ur in user.user_roles]
        user_summaries.append(UserSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            roles=roles,
            last_login=user.last_login.isoformat() if user.last_login else None,
        ))

    total_pages = (total + page_size - 1) // page_size

    return UserListResponse(
        users=user_summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{user_id}",
    response_model=UserDetail,
    summary="Get user by ID",
    description="Get detailed user information. Requires admin role.",
)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> UserDetail:
    """Get detailed user information by ID.

    Args:
        user_id: User ID to retrieve
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        Detailed user information

    Raises:
        HTTPException: 404 if user not found
    """
    stmt = (
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Get permissions
    user_perms = await rbac_service.get_user_permissions(db, user_id)
    permissions = list(user_perms.permissions) if user_perms else []

    roles = [ur.role.name for ur in user.user_roles]
    is_locked = (
        user.locked_until is not None
        and user.locked_until > __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
    )

    return UserDetail(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        roles=roles,
        permissions=permissions,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
        failed_login_attempts=user.failed_login_attempts,
        is_locked=is_locked,
    )


@router.put(
    "/{user_id}/roles",
    response_model=UserDetail,
    summary="Update user roles",
    description="Update the roles assigned to a user. Requires admin role.",
)
async def update_user_roles(
    user_id: str,
    roles_data: UpdateRolesRequest,
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> UserDetail:
    """Update the roles assigned to a user.

    Args:
        user_id: User ID to update
        roles_data: New roles to assign
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        Updated user information

    Raises:
        HTTPException: 404 if user not found
        HTTPException: 400 if roles are invalid
    """
    # Prevent admin from removing their own admin role
    if user_id == current_user.id and "admin" not in roles_data.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin role",
        )

    try:
        success = await rbac_service.set_user_roles(
            db=db,
            user_id=user_id,
            role_names=roles_data.roles,
            assigned_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    logger.info(
        f"Admin {current_user.email} updated roles for user {user_id}: {roles_data.roles}"
    )

    # Return updated user
    return await get_user(user_id, db, rbac_service, current_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate user",
    description="Deactivate a user account. Requires admin role.",
)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    current_user: CurrentUser = Depends(require_admin),
) -> None:
    """Deactivate a user account.

    Deactivated users cannot log in but their data is preserved
    for audit purposes.

    Args:
        user_id: User ID to deactivate
        db: Database session
        auth_service: Authentication service
        current_user: Current admin user

    Raises:
        HTTPException: 404 if user not found
        HTTPException: 400 if trying to deactivate self
    """
    # Prevent self-deactivation
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    success = await auth_service.deactivate_user(db, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    logger.info(f"Admin {current_user.email} deactivated user {user_id}")


@router.post(
    "/{user_id}/reactivate",
    response_model=UserDetail,
    summary="Reactivate user",
    description="Reactivate a deactivated user account. Requires admin role.",
)
async def reactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> UserDetail:
    """Reactivate a deactivated user account.

    Args:
        user_id: User ID to reactivate
        db: Database session
        auth_service: Authentication service
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        Reactivated user information

    Raises:
        HTTPException: 404 if user not found
    """
    success = await auth_service.reactivate_user(db, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    logger.info(f"Admin {current_user.email} reactivated user {user_id}")

    return await get_user(user_id, db, rbac_service, current_user)


@router.get(
    "/{user_id}/permissions",
    response_model=PermissionsResponse,
    summary="Get user permissions",
    description="Get a user's effective permissions. Requires admin role.",
)
async def get_user_permissions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> PermissionsResponse:
    """Get a user's effective permissions from all roles.

    Args:
        user_id: User ID to check
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        User's roles and permissions

    Raises:
        HTTPException: 404 if user not found
    """
    user_perms = await rbac_service.get_user_permissions(db, user_id)

    if not user_perms:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found or inactive",
        )

    return PermissionsResponse(
        user_id=user_perms.user_id,
        email=user_perms.email,
        roles=user_perms.roles,
        permissions=list(user_perms.permissions),
        is_admin=user_perms.is_admin,
    )


# -------------------------------------------------------------------------
# Role Endpoints
# -------------------------------------------------------------------------


@router.get(
    "/roles/all",
    response_model=list[RoleResponse],
    summary="List all roles",
    description="Get all available roles with their permissions. Requires admin role.",
)
async def list_roles(
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> list[RoleResponse]:
    """List all available roles.

    Args:
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        List of all roles
    """
    roles = await rbac_service.get_all_roles(db)

    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            permissions=role.permissions,
            user_count=role.user_count,
        )
        for role in roles
    ]


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom role",
    description="Create a new custom role. Requires admin role.",
)
async def create_role(
    role_data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> RoleResponse:
    """Create a new custom role.

    Args:
        role_data: Role data with name, description, and permissions
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        Created role information

    Raises:
        HTTPException: 400 if role name exists
    """
    try:
        role = await rbac_service.create_role(
            db=db,
            name=role_data["name"],
            description=role_data.get("description"),
            permission_names=role_data.get("permissions", []),
            is_system_role=False,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.info(f"Admin {current_user.email} created role: {role.name}")

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        permissions=role_data.get("permissions", []),
        user_count=0,
    )


@router.delete(
    "/roles/{role_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete custom role",
    description="Delete a custom role. System roles cannot be deleted. Requires admin role.",
)
async def delete_role(
    role_name: str,
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> None:
    """Delete a custom role.

    System roles (admin, provider, biller, viewer) cannot be deleted.

    Args:
        role_name: Name of the role to delete
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Raises:
        HTTPException: 404 if role not found
        HTTPException: 400 if trying to delete system role
    """
    role = await rbac_service.get_role_by_name(db, role_name)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' not found",
        )

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles",
        )

    await rbac_service.delete_role(db, role_name)
    logger.info(f"Admin {current_user.email} deleted role: {role_name}")
