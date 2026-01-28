"""Add policies, policy_sections, and policy_alert_rules tables.

Revision ID: 021
Revises: 020
Create Date: 2026-01-27

Adds tables for institutional policy management:
- policies: Policy documents with versioning and status
- policy_sections: Searchable sections with embeddings
- policy_alert_rules: Links policy sections to alert rules
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create policies table
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_organization", sa.String(500), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_policies_name", "policies", ["name"])
    op.create_index("ix_policies_status", "policies", ["status"])
    op.create_index("ix_policies_status_name", "policies", ["status", "name"])

    # Create policy_sections table
    op.create_table(
        "policy_sections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_number", sa.String(50), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("applies_to_conditions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("applies_to_measurements", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
    )
    op.create_index("ix_policy_sections_policy", "policy_sections", ["policy_id"])

    # Create policy_alert_rules table
    op.create_table(
        "policy_alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "policy_section_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("policy_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_rule_id", sa.String(255), nullable=False),
        sa.Column("mapping_confidence", sa.Float(), nullable=True),
        sa.Column("mapping_rationale", sa.Text(), nullable=True),
    )
    op.create_index("ix_policy_alert_rules_section_id", "policy_alert_rules", ["policy_section_id"])
    op.create_index("ix_policy_alert_rules_rule_id", "policy_alert_rules", ["alert_rule_id"])
    op.create_index(
        "ix_policy_alert_rules_section_rule",
        "policy_alert_rules",
        ["policy_section_id", "alert_rule_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_alert_rules_section_rule")
    op.drop_index("ix_policy_alert_rules_rule_id")
    op.drop_index("ix_policy_alert_rules_section_id")
    op.drop_table("policy_alert_rules")

    op.drop_index("ix_policy_sections_policy")
    op.drop_table("policy_sections")

    op.drop_index("ix_policies_status_name")
    op.drop_index("ix_policies_status")
    op.drop_index("ix_policies_name")
    op.drop_table("policies")
