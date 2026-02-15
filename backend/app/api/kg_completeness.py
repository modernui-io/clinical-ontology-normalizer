"""KG Completeness Scoring API (P2-006).

Exposes the KG completeness scorer as a REST endpoint so the frontend
can render per-patient chart coverage summaries.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.services.kg_completeness_scorer import (
    KGCompletenessScore,
    score_patient_graph,
)

router = APIRouter(prefix="/kg/completeness", tags=["kg-completeness"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class KGNode(BaseModel):
    """Minimal KG node for completeness scoring."""

    type: str = Field(..., description="Node type, e.g. condition, drug, measurement")
    label: str | None = Field(None, description="Human-readable label")


class KGEdge(BaseModel):
    """Minimal KG edge for completeness scoring."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relation: str | None = Field(None, description="Edge relation type")


class CompletenessRequest(BaseModel):
    """Request body for scoring a patient graph."""

    patient_id: str = Field(..., description="Patient identifier")
    nodes: list[KGNode] = Field(default_factory=list)
    edges: list[KGEdge] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_id": "pt-001",
                "nodes": [
                    {"type": "condition", "label": "Type 2 Diabetes"},
                    {"type": "drug", "label": "Metformin"},
                    {"type": "measurement", "label": "HbA1c"},
                ],
                "edges": [
                    {"source": "pt-001", "target": "condition-1", "relation": "has_condition"},
                ],
            }
        }
    }


class CompletenessResponse(BaseModel):
    """Response body with completeness score details."""

    patient_id: str
    overall_score: float = Field(..., ge=0.0, le=1.0)
    dimensions: dict[str, float]
    missing_categories: list[str]
    data_quality_flags: list[str]
    category_counts: dict[str, int]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/score",
    response_model=CompletenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Score patient KG completeness",
    description="Evaluate how complete a patient knowledge graph is across clinical dimensions.",
)
def score_completeness(body: CompletenessRequest) -> CompletenessResponse:
    """Score the completeness of a patient knowledge graph."""
    nodes_dicts: list[dict[str, Any]] = [n.model_dump() for n in body.nodes]
    edges_dicts: list[dict[str, Any]] = [e.model_dump() for e in body.edges]

    result: KGCompletenessScore = score_patient_graph(
        patient_id=body.patient_id,
        kg_nodes=nodes_dicts,
        kg_edges=edges_dicts,
    )

    return CompletenessResponse(
        patient_id=body.patient_id,
        overall_score=result.overall_score,
        dimensions=result.dimensions,
        missing_categories=result.missing_categories,
        data_quality_flags=result.data_quality_flags,
        category_counts=result.category_counts,
    )
