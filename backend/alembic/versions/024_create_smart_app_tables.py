"""Create SMART on FHIR app tables.

Revision ID: 024
Revises: 023
Create Date: 2026-01-28

This migration creates tables for SMART on FHIR app registration:
- smart_apps: Registered OAuth2 client applications
- smart_authorization_codes: Authorization codes for OAuth2 authorization code flow

SMART on FHIR is a healthcare-specific authorization framework built on OAuth2
that enables secure, scoped access to FHIR APIs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create smart_apps table
    op.create_table(
        "smart_apps",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="OAuth2 client identifier (unique per app)",
        ),
        sa.Column(
            "client_secret_hash",
            sa.String(255),
            nullable=True,
            comment="Bcrypt hashed client secret (null for public clients)",
        ),
        sa.Column(
            "app_name",
            sa.String(255),
            nullable=False,
            comment="Human-readable application name",
        ),
        sa.Column(
            "redirect_uris",
            postgresql.JSON(),
            nullable=False,
            server_default="[]",
            comment="List of allowed OAuth2 redirect URIs",
        ),
        sa.Column(
            "scopes",
            postgresql.JSON(),
            nullable=False,
            server_default="[]",
            comment="List of allowed SMART on FHIR scopes",
        ),
        sa.Column(
            "grant_types",
            postgresql.JSON(),
            nullable=False,
            server_default='["authorization_code"]',
            comment="Allowed OAuth2 grant types",
        ),
        sa.Column(
            "launch_url",
            sa.String(2048),
            nullable=True,
            comment="EHR launch URL for embedded launch",
        ),
        sa.Column(
            "is_confidential",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Whether this is a confidential client (has client_secret)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Whether the app is currently active and can authorize",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Timestamp of last update",
        ),
    )
    op.create_index("ix_smart_apps_client_id", "smart_apps", ["client_id"], unique=True)
    op.create_index("ix_smart_apps_is_active", "smart_apps", ["is_active"])

    # Create smart_authorization_codes table
    op.create_table(
        "smart_authorization_codes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="The authorization code (cryptographically random)",
        ),
        sa.Column(
            "client_id",
            sa.String(255),
            sa.ForeignKey("smart_apps.client_id", ondelete="CASCADE"),
            nullable=False,
            comment="OAuth2 client identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User who authorized the request",
        ),
        sa.Column(
            "redirect_uri",
            sa.String(2048),
            nullable=False,
            comment="Redirect URI for this authorization",
        ),
        sa.Column(
            "scope",
            sa.Text(),
            nullable=False,
            comment="Space-separated list of granted scopes",
        ),
        sa.Column(
            "code_challenge",
            sa.String(128),
            nullable=True,
            comment="PKCE code challenge (base64url-encoded SHA256 of verifier)",
        ),
        sa.Column(
            "code_challenge_method",
            sa.String(10),
            nullable=True,
            comment="PKCE challenge method (S256)",
        ),
        sa.Column(
            "patient_id",
            sa.String(255),
            nullable=True,
            comment="EHR launch context: selected patient ID",
        ),
        sa.Column(
            "encounter_id",
            sa.String(255),
            nullable=True,
            comment="EHR launch context: selected encounter ID",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the authorization code expires",
        ),
        sa.Column(
            "is_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Whether the code has been exchanged for tokens",
        ),
    )
    op.create_index(
        "ix_smart_authorization_codes_code",
        "smart_authorization_codes",
        ["code"],
        unique=True,
    )
    op.create_index(
        "ix_smart_authorization_codes_client_id",
        "smart_authorization_codes",
        ["client_id"],
    )
    op.create_index(
        "ix_smart_authorization_codes_user_id",
        "smart_authorization_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_smart_authorization_codes_patient_id",
        "smart_authorization_codes",
        ["patient_id"],
    )
    op.create_index(
        "ix_smart_authorization_codes_encounter_id",
        "smart_authorization_codes",
        ["encounter_id"],
    )
    op.create_index(
        "ix_smart_authorization_codes_expires_at",
        "smart_authorization_codes",
        ["expires_at"],
    )
    op.create_index(
        "ix_smart_authorization_codes_is_used",
        "smart_authorization_codes",
        ["is_used"],
    )


def downgrade() -> None:
    # Drop smart_authorization_codes table and indexes
    op.drop_index("ix_smart_authorization_codes_is_used")
    op.drop_index("ix_smart_authorization_codes_expires_at")
    op.drop_index("ix_smart_authorization_codes_encounter_id")
    op.drop_index("ix_smart_authorization_codes_patient_id")
    op.drop_index("ix_smart_authorization_codes_user_id")
    op.drop_index("ix_smart_authorization_codes_client_id")
    op.drop_index("ix_smart_authorization_codes_code")
    op.drop_table("smart_authorization_codes")

    # Drop smart_apps table and indexes
    op.drop_index("ix_smart_apps_is_active")
    op.drop_index("ix_smart_apps_client_id")
    op.drop_table("smart_apps")
