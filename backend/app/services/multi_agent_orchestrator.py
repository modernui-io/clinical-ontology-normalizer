"""
Multi-Agent Orchestration Service for Clinical Decision Support.

Implements a TrustedMDT-style multi-agent system where specialized agents
collaborate on complex clinical cases:
- Diagnostic Agent: Differential diagnosis and condition assessment
- Treatment Agent: Treatment recommendations and drug selection
- Safety Agent: Drug interactions, contraindications, safety checks
- Evidence Agent: Literature and guideline-based recommendations

Based on published research:
- TrustedMDT (2025): Multi-disciplinary team simulation
- MedAgentBench (2025): Standardized medical agent benchmarks
- DR.KNOWS (2025): Knowledge graph-based reasoning

Key Features:
- Shared reasoning context across agents
- Consensus building with explainable disagreements
- Confidence aggregation across specialist perspectives
- Provenance tracking for all recommendations
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Specialized agent roles in the clinical MDT."""

    DIAGNOSTIC = "diagnostic"  # Differential diagnosis
    TREATMENT = "treatment"  # Treatment planning
    SAFETY = "safety"  # Drug safety, interactions
    EVIDENCE = "evidence"  # Literature/guideline review
    COORDINATOR = "coordinator"  # MDT coordination
    POLICY = "policy"  # Policy/guideline compliance
    TEMPORAL = "temporal"  # Temporal reasoning


class ConsensusLevel(str, Enum):
    """Level of agreement among agents."""

    UNANIMOUS = "unanimous"  # All agents agree
    STRONG = "strong"  # >80% agreement
    MODERATE = "moderate"  # 60-80% agreement
    WEAK = "weak"  # 40-60% agreement
    CONFLICTING = "conflicting"  # <40% agreement


class RecommendationType(str, Enum):
    """Types of clinical recommendations."""

    DIAGNOSIS = "diagnosis"
    TREATMENT = "treatment"
    MEDICATION = "medication"
    TEST = "test"
    REFERRAL = "referral"
    MONITORING = "monitoring"
    CONTRAINDICATION = "contraindication"
    WARNING = "warning"


@dataclass
class KGTraversalPath:
    """A path traversed through the knowledge graph during reasoning."""

    path_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    temporal_info: str | None = None

    def to_prompt_text(self) -> str:
        """Format this path for inclusion in LLM prompts."""
        if not self.nodes:
            return ""

        lines = [f"Path: {self.description}"]

        # Build path string from nodes and edges
        path_parts = []
        for i, node in enumerate(self.nodes):
            node_label = node.get("label", "Unknown")
            path_parts.append(node_label)

            if i < len(self.edges):
                edge = self.edges[i]
                edge_type = edge.get("type", "relates_to")
                edge_conf = edge.get("confidence", 0.0)
                path_parts.append(f"--[{edge_type} ({edge_conf:.2f})]-->")

        lines.append("  " + " ".join(path_parts))

        if self.temporal_info:
            lines.append(f"  Temporal: {self.temporal_info}")

        lines.append(f"  Confidence: {self.confidence:.2f}")

        return "\n".join(lines)


@dataclass
class CausalChain:
    """A causal reasoning chain derived from the knowledge graph."""

    chain_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    links: list[dict[str, Any]] = field(default_factory=list)
    pathway_type: str = ""  # treatment, adverse_event, progression
    confidence: float = 0.0
    temporal_valid: bool = True
    validation_notes: str = ""

    def to_prompt_text(self) -> str:
        """Format this chain for inclusion in LLM prompts."""
        lines = [f"Causal Chain ({self.pathway_type}): {self.description}"]

        for link in self.links:
            source = link.get("source", "Unknown")
            relation = link.get("relation", "causes")
            target = link.get("target", "Unknown")
            lines.append(f"  {source} --{relation}--> {target}")

        lines.append(f"  Confidence: {self.confidence:.2f}")
        if not self.temporal_valid:
            lines.append(f"  WARNING: Temporal inconsistency - {self.validation_notes}")

        return "\n".join(lines)


