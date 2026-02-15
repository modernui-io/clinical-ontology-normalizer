"""Workflow-specific confidence threshold policies (P1-003).

Extends the base confidence policy (P0-021) with per-workflow-type
threshold overrides.  High-risk clinical workflows (e.g. medication review)
require higher confidence before actions are permitted, while low-risk
workflows (e.g. administrative queries) can accept lower confidence.

Environment:
    CONFIDENCE_POLICY_OVERRIDES: JSON string with per-workflow overrides.
        Example: '{"medication_review": {"action": 0.92}}'
"""

from __future__ import annotations

import json
import logging
import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.confidence_policy import DEFAULT_THRESHOLDS, ConfidencePolicy

logger = logging.getLogger(__name__)

_POLICY_VERSION = "1.0.0"


class WorkflowType(str, Enum):
    """Clinical workflow types with varying risk profiles."""

    MEDICATION_REVIEW = "medication_review"
    DIAGNOSIS_SUPPORT = "diagnosis_support"
    LAB_INTERPRETATION = "lab_interpretation"
    GENERAL_QUERY = "general_query"
    ADMINISTRATIVE = "administrative"


# Default threshold overrides per workflow type.
# Each dict maps risk-tier -> minimum confidence.
# Missing tiers fall back to the base DEFAULT_THRESHOLDS.
_WORKFLOW_DEFAULTS: dict[str, dict[str, float]] = {
    WorkflowType.MEDICATION_REVIEW: {
        "informational": 0.10,
        "suggestion": 0.65,
        "recommendation": 0.80,
        "action": 0.90,
        "critical_action": 0.97,
    },
    WorkflowType.DIAGNOSIS_SUPPORT: {
        "informational": 0.05,
        "suggestion": 0.55,
        "recommendation": 0.75,
        "action": 0.88,
        "critical_action": 0.96,
    },
    WorkflowType.LAB_INTERPRETATION: {
        "informational": 0.0,
        "suggestion": 0.50,
        "recommendation": 0.70,
        "action": 0.85,
        "critical_action": 0.95,
    },
    WorkflowType.GENERAL_QUERY: {
        "informational": 0.0,
        "suggestion": 0.35,
        "recommendation": 0.50,
        "action": 0.70,
        "critical_action": 0.85,
    },
    WorkflowType.ADMINISTRATIVE: {
        "informational": 0.0,
        "suggestion": 0.25,
        "recommendation": 0.40,
        "action": 0.60,
        "critical_action": 0.80,
    },
}


class WorkflowConfidencePolicy(BaseModel):
    """Per-workflow confidence threshold configuration."""

    workflow_type: str = Field(..., description="Workflow type this policy applies to")
    thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Risk-tier -> minimum confidence overrides",
    )
    strict_mode: bool = Field(
        default=True,
        description="Block (True) or warn (False) when below threshold",
    )

    def to_confidence_policy(self) -> ConfidencePolicy:
        """Convert to base ConfidencePolicy with merged thresholds."""
        merged = dict(DEFAULT_THRESHOLDS)
        merged.update(self.thresholds)
        return ConfidencePolicy(thresholds=merged, strict_mode=self.strict_mode)


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------
_cached_overrides: dict[str, dict[str, float]] | None = None


def _load_env_overrides() -> dict[str, dict[str, float]]:
    """Load custom threshold overrides from CONFIDENCE_POLICY_OVERRIDES env var.

    Expected format: JSON object mapping workflow type -> {risk_tier: threshold}.
    Returns empty dict on parse failure.
    """
    global _cached_overrides
    if _cached_overrides is not None:
        return _cached_overrides

    raw = os.environ.get("CONFIDENCE_POLICY_OVERRIDES", "").strip()
    if not raw:
        _cached_overrides = {}
        return _cached_overrides

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object at top level")
        # Validate structure
        result: dict[str, dict[str, float]] = {}
        for wf_key, tier_dict in parsed.items():
            if not isinstance(tier_dict, dict):
                logger.warning(
                    "CONFIDENCE_POLICY_OVERRIDES: skipping non-dict value for %s",
                    wf_key,
                )
                continue
            result[wf_key] = {
                str(k): float(v) for k, v in tier_dict.items()
            }
        _cached_overrides = result
        logger.info(
            "Loaded CONFIDENCE_POLICY_OVERRIDES for workflows: %s",
            list(result.keys()),
        )
        return _cached_overrides
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning(
            "Failed to parse CONFIDENCE_POLICY_OVERRIDES: %s", exc,
        )
        _cached_overrides = {}
        return _cached_overrides


