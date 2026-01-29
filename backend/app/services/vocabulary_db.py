"""Database-backed vocabulary service for OMOP concept lookup.

Loads concepts from the database for NLP term extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models import Concept, ConceptSynonym
from app.schemas.base import Domain

logger = logging.getLogger(__name__)


@dataclass
class OMOPConcept:
    """OMOP concept representation for NLP matching."""

    concept_id: int
    concept_name: str
    concept_code: str
    vocabulary_id: str
    domain_id: str
    synonyms: list[str] = field(default_factory=list)

    @property
    def domain(self) -> Domain:
        """Convert domain_id string to Domain enum."""
        domain_map = {
            "Condition": Domain.CONDITION,
            "Drug": Domain.DRUG,
            "Measurement": Domain.MEASUREMENT,
            "Procedure": Domain.PROCEDURE,
            "Observation": Domain.OBSERVATION,
            "Device": Domain.DEVICE,
        }
        return domain_map.get(self.domain_id, Domain.OBSERVATION)


class DatabaseVocabularyService:
    """Database-backed vocabulary service for NLP extraction.

    Loads concepts and synonyms from the database for term matching.
    Designed to work with the full OMOP vocabulary.

    Usage:
        vocab = DatabaseVocabularyService()
        vocab.load()  # Loads from database
        # Now vocab.concepts contains all terms for NLP matching
    """

    def __init__(self) -> None:
        """Initialize the vocabulary service."""
        self._concepts: list[OMOPConcept] = []
        self._synonym_index: dict[str, list[OMOPConcept]] = {}
        self._loaded = False

    @property
    def concepts(self) -> list[OMOPConcept]:
        """Get all loaded concepts."""
        return self._concepts

    @property
    def is_loaded(self) -> bool:
        """Check if vocabulary has been loaded."""
        return self._loaded

    def load(self, domains: list[str] | None = None) -> None:
        """Load vocabulary from database.

        Args:
            domains: Optional list of domains to load (e.g., ["Condition", "Drug"]).
                    If None, loads all domains.
        """
        if self._loaded:
            return

        logger.info("Loading vocabulary from database...")

        with Session(get_sync_engine()) as session:
            # Build query
            stmt = select(Concept)
            if domains:
                stmt = stmt.where(Concept.domain_id.in_(domains))

            result = session.execute(stmt)
            db_concepts = result.scalars().all()

            logger.info(f"Found {len(db_concepts)} concepts in database")

            # Load synonyms for all concepts
            synonym_stmt = select(ConceptSynonym)
            synonym_result = session.execute(synonym_stmt)
            all_synonyms = synonym_result.scalars().all()

            # Build synonym lookup by concept_id
            synonyms_by_concept: dict[int, list[str]] = {}
            for syn in all_synonyms:
                if syn.concept_id not in synonyms_by_concept:
                    synonyms_by_concept[syn.concept_id] = []
                synonyms_by_concept[syn.concept_id].append(syn.concept_synonym_name)

            logger.info(f"Found {len(all_synonyms)} synonyms in database")

            # Build concept objects with synonyms
            for db_concept in db_concepts:
                # Get synonyms for this concept
                concept_synonyms = synonyms_by_concept.get(db_concept.concept_id, [])

                # Always include the concept name itself as a synonym
                all_names = [db_concept.concept_name.lower()]
                all_names.extend(concept_synonyms)

                # Deduplicate
                unique_synonyms = list(set(all_names))

                concept = OMOPConcept(
                    concept_id=db_concept.concept_id,
                    concept_name=db_concept.concept_name,
                    concept_code=str(db_concept.concept_id),  # Use concept_id as code
                    vocabulary_id=db_concept.vocabulary_id,
                    domain_id=db_concept.domain_id,
                    synonyms=unique_synonyms,
                )
                self._concepts.append(concept)

                # Build synonym index
                for synonym in unique_synonyms:
                    if synonym not in self._synonym_index:
                        self._synonym_index[synonym] = []
                    self._synonym_index[synonym].append(concept)

            self._loaded = True
            logger.info(
                f"Vocabulary loaded: {len(self._concepts)} concepts, "
                f"{len(self._synonym_index)} unique synonyms"
            )

    def search(self, term: str, domain: str | None = None) -> list[OMOPConcept]:
        """Search for concepts matching a term.

        Args:
            term: The term to search for.
            domain: Optional domain filter.

        Returns:
            List of matching concepts.
        """
        if not self._loaded:
            self.load()

        term_lower = term.lower()
        matches = self._synonym_index.get(term_lower, [])

        if domain:
            matches = [c for c in matches if c.domain_id == domain]

        return matches

    def get_by_concept_id(self, concept_id: int) -> OMOPConcept | None:
        """Get a concept by its OMOP concept_id."""
        if not self._loaded:
            self.load()

        for concept in self._concepts:
            if concept.concept_id == concept_id:
                return concept
        return None

    def get_statistics(self) -> dict[str, int]:
        """Get vocabulary statistics."""
        if not self._loaded:
            self.load()

        stats: dict[str, int] = {"total_concepts": len(self._concepts)}

        # Count by domain
        domain_counts: dict[str, int] = {}
        for concept in self._concepts:
            domain = concept.domain_id
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        stats.update(domain_counts)
        stats["total_synonyms"] = len(self._synonym_index)

        return stats
