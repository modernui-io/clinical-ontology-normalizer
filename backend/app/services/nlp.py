"""NLP service interface for clinical text processing.

Provides the interface for extracting mentions from clinical documents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.schemas.base import Assertion, Experiencer, Temporality


@dataclass
class ExtractedMention:
    """A mention extracted from clinical text.

    This is the output of the NLP extraction process before
    it gets persisted to the database.
    """

    text: str
    start_offset: int
    end_offset: int
    lexical_variant: str
    section: str | None = None
    assertion: Assertion = field(default=Assertion.PRESENT)
    temporality: Temporality = field(default=Temporality.CURRENT)
    experiencer: Experiencer = field(default=Experiencer.PATIENT)
    confidence: float = 1.0
    # Domain hint from vocabulary (helps mapping service prioritize correct concept)
    domain_hint: str | None = None
    # Direct concept_id if known from curated vocabulary (bypasses mapping)
    omop_concept_id: int | None = None
    # Probabilistic assertion fields (from assertion_classifier)
    assertion_confidence: float | None = None  # Calibrated confidence in assertion (0-1)
    assertion_trigger: str | None = None  # The trigger pattern that determined assertion
    # Temporal fields (from temporal_extractor)
    event_date: datetime | None = None  # Resolved date from temporal expression
    date_precision: str | None = None  # "day", "month", "year", "approximate"
    temporal_relationship: str | None = None  # "onset", "diagnosed", "started", "stopped", "during"

    @property
    def is_negated(self) -> bool:
        """Check if this mention represents a negated finding."""
        return self.assertion == Assertion.ABSENT

    @property
    def is_uncertain(self) -> bool:
        """Check if this mention represents an uncertain finding."""
        return self.assertion == Assertion.POSSIBLE

    @property
    def is_family_history(self) -> bool:
        """Check if this mention is about family history."""
        return self.experiencer == Experiencer.FAMILY


class NLPServiceInterface(ABC):
    """Interface for NLP extraction services.

    All NLP implementations must implement this interface to ensure
    compatibility with the document processing pipeline.

    Example usage:
        class MyNLPService(NLPServiceInterface):
            def extract_mentions(self, text, document_id):
                # Implementation
                ...

        service = MyNLPService()
        mentions = service.extract_mentions(document.text, document.id)
    """

    @abstractmethod
    def extract_mentions(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
        document_date: datetime | None = None,
    ) -> list[ExtractedMention]:
        """Extract clinical mentions from document text.

        This method should identify clinical terms, conditions, drugs,
        measurements, and other relevant entities in the text. It should
        also determine the assertion (present/absent/possible), temporality
        (current/past/future), and experiencer (patient/family/other) for
        each mention.

        Args:
            text: The clinical note text to process.
            document_id: UUID of the source document (for logging/reference).
            note_type: Optional type of clinical note (e.g., 'progress_note',
                      'discharge_summary') which may influence extraction.
            document_date: Optional document date for resolving relative
                          temporal expressions (e.g., "3 days ago").

        Returns:
            List of ExtractedMention objects with text spans and attributes.
        """
        pass  # pragma: no cover


class BaseNLPService(NLPServiceInterface):
    """Base NLP service with common functionality.

    Provides shared utilities for NLP implementations.
    """

    def normalize_text(self, text: str) -> str:
        """Normalize clinical text for processing.

        Performs common preprocessing steps like:
        - Normalizing whitespace
        - Converting to consistent case where appropriate

        Args:
            text: Raw clinical text.

        Returns:
            Normalized text string.
        """
        # Normalize multiple whitespaces to single space
        import re

        normalized = re.sub(r"\s+", " ", text)
        return normalized.strip()

    def get_section_name(self, text: str, offset: int) -> str | None:
        """Try to identify the clinical section for a given offset.

        Common sections include: Chief Complaint, HPI, Assessment, Plan, etc.

        Args:
            text: The full document text.
            offset: Character offset to find section for.

        Returns:
            Section name if identified, None otherwise.
        """
        # Common clinical note section headers
        section_patterns = [
            "Chief Complaint",
            "CC",
            "History of Present Illness",
            "HPI",
            "Past Medical History",
            "PMH",
            "Social History",
            "Family History",
            "Review of Systems",
            "ROS",
            "Physical Exam",
            "PE",
            "Assessment",
            "Plan",
            "Medications",
            "Allergies",
            "Vital Signs",
            "Labs",
            "Imaging",
            "Hospital Course",
            "Discharge Diagnosis",
            "Admission Diagnosis",
            "Discharge Medications",
            "Follow-up",
        ]

        text_before = text[:offset].lower()

        # Find the most recent section header
        current_section = None
        current_pos = -1

        for pattern in section_patterns:
            # Look for pattern followed by : or newline
            search_pattern = pattern.lower()
            pos = text_before.rfind(search_pattern)
            if pos > current_pos:
                current_pos = pos
                current_section = pattern

        return current_section

    def extract_mentions(
        self,
        text: str,
        document_id: UUID,
        note_type: str | None = None,
        document_date: datetime | None = None,
    ) -> list[ExtractedMention]:
        """Default implementation that returns empty list.

        Subclasses should override this method.
        """
        return []
