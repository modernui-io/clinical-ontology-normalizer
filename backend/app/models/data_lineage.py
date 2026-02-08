"""SQLAlchemy model for Data Lineage tracking.

CDO-1: Data Lineage Tracking (P2 - foundational for compliance and trust).

Tracks WHERE each ClinicalFact came from and HOW it was derived,
enabling regulatory compliance audits and debugging of the data pipeline.

The data_lineage table is append-only: no updates or deletes.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SourceType(str, Enum):
    """Source type for lineage records.

    Indicates how the ClinicalFact was originally produced.
    """

    FHIR_IMPORT = "fhir_import"
    NLP_EXTRACTION = "nlp_extraction"
    MANUAL_ENTRY = "manual_entry"
    DERIVED = "derived"
    EXTERNAL_API = "external_api"


class DataLineageRecord(Base):
    """Data lineage record linking a ClinicalFact to its origin.

    CDO-1: Every ClinicalFact should have a corresponding lineage record
    documenting its source, extraction method, and transformation chain.

    This table is append-only for auditability -- records are never
    updated or deleted.
    """

    __tablename__ = "data_lineage"

    clinical_fact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("clinical_facts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[SourceType] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    source_document_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    source_resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    source_resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    extraction_method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    extraction_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    transformation_chain: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    clinical_fact = relationship("ClinicalFact", backref="lineage_records")

    __table_args__ = (
        # Patient lineage queries go through clinical_facts FK,
        # but we index source_type for aggregate queries.
        Index("ix_data_lineage_source_type", "source_type"),
        Index("ix_data_lineage_fact_source", "clinical_fact_id", "source_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<DataLineageRecord(id={self.id}, fact_id={self.clinical_fact_id}, "
            f"source={self.source_type})>"
        )
