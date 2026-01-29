"""JWT token creation and validation utilities.

This module provides JWT token-related operations:
- Access token generation
- Refresh token generation
- Token pair creation
- Token decoding and validation

Security considerations:
- JWT tokens use HS256 algorithm
- Refresh tokens include unique JTI for revocation tracking
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

import jwt

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.rbac import User

logger = logging.getLogger(__name__)


# JWT Configuration - Use stable key from environment
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenType(str, Enum):
    """Type of JWT token."""

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds


@dataclass
class TokenPayload:
    """Decoded JWT token payload."""

    sub: str  # User ID
    email: str
    type: TokenType
    exp: datetime
    iat: datetime
    roles: list[str]
    permissions: list[str]


def create_access_token(
    user: "User",
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
    access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token for a user.

    Args:
        user: User to create token for
        secret_key: Secret key for JWT signing
        algorithm: JWT algorithm (HS256 or RS256)
        access_token_expire_minutes: Access token expiration in minutes
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT access token
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=access_token_expire_minutes)

    now = datetime.now(UTC)
    expire = now + expires_delta

    # Get user's roles and permissions
    roles = [ur.role.name for ur in user.user_roles]
    permissions: list[str] = []
    for ur in user.user_roles:
        for rp in ur.role.role_permissions:
            perm_name = rp.permission.name
            if perm_name not in permissions:
                permissions.append(perm_name)

    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "type": TokenType.ACCESS.value,
        "exp": expire,
        "iat": now,
        "roles": roles,
        "permissions": permissions,
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(
    user: "User",
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
    refresh_token_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS,
) -> str:
    """Create a refresh token for a user.

    Args:
        user: User to create token for
        secret_key: Secret key for JWT signing
        algorithm: JWT algorithm (HS256 or RS256)
        refresh_token_expire_days: Refresh token expiration in days

    Returns:
        Encoded JWT refresh token
    """
    expires_delta = timedelta(days=refresh_token_expire_days)
    now = datetime.now(UTC)
    expire = now + expires_delta

    # Generate a unique token ID for revocation tracking
    token_id = secrets.token_urlsafe(32)

    payload = {
        "sub": user.id,
        "email": user.email,
        "type": TokenType.REFRESH.value,
        "exp": expire,
        "iat": now,
        "jti": token_id,  # Token ID for revocation
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_token_pair(
    user: "User",
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
    access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
    refresh_token_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS,
) -> TokenPair:
    """Create both access and refresh tokens for a user.

    Args:
        user: User to create tokens for
        secret_key: Secret key for JWT signing
        algorithm: JWT algorithm (HS256 or RS256)
        access_token_expire_minutes: Access token expiration in minutes
        refresh_token_expire_days: Refresh token expiration in days

    Returns:
        TokenPair with access and refresh tokens
    """
    access_token = create_access_token(
        user,
        secret_key=secret_key,
        algorithm=algorithm,
        access_token_expire_minutes=access_token_expire_minutes,
    )
    refresh_token = create_refresh_token(
        user,
        secret_key=secret_key,
        algorithm=algorithm,
        refresh_token_expire_days=refresh_token_expire_days,
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_token_expire_minutes * 60,
    )


def decode_token(
    token: str,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Args:
        token: JWT token to decode
        secret_key: Secret key for JWT verification
        algorithm: JWT algorithm (HS256 or RS256)

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token: {e}")
        return None


def validate_access_token(
    token: str,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> TokenPayload | None:
    """Validate an access token and return its payload.

    Args:
        token: JWT access token to validate
        secret_key: Secret key for JWT verification
        algorithm: JWT algorithm (HS256 or RS256)

    Returns:
        TokenPayload if valid, None otherwise
    """
    payload = decode_token(token, secret_key=secret_key, algorithm=algorithm)
    if not payload:
        return None

    # Verify it's an access token
    if payload.get("type") != TokenType.ACCESS.value:
        return None

    return TokenPayload(
        sub=payload["sub"],
        email=payload["email"],
        type=TokenType.ACCESS,
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        roles=payload.get("roles", []),
        permissions=payload.get("permissions", []),
    )


def validate_refresh_token(
    token: str,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> dict[str, Any] | None:
    """Validate a refresh token.

    Args:
        token: JWT refresh token to validate
        secret_key: Secret key for JWT verification
        algorithm: JWT algorithm (HS256 or RS256)

    Returns:
        Token payload if valid, None otherwise
    """
    payload = decode_token(token, secret_key=secret_key, algorithm=algorithm)
    if not payload:
        return None

    # Verify it's a refresh token
    if payload.get("type") != TokenType.REFRESH.value:
        return None

    return payload
