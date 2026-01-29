"""Database-backed OMOP Concept Mapping Service.

Maps clinical mentions to OMOP standard concepts by querying
the database tables populated by the seed script.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.vocabulary import Concept
from app.schemas.base import Domain
from app.services.mapping import BaseMappingService, ConceptCandidate, MappingMethod


class DatabaseMappingService(BaseMappingService):
    """Database-backed mapping service for OMOP concepts.

    Queries the concepts and concept_synonyms tables to map
    clinical mentions to OMOP standard concepts.

    Usage:
        service = DatabaseMappingService()
        service.load_from_db(session)
        candidates = service.map_mention("hypertension")
    """

    def __init__(self, session: Session | None = None) -> None:
        """Initialize the database mapping service."""
        super().__init__()
        self._session = session
        self._concepts: list[Concept] = []
        self._synonym_index: dict[str, list[tuple[Concept, str]]] = {}
        self._concept_id_index: dict[int, Concept] = {}
        self._loaded = False

    def load_from_db(self, session: Session | None = None) -> None:
        """Load concepts from database into memory."""
        if self._loaded:
            return

        db_session = session or self._session
        if db_session is None:
            raise ValueError("No database session available")

        stmt = select(Concept).options(joinedload(Concept.synonyms))
        result = db_session.execute(stmt)
        self._concepts = list(result.scalars().unique().all())

        self._synonym_index = {}
        self._concept_id_index = {}

        for concept in self._concepts:
            self._concept_id_index[concept.concept_id] = concept

            name_key = concept.concept_name.lower().strip()
            if name_key not in self._synonym_index:
                self._synonym_index[name_key] = []
            self._synonym_index[name_key].append((concept, concept.concept_name))

            for synonym in concept.synonyms:
                syn_key = synonym.concept_synonym_name.lower().strip()
                if syn_key not in self._synonym_index:
                    self._synonym_index[syn_key] = []
                self._synonym_index[syn_key].append((concept, synonym.concept_synonym_name))

        self._loaded = True

    def is_loaded(self) -> bool:
        """Check if the vocabulary is loaded."""
        return self._loaded

    @property
    def concept_count(self) -> int:
        """Get the number of loaded concepts."""
        return len(self._concepts)

    def _ensure_loaded(self) -> None:
        """Ensure concepts are loaded before queries."""
        if not self._loaded:
            if self._session is not None:
                self.load_from_db(self._session)
            else:
                raise RuntimeError("Vocabulary not loaded. Call load_from_db(session) first.")

    def _domain_from_string(self, domain_id: str) -> Domain:
        """Convert domain_id string to Domain enum."""
        domain_map = {
            "Condition": Domain.CONDITION,
            "Drug": Domain.DRUG,
            "Measurement": Domain.MEASUREMENT,
            "Procedure": Domain.PROCEDURE,
            "Observation": Domain.OBSERVATION,
            "Device": Domain.DEVICE,
        }
        return domain_map.get(domain_id, Domain.OBSERVATION)

    def _concept_to_candidate(
        self,
        concept: Concept,
        score: float,
        method: MappingMethod,
        rank: int = 1,
    ) -> ConceptCandidate:
        """Convert a database Concept to ConceptCandidate."""
        return ConceptCandidate(
            omop_concept_id=concept.concept_id,
            concept_name=concept.concept_name,
            concept_code=str(concept.concept_id),
            vocabulary_id=concept.vocabulary_id,
            domain_id=self._domain_from_string(concept.domain_id),
            score=score,
            method=method,
            rank=rank,
        )

    def map_mention(
        self,
        text: str,
        domain: Domain | None = None,
        limit: int = 5,
    ) -> list[ConceptCandidate]:
        """Map a mention text to candidate OMOP concepts."""
        self._ensure_loaded()

        candidates: list[ConceptCandidate] = []
        seen_ids: set[int] = set()
        normalized_text = self.normalize_text(text)

        def add_candidate(
            concept: Concept,
            score: float,
            method: MappingMethod,
        ) -> bool:
            if concept.concept_id in seen_ids:
                return False
            if domain is not None and self._domain_from_string(concept.domain_id) != domain:
                return False

            candidate = self._concept_to_candidate(
                concept=concept,
                score=score,
                method=method,
                rank=len(candidates) + 1,
            )
            candidates.append(candidate)
            seen_ids.add(concept.concept_id)
            return True

        # Exact match on normalized text
        if normalized_text in self._synonym_index:
            for concept, _variant in self._synonym_index[normalized_text]:
                if add_candidate(concept, 1.0, MappingMethod.EXACT):
                    if len(candidates) >= limit:
                        return candidates

        # Check other normalized forms
        for synonym_key, entries in self._synonym_index.items():
            if self.normalize_text(synonym_key) == normalized_text:
                if synonym_key != normalized_text:
                    for concept, _variant in entries:
                        if add_candidate(concept, 0.95, MappingMethod.EXACT):
                            if len(candidates) >= limit:
                                return candidates

        # Fuzzy matching if not enough exact matches found
        if len(candidates) < limit:
            fuzzy_candidates: list[tuple[Concept, float]] = []
            min_threshold = 0.3

            for synonym_key, entries in self._synonym_index.items():
                similarity = self.calculate_similarity(text, synonym_key)
                if similarity >= min_threshold:
                    for concept, _variant in entries:
                        if concept.concept_id not in seen_ids:
                            if (
                                domain is None
                                or self._domain_from_string(concept.domain_id) == domain
                            ):
                                fuzzy_candidates.append((concept, similarity))

            # Sort by score descending and add top candidates
            fuzzy_candidates.sort(key=lambda x: x[1], reverse=True)
            for concept, score in fuzzy_candidates:
                if add_candidate(concept, score, MappingMethod.FUZZY):
                    if len(candidates) >= limit:
                        break

        return candidates

    def get_concept_by_id(self, concept_id: int) -> ConceptCandidate | None:
        """Look up a concept by its OMOP concept ID."""
        self._ensure_loaded()

        concept = self._concept_id_index.get(concept_id)
        if concept is None:
            return None

        return self._concept_to_candidate(
            concept=concept,
            score=1.0,
            method=MappingMethod.EXACT,
        )

    def get_synonyms(self, concept_id: int) -> list[str]:
        """Get synonyms for a concept by ID."""
        self._ensure_loaded()

        concept = self._concept_id_index.get(concept_id)
        if concept is None:
            return []

        return [s.concept_synonym_name for s in concept.synonyms]

    def search_by_domain(
        self,
        text: str,
        domain: Domain,
        limit: int = 5,
    ) -> list[ConceptCandidate]:
        """Search for concepts by term within a specific domain."""
        return self.map_mention(text, domain=domain, limit=limit)
