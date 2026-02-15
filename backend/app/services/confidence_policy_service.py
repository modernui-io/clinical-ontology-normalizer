"""Confidence-to-action policy gating service (P0-021).

Prevents low-confidence results from triggering high-risk clinical actions.
Risk tiers define minimum confidence thresholds; the policy can operate in
strict mode (block) or advisory mode (warn).

Environment:
    CONFIDENCE_POLICY_STRICT: "true" (default) or "false"
"""

from __future__ import annotations

import logging
import os

from app.schemas.confidence_policy import (
    ActionGateResult,
    ConfidencePolicy,
    DEFAULT_THRESHOLDS,
    RiskTier,
)

logger = logging.getLogger(__name__)

# Module-level singleton policy, configured from env
_policy: ConfidencePolicy | None = None


def _get_policy() -> ConfidencePolicy:
    """Return the module-level policy, creating it on first call."""
    global _policy
    if _policy is None:
        strict_env = os.environ.get("CONFIDENCE_POLICY_STRICT", "true").lower()
        _policy = ConfidencePolicy(strict_mode=strict_env not in ("false", "0", "no"))
    return _policy


def reset_policy() -> None:
    """Reset cached policy (useful for testing)."""
    global _policy
    _policy = None


def check_action_gate(
    confidence: float,
    risk_tier: str,
    *,
    policy: ConfidencePolicy | None = None,
) -> ActionGateResult:
    """Check whether a confidence score meets the threshold for a risk tier.

    Args:
        confidence: The actual confidence score (0.0 - 1.0).
        risk_tier: One of the RiskTier values.
        policy: Optional override policy; uses global singleton if None.

    Returns:
        ActionGateResult with allowed/blocked status and details.
    """
    pol = policy or _get_policy()

    # Normalize tier string
    tier_key = risk_tier.lower()

    # Look up threshold, falling back to the strictest tier if unknown
    required = pol.thresholds.get(tier_key, DEFAULT_THRESHOLDS.get(tier_key, 0.95))

    allowed = confidence >= required

    if allowed:
        message = (
            f"Confidence {confidence:.2f} meets {tier_key} threshold ({required:.2f})"
        )
    elif pol.strict_mode:
        message = (
            f"BLOCKED: Confidence {confidence:.2f} below {tier_key} "
            f"threshold ({required:.2f}). Action requires clinician review."
        )
    else:
        message = (
            f"WARNING: Confidence {confidence:.2f} below {tier_key} "
            f"threshold ({required:.2f}). Proceeding with caution."
        )
        # In non-strict mode, we still report allowed=False but the message
        # indicates advisory-only behavior
        allowed = False

    logger.debug(
        "P0-021 action gate: tier=%s required=%.2f actual=%.2f allowed=%s strict=%s",
        tier_key,
        required,
        confidence,
        allowed,
        pol.strict_mode,
    )

    return ActionGateResult(
        allowed=allowed,
        risk_tier=tier_key,
        required_confidence=required,
        actual_confidence=round(confidence, 4),
        message=message,
    )
