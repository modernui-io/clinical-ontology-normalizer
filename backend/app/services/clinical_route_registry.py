"""Clinical Route Registry (P3-001).

Centralises the status of every clinical API route so operators and
consumers can discover which paths are canonical, deprecated, or
experimental.  The registry is queried by middleware to inject the
``X-Route-Status`` response header on every clinical response.
"""

from __future__ import annotations

from enum import Enum
from typing import Sequence

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Route status enum
# ---------------------------------------------------------------------------

class RouteStatus(str, Enum):
    """Lifecycle status of a clinical API route."""

    CANONICAL = "canonical"
    DEPRECATED = "deprecated"
    SHADOW = "shadow"
    EXPERIMENTAL = "experimental"


# ---------------------------------------------------------------------------
# Route descriptor
# ---------------------------------------------------------------------------

class ClinicalRoute(BaseModel):
    """Metadata for a single clinical API route."""

    path: str = Field(..., description="Full route path including prefix")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    status: RouteStatus = Field(..., description="Lifecycle status")
    replacement_path: str | None = Field(
        None,
        description="Canonical replacement path (set when status is deprecated)",
    )
    description: str = Field("", description="Human-readable description")


# ---------------------------------------------------------------------------
# Static registry
# ---------------------------------------------------------------------------

_REGISTRY: list[ClinicalRoute] = [
    # ---- canonical: /api/v1/clinical-agent ----
    ClinicalRoute(
        path="/api/v1/clinical-agent/import",
        method="POST",
        status=RouteStatus.CANONICAL,
        description="Bulk import clinical documents with NLP processing",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/build-graph",
        method="POST",
        status=RouteStatus.CANONICAL,
        description="Build knowledge graph from pre-extracted entities",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/graph/{patient_id}",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="Get patient knowledge graph",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/query/{patient_id}",
        method="POST",
        status=RouteStatus.CANONICAL,
        description="Hybrid query combining EHR data and knowledge graph",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/graph/{patient_id}",
        method="DELETE",
        status=RouteStatus.CANONICAL,
        description="Delete patient knowledge graph",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/patients",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="List patients with knowledge graphs",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/provenance/{query_id}",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="Get provenance for a query",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/lineage/{patient_id}/{node_id}",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="Get fact lineage for a KG node",
    ),
    ClinicalRoute(
        path="/api/v1/clinical-agent/provenance-chain/{query_id}",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="Get full provenance chain for a query",
    ),

    # ---- deprecated: /api/v1/nlp ----
    ClinicalRoute(
        path="/api/v1/nlp/extract",
        method="POST",
        status=RouteStatus.DEPRECATED,
        replacement_path="/api/v1/clinical-agent/import",
        description="Extract entities from clinical text (deprecated)",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/extract/batch",
        method="POST",
        status=RouteStatus.DEPRECATED,
        replacement_path="/api/v1/clinical-agent/import",
        description="Batch extract entities (deprecated)",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/build-graph",
        method="POST",
        status=RouteStatus.DEPRECATED,
        replacement_path="/api/v1/clinical-agent/build-graph",
        description="Build knowledge graph from clinical text (deprecated)",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/batch-build-graph",
        method="POST",
        status=RouteStatus.DEPRECATED,
        replacement_path="/api/v1/clinical-agent/import",
        description="Batch build knowledge graph (deprecated)",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/analyze",
        method="POST",
        status=RouteStatus.DEPRECATED,
        replacement_path="/api/v1/clinical-agent/query/{patient_id}",
        description="Hybrid clinical analysis (deprecated)",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/ontology/map",
        method="POST",
        status=RouteStatus.DEPRECATED,
        replacement_path="/api/v1/clinical-agent/import",
        description="Ontology mapping (deprecated)",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/models",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="List available NLP models",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/normalize",
        method="POST",
        status=RouteStatus.CANONICAL,
        description="Normalize entities to standard codes",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/samples",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="Get sample clinical notes for testing",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/stats",
        method="GET",
        status=RouteStatus.CANONICAL,
        description="Get NLP service statistics",
    ),
    ClinicalRoute(
        path="/api/v1/nlp/preload",
        method="POST",
        status=RouteStatus.CANONICAL,
        description="Preload LLM model",
    ),
]


def get_route_registry() -> Sequence[ClinicalRoute]:
    """Return the full clinical route registry."""
    return list(_REGISTRY)


def is_canonical(path: str) -> bool:
    """Return True if *path* is a canonical clinical route."""
    for route in _REGISTRY:
        if route.path == path and route.status == RouteStatus.CANONICAL:
            return True
    return False


def get_route_status(path: str, method: str = "GET") -> RouteStatus | None:
    """Look up the status of a specific route + method pair.

    Returns ``None`` if the route is not in the registry.
    """
    method_upper = method.upper()
    for route in _REGISTRY:
        if route.path == path and route.method == method_upper:
            return route.status
    return None


def get_replacement_path(path: str, method: str = "GET") -> str | None:
    """Return the canonical replacement for a deprecated route, or None."""
    method_upper = method.upper()
    for route in _REGISTRY:
        if route.path == path and route.method == method_upper:
            return route.replacement_path
    return None
