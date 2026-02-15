"""P2-019: API budget and timeout policies for the hybrid query path.

Provides a ``BudgetTracker`` async context manager that enforces wall-clock
limits on each phase of a hybrid clinical query (LLM call, knowledge-graph
traversal, document retrieval, and total). When any phase exceeds its budget
a ``BudgetExceeded`` exception is raised so the caller can return a degraded
response rather than hang indefinitely.

Limits are configurable via environment variables:
    QUERY_BUDGET_TOTAL_SECONDS   (default 30)
    QUERY_BUDGET_LLM_SECONDS     (default 15)
    QUERY_BUDGET_KG_SECONDS      (default 10)
    QUERY_BUDGET_DOC_SECONDS     (default 5)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Literal

Phase = Literal["llm", "kg", "doc_retrieval"]


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


@dataclass
class QueryBudget:
    """Configurable time limits for each phase of a hybrid query."""

    max_total_seconds: float = field(
        default_factory=lambda: _env_float("QUERY_BUDGET_TOTAL_SECONDS", 30.0)
    )
    max_llm_seconds: float = field(
        default_factory=lambda: _env_float("QUERY_BUDGET_LLM_SECONDS", 15.0)
    )
    max_kg_seconds: float = field(
        default_factory=lambda: _env_float("QUERY_BUDGET_KG_SECONDS", 10.0)
    )
    max_doc_retrieval_seconds: float = field(
        default_factory=lambda: _env_float("QUERY_BUDGET_DOC_SECONDS", 5.0)
    )

    def limit_for(self, phase: Phase) -> float:
        """Return the per-phase limit in seconds."""
        return {
            "llm": self.max_llm_seconds,
            "kg": self.max_kg_seconds,
            "doc_retrieval": self.max_doc_retrieval_seconds,
        }[phase]


class BudgetExceeded(Exception):
    """Raised when a query phase or total time exceeds its budget."""

    def __init__(self, phase: str, elapsed: float, limit: float) -> None:
        self.phase = phase
        self.elapsed = elapsed
        self.limit = limit
        super().__init__(
            f"Budget exceeded for '{phase}': {elapsed:.2f}s > {limit:.2f}s limit"
        )


class BudgetTracker:
    """Track and enforce wall-clock budgets for hybrid query phases.

    Usage::

        tracker = BudgetTracker()

        tracker.start_phase("llm")
        result = await call_llm(...)
        tracker.end_phase("llm")

        tracker.start_phase("kg")
        nodes = await query_kg(...)
        tracker.end_phase("kg")

        summary = tracker.get_summary()
    """

    def __init__(self, budget: QueryBudget | None = None) -> None:
        self.budget = budget or QueryBudget()
        self._start_time: float = time.monotonic()
        self._phase_starts: dict[str, float] = {}
        self._phase_elapsed: dict[str, float] = {}

    # -- phase tracking -----------------------------------------------------

    def start_phase(self, phase: Phase) -> None:
        """Mark the beginning of a budget phase."""
        self._phase_starts[phase] = time.monotonic()

    def end_phase(self, phase: Phase) -> None:
        """Mark the end of a budget phase and enforce limits.

        Raises ``BudgetExceeded`` if the phase or total budget is exceeded.
        """
        start = self._phase_starts.pop(phase, None)
        if start is None:
            return  # phase was never started; no-op

        elapsed = time.monotonic() - start
        self._phase_elapsed[phase] = elapsed

        # Per-phase check
        limit = self.budget.limit_for(phase)
        if elapsed > limit:
            raise BudgetExceeded(phase, elapsed, limit)

        # Total check
        total_elapsed = time.monotonic() - self._start_time
        if total_elapsed > self.budget.max_total_seconds:
            raise BudgetExceeded("total", total_elapsed, self.budget.max_total_seconds)

    # -- summary ------------------------------------------------------------

    def total_elapsed(self) -> float:
        """Seconds since the tracker was created."""
        return time.monotonic() - self._start_time

    def get_summary(self) -> dict[str, float]:
        """Return a dict of phase -> elapsed_ms suitable for API responses."""
        summary: dict[str, float] = {}
        for phase, elapsed in self._phase_elapsed.items():
            summary[f"{phase}_ms"] = round(elapsed * 1000, 1)
        summary["total_ms"] = round(self.total_elapsed() * 1000, 1)
        return summary
