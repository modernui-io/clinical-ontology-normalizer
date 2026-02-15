"""KG Merge Validator - P1-007.

Provenance integrity checks for KG entity merge/deduplication.
Rejects merges based only on substring matching; requires either exact
concept ID match, OMOP concept match, or high-confidence NLP coreference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MergeStrategy(str, Enum):
    """How two entities were determined to be merge candidates."""

    EXACT_CONCEPT_ID = "exact_concept_id"
    OMOP_CONCEPT_MATCH = "omop_concept_match"
    NLP_COREFERENCE = "nlp_coreference"
    SUBSTRING_MATCH = "substring_match"
    WORD_OVERLAP = "word_overlap"


@dataclass
class MergeCandidate:
    """Represents one side of a potential KG entity merge."""

    node_id: str
    label: str
    node_type: str
    omop_concept_id: int | None = None
    assertion: str = "PRESENT"
    confidence: float = 1.0
    properties: dict = field(default_factory=dict)


@dataclass
class MergeDecision:
    """Result of merge validation."""

    approved: bool
    strategy: MergeStrategy
    reason: str
    similarity_score: float = 0.0


# Minimum NLP coreference confidence to allow merge
_MIN_COREFERENCE_CONFIDENCE = 0.90


def validate_merge_provenance(
    entity_a: MergeCandidate,
    entity_b: MergeCandidate,
    *,
    coreference_confidence: float | None = None,
) -> MergeDecision:
    """Validate whether two KG entities should be merged.

    Rejects merges that rely solely on substring matching.
    Accepted merge strategies (in priority order):
      1. Exact OMOP concept_id match
      2. OMOP concept match (both have concept IDs in same hierarchy)
      3. High-confidence NLP coreference (>= 0.90)

    Rejected:
      - Substring-only match
      - Word-overlap-only match
      - Mismatched assertions (e.g. PRESENT vs ABSENT)
      - Mismatched node types

    Args:
        entity_a: First entity candidate.
        entity_b: Second entity candidate.
        coreference_confidence: Optional NLP coreference score between
            the two entities (0.0-1.0).

    Returns:
        MergeDecision indicating whether the merge is approved.
    """
    # Gate: different node types never merge
    if entity_a.node_type != entity_b.node_type:
        return MergeDecision(
            approved=False,
            strategy=MergeStrategy.WORD_OVERLAP,
            reason=f"Node type mismatch: {entity_a.node_type} vs {entity_b.node_type}",
        )

    # Gate: different assertions never merge (e.g. HIV present vs HIV absent)
    if entity_a.assertion != entity_b.assertion:
        return MergeDecision(
            approved=False,
            strategy=MergeStrategy.WORD_OVERLAP,
            reason=f"Assertion mismatch: {entity_a.assertion} vs {entity_b.assertion}",
        )

    # Strategy 1: Exact OMOP concept_id match
    if (
        entity_a.omop_concept_id is not None
        and entity_b.omop_concept_id is not None
        and entity_a.omop_concept_id == entity_b.omop_concept_id
    ):
        return MergeDecision(
            approved=True,
            strategy=MergeStrategy.EXACT_CONCEPT_ID,
            reason=f"Exact OMOP concept_id match: {entity_a.omop_concept_id}",
            similarity_score=1.0,
        )

    # Strategy 2: Both have OMOP concept IDs (different) - check hierarchy
    if (
        entity_a.omop_concept_id is not None
        and entity_b.omop_concept_id is not None
    ):
        # Different concept IDs -> not a merge (they are distinct concepts)
        return MergeDecision(
            approved=False,
            strategy=MergeStrategy.OMOP_CONCEPT_MATCH,
            reason=(
                f"Different OMOP concepts: {entity_a.omop_concept_id} "
                f"vs {entity_b.omop_concept_id}"
            ),
            similarity_score=0.0,
        )

    # Strategy 3: NLP coreference
    if coreference_confidence is not None:
        if coreference_confidence >= _MIN_COREFERENCE_CONFIDENCE:
            return MergeDecision(
                approved=True,
                strategy=MergeStrategy.NLP_COREFERENCE,
                reason=(
                    f"NLP coreference confidence {coreference_confidence:.2f} "
                    f">= threshold {_MIN_COREFERENCE_CONFIDENCE}"
                ),
                similarity_score=coreference_confidence,
            )
        else:
            return MergeDecision(
                approved=False,
                strategy=MergeStrategy.NLP_COREFERENCE,
                reason=(
                    f"NLP coreference confidence {coreference_confidence:.2f} "
                    f"below threshold {_MIN_COREFERENCE_CONFIDENCE}"
                ),
                similarity_score=coreference_confidence,
            )

    # Detect substring-only match and REJECT it
    label_a = entity_a.label.lower()
    label_b = entity_b.label.lower()

    if label_a == label_b:
        # Exact text match is acceptable even without OMOP
        return MergeDecision(
            approved=True,
            strategy=MergeStrategy.OMOP_CONCEPT_MATCH,
            reason="Exact label match",
            similarity_score=1.0,
        )

    if label_a in label_b or label_b in label_a:
        # Substring match without concept backing -> REJECT
        logger.warning(
            "Rejected merge on substring-only match: '%s' vs '%s'",
            entity_a.label,
            entity_b.label,
        )
        return MergeDecision(
            approved=False,
            strategy=MergeStrategy.SUBSTRING_MATCH,
            reason=(
                f"Substring-only match rejected: "
                f"'{entity_a.label}' vs '{entity_b.label}'"
            ),
            similarity_score=0.5,
        )

    # Word overlap without concept backing -> REJECT
    words_a = set(label_a.split())
    words_b = set(label_b.split())
    common = words_a & words_b
    if common:
        logger.warning(
            "Rejected merge on word-overlap-only match: '%s' vs '%s' (common: %s)",
            entity_a.label,
            entity_b.label,
            common,
        )
        return MergeDecision(
            approved=False,
            strategy=MergeStrategy.WORD_OVERLAP,
            reason=(
                f"Word-overlap-only match rejected: "
                f"'{entity_a.label}' vs '{entity_b.label}' "
                f"(common words: {common})"
            ),
            similarity_score=len(common) / max(len(words_a | words_b), 1),
        )

    # No relationship found at all
    return MergeDecision(
        approved=False,
        strategy=MergeStrategy.WORD_OVERLAP,
        reason=f"No matching signal between '{entity_a.label}' and '{entity_b.label}'",
        similarity_score=0.0,
    )
