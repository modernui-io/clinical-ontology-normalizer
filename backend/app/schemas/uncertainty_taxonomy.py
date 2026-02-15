"""P2-007: Uncertainty taxonomy and reason codes for decline/degraded outputs.

Provides a structured vocabulary for communicating *why* a clinical agent
response was declined, degraded, or carries lower confidence. Each reason
code maps to a human-readable description and severity level so downstream
consumers (UIs, audit logs, escalation workflows) can act deterministically.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class UncertaintyCategory(str, Enum):
    """Top-level categories for uncertainty in clinical agent responses."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    STALE_DATA = "stale_data"
    MODEL_LIMITATION = "model_limitation"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    SCOPE_EXCEEDED = "scope_exceeded"


class UncertaintyReason(BaseModel):
    """A single reason code describing why a response carries uncertainty."""

    category: UncertaintyCategory
    code: str = Field(..., pattern=r"^UC-\d{3}$", description="Reason code e.g. UC-001")
    description: str
    severity: Literal["info", "warning", "error"]


# ---------------------------------------------------------------------------
# Canonical reason catalog
# ---------------------------------------------------------------------------

REASON_CATALOG: dict[str, UncertaintyReason] = {
    "UC-001": UncertaintyReason(
        category=UncertaintyCategory.INSUFFICIENT_EVIDENCE,
        code="UC-001",
        description="No matching clinical documents found for the query.",
        severity="error",
    ),
    "UC-002": UncertaintyReason(
        category=UncertaintyCategory.INSUFFICIENT_EVIDENCE,
        code="UC-002",
        description="No knowledge graph entities matched the query.",
        severity="error",
    ),
    "UC-003": UncertaintyReason(
        category=UncertaintyCategory.LOW_CONFIDENCE,
        code="UC-003",
        description="Aggregate confidence is below the safety threshold (0.3).",
        severity="error",
    ),
    "UC-004": UncertaintyReason(
        category=UncertaintyCategory.CONFLICTING_EVIDENCE,
        code="UC-004",
        description="Evidence sources present contradictory clinical findings.",
        severity="warning",
    ),
    "UC-005": UncertaintyReason(
        category=UncertaintyCategory.STALE_DATA,
        code="UC-005",
        description="Most recent clinical data is older than 90 days.",
        severity="warning",
    ),
    "UC-006": UncertaintyReason(
        category=UncertaintyCategory.MODEL_LIMITATION,
        code="UC-006",
        description="LLM reasoning was unavailable; rule-based fallback was used.",
        severity="warning",
    ),
    "UC-007": UncertaintyReason(
        category=UncertaintyCategory.DEPENDENCY_UNAVAILABLE,
        code="UC-007",
        description="Knowledge graph service was unreachable.",
        severity="warning",
    ),
    "UC-008": UncertaintyReason(
        category=UncertaintyCategory.DEPENDENCY_UNAVAILABLE,
        code="UC-008",
        description="Document store was unreachable.",
        severity="warning",
    ),
    "UC-009": UncertaintyReason(
        category=UncertaintyCategory.SCOPE_EXCEEDED,
        code="UC-009",
        description="Query exceeds the scope of loaded clinical data for this patient.",
        severity="info",
    ),
    "UC-010": UncertaintyReason(
        category=UncertaintyCategory.LOW_CONFIDENCE,
        code="UC-010",
        description="Confidence is moderate (0.3-0.5); review recommended.",
        severity="info",
    ),
}


def get_uncertainty_reason(code: str) -> UncertaintyReason | None:
    """Look up a reason by its code. Returns None if not found."""
    return REASON_CATALOG.get(code)


def classify_uncertainty(
    confidence: float,
    evidence_count: int,
    kg_node_count: int,
    dependency_state: dict[str, bool] | None = None,
    fallback_used: bool = False,
) -> list[str]:
    """Return applicable uncertainty reason codes given query diagnostics.

    Parameters
    ----------
    confidence:
        Aggregate confidence score (0.0-1.0).
    evidence_count:
        Number of evidence sources (documents) found.
    kg_node_count:
        Number of knowledge-graph nodes matched.
    dependency_state:
        Dict with keys like ``kg_available``, ``documents_available``,
        ``llm_available`` mapped to booleans.
    fallback_used:
        True when a fallback path (e.g. rule-based) was used instead of the
        primary LLM reasoning path.
    """
    codes: list[str] = []
    dep = dependency_state or {}

    # Evidence gaps
    if evidence_count == 0:
        codes.append("UC-001")
    if kg_node_count == 0:
        codes.append("UC-002")

    # Confidence thresholds
    if confidence < 0.3:
        codes.append("UC-003")
    elif confidence < 0.5:
        codes.append("UC-010")

    # Dependency availability
    if not dep.get("kg_available", True):
        codes.append("UC-007")
    if not dep.get("documents_available", True):
        codes.append("UC-008")

    # Fallback / model limitation
    if fallback_used:
        codes.append("UC-006")

    return codes
