"""Create RBAC (Role-Based Access Control) tables.

Revision ID: 016
Revises: 015
Create Date: 2026-01-18

This migration creates tables for the RBAC system:
- permissions: Fine-grained permissions (resource:action pairs)
- roles: Named collections of permissions
- users: System users with authentication credentials
- user_roles: Many-to-many relationship between users and roles
- role_permissions: Many-to-many relationship between roles and permissions
- refresh_tokens: JWT refresh token storage for token rotation

Default roles created:
- admin: Full system access
- provider: Clinical data access
- biller: Billing and coding access
- viewer: Read-only access
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016b"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create permissions table
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"])
    op.create_index("ix_permissions_resource", "permissions", ["resource"])
    op.create_index("ix_permissions_action", "permissions", ["action"])

    # Create roles table
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False, default=False),
    )
    op.create_index("ix_roles_name", "roles", ["name"])

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, default=0),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # Create user_roles junction table
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    # Create role_permissions junction table
    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, default=False),
        sa.Column("device_info", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_is_revoked", "refresh_tokens", ["is_revoked"])

    # Insert default permissions
    permissions_data = [
        # Documents
        ("documents:read", "documents", "read", "View clinical documents"),
        ("documents:write", "documents", "write", "Create and edit clinical documents"),
        ("documents:delete", "documents", "delete", "Delete clinical documents"),
        ("documents:admin", "documents", "admin", "Administer document settings"),
        # Patients
        ("patients:read", "patients", "read", "View patient information"),
        ("patients:write", "patients", "write", "Create and edit patient records"),
        ("patients:delete", "patients", "delete", "Delete patient records"),
        ("patients:admin", "patients", "admin", "Administer patient settings"),
        # Billing
        ("billing:read", "billing", "read", "View billing information"),
        ("billing:write", "billing", "write", "Create and edit billing records"),
        ("billing:delete", "billing", "delete", "Delete billing records"),
        ("billing:admin", "billing", "admin", "Administer billing settings"),
        # Coding
        ("coding:read", "coding", "read", "View medical codes"),
        ("coding:write", "coding", "write", "Assign and modify codes"),
        ("coding:delete", "coding", "delete", "Remove code assignments"),
        ("coding:admin", "coding", "admin", "Administer coding settings"),
        # Audit
        ("audit:read", "audit", "read", "View audit logs"),
        ("audit:write", "audit", "write", "Create audit entries"),
        ("audit:export", "audit", "export", "Export audit logs"),
        ("audit:admin", "audit", "admin", "Administer audit settings"),
        # Admin
        ("admin:read", "admin", "read", "View admin settings"),
        ("admin:write", "admin", "write", "Modify admin settings"),
        ("admin:manage_users", "admin", "manage_users", "Manage user accounts"),
        ("admin:manage_roles", "admin", "manage_roles", "Manage roles and permissions"),
        # Vocabulary
        ("vocabulary:read", "vocabulary", "read", "Search and view vocabulary terms"),
        ("vocabulary:write", "vocabulary", "write", "Add custom vocabulary terms"),
        ("vocabulary:admin", "vocabulary", "admin", "Administer vocabulary settings"),
        # Graphs
        ("graphs:read", "graphs", "read", "View knowledge graphs"),
        ("graphs:write", "graphs", "write", "Modify knowledge graphs"),
        ("graphs:admin", "graphs", "admin", "Administer graph settings"),
        # Export
        ("export:read", "export", "read", "View export jobs"),
        ("export:write", "export", "write", "Create export jobs"),
        ("export:admin", "export", "admin", "Administer export settings"),
        # LLM
        ("llm:read", "llm", "read", "Use LLM features (read)"),
        ("llm:write", "llm", "write", "Use LLM features (generate)"),
        ("llm:admin", "llm", "admin", "Administer LLM settings"),
    ]

    # Create a mapping of permission names to UUIDs
    perm_ids = {}
    for name, resource, action, description in permissions_data:
        perm_id = str(uuid4())
        perm_ids[name] = perm_id
        op.execute(
            f"""
            INSERT INTO permissions (id, name, resource, action, description)
            VALUES ('{perm_id}', '{name}', '{resource}', '{action}', '{description}')
            """
        )

    # Insert default roles
    roles_data = {
        "admin": {
            "description": "Full system access - can manage users, roles, and all data",
            "permissions": list(perm_ids.keys()),  # All permissions
        },
        "provider": {
            "description": "Clinical data access - can view and modify patient data",
            "permissions": [
                "documents:read", "documents:write",
                "patients:read", "patients:write",
                "billing:read",
                "coding:read",
                "vocabulary:read",
                "graphs:read", "graphs:write",
                "export:read", "export:write",
                "llm:read", "llm:write",
            ],
        },
        "biller": {
            "description": "Billing and coding access - can manage billing codes and HCC analysis",
            "permissions": [
                "documents:read",
                "patients:read",
                "billing:read", "billing:write",
                "coding:read", "coding:write",
                "vocabulary:read",
                "export:read", "export:write",
            ],
        },
        "viewer": {
            "description": "Read-only access - can view non-sensitive data",
            "permissions": [
                "documents:read",
                "vocabulary:read",
                "graphs:read",
            ],
        },
    }

    # Create roles and their permissions
    for role_name, role_config in roles_data.items():
        role_id = str(uuid4())
        op.execute(
            f"""
            INSERT INTO roles (id, name, description, is_system_role)
            VALUES ('{role_id}', '{role_name}', '{role_config["description"]}', true)
            """
        )

        # Add role permissions
        for perm_name in role_config["permissions"]:
            if perm_name in perm_ids:
                rp_id = str(uuid4())
                op.execute(
                    f"""
                    INSERT INTO role_permissions (id, role_id, permission_id)
                    VALUES ('{rp_id}', '{role_id}', '{perm_ids[perm_name]}')
                    """
                )


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_index("ix_refresh_tokens_is_revoked")
    op.drop_index("ix_refresh_tokens_expires_at")
    op.drop_index("ix_refresh_tokens_token_hash")
    op.drop_index("ix_refresh_tokens_user_id")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_role_permissions_permission_id")
    op.drop_index("ix_role_permissions_role_id")
    op.drop_table("role_permissions")

    op.drop_index("ix_user_roles_role_id")
    op.drop_index("ix_user_roles_user_id")
    op.drop_table("user_roles")

    op.drop_index("ix_users_is_active")
    op.drop_index("ix_users_email")
    op.drop_table("users")

    op.drop_index("ix_roles_name")
    op.drop_table("roles")

    op.drop_index("ix_permissions_action")
    op.drop_index("ix_permissions_resource")
    op.drop_index("ix_permissions_name")
    op.drop_table("permissions")
