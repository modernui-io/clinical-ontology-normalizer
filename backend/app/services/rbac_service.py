"""Role-Based Access Control (RBAC) service for permission management.

This service provides:
- Permission checking for users
- Role management (create, update, delete)
- Permission management
- User role assignment
- Default role/permission initialization

The RBAC system supports:
- Resource-based permissions (documents:read, patients:write, etc.)
- Multiple roles per user
- System roles that cannot be deleted
- Permission caching for performance

VP-Memory-1: Permission cache is bounded with TTL to prevent memory growth.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rbac import Permission, Role, RolePermission, User, UserRole

logger = logging.getLogger(__name__)


# =============================================================================
# VP-Memory-1: Bounded TTL Cache
# =============================================================================


class BoundedTTLCache:
    """Thread-safe bounded cache with TTL eviction.

    VP-Memory-1: Prevents unbounded memory growth by limiting cache size
    and automatically expiring entries after TTL.
    """

    def __init__(self, maxsize: int = 10000, ttl: float = 3600.0):
        """Initialize bounded TTL cache.

        Args:
            maxsize: Maximum number of entries
            ttl: Time-to-live in seconds for each entry
        """
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]
            if time.time() > expires_at:
                # Expired, remove it
                del self._cache[key]
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            expires_at = time.time() + self._ttl

            # If key exists, update it
            if key in self._cache:
                self._cache[key] = (value, expires_at)
                self._cache.move_to_end(key)
                return

            # Evict oldest if at capacity
            while len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)

            self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        """Return number of entries (may include expired)."""
        return len(self._cache)

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [
                k for k, (_, exp) in self._cache.items() if now > exp
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        return removed


class ResourceType(str, Enum):
    """Resource types for permission checking."""

    DOCUMENTS = "documents"
    PATIENTS = "patients"
    BILLING = "billing"
    CODING = "coding"
    AUDIT = "audit"
    ADMIN = "admin"
    VOCABULARY = "vocabulary"
    GRAPHS = "graphs"
    EXPORT = "export"
    LLM = "llm"


class ActionType(str, Enum):
    """Action types for permission checking."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXPORT = "export"


@dataclass
class PermissionCheck:
    """Result of a permission check."""

    allowed: bool
    user_id: str
    resource: str
    action: str
    roles: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass
class RoleInfo:
    """Role information with permissions."""

    id: str
    name: str
    description: str | None
    is_system_role: bool
    permissions: list[str]
    user_count: int = 0


@dataclass
class UserPermissions:
    """User's complete permission set."""

    user_id: str
    email: str
    roles: list[str]
    permissions: set[str]
    is_admin: bool = False


