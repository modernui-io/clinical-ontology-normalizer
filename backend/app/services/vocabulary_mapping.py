"""Vocabulary Mapping Service for cross-vocabulary translation.

Provides mapping between source vocabularies (ICD-10, CPT, NDC, etc.)
and OMOP standard vocabularies (SNOMED, RxNorm, LOINC).

This service uses OMOP concept_relationship data to:
- Map ICD-10-CM to SNOMED CT
- Map ICD-10-PCS to SNOMED CT
- Map CPT to SNOMED CT
- Map NDC to RxNorm
- Map ICD-9 to SNOMED CT
- Map LOINC to standard LOINC

Key features:
- Batch mapping for efficient processing
- Confidence scoring based on mapping type
- Unmapped code flagging and reporting
- Local code mapping support
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class MappingType(str, Enum):
    """Type of vocabulary mapping."""

    DIRECT = "direct"  # 1:1 "Maps to" relationship
    INFERRED = "inferred"  # Through hierarchy or semantic similarity
    LOCAL = "local"  # User-defined local code mapping
    UNMAPPED = "unmapped"  # No mapping found


class ConfidenceLevel(str, Enum):
    """Confidence level for mappings."""

    HIGH = "high"  # Direct 1:1 mapping
    MEDIUM = "medium"  # Inferred or multiple candidates
    LOW = "low"  # Uncertain or partial match


class SourceVocabulary(str, Enum):
    """Source vocabularies for mapping."""

    ICD10CM = "ICD10CM"
    ICD10PCS = "ICD10PCS"
    ICD9CM = "ICD9CM"
    ICD9PROC = "ICD9Proc"
    CPT4 = "CPT4"
    HCPCS = "HCPCS"
    NDC = "NDC"
    LOINC = "LOINC"
    SNOMED = "SNOMED"  # For hierarchy lookups
    RXNORM = "RxNorm"  # For hierarchy lookups


class TargetVocabulary(str, Enum):
    """Target standard vocabularies."""

    SNOMED = "SNOMED"
    RXNORM = "RxNorm"
    LOINC = "LOINC"


# Standard mapping paths
VOCABULARY_MAPPING_PATHS: dict[SourceVocabulary, TargetVocabulary] = {
    SourceVocabulary.ICD10CM: TargetVocabulary.SNOMED,
    SourceVocabulary.ICD10PCS: TargetVocabulary.SNOMED,
    SourceVocabulary.ICD9CM: TargetVocabulary.SNOMED,
    SourceVocabulary.ICD9PROC: TargetVocabulary.SNOMED,
    SourceVocabulary.CPT4: TargetVocabulary.SNOMED,
    SourceVocabulary.HCPCS: TargetVocabulary.SNOMED,
    SourceVocabulary.NDC: TargetVocabulary.RXNORM,
    SourceVocabulary.LOINC: TargetVocabulary.LOINC,
}


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class MappingResult:
    """Result of mapping a source code to OMOP."""

    source_code: str
    source_vocabulary: str
    source_concept_id: int | None = None
    source_concept_name: str | None = None

    # Target (standard) concept
    target_concept_id: int | None = None
    target_concept_name: str | None = None
    target_vocabulary: str | None = None

    # Mapping metadata
    mapping_type: MappingType = MappingType.UNMAPPED
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_score: float = 0.0
    relationship_id: str | None = None

    # For unmapped codes
    unmapped_reason: str | None = None

    @property
    def is_mapped(self) -> bool:
        """Check if the code was successfully mapped."""
        return self.target_concept_id is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_code": self.source_code,
            "source_vocabulary": self.source_vocabulary,
            "source_concept_id": self.source_concept_id,
            "source_concept_name": self.source_concept_name,
            "target_concept_id": self.target_concept_id,
            "target_concept_name": self.target_concept_name,
            "target_vocabulary": self.target_vocabulary,
            "mapping_type": self.mapping_type.value,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "relationship_id": self.relationship_id,
            "is_mapped": self.is_mapped,
            "unmapped_reason": self.unmapped_reason,
        }


@dataclass
class BatchMappingResult:
    """Result of batch mapping operation."""

    total_codes: int = 0
    mapped_count: int = 0
    unmapped_count: int = 0
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0

    results: list[MappingResult] = field(default_factory=list)
    unmapped_codes: list[str] = field(default_factory=list)

    @property
    def mapping_rate(self) -> float:
        """Calculate the mapping success rate."""
        return self.mapped_count / self.total_codes if self.total_codes > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_codes": self.total_codes,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "mapping_rate": round(self.mapping_rate, 3),
            "high_confidence_count": self.high_confidence_count,
            "medium_confidence_count": self.medium_confidence_count,
            "low_confidence_count": self.low_confidence_count,
            "unmapped_codes": self.unmapped_codes,
        }


@dataclass
class LocalCodeMapping:
    """User-defined local code mapping."""

    local_code: str
    local_vocabulary: str
    local_description: str
    omop_concept_id: int
    omop_concept_name: str
    created_by: str | None = None
    approved: bool = False


# ============================================================================
# Vocabulary Mapping Service
# ============================================================================


class VocabularyMappingService:
    """Service for mapping between vocabularies.

    Uses OMOP concept_relationship data to translate source codes
    to standard OMOP concepts.

    Example:
        service = VocabularyMappingService()

        # Map a single ICD-10 code
        result = service.map_code("J18.9", SourceVocabulary.ICD10CM)
        if result.is_mapped:
            print(f"Mapped to SNOMED: {result.target_concept_name}")

        # Batch map multiple codes
        codes = [("J18.9", SourceVocabulary.ICD10CM), ("E11.9", SourceVocabulary.ICD10CM)]
        batch_result = service.batch_map_codes(codes)
        print(f"Mapping rate: {batch_result.mapping_rate:.1%}")
    """

    def __init__(self) -> None:
        """Initialize the vocabulary mapping service."""
        # Caches for efficient lookup
        self._concept_cache: dict[tuple[str, str], tuple[int, str]] = {}
        self._mapping_cache: dict[int, list[tuple[int, str, str]]] = {}
        self._local_mappings: dict[tuple[str, str], LocalCodeMapping] = {}

        # Statistics
        self._stats = {
            "lookups": 0,
            "cache_hits": 0,
            "mappings_found": 0,
            "unmapped": 0,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            **self._stats,
            "concept_cache_size": len(self._concept_cache),
            "mapping_cache_size": len(self._mapping_cache),
            "local_mappings": len(self._local_mappings),
        }

    def map_code(
        self,
        code: str,
        source_vocabulary: SourceVocabulary | str,
        target_vocabulary: TargetVocabulary | str | None = None,
    ) -> MappingResult:
        """Map a source code to OMOP standard concept.

        Args:
            code: The source code (e.g., "J18.9" for ICD-10)
            source_vocabulary: Source vocabulary
            target_vocabulary: Optional target vocabulary override

        Returns:
            MappingResult with mapping details
        """
        self._stats["lookups"] += 1

        # Normalize inputs
        if isinstance(source_vocabulary, str):
            source_vocabulary = SourceVocabulary(source_vocabulary)
        if isinstance(target_vocabulary, str):
            target_vocabulary = TargetVocabulary(target_vocabulary)

        # Determine target vocabulary
        if target_vocabulary is None:
            target_vocabulary = VOCABULARY_MAPPING_PATHS.get(source_vocabulary)

        # Check local mappings first
        local_key = (code.upper(), source_vocabulary.value)
        if local_key in self._local_mappings:
            local = self._local_mappings[local_key]
            self._stats["mappings_found"] += 1
            return MappingResult(
                source_code=code,
                source_vocabulary=source_vocabulary.value,
                source_concept_id=None,
                source_concept_name=local.local_description,
                target_concept_id=local.omop_concept_id,
                target_concept_name=local.omop_concept_name,
                target_vocabulary=target_vocabulary.value if target_vocabulary else None,
                mapping_type=MappingType.LOCAL,
                confidence=ConfidenceLevel.MEDIUM,
                confidence_score=0.7,
            )

        # Check concept cache
        cache_key = (code.upper(), source_vocabulary.value)
        if cache_key in self._concept_cache:
            self._stats["cache_hits"] += 1
            source_concept_id, source_name = self._concept_cache[cache_key]
        else:
            # Look up in vocabulary service
            source_concept_id, source_name = self._lookup_source_concept(
                code, source_vocabulary
            )
            if source_concept_id:
                self._concept_cache[cache_key] = (source_concept_id, source_name)

        if not source_concept_id:
            self._stats["unmapped"] += 1
            return MappingResult(
                source_code=code,
                source_vocabulary=source_vocabulary.value,
                mapping_type=MappingType.UNMAPPED,
                unmapped_reason=f"Source code not found in {source_vocabulary.value}",
            )

        # Find mapping to standard concept
        mappings = self._get_mappings(source_concept_id)

        if not mappings:
            self._stats["unmapped"] += 1
            return MappingResult(
                source_code=code,
                source_vocabulary=source_vocabulary.value,
                source_concept_id=source_concept_id,
                source_concept_name=source_name,
                mapping_type=MappingType.UNMAPPED,
                unmapped_reason="No 'Maps to' relationship found",
            )

        # Find best mapping (prefer "Maps to" relationship)
        best_mapping = None
        for target_id, relationship, target_name in mappings:
            if relationship == "Maps to":
                best_mapping = (target_id, relationship, target_name)
                break
        if not best_mapping and mappings:
            best_mapping = mappings[0]

        if best_mapping:
            target_id, relationship, target_name = best_mapping
            self._stats["mappings_found"] += 1

            # Calculate confidence based on relationship type
            if relationship == "Maps to":
                confidence = ConfidenceLevel.HIGH
                score = 0.95
            elif relationship in ("Is a", "Subsumes"):
                confidence = ConfidenceLevel.MEDIUM
                score = 0.75
            else:
                confidence = ConfidenceLevel.LOW
                score = 0.5

            return MappingResult(
                source_code=code,
                source_vocabulary=source_vocabulary.value,
                source_concept_id=source_concept_id,
                source_concept_name=source_name,
                target_concept_id=target_id,
                target_concept_name=target_name,
                target_vocabulary=target_vocabulary.value if target_vocabulary else None,
                mapping_type=MappingType.DIRECT,
                confidence=confidence,
                confidence_score=score,
                relationship_id=relationship,
            )

        self._stats["unmapped"] += 1
        return MappingResult(
            source_code=code,
            source_vocabulary=source_vocabulary.value,
            source_concept_id=source_concept_id,
            source_concept_name=source_name,
            mapping_type=MappingType.UNMAPPED,
            unmapped_reason="No suitable mapping found",
        )

    def batch_map_codes(
        self,
        codes: list[tuple[str, SourceVocabulary | str]],
        target_vocabulary: TargetVocabulary | str | None = None,
    ) -> BatchMappingResult:
        """Map multiple codes efficiently.

        Args:
            codes: List of (code, source_vocabulary) tuples
            target_vocabulary: Optional target vocabulary override

        Returns:
            BatchMappingResult with all mappings and statistics
        """
        result = BatchMappingResult(total_codes=len(codes))

        for code, source_vocab in codes:
            mapping = self.map_code(code, source_vocab, target_vocabulary)
            result.results.append(mapping)

            if mapping.is_mapped:
                result.mapped_count += 1
                if mapping.confidence == ConfidenceLevel.HIGH:
                    result.high_confidence_count += 1
                elif mapping.confidence == ConfidenceLevel.MEDIUM:
                    result.medium_confidence_count += 1
                else:
                    result.low_confidence_count += 1
            else:
                result.unmapped_count += 1
                result.unmapped_codes.append(f"{source_vocab}:{code}")

        return result

    def add_local_mapping(self, mapping: LocalCodeMapping) -> None:
        """Add a user-defined local code mapping.

        Args:
            mapping: The local mapping to add
        """
        key = (mapping.local_code.upper(), mapping.local_vocabulary)
        self._local_mappings[key] = mapping

    def get_unmapped_report(
        self,
        codes: list[tuple[str, SourceVocabulary | str]],
    ) -> dict[str, Any]:
        """Generate a report of unmapped codes.

        Args:
            codes: List of (code, source_vocabulary) tuples

        Returns:
            Report with unmapped code details and suggestions
        """
        batch_result = self.batch_map_codes(codes)

        unmapped_by_vocab: dict[str, list[str]] = {}
        for result in batch_result.results:
            if not result.is_mapped:
                vocab = result.source_vocabulary
                if vocab not in unmapped_by_vocab:
                    unmapped_by_vocab[vocab] = []
                unmapped_by_vocab[vocab].append(result.source_code)

        return {
            "total_codes": batch_result.total_codes,
            "unmapped_count": batch_result.unmapped_count,
            "unmapped_rate": 1 - batch_result.mapping_rate,
            "unmapped_by_vocabulary": unmapped_by_vocab,
            "unmapped_codes": batch_result.unmapped_codes,
            "suggestion": "Review unmapped codes for local mapping or vocabulary updates",
        }

    def _lookup_source_concept(
        self,
        code: str,
        vocabulary: SourceVocabulary,
    ) -> tuple[int | None, str | None]:
        """Look up source concept in vocabulary.

        This method should be overridden or connected to actual vocabulary data.
        For now, returns None (will be populated from database later).
        """
        # In production, this queries the concepts table
        # For now, return None to indicate lookup needed
        return None, None

    def _get_mappings(
        self,
        concept_id: int,
    ) -> list[tuple[int, str, str]]:
        """Get mappings for a concept.

        Returns list of (target_concept_id, relationship_id, target_name).
        This method should be overridden or connected to actual mapping data.
        """
        # Check cache
        if concept_id in self._mapping_cache:
            return self._mapping_cache[concept_id]

        # In production, this queries concept_relationships table
        # For now, return empty list (will be populated from database later)
        return []


# ============================================================================
# Singleton
# ============================================================================

_vocabulary_mapping_service: VocabularyMappingService | None = None
_vocabulary_lock = threading.Lock()


def get_vocabulary_mapping_service() -> VocabularyMappingService:
    """Get or create the vocabulary mapping service singleton."""
    global _vocabulary_mapping_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _vocabulary_mapping_service is None:
        with _vocabulary_lock:
            if _vocabulary_mapping_service is None:
                _vocabulary_mapping_service = VocabularyMappingService()
    return _vocabulary_mapping_service


def reset_vocabulary_mapping_service() -> None:
    """Reset the vocabulary mapping service singleton (for testing)."""
    global _vocabulary_mapping_service
    _vocabulary_mapping_service = None