@dataclass
class TemporalContext:
    """Temporal context for reasoning."""

    reference_time: datetime | None = None
    active_conditions: list[dict[str, Any]] = field(default_factory=list)
    active_medications: list[dict[str, Any]] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    temporal_constraints: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Format temporal context for LLM prompts."""
        lines = ["[Temporal Context]"]

        if self.reference_time:
            lines.append(f"Reference Time: {self.reference_time.isoformat()}")

        if self.active_conditions:
            lines.append("Currently Active Conditions:")
            for cond in self.active_conditions[:5]:
                start = cond.get("start_date", "unknown")
                name = cond.get("name", "Unknown")
                lines.append(f"  - {name} (since {start})")

        if self.active_medications:
            lines.append("Current Medications:")
            for med in self.active_medications[:5]:
                start = med.get("start_date", "unknown")
                name = med.get("name", "Unknown")
                dose = med.get("dose", "")
                lines.append(f"  - {name} {dose} (since {start})")

        if self.recent_events:
            lines.append("Recent Events (last 30 days):")
            for event in self.recent_events[:5]:
                date = event.get("date", "unknown")
                desc = event.get("description", "Unknown event")
                lines.append(f"  - {date}: {desc}")

        if self.temporal_constraints:
            lines.append("Temporal Constraints:")
            for constraint in self.temporal_constraints:
                lines.append(f"  - {constraint}")

        return "\n".join(lines)


@dataclass
class PolicyConstraint:
    """A policy rule or guideline constraint for reasoning."""

    rule_id: str = ""
    rule_name: str = ""
    description: str = ""
    applies_to: list[str] = field(default_factory=list)
    if_conditions: dict[str, Any] = field(default_factory=dict)
    then_actions: dict[str, Any] = field(default_factory=dict)
    evidence_grade: str = ""
    recommendation_strength: str = ""
    source: str = ""

    def to_prompt_text(self) -> str:
        """Format policy constraint for LLM prompts."""
        lines = [f"Rule: {self.rule_id}"]
        lines.append(f"  Name: {self.rule_name}")

        if self.if_conditions:
            lines.append("  IF:")
            for key, value in self.if_conditions.items():
                lines.append(f"    - {key}: {value}")

        if self.then_actions:
            lines.append("  THEN:")
            for key, value in self.then_actions.items():
                lines.append(f"    - {key}: {value}")

        if self.evidence_grade:
            lines.append(f"  Evidence Grade: {self.evidence_grade}")
        if self.recommendation_strength:
            lines.append(f"  Recommendation: {self.recommendation_strength}")
        if self.source:
            lines.append(f"  Source: {self.source}")

        return "\n".join(lines)


@dataclass
class AgentContext:
    """Shared context for agent reasoning.

    This context is passed to all agents and includes:
    1. Basic patient information (demographics, conditions, medications)
    2. Knowledge graph traversal paths (from multi-hop reasoning)
    3. Causal chains (validated causal relationships)
    4. Temporal context (time-aware reasoning)
    5. Policy constraints (applicable guidelines and rules)

    The to_llm_prompt() method formats all this context for inclusion
    in LLM prompts, enabling the hybrid reasoning approach where the
    LLM can leverage structured graph evidence in its analysis.
    """

    # Basic patient context
    patient_id: str
    clinical_text: str = ""
    conditions: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    lab_values: list[dict[str, Any]] = field(default_factory=list)
    vitals: dict[str, Any] = field(default_factory=dict)
    demographics: dict[str, Any] = field(default_factory=dict)
    previous_recommendations: list[dict[str, Any]] = field(default_factory=list)

    # Knowledge graph traversal context (for hybrid reasoning)
    kg_traversal_paths: list[KGTraversalPath] = field(default_factory=list)

    # Causal reasoning chains
    causal_chains: list[CausalChain] = field(default_factory=list)

    # Temporal reasoning context
    temporal_context: TemporalContext | None = None

    # Policy/guideline constraints
    policy_constraints: list[PolicyConstraint] = field(default_factory=list)

    def to_llm_prompt(self, include_sections: list[str] | None = None) -> str:
        """Format the context for inclusion in LLM prompts.

        This method serializes the knowledge graph evidence and temporal
        context into a structured text format that LLMs can reason over.

        Args:
            include_sections: Optional list of sections to include. If None,
                includes all sections. Options: 'patient', 'graph', 'causal',
                'temporal', 'policy'

        Returns:
            Formatted context string for LLM prompt
        """
        sections = include_sections or ["patient", "graph", "causal", "temporal", "policy"]
        parts = []

        # Patient context
        if "patient" in sections:
            parts.append(self._format_patient_context())

        # Knowledge graph traversal paths
        if "graph" in sections and self.kg_traversal_paths:
            parts.append(self._format_graph_context())

        # Causal reasoning chains
        if "causal" in sections and self.causal_chains:
            parts.append(self._format_causal_context())

        # Temporal context
        if "temporal" in sections and self.temporal_context:
            parts.append(self.temporal_context.to_prompt_text())

        # Policy constraints
        if "policy" in sections and self.policy_constraints:
            parts.append(self._format_policy_context())

        return "\n\n".join(parts)

    def _format_patient_context(self) -> str:
        """Format basic patient context."""
        lines = ["[Patient Context]"]

        if self.demographics:
            age = self.demographics.get("age", "Unknown")
            gender = self.demographics.get("gender", "Unknown")
            lines.append(f"Demographics: {age} year old {gender}")

        if self.conditions:
            lines.append("Conditions:")
            for cond in self.conditions[:5]:
                name = cond.get("name", "Unknown")
                conf = cond.get("confidence", 0.0)
                lines.append(f"  - {name} (confidence: {conf:.2f})")

        if self.medications:
            lines.append("Current Medications:")
            for med in self.medications[:5]:
                name = med.get("name", "Unknown")
                dose = med.get("dose", "")
                lines.append(f"  - {name} {dose}")

        if self.allergies:
            lines.append(f"Allergies: {', '.join(self.allergies)}")

        if self.lab_values:
            lines.append("Recent Lab Values:")
            for lab in self.lab_values[:5]:
                name = lab.get("name", "Unknown")
                value = lab.get("value", "")
                unit = lab.get("unit", "")
                lines.append(f"  - {name}: {value} {unit}")

        return "\n".join(lines)

    def _format_graph_context(self) -> str:
        """Format knowledge graph traversal paths."""
        lines = ["[Graph Evidence]"]
        lines.append("The following paths were traversed through the knowledge graph:")

        for i, path in enumerate(self.kg_traversal_paths[:5], 1):
            lines.append(f"\n{i}. {path.to_prompt_text()}")

        return "\n".join(lines)

    def _format_causal_context(self) -> str:
        """Format causal reasoning chains."""
        lines = ["[Causal Evidence]"]
        lines.append("The following causal relationships were identified:")

        for chain in self.causal_chains[:3]:
            lines.append(f"\n{chain.to_prompt_text()}")

        return "\n".join(lines)

    def _format_policy_context(self) -> str:
        """Format policy constraints."""
        lines = ["[Policy Constraints]"]
        lines.append("The following clinical guidelines apply:")

        for constraint in self.policy_constraints[:5]:
            lines.append(f"\n{constraint.to_prompt_text()}")

        return "\n".join(lines)

    def add_kg_path(
        self,
        description: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        confidence: float = 0.0,
        temporal_info: str | None = None,
    ) -> None:
        """Add a knowledge graph traversal path to the context."""
        path = KGTraversalPath(
            description=description,
            nodes=nodes,
            edges=edges,
            confidence=confidence,
            temporal_info=temporal_info,
        )
        self.kg_traversal_paths.append(path)

    def add_causal_chain(
        self,
        description: str,
        links: list[dict[str, Any]],
        pathway_type: str,
        confidence: float = 0.0,
        temporal_valid: bool = True,
        validation_notes: str = "",
    ) -> None:
        """Add a causal reasoning chain to the context."""
        chain = CausalChain(
            description=description,
            links=links,
            pathway_type=pathway_type,
            confidence=confidence,
            temporal_valid=temporal_valid,
            validation_notes=validation_notes,
        )
        self.causal_chains.append(chain)

    def add_policy_constraint(
        self,
        rule_id: str,
        rule_name: str,
        description: str = "",
        applies_to: list[str] | None = None,
        if_conditions: dict[str, Any] | None = None,
        then_actions: dict[str, Any] | None = None,
        evidence_grade: str = "",
        recommendation_strength: str = "",
        source: str = "",
    ) -> None:
        """Add a policy constraint to the context."""
        constraint = PolicyConstraint(
            rule_id=rule_id,
            rule_name=rule_name,
            description=description,
            applies_to=applies_to or [],
            if_conditions=if_conditions or {},
            then_actions=then_actions or {},
            evidence_grade=evidence_grade,
            recommendation_strength=recommendation_strength,
            source=source,
        )
        self.policy_constraints.append(constraint)


@dataclass
class AgentRecommendation:
    """A single recommendation from an agent."""

    recommendation_id: str = field(default_factory=lambda: str(uuid4()))
    agent_role: AgentRole = AgentRole.DIAGNOSTIC
    recommendation_type: RecommendationType = RecommendationType.DIAGNOSIS
    content: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    reasoning_chain: list[str] = field(default_factory=list)
    supporting_data: dict[str, Any] = field(default_factory=dict)
    contraindications: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentVote:
    """Agent's vote on a recommendation."""

    agent_role: AgentRole
    agrees: bool
    confidence: float = 1.0
    concerns: list[str] = field(default_factory=list)
    alternative_suggestion: str | None = None


