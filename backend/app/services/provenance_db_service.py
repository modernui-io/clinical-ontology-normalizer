"""Provenance database service for tracking entity origins and reasoning traces.

Provides CRUD operations for provenance records and reasoning traces,
supporting full traceability from clinical answers back to source data.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provenance import (
    ConfidenceLevelDB,
    ExtractionMethodDB,
    ProvenanceRecord,
    ReasoningStepType,
    ReasoningTrace,
)

logger = logging.getLogger(__name__)


class ProvenanceDBService:
    """Service for managing provenance records and reasoning traces."""

    async def create_provenance_record(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: str,
        extraction_method: str,
        confidence_level: str = "medium",
        confidence_score: float | None = None,
        patient_id: str | None = None,
        source_document_id: str | None = None,
        source_section: str | None = None,
        source_span_start: int | None = None,
        source_span_end: int | None = None,
        extracted_text: str | None = None,
        extraction_model: str | None = None,
        extraction_timestamp: datetime | None = None,
        verified_by: str | None = None,
        verified_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProvenanceRecord:
        """Create a new provenance record for an extracted entity."""
        record = ProvenanceRecord(
            id=str(uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            patient_id=patient_id,
            extraction_method=extraction_method,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            source_document_id=source_document_id,
            source_section=source_section,
            source_span_start=source_span_start,
            source_span_end=source_span_end,
            extracted_text=extracted_text,
            extraction_model=extraction_model,
            extraction_timestamp=extraction_timestamp or datetime.now(timezone.utc),
            verified_by=verified_by,
            verified_at=verified_at,
            extra_metadata=metadata,
        )
        session.add(record)
        return record

    async def create_reasoning_trace(
        self,
        session: AsyncSession,
        query_id: str,
        step_order: int,
        step_type: str,
        patient_id: str | None = None,
        input_summary: str | None = None,
        output_summary: str | None = None,
        confidence_contribution: float | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReasoningTrace:
        """Create a new reasoning trace step."""
        trace = ReasoningTrace(
            id=str(uuid4()),
            query_id=query_id,
            patient_id=patient_id,
            step_order=step_order,
            step_type=step_type,
            input_summary=input_summary,
            output_summary=output_summary,
            confidence_contribution=confidence_contribution,
            duration_ms=duration_ms,
            extra_metadata=metadata,
        )
        session.add(trace)
        return trace

    async def get_provenance_for_entity(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: str,
    ) -> list[ProvenanceRecord]:
        """Get all provenance records for a specific entity."""
        result = await session.execute(
            select(ProvenanceRecord)
            .where(
                ProvenanceRecord.entity_type == entity_type,
                ProvenanceRecord.entity_id == entity_id,
            )
            .order_by(ProvenanceRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_reasoning_for_query(
        self,
        session: AsyncSession,
        query_id: str,
    ) -> list[ReasoningTrace]:
        """Get all reasoning traces for a query, ordered by step."""
        result = await session.execute(
            select(ReasoningTrace)
            .where(ReasoningTrace.query_id == query_id)
            .order_by(ReasoningTrace.step_order)
        )
        return list(result.scalars().all())

    async def get_provenance_chain(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: str,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Get nested provenance chain with source documents.

        Traverses from entity -> provenance records -> source documents,
        applying confidence decay at each hop.
        """
        HOP_DECAY = 0.9

        records = await self.get_provenance_for_entity(session, entity_type, entity_id)

        chain: dict[str, Any] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "provenance_records": [],
        }

        for record in records:
            record_data: dict[str, Any] = {
                "id": record.id,
                "extraction_method": record.extraction_method,
                "confidence_level": record.confidence_level,
                "confidence_score": record.confidence_score,
                "extracted_text": record.extracted_text,
                "source_document_id": record.source_document_id,
                "source_section": record.source_section,
                "source_span_start": record.source_span_start,
                "source_span_end": record.source_span_end,
                "extraction_model": record.extraction_model,
                "extraction_timestamp": (
                    record.extraction_timestamp.isoformat()
                    if record.extraction_timestamp
                    else None
                ),
                "metadata": record.extra_metadata,
            }

            # Apply confidence decay for downstream confidence
            if record.confidence_score is not None:
                record_data["effective_confidence"] = round(
                    record.confidence_score * (HOP_DECAY ** 1), 4
                )

            chain["provenance_records"].append(record_data)

        return chain

    async def get_provenance_for_patient(
        self,
        session: AsyncSession,
        patient_id: str,
        entity_type: str | None = None,
    ) -> list[ProvenanceRecord]:
        """Get all provenance records for a patient, optionally filtered by type."""
        stmt = select(ProvenanceRecord).where(
            ProvenanceRecord.patient_id == patient_id
        )
        if entity_type:
            stmt = stmt.where(ProvenanceRecord.entity_type == entity_type)
        stmt = stmt.order_by(ProvenanceRecord.created_at.desc())

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_reasoning_trace_confidence(
        self,
        session: AsyncSession,
        trace_id: str,
        confidence_contribution: float,
    ) -> None:
        """Update the confidence contribution of a reasoning trace step."""
        result = await session.execute(
            select(ReasoningTrace).where(ReasoningTrace.id == trace_id)
        )
        trace = result.scalar_one_or_none()
        if trace:
            trace.confidence_contribution = confidence_contribution

    async def create_concept_provenance(
        self,
        session: AsyncSession,
        concept_id: int,
        vocabulary_id: str,
        version: str | None = None,
        mapping_confidence: float | None = None,
    ) -> ProvenanceRecord:
        """Create provenance for an OMOP concept mapping."""
        return await self.create_provenance_record(
            session=session,
            entity_type="omop_concept",
            entity_id=str(concept_id),
            extraction_method="vocabulary_mapping",
            confidence_level="high" if (mapping_confidence or 0) >= 0.8 else "medium",
            confidence_score=mapping_confidence,
            metadata={
                "vocabulary_id": vocabulary_id,
                "version": version,
                "concept_id": concept_id,
            },
        )

    async def get_concept_provenance(
        self,
        session: AsyncSession,
        concept_id: int,
    ) -> list[ProvenanceRecord]:
        """Get provenance for an OMOP concept."""
        return await self.get_provenance_for_entity(
            session, "omop_concept", str(concept_id)
        )

    async def create_guideline_citation_provenance(
        self,
        session: AsyncSession,
        query_id: str,
        section_id: str,
        relevance_score: float,
        match_reasons: list[str] | None = None,
        evidence_grade: str | None = None,
        recommendation_level: str | None = None,
    ) -> ProvenanceRecord:
        """Create provenance for a guideline citation used in a query."""
        return await self.create_provenance_record(
            session=session,
            entity_type="guideline_citation",
            entity_id=section_id,
            extraction_method="rag_search",
            confidence_level="high" if relevance_score >= 0.7 else "medium",
            confidence_score=relevance_score,
            metadata={
                "query_id": query_id,
                "section_id": section_id,
                "relevance_score": relevance_score,
                "match_reasons": match_reasons or [],
                "evidence_grade": evidence_grade,
                "recommendation_level": recommendation_level,
            },
        )


# Singleton instance
_provenance_db_service: ProvenanceDBService | None = None
_provenance_db_lock = threading.Lock()


def get_provenance_db_service() -> ProvenanceDBService:
    """Get the singleton ProvenanceDBService instance."""
    global _provenance_db_service

    if _provenance_db_service is None:
        with _provenance_db_lock:
            if _provenance_db_service is None:
                logger.info("Creating singleton ProvenanceDBService instance")
                _provenance_db_service = ProvenanceDBService()

    return _provenance_db_service
