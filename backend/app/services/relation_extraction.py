"""Clinical Relation Extraction Service.

Extracts relationships between clinical entities such as:
- Drug treats Condition
- Drug causes Side Effect
- Symptom indicates Condition
- Test diagnoses Condition
- Condition requires Procedure

Uses pattern matching and dependency parsing for relation detection.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from app.schemas.base import Domain
from app.services.nlp import ExtractedMention

logger = logging.getLogger(__name__)


class RelationType(str, Enum):
    """Types of clinical relationships."""

    # Treatment relations
    TREATS = "treats"  # Drug treats Condition
    PRESCRIBED_FOR = "prescribed_for"  # Drug prescribed for Condition
    ALLEVIATES = "alleviates"  # Drug alleviates Symptom

    # Adverse effect relations
    CAUSES = "causes"  # Drug causes Side Effect
    CONTRAINDICATED_FOR = "contraindicated_for"  # Drug contraindicated for Condition

    # Diagnostic relations
    INDICATES = "indicates"  # Symptom indicates Condition
    DIAGNOSES = "diagnoses"  # Test diagnoses Condition
    FINDING_OF = "finding_of"  # Measurement is finding of Condition

    # Procedural relations
    REQUIRES = "requires"  # Condition requires Procedure
    PERFORMED_FOR = "performed_for"  # Procedure performed for Condition

    # Anatomical relations
    LOCATED_IN = "located_in"  # Finding located in Anatomic Site
    AFFECTS = "affects"  # Condition affects Anatomic Site

    # Temporal relations
    PRECEDES = "precedes"  # Event precedes Event
    FOLLOWS = "follows"  # Event follows Event
    CONCURRENT_WITH = "concurrent_with"  # Event concurrent with Event

    # Causal relations
    CAUSED_BY = "caused_by"  # Condition caused by Event
    WORSENED_BY = "worsened_by"  # Condition worsened by Factor


@dataclass
class ExtractedRelation:
    """A relationship extracted from clinical text."""

    # Relation identifiers
    id: UUID = field(default_factory=uuid4)

    # Source entity (subject)
    source_text: str = ""
    source_start: int = 0
    source_end: int = 0
    source_domain: str | None = None
    source_mention_id: UUID | None = None

    # Target entity (object)
    target_text: str = ""
    target_start: int = 0
    target_end: int = 0
    target_domain: str | None = None
    target_mention_id: UUID | None = None

    # Relation properties
    relation_type: RelationType = RelationType.TREATS
    confidence: float = 0.0
    evidence_text: str = ""  # The text span containing the relation
    extraction_method: str = "pattern"  # pattern, dependency, ml


# ============================================================================
# Relation Patterns
# ============================================================================

# Pattern format: (regex, source_domain, target_domain, relation_type)
# Source is captured in group 1, target in group 2

TREATMENT_PATTERNS = [
    # Drug for Condition patterns
    (r"(\b\w+(?:\s+\w+)?\b)\s+(?:for|to\s+treat|for\s+treatment\s+of)\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.DRUG.value, Domain.CONDITION.value, RelationType.TREATS),

    # Started on Drug for Condition
    (r"started\s+(?:on\s+)?(\b\w+(?:\s+\w+)?\b)\s+for\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.DRUG.value, Domain.CONDITION.value, RelationType.PRESCRIBED_FOR),

    # Continue Drug for Condition
    (r"continue\s+(\b\w+(?:\s+\w+)?\b)\s+for\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.DRUG.value, Domain.CONDITION.value, RelationType.TREATS),

    # Condition - Drug pattern (common in assessment)
    (r"(\b\w+(?:\s+\w+)*\b)\s*[-–:]\s*(?:start|continue|on)\s+(\b\w+(?:\s+\w+)?\b)",
     Domain.CONDITION.value, Domain.DRUG.value, RelationType.TREATS),

    # Patient on Drug for Condition
    (r"(?:patient\s+)?on\s+(\b\w+(?:\s+\w+)?\b)\s+for\s+(?:his|her|their\s+)?(\b\w+(?:\s+\w+)*\b)",
     Domain.DRUG.value, Domain.CONDITION.value, RelationType.TREATS),

    # Condition, treated with Drug (history format)
    (r"(\b\w+(?:\s+\w+)*\b),?\s+(?:treated|managed)\s+(?:with|on)\s+(\b\w+(?:\s+\w+)?\b)",
     Domain.CONDITION.value, Domain.DRUG.value, RelationType.TREATS),

    # Condition, controlled on Drug (history format)
    (r"(\b\w+(?:\s+\w+)*\b),?\s+(?:controlled|stable)\s+(?:on|with)\s+(\b\w+(?:\s+\w+)?\b)",
     Domain.CONDITION.value, Domain.DRUG.value, RelationType.TREATS),

    # Condition, on Drug (simplified history format)
    (r"(\b\w+(?:\s+\w+)*\b),?\s+on\s+(\b\w+(?:\s+\w+)?\b)",
     Domain.CONDITION.value, Domain.DRUG.value, RelationType.TREATS),
]

ADVERSE_PATTERNS = [
    # Drug causes Side Effect
    (r"(\b\w+(?:\s+\w+)?\b)\s+(?:caused?|causing|leads?\s+to|resulted?\s+in)\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.DRUG.value, Domain.CONDITION.value, RelationType.CAUSES),

    # Side effect from Drug
    (r"(\b\w+(?:\s+\w+)*\b)\s+(?:from|due\s+to|secondary\s+to)\s+(\b\w+(?:\s+\w+)?\b)",
     Domain.CONDITION.value, Domain.DRUG.value, RelationType.CAUSED_BY),

    # Allergic to Drug
    (r"allergic\s+(?:to|reaction\s+to)\s+(\b\w+(?:\s+\w+)?\b)",
     None, Domain.DRUG.value, RelationType.CONTRAINDICATED_FOR),
]

DIAGNOSTIC_PATTERNS = [
    # Test shows/reveals Condition
    (r"(\b\w+(?:\s+\w+)?\b)\s+(?:shows?|revealed?|demonstrates?|confirms?)\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.MEASUREMENT.value, Domain.CONDITION.value, RelationType.DIAGNOSES),

    # Condition diagnosed by Test
    (r"(\b\w+(?:\s+\w+)*\b)\s+(?:diagnosed\s+(?:by|with|on)|confirmed\s+(?:by|on))\s+(\b\w+(?:\s+\w+)?\b)",
     Domain.CONDITION.value, Domain.MEASUREMENT.value, RelationType.DIAGNOSES),

    # Symptom suggestive of Condition
    (r"(\b\w+(?:\s+\w+)*\b)\s+(?:suggestive\s+of|consistent\s+with|indicative\s+of|concerning\s+for)\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.OBSERVATION.value, Domain.CONDITION.value, RelationType.INDICATES),
]

PROCEDURE_PATTERNS = [
    # Procedure for Condition
    (r"(\b\w+(?:\s+\w+)*\b)\s+(?:for|to\s+treat|performed\s+for)\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.PROCEDURE.value, Domain.CONDITION.value, RelationType.PERFORMED_FOR),

    # Condition - Procedure pattern
    (r"(\b\w+(?:\s+\w+)*\b)\s*[-–:]\s*(?:schedule|perform|undergo)\s+(\b\w+(?:\s+\w+)*\b)",
     Domain.CONDITION.value, Domain.PROCEDURE.value, RelationType.REQUIRES),
]

ANATOMICAL_PATTERNS = [
    # Condition in/of Anatomy
    (r"(\b\w+(?:\s+\w+)*\b)\s+(?:in|of|involving)\s+(?:the\s+)?(\b\w+(?:\s+\w+)*\b)",
     Domain.CONDITION.value, Domain.SPEC_ANATOMIC_SITE.value, RelationType.LOCATED_IN),

    # Anatomy Condition (e.g., "chest pain", "knee arthritis")
    (r"(\b\w+)\s+(pain|mass|lesion|tumor|infection|inflammation|swelling)",
     Domain.SPEC_ANATOMIC_SITE.value, Domain.CONDITION.value, RelationType.AFFECTS),
]


# Combine all patterns
ALL_PATTERNS = (
    TREATMENT_PATTERNS +
    ADVERSE_PATTERNS +
    DIAGNOSTIC_PATTERNS +
    PROCEDURE_PATTERNS +
    ANATOMICAL_PATTERNS
)


@dataclass
class RelationExtractionConfig:
    """Configuration for relation extraction."""

    # Minimum confidence threshold
    min_confidence: float = 0.5

    # Maximum distance between entities (in characters)
    max_entity_distance: int = 200

    # Use dependency parsing if available
    use_dependency_parsing: bool = True

    # Use pattern matching
    use_patterns: bool = True

    # Domain filters (only extract relations between these domains)
    allowed_source_domains: list[str] | None = None
    allowed_target_domains: list[str] | None = None


@dataclass
class RelationExtractionService:
    """Service for extracting clinical relations from text.

    This service extracts relationships between clinical entities using:
    1. Pattern matching with curated clinical patterns
    2. Entity proximity analysis with domain-based rules
    3. Dependency parsing (when spaCy is available)

    Usage:
        service = RelationExtractionService()

        # Extract mentions first using NER
        mentions = ner_service.extract_mentions(text, doc_id)

        # Then extract relations between mentions
        relations = service.extract_relations(text, mentions)

        # Or extract both patterns and mention-based relations
        all_relations = service.extract_all(text, mentions)
    """

    config: RelationExtractionConfig = field(default_factory=RelationExtractionConfig)
    _nlp: Any = field(default=None, init=False, repr=False)
    _spacy_available: bool = field(default=False, init=False)
    _initialized: bool = field(default=False, init=False)

    def _initialize(self) -> None:
        """Lazy initialization of NLP components."""
        if self._initialized:
            return

        if self.config.use_dependency_parsing:
            try:
                import spacy
                try:
                    self._nlp = spacy.load("en_core_web_sm")
                    self._spacy_available = True
                    logger.info("Loaded spaCy for dependency parsing")
                except OSError:
                    logger.warning("spaCy model not available for dependency parsing")
            except ImportError:
                logger.warning("spaCy not installed, dependency parsing disabled")

        self._initialized = True

    def _extract_pattern_relations(self, text: str) -> list[ExtractedRelation]:
        """Extract relations using pattern matching."""
        relations: list[ExtractedRelation] = []

        for pattern, source_domain, target_domain, relation_type in ALL_PATTERNS:
            try:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Get matched groups
                    groups = match.groups()
                    if len(groups) >= 2:
                        source_text = groups[0]
                        target_text = groups[1]
                    elif len(groups) == 1:
                        # For patterns with only target (e.g., "allergic to X")
                        source_text = ""
                        target_text = groups[0]
                    else:
                        continue

                    # Skip very short matches
                    if len(target_text.strip()) < 2:
                        continue

                    relation = ExtractedRelation(
                        source_text=source_text.strip(),
                        source_start=match.start(1) if source_text else match.start(),
                        source_end=match.end(1) if source_text else match.start(),
                        source_domain=source_domain,
                        target_text=target_text.strip(),
                        target_start=match.start(2) if len(groups) >= 2 else match.start(1),
                        target_end=match.end(2) if len(groups) >= 2 else match.end(1),
                        target_domain=target_domain,
                        relation_type=relation_type,
                        confidence=0.7,  # Pattern matches have moderate confidence
                        evidence_text=match.group(0),
                        extraction_method="pattern",
                    )
                    relations.append(relation)

            except re.error as e:
                logger.debug(f"Pattern error: {e}")
                continue

        return relations

    def _extract_proximity_relations(
        self,
        text: str,
        mentions: list[ExtractedMention],
    ) -> list[ExtractedRelation]:
        """Extract relations based on entity proximity and domain rules."""
        relations: list[ExtractedRelation] = []

        # Domain pair rules: (source_domain, target_domain, relation_type, keywords)
        domain_rules = [
            (Domain.DRUG.value, Domain.CONDITION.value, RelationType.TREATS,
             ["for", "treat", "treating", "therapy"]),
            (Domain.CONDITION.value, Domain.DRUG.value, RelationType.TREATS,
             ["on", "taking", "continue", "start"]),
            (Domain.OBSERVATION.value, Domain.CONDITION.value, RelationType.INDICATES,
             ["suggestive", "concerning", "indicates", "shows"]),
            (Domain.MEASUREMENT.value, Domain.CONDITION.value, RelationType.DIAGNOSES,
             ["confirms", "shows", "reveals", "positive"]),
            (Domain.PROCEDURE.value, Domain.CONDITION.value, RelationType.PERFORMED_FOR,
             ["for", "to treat", "performed"]),
        ]

        # Check all pairs of mentions
        for i, source_mention in enumerate(mentions):
            for j, target_mention in enumerate(mentions):
                if i == j:
                    continue

                # Check distance
                distance = abs(source_mention.start_offset - target_mention.start_offset)
                if distance > self.config.max_entity_distance:
                    continue

                # Check domain rules
                for src_domain, tgt_domain, rel_type, keywords in domain_rules:
                    if (source_mention.domain_hint == src_domain and
                        target_mention.domain_hint == tgt_domain):

                        # Get text between entities
                        start = min(source_mention.end_offset, target_mention.end_offset)
                        end = max(source_mention.start_offset, target_mention.start_offset)
                        between_text = text[start:end].lower()

                        # Check for keywords
                        has_keyword = any(kw in between_text for kw in keywords)

                        if has_keyword or distance < 50:  # Close entities or keyword present
                            confidence = 0.8 if has_keyword else 0.5

                            relation = ExtractedRelation(
                                source_text=source_mention.text,
                                source_start=source_mention.start_offset,
                                source_end=source_mention.end_offset,
                                source_domain=source_mention.domain_hint,
                                source_mention_id=None,  # Would be set if mentions have IDs
                                target_text=target_mention.text,
                                target_start=target_mention.start_offset,
                                target_end=target_mention.end_offset,
                                target_domain=target_mention.domain_hint,
                                target_mention_id=None,
                                relation_type=rel_type,
                                confidence=confidence,
                                evidence_text=text[min(source_mention.start_offset, target_mention.start_offset):
                                                  max(source_mention.end_offset, target_mention.end_offset)],
                                extraction_method="proximity",
                            )
                            relations.append(relation)
                            break  # Only one relation per pair

        return relations

    def _extract_dependency_relations(
        self,
        text: str,
        mentions: list[ExtractedMention],
    ) -> list[ExtractedRelation]:
        """Extract relations using dependency parsing."""
        if not self._spacy_available or self._nlp is None:
            return []

        relations: list[ExtractedRelation] = []

        try:
            doc = self._nlp(text)

            # Build a map of character positions to tokens
            char_to_token: dict[int, Any] = {}
            for token in doc:
                for i in range(token.idx, token.idx + len(token.text)):
                    char_to_token[i] = token

            # Find tokens for each mention
            mention_tokens: dict[int, list] = {}
            for i, mention in enumerate(mentions):
                tokens = []
                for pos in range(mention.start_offset, mention.end_offset):
                    if pos in char_to_token:
                        token = char_to_token[pos]
                        if token not in tokens:
                            tokens.append(token)
                mention_tokens[i] = tokens

            # Check dependency paths between mention pairs
            for i, source_mention in enumerate(mentions):
                for j, target_mention in enumerate(mentions):
                    if i == j:
                        continue

                    source_tokens = mention_tokens.get(i, [])
                    target_tokens = mention_tokens.get(j, [])

                    if not source_tokens or not target_tokens:
                        continue

                    # Check if there's a dependency path
                    for src_token in source_tokens:
                        for tgt_token in target_tokens:
                            # Direct dependency
                            if tgt_token.head == src_token:
                                relation_type = self._dep_to_relation(
                                    tgt_token.dep_,
                                    source_mention.domain_hint,
                                    target_mention.domain_hint,
                                )
                                if relation_type:
                                    relation = ExtractedRelation(
                                        source_text=source_mention.text,
                                        source_start=source_mention.start_offset,
                                        source_end=source_mention.end_offset,
                                        source_domain=source_mention.domain_hint,
                                        target_text=target_mention.text,
                                        target_start=target_mention.start_offset,
                                        target_end=target_mention.end_offset,
                                        target_domain=target_mention.domain_hint,
                                        relation_type=relation_type,
                                        confidence=0.75,
                                        evidence_text=text[min(src_token.idx, tgt_token.idx):
                                                         max(src_token.idx + len(src_token.text),
                                                             tgt_token.idx + len(tgt_token.text))],
                                        extraction_method="dependency",
                                    )
                                    relations.append(relation)

        except Exception as e:
            logger.warning(f"Dependency parsing failed: {e}")

        return relations

    def _dep_to_relation(
        self,
        dep: str,
        source_domain: str | None,
        target_domain: str | None,
    ) -> RelationType | None:
        """Map dependency label to relation type based on domains."""
        # Dependency label mappings based on domain context
        if source_domain == Domain.DRUG.value and target_domain == Domain.CONDITION.value:
            if dep in ["prep", "pobj", "dobj"]:
                return RelationType.TREATS
        elif source_domain == Domain.CONDITION.value and target_domain == Domain.DRUG.value:
            if dep in ["prep", "pobj"]:
                return RelationType.TREATS
        elif source_domain == Domain.MEASUREMENT.value and target_domain == Domain.CONDITION.value:
            if dep in ["dobj", "attr"]:
                return RelationType.DIAGNOSES
        elif source_domain == Domain.PROCEDURE.value and target_domain == Domain.CONDITION.value:
            if dep in ["prep", "pobj"]:
                return RelationType.PERFORMED_FOR

        return None

    def _deduplicate_relations(
        self,
        relations: list[ExtractedRelation],
    ) -> list[ExtractedRelation]:
        """Remove duplicate relations, keeping highest confidence."""
        # Key: (source_text, target_text, relation_type)
        best_relations: dict[tuple, ExtractedRelation] = {}

        for rel in relations:
            key = (
                rel.source_text.lower().strip(),
                rel.target_text.lower().strip(),
                rel.relation_type,
            )

            if key not in best_relations or rel.confidence > best_relations[key].confidence:
                best_relations[key] = rel

        return list(best_relations.values())

    def extract_pattern_relations(self, text: str) -> list[ExtractedRelation]:
        """Extract relations using pattern matching only.

        Use this for quick extraction without NER mentions.

        Args:
            text: Clinical text to process.

        Returns:
            List of extracted relations.
        """
        if not self.config.use_patterns:
            return []

        relations = self._extract_pattern_relations(text)

        # Filter by confidence
        relations = [r for r in relations if r.confidence >= self.config.min_confidence]

        # Filter by domain if configured
        if self.config.allowed_source_domains:
            relations = [r for r in relations
                        if r.source_domain in self.config.allowed_source_domains]
        if self.config.allowed_target_domains:
            relations = [r for r in relations
                        if r.target_domain in self.config.allowed_target_domains]

        return self._deduplicate_relations(relations)

    def extract_mention_relations(
        self,
        text: str,
        mentions: list[ExtractedMention],
    ) -> list[ExtractedRelation]:
        """Extract relations between pre-extracted mentions.

        Use this when you already have NER mentions and want to find
        relationships between them.

        Args:
            text: Original clinical text.
            mentions: List of extracted mentions from NER.

        Returns:
            List of extracted relations.
        """
        self._initialize()

        relations: list[ExtractedRelation] = []

        # Proximity-based extraction
        relations.extend(self._extract_proximity_relations(text, mentions))

        # Dependency-based extraction
        if self.config.use_dependency_parsing:
            relations.extend(self._extract_dependency_relations(text, mentions))

        # Filter by confidence
        relations = [r for r in relations if r.confidence >= self.config.min_confidence]

        # Filter by domain if configured
        if self.config.allowed_source_domains:
            relations = [r for r in relations
                        if r.source_domain in self.config.allowed_source_domains]
        if self.config.allowed_target_domains:
            relations = [r for r in relations
                        if r.target_domain in self.config.allowed_target_domains]

        return self._deduplicate_relations(relations)

    def extract_all(
        self,
        text: str,
        mentions: list[ExtractedMention] | None = None,
    ) -> list[ExtractedRelation]:
        """Extract all relations using all available methods.

        Args:
            text: Clinical text to process.
            mentions: Optional list of pre-extracted mentions.

        Returns:
            Combined list of extracted relations (deduplicated).
        """
        self._initialize()

        all_relations: list[ExtractedRelation] = []

        # Pattern-based extraction
        if self.config.use_patterns:
            all_relations.extend(self._extract_pattern_relations(text))

        # Mention-based extraction
        if mentions:
            all_relations.extend(self._extract_proximity_relations(text, mentions))
            if self.config.use_dependency_parsing:
                all_relations.extend(self._extract_dependency_relations(text, mentions))

        # Filter and deduplicate
        all_relations = [r for r in all_relations if r.confidence >= self.config.min_confidence]

        return self._deduplicate_relations(all_relations)


# Singleton instance
_relation_service: RelationExtractionService | None = None
_relation_lock = threading.Lock()


def get_relation_extraction_service(
    config: RelationExtractionConfig | None = None,
) -> RelationExtractionService:
    """Get the singleton relation extraction service.

    Args:
        config: Optional configuration. Only used on first call.

    Returns:
        RelationExtractionService instance.
    """
    global _relation_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _relation_service is None:
        with _relation_lock:
            if _relation_service is None:
                _relation_service = RelationExtractionService(
                    config=config or RelationExtractionConfig()
                )
    return _relation_service


def reset_relation_extraction_service() -> None:
    """Reset the singleton service (mainly for testing)."""
    global _relation_service
    _relation_service = None
