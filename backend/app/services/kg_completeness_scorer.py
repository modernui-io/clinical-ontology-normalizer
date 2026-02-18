"""KG Completeness Scorer (P2-006).

Evaluates the completeness of a patient knowledge graph by checking
which clinical data categories are present and computing a weighted
overall score.
"""
# MODULE: graph_analytics
# MATURITY: pilot

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Dimension weights for overall score computation
# ---------------------------------------------------------------------------

_DIMENSION_WEIGHTS: dict[str, float] = {
    "conditions": 0.25,
    "medications": 0.20,
    "labs": 0.20,
    "procedures": 0.15,
    "demographics": 0.20,
}

# Minimum counts for a "full" dimension score
_DIMENSION_THRESHOLDS: dict[str, int] = {
    "conditions": 3,
    "medications": 2,
    "labs": 3,
    "procedures": 1,
    "demographics": 2,
}

# Node types mapped to dimensions
_NODE_TYPE_TO_DIMENSION: dict[str, str] = {
    "condition": "conditions",
    "drug": "medications",
    "medication": "medications",
    "measurement": "labs",
    "lab": "labs",
    "procedure": "procedures",
    "demographic": "demographics",
    "patient": "demographics",
    "observation": "labs",
}


@dataclass
class KGCompletenessScore:
    """Result of a KG completeness evaluation."""

    overall_score: float
    dimensions: dict[str, float]
    missing_categories: list[str]
    data_quality_flags: list[str]
    category_counts: dict[str, int] = field(default_factory=dict)


def score_patient_graph(
    patient_id: str,
    kg_nodes: list[dict[str, Any]],
    kg_edges: list[dict[str, Any]],
) -> KGCompletenessScore:
    """Evaluate completeness of a patient knowledge graph.

    Args:
        patient_id: The patient identifier.
        kg_nodes: List of KG node dicts, each with at least a 'type' or
            'node_type' field and optionally a 'label' or 'name'.
        kg_edges: List of KG edge dicts (used for connectivity checks).

    Returns:
        KGCompletenessScore with per-dimension scores and actionable insights.
    """
    # Count nodes per dimension
    counts: dict[str, int] = {dim: 0 for dim in _DIMENSION_WEIGHTS}

    for node in kg_nodes:
        node_type = (
            node.get("type") or node.get("node_type") or ""
        ).lower().strip()
        dimension = _NODE_TYPE_TO_DIMENSION.get(node_type)
        if dimension and dimension in counts:
            counts[dimension] += 1

    # Score each dimension: 0-1 based on count vs threshold
    dimensions: dict[str, float] = {}
    for dim, threshold in _DIMENSION_THRESHOLDS.items():
        count = counts.get(dim, 0)
        if count == 0:
            dimensions[dim] = 0.0
        elif count >= threshold:
            dimensions[dim] = 1.0
        else:
            dimensions[dim] = round(count / threshold, 2)

    # Weighted overall score
    overall = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        overall += dimensions.get(dim, 0.0) * weight
    overall = round(overall, 2)

    # Missing categories
    missing: list[str] = []
    _MISSING_LABELS: dict[str, str] = {
        "conditions": "No conditions/diagnoses found",
        "medications": "Missing medication list",
        "labs": "No lab results found",
        "procedures": "No procedures documented",
        "demographics": "Incomplete demographics",
    }
    for dim, score in dimensions.items():
        if score == 0.0:
            missing.append(_MISSING_LABELS.get(dim, f"No {dim} data"))

    # Data quality flags
    flags: list[str] = []
    if not kg_nodes:
        flags.append("Empty knowledge graph -- no nodes present")
    if not kg_edges and len(kg_nodes) > 1:
        flags.append("No relationships between nodes -- graph is disconnected")
    if overall < 0.3:
        flags.append("Very low completeness -- clinical decisions may be unreliable")
    for dim, score in dimensions.items():
        if 0 < score < 0.5:
            flags.append(f"Sparse {dim} data -- only {counts.get(dim, 0)} item(s)")

    return KGCompletenessScore(
        overall_score=overall,
        dimensions=dimensions,
        missing_categories=missing,
        data_quality_flags=flags,
        category_counts=counts,
    )
