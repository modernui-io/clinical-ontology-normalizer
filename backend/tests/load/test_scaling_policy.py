"""P2-013: Tests for horizontal scaling policy."""

from __future__ import annotations

import os
import time
from unittest import mock

import pytest

from app.core.scaling_policy import ScalingAction, ScalingDecision, ScalingPolicy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def policy() -> ScalingPolicy:
    """Default policy: min=1, max=10, up=50, down=10, cooldown=120."""
    return ScalingPolicy(
        min_workers=1,
        max_workers=10,
        scale_up_threshold=50,
        scale_down_threshold=10,
        cooldown_seconds=120,
    )


@pytest.fixture
def no_cooldown_policy() -> ScalingPolicy:
    """Policy with zero cooldown for easier sequential testing."""
    return ScalingPolicy(
        min_workers=1,
        max_workers=10,
        scale_up_threshold=50,
        scale_down_threshold=10,
        cooldown_seconds=0,
    )


# ---------------------------------------------------------------------------
# Construction / validation
# ---------------------------------------------------------------------------

class TestScalingPolicyValidation:
    def test_default_values(self) -> None:
        p = ScalingPolicy()
        assert p.min_workers >= 1
        assert p.max_workers >= p.min_workers

    def test_min_workers_too_low(self) -> None:
        with pytest.raises(ValueError, match="min_workers must be >= 1"):
            ScalingPolicy(min_workers=0)

    def test_max_less_than_min(self) -> None:
        with pytest.raises(ValueError, match="max_workers must be >= min_workers"):
            ScalingPolicy(min_workers=5, max_workers=3)

    def test_scale_up_threshold_non_positive(self) -> None:
        with pytest.raises(ValueError, match="scale_up_threshold must be > 0"):
            ScalingPolicy(scale_up_threshold=0)

    def test_scale_down_threshold_negative(self) -> None:
        with pytest.raises(ValueError, match="scale_down_threshold must be >= 0"):
            ScalingPolicy(scale_down_threshold=-1)

    def test_down_gte_up(self) -> None:
        with pytest.raises(ValueError, match="scale_down_threshold must be < scale_up_threshold"):
            ScalingPolicy(scale_up_threshold=50, scale_down_threshold=50)

    def test_negative_cooldown(self) -> None:
        with pytest.raises(ValueError, match="cooldown_seconds must be >= 0"):
            ScalingPolicy(cooldown_seconds=-1)

    def test_env_var_override(self) -> None:
        env = {
            "WORKER_MIN": "2",
            "WORKER_MAX": "20",
            "SCALE_UP_THRESHOLD": "100",
            "SCALE_DOWN_THRESHOLD": "5",
            "SCALE_COOLDOWN_SECONDS": "60",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            p = ScalingPolicy()
            assert p.min_workers == 2
            assert p.max_workers == 20
            assert p.scale_up_threshold == 100
            assert p.scale_down_threshold == 5
            assert p.cooldown_seconds == 60


# ---------------------------------------------------------------------------
# Scaling decisions
# ---------------------------------------------------------------------------

class TestEvaluateScaling:
    def test_hold_when_within_thresholds(self, policy: ScalingPolicy) -> None:
        decision = policy.evaluate_scaling(current_workers=2, queue_depth=60)
        # 60/2 = 30 -> between 10 and 50
        assert decision.action is ScalingAction.HOLD
        assert decision.target_workers == 2

    def test_scale_up_when_depth_high(self, policy: ScalingPolicy) -> None:
        decision = policy.evaluate_scaling(current_workers=2, queue_depth=200)
        # 200/2 = 100 > 50 threshold
        assert decision.action is ScalingAction.SCALE_UP
        assert decision.target_workers > 2
        assert decision.target_workers <= 10

    def test_scale_down_when_depth_low(self, no_cooldown_policy: ScalingPolicy) -> None:
        decision = no_cooldown_policy.evaluate_scaling(current_workers=5, queue_depth=10)
        # 10/5 = 2 < 10 threshold
        assert decision.action is ScalingAction.SCALE_DOWN
        assert decision.target_workers < 5
        assert decision.target_workers >= 1

    def test_scale_down_to_min(self, no_cooldown_policy: ScalingPolicy) -> None:
        decision = no_cooldown_policy.evaluate_scaling(current_workers=5, queue_depth=0)
        assert decision.action is ScalingAction.SCALE_DOWN
        assert decision.target_workers == 1  # min_workers

    def test_scale_up_capped_at_max(self, policy: ScalingPolicy) -> None:
        decision = policy.evaluate_scaling(current_workers=2, queue_depth=10000)
        assert decision.action is ScalingAction.SCALE_UP
        assert decision.target_workers <= 10

    def test_hold_at_max_workers(self, policy: ScalingPolicy) -> None:
        decision = policy.evaluate_scaling(current_workers=10, queue_depth=10000)
        # Already at max
        assert decision.action is ScalingAction.HOLD
        assert decision.target_workers == 10

    def test_hold_at_min_workers_low_depth(self, no_cooldown_policy: ScalingPolicy) -> None:
        decision = no_cooldown_policy.evaluate_scaling(current_workers=1, queue_depth=0)
        # Already at min
        assert decision.action is ScalingAction.HOLD
        assert decision.target_workers == 1


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------

class TestCooldown:
    def test_cooldown_prevents_immediate_rescale(self, policy: ScalingPolicy) -> None:
        # First evaluation triggers scale-up
        d1 = policy.evaluate_scaling(current_workers=2, queue_depth=200)
        assert d1.action is ScalingAction.SCALE_UP

        # Second evaluation is in cooldown
        d2 = policy.evaluate_scaling(current_workers=d1.target_workers, queue_depth=200)
        assert d2.action is ScalingAction.HOLD
        assert "cooldown" in d2.reason.lower()

    def test_reset_cooldown(self, policy: ScalingPolicy) -> None:
        policy.evaluate_scaling(current_workers=2, queue_depth=200)
        policy.reset_cooldown()
        d = policy.evaluate_scaling(current_workers=2, queue_depth=200)
        assert d.action is ScalingAction.SCALE_UP

    def test_no_cooldown_when_zero(self, no_cooldown_policy: ScalingPolicy) -> None:
        d1 = no_cooldown_policy.evaluate_scaling(current_workers=2, queue_depth=200)
        assert d1.action is ScalingAction.SCALE_UP
        d2 = no_cooldown_policy.evaluate_scaling(current_workers=2, queue_depth=200)
        # With 0 cooldown, second evaluation should also be SCALE_UP
        assert d2.action is ScalingAction.SCALE_UP


# ---------------------------------------------------------------------------
# Edge cases and input validation
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_invalid_current_workers(self, policy: ScalingPolicy) -> None:
        with pytest.raises(ValueError, match="current_workers must be >= 1"):
            policy.evaluate_scaling(current_workers=0, queue_depth=10)

    def test_negative_queue_depth(self, policy: ScalingPolicy) -> None:
        with pytest.raises(ValueError, match="queue_depth must be >= 0"):
            policy.evaluate_scaling(current_workers=1, queue_depth=-1)

    def test_decision_fields_populated(self, policy: ScalingPolicy) -> None:
        d = policy.evaluate_scaling(current_workers=3, queue_depth=90)
        assert isinstance(d, ScalingDecision)
        assert d.current_workers == 3
        assert d.queue_depth == 90
        assert d.depth_per_worker == 30.0
        assert isinstance(d.reason, str)

    def test_single_worker_high_depth(self, policy: ScalingPolicy) -> None:
        d = policy.evaluate_scaling(current_workers=1, queue_depth=500)
        assert d.action is ScalingAction.SCALE_UP
        assert d.depth_per_worker == 500.0

    def test_exact_threshold_boundary(self, no_cooldown_policy: ScalingPolicy) -> None:
        # depth_per_worker == scale_up_threshold exactly -> not greater, so HOLD
        d = no_cooldown_policy.evaluate_scaling(current_workers=2, queue_depth=100)
        assert d.action is ScalingAction.HOLD

    def test_just_above_scale_up_threshold(self, no_cooldown_policy: ScalingPolicy) -> None:
        d = no_cooldown_policy.evaluate_scaling(current_workers=2, queue_depth=101)
        assert d.action is ScalingAction.SCALE_UP