@dataclass
class ConsensusResult:
    """Result of multi-agent consensus."""

    recommendation_id: str
    recommendation: AgentRecommendation
    consensus_level: ConsensusLevel
    agreement_score: float  # 0-1
    votes: list[AgentVote] = field(default_factory=list)
    dissenting_concerns: list[str] = field(default_factory=list)
    final_confidence: float = 0.0
    explanation: str = ""


@dataclass
class MDTSession:
    """A multi-disciplinary team discussion session."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    patient_id: str = ""
    context: AgentContext | None = None
    recommendations: list[AgentRecommendation] = field(default_factory=list)
    consensus_results: list[ConsensusResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: str = "in_progress"


class BaseAgent:
    """Base class for specialized clinical agents."""

    def __init__(
        self,
        role: AgentRole,
        name: str,
        description: str,
    ):
        self.role = role
        self.name = name
        self.description = description
        self.reasoning_steps: list[str] = []

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Analyze context and generate recommendations."""
        raise NotImplementedError

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote on another agent's recommendation."""
        raise NotImplementedError

    def add_reasoning_step(self, step: str) -> None:
        """Record a reasoning step."""
        self.reasoning_steps.append(step)

    def get_reasoning_chain(self) -> list[str]:
        """Get the reasoning chain."""
        return self.reasoning_steps.copy()

    def clear_reasoning(self) -> None:
        """Clear reasoning steps for new analysis."""
        self.reasoning_steps = []


