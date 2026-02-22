"""Add research experiment tracking tables for NeurIPS paper data collection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "045"
down_revision: str | None = "044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create enums idempotently
    for type_name, values in [
        ("experiment_status", "'draft', 'running', 'completed', 'failed', 'archived'"),
        ("experiment_run_status", "'pending', 'processing', 'completed', 'failed'"),
        ("metric_category", "'nlp', 'mapping', 'assertion', 'kg', 'rag', 'timing'"),
    ]:
        result = conn.execute(
            sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": type_name},
        )
        if result.fetchone() is None:
            conn.execute(sa.text(
                f"CREATE TYPE {type_name} AS ENUM ({values})"
            ))

    # Create tables via raw SQL to avoid asyncpg/sa.Enum interaction bug
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS research_experiments (
            id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            hypothesis TEXT,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            status experiment_status NOT NULL DEFAULT 'draft',
            summary_metrics JSONB,
            tags TEXT[],
            created_by VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            deleted_at TIMESTAMPTZ
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS research_experiment_runs (
            id VARCHAR(255) PRIMARY KEY,
            experiment_id VARCHAR(255) NOT NULL REFERENCES research_experiments(id) ON DELETE CASCADE,
            mimic_batch_id VARCHAR(255),
            run_config JSONB,
            document_ids TEXT[],
            patient_ids TEXT[],
            status experiment_run_status NOT NULL DEFAULT 'pending',
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS research_experiment_metrics (
            id VARCHAR(255) PRIMARY KEY,
            run_id VARCHAR(255) NOT NULL REFERENCES research_experiment_runs(id) ON DELETE CASCADE,
            category metric_category NOT NULL,
            metric_name VARCHAR(255) NOT NULL,
            metric_value DOUBLE PRECISION NOT NULL,
            detail JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    # Indexes
    for idx_name, table, cols in [
        ("ix_research_experiments_status", "research_experiments", "status"),
        ("ix_research_experiments_created_by", "research_experiments", "created_by"),
        ("ix_research_runs_experiment_id", "research_experiment_runs", "experiment_id"),
        ("ix_research_runs_status", "research_experiment_runs", "status"),
        ("ix_research_metrics_run_id", "research_experiment_metrics", "run_id"),
        ("ix_research_metrics_category", "research_experiment_metrics", "category"),
    ]:
        conn.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({cols})"
        ))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_research_metrics_run_category "
        "ON research_experiment_metrics (run_id, category)"
    ))


def downgrade() -> None:
    op.drop_table("research_experiment_metrics")
    op.drop_table("research_experiment_runs")
    op.drop_table("research_experiments")
    op.execute("DROP TYPE IF EXISTS metric_category")
    op.execute("DROP TYPE IF EXISTS experiment_run_status")
    op.execute("DROP TYPE IF EXISTS experiment_status")
