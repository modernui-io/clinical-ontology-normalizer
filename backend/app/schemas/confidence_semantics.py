"""P1-002: Standardized confidence semantics schema.

Provides a structured breakdown of how confidence scores are computed
across extraction, knowledge graph, reasoning, and final aggregation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceSource(str, Enum):
    """Source type for a confidence component."""

    EXTRACTION = "extraction"
    KG = "kg"
    REASONING = "reasoning"
    FINAL = "final"


class ConfidenceComponent(BaseModel):
    """A single component contributing to the aggregate confidence score."""

    source: ConfidenceSource
    score: float = Field(ge=0.0, le=1.0, description="Raw score for this component")
    weight: float = Field(ge=0.0, le=1.0, description="Weight applied to this component")
    method: str = Field(description="How this score was derived, e.g. 'entity_count_heuristic'")


class ConfidenceBreakdown(BaseModel):
    """Full breakdown of confidence computation."""

    components: list[ConfidenceComponent]
    aggregate_score: float = Field(ge=0.0, le=1.0)
    aggregate_method: str = "weighted_mean"