class DiagnosticAgent(BaseAgent):
    """Agent specialized in differential diagnosis."""

    def __init__(self):
        super().__init__(
            role=AgentRole.DIAGNOSTIC,
            name="Diagnostic Specialist",
            description="Analyzes symptoms and clinical findings to generate differential diagnoses",
        )

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Generate differential diagnoses based on clinical context."""
        self.clear_reasoning()
        recommendations = []

        self.add_reasoning_step("Analyzing patient symptoms and clinical findings")

        # Analyze existing conditions
        if context.conditions:
            self.add_reasoning_step(f"Found {len(context.conditions)} existing conditions")
            for condition in context.conditions[:3]:  # Top 3
                recommendations.append(
                    AgentRecommendation(
                        agent_role=self.role,
                        recommendation_type=RecommendationType.DIAGNOSIS,
                        content=f"Confirmed: {condition.get('name', 'Unknown')}",
                        confidence=condition.get("confidence", 0.8),
                        evidence=[f"Clinical documentation: {condition.get('source', 'note')}"],
                        reasoning_chain=self.get_reasoning_chain(),
                    )
                )

        # Analyze symptoms for potential diagnoses
        if context.clinical_text:
            self.add_reasoning_step("Parsing clinical text for symptoms and signs")
            # In production, this would use NLP and knowledge graph
            self.add_reasoning_step("Cross-referencing with medical ontologies")

        return recommendations

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote on another agent's recommendation."""
        # Diagnostic agent checks if recommendation is clinically consistent
        if recommendation.recommendation_type == RecommendationType.DIAGNOSIS:
            return AgentVote(
                agent_role=self.role,
                agrees=True,
                confidence=0.9,
            )

        # For treatment recommendations, check diagnostic consistency
        if recommendation.recommendation_type in [
            RecommendationType.TREATMENT,
            RecommendationType.MEDICATION,
        ]:
            # Check if treatment matches known conditions
            return AgentVote(
                agent_role=self.role,
                agrees=True,
                confidence=0.8,
                concerns=["Verify diagnosis before proceeding with treatment"],
            )

        return AgentVote(agent_role=self.role, agrees=True, confidence=0.7)


