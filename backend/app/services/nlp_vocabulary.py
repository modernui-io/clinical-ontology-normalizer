"""Filtered vocabulary service for NLP extraction.

This service loads a curated subset of OMOP concepts optimized for
clinical NLP extraction. It filters to high-value concepts to keep
memory usage manageable while maintaining good clinical coverage.

Key features:
1. Filters to clinical vocabularies (SNOMED, RxNorm, LOINC)
2. Filters to clinical domains (Condition, Drug, Measurement, Procedure)
3. Only loads standard/valid concepts
4. Limits total concepts to prevent OOM issues
5. Loads clinical abbreviations for labs, vitals, and common terms

For full vocabulary lookup/mapping, use DatabaseMappingServiceSQL
which performs SQL queries instead of in-memory matching.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models import Concept, ConceptSynonym
from app.schemas.base import Domain

logger = logging.getLogger(__name__)

# Path to clinical abbreviations file
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
CLINICAL_ABBREVIATIONS_FILE = FIXTURES_DIR / "clinical_abbreviations.json"

# Maximum concepts to load for NLP patterns (memory safety)
MAX_NLP_CONCEPTS = 150_000

# Priority concept classes - these are the base terms we want for NLP extraction
# Ordered by priority (loaded first)
PRIORITY_CONCEPT_CLASSES = [
    # Drug ingredients (simple drug names like "furosemide", "metformin")
    ("RxNorm", "Ingredient"),
    ("SNOMED", "Substance"),
    # Clinical findings (diagnoses, symptoms)
    ("SNOMED", "Clinical Finding"),
    ("SNOMED", "Disorder"),
    # Lab tests
    ("LOINC", "Lab Test"),
    ("LOINC", "Clinical Observation"),
    # Procedures
    ("SNOMED", "Procedure"),
    # Clinical drug forms (for matching "furosemide 40mg")
    ("RxNorm", "Clinical Drug"),
    ("RxNorm", "Clinical Drug Form"),
]

# Fallback vocabularies if priority classes don't fill quota
NLP_VOCABULARIES = {
    "SNOMED",       # Core clinical terminology
    "RxNorm",       # Drug names
    "LOINC",        # Lab tests
}

# Domains to include for NLP extraction
NLP_DOMAINS = {
    "Condition",    # Diagnoses, symptoms
    "Drug",         # Medications
    "Measurement",  # Lab results, vitals
    "Procedure",    # Clinical procedures
    "Observation",  # Clinical observations
    "Device",       # Medical devices
}

# Standard concept flags (OMOP CDM standard_concept values)
STANDARD_CONCEPT_FLAGS = {"S", "C"}  # Standard and Classification concepts


@dataclass
class NLPConcept:
    """Lightweight concept representation for NLP matching."""

    concept_id: int
    concept_name: str
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


class FilteredNLPVocabularyService:
    """Filtered vocabulary service for memory-efficient NLP extraction.

    Loads only high-value clinical concepts from the database to prevent
    OOM issues while maintaining good extraction coverage.

    Usage:
        vocab = FilteredNLPVocabularyService()
        vocab.load()  # Loads filtered concepts from database
        # Now vocab.concepts contains terms for NLP matching
    """

    def __init__(
        self,
        max_concepts: int = MAX_NLP_CONCEPTS,
        vocabularies: set[str] | None = None,
        domains: set[str] | None = None,
    ) -> None:
        """Initialize the filtered vocabulary service.

        Args:
            max_concepts: Maximum concepts to load (default 100K).
            vocabularies: Vocabularies to include (default: SNOMED, RxNorm, LOINC).
            domains: Domains to include (default: clinical domains).
        """
        self._max_concepts = max_concepts
        self._vocabularies = vocabularies or NLP_VOCABULARIES
        self._domains = domains or NLP_DOMAINS
        self._concepts: list[NLPConcept] = []
        self._synonym_index: dict[str, list[NLPConcept]] = {}
        self._loaded = False

    @property
    def concepts(self) -> list[NLPConcept]:
        """Get all loaded concepts."""
        return self._concepts

    @property
    def is_loaded(self) -> bool:
        """Check if vocabulary has been loaded."""
        return self._loaded

    def load(self) -> None:
        """Load filtered vocabulary from database.

        Uses a priority-based loading strategy:
        1. FIRST loads clinical abbreviations (curated labs, vitals, common terms)
        2. Then loads high-value concept classes (Ingredients, Clinical Findings)
        3. Finally fills remaining quota with other standard concepts

        This ensures clinical abbreviations (which have correct domains) are
        matched BEFORE database concepts. For example, "creatinine" should be
        Measurement (from our abbreviations), not Drug (from RxNorm).
        """
        if self._loaded:
            return

        logger.info(
            f"Loading filtered NLP vocabulary (max {self._max_concepts} concepts)..."
        )

        # Phase 0: Load clinical abbreviations FIRST (highest priority)
        # These are curated terms with correct domains that should take precedence
        self._load_clinical_abbreviations()
        curated_synonyms = set(self._synonym_index.keys())
        logger.info(f"Loaded {len(self._concepts)} clinical abbreviations with {len(curated_synonyms)} synonyms")

        db_concepts = []
        loaded_ids: set[int] = set()

        with Session(get_sync_engine()) as session:
            # Phase 1: Load priority concept classes first
            for vocab_id, concept_class in PRIORITY_CONCEPT_CLASSES:
                if len(db_concepts) >= self._max_concepts:
                    break

                remaining = self._max_concepts - len(db_concepts)
                logger.info(f"Loading {vocab_id}/{concept_class} (up to {remaining})...")

                stmt = (
                    select(Concept)
                    .where(
                        and_(
                            Concept.vocabulary_id == vocab_id,
                            Concept.concept_class_id == concept_class,
                            Concept.standard_concept.in_(STANDARD_CONCEPT_FLAGS),
                            Concept.domain_id.in_(self._domains),
                        )
                    )
                    # Shorter names first (base terms like "furosemide" before "furosemide 40mg tablet")
                    .order_by(func.length(Concept.concept_name), Concept.concept_name)
                    .limit(remaining)
                )

                result = session.execute(stmt)
                for concept in result.scalars():
                    if concept.concept_id not in loaded_ids:
                        db_concepts.append(concept)
                        loaded_ids.add(concept.concept_id)

                logger.info(f"  Loaded {len(db_concepts)} total concepts so far")

            # Phase 2: Fill remaining with other standard concepts
            if len(db_concepts) < self._max_concepts:
                remaining = self._max_concepts - len(db_concepts)
                logger.info(f"Filling remaining {remaining} slots with other concepts...")

                stmt = (
                    select(Concept)
                    .where(
                        and_(
                            Concept.vocabulary_id.in_(self._vocabularies),
                            Concept.domain_id.in_(self._domains),
                            Concept.standard_concept.in_(STANDARD_CONCEPT_FLAGS),
                            ~Concept.concept_id.in_(loaded_ids) if loaded_ids else True,
                        )
                    )
                    .order_by(func.length(Concept.concept_name), Concept.concept_name)
                    .limit(remaining)
                )

                result = session.execute(stmt)
                for concept in result.scalars():
                    if concept.concept_id not in loaded_ids:
                        db_concepts.append(concept)
                        loaded_ids.add(concept.concept_id)

            logger.info(f"Loaded {len(db_concepts)} concepts total")

            # Get concept IDs for synonym lookup
            concept_ids = list(loaded_ids)

            # Load synonyms only for the filtered concepts
            if concept_ids:
                synonym_stmt = select(ConceptSynonym).where(
                    ConceptSynonym.concept_id.in_(concept_ids)
                )
                synonym_result = session.execute(synonym_stmt)
                all_synonyms = synonym_result.scalars().all()

                # Build synonym lookup by concept_id
                synonyms_by_concept: dict[int, list[str]] = {}
                for syn in all_synonyms:
                    if syn.concept_id not in synonyms_by_concept:
                        synonyms_by_concept[syn.concept_id] = []
                    synonyms_by_concept[syn.concept_id].append(
                        syn.concept_synonym_name.lower()
                    )

                logger.info(f"Found {len(all_synonyms)} synonyms for filtered concepts")
            else:
                synonyms_by_concept = {}

            # Build concept objects with synonyms
            # Skip synonyms already covered by clinical abbreviations
            for db_concept in db_concepts:
                # Get synonyms for this concept
                concept_synonyms = synonyms_by_concept.get(db_concept.concept_id, [])

                # Always include the concept name itself
                all_names = [db_concept.concept_name.lower()]
                all_names.extend(concept_synonyms)

                # Deduplicate and filter out synonyms already in clinical abbreviations
                # This prevents RxNorm "creatinine" (Drug) from overriding our
                # clinical abbreviation "creatinine" (Measurement)
                unique_synonyms = [
                    s for s in set(all_names)
                    if s not in curated_synonyms
                ]

                # Skip concepts where all synonyms are already covered
                if not unique_synonyms:
                    continue

                concept = NLPConcept(
                    concept_id=db_concept.concept_id,
                    concept_name=db_concept.concept_name,
                    vocabulary_id=db_concept.vocabulary_id,
                    domain_id=db_concept.domain_id,
                    synonyms=unique_synonyms,
                )
                self._concepts.append(concept)

                # Build synonym index for fast lookup
                for synonym in unique_synonyms:
                    if synonym not in self._synonym_index:
                        self._synonym_index[synonym] = []
                    self._synonym_index[synonym].append(concept)

            # Clinical abbreviations already loaded in Phase 0 above

            self._loaded = True
            logger.info(
                f"NLP vocabulary loaded: {len(self._concepts)} concepts, "
                f"{len(self._synonym_index)} unique terms"
            )

    def _load_clinical_abbreviations(self) -> None:
        """Load clinical abbreviations for labs, vitals, and common terms.

        These are curated short forms that aren't in OMOP vocabularies
        but are essential for clinical NLP extraction.
        """
        if not CLINICAL_ABBREVIATIONS_FILE.exists():
            logger.warning(f"Clinical abbreviations file not found: {CLINICAL_ABBREVIATIONS_FILE}")
            return

        try:
            with open(CLINICAL_ABBREVIATIONS_FILE) as f:
                data = json.load(f)

            terms = data.get("terms", [])
            added_count = 0

            for term in terms:
                name = term.get("name", "")
                synonyms = [s.lower() for s in term.get("synonyms", [])]
                domain_str = term.get("domain", "Observation")
                concept_id = term.get("omop_concept_id", 0)

                if not name or not synonyms:
                    continue

                # Create NLP concept for this abbreviation
                concept = NLPConcept(
                    concept_id=concept_id,
                    concept_name=name,
                    vocabulary_id="Clinical Abbreviations",
                    domain_id=domain_str,
                    synonyms=synonyms,
                )
                self._concepts.append(concept)

                # Add to synonym index
                for synonym in synonyms:
                    if synonym not in self._synonym_index:
                        self._synonym_index[synonym] = []
                    self._synonym_index[synonym].append(concept)

                added_count += 1

            logger.info(f"Loaded {added_count} clinical abbreviations for labs, vitals, and common terms")

        except Exception as e:
            logger.error(f"Error loading clinical abbreviations: {e}")

    def search(self, term: str, domain: str | None = None) -> list[NLPConcept]:
        """Search for concepts matching a term.

        Args:
            term: The term to search for (exact match on synonym index).
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

        # Count by vocabulary
        vocab_counts: dict[str, int] = {}
        for concept in self._concepts:
            vocab = concept.vocabulary_id
            vocab_counts[vocab] = vocab_counts.get(vocab, 0) + 1

        stats["domains"] = domain_counts
        stats["vocabularies"] = vocab_counts
        stats["total_synonyms"] = len(self._synonym_index)

        return stats
