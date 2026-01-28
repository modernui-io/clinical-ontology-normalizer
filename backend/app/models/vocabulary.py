"""SQLAlchemy models for OMOP vocabulary concepts."""

import enum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.core.database import Base


class ConceptStatus(str, enum.Enum):
    """Status of a vocabulary concept."""

    active = "active"
    deprecated = "deprecated"
    retired = "retired"
    merged = "merged"


class Concept(Base):
    """OMOP Concept table (simplified for local development).

    This is a subset of the OMOP CDM CONCEPT table containing
    only the fields needed for concept lookup and mapping.

    Note: Uses UUID id from Base for internal tracking, but concept_id
    is the OMOP-standard identifier used for lookups and mapping.
    """

    __tablename__ = "concepts"

    concept_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )
    concept_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    domain_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    vocabulary_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    concept_class_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    standard_concept: Mapped[str | None] = mapped_column(
        String(1),
        nullable=True,
    )

    # Embedding vector for semantic search (384 dimensions for MiniLM)
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )

    # Versioning columns
    vocabulary_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    version_date: Mapped[str | None] = mapped_column(
        Date,
        nullable=True,
    )
    previous_concept_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    status: Mapped[ConceptStatus] = mapped_column(
        Enum(ConceptStatus, name="concept_status"),
        nullable=False,
        server_default="active",
        index=True,
    )
    status_changed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship to synonyms
    synonyms = relationship(
        "ConceptSynonym",
        back_populates="concept",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Concept(concept_id={self.concept_id}, name='{self.concept_name}', domain='{self.domain_id}')>"

    @property
    def is_standard(self) -> bool:
        """Check if this is a standard concept."""
        return bool(self.standard_concept == "S")


class ConceptSynonym(Base):
    """OMOP Concept Synonym table for fuzzy matching.

    Stores alternative names for concepts to improve matching.
    """

    __tablename__ = "concept_synonyms"

    concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concepts.concept_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_synonym_name: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        index=True,
    )
    language_concept_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4180186,  # English
    )

    # Relationship to concept
    concept = relationship("Concept", back_populates="synonyms")

    def __repr__(self) -> str:
        return f"<ConceptSynonym(concept_id={self.concept_id}, name='{self.concept_synonym_name}')>"


class ConceptRelationship(Base):
    """OMOP Concept Relationship table for cross-vocabulary mapping.

    Stores relationships between concepts including:
    - Maps to: Non-standard to standard concept mappings
    - Is a: Hierarchical relationships
    - May treat: Drug to condition relationships
    - And many more...

    Key relationship types for mapping:
    - "Maps to": Source vocabulary → Standard vocabulary (SNOMED, RxNorm)
    - "Mapped from": Reverse of "Maps to"
    - "Is a" / "Subsumes": Hierarchical parent-child
    """

    __tablename__ = "concept_relationships"

    concept_id_1: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    concept_id_2: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    relationship_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    valid_start_date: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )
    valid_end_date: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )
    invalid_reason: Mapped[str | None] = mapped_column(
        String(1),
        nullable=True,
    )
    relationship_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ConceptRelationship({self.concept_id_1} -{self.relationship_id}-> {self.concept_id_2})>"

    @property
    def is_valid(self) -> bool:
        """Check if this relationship is currently valid."""
        return self.invalid_reason is None