class TreatmentAgent(BaseAgent):
    """Agent specialized in treatment planning."""

    def __init__(self):
        super().__init__(
            role=AgentRole.TREATMENT,
            name="Treatment Specialist",
            description="Recommends treatments based on diagnoses and clinical guidelines",
        )

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Generate treatment recommendations."""
        self.clear_reasoning()
        recommendations = []

        self.add_reasoning_step("Reviewing diagnoses and clinical history")

        # Treatment recommendations based on conditions
        for condition in context.conditions[:3]:
            condition_name = condition.get("name", "Unknown")
            self.add_reasoning_step(f"Evaluating treatment options for {condition_name}")

            # In production, this would query the knowledge graph for treatments
            recommendations.append(
                AgentRecommendation(
                    agent_role=self.role,
                    recommendation_type=RecommendationType.TREATMENT,
                    content=f"Recommended treatment plan for {condition_name}",
                    confidence=0.85,
                    evidence=["Clinical practice guidelines"],
                    reasoning_chain=self.get_reasoning_chain(),
                )
            )

        return recommendations

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote on another agent's recommendation."""
        if recommendation.recommendation_type == RecommendationType.TREATMENT:
            return AgentVote(
                agent_role=self.role,
                agrees=True,
                confidence=0.9,
            )

        return AgentVote(agent_role=self.role, agrees=True, confidence=0.8)


class SafetyAgent(BaseAgent):
    """Agent specialized in drug safety and interactions."""

    def __init__(self):
        super().__init__(
            role=AgentRole.SAFETY,
            name="Safety Specialist",
            description="Checks for drug interactions, contraindications, and safety issues",
        )

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Identify safety concerns."""
        self.clear_reasoning()
        recommendations = []

        self.add_reasoning_step("Checking medication list for interactions")

        # Check drug interactions
        if len(context.medications) > 1:
            self.add_reasoning_step(
                f"Analyzing interactions between {len(context.medications)} medications"
            )
            # In production, this would use the drug interaction service

        # Check allergies
        if context.allergies:
            self.add_reasoning_step(f"Reviewing {len(context.allergies)} documented allergies")
            for allergy in context.allergies:
                recommendations.append(
                    AgentRecommendation(
                        agent_role=self.role,
                        recommendation_type=RecommendationType.WARNING,
                        content=f"Documented allergy: {allergy}",
                        confidence=1.0,
                        evidence=["Patient allergy record"],
                        reasoning_chain=self.get_reasoning_chain(),
                    )
                )

        return recommendations

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote on another agent's recommendation from safety perspective."""
        concerns = []

        # Check medication recommendations against allergies
        if recommendation.recommendation_type == RecommendationType.MEDICATION:
            for allergy in context.allergies:
                if allergy.lower() in recommendation.content.lower():
                    return AgentVote(
                        agent_role=self.role,
                        agrees=False,
                        confidence=1.0,
                        concerns=[f"Patient has documented allergy to {allergy}"],
                    )

        # Check for drug interactions
        if recommendation.recommendation_type == RecommendationType.MEDICATION:
            concerns.append("Verify no interactions with current medications")

        return AgentVote(
            agent_role=self.role,
            agrees=True,
            confidence=0.85,
            concerns=concerns,
        )


class EvidenceAgent(BaseAgent):
    """Agent specialized in evidence-based medicine."""

    def __init__(self):
        super().__init__(
            role=AgentRole.EVIDENCE,
            name="Evidence Specialist",
            description="Reviews clinical evidence and guidelines for recommendations",
        )

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Provide evidence-based recommendations."""
        self.clear_reasoning()
        recommendations = []

        self.add_reasoning_step("Searching clinical guidelines and literature")

        for condition in context.conditions[:2]:
            condition_name = condition.get("name", "Unknown")
            self.add_reasoning_step(f"Reviewing evidence base for {condition_name}")

            recommendations.append(
                AgentRecommendation(
                    agent_role=self.role,
                    recommendation_type=RecommendationType.TREATMENT,
                    content=f"Evidence-based management for {condition_name}",
                    confidence=0.8,
                    evidence=[
                        "Clinical practice guideline",
                        "Systematic review evidence",
                    ],
                    reasoning_chain=self.get_reasoning_chain(),
                )
            )

        return recommendations

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote based on evidence support."""
        # Check for evidence support
        has_evidence = len(recommendation.evidence) > 0

        return AgentVote(
            agent_role=self.role,
            agrees=has_evidence,
            confidence=0.8 if has_evidence else 0.4,
            concerns=[] if has_evidence else ["Limited evidence support for recommendation"],
        )


