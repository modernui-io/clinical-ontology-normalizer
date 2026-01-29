"""Temporal Reasoning Agent for Clinical Decision Support.

This agent is specialized in temporal constraint validation and
time-aware clinical reasoning.

Features:
- Validates temporal consistency of recommendations
- Detects temporal conflicts (e.g., treatment before diagnosis)
- Answers temporal queries about patient timeline
- Projects future states based on temporal patterns
- Participates in TrustedMDT consensus with temporal perspective

Based on research in Temporal Knowledge Graphs for healthcare.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.schemas.knowledge_graph import TemporalOrder
from app.services.multi_agent_orchestrator import (
    AgentContext,
    AgentRecommendation,
    AgentRole,
    AgentVote,
    BaseAgent,
    CausalChain,
    RecommendationType,
    TemporalContext,
)

logger = logging.getLogger(__name__)


@dataclass
class TemporalConflict:
    """A temporal inconsistency detected in the clinical timeline."""

    conflict_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    severity: str = "moderate"  # critical, high, moderate, low
    event_a: dict[str, Any] = field(default_factory=dict)
    event_b: dict[str, Any] = field(default_factory=dict)
    expected_order: str = ""
    actual_order: str = ""
    recommendation: str = ""


@dataclass
class TemporalProjection:
    """A projected future event based on temporal patterns."""

    projection_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    projected_date: datetime | None = None
    confidence: float = 0.0
    based_on: list[str] = field(default_factory=list)
    recommended_action: str = ""


class TemporalReasoningAgent(BaseAgent):
    """Agent specialized in temporal reasoning for clinical decision support.

    This agent:
    1. Validates temporal consistency of clinical facts and recommendations
    2. Detects temporal conflicts in the patient timeline
    3. Projects future events based on patterns
    4. Votes on recommendations considering temporal feasibility
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.DIAGNOSTIC,  # Uses DIAGNOSTIC role for voting
            name="Temporal Reasoning Specialist",
            description="Validates temporal consistency and performs time-aware reasoning",
        )

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Analyze temporal aspects of patient data and generate recommendations."""
        self.clear_reasoning()
        recommendations = []

        self.add_reasoning_step("Analyzing patient timeline for temporal patterns")

        # Build temporal context if not present
        if not context.temporal_context:
            context.temporal_context = self._build_temporal_context(context)

        # Check for temporal conflicts
        conflicts = self._detect_temporal_conflicts(context)
        for conflict in conflicts:
            self.add_reasoning_step(f"Detected temporal conflict: {conflict.description}")

            recommendations.append(
                AgentRecommendation(
                    agent_role=self.role,
                    recommendation_type=RecommendationType.WARNING,
                    content=f"Temporal inconsistency detected: {conflict.description}. "
                            f"{conflict.recommendation}",
                    confidence=0.9,
                    evidence=[
                        f"Event A: {conflict.event_a.get('description', 'Unknown')}",
                        f"Event B: {conflict.event_b.get('description', 'Unknown')}",
                    ],
                    reasoning_chain=self.get_reasoning_chain(),
                    supporting_data={
                        "conflict_id": conflict.conflict_id,
                        "severity": conflict.severity,
                        "conflict_type": "temporal_inconsistency",
                    },
                )
            )

        # Validate causal chain temporal ordering
        for chain in context.causal_chains:
            if not chain.temporal_valid:
                self.add_reasoning_step(
                    f"Causal chain '{chain.description}' has temporal issues"
                )

                recommendations.append(
                    AgentRecommendation(
                        agent_role=self.role,
                        recommendation_type=RecommendationType.WARNING,
                        content=f"Causal chain temporal issue: {chain.validation_notes}",
                        confidence=0.85,
                        evidence=[f"Chain: {chain.description}"],
                        reasoning_chain=self.get_reasoning_chain(),
                    )
                )

        # Generate projections for monitoring
        projections = self._generate_temporal_projections(context)
        for projection in projections:
            self.add_reasoning_step(f"Projected event: {projection.description}")

            if projection.recommended_action:
                recommendations.append(
                    AgentRecommendation(
                        agent_role=self.role,
                        recommendation_type=RecommendationType.MONITORING,
                        content=projection.recommended_action,
                        confidence=projection.confidence,
                        evidence=projection.based_on,
                        reasoning_chain=self.get_reasoning_chain(),
                        supporting_data={
                            "projection_id": projection.projection_id,
                            "projected_date": (
                                projection.projected_date.isoformat()
                                if projection.projected_date
                                else None
                            ),
                        },
                    )
                )

        # Add temporal constraints to context
        self._add_temporal_constraints(context)

        return recommendations

    def _build_temporal_context(self, context: AgentContext) -> TemporalContext:
        """Build temporal context from patient data."""
        now = datetime.now(timezone.utc)

        # Extract active conditions with dates
        active_conditions = []
        for cond in context.conditions:
            if cond.get("status") != "resolved":
                active_conditions.append({
                    "name": cond.get("name", "Unknown"),
                    "start_date": cond.get("start_date", "unknown"),
                    "confidence": cond.get("confidence", 0.0),
                })

        # Extract active medications with dates
        active_medications = []
        for med in context.medications:
            if med.get("status") != "discontinued":
                active_medications.append({
                    "name": med.get("name", "Unknown"),
                    "dose": med.get("dose", ""),
                    "start_date": med.get("start_date", "unknown"),
                })

        # Build recent events from lab values
        recent_events = []
        for lab in context.lab_values:
            lab_date = lab.get("date")
            if lab_date:
                try:
                    if isinstance(lab_date, str):
                        lab_dt = datetime.fromisoformat(lab_date.replace("Z", "+00:00"))
                    else:
                        lab_dt = lab_date

                    if (now - lab_dt).days <= 30:
                        recent_events.append({
                            "date": lab_dt.strftime("%Y-%m-%d"),
                            "description": f"{lab.get('name', 'Lab')}: {lab.get('value', '')} {lab.get('unit', '')}",
                        })
                except (ValueError, TypeError):
                    pass

        return TemporalContext(
            reference_time=now,
            active_conditions=active_conditions,
            active_medications=active_medications,
            recent_events=sorted(recent_events, key=lambda x: x["date"], reverse=True),
        )

    def _detect_temporal_conflicts(self, context: AgentContext) -> list[TemporalConflict]:
        """Detect temporal inconsistencies in the patient timeline."""
        conflicts = []

        # Check treatment-diagnosis temporal ordering
        for med in context.medications:
            med_start = med.get("start_date")
            if not med_start:
                continue

            try:
                if isinstance(med_start, str):
                    med_dt = datetime.fromisoformat(med_start.replace("Z", "+00:00"))
                else:
                    med_dt = med_start
            except (ValueError, TypeError):
                continue

            # Find related conditions (treatments should follow diagnoses)
            for cond in context.conditions:
                cond_start = cond.get("start_date")
                if not cond_start:
                    continue

                try:
                    if isinstance(cond_start, str):
                        cond_dt = datetime.fromisoformat(cond_start.replace("Z", "+00:00"))
                    else:
                        cond_dt = cond_start
                except (ValueError, TypeError):
                    continue

                # Check if medication started before condition was diagnosed
                # (more than 7 days before is suspicious)
                if med_dt < cond_dt - timedelta(days=7):
                    # Check if this medication typically treats this condition
                    med_name = med.get("name", "").lower()
                    cond_name = cond.get("name", "").lower()

                    # Simple heuristic - in production, use KG relationships
                    treatment_pairs = [
                        ("metformin", "diabetes"),
                        ("insulin", "diabetes"),
                        ("lisinopril", "hypertension"),
                        ("amlodipine", "hypertension"),
                        ("atorvastatin", "hyperlipidemia"),
                    ]

                    for med_pattern, cond_pattern in treatment_pairs:
                        if med_pattern in med_name and cond_pattern in cond_name:
                            conflicts.append(
                                TemporalConflict(
                                    description=f"{med.get('name')} started before {cond.get('name')} was diagnosed",
                                    severity="high",
                                    event_a={
                                        "description": f"{med.get('name')} started",
                                        "date": med_dt.isoformat(),
                                    },
                                    event_b={
                                        "description": f"{cond.get('name')} diagnosed",
                                        "date": cond_dt.isoformat(),
                                    },
                                    expected_order="diagnosis_before_treatment",
                                    actual_order="treatment_before_diagnosis",
                                    recommendation="Verify diagnosis date or medication start date",
                                )
                            )
                            break

        return conflicts

    def _generate_temporal_projections(
        self, context: AgentContext
    ) -> list[TemporalProjection]:
        """Generate projections for future monitoring needs."""
        projections = []
        now = datetime.now(timezone.utc)

        # Check for medications that need monitoring
        for med in context.medications:
            med_name = med.get("name", "").lower()
            med_start = med.get("start_date")

            if not med_start:
                continue

            try:
                if isinstance(med_start, str):
                    start_dt = datetime.fromisoformat(med_start.replace("Z", "+00:00"))
                else:
                    start_dt = med_start
            except (ValueError, TypeError):
                continue

            # ACE inhibitors/ARBs need renal monitoring
            if any(x in med_name for x in ["lisinopril", "losartan", "enalapril", "valsartan"]):
                # Check if creatinine was done in last 6 months
                has_recent_creatinine = False
                for lab in context.lab_values:
                    if "creatinine" in lab.get("name", "").lower():
                        lab_date = lab.get("date")
                        if lab_date:
                            try:
                                if isinstance(lab_date, str):
                                    lab_dt = datetime.fromisoformat(lab_date.replace("Z", "+00:00"))
                                else:
                                    lab_dt = lab_date

                                if (now - lab_dt).days <= 180:
                                    has_recent_creatinine = True
                                    break
                            except (ValueError, TypeError):
                                pass

                if not has_recent_creatinine:
                    projections.append(
                        TemporalProjection(
                            description=f"Renal function monitoring due for {med.get('name')}",
                            projected_date=now + timedelta(days=14),
                            confidence=0.9,
                            based_on=[
                                f"Started {med.get('name')} on {start_dt.strftime('%Y-%m-%d')}",
                                "No creatinine in last 6 months",
                                "KDIGO guidelines recommend annual monitoring",
                            ],
                            recommended_action=f"Order serum creatinine and eGFR - monitoring for {med.get('name')}",
                        )
                    )

            # Metformin needs B12 monitoring
            if "metformin" in med_name:
                # Check for B12 in last year
                has_recent_b12 = False
                for lab in context.lab_values:
                    if "b12" in lab.get("name", "").lower() or "cobalamin" in lab.get("name", "").lower():
                        lab_date = lab.get("date")
                        if lab_date:
                            try:
                                if isinstance(lab_date, str):
                                    lab_dt = datetime.fromisoformat(lab_date.replace("Z", "+00:00"))
                                else:
                                    lab_dt = lab_date

                                if (now - lab_dt).days <= 365:
                                    has_recent_b12 = True
                                    break
                            except (ValueError, TypeError):
                                pass

                if not has_recent_b12:
                    projections.append(
                        TemporalProjection(
                            description="Vitamin B12 monitoring due for metformin therapy",
                            projected_date=now + timedelta(days=30),
                            confidence=0.8,
                            based_on=[
                                f"On metformin since {start_dt.strftime('%Y-%m-%d')}",
                                "No B12 level in last year",
                                "ADA recommends periodic B12 monitoring",
                            ],
                            recommended_action="Order vitamin B12 level - monitoring for metformin",
                        )
                    )

        return projections

    def _add_temporal_constraints(self, context: AgentContext) -> None:
        """Add temporal constraints to the context for other agents."""
        if context.temporal_context:
            constraints = []

            # Add constraints based on medications
            for med in context.medications:
                med_name = med.get("name", "")
                if any(x in med_name.lower() for x in ["warfarin", "coumadin"]):
                    constraints.append(
                        "INR monitoring required at regular intervals (warfarin therapy)"
                    )
                if any(x in med_name.lower() for x in ["lithium"]):
                    constraints.append(
                        "Lithium level monitoring required (lithium therapy)"
                    )

            # Add constraints based on conditions
            for cond in context.conditions:
                cond_name = cond.get("name", "")
                if "diabetes" in cond_name.lower():
                    constraints.append("HbA1c monitoring every 3-6 months (diabetes)")
                if "ckd" in cond_name.lower() or "kidney disease" in cond_name.lower():
                    constraints.append("eGFR monitoring at CKD-appropriate intervals")

            context.temporal_context.temporal_constraints = constraints

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote on a recommendation from a temporal reasoning perspective."""
        concerns = []

        # Check temporal feasibility
        if recommendation.recommendation_type == RecommendationType.TREATMENT:
            # Check if there's a temporal conflict
            for conflict in self._detect_temporal_conflicts(context):
                if conflict.severity in ["critical", "high"]:
                    concerns.append(
                        f"Temporal conflict detected: {conflict.description}"
                    )

        # Check if recommendation respects temporal constraints
        if context.temporal_context:
            for constraint in context.temporal_context.temporal_constraints:
                # Simple check - in production, more sophisticated matching
                if "monitoring" in constraint.lower() and "monitoring" in recommendation.content.lower():
                    return AgentVote(
                        agent_role=self.role,
                        agrees=True,
                        confidence=0.95,
                        concerns=[],
                    )

        # Check causal chain validity
        for chain in context.causal_chains:
            if not chain.temporal_valid:
                if recommendation.content.lower() in chain.description.lower():
                    concerns.append(f"Related causal chain has temporal issues: {chain.validation_notes}")

        if concerns:
            return AgentVote(
                agent_role=self.role,
                agrees=False,
                confidence=0.7,
                concerns=concerns,
            )

        return AgentVote(
            agent_role=self.role,
            agrees=True,
            confidence=0.8,
        )

    def validate_causal_chain_temporal(
        self,
        chain: CausalChain,
    ) -> tuple[bool, str]:
        """Validate temporal ordering of a causal chain.

        Ensures causes precede effects.
        """
        for i, link in enumerate(chain.links[:-1]):
            source_time = link.get("source_time")
            target_time = chain.links[i + 1].get("source_time")

            if source_time and target_time:
                try:
                    if isinstance(source_time, str):
                        source_dt = datetime.fromisoformat(source_time.replace("Z", "+00:00"))
                    else:
                        source_dt = source_time

                    if isinstance(target_time, str):
                        target_dt = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
                    else:
                        target_dt = target_time

                    if source_dt > target_dt:
                        return (
                            False,
                            f"Cause '{link.get('source')}' occurs after effect '{chain.links[i+1].get('source')}'",
                        )
                except (ValueError, TypeError):
                    pass

        return True, "Temporal ordering valid"
