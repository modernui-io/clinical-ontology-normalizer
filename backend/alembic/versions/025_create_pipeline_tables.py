"""Create pipeline and data source tables

Revision ID: 025
Revises: 024
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE datasourcetype AS ENUM (
            'fhir_server', 'hie', 'aggregator', 'file_upload', 'hl7_feed', 'database', 'ccda'
        )
    """)

    op.execute("""
        CREATE TYPE healthstatus AS ENUM (
            'healthy', 'degraded', 'offline', 'unknown'
        )
    """)

    op.execute("""
        CREATE TYPE authmethod AS ENUM (
            'none', 'basic', 'bearer_token', 'oauth2_client_credentials',
            'oauth2_authorization_code', 'api_key', 'smart_backend'
        )
    """)

    op.execute("""
        CREATE TYPE pipelinestatus AS ENUM (
            'active', 'paused', 'disabled'
        )
    """)

    op.execute("""
        CREATE TYPE scheduletype AS ENUM (
            'manual', 'interval', 'cron'
        )
    """)

    op.execute("""
        CREATE TYPE pipelinerunstatus AS ENUM (
            'pending', 'running', 'completed', 'completed_with_warnings', 'failed', 'cancelled'
        )
    """)

    op.execute("""
        CREATE TYPE pipelinestage AS ENUM (
            'initializing', 'connecting', 'ingesting', 'validating',
            'transforming', 'enriching', 'loading', 'finalizing'
        )
    """)

    # Create data_sources table
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", postgresql.ENUM("fhir_server", "hie", "aggregator", "file_upload", "hl7_feed", "database", "ccda", name="datasourcetype", create_type=False), nullable=False),
        sa.Column("connection_config", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("auth_method", postgresql.ENUM("none", "basic", "bearer_token", "oauth2_client_credentials", "oauth2_authorization_code", "api_key", "smart_backend", name="authmethod", create_type=False), nullable=False, server_default="none"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("health_status", postgresql.ENUM("healthy", "degraded", "offline", "unknown", name="healthstatus", create_type=False), nullable=False, server_default="unknown"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_message", sa.Text, nullable=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_records_imported", sa.Integer, nullable=False, server_default="0"),
        sa.Column("default_batch_size", sa.Integer, nullable=False, server_default="100"),
        sa.Column("default_timeout_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("default_retry_count", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_index("ix_data_sources_source_type", "data_sources", ["source_type"])
    op.create_index("ix_data_sources_is_active", "data_sources", ["is_active"])
    op.create_index("ix_data_sources_health_status", "data_sources", ["health_status"])

    # Create pipelines table
    op.create_table(
        "pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", postgresql.ENUM("active", "paused", "disabled", name="pipelinestatus", create_type=False), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("schedule_type", postgresql.ENUM("manual", "interval", "cron", name="scheduletype", create_type=False), nullable=False, server_default="manual"),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("schedule_interval_minutes", sa.Integer, nullable=True),
        sa.Column("transformation_config", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(50), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_runs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("successful_runs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_runs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_index("ix_pipelines_source_id", "pipelines", ["source_id"])
    op.create_index("ix_pipelines_status", "pipelines", ["status"])
    op.create_index("ix_pipelines_is_active", "pipelines", ["is_active"])
    op.create_index("ix_pipelines_next_run_at", "pipelines", ["next_run_at"])

    # Create pipeline_runs table
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "running", "completed", "completed_with_warnings", "failed", "cancelled", name="pipelinerunstatus", create_type=False), nullable=False, server_default="pending"),
        sa.Column("current_stage", postgresql.ENUM("initializing", "connecting", "ingesting", "validating", "transforming", "enriching", "loading", "finalizing", name="pipelinestage", create_type=False), nullable=False, server_default="initializing"),
        sa.Column("progress_percent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_succeeded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stage_statistics", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_details", postgresql.JSON, nullable=True),
        sa.Column("warnings", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("triggered_by_user", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_entity_ids", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_pipeline_runs_pipeline_id", "pipeline_runs", ["pipeline_id"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("pipeline_runs")
    op.drop_table("pipelines")
    op.drop_table("data_sources")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS pipelinestage")
    op.execute("DROP TYPE IF EXISTS pipelinerunstatus")
    op.execute("DROP TYPE IF EXISTS scheduletype")
    op.execute("DROP TYPE IF EXISTS pipelinestatus")
    op.execute("DROP TYPE IF EXISTS authmethod")
    op.execute("DROP TYPE IF EXISTS healthstatus")
    op.execute("DROP TYPE IF EXISTS datasourcetype")
