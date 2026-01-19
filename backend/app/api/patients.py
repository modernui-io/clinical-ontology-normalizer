"""Patient API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ErrorCode, NotFoundError
from app.core.database import get_sync_engine
from app.models.clinical_fact import ClinicalFact as ClinicalFactModel
from app.models.knowledge_graph import KGNode
from app.schemas import ClinicalFact
from app.schemas.base import Assertion, Domain
from app.schemas.knowledge_graph import PatientGraph
from app.services.graph_builder_db import DatabaseGraphBuilderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get(
    "/{patient_id}/graph",
    response_model=PatientGraph,
    summary="Get patient knowledge graph",
    description="Retrieve the complete knowledge graph for a patient, including all nodes and edges.",
)
def get_patient_graph(patient_id: str) -> PatientGraph:
    """Get the complete knowledge graph for a patient.

    This endpoint builds or retrieves the patient's knowledge graph,
    which contains:
    - A central patient node
    - Nodes for conditions, drugs, measurements, procedures
    - Edges connecting the patient to clinical facts

    Args:
        patient_id: The patient identifier.

    Returns:
        PatientGraph with all nodes and edges.

    Raises:
        HTTPException: 404 if patient has no data.
    """
    logger.info(f"Getting knowledge graph for patient_id={patient_id}")

    with Session(get_sync_engine()) as session:
        graph_service = DatabaseGraphBuilderService(session)

        # Check if patient has any data
        existing_nodes = (
            session.execute(select(KGNode).where(KGNode.patient_id == patient_id).limit(1))
            .scalars()
            .first()
        )

        # If no nodes exist, check if there are any facts and build the graph
        if existing_nodes is None:
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

            # Build graph from facts
            logger.info(f"Building knowledge graph for patient_id={patient_id}")
            graph_service.build_graph_for_patient(patient_id)
            session.commit()

        # Get the complete graph
        patient_graph = graph_service.get_patient_graph(patient_id)

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
def build_patient_graph(patient_id: str) -> PatientGraph:
    """Build the knowledge graph for a patient from clinical facts.

    This endpoint forces a rebuild of the patient's knowledge graph,
    projecting all clinical facts into nodes and edges.

    Args:
        patient_id: The patient identifier.

    Returns:
        PatientGraph with all nodes and edges.

    Raises:
        HTTPException: 404 if patient has no clinical facts.
    """
    logger.info(f"Building knowledge graph for patient_id={patient_id}")

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

    Returns:
        List of ClinicalFact objects.

    Raises:
        HTTPException: 404 if patient has no facts.
    """
    logger.info(f"Getting clinical facts for patient_id={patient_id}")

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
