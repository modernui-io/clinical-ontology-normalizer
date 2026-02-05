"""Concept lookup service for mapping extracted entities to OMOP concept_ids.

This service provides:
1. Exact match lookup by concept_name
2. Case-insensitive fuzzy matching
3. Domain-specific prioritization (NDFRT for drugs, SNOMED for conditions)
4. Redis caching for performance

Phase 2 of the Ontology Relationships implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocabulary import Concept

logger = logging.getLogger(__name__)


@dataclass
class ConceptMatch:
    """Result of a concept lookup."""

    concept_id: int
    concept_name: str
    vocabulary_id: str
    concept_class_id: str
    domain_id: str
    score: float = 1.0  # Match confidence (1.0 = exact, lower = fuzzy)

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "concept_name": self.concept_name,
            "vocabulary_id": self.vocabulary_id,
            "concept_class_id": self.concept_class_id,
            "domain_id": self.domain_id,
            "score": self.score,
        }


# Vocabulary priorities by domain - prefer vocabularies with rich relationships
DRUG_VOCABULARIES = ["NDFRT", "RxNorm", "NDC", "ATC"]
CONDITION_VOCABULARIES = ["NDFRT", "SNOMED", "ICD10CM", "ICD9CM"]
MEASUREMENT_VOCABULARIES = ["LOINC", "SNOMED"]
PROCEDURE_VOCABULARIES = ["SNOMED", "CPT4", "HCPCS", "ICD10PCS"]

# Concept classes to prioritize for relationship lookups
DRUG_CONCEPT_CLASSES = ["Pharma Preparation", "Ingredient", "Clinical Drug", "Drug"]
CONDITION_CONCEPT_CLASSES = ["Ind / CI", "Clinical Finding", "Disorder", "Disease"]


async def lookup_concept(
    db: AsyncSession,
    text: str,
    domain: str | None = None,
) -> ConceptMatch | None:
    """Find the best matching OMOP concept_id for extracted text.

    Args:
        db: Database session
        text: Extracted entity text (e.g., "metformin", "diabetes")
        domain: Optional domain hint ("Drug", "Condition", "Measurement", "Procedure")

    Returns:
        ConceptMatch if found, None otherwise
    """
    if not text or len(text) < 2:
        return None

    normalized_text = text.strip()

    # 1. Try exact match (case-insensitive) with domain prioritization
    match = await _exact_match(db, normalized_text, domain)
    if match:
        return match

    # 2. Try uppercase exact match (NDFRT uses uppercase names)
    match = await _exact_match(db, normalized_text.upper(), domain)
    if match:
        return match

    # 3. Try fuzzy match with trigram similarity
    match = await _fuzzy_match(db, normalized_text, domain)
    if match:
        return match

    return None


async def _exact_match(
    db: AsyncSession,
    text: str,
    domain: str | None,
) -> ConceptMatch | None:
    """Try exact match on concept_name."""

    # Get vocabulary priority list based on domain
    priority_vocabs = _get_priority_vocabularies(domain)

    # Query for exact match - select only needed columns to avoid missing columns
    # Note: The concepts table doesn't have invalid_reason/status columns,
    # all loaded concepts are assumed valid
    query = select(
        Concept.concept_id,
        Concept.concept_name,
        Concept.vocabulary_id,
        Concept.concept_class_id,
        Concept.domain_id,
    ).where(
        func.upper(Concept.concept_name) == text.upper(),
    )

    # Note: Don't filter by domain_id because NDFRT uses "Drug" domain for conditions
    # that have clinical relationships. The vocabulary prioritization will pick the best match.

    result = await db.execute(query.limit(50))
    rows = result.fetchall()

    if not rows:
        return None

    # Convert to simple objects for prioritization
    @dataclass
    class SimpleConcept:
        concept_id: int
        concept_name: str
        vocabulary_id: str
        concept_class_id: str
        domain_id: str

    concepts = [
        SimpleConcept(
            concept_id=row[0],
            concept_name=row[1],
            vocabulary_id=row[2],
            concept_class_id=row[3],
            domain_id=row[4],
        )
        for row in rows
    ]

    # Prioritize by vocabulary
    best_match = _select_best_concept(concepts, priority_vocabs, domain)
    if best_match:
        return ConceptMatch(
            concept_id=best_match.concept_id,
            concept_name=best_match.concept_name,
            vocabulary_id=best_match.vocabulary_id,
            concept_class_id=best_match.concept_class_id,
            domain_id=best_match.domain_id,
            score=1.0,
        )

    return None


async def _fuzzy_match(
    db: AsyncSession,
    text: str,
    domain: str | None,
    min_similarity: float = 0.6,
) -> ConceptMatch | None:
    """Try fuzzy match using PostgreSQL trigram similarity."""

    priority_vocabs = _get_priority_vocabularies(domain)

    # Use pg_trgm extension for similarity matching
    # This requires the pg_trgm extension to be enabled
    try:
        # Build query with similarity scoring
        domain_filter = f"AND UPPER(domain_id) = '{domain.upper()}'" if domain else ""

        query_text = f"""
            SELECT concept_id, concept_name, vocabulary_id, concept_class_id,
                   domain_id, similarity(concept_name, :text) as sim
            FROM concepts
            WHERE similarity(concept_name, :text) > :min_sim
            {domain_filter}
            ORDER BY sim DESC
            LIMIT 20
        """

        result = await db.execute(
            text(query_text),
            {"text": text, "min_sim": min_similarity}
        )
        rows = result.fetchall()

        if not rows:
            return None

        # Convert to lightweight objects for selection
        @dataclass
        class SimpleMatch:
            concept_id: int
            concept_name: str
            vocabulary_id: str
            concept_class_id: str
            domain_id: str
            similarity: float

        matches = [
            SimpleMatch(
                concept_id=row[0],
                concept_name=row[1],
                vocabulary_id=row[2],
                concept_class_id=row[3],
                domain_id=row[4],
                similarity=row[5],
            )
            for row in rows
        ]

        # Select best match considering vocabulary priority and similarity
        best = _select_best_fuzzy_match(matches, priority_vocabs, domain)
        if best:
            return ConceptMatch(
                concept_id=best.concept_id,
                concept_name=best.concept_name,
                vocabulary_id=best.vocabulary_id,
                concept_class_id=best.concept_class_id,
                domain_id=best.domain_id,
                score=best.similarity,
            )
    except Exception as e:
        # Trigram extension might not be available
        logger.warning(f"Fuzzy matching failed (pg_trgm may not be enabled): {e}")

    return None


def _get_priority_vocabularies(domain: str | None) -> list[str]:
    """Get priority vocabulary list based on domain."""
    if not domain:
        return DRUG_VOCABULARIES + CONDITION_VOCABULARIES  # Default to all

    domain_upper = domain.upper()
    if domain_upper == "DRUG":
        return DRUG_VOCABULARIES
    elif domain_upper in ("CONDITION", "DISORDER", "DISEASE"):
        return CONDITION_VOCABULARIES
    elif domain_upper in ("MEASUREMENT", "LAB", "OBSERVATION"):
        return MEASUREMENT_VOCABULARIES
    elif domain_upper == "PROCEDURE":
        return PROCEDURE_VOCABULARIES
    else:
        return DRUG_VOCABULARIES + CONDITION_VOCABULARIES


def _get_priority_classes(domain: str | None) -> list[str]:
    """Get priority concept classes based on domain."""
    if not domain:
        return DRUG_CONCEPT_CLASSES + CONDITION_CONCEPT_CLASSES

    domain_upper = domain.upper()
    if domain_upper == "DRUG":
        return DRUG_CONCEPT_CLASSES
    elif domain_upper in ("CONDITION", "DISORDER", "DISEASE"):
        return CONDITION_CONCEPT_CLASSES
    else:
        return DRUG_CONCEPT_CLASSES + CONDITION_CONCEPT_CLASSES


def _select_best_concept(
    concepts: list[Concept],
    priority_vocabs: list[str],
    domain: str | None,
) -> Concept | None:
    """Select best concept from candidates based on vocabulary and class priority."""
    if not concepts:
        return None

    priority_classes = _get_priority_classes(domain)

    # Score each concept
    def score_concept(c: Concept) -> tuple[int, int, int]:
        vocab_score = (
            priority_vocabs.index(c.vocabulary_id)
            if c.vocabulary_id in priority_vocabs
            else 100
        )
        class_score = (
            priority_classes.index(c.concept_class_id)
            if c.concept_class_id in priority_classes
            else 100
        )
        # Prefer shorter names (more likely to be the canonical form)
        length_score = len(c.concept_name)
        return (vocab_score, class_score, length_score)

    return min(concepts, key=score_concept)


def _select_best_fuzzy_match(
    matches: list,
    priority_vocabs: list[str],
    domain: str | None,
) -> object | None:
    """Select best fuzzy match considering similarity and vocabulary priority."""
    if not matches:
        return None

    priority_classes = _get_priority_classes(domain)

    def score_match(m) -> tuple[float, int, int]:
        # Primary: similarity (higher is better, so negate)
        sim_score = -m.similarity
        vocab_score = (
            priority_vocabs.index(m.vocabulary_id)
            if m.vocabulary_id in priority_vocabs
            else 100
        )
        class_score = (
            priority_classes.index(m.concept_class_id)
            if m.concept_class_id in priority_classes
            else 100
        )
        return (sim_score, vocab_score, class_score)

    return min(matches, key=score_match)


async def lookup_concepts_batch(
    db: AsyncSession,
    entities: list[dict],
) -> dict[str, ConceptMatch | None]:
    """Batch lookup for multiple entities.

    Args:
        db: Database session
        entities: List of dicts with 'text' and optional 'entity_type' keys

    Returns:
        Dict mapping entity text to ConceptMatch (or None if not found)
    """
    results: dict[str, ConceptMatch | None] = {}

    for entity in entities:
        text = entity.get("text", "")
        entity_type = entity.get("entity_type", "")

        # Map entity_type to domain
        domain = _entity_type_to_domain(entity_type)

        match = await lookup_concept(db, text, domain)
        results[text] = match

    return results


def _entity_type_to_domain(entity_type: str) -> str | None:
    """Map NLP entity types to OMOP domains."""
    mapping = {
        "DRUG": "Drug",
        "MEDICATION": "Drug",
        "CONDITION": "Condition",
        "DISEASE": "Condition",
        "SYMPTOM": "Condition",
        "MEASUREMENT": "Measurement",
        "LAB": "Measurement",
        "OBSERVATION": "Observation",
        "PROCEDURE": "Procedure",
        "DEVICE": "Device",
    }
    return mapping.get(entity_type.upper())


# Simple in-memory cache for development/testing
_concept_cache: dict[str, ConceptMatch | None] = {}


async def lookup_concept_cached(
    db: AsyncSession,
    text: str,
    domain: str | None = None,
) -> ConceptMatch | None:
    """Cached concept lookup (uses simple in-memory cache).

    For production, this should be replaced with Redis caching.
    """
    cache_key = f"{text.lower()}:{domain or 'any'}"

    if cache_key in _concept_cache:
        return _concept_cache[cache_key]

    match = await lookup_concept(db, text, domain)
    _concept_cache[cache_key] = match

    return match


def clear_concept_cache() -> None:
    """Clear the concept cache."""
    _concept_cache.clear()
