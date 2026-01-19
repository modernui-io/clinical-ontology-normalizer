"""Authentication API endpoints.

This module provides REST API endpoints for:
- POST /auth/login - Authenticate and get JWT tokens
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Invalidate refresh token
- GET /auth/me - Get current user information
- POST /auth/register - Register new user (admin only)
- POST /auth/change-password - Change user password

All authentication uses JWT tokens:
- Access tokens: Short-lived (30 min), used for API access
- Refresh tokens: Long-lived (7 days), used to get new access tokens
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth_middleware import (
    CurrentUser,
    get_current_user,
    require_admin,
)
from app.core.database import get_db
from app.services.auth_service import AuthService, get_auth_service
from app.services.rbac_service import RBACService, get_rbac_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Login request with email and password."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="Refresh token to exchange")


class LogoutRequest(BaseModel):
    """Logout request with refresh token."""

    refresh_token: str = Field(..., description="Refresh token to revoke")


class RegisterRequest(BaseModel):
    """User registration request (admin only)."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    name: str = Field(..., min_length=1, max_length=255, description="User display name")
    roles: list[str] = Field(
        default=["viewer"],
        description="List of role names to assign",
    )


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class UserResponse(BaseModel):
    """User information response."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User display name")
    is_active: bool = Field(..., description="Whether user is active")
    roles: list[str] = Field(..., description="Assigned role names")
    permissions: list[str] = Field(..., description="Effective permissions")


class MeResponse(BaseModel):
    """Current user information response."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    roles: list[str] = Field(..., description="Assigned role names")
    permissions: list[str] = Field(..., description="Effective permissions")
    is_admin: bool = Field(..., description="Whether user has admin role")


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT tokens",
    description="Authenticate with email and password to receive access and refresh tokens.",
)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Args:
        request: FastAPI request object
        login_data: Login credentials
        db: Database session
        auth_service: Authentication service

    Returns:
        TokenResponse with access and refresh tokens

    Raises:
        HTTPException: 401 if authentication fails
    """
    # Get client information for audit
    ip_address = request.client.host if request.client else None
    device_info = request.headers.get("user-agent")

    result = await auth_service.authenticate(
        db=db,
        email=login_data.email,
        password=login_data.password,
        ip_address=ip_address,
        device_info=device_info,
    )

    if not result.success:
        logger.info(f"Failed login attempt for: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error or "Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not result.tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        )

    logger.info(f"Successful login for: {login_data.email}")
    return TokenResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        token_type=result.tokens.token_type,
        expires_in=result.tokens.expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for new access and refresh tokens.",
)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Refresh access token using refresh token.

    This implements token rotation - the old refresh token is revoked
    and a new token pair is issued.

    Args:
        refresh_data: Refresh token
        db: Database session
        auth_service: Authentication service

    Returns:
        TokenResponse with new tokens

    Raises:
        HTTPException: 401 if refresh token is invalid or revoked
    """
    result = await auth_service.refresh_tokens(
        db=db,
        refresh_token=refresh_data.refresh_token,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error or "Token refresh failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not result.tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        )

    return TokenResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        token_type=result.tokens.token_type,
        expires_in=result.tokens.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke refresh token",
    description="Revoke the refresh token to prevent further use.",
)
async def logout(
    logout_data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """Logout user by revoking refresh token.

    Args:
        logout_data: Refresh token to revoke
        db: Database session
        auth_service: Authentication service
    """
    await auth_service.logout(
        db=db,
        refresh_token=logout_data.refresh_token,
    )
    # Always return success even if token not found (idempotent)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout from all devices",
    description="Revoke all refresh tokens for the current user.",
)
async def logout_all(
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Logout user from all devices by revoking all refresh tokens.

    Args:
        db: Database session
        auth_service: Authentication service
        current_user: Current authenticated user
    """
    count = await auth_service.logout_all_devices(
        db=db,
        user_id=current_user.id,
    )
    logger.info(f"Logged out user {current_user.email} from {count} devices")


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current user information",
    description="Get the authenticated user's information from the JWT token.",
)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> MeResponse:
    """Get current user information from JWT token.

    Args:
        current_user: Current authenticated user

    Returns:
        MeResponse with user information
    """
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        roles=current_user.roles,
        permissions=current_user.permissions,
        is_admin=current_user.is_admin(),
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user (admin only)",
    description="Create a new user account. Requires admin role.",
)
async def register_user(
    register_data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> UserResponse:
    """Register a new user (admin only).

    Args:
        register_data: User registration data
        db: Database session
        auth_service: Authentication service
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        UserResponse with created user information

    Raises:
        HTTPException: 400 if email exists or roles invalid
        HTTPException: 403 if not admin
    """
    try:
        user = await auth_service.create_user(
            db=db,
            email=register_data.email,
            password=register_data.password,
            name=register_data.name,
            role_names=register_data.roles,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Get user permissions
    user_perms = await rbac_service.get_user_permissions(db, user.id)
    permissions = list(user_perms.permissions) if user_perms else []

    logger.info(f"Admin {current_user.email} created user: {user.email}")
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        roles=register_data.roles,
        permissions=permissions,
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="Change the current user's password.",
)
async def change_password(
    password_data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Change the current user's password.

    This will revoke all existing refresh tokens for security.

    Args:
        password_data: Current and new password
        db: Database session
        auth_service: Authentication service
        current_user: Current authenticated user

    Raises:
        HTTPException: 400 if current password is wrong
    """
    success = await auth_service.update_password(
        db=db,
        user_id=current_user.id,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    logger.info(f"Password changed for user: {current_user.email}")


@router.post(
    "/initialize",
    summary="Initialize RBAC system",
    description="Initialize default roles and permissions. Admin only.",
)
async def initialize_rbac(
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service),
    current_user: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    """Initialize the RBAC system with default roles and permissions.

    This creates all default permissions and roles if they don't exist.
    Safe to call multiple times.

    Args:
        db: Database session
        rbac_service: RBAC service
        current_user: Current admin user

    Returns:
        Summary of initialized items
    """
    perm_count = await rbac_service.initialize_default_permissions(db)
    role_count = await rbac_service.initialize_default_roles(db)

    logger.info(
        f"RBAC initialized by {current_user.email}: "
        f"{perm_count} permissions, {role_count} roles"
    )

    return {
        "permissions_created": perm_count,
        "roles_created": role_count,
        "message": "RBAC system initialized successfully",
    }
