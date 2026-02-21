"""Database-backed ClinicalFact builder service.

Implements fact construction with database persistence,
deduplication, and evidence linking.

IMPORTANT: Negated findings (assertion=ABSENT) MUST be preserved
and correctly represented in the knowledge graph.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pipeline_version import get_current_pipeline_version
from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.schemas.base import Assertion, Domain
from app.services.fact_builder import (
    BaseFactBuilderService,
    EvidenceInput,
    FactInput,
    FactResult,
)

logger = logging.getLogger(__name__)


class DatabaseFactBuilderService(BaseFactBuilderService):
    """Database-backed fact builder service.

    Creates and manages ClinicalFacts in the database with
    deduplication and evidence tracking.

    Usage:
        service = DatabaseFactBuilderService(session)
        result = service.create_fact_from_mention(
            mention_id=mention.id,
            patient_id="P001",
            omop_concept_id=437663,
            concept_name="Fever",
            domain=Domain.CONDITION,
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.95,
        )
    """

    def __init__(self, session: Session) -> None:
        """Initialize the database fact builder.

        Args:
            session: SQLAlchemy database session.
        """
        super().__init__()
        self._session = session
        self._dedup_cache: dict[str, UUID] = {}

    def create_fact(
        self,
        fact_input: FactInput,
        evidence: list[EvidenceInput] | None = None,
    ) -> FactResult:
        """Create a ClinicalFact with optional evidence.

        Handles deduplication - if a fact with the same key already
        exists, adds evidence to it instead of creating a duplicate.

        IMPORTANT: Negated findings are correctly preserved.
        """
        # Calculate dedup key
        dedup_key = self.calculate_dedup_key(
            patient_id=fact_input.patient_id,
            omop_concept_id=fact_input.omop_concept_id,
            assertion=fact_input.assertion,
            temporality=fact_input.temporality,
            experiencer=fact_input.experiencer,
        )

        # Check for existing fact
        existing_fact_id = self._find_existing_fact(dedup_key, fact_input)

        if existing_fact_id:
            # Add evidence to existing fact
            return self._add_evidence_to_existing(
                fact_id=existing_fact_id,
                evidence=evidence or [],
                new_confidence=fact_input.confidence,
            )

        # Create new fact
        # CSO-1: Stamp every new ClinicalFact with the current pipeline version
        pipeline_info = get_current_pipeline_version()
        fact = ClinicalFact(
            patient_id=fact_input.patient_id,
            domain=fact_input.domain,
            omop_concept_id=fact_input.omop_concept_id,
            concept_name=fact_input.concept_name,
            assertion=fact_input.assertion,
            temporality=fact_input.temporality,
            experiencer=fact_input.experiencer,
            confidence=fact_input.confidence,
            value=fact_input.value,
            unit=fact_input.unit,
            start_date=fact_input.start_date,
            end_date=fact_input.end_date,
            pipeline_version=pipeline_info.version_string,
        )
        self._session.add(fact)
        self._session.flush()  # Get the fact ID

        # Create evidence links - batch add, single flush
        evidence_records = []
        for ev in evidence or []:
            fact_evidence = FactEvidence(
                fact_id=fact.id,
                evidence_type=ev.evidence_type,
                source_id=str(ev.source_id),
                source_table=ev.source_table,
                weight=ev.weight,
                notes=ev.notes,
            )
            self._session.add(fact_evidence)
            evidence_records.append(fact_evidence)

        if evidence_records:
            self._session.flush()
        evidence_ids = [UUID(e.id) for e in evidence_records]

        # Cache for future dedup lookups
        self._dedup_cache[dedup_key] = UUID(fact.id)

        return FactResult(
            fact_id=UUID(fact.id),
            evidence_ids=evidence_ids,
            is_new=True,
        )

    def _find_existing_fact(
        self,
        dedup_key: str,
        fact_input: FactInput,
    ) -> UUID | None:
        """Find an existing fact matching the dedup key.

        Checks both the local cache and database.
        """
        # Check cache first
        if dedup_key in self._dedup_cache:
            return self._dedup_cache[dedup_key]

        # Query database
        stmt = (
            select(ClinicalFact)
            .where(ClinicalFact.patient_id == fact_input.patient_id)
            .where(ClinicalFact.omop_concept_id == fact_input.omop_concept_id)
            .where(ClinicalFact.assertion == fact_input.assertion)
            .where(ClinicalFact.temporality == fact_input.temporality)
            .where(ClinicalFact.experiencer == fact_input.experiencer)
        )
        result = self._session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            fact_id = UUID(existing.id)
            self._dedup_cache[dedup_key] = fact_id
            return fact_id

        return None

    def _add_evidence_to_existing(
        self,
        fact_id: UUID,
        evidence: list[EvidenceInput],
        new_confidence: float,
    ) -> FactResult:
        """Add evidence to an existing fact and update confidence."""
        # Get existing fact
        stmt = select(ClinicalFact).where(ClinicalFact.id == str(fact_id))
        result = self._session.execute(stmt)
        fact = result.scalar_one()

        # Update confidence using merge formula
        fact.confidence = self.merge_confidence(fact.confidence, new_confidence)

        # Add new evidence links - check existing in batch, then add all at once
        evidence_ids = []
        new_evidence_records = []

        if evidence:
            # Batch check for existing evidence
            existing_ev_stmt = (
                select(FactEvidence.source_id, FactEvidence.source_table)
                .where(FactEvidence.fact_id == str(fact_id))
            )
            existing_ev_result = self._session.execute(existing_ev_stmt)
            existing_keys = {(row[0], row[1]) for row in existing_ev_result}

            for ev in evidence:
                ev_key = (str(ev.source_id), ev.source_table)
                if ev_key not in existing_keys:
                    fact_evidence = FactEvidence(
                        fact_id=str(fact_id),
                        evidence_type=ev.evidence_type,
                        source_id=str(ev.source_id),
                        source_table=ev.source_table,
                        weight=ev.weight,
                        notes=ev.notes,
                    )
                    self._session.add(fact_evidence)
                    new_evidence_records.append(fact_evidence)

            if new_evidence_records:
                self._session.flush()
                evidence_ids = [UUID(e.id) for e in new_evidence_records]

        return FactResult(
            fact_id=fact_id,
            evidence_ids=evidence_ids,
            is_new=False,
        )

    def get_fact_by_id(self, fact_id: UUID) -> FactInput | None:
        """Retrieve a fact by its ID."""
        stmt = select(ClinicalFact).where(ClinicalFact.id == str(fact_id))
        result = self._session.execute(stmt)
        fact = result.scalar_one_or_none()

        if fact is None:
            return None

        return FactInput(
            patient_id=fact.patient_id,
            domain=fact.domain,
            omop_concept_id=fact.omop_concept_id,
            concept_name=fact.concept_name,
            assertion=fact.assertion,
            temporality=fact.temporality,
            experiencer=fact.experiencer,
            confidence=fact.confidence,
            value=fact.value,
            unit=fact.unit,
        )

    def get_facts_for_patient(
        self,
        patient_id: str,
        domain: Domain | None = None,
        include_negated: bool = True,
    ) -> list[FactInput]:
        """Get all facts for a patient."""
        stmt = select(ClinicalFact).where(ClinicalFact.patient_id == patient_id)

        if domain is not None:
            stmt = stmt.where(ClinicalFact.domain == domain)

        if not include_negated:
            stmt = stmt.where(ClinicalFact.assertion != Assertion.ABSENT)

        result = self._session.execute(stmt)
        facts = result.scalars().all()

        return [
            FactInput(
                patient_id=f.patient_id,
                domain=f.domain,
                omop_concept_id=f.omop_concept_id,
                concept_name=f.concept_name,
                assertion=f.assertion,
                temporality=f.temporality,
                experiencer=f.experiencer,
                confidence=f.confidence,
                value=f.value,
                unit=f.unit,
            )
            for f in facts
        ]

    def get_negated_facts_for_patient(self, patient_id: str) -> list[FactInput]:
        """Get negated findings for a patient.

        Returns facts with assertion=ABSENT, which should be
        exported to NOTE_NLP with term_exists='N'.
        """
        stmt = (
            select(ClinicalFact)
            .where(ClinicalFact.patient_id == patient_id)
            .where(ClinicalFact.assertion == Assertion.ABSENT)
        )
        result = self._session.execute(stmt)
        facts = result.scalars().all()

        return [
            FactInput(
                patient_id=f.patient_id,
                domain=f.domain,
                omop_concept_id=f.omop_concept_id,
                concept_name=f.concept_name,
                assertion=f.assertion,
                temporality=f.temporality,
                experiencer=f.experiencer,
                confidence=f.confidence,
                value=f.value,
                unit=f.unit,
            )
            for f in facts
        ]

    def get_evidence_for_fact(self, fact_id: UUID) -> list[EvidenceInput]:
        """Get all evidence linked to a fact."""
        stmt = select(FactEvidence).where(FactEvidence.fact_id == str(fact_id))
        result = self._session.execute(stmt)
        evidence_records = result.scalars().all()

        return [
            EvidenceInput(
                evidence_type=e.evidence_type,
                source_id=UUID(e.source_id),
                source_table=e.source_table,
                weight=e.weight,
                notes=e.notes,
            )
            for e in evidence_records
        ]
