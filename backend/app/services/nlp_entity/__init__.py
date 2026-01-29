"""NLP services for clinical entity extraction and normalization.

This package provides clinical NLP capabilities:
- Entity extraction (diagnoses, medications, procedures, labs, vitals, etc.)
- Entity normalization to standard vocabularies (SNOMED-CT, RxNorm, ICD-10, CPT, LOINC)
- Negation detection using NegEx-style algorithm
- Section detection for clinical documents
- Drug interaction checking

Usage:
    from app.services.nlp_entity import ClinicalNLPEntityService, get_nlp_entity_service

    # Using singleton
    service = get_nlp_entity_service()
    result = service.extract_entities("Patient has diabetes and hypertension")

    # Or create new instance
    service = ClinicalNLPEntityService()
    result = service.extract_entities(text)
"""

# Re-export everything from core for backwards compatibility
from .nlp_entity_core import (
    ClinicalNLPEntityService,
    ExtractionResult,
    MLModelProtocol,
    NLPModelInfo,
    get_nlp_entity_service,
    reset_nlp_entity_service,
)

# Re-export types from normalizers
from .nlp_entity_normalizers import (
    AssertionStatus,
    ClinicalSection,
    EntitySpan,
    EntityType,
    NormalizedCode,
    NormalizationVocabulary,
    SectionSpan,
)

# Re-export extractors
from .nlp_entity_extractors import (
    ExtractedEntity,
)

# Re-export linkers
from .nlp_entity_linkers import (
    NormalizationResult,
)

__all__ = [
    # Main service
    "ClinicalNLPEntityService",
    "get_nlp_entity_service",
    "reset_nlp_entity_service",
    # Result types
    "ExtractionResult",
    "NormalizationResult",
    "ExtractedEntity",
    # Enums and types
    "EntityType",
    "AssertionStatus",
    "ClinicalSection",
    "NormalizationVocabulary",
    # Data classes
    "EntitySpan",
    "NormalizedCode",
    "SectionSpan",
    "NLPModelInfo",
    # Protocols
    "MLModelProtocol",
]
