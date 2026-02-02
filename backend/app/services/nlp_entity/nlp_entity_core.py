"""Main NLP Entity Service class - core orchestration.

This module contains:
- ClinicalNLPEntityService class
- Public API for entity extraction and normalization
- ML model registration and management
- Service statistics
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .nlp_entity_normalizers import (
    AssertionStatus,
    ClinicalSection,
    EntitySpan,
    EntityType,
    NormalizedCode,
    NormalizationVocabulary,
    NormalizerMixin,
    SectionSpan,
)
from .nlp_entity_extractors import (
    ExtractedEntity,
    ExtractorMixin,
    DIAGNOSIS_PATTERNS,
    SYMPTOM_PATTERNS,
    MEDICATION_PATTERNS,
    PROCEDURE_PATTERNS,
    VITAL_SIGN_PATTERNS,
    LAB_RESULT_PATTERNS,
    ALLERGY_PATTERNS,
    SOCIAL_HISTORY_PATTERNS,
)
from .nlp_entity_linkers import (
    LinkerMixin,
    NormalizationResult,
    CLINICAL_CODE_MAPPINGS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Public Re-exports for backwards compatibility
# ============================================================================

# Re-export all the types that were previously defined in nlp_entity_service.py
__all__ = [
    "EntityType",
    "AssertionStatus",
    "ClinicalSection",
    "NormalizationVocabulary",
    "EntitySpan",
    "NormalizedCode",
    "SectionSpan",
    "ExtractedEntity",
    "NormalizationResult",
    "ExtractionResult",
    "NLPModelInfo",
    "MLModelProtocol",
    "ClinicalNLPEntityService",
    "get_nlp_entity_service",
    "reset_nlp_entity_service",
]


# ============================================================================
# Protocols and Data Classes
# ============================================================================


class MLModelProtocol(Protocol):
    """Protocol for ML models that can be registered with the service."""

    def extract_entities(
        self, text: str, entity_types: list[EntityType] | None = None
    ) -> list[ExtractedEntity]:
        """Extract entities from text."""
        ...

    def get_model_info(self) -> "NLPModelInfo":
        """Get information about the model."""
        ...


@dataclass
class NLPModelInfo:
    """Information about an NLP model."""

    model_id: str
    name: str
    description: str
    entity_types: list[EntityType]
    is_available: bool
    version: str = "1.0.0"
    metadata: dict = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of entity extraction."""

    entities: list[ExtractedEntity]
    model_id: str
    processing_time_ms: float
    text_length: int
    sections: list[SectionSpan] = field(default_factory=list)

    @property
    def entity_count(self) -> int:
        """Get total number of entities."""
        return len(self.entities)

    @property
    def entities_by_type(self) -> dict[str, int]:
        """Get entity counts by type."""
        counts: dict[str, int] = {}
        for entity in self.entities:
            type_name = entity.entity_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "entity_count": self.entity_count,
            "entities_by_type": self.entities_by_type,
            "model_id": self.model_id,
            "processing_time_ms": self.processing_time_ms,
            "text_length": self.text_length,
            "entities": [
                {
                    "id": e.id,
                    "type": e.entity_type.value,
                    "text": e.text,
                    "normalized_text": e.normalized_text,
                    "span": {"start": e.span.start, "end": e.span.end},
                    "section": e.section.value,
                    "assertion": e.assertion.value,
                    "confidence": e.confidence,
                    "normalized_codes": [
                        {
                            "code": c.code,
                            "display": c.display,
                            "system": c.system.value,
                            "confidence": c.confidence,
                        }
                        for c in e.normalized_codes
                    ],
                }
                for e in self.entities
            ],
        }


# ============================================================================
# Main Service Class
# ============================================================================


