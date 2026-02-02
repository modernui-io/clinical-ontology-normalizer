"""ModernBERT-based Clinical NER Service.

Provides clinical NER using ModernBERT architecture with:
- 8192 token context window (no chunking needed)
- Flash Attention 2 for efficient long-context processing
- GPU acceleration with CPU fallback
- Lazy model initialization with caching

ModernBERT advantages over traditional BERT:
- 8x longer context (8192 vs 512 tokens)
- Flash Attention 2 for O(n) memory scaling
- Better throughput on long clinical notes
- Improved accuracy on long-range dependencies

References:
- ModernBERT: https://huggingface.co/answerdotai/ModernBERT-base
- Flash Attention: https://github.com/Dao-AILab/flash-attention
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.services.nlp import BaseNLPService, ExtractedMention

logger = logging.getLogger(__name__)


# Entity type to OMOP domain mapping (same as clinical NER)
ENTITY_TO_DOMAIN: dict[str, str] = {
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
}


@dataclass
class ModernBERTConfig:
    """Configuration for ModernBERT-based clinical NER.

    ModernBERT supports 8192 tokens, eliminating the need for chunking
    on most clinical documents.
    """

    # Primary model - fine-tuned clinical NER on ModernBERT
    # Override with your own fine-tuned model
    model_name: str = "answerdotai/ModernBERT-base"

    # Fallback models if primary unavailable
    fallback_models: tuple[str, ...] = (
        "samrawal/bert-base-uncased_clinical-ner",
        "alvaroalon2/biobert_diseases_ner",
        "dmis-lab/biobert-base-cased-v1.1",
    )

    # ModernBERT's key advantage: 8192 token context
    max_sequence_length: int = 8192

    # Batch size for inference
    batch_size: int = 4

    # Minimum confidence threshold
    min_confidence: float = 0.5

    # Minimum entity length in characters
    min_entity_length: int = 2

    # Use Flash Attention 2 if available (significant speedup)
    use_flash_attention: bool = True

    # GPU settings
    use_gpu: bool = True
    device_map: str = "auto"  # "auto", "cuda", "mps", "cpu"

    # Context window for assertion detection (characters)
    context_window: int = 100

    # Enable assertion/temporality detection
    detect_assertion: bool = True
    detect_temporality: bool = True


@dataclass
class EntityWithContext:
    """Extracted entity with surrounding context for downstream tasks."""

    text: str
    start: int
    end: int
    entity_type: str
    confidence: float
    context_before: str
    context_after: str
    full_sentence: str | None = None


@dataclass
class ModernBERTNERService(BaseNLPService):
    """Clinical NER service using ModernBERT with 8K context.

    Key features:
    - 8192 token context window (no chunking for most documents)
    - Flash Attention 2 for efficient processing
    - GPU support with automatic fallback
    - Lazy initialization for fast startup

    Usage:
        service = ModernBERTNERService()

        # Extract mentions (standard interface)
        mentions = service.extract_mentions(text, doc_id)

        # Extract entities with context (for downstream tasks)
        entities = service.extract_with_context(text)

        # Direct entity extraction
        entities = service.extract_entities(text)
    """

    config: ModernBERTConfig = field(default_factory=ModernBERTConfig)

    # Lazy-loaded model components
    _model: Any = field(default=None, init=False, repr=False)
    _tokenizer: Any = field(default=None, init=False, repr=False)
    _pipeline: Any = field(default=None, init=False, repr=False)
    _device: str = field(default="cpu", init=False)
    _initialized: bool = field(default=False, init=False)
    _model_available: bool = field(default=True, init=False)
    _using_flash_attention: bool = field(default=False, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # Context patterns for assertion detection
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
        """Lazy initialization of ModernBERT model.

        Thread-safe initialization with caching.
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self._init_device()
            self._init_model()
            self._initialized = True

    def _init_device(self) -> None:
        """Initialize compute device (GPU/MPS/CPU)."""
        try:
            import torch

            if self.config.use_gpu:
                if torch.cuda.is_available():
                    self._device = "cuda"
                    logger.info("Using CUDA GPU for ModernBERT")
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    self._device = "mps"
                    logger.info("Using Apple MPS for ModernBERT")
                else:
                    self._device = "cpu"
                    logger.info("No GPU available, using CPU for ModernBERT")
            else:
                self._device = "cpu"
                logger.info("GPU disabled, using CPU for ModernBERT")

        except ImportError:
            self._device = "cpu"
            logger.warning("PyTorch not available, using CPU")

    def _init_model(self) -> None:
        """Initialize ModernBERT model with optional Flash Attention."""
        try:
            from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

            # Try to enable Flash Attention 2
            attn_implementation = None
            if self.config.use_flash_attention:
                try:
                    import flash_attn  # noqa: F401
                    attn_implementation = "flash_attention_2"
                    self._using_flash_attention = True
                    logger.info("Flash Attention 2 enabled for ModernBERT")
                except ImportError:
                    logger.info("Flash Attention not available, using standard attention")

            # Try primary model first
            models_to_try = [self.config.model_name] + list(self.config.fallback_models)

            for model_name in models_to_try:
                try:
                    # Load tokenizer
                    self._tokenizer = AutoTokenizer.from_pretrained(
                        model_name,
                        model_max_length=self.config.max_sequence_length,
                    )

                    # Build model kwargs
                    model_kwargs: dict[str, Any] = {}
                    if attn_implementation:
                        model_kwargs["attn_implementation"] = attn_implementation

                    # Create NER pipeline
                    device_arg = 0 if self._device == "cuda" else -1 if self._device == "cpu" else None

                    self._pipeline = pipeline(
                        "ner",
                        model=model_name,
                        tokenizer=self._tokenizer,
                        aggregation_strategy="simple",
                        device=device_arg,
                        model_kwargs=model_kwargs if model_kwargs else None,
                    )

                    self._model_available = True
                    logger.info(f"Loaded ModernBERT NER model: {model_name}")
                    return

                except Exception as e:
                    logger.warning(f"Could not load model {model_name}: {e}")
                    continue

            # No models loaded
            self._model_available = False
            logger.error("No NER models could be loaded")

        except ImportError as e:
            self._model_available = False
            logger.warning(f"transformers not available: {e}")

    def is_available(self) -> bool:
        """Check if the service is available."""
        self._initialize()
        return self._model_available

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        self._initialize()
        return {
            "model_available": self._model_available,
            "device": self._device,
            "flash_attention": self._using_flash_attention,
            "max_sequence_length": self.config.max_sequence_length,
            "model_name": self.config.model_name,
        }

    def _get_context(self, text: str, start: int, end: int) -> tuple[str, str]:
        """Get context before and after an entity span."""
        window = self.config.context_window
        context_before = text[max(0, start - window):start].lower()
        context_after = text[end:min(len(text), end + window)].lower()
        return context_before, context_after

    def _detect_assertion(self, text: str, start: int, end: int) -> Assertion:
        """Detect assertion status from context."""
        if not self.config.detect_assertion:
            return Assertion.PRESENT

        context_before, context_after = self._get_context(text, start, end)

        # Check uncertainty first
        for pattern in self.UNCERTAINTY_PATTERNS:
            if re.search(pattern, context_before) or re.search(pattern, context_after):
                return Assertion.POSSIBLE

        # Check negation
        for pattern in self.NEGATION_PATTERNS:
            if re.search(pattern, context_before):
                return Assertion.ABSENT

        return Assertion.PRESENT

    def _detect_temporality(self, text: str, start: int, end: int) -> Temporality:
        """Detect temporality from context."""
        if not self.config.detect_temporality:
            return Temporality.CURRENT

        context_before, _ = self._get_context(text, start, end)

        for pattern in self.PAST_PATTERNS:
            if re.search(pattern, context_before):
                return Temporality.PAST

        return Temporality.CURRENT

    def _detect_experiencer(self, text: str, start: int, end: int) -> Experiencer:
        """Detect experiencer from context."""
        context_before, _ = self._get_context(text, start, end)

        for pattern in self.FAMILY_PATTERNS:
            if re.search(pattern, context_before):
                return Experiencer.FAMILY

        return Experiencer.PATIENT

    def _get_sentence(self, text: str, position: int) -> str | None:
        """Extract the sentence containing a position."""
        # Simple sentence boundary detection
        sentence_ends = [m.end() for m in re.finditer(r'[.!?]\s+', text)]
        sentence_ends.append(len(text))

        start = 0
        for end in sentence_ends:
            if position < end:
                return text[start:end].strip()
            start = end

        return None

    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Extract entities without conversion to ExtractedMention.

        Args:
            text: Clinical text to process.

        Returns:
            List of raw entity dictionaries with keys:
            - word: Entity text
            - start: Start offset
            - end: End offset
            - entity_group: Entity type
            - score: Confidence score
        """
        self._initialize()

        if not self._model_available or self._pipeline is None:
            return []

        try:
            # Safety check: if text is long, always chunk
            # ~3 chars per token on average, so 8192 * 3 = ~24,576 chars
            # Use 20,000 chars as safe threshold
            if len(text) > 20000:
                logger.info(f"Text exceeds safe char limit ({len(text)} chars), using chunking")
                return self._extract_chunked(text)

            # For shorter texts, check token count precisely
            if self._tokenizer is not None:
                tokenized = self._tokenizer(text, return_length=True, truncation=False)
                token_count = tokenized["length"][0] if isinstance(tokenized["length"], list) else tokenized["length"]

                if token_count > self.config.max_sequence_length:
                    logger.info(f"Document exceeds {self.config.max_sequence_length} tokens ({token_count}), using chunking")
                    return self._extract_chunked(text)

            # Single pass - text is within limits
            return self._pipeline(text)

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            # Fallback: try chunking anyway if direct call failed
            try:
                logger.info("Attempting chunked extraction as fallback")
                return self._extract_chunked(text)
            except Exception as e2:
                logger.error(f"Chunked extraction also failed: {e2}")
                return []

    def _extract_chunked(self, text: str) -> list[dict[str, Any]]:
        """Extract from very long text using overlapping chunks.

        Uses conservative chunk sizing to avoid exceeding model limits.
        """
        # Conservative: ~3 chars per token to stay well under limit
        # This ensures chunks won't exceed max_sequence_length even with
        # variable token lengths (some tokens < 1 char, e.g., subwords)
        chars_per_token = 3
        # Use 75% of max to leave buffer for tokenization variance
        max_chunk_tokens = int(self.config.max_sequence_length * 0.75)
        chunk_chars = max_chunk_tokens * chars_per_token
        overlap_chars = 200

        all_entities = []
        start = 0
        chunk_num = 0

        while start < len(text):
            end = min(start + chunk_chars, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                for punct in [". ", ".\n", "! ", "? "]:
                    last_punct = text[start:end].rfind(punct)
                    if last_punct > chunk_chars // 2:
                        end = start + last_punct + len(punct)
                        break

            chunk = text[start:end]
            chunk_num += 1

            try:
                entities = self._pipeline(chunk)

                # Adjust offsets for chunk position
                for ent in entities:
                    ent["start"] += start
                    ent["end"] += start

                all_entities.extend(entities)
            except Exception as e:
                logger.warning(f"Chunk {chunk_num} extraction failed ({len(chunk)} chars): {e}")
                # Continue with next chunk

            start = end - overlap_chars

        logger.info(f"Processed {chunk_num} chunks, found {len(all_entities)} raw entities")
        return self._deduplicate_entities(all_entities)

    def _deduplicate_entities(self, entities: list[dict]) -> list[dict]:
        """Remove duplicate entities from overlapping chunks."""
        if not entities:
            return []

        # Sort by start position
        entities.sort(key=lambda e: (e["start"], -e.get("score", 0)))

        deduplicated = []
        seen_spans: set[tuple[int, int]] = set()

        for ent in entities:
            span = (ent["start"], ent["end"])
            if span not in seen_spans:
                deduplicated.append(ent)
                seen_spans.add(span)

        return deduplicated

    def extract_with_context(
        self,
        text: str,
        context_window: int | None = None,
    ) -> list[EntityWithContext]:
        """Extract entities with surrounding context.

        Useful for downstream tasks like relation extraction or
        LLM-based refinement.

        Args:
            text: Clinical text to process.
            context_window: Override default context window (chars).

        Returns:
            List of EntityWithContext objects.
        """
        window = context_window or self.config.context_window
        raw_entities = self.extract_entities(text)

        entities_with_context = []
        for ent in raw_entities:
            entity_text = ent.get("word", "")
            start = ent.get("start", 0)
            end = ent.get("end", 0)

            context_before = text[max(0, start - window):start]
            context_after = text[end:min(len(text), end + window)]
            sentence = self._get_sentence(text, start)

            entities_with_context.append(EntityWithContext(
                text=entity_text,
                start=start,
                end=end,
                entity_type=ent.get("entity_group", "UNKNOWN"),
                confidence=ent.get("score", 0.0),
                context_before=context_before,
                context_after=context_after,
                full_sentence=sentence,
            ))

        return entities_with_context

    def extract_mentions(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
    ) -> list[ExtractedMention]:
        """Extract clinical mentions (standard NLP interface).

        Args:
            text: Clinical note text to process.
            document_id: UUID of the source document.
            note_type: Optional note type for context.

        Returns:
            List of ExtractedMention objects.
        """
        raw_entities = self.extract_entities(text)
        mentions: list[ExtractedMention] = []

        for ent in raw_entities:
            try:
                entity_text = ent.get("word", "")
                start = ent.get("start", 0)
                end = ent.get("end", 0)
                confidence = ent.get("score", 0.7)

                # Skip short entities
                if len(entity_text.strip()) < self.config.min_entity_length:
                    continue

                # Map entity type to domain
                entity_type = ent.get("entity_group", "UNKNOWN")
                if entity_type.startswith(("B-", "I-")):
                    entity_type = entity_type[2:]

                domain = ENTITY_TO_DOMAIN.get(entity_type.upper())
                if domain is None:
                    continue

                # Skip low confidence
                if confidence < self.config.min_confidence:
                    continue

                # Detect attributes from context
                assertion = self._detect_assertion(text, start, end)
                temporality = self._detect_temporality(text, start, end)
                experiencer = self._detect_experiencer(text, start, end)
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

        logger.debug(f"ModernBERT extracted {len(mentions)} mentions from document {document_id}")
        return mentions


# Singleton instance
_modernbert_ner_service: ModernBERTNERService | None = None
_modernbert_ner_lock = threading.Lock()


def get_modernbert_ner_service(
    config: ModernBERTConfig | None = None,
) -> ModernBERTNERService:
    """Get the singleton ModernBERT NER service.

    Args:
        config: Optional configuration. Only used on first call.

    Returns:
        ModernBERTNERService instance.
    """
    global _modernbert_ner_service
    if _modernbert_ner_service is None:
        with _modernbert_ner_lock:
            if _modernbert_ner_service is None:
                _modernbert_ner_service = ModernBERTNERService(
                    config=config or ModernBERTConfig()
                )
    return _modernbert_ner_service


def reset_modernbert_ner_service() -> None:
    """Reset the singleton service (for testing)."""
    global _modernbert_ner_service
    with _modernbert_ner_lock:
        _modernbert_ner_service = None
