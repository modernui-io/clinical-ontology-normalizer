"""Tests for P0-021: Confidence-to-action policy gating.

Validates that the confidence policy service correctly gates actions
based on risk tier thresholds and strict/advisory mode.
"""

from __future__ import annotations

import os

import pytest

from app.schemas.confidence_policy import (
    ActionGateResult,
    ConfidencePolicy,
    RiskTier,
)
from app.services.confidence_policy_service import (
    check_action_gate,
    reset_policy,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset global policy before each test."""
    reset_policy()
    yield
    reset_policy()


# ---------------------------------------------------------------------------
# Risk tier threshold tests
# ---------------------------------------------------------------------------

class TestRiskTierThresholds:
    """Verify each risk tier enforces its threshold."""

    def test_informational_any_confidence_allowed(self):
        result = check_action_gate(0.0, "informational")
        assert result.allowed is True
        assert result.required_confidence == 0.0

    def test_suggestion_at_threshold(self):
        result = check_action_gate(0.5, "suggestion")
        assert result.allowed is True

    def test_suggestion_below_threshold(self):
        result = check_action_gate(0.49, "suggestion")
        assert result.allowed is False

    def test_recommendation_at_threshold(self):
        result = check_action_gate(0.7, "recommendation")
        assert result.allowed is True

    def test_recommendation_below_threshold(self):
        result = check_action_gate(0.69, "recommendation")
        assert result.allowed is False

    def test_action_at_threshold(self):
        result = check_action_gate(0.85, "action")
        assert result.allowed is True

    def test_action_below_threshold(self):
        result = check_action_gate(0.84, "action")
        assert result.allowed is False

    def test_critical_action_at_threshold(self):
        result = check_action_gate(0.95, "critical_action")
        assert result.allowed is True

    def test_critical_action_below_threshold(self):
        result = check_action_gate(0.94, "critical_action")
        assert result.allowed is False

    def test_high_confidence_passes_all_tiers(self):
        for tier in RiskTier:
            result = check_action_gate(0.99, tier.value)
            assert result.allowed is True, f"Expected allowed for tier {tier.value} at 0.99"


# ---------------------------------------------------------------------------
# ActionGateResult structure tests
# ---------------------------------------------------------------------------

class TestActionGateResult:
    """Verify ActionGateResult contains correct fields."""

    def test_result_fields_present(self):
        result = check_action_gate(0.8, "recommendation")
        assert isinstance(result, ActionGateResult)
        assert result.risk_tier == "recommendation"
        assert result.required_confidence == 0.7
        assert result.actual_confidence == 0.8
        assert result.allowed is True
        assert result.message != ""

    def test_blocked_result_has_message(self):
        result = check_action_gate(0.3, "action")
        assert result.allowed is False
        assert "BLOCKED" in result.message
        assert "clinician review" in result.message.lower()

    def test_result_serializable(self):
        result = check_action_gate(0.75, "recommendation")
        data = result.model_dump()
        assert isinstance(data, dict)
        assert "allowed" in data
        assert "risk_tier" in data
        assert "required_confidence" in data
        assert "actual_confidence" in data
        assert "message" in data


# ---------------------------------------------------------------------------
# Strict vs advisory mode
# ---------------------------------------------------------------------------

class TestStrictMode:
    """Verify strict vs advisory mode behavior."""

    def test_strict_mode_blocks(self):
        policy = ConfidencePolicy(strict_mode=True)
        result = check_action_gate(0.5, "action", policy=policy)
        assert result.allowed is False
        assert "BLOCKED" in result.message

    def test_advisory_mode_warns(self):
        policy = ConfidencePolicy(strict_mode=False)
        result = check_action_gate(0.5, "action", policy=policy)
        assert result.allowed is False
        assert "WARNING" in result.message

    def test_strict_mode_env_variable(self, monkeypatch):
        monkeypatch.setenv("CONFIDENCE_POLICY_STRICT", "false")
        reset_policy()
        result = check_action_gate(0.5, "action")
        assert result.allowed is False
        assert "WARNING" in result.message

    def test_strict_mode_default_true(self, monkeypatch):
        monkeypatch.delenv("CONFIDENCE_POLICY_STRICT", raising=False)
        reset_policy()
        result = check_action_gate(0.5, "action")
        assert result.allowed is False
        assert "BLOCKED" in result.message


# ---------------------------------------------------------------------------
# Custom policy thresholds
# ---------------------------------------------------------------------------

class TestCustomPolicy:
    """Verify custom threshold overrides."""

    def test_custom_threshold_lower(self):
        policy = ConfidencePolicy(
            thresholds={"recommendation": 0.5},
            strict_mode=True,
        )
        result = check_action_gate(0.55, "recommendation", policy=policy)
        assert result.allowed is True
        assert result.required_confidence == 0.5

    def test_custom_threshold_higher(self):
        policy = ConfidencePolicy(
            thresholds={"suggestion": 0.9},
            strict_mode=True,
        )
        result = check_action_gate(0.85, "suggestion", policy=policy)
        assert result.allowed is False
        assert result.required_confidence == 0.9

    def test_unknown_tier_defaults_to_strictest(self):
        result = check_action_gate(0.9, "unknown_tier")
        # Unknown tiers fall back to 0.95 (critical_action level)
        assert result.allowed is False
        assert result.required_confidence == 0.95


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases for confidence policy."""

    def test_zero_confidence(self):
        result = check_action_gate(0.0, "informational")
        assert result.allowed is True

    def test_zero_confidence_non_informational(self):
        result = check_action_gate(0.0, "suggestion")
        assert result.allowed is False

    def test_confidence_exactly_one(self):
        result = check_action_gate(1.0, "critical_action")
        assert result.allowed is True

    def test_case_insensitive_tier(self):
        result = check_action_gate(0.9, "RECOMMENDATION")
        assert result.allowed is True
        assert result.risk_tier == "recommendation"

    def test_actual_confidence_rounded(self):
        result = check_action_gate(0.123456789, "informational")
        assert result.actual_confidence == 0.1235
