"""Provenance assembler for building structured provenance chains.

Assembles reasoning chains and entity provenance from database records
into structured dictionaries suitable for API responses.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.provenance_db_service import get_provenance_db_service

logger = logging.getLogger(__name__)


async def assemble_reasoning_chain(
    query_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Assemble a structured reasoning chain for a query.

    Returns a dict with steps, total confidence, total duration,
    and source attribution.
    """
    provenance_svc = get_provenance_db_service()
    traces = await provenance_svc.get_reasoning_for_query(session, query_id)

    steps = []
    for trace in traces:
        step = {
            "step_order": trace.step_order,
            "step_type": trace.step_type,
            "input_summary": trace.input_summary,
            "output_summary": trace.output_summary,
            "confidence_contribution": trace.confidence_contribution,
            "duration_ms": trace.duration_ms,
            "metadata": trace.extra_metadata,
            "created_at": trace.created_at.isoformat() if trace.created_at else None,
        }
        steps.append(step)

    total_confidence = sum(t.confidence_contribution or 0 for t in traces)
    total_duration = sum(t.duration_ms or 0 for t in traces)

    # Determine source types used
    source_types = set()
    for trace in traces:
        if trace.step_type == "kg_retrieval":
            source_types.add("knowledge_graph")
        elif trace.step_type == "rag_search":
            source_types.add("clinical_guidelines")
            if trace.extra_metadata and trace.extra_metadata.get("policy_count", 0) > 0:
                source_types.add("institutional_policies")
        elif trace.step_type == "llm_inference":
            source_types.add("llm_reasoning")

    return {
        "query_id": query_id,
        "steps": steps,
        "total_steps": len(steps),
        "total_confidence": round(total_confidence, 4),
        "total_duration_ms": round(total_duration, 2),
        "source_types": sorted(source_types),
    }


async def assemble_entity_provenance(
    entity_ids: list[tuple[str, str]],
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Assemble provenance for a list of entities.

    Args:
        entity_ids: List of (entity_type, entity_id) tuples.
        session: Database session.

    Returns:
        List of provenance dicts with entity label, source doc,
        extraction method, and original text span.
    """
    provenance_svc = get_provenance_db_service()
    results = []

    for entity_type, entity_id in entity_ids:
        records = await provenance_svc.get_provenance_for_entity(
            session, entity_type, entity_id
        )

        for record in records:
            results.append({
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "patient_id": record.patient_id,
                "extraction_method": record.extraction_method,
                "confidence_level": record.confidence_level,
                "confidence_score": record.confidence_score,
                "source_document_id": record.source_document_id,
                "source_section": record.source_section,
                "extracted_text": record.extracted_text,
                "extraction_model": record.extraction_model,
                "extraction_timestamp": (
                    record.extraction_timestamp.isoformat()
                    if record.extraction_timestamp
                    else None
                ),
                "metadata": record.extra_metadata,
            })

    return results