# Default roles and their permissions
DEFAULT_ROLES: dict[str, dict[str, Any]] = {
    "admin": {
        "description": "Full system access - can manage users, roles, and all data",
        "is_system_role": True,
        "permissions": [
            # Full access to all resources
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
    },
    "provider": {
        "description": "Clinical data access - can view and modify patient data",
        "is_system_role": True,
        "permissions": [
            # Clinical document access
            "documents:read", "documents:write",
            # Patient information access
            "patients:read", "patients:write",
            # Read billing/coding info but not modify
            "billing:read",
            "coding:read",
            # Vocabulary lookup
            "vocabulary:read",
            # Knowledge graph access
            "graphs:read", "graphs:write",
            # Export patient data
            "export:read", "export:write",
            # Use LLM features
            "llm:read", "llm:write",
        ],
    },
    "biller": {
        "description": "Billing and coding access - can manage billing codes and HCC analysis",
        "is_system_role": True,
        "permissions": [
            # Read clinical documents for coding
            "documents:read",
            # Read patient information for billing
            "patients:read",
            # Full billing access
            "billing:read", "billing:write",
            # Full coding access
            "coding:read", "coding:write",
            # Vocabulary for code lookup
            "vocabulary:read",
            # Export billing data
            "export:read", "export:write",
        ],
    },
    "viewer": {
        "description": "Read-only access - can view non-sensitive data",
        "is_system_role": True,
        "permissions": [
            # Read-only access to documents (no PHI by default)
            "documents:read",
            # Read vocabulary
            "vocabulary:read",
            # Read graphs
            "graphs:read",
        ],
    },
}

# All permissions that can be assigned
ALL_PERMISSIONS: dict[str, str] = {
    # Documents
    "documents:read": "View clinical documents",
    "documents:write": "Create and edit clinical documents",
    "documents:delete": "Delete clinical documents",
    "documents:admin": "Administer document settings",
    # Patients
    "patients:read": "View patient information",
    "patients:write": "Create and edit patient records",
    "patients:delete": "Delete patient records",
    "patients:admin": "Administer patient settings",
    # Billing
    "billing:read": "View billing information",
    "billing:write": "Create and edit billing records",
    "billing:delete": "Delete billing records",
    "billing:admin": "Administer billing settings",
    # Coding
    "coding:read": "View medical codes",
    "coding:write": "Assign and modify codes",
    "coding:delete": "Remove code assignments",
    "coding:admin": "Administer coding settings",
    # Audit
    "audit:read": "View audit logs",
    "audit:write": "Create audit entries",
    "audit:export": "Export audit logs",
    "audit:admin": "Administer audit settings",
    # Admin
    "admin:read": "View admin settings",
    "admin:write": "Modify admin settings",
    "admin:manage_users": "Manage user accounts",
    "admin:manage_roles": "Manage roles and permissions",
    # Vocabulary
    "vocabulary:read": "Search and view vocabulary terms",
    "vocabulary:write": "Add custom vocabulary terms",
    "vocabulary:admin": "Administer vocabulary settings",
    # Graphs
    "graphs:read": "View knowledge graphs",
    "graphs:write": "Modify knowledge graphs",
    "graphs:admin": "Administer graph settings",
    # Export
    "export:read": "View export jobs",
    "export:write": "Create export jobs",
    "export:admin": "Administer export settings",
    # LLM
    "llm:read": "Use LLM features (read)",
    "llm:write": "Use LLM features (generate)",
    "llm:admin": "Administer LLM settings",
}


class RBACService:
    """Service for Role-Based Access Control operations.

    This service manages roles, permissions, and user authorization.
    It provides methods for checking permissions, managing roles,
    and initializing the default RBAC configuration.
    """

    def __init__(self) -> None:
        """Initialize the RBAC service."""
        # VP-Memory-1: Bounded permission cache with TTL
        # Max 10k users, 1-hour TTL to prevent unbounded memory growth
        self._permission_cache = BoundedTTLCache(maxsize=10000, ttl=3600.0)

    def clear_cache(self, user_id: str | None = None) -> None:
        """Clear the permission cache.

        Args:
            user_id: Optional user ID to clear specific cache, or None to clear all
        """
        if user_id:
            self._permission_cache.delete(user_id)
        else:
            self._permission_cache.clear()

    # -------------------------------------------------------------------------
    # Permission Checking
    # -------------------------------------------------------------------------

    async def check_permission(
        self,
        db: AsyncSession,
        user_id: str,
        resource: str,
        action: str,
    ) -> PermissionCheck:
        """Check if a user has a specific permission.

        Args:
            db: Database session
            user_id: User ID to check
            resource: Resource type (e.g., 'documents', 'patients')
            action: Action type (e.g., 'read', 'write', 'delete')

        Returns:
            PermissionCheck with result and details
        """
        permission_name = f"{resource}:{action}"

        # Get user permissions (from cache or database)
        user_perms = await self.get_user_permissions(db, user_id)

        if user_perms is None:
            return PermissionCheck(
                allowed=False,
                user_id=user_id,
                resource=resource,
                action=action,
                reason="User not found",
            )

        # Admins have all permissions
        if user_perms.is_admin:
            return PermissionCheck(
                allowed=True,
                user_id=user_id,
                resource=resource,
                action=action,
                roles=user_perms.roles,
                reason="Admin access",
            )

        # Check specific permission
        allowed = permission_name in user_perms.permissions

        return PermissionCheck(
            allowed=allowed,
            user_id=user_id,
            resource=resource,
            action=action,
            roles=user_perms.roles,
            reason="Permission granted" if allowed else "Permission denied",
        )

    async def get_user_permissions(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> UserPermissions | None:
        """Get all permissions for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            UserPermissions with all roles and permissions, or None if user not found
        """
        # Check cache first
        cached_perms = self._permission_cache.get(user_id)
        if cached_perms is not None:
            # Need to get user info from DB for full response
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                return UserPermissions(
                    user_id=user_id,
                    email=user.email,
                    roles=[],  # Not cached
                    permissions=cached_perms,
                    is_admin="admin:manage_users" in cached_perms,
                )

        # Load from database
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(User.id == user_id, User.is_active == True)  # noqa: E712
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Collect roles and permissions
        roles: list[str] = []
        permissions: set[str] = set()

        for user_role in user.user_roles:
            roles.append(user_role.role.name)
            for role_perm in user_role.role.role_permissions:
                permissions.add(role_perm.permission.name)

        # Update cache
        self._permission_cache.set(user_id, permissions)

        is_admin = "admin" in roles or "admin:manage_users" in permissions

        return UserPermissions(
            user_id=user_id,
            email=user.email,
            roles=roles,
            permissions=permissions,
            is_admin=is_admin,
        )

    async def has_any_permission(
        self,
        db: AsyncSession,
        user_id: str,
        permissions: list[str],
    ) -> bool:
        """Check if user has any of the specified permissions.

        Args:
            db: Database session
            user_id: User ID
            permissions: List of permission names to check

        Returns:
            True if user has at least one permission
        """
        user_perms = await self.get_user_permissions(db, user_id)
        if not user_perms:
            return False
        if user_perms.is_admin:
            return True
        return bool(user_perms.permissions & set(permissions))

    async def has_all_permissions(
        self,
        db: AsyncSession,
        user_id: str,
        permissions: list[str],
    ) -> bool:
        """Check if user has all specified permissions.

        Args:
            db: Database session
            user_id: User ID
            permissions: List of permission names to check

        Returns:
            True if user has all permissions
        """
        user_perms = await self.get_user_permissions(db, user_id)
        if not user_perms:
            return False
        if user_perms.is_admin:
            return True
        return set(permissions).issubset(user_perms.permissions)

    # -------------------------------------------------------------------------
    # Role Management
    # -------------------------------------------------------------------------

    async def get_all_roles(self, db: AsyncSession) -> list[RoleInfo]:
        """Get all roles with their permissions and user counts.

        Args:
            db: Database session

        Returns:
            List of RoleInfo objects
        """
        stmt = (
            select(Role)
            .options(
                selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
        )
        result = await db.execute(stmt)
        roles = result.scalars().all()

        role_infos = []
        for role in roles:
            # Count users with this role
            count_stmt = select(func.count()).select_from(UserRole).where(
                UserRole.role_id == role.id
            )
            count_result = await db.execute(count_stmt)
            user_count = count_result.scalar() or 0

            permissions = [rp.permission.name for rp in role.role_permissions]

            role_infos.append(RoleInfo(
                id=role.id,
                name=role.name,
                description=role.description,
                is_system_role=role.is_system_role,
                permissions=permissions,
                user_count=user_count,
            ))

        return role_infos

    async def get_role_by_name(
        self,
        db: AsyncSession,
        role_name: str,
    ) -> Role | None:
        """Get a role by name with permissions loaded.

        Args:
            db: Database session
            role_name: Name of the role

        Returns:
            Role if found, None otherwise
        """
        stmt = (
            select(Role)
            .options(
                selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(Role.name == role_name)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_role(
        self,
        db: AsyncSession,
        name: str,
        description: str | None = None,
        permission_names: list[str] | None = None,
        is_system_role: bool = False,
    ) -> Role:
        """Create a new role.

        Args:
            db: Database session
            name: Unique role name
            description: Role description
            permission_names: List of permission names to assign
            is_system_role: Whether this is a system role

        Returns:
            Created Role instance

        Raises:
            ValueError: If role name already exists
        """
        # Check if role exists
        existing = await self.get_role_by_name(db, name)
        if existing:
            raise ValueError(f"Role '{name}' already exists")

        # Create role
        role = Role(
            name=name,
            description=description,
            is_system_role=is_system_role,
        )
        db.add(role)
        await db.flush()

        # Add permissions
        if permission_names:
            stmt = select(Permission).where(Permission.name.in_(permission_names))
            result = await db.execute(stmt)
            permissions = result.scalars().all()

            for perm in permissions:
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(role_perm)

        await db.commit()
        logger.info(f"Created role: {name}")
        return role

    async def update_role_permissions(
        self,
        db: AsyncSession,
        role_name: str,
        permission_names: list[str],
    ) -> Role | None:
        """Update a role's permissions.

        Args:
            db: Database session
            role_name: Name of the role to update
            permission_names: New list of permission names

        Returns:
            Updated Role or None if not found
        """
        role = await self.get_role_by_name(db, role_name)
        if not role:
            return None

        # Delete existing permissions
        stmt = delete(RolePermission).where(RolePermission.role_id == role.id)
        await db.execute(stmt)

        # Add new permissions
        if permission_names:
            stmt = select(Permission).where(Permission.name.in_(permission_names))
            result = await db.execute(stmt)
            permissions = result.scalars().all()

            for perm in permissions:
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(role_perm)

        await db.commit()

        # Clear all caches as role permissions changed
        self.clear_cache()

        logger.info(f"Updated permissions for role: {role_name}")
        return role

    async def delete_role(
        self,
        db: AsyncSession,
        role_name: str,
    ) -> bool:
        """Delete a role (system roles cannot be deleted).

        Args:
            db: Database session
            role_name: Name of the role to delete

        Returns:
            True if deleted, False if not found or is system role
        """
        role = await self.get_role_by_name(db, role_name)
        if not role:
            return False

        if role.is_system_role:
            logger.warning(f"Attempted to delete system role: {role_name}")
            return False

        await db.delete(role)
        await db.commit()

        # Clear all caches
        self.clear_cache()

        logger.info(f"Deleted role: {role_name}")
        return True

    # -------------------------------------------------------------------------
    # User Role Assignment
    # -------------------------------------------------------------------------

    async def assign_role_to_user(
        self,
        db: AsyncSession,
        user_id: str,
        role_name: str,
        assigned_by: str | None = None,
    ) -> bool:
        """Assign a role to a user.

        Args:
            db: Database session
            user_id: User ID
            role_name: Name of the role to assign
            assigned_by: ID of user making the assignment

        Returns:
            True if assigned, False if user/role not found or already assigned
        """
        # Get role
        role = await self.get_role_by_name(db, role_name)
        if not role:
            return False

        # Check user exists
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return False

        # Check if already assigned
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return False  # Already assigned

        # Create assignment
        user_role = UserRole(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by,
        )
        db.add(user_role)
        await db.commit()

        # Clear user's permission cache
        self.clear_cache(user_id)

        logger.info(f"Assigned role '{role_name}' to user {user_id}")
        return True

    async def remove_role_from_user(
        self,
        db: AsyncSession,
        user_id: str,
        role_name: str,
    ) -> bool:
        """Remove a role from a user.

        Args:
            db: Database session
            user_id: User ID
            role_name: Name of the role to remove

        Returns:
            True if removed, False if not assigned
        """
        # Get role
        role = await self.get_role_by_name(db, role_name)
        if not role:
            return False

        stmt = delete(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
        )
        result = await db.execute(stmt)
        await db.commit()

        # Clear user's permission cache
        self.clear_cache(user_id)

        if result.rowcount > 0:
            logger.info(f"Removed role '{role_name}' from user {user_id}")
            return True
        return False

    async def get_user_roles(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> list[RoleInfo]:
        """Get all roles assigned to a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of RoleInfo objects
        """
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .options(
                selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(UserRole.user_id == user_id)
        )
        result = await db.execute(stmt)
        roles = result.scalars().all()

        return [
            RoleInfo(
                id=role.id,
                name=role.name,
                description=role.description,
                is_system_role=role.is_system_role,
                permissions=[rp.permission.name for rp in role.role_permissions],
            )
            for role in roles
        ]

    async def set_user_roles(
        self,
        db: AsyncSession,
        user_id: str,
        role_names: list[str],
        assigned_by: str | None = None,
    ) -> bool:
        """Set a user's roles (replaces existing roles).

        Args:
            db: Database session
            user_id: User ID
            role_names: List of role names to assign
            assigned_by: ID of user making the assignment

        Returns:
            True if successful
        """
        # Check user exists
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return False

        # Get roles
        stmt = select(Role).where(Role.name.in_(role_names))
        result = await db.execute(stmt)
        roles = result.scalars().all()

        if len(roles) != len(role_names):
            found_names = {r.name for r in roles}
            missing = set(role_names) - found_names
            raise ValueError(f"Roles not found: {missing}")

        # Delete existing role assignments
        stmt = delete(UserRole).where(UserRole.user_id == user_id)
        await db.execute(stmt)

        # Create new assignments
        for role in roles:
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                assigned_by=assigned_by,
            )
            db.add(user_role)

        await db.commit()

        # Clear user's permission cache
        self.clear_cache(user_id)

        logger.info(f"Set roles for user {user_id}: {role_names}")
        return True

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    async def initialize_default_permissions(self, db: AsyncSession) -> int:
        """Initialize all default permissions in the database.

        Args:
            db: Database session

        Returns:
            Number of permissions created
        """
        created_count = 0

        for perm_name, description in ALL_PERMISSIONS.items():
            # Check if permission exists
            stmt = select(Permission).where(Permission.name == perm_name)
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                continue

            # Parse resource and action from name
            resource, action = perm_name.split(":", 1)

            perm = Permission(
                name=perm_name,
                resource=resource,
                action=action,
                description=description,
            )
            db.add(perm)
            created_count += 1

        await db.commit()
        logger.info(f"Initialized {created_count} default permissions")
        return created_count

    async def initialize_default_roles(self, db: AsyncSession) -> int:
        """Initialize all default roles with their permissions.

        Args:
            db: Database session

        Returns:
            Number of roles created
        """
        # First ensure permissions exist
        await self.initialize_default_permissions(db)

        created_count = 0

        for role_name, role_config in DEFAULT_ROLES.items():
            # Check if role exists
            existing = await self.get_role_by_name(db, role_name)
            if existing:
                continue

            # Create role
            role = Role(
                name=role_name,
                description=role_config["description"],
                is_system_role=role_config["is_system_role"],
            )
            db.add(role)
            await db.flush()

            # Add permissions
            perm_names = role_config["permissions"]
            stmt = select(Permission).where(Permission.name.in_(perm_names))
            result = await db.execute(stmt)
            permissions = result.scalars().all()

            for perm in permissions:
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(role_perm)

            created_count += 1

        await db.commit()
        logger.info(f"Initialized {created_count} default roles")
        return created_count

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats
        """
        return {
            "cache_size": len(self._permission_cache),
            "default_roles": list(DEFAULT_ROLES.keys()),
            "total_permissions_defined": len(ALL_PERMISSIONS),
        }


# Singleton instance
_rbac_service: RBACService | None = None


def get_rbac_service() -> RBACService:
    """Get the singleton RBACService instance.

    Returns:
        RBACService instance
    """
    global _rbac_service
    if _rbac_service is None:
        _rbac_service = RBACService()
    return _rbac_service


def reset_rbac_service() -> None:
    """Reset the singleton for testing."""
    global _rbac_service
    _rbac_service = None
