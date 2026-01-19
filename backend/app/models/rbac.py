"""SQLAlchemy models for Role-Based Access Control (RBAC).

This module implements a comprehensive RBAC system with:
- Users: System users with authentication credentials
- Roles: Named collections of permissions (admin, provider, biller, viewer)
- Permissions: Fine-grained access control (resource + action pairs)
- UserRole: Many-to-many relationship between users and roles
- RolePermission: Many-to-many relationship between roles and permissions

The RBAC system follows the principle of least privilege and supports:
- Multiple roles per user
- Hierarchical permission inheritance
- Resource-based access control (documents, patients, billing, etc.)
- Action-based permissions (read, write, delete, admin)
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    pass


class Permission(Base):
    """Fine-grained permission for resource access control.

    Permissions are defined as resource-action pairs:
    - resource: The type of resource (documents, patients, billing, etc.)
    - action: The allowed operation (read, write, delete, admin)

    Examples:
    - documents:read - View clinical documents
    - documents:write - Create/edit clinical documents
    - patients:read - View patient information
    - billing:write - Create/modify billing codes
    - admin:manage_users - User management access
    """

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Human-readable permission name",
    )
    resource: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Resource type (documents, patients, billing, admin, etc.)",
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Allowed action (read, write, delete, admin)",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of what this permission allows",
    )

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name={self.name}, resource={self.resource}, action={self.action})>"


class Role(Base):
    """Named role containing a set of permissions.

    Default roles:
    - admin: Full system access
    - provider: Clinical data access (documents, patients, clinical features)
    - biller: Billing and coding access (billing codes, HCC, claims)
    - viewer: Read-only access to non-sensitive data

    Roles can be customized by adding/removing permissions.
    Users can have multiple roles, and their effective permissions
    are the union of all role permissions.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique role name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the role's purpose",
    )
    is_system_role: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is a built-in system role",
    )

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name}, is_system_role={self.is_system_role})>"


class User(Base):
    """System user with authentication credentials.

    Users authenticate via email/password and are assigned roles
    that determine their permissions. User accounts can be deactivated
    (is_active=False) without deletion for audit trail purposes.

    Password hashing is handled by the AuthService using bcrypt.
    JWT tokens are used for stateless authentication.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="User email address (unique identifier)",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User's display name",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the user account is active",
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last successful login",
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last password change",
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of consecutive failed login attempts",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Account locked until this time (for brute force protection)",
    )

    # Relationships
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def roles(self) -> list[Role]:
        """Get list of roles assigned to this user."""
        return [ur.role for ur in self.user_roles]

    @property
    def permissions(self) -> set[str]:
        """Get set of all permission names from user's roles."""
        perms: set[str] = set()
        for user_role in self.user_roles:
            for role_perm in user_role.role.role_permissions:
                perms.add(role_perm.permission.name)
        return perms

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has a specific permission.

        Args:
            resource: Resource type (e.g., 'documents', 'patients')
            action: Action type (e.g., 'read', 'write', 'delete')

        Returns:
            True if user has the permission, False otherwise.
        """
        permission_name = f"{resource}:{action}"
        return permission_name in self.permissions

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role.

        Args:
            role_name: Name of the role to check

        Returns:
            True if user has the role, False otherwise.
        """
        return any(ur.role.name == role_name for ur in self.user_roles)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, is_active={self.is_active})>"


class UserRole(Base):
    """Many-to-many relationship between users and roles.

    Tracks which roles are assigned to which users, including
    metadata about when the assignment was made and by whom.
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who assigned this role",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When the role was assigned",
    )

    # Relationships
    user: Mapped[User] = relationship(
        back_populates="user_roles",
        foreign_keys=[user_id],
    )
    role: Mapped[Role] = relationship(
        back_populates="user_roles",
    )

    def __repr__(self) -> str:
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


class RolePermission(Base):
    """Many-to-many relationship between roles and permissions.

    Defines which permissions are included in each role.
    """

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    role_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    role: Mapped[Role] = relationship(
        back_populates="role_permissions",
    )
    permission: Mapped[Permission] = relationship(
        back_populates="role_permissions",
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"


class RefreshToken(Base):
    """Refresh token for JWT token rotation.

    Stores refresh tokens for users to enable token rotation
    and revocation. Each token has an expiration time and can
    be revoked by setting is_revoked=True.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash of the refresh token",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When the token expires",
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether the token has been revoked",
    )
    device_info: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent or device information",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address where token was issued",
    )

    # Relationships
    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"<RefreshToken(user_id={self.user_id}, expires_at={self.expires_at}, is_revoked={self.is_revoked})>"
