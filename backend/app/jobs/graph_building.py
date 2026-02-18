"""Graph building job function for background processing with RQ.

Decouples knowledge graph construction from document processing,
allowing graph builds to run asynchronously in a dedicated queue.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.audit import AuditAction, log_audit
from app.core.database import get_sync_engine
from app.services.graph_builder_db import DatabaseGraphBuilderService
from app.services.kg_cache_service import get_kg_cache_service

logger = logging.getLogger(__name__)


def build_graph_for_patient_job(patient_id: str) -> dict:
    """Build the knowledge graph for a patient in a background job.

    Opens its own database session, builds the graph, and invalidates
    the KG cache afterward.

    Args:
        patient_id: The patient identifier to build the graph for.

    Returns:
        Dictionary with build results including node/edge counts.
    """
    logger.info(f"Starting graph building job for patient_id={patient_id}")

    log_audit(
        action=AuditAction.CREATE,
        resource_type="knowledge_graph",
        resource_id=patient_id,
        user_id="worker:graph_building",
        details={"stage": "start"},
    )

    try:
        engine = get_sync_engine()
        with Session(engine) as session:
            graph_builder = DatabaseGraphBuilderService(session)
            graph_result = graph_builder.build_graph_for_patient(patient_id)
            session.commit()

            logger.info(
                f"Built knowledge graph for patient {patient_id}: "
                f"{graph_result.nodes_created} nodes, {graph_result.edges_created} edges"
            )

        # Invalidate KG cache after successful build
        try:
            cache_service = get_kg_cache_service()
            invalidated = cache_service.invalidate_patient(patient_id)
            if invalidated > 0:
                logger.info(
                    f"Invalidated {invalidated} cache entries for patient_id={patient_id}"
                )
        except Exception as e:
            logger.warning(
                f"Failed to invalidate cache for patient_id={patient_id}: {e}"
            )

        log_audit(
            action=AuditAction.CREATE,
            resource_type="knowledge_graph",
            resource_id=patient_id,
            user_id="worker:graph_building",
            details={
                "stage": "completed",
                "nodes_created": graph_result.nodes_created,
                "edges_created": graph_result.edges_created,
                "node_count": graph_result.node_count,
                "edge_count": graph_result.edge_count,
            },
        )

        return {
            "success": True,
            "patient_id": patient_id,
            "nodes_created": graph_result.nodes_created,
            "edges_created": graph_result.edges_created,
            "node_count": graph_result.node_count,
            "edge_count": graph_result.edge_count,
        }

    except Exception as e:
        logger.exception(f"Error building graph for patient {patient_id}: {e}")

        log_audit(
            action=AuditAction.ERROR,
            resource_type="knowledge_graph",
            resource_id=patient_id,
            user_id="worker:graph_building",
            details={"stage": "failed", "error": str(e)[:500]},
            success=False,
        )

        return {"success": False, "patient_id": patient_id, "error": str(e)}
