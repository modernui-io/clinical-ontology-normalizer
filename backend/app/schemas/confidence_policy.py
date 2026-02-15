"""Pydantic schemas for confidence-to-action policy gating (P0-021).

Defines risk tiers and confidence thresholds that prevent
low-confidence results from triggering high-risk clinical actions.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Action risk tiers ordered by increasing required confidence."""

    INFORMATIONAL = "informational"
    SUGGESTION = "suggestion"
    RECOMMENDATION = "recommendation"
    ACTION = "action"
    CRITICAL_ACTION = "critical_action"


# Default confidence thresholds per risk tier
DEFAULT_THRESHOLDS: dict[str, float] = {
    RiskTier.INFORMATIONAL: 0.0,
    RiskTier.SUGGESTION: 0.5,
    RiskTier.RECOMMENDATION: 0.7,
    RiskTier.ACTION: 0.85,
    RiskTier.CRITICAL_ACTION: 0.95,
}


class ConfidencePolicy(BaseModel):
    """Configurable confidence thresholds per risk tier."""

    thresholds: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_THRESHOLDS),
        description="Minimum confidence required per risk tier",
    )
    strict_mode: bool = Field(
        default=True,
        description="When True, low-confidence actions are blocked; when False, they are warned",
    )


class ActionGateResult(BaseModel):
    """Result of checking a confidence score against a risk tier."""

    allowed: bool = Field(
        ..., description="Whether the action is permitted at this confidence level"
    )
    risk_tier: str = Field(
        ..., description="The risk tier that was evaluated"
    )
    required_confidence: float = Field(
        ..., description="Minimum confidence required for this tier"
    )
    actual_confidence: float = Field(
        ..., description="The actual confidence score that was checked"
    )
    message: str = Field(
        default="", description="Human-readable explanation of the gate decision"
    )