def reset_overrides_cache() -> None:
    """Clear the cached overrides (for testing)."""
    global _cached_overrides
    _cached_overrides = None


def get_policy_for_workflow(
    workflow_type: str | WorkflowType,
    *,
    strict_mode: bool = True,
) -> WorkflowConfidencePolicy:
    """Build a WorkflowConfidencePolicy for the given workflow type.

    Resolution order for thresholds:
    1. Environment overrides (CONFIDENCE_POLICY_OVERRIDES)
    2. Built-in workflow defaults (_WORKFLOW_DEFAULTS)
    3. Base DEFAULT_THRESHOLDS

    Args:
        workflow_type: A WorkflowType value or string.
        strict_mode: Whether to block or warn on low confidence.

    Returns:
        WorkflowConfidencePolicy with fully-resolved thresholds.
    """
    wf_str = workflow_type.value if isinstance(workflow_type, WorkflowType) else str(workflow_type)

    # Start from base thresholds
    merged: dict[str, float] = dict(DEFAULT_THRESHOLDS)

    # Layer on workflow defaults
    wf_defaults = _WORKFLOW_DEFAULTS.get(wf_str, {})
    merged.update(wf_defaults)

    # Layer on env overrides
    env_overrides = _load_env_overrides()
    wf_env = env_overrides.get(wf_str, {})
    merged.update(wf_env)

    return WorkflowConfidencePolicy(
        workflow_type=wf_str,
        thresholds=merged,
        strict_mode=strict_mode,
    )


def get_policy_version() -> str:
    """Return the current policy version string for audit logging."""
    return _POLICY_VERSION


def detect_workflow_type(query: str, query_type: str | None = None) -> WorkflowType:
    """Infer a WorkflowType from the query text and optional query_type hint.

    This is a lightweight heuristic; callers may override the result.
    """
    q = query.lower()

    # Check explicit query_type hint first
    if query_type:
        qt = query_type.lower()
        if qt in ("medication",):
            return WorkflowType.MEDICATION_REVIEW
        if qt in ("condition", "diagnosis"):
            return WorkflowType.DIAGNOSIS_SUPPORT
        if qt in ("lab", "vital"):
            return WorkflowType.LAB_INTERPRETATION
        if qt in ("administrative", "admin", "billing"):
            return WorkflowType.ADMINISTRATIVE

    # Keyword heuristics
    medication_keywords = [
        "medication", "drug", "prescription", "dose", "dosage",
        "prescribe", "refill", "contraindication", "interaction",
    ]
    diagnosis_keywords = [
        "diagnosis", "diagnose", "condition", "disease", "differential",
        "symptom", "prognosis",
    ]
    lab_keywords = [
        "lab", "test", "result", "level", "value", "a1c", "glucose",
        "creatinine", "hemoglobin", "vital", "blood pressure",
    ]
    admin_keywords = [
        "billing", "code", "icd", "cpt", "insurance", "authorization",
        "schedule", "appointment", "administrative",
    ]

    for kw in medication_keywords:
        if kw in q:
            return WorkflowType.MEDICATION_REVIEW
    for kw in diagnosis_keywords:
        if kw in q:
            return WorkflowType.DIAGNOSIS_SUPPORT
    for kw in lab_keywords:
        if kw in q:
            return WorkflowType.LAB_INTERPRETATION
    for kw in admin_keywords:
        if kw in q:
            return WorkflowType.ADMINISTRATIVE

    return WorkflowType.GENERAL_QUERY
