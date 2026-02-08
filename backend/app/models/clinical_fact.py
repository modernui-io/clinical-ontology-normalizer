"""SQLAlchemy models for ClinicalFact and FactEvidence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.clinical_fact import EvidenceType


class ClinicalFact(SoftDeleteMixin, Base):
    """Canonical normalized clinical fact.

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Represents a deduplicated, normalized clinical finding combining
    evidence from both NLP extraction and structured data sources.

    CRITICAL: Negated findings (assertion=ABSENT) MUST be preserved.
    They should NOT be inserted into positive OMOP event tables but
    should be:
    1. Stored in this table with assertion=ABSENT
    2. Exported to NOTE_NLP with term_exists='N'
    3. Represented in the knowledge graph with appropriate markers
    """

    __tablename__ = "clinical_facts"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    domain: Mapped[Domain] = mapped_column(
        Enum(Domain, name="domain_type", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    omop_concept_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    concept_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    assertion: Mapped[Assertion] = mapped_column(
        Enum(Assertion, name="assertion_type", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Assertion.PRESENT,
        index=True,
    )
    temporality: Mapped[Temporality] = mapped_column(
        Enum(Temporality, name="temporality_type", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Temporality.CURRENT,
    )
    experiencer: Mapped[Experiencer] = mapped_column(
        Enum(Experiencer, name="experiencer_type", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Experiencer.PATIENT,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # CSO-1: Pipeline version that produced this fact for reproducibility.
    # Nullable for backward compatibility with facts created before
    # version tracking was introduced.
    pipeline_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Vector embedding for semantic search (384 dimensions for MiniLM)
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )

    # Relationships
    evidence = relationship(
        "FactEvidence",
        back_populates="fact",
        cascade="all, delete-orphan",
    )

    # VP-Performance: Composite indexes for common query patterns
    __table_args__ = (
        # Patient + domain: "Get all conditions/drugs/measurements for patient"
        Index("ix_clinical_facts_patient_domain", "patient_id", "domain"),
        # Patient + assertion: "Get all negated findings for patient"
        Index("ix_clinical_facts_patient_assertion", "patient_id", "assertion"),
        # Patient + domain + assertion: "Get all positive conditions for patient"
        Index("ix_clinical_facts_patient_domain_assertion", "patient_id", "domain", "assertion"),
        # Patient + concept: "Get all instances of specific diagnosis for patient"
        Index("ix_clinical_facts_patient_concept", "patient_id", "omop_concept_id"),
    )

    def __repr__(self) -> str:
        return f"<ClinicalFact(id={self.id}, patient={self.patient_id}, concept={self.concept_name}, assertion={self.assertion})>"

    @property
    def is_negated(self) -> bool:
        """Check if this fact represents a negated finding."""
        return bool(self.assertion == Assertion.ABSENT)

    @property
    def is_uncertain(self) -> bool:
        """Check if this fact represents an uncertain finding."""
        return bool(self.assertion == Assertion.POSSIBLE)

    @property
    def is_family_history(self) -> bool:
        """Check if this fact is about a family member."""
        return bool(self.experiencer == Experiencer.FAMILY)


class FactEvidence(Base):
    """Evidence linking a ClinicalFact to its source.

    Enables full provenance tracking by linking facts to their
    evidence sources (mentions from NLP, structured data records,
    or inferred relationships).
    """

    __tablename__ = "fact_evidence"

    fact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("clinical_facts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType, name="evidence_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )
    source_table: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    fact = relationship("ClinicalFact", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<FactEvidence(fact_id={self.fact_id}, type={self.evidence_type}, source={self.source_table})>"
