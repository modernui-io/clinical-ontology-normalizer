"""Rule-based NLP service for clinical mention extraction.

Uses Aho-Corasick algorithm for O(n) pattern matching and vocabulary
lookups to extract mentions from clinical documents.

# MATURITY: deprecated-standalone — use via nlp_entity or nlp_ensemble
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

try:
    import ahocorasick
    HAS_AHOCORASICK = True
except ImportError:
    ahocorasick = None  # type: ignore
    HAS_AHOCORASICK = False

from app.schemas.base import Assertion, Experiencer, Temporality
from app.services.assertion_classifier import (
    ProbabilisticAssertionClassifier,
    classify_assertion,
)
from app.services.nlp import BaseNLPService, ExtractedMention
from app.services.section_parser import ClinicalSection, SectionParser, get_section_parser
from app.services.temporal_extractor import TemporalExtractor
from app.services.vocabulary import VocabularyService, get_vocabulary_service

if TYPE_CHECKING:
    from ahocorasick import Automaton

logger = logging.getLogger(__name__)


class VocabularyServiceProtocol(Protocol):
    """Protocol for vocabulary services (file-based or database-backed)."""

    @property
    def concepts(self) -> list: ...

    def load(self) -> None: ...


class RuleBasedNLPService(BaseNLPService):
    """Rule-based mention extractor using regex and vocabulary matching.

    This service extracts clinical mentions by:
    1. Searching for known clinical terms from the vocabulary
    2. Using regex patterns to identify common clinical patterns
    3. Applying context rules for negation, temporality, and experiencer

    By default, uses database-backed vocabulary if USE_DB_VOCABULARY=true
    environment variable is set, otherwise falls back to file-based fixture.

    Usage:
        nlp = RuleBasedNLPService()
        mentions = nlp.extract_mentions(document.text, document.id)

        # Or with explicit vocabulary service:
        vocab = VocabularyService()
        nlp = RuleBasedNLPService(vocab)
    """

    # Stopwords - common English words that should NOT be extracted as clinical terms
    # These may exist as concepts in OMOP but create noise when extracted from text
    STOPWORDS = {
        # Common English words
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "or", "and", "but", "if", "then", "so", "as", "at", "by", "for",
        "from", "in", "into", "of", "on", "to", "with", "without",
        "yes", "no", "not", "can", "will", "may", "has", "had", "have",
        "all", "any", "some", "one", "two", "per", "mg", "ml",
        # Common medical/clinical words that are too generic
        "air",      # RxNorm Ingredient - creates false positives from "room air"
        "water",    # Too common
        "normal",   # Too generic - "within normal limits"
        "stable",   # Too generic - "vitals stable"
        "pain",     # Too generic without context
        "use",      # From "use of"
        "day",      # Too common
        "time",     # Too common
        "room",     # Too common
        "well",     # Too common - "patient doing well"
        "new",      # Too common
        "old",      # Too common
        "left",     # Too ambiguous without body site context
        "right",    # Too ambiguous without body site context
        "patient",  # Too common
    }

    # Minimum term length to extract (helps reduce noise)
    MIN_TERM_LENGTH = 2

    # Confidence scoring parameters
    # These weights sum to 1.0 and determine how much each factor contributes
    CONFIDENCE_WEIGHTS = {
        "base": 0.4,           # Base match confidence
        "term_length": 0.2,    # Longer terms = higher confidence
        "section_fit": 0.2,    # Section-domain affinity
        "specificity": 0.1,    # Concept specificity (has OMOP ID)
        "case_match": 0.1,     # Exact case match bonus
    }

    # Common patterns for clinical terms not in vocabulary
    CLINICAL_PATTERNS = [
        # Vital signs with values
        r"(?:temperature|temp)\s*(?:of\s*)?([\d.]+)\s*(?:°?[FC])?",
        r"(?:blood pressure|bp)\s*(?:of\s*)?(\d+/\d+)\s*(?:mmHg)?",
        r"(?:heart rate|hr|pulse)\s*(?:of\s*)?(\d+)\s*(?:bpm)?",
        r"(?:respiratory rate|rr)\s*(?:of\s*)?(\d+)\s*(?:/min)?",
        r"(?:oxygen saturation|o2 sat|spo2)\s*(?:of\s*)?(\d+)\s*%?",
        # Lab values
        r"(?:hemoglobin|hgb)\s*(?:of\s*)?([\d.]+)\s*(?:g/dL)?",
        r"(?:white blood cell|wbc)\s*(?:count\s*)?(?:of\s*)?([\d.]+)\s*(?:k/uL)?",
        r"(?:creatinine|cr)\s*(?:of\s*)?([\d.]+)\s*(?:mg/dL)?",
        r"(?:bnp)\s*(?:of\s*)?([\d.]+)\s*(?:pg/mL)?",
    ]

    # Positive assertion triggers (words that indicate presence - check FIRST)
    # These override negation when found closer to the mention
    POSITIVE_TRIGGERS = [
        r"\btaking\b",
        r"\btakes\b",
        r"\bon\b",  # "on metformin"
        r"\breceiving\b",
        r"\breceives\b",
        r"\bprescribed\b",
        r"\bstarted\s+(?:on\s+)?",
        r"\bcontinue\b",
        r"\bcontinued\b",
        r"\bcontinuing\b",
        r"\busing\b",
        r"\bhas\b",  # "has diabetes"
        r"\bwith\b",  # "patient with hypertension"
        r"\bdiagnosed\s+with\b",
        r"\bpresents?\s+with\b",
        r"\bcomplaining\s+of\b",
        r"\breports?\b",
    ]

    # Negation triggers (words that indicate absence)
    # Note: Order matters - check "cannot rule out" for uncertainty first
    # Canonical source: app.services.nlp_shared.CANONICAL_NEGATION_TRIGGERS
    NEGATION_TRIGGERS = [
        r"\bno\b",
        r"\bnot\b",
        r"\bdenies\b",
        r"\bdenied\b",
        r"\bwithout\b",
        r"\babsence\s+of\b",
        r"\bnegative\s+for\b",
        r"\bruled\s+out\b",  # Past tense - confirmed absence
        r"\brunlikely\b",
        r"\bno\s+evidence\s+of\b",
    ]

    # Uncertainty triggers (words that indicate possibility)
    # These should be checked BEFORE negation for proper precedence
    UNCERTAINTY_TRIGGERS = [
        r"\bcannot\s+rule\s+out\b",  # Uncertain, NOT negated
        r"\bcan\'?t\s+rule\s+out\b",  # Uncertain, NOT negated
        r"\bpossible\b",
        r"\bprobable\b",
        r"\bsuspected?\b",
        r"\bquestionable\b",
        r"\bmay\s+have\b",
        r"\bmight\s+have\b",
        r"\bcould\s+be\b",
        r"\bappears?\s+to\s+be\b",
        r"\blikely\b",
        r"\bconcern\s+for\b",
        r"\brule\s+out\b",  # Not yet ruled out = uncertain
    ]

    # Past temporality triggers
    PAST_TRIGGERS = [
        r"\bhistory\s+of\b",
        r"\bpast\s+history\s+of\b",
        r"\bprior\b",
        r"\bprevious\b",
        r"\bformer\b",
        r"\bhad\b",
        r"\bwas\s+diagnosed\s+with\b",
        r"\bremote\b",
    ]

    # Family history triggers
    FAMILY_TRIGGERS = [
        r"\bfamily\s+history\b",  # Matches "family history" in any context
        r"\bfamily\s+hx\b",
        r"\bfhx\b",
        r"\bmother\s+(?:has|had|with|diagnosed)\b",
        r"\bfather\s+(?:has|had|with|diagnosed)\b",
        r"\bsibling\s+(?:has|had|with|diagnosed)\b",
        r"\bbrother\s+(?:has|had|with|diagnosed)\b",
        r"\bsister\s+(?:has|had|with|diagnosed)\b",
        r"\bparent\s+(?:has|had|with|diagnosed)\b",
    ]

    def __init__(self, vocabulary_service: VocabularyServiceProtocol | None = None) -> None:
        """Initialize the rule-based NLP service.

        Args:
            vocabulary_service: Optional vocabulary service for term lookup.
                               If not provided, uses the singleton file-based
                               vocabulary (or filtered database if USE_DB_VOCABULARY=true).
        """
        super().__init__()

        if vocabulary_service is not None:
            self._vocabulary_service = vocabulary_service
        elif os.environ.get("USE_DB_VOCABULARY", "").lower() == "true":
            # Use FILTERED database vocabulary for memory-efficient NLP extraction
            # This loads only high-value clinical terms (~100K) instead of all 5.36M
            from app.services.nlp_vocabulary import FilteredNLPVocabularyService
            logger.info("Using filtered database vocabulary service for NLP extraction")
            self._vocabulary_service = FilteredNLPVocabularyService()
        else:
            # Use singleton vocabulary service (pre-loaded at app startup)
            self._vocabulary_service = get_vocabulary_service()

        # Aho-Corasick automaton for O(n) pattern matching
        self._automaton: "Automaton | None" = None
        self._initialized = False

        # Section parser for section-aware extraction
        self._section_parser: SectionParser = get_section_parser()

    def _initialize_patterns(self) -> None:
        """Build Aho-Corasick automaton from vocabulary terms.

        Uses Aho-Corasick algorithm for O(n) pattern matching regardless
        of the number of patterns. This is significantly faster than
        regex-based matching for large vocabularies.
        """
        if self._initialized:
            return

        self._vocabulary_service.load()

        # Build Aho-Corasick automaton (if available)
        if not HAS_AHOCORASICK:
            logger.warning("ahocorasick not installed, rule-based extraction will be limited")
            self._initialized = True
            return

        self._automaton = ahocorasick.Automaton()

        # Track which patterns we've added (avoid duplicates)
        added_patterns: set[str] = set()

        # Build automaton from vocabulary synonyms with domain/concept hints
        for concept in self._vocabulary_service.concepts:
            for synonym in concept.synonyms:
                # Normalize to lowercase for case-insensitive matching
                key = synonym.lower()

                # Skip duplicates (keep first occurrence)
                if key in added_patterns:
                    continue

                added_patterns.add(key)

                # Store metadata: (original_synonym, domain_id, concept_id)
                self._automaton.add_word(key, (synonym, concept.domain_id, concept.concept_id))

        # Finalize the automaton (required before searching)
        self._automaton.make_automaton()

        self._initialized = True
        logger.info(f"Aho-Corasick automaton built with {len(added_patterns)} patterns")

    def extract_mentions(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
        document_date: datetime | None = None,
    ) -> list[ExtractedMention]:
        """Extract clinical mentions from document text.

        Uses Aho-Corasick for O(n) pattern matching to find clinical
        terms, then applies context rules for assertion, temporality,
        and experiencer. Section-aware extraction adjusts confidence
        based on section-domain fit.

        Args:
            text: The clinical note text to process.
            document_id: UUID of the source document.
            note_type: Optional type of clinical note.

        Returns:
            List of ExtractedMention objects with text spans and attributes.
        """
        self._initialize_patterns()

        if self._automaton is None:
            return []

        mentions: list[ExtractedMention] = []
        seen_spans: set[tuple[int, int]] = set()

        # Parse sections once for efficient O(1) lookups
        section_spans = self._section_parser.parse(text)

        # Build section lookup map for O(1) access
        # Key is character offset, value is section
        def get_section_at_offset(offset: int) -> ClinicalSection:
            """Get section for offset using pre-parsed sections."""
            for span in reversed(section_spans):
                if span.start <= offset:
                    return span.section
            return ClinicalSection.UNKNOWN

        # Search text with Aho-Corasick automaton (O(n) complexity)
        text_lower = text.lower()

        for end_index, (lexical_variant, domain_id, concept_id) in self._automaton.iter(text_lower):
            # Calculate start position (end_index is inclusive)
            pattern_len = len(lexical_variant)
            start = end_index - pattern_len + 1
            end = end_index + 1

            # Get the original text (preserve case)
            matched_text = text[start:end]

            # Verify word boundaries (automaton matches substrings)
            if not self._is_word_boundary(text, start, end):
                continue

            # Skip if we've already found a mention at this span
            if (start, end) in seen_spans:
                continue

            # Skip stopwords (common English words that create noise)
            if matched_text.lower() in self.STOPWORDS:
                continue

            # Skip terms below minimum length
            if len(matched_text) < self.MIN_TERM_LENGTH:
                continue

            seen_spans.add((start, end))

            # Get context for attribute detection
            # Use surrounding context for temporality and experiencer
            surrounding_context = self._get_context_window(text, start, end)

            # Use probabilistic assertion classifier for calibrated confidence
            assertion_result = classify_assertion(text, start, end)
            assertion = assertion_result.assertion
            assertion_confidence = assertion_result.confidence
            assertion_trigger = assertion_result.trigger_text

            temporality = self._detect_temporality(surrounding_context)
            experiencer = self._detect_experiencer(surrounding_context)

            # Get section using pre-parsed sections (O(1) lookup)
            clinical_section = get_section_at_offset(start)
            section_name = clinical_section.value if clinical_section != ClinicalSection.UNKNOWN else None

            # Calculate comprehensive confidence score
            confidence = self._calculate_confidence(
                matched_text=matched_text,
                lexical_variant=lexical_variant,
                concept_id=concept_id,
                domain_id=domain_id,
                clinical_section=clinical_section,
                assertion=assertion,
            )

            mention = ExtractedMention(
                text=matched_text,
                start_offset=start,
                end_offset=end,
                lexical_variant=lexical_variant,
                section=section_name,
                assertion=assertion,
                temporality=temporality,
                experiencer=experiencer,
                confidence=confidence,
                domain_hint=domain_id,  # Pass domain from vocabulary
                omop_concept_id=concept_id,  # Direct concept_id if available
                assertion_confidence=assertion_confidence,  # Calibrated assertion confidence
                assertion_trigger=assertion_trigger,  # Trigger that determined assertion
            )
            mentions.append(mention)

        # Sort mentions by position
        mentions.sort(key=lambda m: m.start_offset)

        # Enrich mentions with temporal data from TemporalExtractor
        if mentions:
            try:
                extractor = TemporalExtractor(reference_date=document_date)
                entities = [
                    {"text": m.text, "start": m.start_offset, "end": m.end_offset}
                    for m in mentions
                ]
                bindings = extractor.bind_entities_to_temporals(text, entities)

                # Build lookup: (start, end) -> binding for O(1) access
                binding_map = {
                    (b.entity_start, b.entity_end): b for b in bindings
                }

                for mention in mentions:
                    binding = binding_map.get((mention.start_offset, mention.end_offset))
                    if binding and binding.temporal_expression.date:
                        mention.event_date = binding.temporal_expression.date
                        mention.date_precision = binding.temporal_expression.date_precision
                        mention.temporal_relationship = binding.relationship
                        # Upgrade temporality to HISTORICAL if temporal evidence
                        # indicates a past event (e.g., "diagnosed in 2019")
                        if binding.relationship in ("diagnosed", "onset", "started", "stopped"):
                            if mention.temporality == Temporality.CURRENT:
                                mention.temporality = Temporality.PAST
            except Exception:
                logger.warning("Temporal enrichment failed, continuing without temporal data", exc_info=True)

        return mentions

    def _is_word_boundary(self, text: str, start: int, end: int) -> bool:
        """Check if match is at word boundaries.

        The Aho-Corasick automaton matches substrings, so we need to
        verify that matches occur at word boundaries (like \\b in regex).

        Args:
            text: Full document text.
            start: Start offset of match.
            end: End offset of match.

        Returns:
            True if match is at word boundaries.
        """
        # Check start boundary
        if start > 0:
            prev_char = text[start - 1]
            if prev_char.isalnum() or prev_char == '_':
                return False

        # Check end boundary
        if end < len(text):
            next_char = text[end]
            if next_char.isalnum() or next_char == '_':
                return False

        return True

    def _get_context_window(
        self,
        text: str,
        start: int,
        end: int,
        window_size: int = 50,
    ) -> str:
        """Get text context around a mention for attribute detection.

        Args:
            text: Full document text.
            start: Start offset of mention.
            end: End offset of mention.
            window_size: Characters to include before/after mention.

        Returns:
            Context string including the mention.
        """
        context_start = max(0, start - window_size)
        context_end = min(len(text), end + window_size)
        return text[context_start:context_end].lower()

    def _get_preceding_context(
        self,
        text: str,
        start: int,
        window_size: int = 50,
    ) -> str:
        """Get text BEFORE a mention for negation detection.

        NegEx-style negation typically only looks at preceding text,
        not following text.

        Args:
            text: Full document text.
            start: Start offset of mention.
            window_size: Characters to include before mention.

        Returns:
            Preceding context string (lowercase).
        """
        context_start = max(0, start - window_size)
        return text[context_start:start].lower()

    def _detect_assertion(self, context: str) -> Assertion:
        """Detect assertion status from context.

        Uses position-based detection: the trigger CLOSEST to the mention wins.
        This prevents negation from previous sentences affecting mentions in
        later sentences (e.g., "No chest pain. Taking metformin").

        Priority order for ties: uncertainty > positive > negation

        Args:
            context: Text context before the mention.

        Returns:
            Assertion enum value (PRESENT, ABSENT, or POSSIBLE).
        """
        # Find positions of all triggers (we want the one closest to the mention)
        # The mention is at the END of context, so higher position = closer

        def find_closest_match(patterns: list[str]) -> int:
            """Find the position of the closest match to end of context."""
            best_pos = -1
            for pattern in patterns:
                for match in re.finditer(pattern, context, re.IGNORECASE):
                    if match.end() > best_pos:
                        best_pos = match.end()
            return best_pos

        uncertainty_pos = find_closest_match(self.UNCERTAINTY_TRIGGERS)
        positive_pos = find_closest_match(self.POSITIVE_TRIGGERS)
        negation_pos = find_closest_match(self.NEGATION_TRIGGERS)

        # If no triggers found, default to PRESENT
        if uncertainty_pos == -1 and positive_pos == -1 and negation_pos == -1:
            return Assertion.PRESENT

        # The closest trigger to the mention wins
        # Use the END position of match (higher = closer to mention)
        max_pos = max(uncertainty_pos, positive_pos, negation_pos)

        if uncertainty_pos == max_pos:
            return Assertion.POSSIBLE
        elif positive_pos == max_pos:
            return Assertion.PRESENT
        elif negation_pos == max_pos:
            return Assertion.ABSENT

        return Assertion.PRESENT

    def _detect_temporality(self, context: str) -> Temporality:
        """Detect temporality from context.

        Checks for past/historical indicators in the context.

        Args:
            context: Text context around the mention.

        Returns:
            Temporality enum value (CURRENT, PAST, or FUTURE).
        """
        for pattern in self.PAST_TRIGGERS:
            if re.search(pattern, context, re.IGNORECASE):
                return Temporality.PAST

        return Temporality.CURRENT

    def _detect_experiencer(self, context: str) -> Experiencer:
        """Detect experiencer from context.

        Checks for family history indicators in the context.

        Args:
            context: Text context around the mention.

        Returns:
            Experiencer enum value (PATIENT, FAMILY, or OTHER).
        """
        for pattern in self.FAMILY_TRIGGERS:
            if re.search(pattern, context, re.IGNORECASE):
                return Experiencer.FAMILY

        return Experiencer.PATIENT

    def _calculate_confidence(
        self,
        matched_text: str,
        lexical_variant: str,
        concept_id: int | None,
        domain_id: str | None,
        clinical_section: ClinicalSection,
        assertion: Assertion,
    ) -> float:
        """Calculate comprehensive confidence score for an extraction.

        Combines multiple signals into a final confidence score:
        - Base match quality (vocabulary match)
        - Term length (longer terms are more specific)
        - Section-domain fit (term type matches section expectations)
        - Specificity (has OMOP concept ID = known entity)
        - Case match (exact case = higher quality match)

        Args:
            matched_text: The actual text matched in the document.
            lexical_variant: The vocabulary term that matched.
            concept_id: OMOP concept ID if available.
            domain_id: OMOP domain (Condition, Drug, etc.).
            clinical_section: The clinical section where match was found.
            assertion: The assertion status (affects final score).

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        weights = self.CONFIDENCE_WEIGHTS
        score = 0.0

        # 1. Base confidence (vocabulary match = high quality)
        score += weights["base"] * 1.0

        # 2. Term length scoring (longer = more specific)
        # Scale: 2 chars = 0.3, 5 chars = 0.6, 10+ chars = 1.0
        term_len = len(matched_text)
        if term_len >= 10:
            length_score = 1.0
        elif term_len >= 5:
            length_score = 0.6 + (term_len - 5) * 0.08  # 0.6 to 1.0
        else:
            length_score = 0.3 + (term_len - 2) * 0.1  # 0.3 to 0.6
        score += weights["term_length"] * length_score

        # 3. Section-domain fit
        section_modifier = self._section_parser.calculate_confidence_modifier(
            clinical_section, domain_id or "Observation"
        )
        # Normalize modifier from 0.8-1.1 range to 0.0-1.0
        section_score = (section_modifier - 0.8) / 0.3
        section_score = max(0.0, min(1.0, section_score))
        score += weights["section_fit"] * section_score

        # 4. Specificity (has concept_id = known OMOP entity)
        specificity_score = 1.0 if concept_id is not None else 0.5
        score += weights["specificity"] * specificity_score

        # 5. Case match bonus (exact match = higher quality)
        if matched_text == lexical_variant:
            case_score = 1.0
        elif matched_text.lower() == lexical_variant.lower():
            case_score = 0.8  # Case-insensitive match
        else:
            case_score = 0.5  # Partial/fuzzy match
        score += weights["case_match"] * case_score

        # Apply assertion penalty for uncertain extractions
        # POSSIBLE assertions get slight reduction (uncertainty = less confident)
        if assertion == Assertion.POSSIBLE:
            score *= 0.9

        # Clamp to valid range
        return max(0.0, min(1.0, score))
