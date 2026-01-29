"""OMOP Mapping service interface for clinical concept mapping.

Provides the interface for mapping extracted mentions to OMOP concepts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from app.schemas.base import Domain


class MappingMethod(str, Enum):
    """Method used for concept mapping."""

    EXACT = "exact"
    FUZZY = "fuzzy"
    ML = "ml"


@dataclass
class ConceptCandidate:
    """A candidate OMOP concept for a mention.

    This is the output of the mapping process before
    it gets persisted to the database.
    """

    omop_concept_id: int
    concept_name: str
    concept_code: str
    vocabulary_id: str
    domain_id: Domain
    score: float
    method: MappingMethod
    rank: int = 1

    @property
    def is_high_confidence(self) -> bool:
        """Check if this candidate has high confidence (score >= 0.9)."""
        return self.score >= 0.9

    @property
    def is_exact_match(self) -> bool:
        """Check if this candidate is from exact matching."""
        return self.method == MappingMethod.EXACT


class MappingServiceInterface(ABC):
    """Interface for OMOP concept mapping services.

    All mapping implementations must implement this interface to ensure
    compatibility with the document processing pipeline.

    Example usage:
        class MyMappingService(MappingServiceInterface):
            def map_mention(self, text, domain):
                # Implementation
                ...

        service = MyMappingService()
        candidates = service.map_mention("pneumonia", Domain.CONDITION)
    """

    @abstractmethod
    def map_mention(
        self,
        text: str,
        domain: Domain | None = None,
        limit: int = 5,
    ) -> list[ConceptCandidate]:
        """Map a mention text to OMOP concepts.

        This method should search for matching OMOP concepts and return
        ranked candidates with confidence scores.

        Args:
            text: The mention text to map (e.g., "pneumonia", "aspirin").
            domain: Optional domain filter (Condition, Drug, etc.).
            limit: Maximum number of candidates to return.

        Returns:
            List of ConceptCandidate objects ranked by score.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_best_match(
        self,
        text: str,
        domain: Domain | None = None,
    ) -> ConceptCandidate | None:
        """Get the best matching concept for a mention.

        Convenience method that returns only the top-ranked candidate.

        Args:
            text: The mention text to map.
            domain: Optional domain filter.

        Returns:
            The best ConceptCandidate or None if no match found.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_concept_by_id(
        self,
        concept_id: int,
    ) -> ConceptCandidate | None:
        """Get a concept by its OMOP concept ID.

        Args:
            concept_id: The OMOP concept ID.

        Returns:
            ConceptCandidate if found, None otherwise.
        """
        pass  # pragma: no cover


class BaseMappingService(MappingServiceInterface):
    """Base mapping service with common functionality.

    Provides shared utilities for mapping implementations.
    """

    def normalize_text(self, text: str) -> str:
        """Normalize text for mapping.

        Performs preprocessing steps like:
        - Converting to lowercase
        - Removing extra whitespace
        - Stripping punctuation at edges

        Args:
            text: Raw mention text.

        Returns:
            Normalized text string.
        """
        import re

        # Convert to lowercase
        normalized = text.lower()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        # Remove leading/trailing punctuation (but keep internal)
        normalized = re.sub(r"^[^\w]+|[^\w]+$", "", normalized)
        return normalized

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two texts.

        Uses simple token overlap as a baseline.

        Args:
            text1: First text string.
            text2: Second text string.

        Returns:
            Similarity score between 0 and 1.
        """
        # Normalize both texts
        t1 = set(self.normalize_text(text1).split())
        t2 = set(self.normalize_text(text2).split())

        if not t1 or not t2:
            return 0.0

        # Jaccard similarity
        intersection = len(t1 & t2)
        union = len(t1 | t2)

        return intersection / union if union > 0 else 0.0

    def map_mention(
        self,
        text: str,
        domain: Domain | None = None,
        limit: int = 5,
    ) -> list[ConceptCandidate]:
        """Default implementation returns empty list.

        Subclasses should override this method.
        """
        return []

    def get_best_match(
        self,
        text: str,
        domain: Domain | None = None,
    ) -> ConceptCandidate | None:
        """Get the best match by calling map_mention.

        Returns the first (highest ranked) result.
        """
        candidates = self.map_mention(text, domain, limit=1)
        return candidates[0] if candidates else None

    def get_concept_by_id(
        self,
        concept_id: int,
    ) -> ConceptCandidate | None:
        """Default implementation returns None.

        Subclasses should override this method.
        """
        return None
