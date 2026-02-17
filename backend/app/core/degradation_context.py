"""Request-scoped degradation tracking via ContextVar.

Phase 1 Safety Envelope: Accumulates component failures during request processing
so that every clinical response can declare its degradation state.

Telemetry counters (for future Prometheus/StatsD instrumentation):
- clinical_agent_degraded_total: Counter for degraded clinical agent responses
- prewarm_critical_failure_total: Counter for critical prewarm failures
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

from app.schemas.degradation import DegradationMetadata

logger = logging.getLogger(__name__)

# Request-scoped accumulator for stage failures
_degraded_components: ContextVar[list[str]] = ContextVar("degraded_components", default=[])
_degradation_warnings: ContextVar[list[str]] = ContextVar("degradation_warnings", default=[])
_fallback_used: ContextVar[bool] = ContextVar("fallback_used", default=False)


class DegradationContext:
    """Static helper for recording and snapshotting degradation state.

    All methods are class-level; state is stored in ContextVars so each
    request (or asyncio task) gets its own isolated accumulator.
    """

    @staticmethod
    def reset() -> None:
        """Clear accumulated degradation state for a new request."""
        _degraded_components.set([])
        _degradation_warnings.set([])
        _fallback_used.set(False)

    @staticmethod
    def record_stage_failure(component: str, error: Exception, fallback_value: Any) -> None:
        """Record a component failure during request processing.

        Args:
            component: Name of the failed component (e.g., "guideline_rag", "neo4j_sync").
            error: The caught exception.
            fallback_value: The value used as fallback (for documentation/logging).
        """
        components = _degraded_components.get()
        if not components:
            # ContextVar default is shared; create a new list on first write
            components = []
            _degraded_components.set(components)
        components.append(component)

        warnings = _degradation_warnings.get()
        if not warnings:
            warnings = []
            _degradation_warnings.set(warnings)
        warnings.append(f"{component}: {type(error).__name__}: {error}")

        _fallback_used.set(True)

        logger.warning(
            f"Degraded: {component} failed ({type(error).__name__}: {error}), "
            f"fallback_value={type(fallback_value).__name__}"
        )

    @staticmethod
    def snapshot() -> DegradationMetadata:
        """Return a snapshot of the current degradation state.

        Pulls trace_id from the request_id context if available.
        """
        from app.api.middleware.request_id import get_request_id

        components = _degraded_components.get()
        warnings = _degradation_warnings.get()
        fallback = _fallback_used.get()

        return DegradationMetadata(
            degraded=len(components) > 0,
            degraded_components=list(components),
            fallback_used=fallback,
            warnings=list(warnings),
            trace_id=get_request_id(),
        )
