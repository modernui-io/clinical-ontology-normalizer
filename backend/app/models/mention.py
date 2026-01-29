"""SQLAlchemy models for Mention and MentionConceptCandidate."""

from __future__ import annotations

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.schemas.base import Assertion, Domain, Experiencer, Temporality


class Mention(Base):
    """NLP-extracted mention from a clinical document.

    Represents a text span identified by the NLP pipeline with
    assertion, temporality, and experiencer metadata.

    IMPORTANT: Negated mentions (assertion=ABSENT) must be preserved
    and exported to NOTE_NLP with term_exists='N'.
    """

    __tablename__ = "mentions"

    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    start_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    end_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    lexical_variant: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    section: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    assertion: Mapped[Assertion] = mapped_column(
        Enum(Assertion, name="assertion_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Assertion.PRESENT,
        index=True,
    )
    temporality: Mapped[Temporality] = mapped_column(
        Enum(Temporality, name="temporality_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Temporality.CURRENT,
    )
    experiencer: Mapped[Experiencer] = mapped_column(
        Enum(Experiencer, name="experiencer_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Experiencer.PATIENT,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    # Relationships
    document = relationship("Document", backref="mentions")
    concept_candidates = relationship(
        "MentionConceptCandidate",
        back_populates="mention",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Mention(id={self.id}, text='{self.text[:30]}...', assertion={self.assertion})>"

    @property
    def is_negated(self) -> bool:
        """Check if this mention is negated."""
        return bool(self.assertion == Assertion.ABSENT)


class MentionConceptCandidate(Base):
    """Candidate OMOP concept mapping for a mention.

    Stores multiple candidate mappings with confidence scores,
    allowing disambiguation and quality assessment.
    """

    __tablename__ = "mention_concept_candidates"

    mention_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("mentions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    omop_concept_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    concept_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    concept_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    vocabulary_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    domain_id: Mapped[Domain] = mapped_column(
        Enum(Domain, name="domain_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Relationships
    mention = relationship("Mention", back_populates="concept_candidates")

    def __repr__(self) -> str:
        return f"<MentionConceptCandidate(mention_id={self.mention_id}, concept={self.concept_name}, rank={self.rank})>"
