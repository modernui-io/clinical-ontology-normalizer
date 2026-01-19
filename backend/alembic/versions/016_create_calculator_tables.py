"""Create custom_calculators and calculator_results tables.

Revision ID: 016
Revises: 015
Create Date: 2026-01-18

This migration creates tables for custom clinical calculators:
- custom_calculators: User-defined calculator definitions with formulas
- calculator_results: Execution results for audit trail

The calculator system supports:
- Safe formula evaluation using a DSL
- Input validation with type and range constraints
- Result interpretation with risk levels
- Audit trail for HIPAA compliance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create custom_calculators table
    op.create_table(
        "custom_calculators",
        # Primary key (inherited from Base)
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Basic information
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Formula using safe DSL
        sa.Column("formula", sa.Text(), nullable=False),
        # Output configuration
        sa.Column("output_type", sa.String(50), nullable=False, default="number"),
        sa.Column("output_unit", sa.String(50), nullable=True),
        # Interpretation rules (JSONB array)
        # Format: [{"min": 0, "max": 18.5, "label": "Underweight", "risk_level": "moderate"}, ...]
        sa.Column("interpretation_rules", postgresql.JSONB(), nullable=True),
        # Input definitions (JSONB array)
        # Format: [{"name": "weight", "type": "number", "label": "Weight", "unit": "kg", ...}, ...]
        sa.Column("inputs", postgresql.JSONB(), nullable=False, server_default="[]"),
        # Recommendations by risk level (JSONB object)
        sa.Column("recommendations", postgresql.JSONB(), nullable=True),
        # References/citations (JSONB array)
        sa.Column("references", postgresql.JSONB(), nullable=True),
        # Metadata
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, default=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # Category/tags
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
    )

    # Create indexes for custom_calculators
    op.create_index("ix_custom_calculators_name", "custom_calculators", ["name"])
    op.create_index("ix_custom_calculators_category", "custom_calculators", ["category"])
    op.create_index("ix_custom_calculators_is_active", "custom_calculators", ["is_active"])
    op.create_index("ix_custom_calculators_is_builtin", "custom_calculators", ["is_builtin"])
    op.create_index("ix_custom_calculators_created_by", "custom_calculators", ["created_by"])
    op.create_index(
        "ix_custom_calculators_category_active",
        "custom_calculators",
        ["category", "is_active"],
    )

    # Create calculator_results table
    op.create_table(
        "calculator_results",
        # Primary key (inherited from Base)
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Link to calculator
        sa.Column("calculator_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("calculator_name", sa.String(255), nullable=False),
        # Patient context (optional)
        sa.Column("patient_id", sa.String(255), nullable=True),
        # Input values used (JSONB object)
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        # Computed result
        sa.Column("result", sa.Float(), nullable=False),
        sa.Column("result_unit", sa.String(50), nullable=True),
        # Interpretation
        sa.Column("risk_level", sa.String(50), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
        # Recommendations generated (JSONB array)
        sa.Column("recommendations", postgresql.JSONB(), nullable=True),
        # Computed components (JSONB object)
        sa.Column("components", postgresql.JSONB(), nullable=True),
        # Execution metadata
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_by", sa.String(255), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=True),
        # Foreign key to calculator
        sa.ForeignKeyConstraint(
            ["calculator_id"],
            ["custom_calculators.id"],
            name="fk_calculator_results_calculator_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for calculator_results
    op.create_index("ix_calculator_results_calculator_id", "calculator_results", ["calculator_id"])
    op.create_index("ix_calculator_results_patient_id", "calculator_results", ["patient_id"])
    op.create_index("ix_calculator_results_calculated_at", "calculator_results", ["calculated_at"])
    op.create_index("ix_calculator_results_calculated_by", "calculator_results", ["calculated_by"])
    op.create_index("ix_calculator_results_risk_level", "calculator_results", ["risk_level"])
    op.create_index(
        "ix_calculator_results_patient_calculated_at",
        "calculator_results",
        ["patient_id", "calculated_at"],
    )
    op.create_index(
        "ix_calculator_results_calculator_calculated_at",
        "calculator_results",
        ["calculator_id", "calculated_at"],
    )


def downgrade() -> None:
    # Drop calculator_results indexes
    op.drop_index("ix_calculator_results_calculator_calculated_at")
    op.drop_index("ix_calculator_results_patient_calculated_at")
    op.drop_index("ix_calculator_results_risk_level")
    op.drop_index("ix_calculator_results_calculated_by")
    op.drop_index("ix_calculator_results_calculated_at")
    op.drop_index("ix_calculator_results_patient_id")
    op.drop_index("ix_calculator_results_calculator_id")

    # Drop calculator_results table
    op.drop_table("calculator_results")

    # Drop custom_calculators indexes
    op.drop_index("ix_custom_calculators_category_active")
    op.drop_index("ix_custom_calculators_created_by")
    op.drop_index("ix_custom_calculators_is_builtin")
    op.drop_index("ix_custom_calculators_is_active")
    op.drop_index("ix_custom_calculators_category")
    op.drop_index("ix_custom_calculators_name")

    # Drop custom_calculators table
    op.drop_table("custom_calculators")
