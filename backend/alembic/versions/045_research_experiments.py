"""Add research experiment tracking tables for NeurIPS paper data collection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "045"
down_revision: str | None = "044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create experiment status enum
    op.execute(
        "CREATE TYPE experiment_status AS ENUM "
        "('draft', 'running', 'completed', 'failed', 'archived')"
    )

    # Create run status enum
    op.execute(
        "CREATE TYPE experiment_run_status AS ENUM "
        "('pending', 'processing', 'completed', 'failed')"
    )

    # Create metric category enum
    op.execute(
        "CREATE TYPE metric_category AS ENUM "
        "('nlp', 'mapping', 'assertion', 'kg', 'rag', 'timing')"
    )

    # Research Experiments table
    op.create_table(
        "research_experiments",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("hypothesis", sa.Text, nullable=True),
        sa.Column(
            "config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "running",
                "completed",
                "failed",
                "archived",
                name="experiment_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("summary_metrics", JSONB, nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_research_experiments_status",
        "research_experiments",
        ["status"],
    )
    op.create_index(
        "ix_research_experiments_created_by",
        "research_experiments",
        ["created_by"],
    )

    # Research Experiment Runs table
    op.create_table(
        "research_experiment_runs",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "experiment_id",
            sa.String(255),
            sa.ForeignKey("research_experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mimic_batch_id", sa.String(255), nullable=True),
        sa.Column("run_config", JSONB, nullable=True),
        sa.Column("document_ids", sa.ARRAY(sa.String), nullable=True),
        sa.Column("patient_ids", sa.ARRAY(sa.String), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="experiment_run_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_research_runs_experiment_id",
        "research_experiment_runs",
        ["experiment_id"],
    )
    op.create_index(
        "ix_research_runs_status",
        "research_experiment_runs",
        ["status"],
    )

    # Research Experiment Metrics table
    op.create_table(
        "research_experiment_metrics",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(255),
            sa.ForeignKey("research_experiment_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "nlp",
                "mapping",
                "assertion",
                "kg",
                "rag",
                "timing",
                name="metric_category",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("metric_name", sa.String(255), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_research_metrics_run_id",
        "research_experiment_metrics",
        ["run_id"],
    )
    op.create_index(
        "ix_research_metrics_category",
        "research_experiment_metrics",
        ["category"],
    )
    op.create_index(
        "ix_research_metrics_run_category",
        "research_experiment_metrics",
        ["run_id", "category"],
    )


def downgrade() -> None:
    op.drop_table("research_experiment_metrics")
    op.drop_table("research_experiment_runs")
    op.drop_table("research_experiments")
    op.execute("DROP TYPE IF EXISTS metric_category")
    op.execute("DROP TYPE IF EXISTS experiment_run_status")
    op.execute("DROP TYPE IF EXISTS experiment_status")