class ClinicalNLPEntityService(NormalizerMixin, ExtractorMixin, LinkerMixin):
    """Clinical NLP service for entity extraction and normalization.

    This service provides:
    - Rule-based entity extraction for clinical text
    - Entity normalization to standard vocabularies (SNOMED, RxNorm, ICD-10, etc.)
    - Negation detection using NegEx-style algorithm
    - Section detection for clinical documents
    - ML model registration for enhanced extraction
    - Drug interaction checking

    Usage:
        service = ClinicalNLPEntityService()
        result = service.extract_entities("Patient has diabetes and hypertension")
        for entity in result.entities:
            print(f"{entity.entity_type}: {entity.text}")
    """

    # Pattern constants (reference to imported patterns)
    DIAGNOSIS_PATTERNS = DIAGNOSIS_PATTERNS
    MEDICATION_PATTERNS = MEDICATION_PATTERNS
    PROCEDURE_PATTERNS = PROCEDURE_PATTERNS
    VITAL_SIGN_PATTERNS = VITAL_SIGN_PATTERNS
    LAB_RESULT_PATTERNS = LAB_RESULT_PATTERNS
    ALLERGY_PATTERNS = ALLERGY_PATTERNS
    SOCIAL_HISTORY_PATTERNS = SOCIAL_HISTORY_PATTERNS
    CLINICAL_CODE_MAPPINGS = CLINICAL_CODE_MAPPINGS

    # Negation triggers (from normalizers module)
    NEGATION_TRIGGERS = [
        r"\bno\b",
        r"\bnot\b",
        r"\bdenies\b",
        r"\bdenied\b",
        r"\bwithout\b",
        r"\babsence\s+of\b",
        r"\bnegative\s+for\b",
        r"\bruled\s+out\b",
        r"\bunlikely\b",
        r"\bno\s+evidence\s+of\b",
        r"\bnever\b",
        r"\bnone\b",
        r"\bfree\s+of\b",
        r"\brules\s+out\b",
        r"\bdeclines\b",
        r"\bdoes\s+not\s+have\b",
        r"\bnon-?\b",
        r"\blow\s+suspicion\s+for\b",
        r"\bno\s+suspicion\s+for\b",
        r"\blow\s+concern\s+for\b",
    ]

    def __init__(self) -> None:
        """Initialize the NLP entity service."""
        # Pattern compilation state
        self._initialized = False
        self._section_regexes: dict = {}
        self._negation_regexes: list = []
        self._uncertainty_regexes: list = []
        self._family_history_regexes: list = []

        # Clinical terminology data
        self._clinical_abbreviations: dict = {}
        self._loinc_codes: dict = {}
        self._abbreviations_loaded = False

        # Terminology services (lazy loaded)
        self._rxnorm_service: Any = None
        self._snomed_service: Any = None
        self._icd10_service: Any = None
        self._cpt_service: Any = None
        self._drug_interactions_service: Any = None

        # ML model registry
        self._ml_models: dict[str, MLModelProtocol] = {}

        # Compile patterns
        self._compile_patterns()

        logger.info("ClinicalNLPEntityService initialized")

    def extract_entities(
        self,
        text: str,
        entity_types: list[EntityType] | None = None,
        model_id: str = "rule_based",
    ) -> ExtractionResult:
        """Extract clinical entities from text.

        Args:
            text: The clinical text to process.
            entity_types: Optional list of entity types to extract. If None, extracts all.
            model_id: The model to use for extraction. Default is "rule_based".

        Returns:
            ExtractionResult containing extracted entities.
        """
        start_time = time.perf_counter()

        # Use ML model if specified and available
        if model_id != "rule_based" and model_id in self._ml_models:
            ml_entities = self._ml_models[model_id].extract_entities(text, entity_types)
            processing_time = (time.perf_counter() - start_time) * 1000
            return ExtractionResult(
                entities=ml_entities,
                model_id=model_id,
                processing_time_ms=round(processing_time, 2),
                text_length=len(text),
            )

        # Rule-based extraction
        sections = self._detect_sections(text)

        all_entities: list[ExtractedEntity] = []

        # Extract by type
        extract_all = entity_types is None

        if extract_all or EntityType.DIAGNOSIS in entity_types or EntityType.SYMPTOM in entity_types:
            all_entities.extend(self._extract_diagnoses_and_symptoms(text, sections))

        if extract_all or EntityType.MEDICATION in entity_types:
            all_entities.extend(self._extract_medications(text, sections))

        if extract_all or EntityType.PROCEDURE in entity_types:
            all_entities.extend(self._extract_procedures(text, sections))

        if extract_all or EntityType.VITAL_SIGN in entity_types:
            all_entities.extend(self._extract_vital_signs(text, sections))

        if extract_all or EntityType.LAB_RESULT in entity_types:
            all_entities.extend(self._extract_lab_results(text, sections))

        if extract_all or EntityType.ANATOMICAL_LOCATION in entity_types:
            all_entities.extend(self._extract_anatomical_locations(text, sections))

        if extract_all or EntityType.TEMPORAL in entity_types:
            all_entities.extend(self._extract_temporal_expressions(text, sections))

        if extract_all or EntityType.ALLERGY in entity_types:
            all_entities.extend(self._extract_allergies(text, sections))

        if extract_all or EntityType.SOCIAL_HISTORY in entity_types:
            all_entities.extend(self._extract_social_history(text, sections))

        # Extract from clinical abbreviations dictionary
        all_entities.extend(self._extract_from_clinical_abbreviations(text, sections))

        # Apply negation detection
        all_entities = self._apply_negation_detection(text, all_entities)

        # Deduplicate overlapping entities
        all_entities = self._deduplicate_entities(all_entities)

        # Filter by requested entity types if specified
        if entity_types is not None:
            all_entities = [e for e in all_entities if e.entity_type in entity_types]

        processing_time = (time.perf_counter() - start_time) * 1000

        return ExtractionResult(
            entities=all_entities,
            model_id=model_id,
            processing_time_ms=round(processing_time, 2),
            text_length=len(text),
            sections=sections,
        )

    def get_model_info(self) -> NLPModelInfo:
        """Get information about the default rule-based model."""
        return NLPModelInfo(
            model_id="rule_based",
            name="Rule-Based Extractor",
            description="Pattern-based clinical entity extraction using regex and clinical rules",
            entity_types=list(EntityType),
            is_available=True,
            version="1.0.0",
        )

    def get_available_models(self) -> list[NLPModelInfo]:
        """Get list of available NLP models."""
        models = [
            NLPModelInfo(
                model_id="rule_based",
                name="Rule-Based Extractor",
                description="Pattern-based clinical entity extraction using regex and clinical rules",
                entity_types=list(EntityType),
                is_available=True,
                version="1.0.0",
            ),
        ]

        # Add registered ML models
        for model_id, model in self._ml_models.items():
            models.append(model.get_model_info())

        return models

    def register_ml_model(self, model_id: str, model: MLModelProtocol) -> None:
        """Register an ML model for entity extraction.

        Args:
            model_id: Unique identifier for the model.
            model: The ML model implementing MLModelProtocol.
        """
        self._ml_models[model_id] = model
        logger.info(f"Registered ML model: {model_id}")

    def get_stats(self) -> dict:
        """Get service statistics."""
        # Count total social history patterns
        social_history_count = sum(
            len(patterns) for patterns in self.SOCIAL_HISTORY_PATTERNS.values()
        )
        return {
            "registered_ml_models": len(self._ml_models),
            "available_entity_types": [e.value for e in EntityType],
            "negation_patterns": len(self.NEGATION_TRIGGERS),
            "diagnosis_patterns": len(self.DIAGNOSIS_PATTERNS),
            "medication_patterns": len(self.MEDICATION_PATTERNS),
            "procedure_patterns": len(self.PROCEDURE_PATTERNS),
            "lab_patterns": len(self.LAB_RESULT_PATTERNS),
            "vital_sign_patterns": len(self.VITAL_SIGN_PATTERNS),
            "allergy_patterns": len(self.ALLERGY_PATTERNS),
            "social_history_patterns": social_history_count,
        }


# ============================================================================
# Singleton Management
# ============================================================================

_nlp_entity_service: ClinicalNLPEntityService | None = None
_nlp_entity_lock = threading.Lock()


def get_nlp_entity_service() -> ClinicalNLPEntityService:
    """Get the singleton NLP entity service instance."""
    global _nlp_entity_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _nlp_entity_service is None:
        with _nlp_entity_lock:
            if _nlp_entity_service is None:
                _nlp_entity_service = ClinicalNLPEntityService()
    return _nlp_entity_service


def reset_nlp_entity_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _nlp_entity_service
    with _nlp_entity_lock:
        _nlp_entity_service = None
