"""Ensemble NLP Service for Clinical Text Processing.

Combines multiple NLP extraction methods for improved accuracy:
- Rule-based extraction: High precision for patterns (medications, vitals, labs)
- ML-based NER: High recall for clinical entities (conditions, drugs, procedures)
- Value extraction: Quantitative measurements with unit normalization
- Relation extraction: Relationships between clinical entities

The ensemble uses voting and confidence boosting when multiple methods agree.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.services.nlp import BaseNLPService, ExtractedMention, NLPServiceInterface
from app.services.nlp_rule_based import RuleBasedNLPService
from app.services.nlp_clinical_ner import (
    ClinicalNERService,
    TransformerNERConfig,
    get_clinical_ner_service,
)
from app.services.nlp_modernbert_ner import (
    ModernBERTNERService,
    ModernBERTConfig,
    get_modernbert_ner_service,
)
from app.services.value_extraction import (
    ValueExtractionService,
    get_value_extraction_service,
)
from app.services.relation_extraction import (
    ExtractedRelation,
    RelationExtractionService,
    get_relation_extraction_service,
)

logger = logging.getLogger(__name__)


@dataclass
class EnsembleConfig:
    """Configuration for the ensemble NLP service."""

    # Enable/disable individual extractors
    use_rule_based: bool = True
    use_ml_ner: bool = True
    use_modernbert: bool = True  # ModernBERT with 8K context
    use_value_extraction: bool = True
    use_relation_extraction: bool = True

    # Confidence thresholds
    min_confidence: float = 0.5
    rule_based_confidence: float = 0.85
    ml_ner_confidence: float = 0.80
    modernbert_confidence: float = 0.88  # Higher base confidence (better accuracy)
    value_confidence: float = 0.90

    # ModernBERT weight multiplier (1.2x due to better accuracy on long contexts)
    modernbert_weight: float = 1.2

    # Confidence boosting when multiple methods agree
    agreement_boost: float = 0.10  # Add this when methods agree
    max_confidence: float = 0.99  # Cap confidence at this level

    # Overlap handling
    prefer_longer_spans: bool = True  # Prefer longer entity spans
    prefer_higher_confidence: bool = True  # Prefer higher confidence

    # Domain-specific preferences
    # When a domain-specific extractor finds an entity, prefer it
    domain_preferences: dict[str, str] = field(default_factory=lambda: {
        Domain.MEASUREMENT.value: "value",  # Prefer value extraction for measurements
        Domain.DRUG.value: "rule_based",  # Prefer rule-based for drugs
        Domain.CONDITION.value: "ml_ner",  # Prefer ML NER for conditions
    })


@dataclass
class EnsembleResult:
    """Result from ensemble extraction."""

    # Extracted mentions (merged from all methods)
    mentions: list[ExtractedMention] = field(default_factory=list)

    # Extracted relations
    relations: list[ExtractedRelation] = field(default_factory=list)

    # Extraction statistics
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsembleNLPService(BaseNLPService):
    """Ensemble NLP service combining multiple extraction methods.

    This service orchestrates multiple NLP extractors and combines their
    results for improved accuracy. It uses:

    1. **Rule-based extraction**: High-precision pattern matching for
       well-defined patterns like medication doses, vital signs, and
       laboratory values.

    2. **ML-based NER**: Transformer-based named entity recognition for
       broader coverage of clinical entities including conditions,
       drugs, and procedures.

    3. **Value extraction**: Specialized extraction for quantitative
       measurements with unit normalization.

    4. **Relation extraction**: Identifies relationships between
       entities like drug-treats-condition.

    The ensemble combines results using:
    - Span overlap detection to merge duplicate mentions
    - Confidence boosting when multiple methods agree
    - Domain-specific preferences for extractor selection

    Usage:
        service = EnsembleNLPService()
        result = service.extract_all(text, document_id)

        # Access mentions
        for mention in result.mentions:
            print(f"{mention.text}: {mention.domain_hint}")

        # Access relations
        for relation in result.relations:
            print(f"{relation.source_text} -> {relation.target_text}")

    Note: For best results, ensure all dependencies are installed:
        pip install spacy transformers torch
    """

    config: EnsembleConfig = field(default_factory=EnsembleConfig)

    # Component services (lazy initialized)
    _rule_based_service: RuleBasedNLPService | None = field(default=None, init=False)
    _ml_ner_service: ClinicalNERService | None = field(default=None, init=False)
    _modernbert_service: ModernBERTNERService | None = field(default=None, init=False)
    _value_service: ValueExtractionService | None = field(default=None, init=False)
    _relation_service: RelationExtractionService | None = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)

    def _initialize(self) -> None:
        """Lazy initialization of component services."""
        if self._initialized:
            return

        if self.config.use_rule_based:
            self._rule_based_service = RuleBasedNLPService()
            logger.info("Initialized rule-based NLP service")

        if self.config.use_ml_ner:
            self._ml_ner_service = get_clinical_ner_service()
            logger.info("Initialized ML NER service")

        if self.config.use_modernbert:
            try:
                self._modernbert_service = get_modernbert_ner_service()
                if self._modernbert_service.is_available():
                    logger.info("Initialized ModernBERT NER service (8K context)")
                else:
                    logger.info("ModernBERT service unavailable, using fallback NER")
                    self._modernbert_service = None
            except Exception as e:
                logger.warning(f"Could not initialize ModernBERT service: {e}")
                self._modernbert_service = None

        if self.config.use_value_extraction:
            self._value_service = get_value_extraction_service()
            logger.info("Initialized value extraction service")

        if self.config.use_relation_extraction:
            self._relation_service = get_relation_extraction_service()
            logger.info("Initialized relation extraction service")

        self._initialized = True

    def _spans_overlap(
        self,
        start1: int,
        end1: int,
        start2: int,
        end2: int,
        threshold: float = 0.5,
    ) -> bool:
        """Check if two spans overlap significantly.

        Args:
            start1, end1: First span boundaries
            start2, end2: Second span boundaries
            threshold: Minimum overlap ratio (0-1)

        Returns:
            True if spans overlap by at least threshold ratio
        """
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_length = max(0, overlap_end - overlap_start)

        if overlap_length == 0:
            return False

        # Calculate overlap ratio relative to smaller span
        span1_length = end1 - start1
        span2_length = end2 - start2
        min_length = min(span1_length, span2_length)

        if min_length == 0:
            return False

        overlap_ratio = overlap_length / min_length
        return overlap_ratio >= threshold

    def _merge_mentions(
        self,
        mentions_by_source: dict[str, list[ExtractedMention]],
    ) -> list[ExtractedMention]:
        """Merge mentions from multiple sources.

        Handles overlapping spans by:
        1. Checking domain preferences
        2. Preferring longer spans
        3. Preferring higher confidence
        4. Boosting confidence when methods agree

        Args:
            mentions_by_source: Dict mapping source name to list of mentions

        Returns:
            Merged list of mentions
        """
        # Flatten all mentions with their sources
        all_mentions: list[tuple[str, ExtractedMention]] = []
        for source, mentions in mentions_by_source.items():
            for mention in mentions:
                all_mentions.append((source, mention))

        if not all_mentions:
            return []

        # Sort by start offset, then by span length (descending)
        all_mentions.sort(
            key=lambda x: (x[1].start_offset, -(x[1].end_offset - x[1].start_offset))
        )

        merged: list[ExtractedMention] = []
        used_spans: list[tuple[int, int]] = []

        for source, mention in all_mentions:
            # Check if this span overlaps with an already-included span
            overlaps_with = None
            for i, (used_start, used_end) in enumerate(used_spans):
                if self._spans_overlap(
                    mention.start_offset, mention.end_offset,
                    used_start, used_end
                ):
                    overlaps_with = i
                    break

            if overlaps_with is not None:
                # Check if we should replace the existing mention
                existing = merged[overlaps_with]

                should_replace = False

                # Check domain preference
                domain = mention.domain_hint
                if domain and domain in self.config.domain_preferences:
                    preferred_source = self.config.domain_preferences[domain]
                    if source == preferred_source:
                        should_replace = True

                # Check span length preference
                if (self.config.prefer_longer_spans and
                    (mention.end_offset - mention.start_offset) >
                    (existing.end_offset - existing.start_offset)):
                    should_replace = True

                # Check confidence preference
                if (self.config.prefer_higher_confidence and
                    mention.confidence > existing.confidence):
                    should_replace = True

                if should_replace:
                    # Replace existing mention
                    merged[overlaps_with] = mention
                    used_spans[overlaps_with] = (mention.start_offset, mention.end_offset)
                else:
                    # Boost confidence of existing mention (agreement)
                    existing.confidence = min(
                        existing.confidence + self.config.agreement_boost,
                        self.config.max_confidence
                    )
            else:
                # No overlap, add new mention
                merged.append(mention)
                used_spans.append((mention.start_offset, mention.end_offset))

        return merged

    def _extract_rule_based(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None,
    ) -> list[ExtractedMention]:
        """Extract mentions using rule-based service."""
        if not self._rule_based_service:
            return []

        try:
            mentions = self._rule_based_service.extract_mentions(
                text, document_id, note_type
            )
            # Set base confidence
            for m in mentions:
                if m.confidence < self.config.rule_based_confidence:
                    m.confidence = self.config.rule_based_confidence
            return mentions
        except Exception as e:
            logger.warning(f"Rule-based extraction failed: {e}")
            return []

    def _extract_ml_ner(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None,
    ) -> list[ExtractedMention]:
        """Extract mentions using ML NER service.

        Gracefully handles long texts that may exceed model limits.
        """
        if not self._ml_ner_service:
            return []

        try:
            mentions = self._ml_ner_service.extract_mentions(
                text, document_id, note_type
            )
            return mentions
        except Exception as e:
            logger.warning(f"ML NER extraction failed: {e}")
            # Log text length for debugging
            logger.debug(f"Failed text length: {len(text)} chars")
            return []

    def _extract_modernbert(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None,
    ) -> list[ExtractedMention]:
        """Extract mentions using ModernBERT NER service.

        ModernBERT has 8K context and higher accuracy, so we apply
        a weight multiplier to its confidence scores. Long texts are
        automatically chunked by the underlying service.
        """
        if not self._modernbert_service:
            return []

        try:
            mentions = self._modernbert_service.extract_mentions(
                text, document_id, note_type
            )
            # Apply weight multiplier for ModernBERT's higher accuracy
            for m in mentions:
                boosted = m.confidence * self.config.modernbert_weight
                m.confidence = min(boosted, self.config.max_confidence)
            logger.debug(f"ModernBERT extracted {len(mentions)} mentions from {len(text)} chars")
            return mentions
        except Exception as e:
            logger.warning(f"ModernBERT extraction failed: {e}")
            logger.debug(f"Failed text length: {len(text)} chars")
            return []

    def _extract_values(
        self,
        text: str,
        document_id: UUID,
    ) -> list[ExtractedMention]:
        """Convert extracted values to mentions."""
        if not self._value_service:
            return []

        try:
            values = self._value_service.extract_all(text)
            mentions = []

            for value in values:
                # Map value type to domain
                domain_map = {
                    "vital_sign": Domain.MEASUREMENT.value,
                    "lab_result": Domain.MEASUREMENT.value,
                    "medication_dose": Domain.DRUG.value,
                    "measurement": Domain.MEASUREMENT.value,
                    "score": Domain.MEASUREMENT.value,
                }
                domain = domain_map.get(value.value_type.value, Domain.MEASUREMENT.value)

                # Create mention from value
                mention = ExtractedMention(
                    text=value.text,
                    start_offset=value.start_offset,
                    end_offset=value.end_offset,
                    lexical_variant=value.name.lower(),
                    domain_hint=domain,
                    omop_concept_id=value.omop_concept_id,
                    assertion=Assertion.PRESENT,
                    temporality=Temporality.CURRENT,
                    experiencer=Experiencer.PATIENT,
                    confidence=self.config.value_confidence,
                )
                mentions.append(mention)

            return mentions
        except Exception as e:
            logger.warning(f"Value extraction failed: {e}")
            return []

    def _extract_relations(
        self,
        text: str,
        mentions: list[ExtractedMention],
    ) -> list[ExtractedRelation]:
        """Extract relations between mentions."""
        if not self._relation_service:
            return []

        try:
            return self._relation_service.extract_all(text, mentions)
        except Exception as e:
            logger.warning(f"Relation extraction failed: {e}")
            return []

    def extract_mentions(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
    ) -> list[ExtractedMention]:
        """Extract mentions using the ensemble of methods.

        This is the main extraction method that combines results from
        all enabled extractors. Long texts are automatically chunked
        by the underlying services.

        Args:
            text: Clinical text to process
            document_id: UUID of the source document
            note_type: Optional note type for context

        Returns:
            Merged list of ExtractedMention objects
        """
        self._initialize()

        text_len = len(text)
        logger.info(f"Ensemble extraction starting for {text_len} chars text")

        mentions_by_source: dict[str, list[ExtractedMention]] = {}

        # Rule-based extraction
        if self.config.use_rule_based:
            rule_mentions = self._extract_rule_based(text, document_id, note_type)
            if rule_mentions:
                mentions_by_source["rule_based"] = rule_mentions
                logger.debug(f"Rule-based: {len(rule_mentions)} mentions")

        # ModernBERT extraction (preferred for long documents)
        if self.config.use_modernbert and self._modernbert_service:
            modernbert_mentions = self._extract_modernbert(text, document_id, note_type)
            if modernbert_mentions:
                mentions_by_source["modernbert"] = modernbert_mentions
                logger.debug(f"ModernBERT: {len(modernbert_mentions)} mentions")

        # ML NER extraction (fallback/supplement)
        if self.config.use_ml_ner:
            ml_mentions = self._extract_ml_ner(text, document_id, note_type)
            if ml_mentions:
                mentions_by_source["ml_ner"] = ml_mentions
                logger.debug(f"ML NER: {len(ml_mentions)} mentions")

        # Value extraction
        if self.config.use_value_extraction:
            value_mentions = self._extract_values(text, document_id)
            if value_mentions:
                mentions_by_source["value"] = value_mentions
                logger.debug(f"Values: {len(value_mentions)} mentions")

        # Merge all mentions
        merged = self._merge_mentions(mentions_by_source)

        # Filter by confidence
        filtered = [m for m in merged if m.confidence >= self.config.min_confidence]

        logger.info(
            f"Ensemble extraction: {sum(len(v) for v in mentions_by_source.values())} "
            f"raw mentions -> {len(filtered)} merged mentions"
        )

        return filtered

    def extract_all(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
    ) -> EnsembleResult:
        """Extract both mentions and relations.

        Performs full extraction pipeline:
        1. Extract mentions using all enabled methods
        2. Merge and deduplicate mentions
        3. Extract relations between mentions

        Args:
            text: Clinical text to process
            document_id: UUID of the source document
            note_type: Optional note type for context

        Returns:
            EnsembleResult with mentions, relations, and stats
        """
        import time

        self._initialize()
        stats: dict[str, Any] = {}

        # Extract mentions
        start_time = time.perf_counter()
        mentions = self.extract_mentions(text, document_id, note_type)
        stats["mention_extraction_ms"] = (time.perf_counter() - start_time) * 1000
        stats["mention_count"] = len(mentions)

        # Extract relations
        relations = []
        if self.config.use_relation_extraction and mentions:
            start_time = time.perf_counter()
            relations = self._extract_relations(text, mentions)
            stats["relation_extraction_ms"] = (time.perf_counter() - start_time) * 1000
            stats["relation_count"] = len(relations)

        # Compute domain distribution
        domain_counts: dict[str, int] = {}
        for m in mentions:
            domain = m.domain_hint or "unknown"
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        stats["by_domain"] = domain_counts

        # Compute relation type distribution
        relation_counts: dict[str, int] = {}
        for r in relations:
            rel_type = r.relation_type.value
            relation_counts[rel_type] = relation_counts.get(rel_type, 0) + 1
        stats["by_relation_type"] = relation_counts

        return EnsembleResult(
            mentions=mentions,
            relations=relations,
            stats=stats,
        )


# Singleton instance
_ensemble_service: EnsembleNLPService | None = None
_ensemble_lock = threading.Lock()


def get_ensemble_nlp_service(
    config: EnsembleConfig | None = None,
) -> EnsembleNLPService:
    """Get the singleton ensemble NLP service.

    Args:
        config: Optional configuration. Only used on first call.

    Returns:
        EnsembleNLPService instance.
    """
    global _ensemble_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _ensemble_service is None:
        with _ensemble_lock:
            if _ensemble_service is None:
                _ensemble_service = EnsembleNLPService(
                    config=config or EnsembleConfig()
                )
    return _ensemble_service


def reset_ensemble_nlp_service() -> None:
    """Reset the singleton service (mainly for testing)."""
    global _ensemble_service
    with _ensemble_lock:
        _ensemble_service = None
