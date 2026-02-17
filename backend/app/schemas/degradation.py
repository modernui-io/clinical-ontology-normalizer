"""Degradation metadata schema for tracking partial response quality.

Phase 1 Safety Envelope: Every clinical response declares its degradation state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DegradationMetadata(BaseModel):
    """Metadata describing whether a response was produced in a degraded state.

    Attached to clinical responses so consumers know when results are partial
    or used fallback logic.
    """

    degraded: bool = Field(default=False, description="True if any component failed during processing")
    degraded_components: list[str] = Field(default_factory=list, description="Names of components that failed")
    fallback_used: bool = Field(default=False, description="True if any fallback logic was invoked")
    warnings: list[str] = Field(default_factory=list, description="Human-readable warning messages")
    trace_id: str | None = Field(default=None, description="Request trace ID for correlation")