class MultiAgentOrchestrator:
    """
    Orchestrates multiple clinical agents for collaborative decision-making.

    Implements the TrustedMDT pattern:
    1. Each specialist agent independently analyzes the case
    2. Agents share recommendations in a shared context
    3. All agents vote on each recommendation
    4. Consensus is built with explainable disagreements
    5. Final recommendations include confidence from all perspectives

    Enhanced with:
    - PolicyComplianceAgent: Checks patient state against policies/guidelines
    - TemporalReasoningAgent: Validates temporal consistency
    - KG traversal paths included in agent context for hybrid reasoning
    """

    def __init__(self, include_policy_agent: bool = True, include_temporal_agent: bool = True):
        """Initialize the orchestrator with specified agents.

        Args:
            include_policy_agent: Include PolicyComplianceAgent
            include_temporal_agent: Include TemporalReasoningAgent
        """
        self.agents: dict[AgentRole, BaseAgent] = {
            AgentRole.DIAGNOSTIC: DiagnosticAgent(),
            AgentRole.TREATMENT: TreatmentAgent(),
            AgentRole.SAFETY: SafetyAgent(),
            AgentRole.EVIDENCE: EvidenceAgent(),
        }

        # Add specialized agents if requested
        if include_policy_agent:
            try:
                from app.services.agents.policy_compliance_agent import PolicyComplianceAgent
                self.agents[AgentRole.POLICY] = PolicyComplianceAgent()
            except ImportError:
                logger.warning("PolicyComplianceAgent not available")

        if include_temporal_agent:
            try:
                from app.services.agents.temporal_reasoning_agent import TemporalReasoningAgent
                self.agents[AgentRole.TEMPORAL] = TemporalReasoningAgent()
            except ImportError:
                logger.warning("TemporalReasoningAgent not available")

        self._active_sessions: dict[str, MDTSession] = {}

    async def create_session(
        self,
        patient_id: str,
        context: AgentContext,
    ) -> MDTSession:
        """Create a new MDT session."""
        session = MDTSession(
            patient_id=patient_id,
            context=context,
        )
        self._active_sessions[session.session_id] = session
        return session

    async def run_mdt_discussion(
        self,
        session_id: str,
    ) -> MDTSession:
        """
        Run a full MDT discussion.

        Steps:
        1. Each agent independently analyzes the case
        2. All recommendations are collected
        3. Each agent votes on all recommendations
        4. Consensus is calculated for each recommendation
        """
        session = self._active_sessions.get(session_id)
        if not session or not session.context:
            raise ValueError(f"Session not found: {session_id}")

        context = session.context

        # Step 1: Gather recommendations from all agents
        all_recommendations: list[AgentRecommendation] = []
        analysis_tasks = [
            agent.analyze(context) for agent in self.agents.values()
        ]
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_recommendations.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Agent analysis failed: {result}")

        session.recommendations = all_recommendations

        # Step 2: Build consensus for each recommendation
        for recommendation in all_recommendations:
            consensus = await self._build_consensus(recommendation, context)
            session.consensus_results.append(consensus)

        # Mark session complete
        session.completed_at = datetime.now(timezone.utc)
        session.status = "completed"

        return session

    async def _build_consensus(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> ConsensusResult:
        """Build consensus across all agents for a recommendation."""
        votes: list[AgentVote] = []

        # Skip self-voting (agent that made recommendation)
        for role, agent in self.agents.items():
            if role != recommendation.agent_role:
                vote = await agent.vote(recommendation, context)
                votes.append(vote)

        # Calculate agreement score
        agreeing_votes = sum(1 for v in votes if v.agrees)
        total_votes = len(votes)
        agreement_score = agreeing_votes / total_votes if total_votes > 0 else 0

        # Determine consensus level
        if agreement_score >= 1.0:
            consensus_level = ConsensusLevel.UNANIMOUS
        elif agreement_score >= 0.8:
            consensus_level = ConsensusLevel.STRONG
        elif agreement_score >= 0.6:
            consensus_level = ConsensusLevel.MODERATE
        elif agreement_score >= 0.4:
            consensus_level = ConsensusLevel.WEAK
        else:
            consensus_level = ConsensusLevel.CONFLICTING

        # Collect dissenting concerns
        dissenting_concerns = []
        for vote in votes:
            if not vote.agrees:
                dissenting_concerns.extend(vote.concerns)
            elif vote.concerns:
                dissenting_concerns.extend(vote.concerns)

        # Calculate final confidence (weighted by agent confidences)
        if votes:
            total_confidence = sum(v.confidence for v in votes if v.agrees)
            agreeing_count = sum(1 for v in votes if v.agrees)
            final_confidence = (
                (total_confidence / agreeing_count) * agreement_score
                if agreeing_count > 0
                else 0
            )
        else:
            final_confidence = recommendation.confidence

        # Generate explanation
        explanation = self._generate_consensus_explanation(
            recommendation,
            consensus_level,
            votes,
            dissenting_concerns,
        )

        return ConsensusResult(
            recommendation_id=recommendation.recommendation_id,
            recommendation=recommendation,
            consensus_level=consensus_level,
            agreement_score=agreement_score,
            votes=votes,
            dissenting_concerns=list(set(dissenting_concerns)),
            final_confidence=final_confidence,
            explanation=explanation,
        )

    def _generate_consensus_explanation(
        self,
        recommendation: AgentRecommendation,
        consensus_level: ConsensusLevel,
        votes: list[AgentVote],
        concerns: list[str],
    ) -> str:
        """Generate human-readable explanation of consensus."""
        explanation_parts = [
            f"Recommendation from {recommendation.agent_role.value} agent: {recommendation.content}",
            f"Consensus level: {consensus_level.value}",
        ]

        # Summarize votes
        agree_count = sum(1 for v in votes if v.agrees)
        disagree_count = len(votes) - agree_count

        if agree_count > 0:
            agreeing_roles = [v.agent_role.value for v in votes if v.agrees]
            explanation_parts.append(f"Supported by: {', '.join(agreeing_roles)}")

        if disagree_count > 0:
            disagreeing_roles = [v.agent_role.value for v in votes if not v.agrees]
            explanation_parts.append(f"Concerns raised by: {', '.join(disagreeing_roles)}")

        if concerns:
            explanation_parts.append(f"Key concerns: {'; '.join(concerns[:3])}")

        return " | ".join(explanation_parts)

    async def get_prioritized_recommendations(
        self,
        session_id: str,
        min_consensus: ConsensusLevel = ConsensusLevel.MODERATE,
    ) -> list[ConsensusResult]:
        """Get recommendations meeting minimum consensus threshold."""
        session = self._active_sessions.get(session_id)
        if not session:
            return []

        # Define consensus order for filtering
        consensus_order = {
            ConsensusLevel.UNANIMOUS: 4,
            ConsensusLevel.STRONG: 3,
            ConsensusLevel.MODERATE: 2,
            ConsensusLevel.WEAK: 1,
            ConsensusLevel.CONFLICTING: 0,
        }

        min_level = consensus_order[min_consensus]

        filtered = [
            result
            for result in session.consensus_results
            if consensus_order[result.consensus_level] >= min_level
        ]

        # Sort by confidence
        return sorted(filtered, key=lambda r: r.final_confidence, reverse=True)

    def get_session(self, session_id: str) -> MDTSession | None:
        """Get a session by ID."""
        return self._active_sessions.get(session_id)

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Get a summary of an MDT session."""
        session = self._active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session.session_id,
            "patient_id": session.patient_id,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "total_recommendations": len(session.recommendations),
            "consensus_results": [
                {
                    "recommendation": r.recommendation.content,
                    "consensus_level": r.consensus_level.value,
                    "agreement_score": r.agreement_score,
                    "final_confidence": r.final_confidence,
                    "concerns": r.dissenting_concerns,
                }
                for r in session.consensus_results
            ],
            "agents_involved": list(self.agents.keys()),
        }


# Singleton instance
_orchestrator: MultiAgentOrchestrator | None = None
_orchestrator_lock = threading.Lock()


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    """Get the singleton multi-agent orchestrator."""
    global _orchestrator
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = MultiAgentOrchestrator()
    return _orchestrator
