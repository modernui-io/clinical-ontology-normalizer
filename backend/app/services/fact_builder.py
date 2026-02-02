"""Fact builder service for ClinicalFact construction.

Converts mentions and structured data into canonical ClinicalFacts
with evidence linking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.clinical_fact import EvidenceType


@dataclass
class FactInput:
    """Input data for creating a ClinicalFact.

    This is an intermediate representation that can be populated
    from either NLP mentions or structured data sources.
    """

    patient_id: str
    domain: Domain
    omop_concept_id: int
    concept_name: str
    assertion: Assertion = Assertion.PRESENT
    temporality: Temporality = Temporality.CURRENT
    experiencer: Experiencer = Experiencer.PATIENT
    confidence: float = 1.0
    value: str | None = None
    unit: str | None = None
    # Event date - extracted from mention context
    start_date: datetime | None = None
    end_date: datetime | None = None

    @property
    def is_negated(self) -> bool:
        """Check if this fact input is for a negated finding."""
        return self.assertion == Assertion.ABSENT

    @property
    def is_uncertain(self) -> bool:
        """Check if this fact input is for an uncertain finding."""
        return self.assertion == Assertion.POSSIBLE


@dataclass
class EvidenceInput:
    """Input data for creating FactEvidence.

    Links a fact to its source evidence.
    """

    evidence_type: EvidenceType
    source_id: UUID
    source_table: str
    weight: float = 1.0
    notes: str | None = None


@dataclass
class FactResult:
    """Result of creating a ClinicalFact.

    Contains the fact ID and associated evidence IDs.
    """

    fact_id: UUID
    evidence_ids: list[UUID] = field(default_factory=list)
    is_new: bool = True  # False if merged with existing fact


class FactBuilderServiceInterface(ABC):
    """Interface for ClinicalFact construction services.

    All fact builder implementations must implement this interface
    to ensure compatibility with the document processing pipeline.

    Example usage:
        builder = MyFactBuilder(session)
        result = builder.create_fact_from_mention(mention, patient_id)
    """

    @abstractmethod
    def create_fact(
        self,
        fact_input: FactInput,
        evidence: list[EvidenceInput] | None = None,
    ) -> FactResult:
        """Create a ClinicalFact with optional evidence.

        IMPORTANT: This method must correctly handle negated findings.
        Facts with assertion=ABSENT should be created and stored
        but NOT inserted into positive OMOP event tables.

        Args:
            fact_input: The fact data to create.
            evidence: Optional list of evidence inputs.

        Returns:
            FactResult with the created fact ID.
        """
        pass  # pragma: no cover

    @abstractmethod
    def create_fact_from_mention(
        self,
        mention_id: UUID,
        patient_id: str,
        omop_concept_id: int,
        concept_name: str,
        domain: Domain,
        assertion: Assertion,
        temporality: Temporality,
        experiencer: Experiencer,
        confidence: float,
        event_date: datetime | None = None,
    ) -> FactResult:
        """Create a ClinicalFact from an NLP-extracted mention.

        Convenience method that creates both the fact and the
        mention evidence link in one call.

        Args:
            mention_id: UUID of the source mention.
            patient_id: Patient identifier.
            omop_concept_id: OMOP concept ID.
            concept_name: Human-readable concept name.
            domain: OMOP domain.
            assertion: Assertion status (present/absent/possible).
            temporality: Temporal context.
            experiencer: Who the fact applies to.
            confidence: Confidence score.
            event_date: When the clinical event occurred (from mention).

        Returns:
            FactResult with the created fact ID.
        """
        pass  # pragma: no cover

    @abstractmethod
    def create_fact_from_structured(
        self,
        source_id: UUID,
        source_table: str,
        patient_id: str,
        omop_concept_id: int,
        concept_name: str,
        domain: Domain,
        value: str | None = None,
        unit: str | None = None,
    ) -> FactResult:
        """Create a ClinicalFact from structured data.

        Handles FHIR resources, CSV imports, or other structured
        data sources.

        Args:
            source_id: UUID of the source record.
            source_table: Name of the source table.
            patient_id: Patient identifier.
            omop_concept_id: OMOP concept ID.
            concept_name: Human-readable concept name.
            domain: OMOP domain.
            value: Optional value (for measurements).
            unit: Optional unit (for measurements).

        Returns:
            FactResult with the created fact ID.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_fact_by_id(self, fact_id: UUID) -> FactInput | None:
        """Retrieve a fact by its ID.

        Args:
            fact_id: The UUID of the fact.

        Returns:
            FactInput if found, None otherwise.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_facts_for_patient(
        self,
        patient_id: str,
        domain: Domain | None = None,
        include_negated: bool = True,
    ) -> list[FactInput]:
        """Get all facts for a patient.

        Args:
            patient_id: Patient identifier.
            domain: Optional domain filter.
            include_negated: Whether to include negated findings.

        Returns:
            List of FactInput objects.
        """
        pass  # pragma: no cover


class BaseFactBuilderService(FactBuilderServiceInterface):
    """Base fact builder with common functionality.

    Provides shared utilities for fact construction. Subclasses
    should override methods as needed.
    """

    def calculate_dedup_key(
        self,
        patient_id: str,
        omop_concept_id: int,
        assertion: Assertion,
        temporality: Temporality,
        experiencer: Experiencer,
    ) -> str:
        """Calculate a deduplication key for a fact.

        Used to identify potentially duplicate facts that should
        be merged rather than duplicated.

        Args:
            patient_id: Patient identifier.
            omop_concept_id: OMOP concept ID.
            assertion: Assertion status.
            temporality: Temporal context.
            experiencer: Who the fact applies to.

        Returns:
            String key for deduplication.
        """
        return f"{patient_id}:{omop_concept_id}:{assertion.value}:{temporality.value}:{experiencer.value}"

    def merge_confidence(
        self,
        existing_confidence: float,
        new_confidence: float,
    ) -> float:
        """Merge confidence scores when deduplicating facts.

        Uses a simple formula: 1 - (1 - a) * (1 - b)
        This increases confidence when multiple sources agree.

        Args:
            existing_confidence: Current confidence.
            new_confidence: New evidence confidence.

        Returns:
            Merged confidence score.
        """
        return 1.0 - (1.0 - existing_confidence) * (1.0 - new_confidence)

    def should_preserve_negation(self, assertion: Assertion) -> bool:
        """Check if a negated finding should be preserved.

        IMPORTANT: Negated findings (assertion=ABSENT) must be preserved
        in the fact table and exported to NOTE_NLP with term_exists='N'.

        Args:
            assertion: The assertion status.

        Returns:
            True if this is a negated finding that should be preserved.
        """
        return assertion == Assertion.ABSENT

    # Default implementations that return empty/None
    def create_fact(
        self,
        fact_input: FactInput,
        evidence: list[EvidenceInput] | None = None,
    ) -> FactResult:
        """Default implementation - override in subclass."""
        raise NotImplementedError("Subclass must implement create_fact")

    def create_fact_from_mention(
        self,
        mention_id: UUID,
        patient_id: str,
        omop_concept_id: int,
        concept_name: str,
        domain: Domain,
        assertion: Assertion,
        temporality: Temporality,
        experiencer: Experiencer,
        confidence: float,
        event_date: datetime | None = None,
    ) -> FactResult:
        """Default implementation using create_fact."""
        fact_input = FactInput(
            patient_id=patient_id,
            domain=domain,
            omop_concept_id=omop_concept_id,
            concept_name=concept_name,
            assertion=assertion,
            temporality=temporality,
            experiencer=experiencer,
            confidence=confidence,
            start_date=event_date,  # Propagate event_date to start_date
        )
        evidence = [
            EvidenceInput(
                evidence_type=EvidenceType.MENTION,
                source_id=mention_id,
                source_table="mentions",
            )
        ]
        return self.create_fact(fact_input, evidence)

    def create_fact_from_structured(
        self,
        source_id: UUID,
        source_table: str,
        patient_id: str,
        omop_concept_id: int,
        concept_name: str,
        domain: Domain,
        value: str | None = None,
        unit: str | None = None,
    ) -> FactResult:
        """Default implementation using create_fact."""
        fact_input = FactInput(
            patient_id=patient_id,
            domain=domain,
            omop_concept_id=omop_concept_id,
            concept_name=concept_name,
            value=value,
            unit=unit,
        )
        evidence = [
            EvidenceInput(
                evidence_type=EvidenceType.STRUCTURED,
                source_id=source_id,
                source_table=source_table,
            )
        ]
        return self.create_fact(fact_input, evidence)

    def get_fact_by_id(self, fact_id: UUID) -> FactInput | None:
        """Default implementation returns None."""
        return None

    def get_facts_for_patient(
        self,
        patient_id: str,
        domain: Domain | None = None,
        include_negated: bool = True,
    ) -> list[FactInput]:
        """Default implementation returns empty list."""
        return []
