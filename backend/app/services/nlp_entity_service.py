"""NLP Entity Service - Backwards compatibility re-exports.

# DEPRECATED: Import from app.services.nlp_entity directly

This module has been refactored into the app.services.nlp_entity package.
All imports are re-exported here for backwards compatibility.

The service is now split into:
- nlp_entity/nlp_entity_core.py - Main service class and orchestration
- nlp_entity/nlp_entity_extractors.py - Entity extraction logic and patterns
- nlp_entity/nlp_entity_linkers.py - Concept linking to standard vocabularies
- nlp_entity/nlp_entity_normalizers.py - Text preprocessing and negation detection
"""

from __future__ import annotations

# Re-export everything from the new package for backwards compatibility
from app.services.nlp_entity import (
    # Main service
    ClinicalNLPEntityService,
    get_nlp_entity_service,
    reset_nlp_entity_service,
    # Result types
    ExtractionResult,
    NormalizationResult,
    ExtractedEntity,
    # Enums and types
    EntityType,
    AssertionStatus,
    ClinicalSection,
    NormalizationVocabulary,
    # Data classes
    EntitySpan,
    NormalizedCode,
    SectionSpan,
    NLPModelInfo,
    # Protocols
    MLModelProtocol,
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
