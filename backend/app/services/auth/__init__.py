"""Authentication service package.

This package provides authentication functionality split into focused modules:
- auth_core: Main AuthService class for user authentication and management
- auth_tokens: JWT token creation and validation utilities
- auth_password: Password hashing and verification utilities

For backwards compatibility, the main classes and functions are re-exported here.
"""

from __future__ import annotations

from .auth_core import (
    AuthResult,
    AuthService,
    get_auth_service,
    reset_auth_service,
)
from .auth_password import (
    hash_password,
    verify_password,
)
from .auth_tokens import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
    TokenPair,
    TokenPayload,
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    validate_access_token,
    validate_refresh_token,
)

__all__ = [
    # Core service
    "AuthService",
    "AuthResult",
    "get_auth_service",
    "reset_auth_service",
    # Token types and data classes
    "TokenType",
    "TokenPair",
    "TokenPayload",
    # Token functions
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "validate_access_token",
    "validate_refresh_token",
    # Password functions
    "hash_password",
    "verify_password",
    # Constants
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
]
