"""Document processing job functions.

P0-014: Worker-based PHI operations emit audit events via log_audit / log_data_access.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, log_audit, log_data_access
from app.core.database import get_sync_engine
from app.models import Document
from app.models.mention import Mention, MentionConceptCandidate
from app.schemas.base import Assertion, Domain, Experiencer, JobStatus, Temporality
from app.services.fact_builder_db import DatabaseFactBuilderService
from app.services.kg_cache_service import get_kg_cache_service
from app.services.mapping_sql import SQLMappingService
from app.services.nlp_rule_based import RuleBasedNLPService

logger = logging.getLogger(__name__)

# Singleton NLP service for reuse across job calls
_nlp_service: RuleBasedNLPService | None = None
_nlp_service_lock = threading.Lock()


def get_nlp_service() -> RuleBasedNLPService:
    """Get or create the NLP service singleton."""
    global _nlp_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _nlp_service is None:
        with _nlp_service_lock:
            if _nlp_service is None:
                _nlp_service = RuleBasedNLPService()
    return _nlp_service


def get_mapping_service(session: Session) -> SQLMappingService:
    """Create a SQL-based mapping service for concept lookups.

    Uses SQL queries instead of loading all concepts into memory,
    enabling full 5.36M vocabulary support without OOM issues.
    """
    return SQLMappingService(session)


# Domain ID mapping from OMOP vocabulary to our Domain enum
DOMAIN_ID_MAP: dict[str, Domain] = {
    "condition": Domain.CONDITION,
    "drug": Domain.DRUG,
    "measurement": Domain.MEASUREMENT,
    "procedure": Domain.PROCEDURE,
    "observation": Domain.OBSERVATION,
    "device": Domain.DEVICE,
    "visit": Domain.VISIT,
}


def map_domain_id(domain_id: str | None) -> Domain:
    """Map an OMOP domain_id string to our Domain enum.

    Args:
        domain_id: The domain_id from OMOP vocabulary (e.g., "Condition", "Drug").

    Returns:
        The matching Domain enum, defaulting to OBSERVATION for unknown domains.
    """
    if domain_id is None:
        return Domain.OBSERVATION
    normalized = domain_id.lower()
    return DOMAIN_ID_MAP.get(normalized, Domain.OBSERVATION)


def map_assertion(assertion_str: str) -> Assertion:
    """Map assertion string to Assertion enum."""
    try:
        return Assertion(assertion_str)
    except ValueError:
        return Assertion.PRESENT


def map_temporality(temporality_str: str) -> Temporality:
    """Map temporality string to Temporality enum."""
    try:
        return Temporality(temporality_str)
    except ValueError:
        return Temporality.CURRENT


def map_experiencer(experiencer_str: str) -> Experiencer:
    """Map experiencer string to Experiencer enum."""
    try:
        return Experiencer(experiencer_str)
    except ValueError:
        return Experiencer.PATIENT


def process_document(document_id: str) -> dict:
    """Process a clinical document through the NLP pipeline.

    This function is executed by an RQ worker. It performs:
    1. Updates document status to PROCESSING
    2. Extracts mentions from the document text (Phase 4)
    3. Maps mentions to OMOP concepts (Phase 5)
    4. Creates ClinicalFacts (Phase 6)
    5. Updates document status to COMPLETED or FAILED

    Args:
        document_id: The UUID of the document to process.

    Returns:
        Dictionary with processing results including mention count.
    """
    logger.info(f"Starting document processing for document_id={document_id}")

    # P0-014: Audit the start of worker-based PHI processing
    log_audit(
        action=AuditAction.READ,
        resource_type="document",
        resource_id=document_id,
        user_id="worker:document_processing",
        details={"stage": "start"},
    )

    try:
        with Session(get_sync_engine()) as session:
            # Update status to PROCESSING
            session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status=JobStatus.PROCESSING)
            )
            session.commit()

            # Fetch the document
            stmt = select(Document).where(Document.id == document_id)
            result = session.execute(stmt)
            document = result.scalar_one_or_none()

            if document is None:
                logger.error(f"Document not found: {document_id}")
                return {"success": False, "error": "Document not found"}

            logger.info(
                f"Processing document: patient_id={document.patient_id}, "
                f"note_type={document.note_type}"
            )

            # Phase 4: Extract mentions using NLP service
            nlp_service = get_nlp_service()
            extracted_mentions = nlp_service.extract_mentions(
                text=document.text,
                document_id=UUID(document_id),
                note_type=document.note_type,
            )

            logger.info(f"Extracted {len(extracted_mentions)} mentions from document")

            # Create Mention records in database
            # Also track direct concept_ids from vocabulary for use in fact building
            mention_records: list[Mention] = []
            direct_concept_map: dict[str, tuple[int, str]] = {}  # mention_id -> (concept_id, domain)

            for extracted in extracted_mentions:
                # Explicitly generate ID to ensure it's available before flush
                mention_id = str(uuid4())
                mention = Mention(
                    id=mention_id,
                    document_id=document_id,
                    text=extracted.text,
                    start_offset=extracted.start_offset,
                    end_offset=extracted.end_offset,
                    lexical_variant=extracted.lexical_variant,
                    section=extracted.section,
                    assertion=extracted.assertion,
                    temporality=extracted.temporality,
                    experiencer=extracted.experiencer,
                    confidence=extracted.confidence,
                )
                mention_records.append(mention)
                session.add(mention)

                # Store direct concept_id if available from vocabulary
                if extracted.omop_concept_id and extracted.omop_concept_id > 0:
                    # We'll map by index since mention.id isn't assigned yet
                    direct_concept_map[len(mention_records) - 1] = (
                        extracted.omop_concept_id,
                        extracted.domain_hint or "Observation"
                    )

            session.flush()  # Assign IDs to mentions

            # Update direct_concept_map with actual mention IDs
            mention_direct_concepts: dict[str, tuple[int, str]] = {}
            for idx, (concept_id, domain) in direct_concept_map.items():
                mention_id = mention_records[idx].id
                mention_direct_concepts[mention_id] = (concept_id, domain)

            # Phase 5: Map mentions to OMOP concepts
            mapping_service = get_mapping_service(session)
            candidate_count = 0

            for mention in mention_records:
                # Check if we have a direct concept_id from vocabulary
                if mention.id in mention_direct_concepts:
                    concept_id, domain = mention_direct_concepts[mention.id]
                    # Create a high-priority candidate with the direct concept
                    # Convert domain to lowercase to match database enum
                    concept_candidate = MentionConceptCandidate(
                        mention_id=mention.id,
                        omop_concept_id=concept_id,
                        concept_name=mention.text,  # Use original text
                        concept_code=str(concept_id),
                        vocabulary_id="Direct",
                        domain_id=domain.lower() if domain else "observation",
                        score=1.0,  # Perfect score for direct match
                        method="direct",
                        rank=1,
                    )
                    session.add(concept_candidate)
                    candidate_count += 1
                else:
                    # Fall back to mapping service
                    candidates = mapping_service.map_mention(
                        text=mention.text,
                        domain=None,  # Allow any domain
                        limit=5,  # Top 5 candidates per mention
                    )

                    for candidate in candidates:
                        concept_candidate = MentionConceptCandidate(
                            mention_id=mention.id,
                            omop_concept_id=candidate.omop_concept_id,
                            concept_name=candidate.concept_name,
                            concept_code=candidate.concept_code,
                            vocabulary_id=candidate.vocabulary_id,
                            domain_id=candidate.domain_id,
                            score=candidate.score,
                            method=candidate.method.value,
                            rank=candidate.rank,
                        )
                        session.add(concept_candidate)
                        candidate_count += 1

            logger.info(
                f"Created {candidate_count} concept candidates for {len(mention_records)} mentions"
            )

            # Phase 6: Create ClinicalFacts from mentions with mapped concepts
            # Batch fetch top candidates for all mentions in one query
            fact_builder = DatabaseFactBuilderService(session)
            fact_count = 0

            mention_ids = [m.id for m in mention_records]
            if mention_ids:
                # Use a window function to get rank-1 candidates in one query
                from sqlalchemy import func as sa_func
                from sqlalchemy.orm import aliased

                ranked_subq = (
                    select(
                        MentionConceptCandidate,
                        sa_func.row_number()
                        .over(
                            partition_by=MentionConceptCandidate.mention_id,
                            order_by=MentionConceptCandidate.rank.asc(),
                        )
                        .label("rn"),
                    )
                    .where(MentionConceptCandidate.mention_id.in_(mention_ids))
                    .subquery()
                )
                top_candidates_stmt = (
                    select(ranked_subq)
                    .where(ranked_subq.c.rn == 1)
                )
                top_results = session.execute(top_candidates_stmt)
                # Build lookup: mention_id -> candidate row
                candidate_map: dict[str, object] = {}
                for row in top_results:
                    candidate_map[row.mention_id] = row

                for mention in mention_records:
                    top_candidate = candidate_map.get(mention.id)
                    if top_candidate is None:
                        continue

                    fact_builder.create_fact_from_mention(
                        mention_id=UUID(mention.id),
                        patient_id=document.patient_id,
                        omop_concept_id=top_candidate.omop_concept_id,
                        concept_name=top_candidate.concept_name,
                        domain=map_domain_id(top_candidate.domain_id),
                        assertion=map_assertion(mention.assertion),
                        temporality=map_temporality(mention.temporality),
                        experiencer=map_experiencer(mention.experiencer),
                        confidence=mention.confidence,
                    )
                    fact_count += 1

            logger.info(f"Created {fact_count} clinical facts from mentions")

            # Phase 7: Enqueue knowledge graph building (runs in background)
            graph_nodes_created = 0
            graph_edges_created = 0
            if fact_count > 0:
                try:
                    from app.core.queue import enqueue_job
                    from app.jobs.graph_building import build_graph_for_patient_job

                    enqueue_job(
                        build_graph_for_patient_job,
                        document.patient_id,
                        queue_name="graph_building",
                    )
                    logger.info(f"Enqueued graph building for patient {document.patient_id}")
                except Exception as e:
                    logger.warning(f"Failed to enqueue graph building: {e}")

            # Update status to COMPLETED
            session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    status=JobStatus.COMPLETED,
                    processed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

            # VP-Caching-1: Invalidate cache after creating new facts
            if fact_count > 0 and document.patient_id:
                try:
                    cache_service = get_kg_cache_service()
                    invalidated = cache_service.invalidate_patient(document.patient_id)
                    if invalidated > 0:
                        logger.info(
                            f"Invalidated {invalidated} cache entries for patient_id={document.patient_id}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to invalidate cache for patient_id={document.patient_id}: {e}"
                    )

            logger.info(
                f"Document processing completed for document_id={document_id}, "
                f"mention_count={len(mention_records)}, "
                f"candidate_count={candidate_count}"
            )

            # P0-014: Audit completion of worker PHI processing
            log_audit(
                action=AuditAction.CREATE,
                resource_type="document",
                resource_id=document_id,
                patient_id=document.patient_id,
                user_id="worker:document_processing",
                details={
                    "stage": "completed",
                    "mention_count": len(mention_records),
                    "fact_count": fact_count,
                    "graph_nodes_created": graph_nodes_created,
                },
            )

            return {
                "success": True,
                "document_id": document_id,
                "patient_id": document.patient_id,
                "mention_count": len(mention_records),
                "candidate_count": candidate_count,
                "fact_count": fact_count,
                "graph_nodes_created": graph_nodes_created,
                "graph_edges_created": graph_edges_created,
            }

    except Exception as e:
        logger.exception(f"Error processing document {document_id}: {e}")

        # P0-014: Audit worker PHI processing failure
        log_audit(
            action=AuditAction.ERROR,
            resource_type="document",
            resource_id=document_id,
            user_id="worker:document_processing",
            details={"stage": "failed", "error": str(e)[:500]},
            success=False,
        )

        # Try to update status to FAILED
        try:
            with Session(get_sync_engine()) as session:
                session.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status=JobStatus.FAILED)
                )
                session.commit()
        except Exception:
            logger.exception("Failed to update document status to FAILED")

        return {"success": False, "error": str(e)}
