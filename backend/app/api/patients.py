"""Patient API endpoints.

VP-Compliance-1: All PHI access is logged for HIPAA compliance.
"""

import logging
from datetime import datetime, UTC
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.errors import ErrorCode, NotFoundError
from app.api.middleware.auth_middleware import CurrentUser, get_current_user
from app.core.audit import log_data_access, AuditAction
from app.core.database import get_sync_engine
from app.models.clinical_fact import ClinicalFact as ClinicalFactModel
from app.models.knowledge_graph import KGNode, KGEdge
from app.schemas import ClinicalFact
from app.schemas.base import Assertion, Domain
from app.schemas.knowledge_graph import PatientGraph, KGNode as KGNodeSchema, KGEdge as KGEdgeSchema, NodeType, EdgeType
from app.services.graph_builder_db import DatabaseGraphBuilderService
from app.services.kg_cache_service import get_kg_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get(
    "/{patient_id}/graph",
    response_model=PatientGraph,
    summary="Get patient knowledge graph",
    description="Retrieve the complete knowledge graph for a patient, including all nodes and edges.",
)
def get_patient_graph(
    patient_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> PatientGraph:
    """Get the complete knowledge graph for a patient.

    This endpoint builds or retrieves the patient's knowledge graph,
    which contains:
    - A central patient node
    - Nodes for conditions, drugs, measurements, procedures
    - Edges connecting the patient to clinical facts

    Args:
        patient_id: The patient identifier.
        current_user: Authenticated user (injected).

    Returns:
        PatientGraph with all nodes and edges.

    Raises:
        HTTPException: 404 if patient has no data.
    """
    # VP-Compliance-1: Log PHI access for HIPAA compliance
    log_data_access(
        resource_type="patient_graph",
        resource_id=patient_id,
        patient_id=patient_id,
        user_id=current_user.id,
        action=AuditAction.READ,
    )

    logger.info(f"Getting knowledge graph for patient_id={patient_id} by user={current_user.id}")

    with Session(get_sync_engine()) as session:
        # Direct query for nodes
        node_stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        node_result = session.execute(node_stmt)
        db_nodes = node_result.scalars().all()

        if not db_nodes:
            # Check if there are any facts we could build from
            facts_exist = (
                session.execute(
                    select(ClinicalFactModel).where(ClinicalFactModel.patient_id == patient_id).limit(1)
                )
                .scalars()
                .first()
            )

            if facts_exist is None:
                raise NotFoundError(
                    message=f"No data found for patient '{patient_id}'",
                    error_code=ErrorCode.NOT_FOUND_PATIENT,
                )

            # Build graph from facts using service
            logger.info(f"Building knowledge graph for patient_id={patient_id}")
            graph_service = DatabaseGraphBuilderService(session)
            graph_service.build_graph_for_patient(patient_id)
            session.commit()

            # VP-Caching-1: Invalidate cache after graph build
            try:
                cache_service = get_kg_cache_service()
                invalidated = cache_service.invalidate_patient(patient_id)
                if invalidated > 0:
                    logger.info(f"Invalidated {invalidated} cache entries for patient_id={patient_id}")
            except Exception as e:
                logger.warning(f"Failed to invalidate cache for patient_id={patient_id}: {e}")

            # Re-query after building
            node_result = session.execute(node_stmt)
            db_nodes = node_result.scalars().all()

        # Direct query for edges
        edge_stmt = select(KGEdge).where(KGEdge.patient_id == patient_id)
        edge_result = session.execute(edge_stmt)
        db_edges = edge_result.scalars().all()

        # Convert to schema objects
        nodes = [
            KGNodeSchema(
                id=UUID(n.id) if isinstance(n.id, str) else n.id,
                patient_id=n.patient_id,
                node_type=NodeType(n.node_type) if isinstance(n.node_type, str) else n.node_type,
                omop_concept_id=n.omop_concept_id,
                label=n.label,
                properties=n.properties or {},
                created_at=n.created_at,
            )
            for n in db_nodes
        ]

        edges = [
            KGEdgeSchema(
                id=UUID(e.id) if isinstance(e.id, str) else e.id,
                patient_id=e.patient_id,
                source_node_id=UUID(e.source_node_id) if isinstance(e.source_node_id, str) else e.source_node_id,
                target_node_id=UUID(e.target_node_id) if isinstance(e.target_node_id, str) else e.target_node_id,
                edge_type=EdgeType(e.edge_type) if isinstance(e.edge_type, str) else e.edge_type,
                fact_id=UUID(e.fact_id) if e.fact_id and isinstance(e.fact_id, str) else e.fact_id,
                properties=e.properties or {},
                created_at=e.created_at,
            )
            for e in db_edges
        ]

        patient_graph = PatientGraph(
            patient_id=patient_id,
            nodes=nodes,
            edges=edges,
        )

        logger.info(
            f"Retrieved graph for patient_id={patient_id}: "
            f"nodes={patient_graph.node_count}, edges={patient_graph.edge_count}"
        )

        return patient_graph


@router.post(
    "/{patient_id}/graph/build",
    response_model=PatientGraph,
    status_code=status.HTTP_201_CREATED,
    summary="Build patient knowledge graph",
    description="Build or rebuild the knowledge graph for a patient from their clinical facts.",
)
def build_patient_graph(
    patient_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> PatientGraph:
    """Build the knowledge graph for a patient from clinical facts.

    This endpoint forces a rebuild of the patient's knowledge graph,
    projecting all clinical facts into nodes and edges.

    Args:
        patient_id: The patient identifier.
        current_user: Authenticated user (injected).

    Returns:
        PatientGraph with all nodes and edges.

    Raises:
        HTTPException: 404 if patient has no clinical facts.
    """
    # VP-Compliance-1: Log PHI access for HIPAA compliance
    log_data_access(
        resource_type="patient_graph",
        resource_id=patient_id,
        patient_id=patient_id,
        user_id=current_user.id,
        action=AuditAction.CREATE,
    )

    logger.info(f"Building knowledge graph for patient_id={patient_id} by user={current_user.id}")

    with Session(get_sync_engine()) as session:
        # Check if patient has any facts
        facts_exist = (
            session.execute(
                select(ClinicalFactModel).where(ClinicalFactModel.patient_id == patient_id).limit(1)
            )
            .scalars()
            .first()
        )

        if facts_exist is None:
            raise NotFoundError(
                message=f"No clinical facts found for patient '{patient_id}'",
                error_code=ErrorCode.NOT_FOUND_PATIENT,
            )

        graph_service = DatabaseGraphBuilderService(session)

        # Build the graph
        result = graph_service.build_graph_for_patient(patient_id)
        session.commit()

        # VP-Caching-1: Invalidate cache after graph rebuild
        try:
            cache_service = get_kg_cache_service()
            invalidated = cache_service.invalidate_patient(patient_id)
            if invalidated > 0:
                logger.info(f"Invalidated {invalidated} cache entries for patient_id={patient_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for patient_id={patient_id}: {e}")

        logger.info(
            f"Built graph for patient_id={patient_id}: "
            f"nodes_created={result.nodes_created}, edges_created={result.edges_created}"
        )

        # Return the complete graph
        return graph_service.get_patient_graph(patient_id)


@router.get(
    "/{patient_id}/facts",
    response_model=list[ClinicalFact],
    summary="Get patient clinical facts",
    description="Retrieve all clinical facts for a patient, with optional filtering.",
)
def get_patient_facts(
    patient_id: str,
    domain: Annotated[Domain | None, Query(description="Filter by domain")] = None,
    assertion: Annotated[Assertion | None, Query(description="Filter by assertion")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Max facts to return")] = 100,
    offset: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ClinicalFact]:
    """Get clinical facts for a patient.

    Returns all clinical facts associated with the patient, with optional
    filtering by domain and/or assertion status.

    Args:
        patient_id: The patient identifier.
        domain: Optional filter by OMOP domain.
        assertion: Optional filter by assertion status.
        limit: Maximum number of facts to return.
        offset: Pagination offset.
        current_user: Authenticated user (injected).

    Returns:
        List of ClinicalFact objects.

    Raises:
        HTTPException: 404 if patient has no facts.
    """
    # VP-Compliance-1: Log PHI access for HIPAA compliance
    log_data_access(
        resource_type="patient_facts",
        resource_id=patient_id,
        patient_id=patient_id,
        user_id=current_user.id,
        action=AuditAction.READ,
    )

    logger.info(f"Getting clinical facts for patient_id={patient_id} by user={current_user.id}")

    with Session(get_sync_engine()) as session:
        # Build query
        stmt = select(ClinicalFactModel).where(ClinicalFactModel.patient_id == patient_id)

        if domain is not None:
            stmt = stmt.where(ClinicalFactModel.domain == domain)
        if assertion is not None:
            stmt = stmt.where(ClinicalFactModel.assertion == assertion)

        # Add ordering and pagination
        stmt = stmt.order_by(ClinicalFactModel.created_at.desc()).offset(offset).limit(limit)

        result = session.execute(stmt)
        facts = result.scalars().all()

        if not facts and offset == 0:
            # Check if patient exists at all
            count_stmt = (
                select(func.count())
                .select_from(ClinicalFactModel)
                .where(ClinicalFactModel.patient_id == patient_id)
            )
            total = session.execute(count_stmt).scalar()
            if total == 0:
                raise NotFoundError(
                    message=f"No clinical facts found for patient '{patient_id}'",
                    error_code=ErrorCode.NOT_FOUND_PATIENT,
                )

        logger.info(f"Found {len(facts)} clinical facts for patient_id={patient_id}")

        return [ClinicalFact.model_validate(f) for f in facts]
