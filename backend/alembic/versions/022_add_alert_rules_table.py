"""Add alert_rules table with default rules.

Revision ID: 022
Revises: 021
Create Date: 2026-01-27

Persists alert rules to the database so they survive server restarts.
Seeds 4 default rules matching the in-memory defaults.
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("category", sa.String(50), nullable=False, server_default="risk_score"),
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("policy_section_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_alert_rules_name", "alert_rules", ["name"])
    op.create_index("ix_alert_rules_policy_section_id", "alert_rules", ["policy_section_id"])

    # Seed 4 default rules
    op.execute(
        sa.text("""
        INSERT INTO alert_rules (id, name, description, severity, category, conditions, enabled, created_by)
        VALUES
        (:id1, 'High Readmission Risk', 'Alert when 30-day readmission risk exceeds threshold', 'high', 'risk_score',
         :cond1, true, 'system'),
        (:id2, 'Critical Lab Value', 'Alert on critical laboratory values', 'critical', 'lab_value',
         :cond2, true, 'system'),
        (:id3, 'Mortality Risk Escalation', 'Alert when mortality risk tier changes to high', 'high', 'risk_score',
         :cond3, true, 'system'),
        (:id4, 'Quality Gap Identified', 'Alert when patient has open quality care gap', 'medium', 'quality_gap',
         :cond4, true, 'system')
        """),
        {
            "id1": str(uuid4()),
            "id2": str(uuid4()),
            "id3": str(uuid4()),
            "id4": str(uuid4()),
            "cond1": '{"rules": [{"field": "readmission_risk_score", "operator": "gte", "value": 0.7}]}',
            "cond2": '{"rules": [{"field": "potassium", "operator": "gt", "value": 6.5}]}',
            "cond3": '{"rules": [{"field": "mortality_risk_tier", "operator": "eq", "value": "high"}]}',
            "cond4": '{"rules": [{"field": "open_quality_gaps", "operator": "gt", "value": 0}]}',
        },
    )


def downgrade() -> None:
    op.drop_index("ix_alert_rules_policy_section_id")
    op.drop_index("ix_alert_rules_name")
    op.drop_table("alert_rules")
