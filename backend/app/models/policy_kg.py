"""SQLAlchemy models for Policy Knowledge Graph.

The Policy Knowledge Graph encodes clinical guidelines, institutional policies,
and decision rules as a structured graph for machine reasoning.

This is separate from the patient knowledge graph because:
1. Policies are stable and versioned; patient data is dynamic
2. Policies apply across all patients; separation enables reuse
3. Different update cadences and access patterns
4. Cleaner compliance auditing
5. Can be pre-computed and cached

Models:
- PolicyKGNode: Nodes representing rules, conditions, actions, exceptions, evidence
- PolicyKGEdge: Relationships between policy nodes (REQUIRES, RECOMMENDS, etc.)
- PolicyRule: Structured IF-THEN-ELSE rule extracted from policy sections

Based on research from Decision Knowledge Graphs for Clinical Practice Guidelines
and temporal knowledge graph reasoning patterns.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PolicyNodeType(str, Enum):
    """Types of nodes in the policy knowledge graph."""

    RULE = "rule"  # Decision rule (IF-THEN structure)
    CONDITION = "condition"  # Triggering condition (IF part)
    ACTION = "action"  # Recommended action (THEN part)
    EXCEPTION = "exception"  # Exception or contraindication (UNLESS part)
    EVIDENCE = "evidence"  # Supporting evidence or rationale
    CONCEPT = "concept"  # Medical concept referenced by rules
    THRESHOLD = "threshold"  # Numeric threshold for conditions
    TIMEFRAME = "timeframe"  # Temporal requirement (e.g., "within 30 days")


class PolicyEdgeType(str, Enum):
    """Types of edges in the policy knowledge graph."""

    # Rule structure edges
    IF_THEN = "if_then"  # Condition → Action
    UNLESS = "unless"  # Rule → Exception
    REQUIRES = "requires"  # Action requires prerequisite
    RECOMMENDS = "recommends"  # Softer recommendation
    CONTRAINDICATES = "contraindicates"  # Should NOT do
    SUPPORTED_BY = "supported_by"  # Rule → Evidence

    # Logical edges
    AND = "and"  # Both conditions must be true
    OR = "or"  # Either condition can be true
    NOT = "not"  # Negation

    # Temporal edges
    BEFORE = "before"  # Must occur before
    AFTER = "after"  # Must occur after
    WITHIN = "within"  # Must occur within timeframe

    # Concept edges
    APPLIES_TO = "applies_to"  # Rule applies to concept
    REFERENCES = "references"  # References another concept
    SUPERSEDES = "supersedes"  # Newer rule supersedes older


class EvidenceGrade(str, Enum):
    """Evidence grading levels for recommendations."""

    A = "A"  # High-quality evidence
    B = "B"  # Moderate-quality evidence
    C = "C"  # Low-quality evidence
    D = "D"  # Very low-quality evidence
    EXPERT = "expert"  # Expert consensus


class RecommendationStrength(str, Enum):
    """Strength of recommendations."""

    STRONG = "strong"  # Strong recommendation
    MODERATE = "moderate"  # Moderate recommendation
    WEAK = "weak"  # Weak/conditional recommendation
    OPTIONAL = "optional"  # Optional consideration


class PolicyKGNode(Base):
    """Node in the policy knowledge graph.

    Represents policy elements that can be reasoned over:
    - Rules: IF-THEN structures encoding clinical guidance
    - Conditions: Triggering conditions for rules
    - Actions: Recommended clinical actions
    - Exceptions: Contraindications and exceptions
    - Evidence: Supporting research and guidelines
    """

    __tablename__ = "policy_kg_nodes"

    # Source linkage
    policy_section_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policy_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Source policy section this node was extracted from",
    )

    # Node type and identity
    node_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Type of policy node (rule, condition, action, etc.)",
    )
    label: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Human-readable label for the node",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description or the full text of the rule",
    )

    # Medical concept linkage
    omop_concept_ids: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        doc="OMOP concept IDs this node relates to",
    )
    snomed_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="SNOMED CT codes this node relates to",
    )
    icd10_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="ICD-10 codes this node relates to",
    )

    # Evidence grading
    evidence_grade: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Evidence grade (A, B, C, D, Expert)",
    )
    recommendation_strength: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Recommendation strength (strong, moderate, weak)",
    )

    # Structured rule components (for RULE type nodes)
    rule_logic: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Structured rule logic in JSON format",
    )

    # Temporal validity
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When this rule became effective",
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When this rule was superseded (null = current)",
    )

    # Semantic search
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
        doc="Vector embedding for semantic search (384 dimensions)",
    )

    # Confidence and provenance
    extraction_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Confidence score for automated extraction (0-1)",
    )
    source_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Original source text this node was extracted from",
    )

    # Relationships
    policy_section = relationship("PolicySection")
    outgoing_edges = relationship(
        "PolicyKGEdge",
        foreign_keys="PolicyKGEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "PolicyKGEdge",
        foreign_keys="PolicyKGEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_policy_kg_nodes_type_label", "node_type", "label"),
        Index("ix_policy_kg_nodes_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:
        return f"<PolicyKGNode(id={self.id}, type={self.node_type}, label='{self.label[:50]}')>"

    @property
    def is_currently_effective(self) -> bool:
        """Check if this node is currently in effect."""
        if self.effective_to is None:
            return True
        from datetime import timezone

        return self.effective_to > datetime.now(timezone.utc)


class PolicyKGEdge(Base):
    """Edge in the policy knowledge graph.

    Represents relationships between policy elements:
    - IF_THEN: Links conditions to actions
    - REQUIRES: Action requires prerequisite
    - CONTRAINDICATES: Action is contraindicated
    - SUPPORTED_BY: Rule is supported by evidence
    """

    __tablename__ = "policy_kg_edges"

    # Node references
    source_node_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policy_kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policy_kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Edge type
    edge_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Type of relationship between nodes",
    )

    # Edge properties
    properties: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        doc="Additional edge properties",
    )

    # Conditions for the edge (e.g., thresholds, timeframes)
    conditions: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Triggering conditions for this relationship",
    )

    # Temporal validity (when this edge is in effect)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Confidence
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Confidence in this relationship (0-1)",
    )

    # Relationships
    source_node = relationship(
        "PolicyKGNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
    target_node = relationship(
        "PolicyKGNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )

    __table_args__ = (
        Index("ix_policy_kg_edges_type", "edge_type"),
        Index("ix_policy_kg_edges_source_target", "source_node_id", "target_node_id"),
        Index("ix_policy_kg_edges_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:
        return f"<PolicyKGEdge(id={self.id}, type={self.edge_type}, {self.source_node_id} → {self.target_node_id})>"


class PolicyRule(Base):
    """Structured clinical decision rule extracted from policies.

    Provides a higher-level abstraction for common IF-THEN-ELSE patterns.
    Links to PolicyKGNodes for detailed graph-based reasoning.
    """

    __tablename__ = "policy_rules"

    # Rule identification
    rule_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique rule identifier (e.g., 'HYPERTENSION_001')",
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Human-readable rule name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description of the rule",
    )

    # Source linkage
    policy_section_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policy_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    policy_kg_node_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policy_kg_nodes.id", ondelete="SET NULL"),
        nullable=True,
        doc="Link to the RULE node in the PolicyKG",
    )

    # Structured rule components
    if_conditions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="IF conditions as structured JSON",
    )
    then_actions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="THEN actions as structured JSON",
    )
    unless_exceptions: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="UNLESS exceptions as structured JSON",
    )

    # Medical concept applicability
    applies_to_conditions: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Condition names this rule applies to",
    )
    applies_to_medications: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Medication names this rule applies to",
    )
    applies_to_measurements: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Measurement names this rule applies to",
    )

    # Evidence grading
    evidence_grade: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    recommendation_strength: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Lifecycle
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        doc="Whether this rule is currently active",
    )

    # Semantic search
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )

    # Relationships
    policy_section = relationship("PolicySection")
    policy_kg_node = relationship("PolicyKGNode")

    __table_args__ = (
        Index("ix_policy_rules_active", "is_active"),
        Index("ix_policy_rules_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:
        return f"<PolicyRule(rule_id={self.rule_id}, name='{self.name[:50]}')>"

    def to_prompt_context(self) -> str:
        """Format this rule for inclusion in LLM prompts."""
        lines = [
            f"Rule: {self.rule_id}",
            f"  Name: {self.name}",
        ]
        if self.description:
            lines.append(f"  Description: {self.description[:200]}")

        # Format conditions
        if self.if_conditions:
            lines.append("  IF:")
            for key, value in self.if_conditions.items():
                lines.append(f"    - {key}: {value}")

        # Format actions
        if self.then_actions:
            lines.append("  THEN:")
            for key, value in self.then_actions.items():
                lines.append(f"    - {key}: {value}")

        # Format exceptions
        if self.unless_exceptions:
            lines.append("  UNLESS:")
            for key, value in self.unless_exceptions.items():
                lines.append(f"    - {key}: {value}")

        if self.evidence_grade:
            lines.append(f"  Evidence Grade: {self.evidence_grade}")
        if self.recommendation_strength:
            lines.append(f"  Recommendation: {self.recommendation_strength}")

        return "\n".join(lines)
