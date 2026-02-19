"""Patient API endpoints.

VP-Compliance-1: All PHI access is logged for HIPAA compliance.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.errors import ErrorCode, NotFoundError
from app.api.middleware.auth_middleware import CurrentUser, get_current_user
from app.core.audit import log_data_access, AuditAction
from app.core.database import get_sync_engine
from app.core.permissions import Permission, PermissionChecker
from app.models.clinical_fact import ClinicalFact as ClinicalFactModel
from app.models.knowledge_graph import KGNode, KGEdge
from app.schemas import ClinicalFact
from app.schemas.base import Assertion, Domain
from app.schemas.knowledge_graph import PatientGraph, KGNode as KGNodeSchema, KGEdge as KGEdgeSchema, NodeType, EdgeType
from app.services.graph_builder_db import DatabaseGraphBuilderService
from app.services.kg_cache_service import get_kg_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


# ---------------------------------------------------------------------------
# Pydantic response models for patient listing
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class PatientSummary(BaseModel):
    """Summary info for a single patient in the browse list."""
    id: str = Field(..., description="Patient ID")
    external_id: str = Field("", description="External / MRN identifier")
    name: str = Field("", description="Patient display name")
    gender: str = Field("", description="Gender")
    birth_date: str = Field("", description="Date of birth")
    created_at: str = Field("", description="When the patient record was created")
    fact_count: int = Field(0, description="Number of clinical facts")
    node_count: int = Field(0, description="Number of KG nodes")
    conditions: list[str] = Field(default_factory=list, description="Top condition labels")
    medications: list[str] = Field(default_factory=list, description="Top medication labels")


class PatientListResponse(BaseModel):
    """Paginated list of patients."""
    patients: list[PatientSummary] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


@router.get(
    "",
    response_model=PatientListResponse,
    summary="List all patients",
    description="Browse all patients that have clinical data, with summary info.",
)
def list_patients(

    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_PATIENTS])),
) -> PatientListResponse:
    """Return a paginated list of patients with summary information.

    Queries kg_nodes for patient nodes and enriches with fact counts and
    top conditions/medications.
    """
    log_data_access(
        resource_type="patient_list",
        resource_id="*",
        patient_id="*",
        user_id=current_user.id,
        action=AuditAction.READ,
    )

    with Session(get_sync_engine()) as session:
        # ---- total distinct patients ----
        total_q = (
            select(func.count(func.distinct(KGNode.patient_id)))
            .where(KGNode.node_type == NodeType.PATIENT.value)
            .where(KGNode.deleted_at.is_(None))
        )
        total: int = session.execute(total_q).scalar() or 0

        # ---- patient nodes (paginated) ----
        offset = (page - 1) * page_size
        patient_nodes_q = (
            select(KGNode)
            .where(KGNode.node_type == NodeType.PATIENT.value)
            .where(KGNode.deleted_at.is_(None))
            .order_by(KGNode.patient_id)
            .offset(offset)
            .limit(page_size)
        )
        patient_nodes = session.execute(patient_nodes_q).scalars().all()

        patient_ids = [n.patient_id for n in patient_nodes]

        if not patient_ids:
            return PatientListResponse(patients=[], total=total, page=page, page_size=page_size)

        # ---- fact counts per patient ----
        fact_counts_q = (
            select(
                ClinicalFactModel.patient_id,
                func.count(ClinicalFactModel.id).label("cnt"),
            )
            .where(ClinicalFactModel.patient_id.in_(patient_ids))
            .group_by(ClinicalFactModel.patient_id)
        )
        fact_counts = {row.patient_id: row.cnt for row in session.execute(fact_counts_q)}

        # ---- node counts per patient ----
        node_counts_q = (
            select(
                KGNode.patient_id,
                func.count(KGNode.id).label("cnt"),
            )
            .where(KGNode.patient_id.in_(patient_ids))
            .where(KGNode.deleted_at.is_(None))
            .group_by(KGNode.patient_id)
        )
        node_counts = {row.patient_id: row.cnt for row in session.execute(node_counts_q)}

        # ---- condition labels per patient (top 5) ----
        condition_nodes_q = (
            select(KGNode.patient_id, KGNode.label)
            .where(KGNode.patient_id.in_(patient_ids))
            .where(KGNode.node_type == NodeType.CONDITION.value)
            .where(KGNode.deleted_at.is_(None))
        )
        conditions_map: dict[str, list[str]] = {}
        for row in session.execute(condition_nodes_q):
            conditions_map.setdefault(row.patient_id, []).append(row.label)
        # Limit to 5
        for pid in conditions_map:
            conditions_map[pid] = conditions_map[pid][:5]

        # ---- drug labels per patient (top 5) ----
        drug_nodes_q = (
            select(KGNode.patient_id, KGNode.label)
            .where(KGNode.patient_id.in_(patient_ids))
            .where(KGNode.node_type == NodeType.DRUG.value)
            .where(KGNode.deleted_at.is_(None))
        )
        drugs_map: dict[str, list[str]] = {}
        for row in session.execute(drug_nodes_q):
            drugs_map.setdefault(row.patient_id, []).append(row.label)
        for pid in drugs_map:
            drugs_map[pid] = drugs_map[pid][:5]

        # ---- build summaries ----
        summaries: list[PatientSummary] = []
        for pn in patient_nodes:
            props = pn.properties or {}
            summaries.append(
                PatientSummary(
                    id=pn.patient_id,
                    external_id=props.get("mrn") or props.get("fhir_id") or "",
                    name=pn.label,
                    gender=props.get("gender", ""),
                    birth_date=props.get("birth_date", ""),
                    created_at=pn.created_at.isoformat() if pn.created_at else "",
                    fact_count=fact_counts.get(pn.patient_id, 0),
                    node_count=node_counts.get(pn.patient_id, 0),
                    conditions=conditions_map.get(pn.patient_id, []),
                    medications=drugs_map.get(pn.patient_id, []),
                )
            )

        return PatientListResponse(
            patients=summaries,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get(
    "/{patient_id}/graph",
    response_model=PatientGraph,
    summary="Get patient knowledge graph",
    description="Retrieve the complete knowledge graph for a patient, including all nodes and edges.",
)
def get_patient_graph(
    patient_id: str,

    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_PATIENTS])),
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
        # Query patient-owned nodes first (to check if graph exists)
        node_stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        node_result = session.execute(node_stmt)
        db_patient_nodes = node_result.scalars().all()

        if not db_patient_nodes:
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
            db_patient_nodes = node_result.scalars().all()

        # Query edges for this patient
        edge_stmt = select(KGEdge).where(KGEdge.patient_id == patient_id)
        edge_result = session.execute(edge_stmt)
        db_edges = edge_result.scalars().all()

        # Collect all node IDs referenced by edges (includes shared concept nodes)
        referenced_node_ids = set()
        for e in db_edges:
            referenced_node_ids.add(str(e.source_node_id))
            referenced_node_ids.add(str(e.target_node_id))

        # Also include patient-owned node IDs
        patient_node_ids = {str(n.id) for n in db_patient_nodes}
        missing_node_ids = referenced_node_ids - patient_node_ids

        # Fetch shared concept nodes referenced by edges but not owned by patient
        db_shared_nodes = []
        if missing_node_ids:
            shared_stmt = select(KGNode).where(KGNode.id.in_(list(missing_node_ids)))
            shared_result = session.execute(shared_stmt)
            db_shared_nodes = shared_result.scalars().all()

        db_nodes = list(db_patient_nodes) + list(db_shared_nodes)

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
    _perm: None = Depends(PermissionChecker([Permission.WRITE_PATIENTS])),
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
    _perm: None = Depends(PermissionChecker([Permission.READ_CLINICAL_FACTS])),
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
