"""Clinical NER service using spaCy and HuggingFace transformer models.

Provides ML-based named entity recognition for clinical text using:
- SpaCy for general NER and text processing
- HuggingFace transformers for biomedical/clinical NER (Bio_ClinicalBERT variants)

This service complements the rule-based NLP service and can be combined
in an ensemble for better coverage and accuracy.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.services.nlp import BaseNLPService, ExtractedMention

logger = logging.getLogger(__name__)

# Entity type to OMOP domain mapping
# HuggingFace clinical NER models often use BIO tagging with these types:
# - PROBLEM: Medical problems, diseases, symptoms
# - TREATMENT: Medications, procedures, therapies
# - TEST: Laboratory tests, diagnostic procedures
# - ANATOMY: Body parts, organs
ENTITY_TO_DOMAIN: dict[str, str] = {
    # Clinical NER model types
    "PROBLEM": Domain.CONDITION.value,
    "DISEASE": Domain.CONDITION.value,
    "SYMPTOM": Domain.OBSERVATION.value,
    "TREATMENT": Domain.DRUG.value,
    "MEDICATION": Domain.DRUG.value,
    "DRUG": Domain.DRUG.value,
    "CHEMICAL": Domain.DRUG.value,
    "TEST": Domain.MEASUREMENT.value,
    "LAB": Domain.MEASUREMENT.value,
    "ANATOMY": Domain.SPEC_ANATOMIC_SITE.value,
    "BODY_PART": Domain.SPEC_ANATOMIC_SITE.value,
    "PROCEDURE": Domain.PROCEDURE.value,

    # SpaCy general NER types (fallback)
    "PERSON": None,  # Skip person names
    "ORG": None,  # Skip organization names
    "GPE": None,  # Skip geopolitical entities
    "DATE": None,  # Skip dates (handled separately)
    "TIME": None,  # Skip times
    "MONEY": None,  # Skip money
    "PERCENT": None,  # Skip percentages
    "CARDINAL": None,  # Skip numbers
    "ORDINAL": None,  # Skip ordinals
    "QUANTITY": Domain.MEASUREMENT.value,  # Quantities might be measurements
    "PRODUCT": Domain.DEVICE.value,  # Products might be medical devices
}

# Confidence levels for different sources
CONFIDENCE_BY_SOURCE = {
    "transformer_ner": 0.85,  # High confidence for transformer models
    "spacy_general": 0.60,    # Lower confidence for general spaCy
    "pattern_match": 0.70,    # Medium confidence for patterns
}


@dataclass
class TransformerNERConfig:
    """Configuration for transformer-based NER."""

    # HuggingFace model for clinical NER
    # Options:
    # - "samrawal/bert-base-uncased_clinical-ner" (clinical entities)
    # - "alvaroalon2/biobert_diseases_ner" (diseases)
    # - "dmis-lab/biobert-base-cased-v1.1" (biomedical base)
    model_name: str = "samrawal/bert-base-uncased_clinical-ner"

    # SpaCy model for general processing
    spacy_model: str = "en_core_web_sm"

    # Use GPU if available
    use_gpu: bool = True

    # Minimum entity length
    min_entity_length: int = 2

    # Minimum confidence threshold
    min_confidence: float = 0.5

    # Context window for assertion detection (characters)
    context_window: int = 50

    # Enable assertion detection
    detect_assertion: bool = True

    # Enable temporality detection
    detect_temporality: bool = True

    # Maximum sequence length for transformers
    max_sequence_length: int = 512

    # Batch size for transformer inference
    batch_size: int = 8

    # Fallback transformer checkpoints to try if the primary model fails to load
    fallback_models: tuple[str, ...] = (
        "alvaroalon2/biobert_diseases_ner",
        "dmis-lab/biobert-base-cased-v1.1",
    )


@dataclass
class ClinicalNERService(BaseNLPService):
    """ML-based clinical NER service using transformers and spaCy.

    This service uses pre-trained biomedical NER models to extract
    clinical entities from text. It provides two extraction methods:

    1. Transformer-based: Uses HuggingFace clinical NER models for
       high-quality entity extraction (requires transformers, torch).

    2. SpaCy-based: Falls back to general spaCy NER when transformers
       aren't available or for additional entity types.

    Usage:
        # Basic usage
        ner = ClinicalNERService()
        mentions = ner.extract_mentions(text, doc_id)

        # With custom config
        config = TransformerNERConfig(min_confidence=0.7)
        ner = ClinicalNERService(config=config)

    Note: For best results, install the clinical NER model:
        pip install transformers torch
    """

    config: TransformerNERConfig = field(default_factory=TransformerNERConfig)
    _nlp: Any = field(default=None, init=False, repr=False)
    _transformer_pipeline: Any = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False)
    _spacy_available: bool = field(default=True, init=False)
    _transformer_available: bool = field(default=True, init=False)

    # Context patterns for assertion/temporality detection
    NEGATION_PATTERNS = [
        r"\bno\b", r"\bnot\b", r"\bnone\b", r"\bnever\b",
        r"\bdenies?\b", r"\bdenied\b", r"\bwithout\b",
        r"\babsent\b", r"\bnegative\b", r"\bruled\s+out\b",
        r"\bno\s+evidence\b", r"\bno\s+sign\b", r"\bfree\s+of\b",
    ]

    UNCERTAINTY_PATTERNS = [
        r"\bpossible\b", r"\bprobable\b", r"\bsuspect\b",
        r"\bquestionable\b", r"\bmay\b", r"\bmight\b",
        r"\bcould\b", r"\blikely\b", r"\brule\s+out\b",
        r"\bconcern\s+for\b", r"\bworrisome\b", r"\bsuggests?\b",
    ]

    PAST_PATTERNS = [
        r"\bhistory\s+of\b", r"\bprior\b", r"\bprevious\b",
        r"\bformer\b", r"\bpast\b", r"\bhad\b", r"\bwas\b",
        r"\bdiagnosed\s+with\b", r"\btreated\s+for\b",
        r"\bresolved\b", r"\bremission\b",
    ]

    FAMILY_PATTERNS = [
        r"\bfamily\s+history\b", r"\bfamilial\b",
        r"\bmother\b", r"\bfather\b", r"\bsibling\b",
        r"\bbrother\b", r"\bsister\b", r"\bgrandparent\b",
        r"\bfh\s*[:]\b", r"\brelative\b",
    ]

    def _initialize(self) -> None:
        """Lazy initialization of NLP models."""
        if self._initialized:
            return

        # Initialize spaCy
        self._init_spacy()

        # Initialize transformer pipeline
        self._init_transformer()

        self._initialized = True

    def _init_spacy(self) -> None:
        """Initialize spaCy model."""
        try:
            import spacy

            try:
                self._nlp = spacy.load(self.config.spacy_model)
                logger.info(f"Loaded spaCy model: {self.config.spacy_model}")
                self._spacy_available = True
            except OSError:
                # Try downloading the model
                try:
                    from spacy.cli import download
                    download(self.config.spacy_model)
                    self._nlp = spacy.load(self.config.spacy_model)
                    self._spacy_available = True
                except Exception as e:
                    logger.warning(f"Could not load spaCy model: {e}")
                    self._spacy_available = False

        except ImportError:
            logger.warning("spaCy not installed")
            self._spacy_available = False

    def _init_transformer(self) -> None:
        """Initialize HuggingFace transformer pipeline."""
        try:
            from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline
            import torch

            device = 0 if (self.config.use_gpu and torch.cuda.is_available()) else -1
            if device == -1 and self.config.use_gpu and torch.backends.mps.is_available():
                device = "mps"

            # Try to load the clinical NER model
            try:
                self._transformer_pipeline = pipeline(
                    "ner",
                    model=self.config.model_name,
                    tokenizer=self.config.model_name,
                    aggregation_strategy="simple",
                    device=device if isinstance(device, int) else None,
                )
                logger.info(f"Loaded transformer NER model: {self.config.model_name}")
                self._transformer_available = True
            except Exception as e:
                logger.warning(f"Could not load transformer model {self.config.model_name}: {e}")
                # Try fallback to biomedical NER models
                for fallback in self.config.fallback_models:
                    try:
                        self._transformer_pipeline = pipeline(
                            "ner",
                            model=fallback,
                            aggregation_strategy="simple",
                            device=device if isinstance(device, int) else None,
                        )
                        logger.info(f"Loaded fallback model: {fallback}")
                        self._transformer_available = True
                        break
                    except Exception:
                        continue

                if not self._transformer_available:
                    logger.warning("No transformer NER models available, using spaCy only")

        except ImportError:
            logger.warning("transformers not installed, using spaCy only")
            self._transformer_available = False

    def is_available(self) -> bool:
        """Check if any NER capability is available."""
        self._initialize()
        return self._spacy_available or self._transformer_available

    def _get_context(self, text: str, start: int, end: int) -> tuple[str, str]:
        """Get context before and after an entity span."""
        window = self.config.context_window
        context_before = text[max(0, start - window):start].lower()
        context_after = text[end:min(len(text), end + window)].lower()
        return context_before, context_after

    def _detect_assertion(self, text: str, start: int, end: int) -> Assertion:
        """Detect assertion status from surrounding context."""
        if not self.config.detect_assertion:
            return Assertion.PRESENT

        context_before, context_after = self._get_context(text, start, end)

        # Check uncertainty first (takes precedence)
        for pattern in self.UNCERTAINTY_PATTERNS:
            if re.search(pattern, context_before) or re.search(pattern, context_after):
                return Assertion.POSSIBLE

        # Check negation
        for pattern in self.NEGATION_PATTERNS:
            if re.search(pattern, context_before):
                return Assertion.ABSENT

        return Assertion.PRESENT

    def _detect_temporality(self, text: str, start: int, end: int) -> Temporality:
        """Detect temporality from surrounding context."""
        if not self.config.detect_temporality:
            return Temporality.CURRENT

        context_before, _ = self._get_context(text, start, end)

        for pattern in self.PAST_PATTERNS:
            if re.search(pattern, context_before):
                return Temporality.PAST

        return Temporality.CURRENT

    def _detect_experiencer(self, text: str, start: int, end: int) -> Experiencer:
        """Detect experiencer from surrounding context."""
        context_before, _ = self._get_context(text, start, end)

        for pattern in self.FAMILY_PATTERNS:
            if re.search(pattern, context_before):
                return Experiencer.FAMILY

        return Experiencer.PATIENT

    def _extract_with_transformer(self, text: str) -> list[dict]:
        """Extract entities using transformer pipeline."""
        if not self._transformer_available or self._transformer_pipeline is None:
            return []

        try:
            # Handle long texts by chunking
            if len(text) > self.config.max_sequence_length * 4:
                chunks = self._chunk_text(text)
                all_entities = []
                offset = 0
                for chunk in chunks:
                    entities = self._transformer_pipeline(chunk)
                    # Adjust offsets for chunk position
                    for ent in entities:
                        ent["start"] += offset
                        ent["end"] += offset
                    all_entities.extend(entities)
                    offset += len(chunk)
                return all_entities
            else:
                return self._transformer_pipeline(text)
        except Exception as e:
            logger.warning(f"Transformer extraction failed: {e}")
            return []

    def _chunk_text(self, text: str, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks for processing."""
        chunk_size = self.config.max_sequence_length * 4
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            # Try to break at sentence boundary
            if end < len(text):
                for punct in [". ", ".\n", "! ", "? "]:
                    last_punct = text[start:end].rfind(punct)
                    if last_punct > chunk_size // 2:
                        end = start + last_punct + len(punct)
                        break
            chunks.append(text[start:end])
            start = end - overlap
        return chunks

    def _extract_with_spacy(self, text: str) -> list[dict]:
        """Extract entities using spaCy."""
        if not self._spacy_available or self._nlp is None:
            return []

        try:
            doc = self._nlp(text)
            entities = []
            for ent in doc.ents:
                entities.append({
                    "word": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "entity_group": ent.label_,
                    "score": 0.6,  # Default confidence for spaCy
                    "source": "spacy",
                })
            return entities
        except Exception as e:
            logger.warning(f"SpaCy extraction failed: {e}")
            return []

    def _merge_entities(
        self,
        transformer_ents: list[dict],
        spacy_ents: list[dict],
    ) -> list[dict]:
        """Merge entities from multiple sources, preferring transformer results."""
        # Create a span index for transformer entities
        transformer_spans = set()
        for ent in transformer_ents:
            start = ent.get("start", 0)
            end = ent.get("end", 0)
            for i in range(start, end):
                transformer_spans.add(i)

        # Add transformer entities
        merged = list(transformer_ents)

        # Add spaCy entities that don't overlap
        for ent in spacy_ents:
            start = ent.get("start", 0)
            end = ent.get("end", 0)

            # Check for overlap
            overlaps = False
            for i in range(start, end):
                if i in transformer_spans:
                    overlaps = True
                    break

            if not overlaps:
                merged.append(ent)

        return merged

    def extract_mentions(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
    ) -> list[ExtractedMention]:
        """Extract clinical mentions using ML-based NER.

        Args:
            text: Clinical note text to process.
            document_id: UUID of the source document.
            note_type: Optional note type for context.

        Returns:
            List of ExtractedMention objects with entity types and context.
        """
        self._initialize()

        if not self.is_available():
            logger.warning("No NER models available")
            return []

        mentions: list[ExtractedMention] = []

        # Extract with transformer (primary)
        transformer_ents = self._extract_with_transformer(text)
        for ent in transformer_ents:
            ent["source"] = "transformer"

        # Extract with spaCy (supplement)
        spacy_ents = self._extract_with_spacy(text)

        # Merge entities
        all_entities = self._merge_entities(transformer_ents, spacy_ents)

        # Convert to ExtractedMention objects
        for ent in all_entities:
            try:
                # Get entity text and span
                entity_text = ent.get("word", "")
                start = ent.get("start", 0)
                end = ent.get("end", 0)

                # Skip short entities
                if len(entity_text.strip()) < self.config.min_entity_length:
                    continue

                # Get entity type and map to domain
                entity_type = ent.get("entity_group", "UNKNOWN")
                # Handle BIO tags (B-DISEASE, I-TREATMENT, etc.)
                if entity_type.startswith(("B-", "I-")):
                    entity_type = entity_type[2:]

                domain = ENTITY_TO_DOMAIN.get(entity_type.upper())

                # Skip entity types we don't care about
                if domain is None:
                    continue

                # Get confidence
                confidence = ent.get("score", 0.7)
                if ent.get("source") == "spacy":
                    confidence = CONFIDENCE_BY_SOURCE["spacy_general"]
                elif confidence < 0.1:
                    confidence = CONFIDENCE_BY_SOURCE["transformer_ner"]

                # Skip low confidence
                if confidence < self.config.min_confidence:
                    continue

                # Detect assertion, temporality, experiencer
                assertion = self._detect_assertion(text, start, end)
                temporality = self._detect_temporality(text, start, end)
                experiencer = self._detect_experiencer(text, start, end)

                # Get section
                section = self.get_section_name(text, start)

                mention = ExtractedMention(
                    text=entity_text,
                    start_offset=start,
                    end_offset=end,
                    lexical_variant=entity_text.lower().strip(),
                    section=section,
                    assertion=assertion,
                    temporality=temporality,
                    experiencer=experiencer,
                    confidence=confidence,
                    domain_hint=domain,
                )

                mentions.append(mention)

            except Exception as e:
                logger.debug(f"Error processing entity {ent}: {e}")
                continue

        logger.debug(f"Extracted {len(mentions)} mentions from document {document_id}")

        return mentions


# Singleton instance
_clinical_ner_service: ClinicalNERService | None = None


def get_clinical_ner_service(
    config: TransformerNERConfig | None = None,
) -> ClinicalNERService:
    """Get the singleton clinical NER service.

    Args:
        config: Optional configuration. Only used on first call.

    Returns:
        ClinicalNERService instance.
    """
    global _clinical_ner_service
    if _clinical_ner_service is None:
        _clinical_ner_service = ClinicalNERService(
            config=config or TransformerNERConfig()
        )
    return _clinical_ner_service


def reset_clinical_ner_service() -> None:
    """Reset the singleton service (mainly for testing)."""
    global _clinical_ner_service
    _clinical_ner_service = None
