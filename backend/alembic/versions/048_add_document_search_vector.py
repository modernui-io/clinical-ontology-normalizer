"""Add search_vector TSVECTOR column to documents.

Revision ID: 048
Revises: 047
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add TSVECTOR column
    op.add_column(
        "documents",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR(), nullable=True),
    )

    # Populate from existing text
    op.execute(
        "UPDATE documents SET search_vector = to_tsvector('english', COALESCE(text, ''))"
    )

    # Create GIN index
    op.create_index(
        "ix_documents_search_vector",
        "documents",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Create trigger to auto-update on INSERT/UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION documents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.text, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER documents_search_vector_trigger
        BEFORE INSERT OR UPDATE OF text ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents")
    op.execute("DROP FUNCTION IF EXISTS documents_search_vector_update()")
    op.drop_index("ix_documents_search_vector", table_name="documents")
    op.drop_column("documents", "search_vector")
