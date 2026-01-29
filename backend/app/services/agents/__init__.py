"""Specialized clinical agents for multi-agent orchestration.

This package contains specialized agents that participate in the
TrustedMDT-style multi-agent clinical decision support system.

Agents:
- PolicyComplianceAgent: Checks patient state against clinical policies
- TemporalReasoningAgent: Validates temporal consistency and time-aware reasoning

These agents extend the base agent types in multi_agent_orchestrator.py
and can be added to the orchestrator for enhanced reasoning capabilities.
"""

from __future__ import annotations

from app.services.agents.policy_compliance_agent import (
    ComplianceGap,
    PolicyComplianceAgent,
    PolicyMatch,
)
from app.services.agents.temporal_reasoning_agent import (
    TemporalConflict,
    TemporalProjection,
    TemporalReasoningAgent,
)

__all__ = [
    "PolicyComplianceAgent",
    "PolicyMatch",
    "ComplianceGap",
    "TemporalReasoningAgent",
    "TemporalConflict",
    "TemporalProjection",
]
