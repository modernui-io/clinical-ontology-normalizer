"""P2-013: Horizontal scaling policy for worker pools.

Evaluates queue depth against worker count to produce scaling decisions.
Configurable via environment variables: WORKER_MIN, WORKER_MAX,
SCALE_UP_THRESHOLD, SCALE_DOWN_THRESHOLD, SCALE_COOLDOWN_SECONDS.
"""

from __future__ import annotations

import enum
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ScalingAction(enum.Enum):
    """Action recommended by the scaling policy."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    HOLD = "hold"


@dataclass(frozen=True)
class ScalingDecision:
    """Result of a scaling evaluation."""
    action: ScalingAction
    current_workers: int
    target_workers: int
    reason: str
    queue_depth: int
    depth_per_worker: float


@dataclass
class ScalingPolicy:
    """Evaluates whether the worker pool should scale up, down, or hold.

    Defaults:
        - min_workers: 1
        - max_workers: 10
        - scale_up_threshold: 50  (queue items per worker to trigger scale-up)
        - scale_down_threshold: 10 (queue items per worker to trigger scale-down)
        - cooldown_seconds: 120
    """

    min_workers: int = field(default_factory=lambda: int(os.environ.get("WORKER_MIN", "1")))
    max_workers: int = field(default_factory=lambda: int(os.environ.get("WORKER_MAX", "10")))
    scale_up_threshold: float = field(
        default_factory=lambda: float(os.environ.get("SCALE_UP_THRESHOLD", "50"))
    )
    scale_down_threshold: float = field(
        default_factory=lambda: float(os.environ.get("SCALE_DOWN_THRESHOLD", "10"))
    )
    cooldown_seconds: int = field(
        default_factory=lambda: int(os.environ.get("SCALE_COOLDOWN_SECONDS", "120"))
    )

    # Internal state
    _last_scale_time: float = field(default=0.0, repr=False, compare=False)
    _last_action: ScalingAction = field(default=ScalingAction.HOLD, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.min_workers < 1:
            raise ValueError("min_workers must be >= 1")
        if self.max_workers < self.min_workers:
            raise ValueError("max_workers must be >= min_workers")
        if self.scale_up_threshold <= 0:
            raise ValueError("scale_up_threshold must be > 0")
        if self.scale_down_threshold < 0:
            raise ValueError("scale_down_threshold must be >= 0")
        if self.scale_down_threshold >= self.scale_up_threshold:
            raise ValueError("scale_down_threshold must be < scale_up_threshold")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be >= 0")

    def _in_cooldown(self) -> bool:
        """Return True if we are still in the cooldown period after the last scale event."""
        if self._last_scale_time == 0.0:
            return False
        return (time.monotonic() - self._last_scale_time) < self.cooldown_seconds

    def evaluate_scaling(
        self,
        current_workers: int,
        queue_depth: int,
    ) -> ScalingDecision:
        """Decide whether to scale the worker pool.

        Args:
            current_workers: Number of currently running workers.
            queue_depth: Total number of pending jobs across all queues.

        Returns:
            ScalingDecision with recommended action and target.
        """
        if current_workers < 1:
            raise ValueError("current_workers must be >= 1")
        if queue_depth < 0:
            raise ValueError("queue_depth must be >= 0")

        depth_per_worker = queue_depth / current_workers

        # Cooldown check
        if self._in_cooldown():
            return ScalingDecision(
                action=ScalingAction.HOLD,
                current_workers=current_workers,
                target_workers=current_workers,
                reason=f"In cooldown period ({self.cooldown_seconds}s)",
                queue_depth=queue_depth,
                depth_per_worker=depth_per_worker,
            )

        # Scale-up check
        if depth_per_worker > self.scale_up_threshold:
            # Calculate how many workers would bring depth_per_worker near the midpoint
            desired = max(
                current_workers + 1,
                min(
                    self.max_workers,
                    int(queue_depth / self.scale_up_threshold) + 1,
                ),
            )
            target = min(desired, self.max_workers)

            if target <= current_workers:
                return ScalingDecision(
                    action=ScalingAction.HOLD,
                    current_workers=current_workers,
                    target_workers=current_workers,
                    reason="Already at max_workers",
                    queue_depth=queue_depth,
                    depth_per_worker=depth_per_worker,
                )

            self._last_scale_time = time.monotonic()
            self._last_action = ScalingAction.SCALE_UP
            logger.info(
                "Scaling UP workers",
                extra={
                    "current_workers": current_workers,
                    "target_workers": target,
                    "queue_depth": queue_depth,
                    "depth_per_worker": depth_per_worker,
                },
            )
            return ScalingDecision(
                action=ScalingAction.SCALE_UP,
                current_workers=current_workers,
                target_workers=target,
                reason=f"depth_per_worker {depth_per_worker:.1f} > threshold {self.scale_up_threshold}",
                queue_depth=queue_depth,
                depth_per_worker=depth_per_worker,
            )

        # Scale-down check
        if depth_per_worker < self.scale_down_threshold:
            desired = max(
                self.min_workers,
                max(1, int(queue_depth / self.scale_up_threshold) + 1) if queue_depth > 0 else self.min_workers,
            )
            target = max(desired, self.min_workers)

            if target >= current_workers:
                return ScalingDecision(
                    action=ScalingAction.HOLD,
                    current_workers=current_workers,
                    target_workers=current_workers,
                    reason="Already at min_workers or target >= current",
                    queue_depth=queue_depth,
                    depth_per_worker=depth_per_worker,
                )

            self._last_scale_time = time.monotonic()
            self._last_action = ScalingAction.SCALE_DOWN
            logger.info(
                "Scaling DOWN workers",
                extra={
                    "current_workers": current_workers,
                    "target_workers": target,
                    "queue_depth": queue_depth,
                    "depth_per_worker": depth_per_worker,
                },
            )
            return ScalingDecision(
                action=ScalingAction.SCALE_DOWN,
                current_workers=current_workers,
                target_workers=target,
                reason=f"depth_per_worker {depth_per_worker:.1f} < threshold {self.scale_down_threshold}",
                queue_depth=queue_depth,
                depth_per_worker=depth_per_worker,
            )

        # Hold
        return ScalingDecision(
            action=ScalingAction.HOLD,
            current_workers=current_workers,
            target_workers=current_workers,
            reason=f"depth_per_worker {depth_per_worker:.1f} within thresholds [{self.scale_down_threshold}, {self.scale_up_threshold}]",
            queue_depth=queue_depth,
            depth_per_worker=depth_per_worker,
        )

    def reset_cooldown(self) -> None:
        """Reset the cooldown timer (e.g. for testing or manual override)."""
        self._last_scale_time = 0.0
