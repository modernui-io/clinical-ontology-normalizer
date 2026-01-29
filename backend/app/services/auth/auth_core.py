"""Authentication service for user management and JWT token handling.

This service provides:
- User authentication (login/logout)
- JWT access and refresh token generation/validation
- User creation and management
- Token rotation and revocation
- Brute force protection

Security considerations:
- Passwords are hashed using bcrypt with salt
- JWT tokens use RS256 or HS256 algorithms
- Refresh tokens are stored hashed in database
- Account lockout after failed login attempts
- Token rotation on refresh
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rbac import RefreshToken, Role, User, UserRole

from .auth_password import hash_password, verify_password
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

logger = logging.getLogger(__name__)


# Brute force protection
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


@dataclass
class AuthResult:
    """Result of authentication attempt."""

    success: bool
    user: User | None = None
    tokens: TokenPair | None = None
    error: str | None = None


class AuthService:
    """Service for user authentication and JWT token management.

    This service handles all authentication-related operations including
    user login, token generation/validation, and user management.
    It uses bcrypt for password hashing and JWT for stateless authentication.
    """

    def __init__(
        self,
        secret_key: str = JWT_SECRET_KEY,
        algorithm: str = JWT_ALGORITHM,
        access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS,
    ) -> None:
        """Initialize the auth service.

        Args:
            secret_key: Secret key for JWT signing
            algorithm: JWT algorithm (HS256 or RS256)
            access_token_expire_minutes: Access token expiration in minutes
            refresh_token_expire_days: Refresh token expiration in days
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    # -------------------------------------------------------------------------
    # Password Hashing (delegated to auth_password module)
    # -------------------------------------------------------------------------

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Bcrypt hashed password string
        """
        return hash_password(password)

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain text password to verify
            hashed_password: Stored bcrypt hash

        Returns:
            True if password matches, False otherwise
        """
        return verify_password(password, hashed_password)

    # -------------------------------------------------------------------------
    # JWT Token Generation (delegated to auth_tokens module)
    # -------------------------------------------------------------------------

    def create_access_token(
        self,
        user: User,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token for a user.

        Args:
            user: User to create token for
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT access token
        """
        return create_access_token(
            user,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            expires_delta=expires_delta,
        )

    def create_refresh_token(self, user: User) -> str:
        """Create a refresh token for a user.

        Args:
            user: User to create token for

        Returns:
            Encoded JWT refresh token
        """
        return create_refresh_token(
            user,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            refresh_token_expire_days=self.refresh_token_expire_days,
        )

    def create_token_pair(self, user: User) -> TokenPair:
        """Create both access and refresh tokens for a user.

        Args:
            user: User to create tokens for

        Returns:
            TokenPair with access and refresh tokens
        """
        return create_token_pair(
            user,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            refresh_token_expire_days=self.refresh_token_expire_days,
        )

    # -------------------------------------------------------------------------
    # JWT Token Validation (delegated to auth_tokens module)
    # -------------------------------------------------------------------------

    def decode_token(self, token: str) -> dict[str, Any] | None:
        """Decode and validate a JWT token.

        Args:
            token: JWT token to decode

        Returns:
            Decoded token payload or None if invalid
        """
        return decode_token(
            token,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
        )

    def validate_access_token(self, token: str) -> TokenPayload | None:
        """Validate an access token and return its payload.

        Args:
            token: JWT access token to validate

        Returns:
            TokenPayload if valid, None otherwise
        """
        return validate_access_token(
            token,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
        )

    def validate_refresh_token(self, token: str) -> dict[str, Any] | None:
        """Validate a refresh token.

        Args:
            token: JWT refresh token to validate

        Returns:
            Token payload if valid, None otherwise
        """
        return validate_refresh_token(
            token,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
        )

    # -------------------------------------------------------------------------
    # User Authentication
    # -------------------------------------------------------------------------

    async def authenticate(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> AuthResult:
        """Authenticate a user with email and password.

        Args:
            db: Database session
            email: User's email address
            password: Plain text password
            ip_address: Client IP address (for audit)
            device_info: Client device info (for audit)

        Returns:
            AuthResult with success status, user, and tokens
        """
        # Find user by email with roles and permissions loaded
        from app.models.rbac import RolePermission
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(User.email == email)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.info(f"Login attempt for unknown email: {email}")
            return AuthResult(success=False, error="Invalid email or password")

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            logger.warning(f"Login attempt for locked account: {email}")
            return AuthResult(
                success=False,
                error=f"Account is locked. Try again after {user.locked_until.isoformat()}",
            )

        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt for inactive account: {email}")
            return AuthResult(success=False, error="Account is deactivated")

        # Verify password
        if not self.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                logger.warning(f"Account locked due to failed attempts: {email}")
            await db.commit()

            logger.info(f"Failed login attempt for: {email}")
            return AuthResult(success=False, error="Invalid email or password")

        # Successful login - reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        await db.commit()

        # Create tokens
        tokens = self.create_token_pair(user)

        # Store refresh token hash in database
        await self._store_refresh_token(
            db, user, tokens.refresh_token, ip_address, device_info
        )

        logger.info(f"Successful login for: {email}")
        return AuthResult(success=True, user=user, tokens=tokens)

    async def _store_refresh_token(
        self,
        db: AsyncSession,
        user: User,
        refresh_token: str,
        ip_address: str | None,
        device_info: str | None,
    ) -> RefreshToken:
        """Store a refresh token hash in the database.

        Args:
            db: Database session
            user: User the token belongs to
            refresh_token: The refresh token to store
            ip_address: Client IP address
            device_info: Client device information

        Returns:
            Created RefreshToken record
        """
        # Hash the token for storage
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Decode to get expiration
        payload = self.decode_token(refresh_token)
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if payload else datetime.now(timezone.utc)

        token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            device_info=device_info,
        )
        db.add(token_record)
        await db.commit()
        return token_record

    async def refresh_tokens(
        self,
        db: AsyncSession,
        refresh_token: str,
    ) -> AuthResult:
        """Refresh access token using a refresh token.

        This implements token rotation - the old refresh token is
        revoked and a new token pair is issued.

        Args:
            db: Database session
            refresh_token: Current refresh token

        Returns:
            AuthResult with new token pair
        """
        # Validate refresh token
        payload = self.validate_refresh_token(refresh_token)
        if not payload:
            return AuthResult(success=False, error="Invalid or expired refresh token")

        # Check if token is revoked
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            logger.warning(f"Attempted use of revoked refresh token for user: {payload['sub']}")
            return AuthResult(success=False, error="Token has been revoked")

        # Get user with roles
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
            )
            .where(User.id == payload["sub"])
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return AuthResult(success=False, error="User not found or inactive")

        # Revoke old refresh token
        token_record.is_revoked = True

        # Create new token pair
        tokens = self.create_token_pair(user)

        # Store new refresh token
        await self._store_refresh_token(
            db, user, tokens.refresh_token,
            token_record.ip_address, token_record.device_info
        )

        logger.info(f"Token refreshed for user: {user.email}")
        return AuthResult(success=True, user=user, tokens=tokens)

    async def logout(
        self,
        db: AsyncSession,
        refresh_token: str,
    ) -> bool:
        """Logout user by revoking their refresh token.

        Args:
            db: Database session
            refresh_token: Refresh token to revoke

        Returns:
            True if logout successful, False otherwise
        """
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount > 0

    async def logout_all_devices(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> int:
        """Logout user from all devices by revoking all refresh tokens.

        Args:
            db: Database session
            user_id: User ID to logout

        Returns:
            Number of tokens revoked
        """
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.commit()

        logger.info(f"Logged out user {user_id} from all devices ({result.rowcount} tokens)")
        return result.rowcount

    # -------------------------------------------------------------------------
    # User Management
    # -------------------------------------------------------------------------

    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        name: str,
        role_names: list[str] | None = None,
        created_by: str | None = None,
    ) -> User:
        """Create a new user with optional roles.

        Args:
            db: Database session
            email: User's email address
            password: Plain text password (will be hashed)
            name: User's display name
            role_names: List of role names to assign
            created_by: ID of user creating this account

        Returns:
            Created User instance

        Raises:
            ValueError: If email already exists or roles not found
        """
        # Check if email already exists
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"User with email {email} already exists")

        # Create user
        user = User(
            email=email,
            name=name,
            hashed_password=self.hash_password(password),
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()  # Get user ID

        # Assign roles
        if role_names:
            stmt = select(Role).where(Role.name.in_(role_names))
            result = await db.execute(stmt)
            roles = result.scalars().all()

            if len(roles) != len(role_names):
                found_names = {r.name for r in roles}
                missing = set(role_names) - found_names
                raise ValueError(f"Roles not found: {missing}")

            for role in roles:
                user_role = UserRole(
                    user_id=user.id,
                    role_id=role.id,
                    assigned_by=created_by,
                )
                db.add(user_role)

        await db.commit()
        await db.refresh(user)

        logger.info(f"Created user: {email} with roles: {role_names}")
        return user

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> User | None:
        """Get a user by ID with roles loaded.

        Args:
            db: Database session
            user_id: User ID to find

        Returns:
            User if found, None otherwise
        """
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
            )
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> User | None:
        """Get a user by email with roles loaded.

        Args:
            db: Database session
            email: User email to find

        Returns:
            User if found, None otherwise
        """
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
            )
            .where(User.email == email)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_password(
        self,
        db: AsyncSession,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Update a user's password.

        Args:
            db: Database session
            user_id: User ID
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password updated, False if current password wrong
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return False

        if not self.verify_password(current_password, user.hashed_password):
            return False

        user.hashed_password = self.hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)

        # Revoke all existing refresh tokens for security
        await self.logout_all_devices(db, user_id)

        await db.commit()
        logger.info(f"Password updated for user: {user.email}")
        return True

    async def deactivate_user(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> bool:
        """Deactivate a user account.

        Args:
            db: Database session
            user_id: User ID to deactivate

        Returns:
            True if deactivated, False if user not found
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return False

        user.is_active = False

        # Revoke all refresh tokens
        await self.logout_all_devices(db, user_id)

        await db.commit()
        logger.info(f"Deactivated user: {user.email}")
        return True

    async def reactivate_user(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> bool:
        """Reactivate a deactivated user account.

        Args:
            db: Database session
            user_id: User ID to reactivate

        Returns:
            True if reactivated, False if user not found
        """
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return False

        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None

        await db.commit()
        logger.info(f"Reactivated user: {user.email}")
        return True


# Singleton instance
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get the singleton AuthService instance.

    Returns:
        AuthService instance
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def reset_auth_service() -> None:
    """Reset the singleton for testing."""
    global _auth_service
    _auth_service = None
