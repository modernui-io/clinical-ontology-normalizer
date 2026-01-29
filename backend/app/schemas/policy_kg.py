"""Pydantic schemas for Policy Knowledge Graph.

These schemas define the API interface for the Policy KG,
which encodes clinical guidelines and decision rules.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyNodeType(str, Enum):
    """Types of nodes in the policy knowledge graph."""

    RULE = "rule"
    CONDITION = "condition"
    ACTION = "action"
    EXCEPTION = "exception"
    EVIDENCE = "evidence"
    CONCEPT = "concept"
    THRESHOLD = "threshold"
    TIMEFRAME = "timeframe"


class PolicyEdgeType(str, Enum):
    """Types of edges in the policy knowledge graph."""

    IF_THEN = "if_then"
    UNLESS = "unless"
    REQUIRES = "requires"
    RECOMMENDS = "recommends"
    CONTRAINDICATES = "contraindicates"
    SUPPORTED_BY = "supported_by"
    AND = "and"
    OR = "or"
    NOT = "not"
    BEFORE = "before"
    AFTER = "after"
    WITHIN = "within"
    APPLIES_TO = "applies_to"
    REFERENCES = "references"
    SUPERSEDES = "supersedes"


class EvidenceGrade(str, Enum):
    """Evidence grading levels."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    EXPERT = "expert"


class RecommendationStrength(str, Enum):
    """Strength of recommendations."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    OPTIONAL = "optional"


# =============================================================================
# Policy KG Node Schemas
# =============================================================================


class PolicyKGNodeCreate(BaseModel):
    """Schema for creating a policy KG node."""

    policy_section_id: UUID | None = Field(
        None, description="Source policy section ID"
    )
    node_type: PolicyNodeType = Field(..., description="Type of policy node")
    label: str = Field(..., description="Human-readable label", max_length=500)
    description: str | None = Field(None, description="Detailed description")
    omop_concept_ids: list[int] | None = Field(
        None, description="Related OMOP concept IDs"
    )
    snomed_codes: list[str] | None = Field(None, description="Related SNOMED codes")
    icd10_codes: list[str] | None = Field(None, description="Related ICD-10 codes")
    evidence_grade: EvidenceGrade | None = Field(None, description="Evidence grade")
    recommendation_strength: RecommendationStrength | None = Field(
        None, description="Recommendation strength"
    )
    rule_logic: dict[str, Any] | None = Field(
        None, description="Structured rule logic (for RULE nodes)"
    )
    effective_from: datetime | None = Field(
        None, description="When this node became effective"
    )
    effective_to: datetime | None = Field(
        None, description="When this node was superseded"
    )
    source_text: str | None = Field(None, description="Original source text")


class PolicyKGNode(BaseModel):
    """Schema for a policy KG node response."""

    id: UUID = Field(..., description="Node ID")
    policy_section_id: UUID | None = Field(None, description="Source policy section")
    node_type: PolicyNodeType = Field(..., description="Type of node")
    label: str = Field(..., description="Human-readable label")
    description: str | None = Field(None, description="Detailed description")
    omop_concept_ids: list[int] | None = Field(None, description="OMOP concept IDs")
    snomed_codes: list[str] | None = Field(None, description="SNOMED codes")
    icd10_codes: list[str] | None = Field(None, description="ICD-10 codes")
    evidence_grade: str | None = Field(None, description="Evidence grade")
    recommendation_strength: str | None = Field(None, description="Recommendation")
    rule_logic: dict[str, Any] | None = Field(None, description="Rule logic")
    effective_from: datetime | None = Field(None, description="Effective from")
    effective_to: datetime | None = Field(None, description="Effective to")
    extraction_confidence: float | None = Field(None, description="Extraction confidence")
    source_text: str | None = Field(None, description="Source text")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


# =============================================================================
# Policy KG Edge Schemas
# =============================================================================


class PolicyKGEdgeCreate(BaseModel):
    """Schema for creating a policy KG edge."""

    source_node_id: UUID = Field(..., description="Source node ID")
    target_node_id: UUID = Field(..., description="Target node ID")
    edge_type: PolicyEdgeType = Field(..., description="Type of relationship")
    properties: dict[str, Any] | None = Field(None, description="Edge properties")
    conditions: dict[str, Any] | None = Field(
        None, description="Triggering conditions"
    )
    effective_from: datetime | None = Field(None, description="Effective from")
    effective_to: datetime | None = Field(None, description="Effective to")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence")


class PolicyKGEdge(BaseModel):
    """Schema for a policy KG edge response."""

    id: UUID = Field(..., description="Edge ID")
    source_node_id: UUID = Field(..., description="Source node ID")
    target_node_id: UUID = Field(..., description="Target node ID")
    edge_type: str = Field(..., description="Type of relationship")
    properties: dict[str, Any] | None = Field(None, description="Edge properties")
    conditions: dict[str, Any] | None = Field(None, description="Conditions")
    effective_from: datetime | None = Field(None, description="Effective from")
    effective_to: datetime | None = Field(None, description="Effective to")
    confidence: float | None = Field(None, description="Confidence score")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


# =============================================================================
# Policy Rule Schemas
# =============================================================================


class RuleCondition(BaseModel):
    """A single condition in a rule's IF clause."""

    field: str = Field(..., description="Field to check (e.g., 'age', 'has_condition')")
    operator: str = Field(
        ..., description="Comparison operator (e.g., '>', '==', 'contains')"
    )
    value: Any = Field(..., description="Value to compare against")
    unit: str | None = Field(None, description="Unit for numeric values")


class RuleAction(BaseModel):
    """A single action in a rule's THEN clause."""

    action_type: str = Field(
        ..., description="Type of action (e.g., 'recommend', 'alert', 'order')"
    )
    target: str = Field(..., description="Target of the action")
    priority: str | None = Field(None, description="Priority level")
    rationale: str | None = Field(None, description="Reason for the action")


class PolicyRuleCreate(BaseModel):
    """Schema for creating a policy rule."""

    rule_id: str = Field(
        ..., description="Unique rule identifier", max_length=100, pattern=r"^[A-Z0-9_]+$"
    )
    name: str = Field(..., description="Human-readable name", max_length=500)
    description: str | None = Field(None, description="Detailed description")
    policy_section_id: UUID | None = Field(None, description="Source policy section")
    if_conditions: dict[str, Any] = Field(..., description="IF conditions")
    then_actions: dict[str, Any] = Field(..., description="THEN actions")
    unless_exceptions: dict[str, Any] | None = Field(
        None, description="UNLESS exceptions"
    )
    applies_to_conditions: list[str] | None = Field(
        None, description="Applicable conditions"
    )
    applies_to_medications: list[str] | None = Field(
        None, description="Applicable medications"
    )
    applies_to_measurements: list[str] | None = Field(
        None, description="Applicable measurements"
    )
    evidence_grade: EvidenceGrade | None = Field(None, description="Evidence grade")
    recommendation_strength: RecommendationStrength | None = Field(
        None, description="Recommendation strength"
    )
    effective_from: datetime | None = Field(None, description="Effective from date")
    effective_to: datetime | None = Field(None, description="Effective to date")


class PolicyRule(BaseModel):
    """Schema for a policy rule response."""

    id: UUID = Field(..., description="Rule database ID")
    rule_id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable name")
    description: str | None = Field(None, description="Detailed description")
    policy_section_id: UUID | None = Field(None, description="Source policy section")
    policy_kg_node_id: UUID | None = Field(None, description="Linked PolicyKG node")
    if_conditions: dict[str, Any] = Field(..., description="IF conditions")
    then_actions: dict[str, Any] = Field(..., description="THEN actions")
    unless_exceptions: dict[str, Any] | None = Field(None, description="Exceptions")
    applies_to_conditions: list[str] | None = Field(None, description="Conditions")
    applies_to_medications: list[str] | None = Field(None, description="Medications")
    applies_to_measurements: list[str] | None = Field(None, description="Measurements")
    evidence_grade: str | None = Field(None, description="Evidence grade")
    recommendation_strength: str | None = Field(None, description="Recommendation")
    effective_from: datetime | None = Field(None, description="Effective from")
    effective_to: datetime | None = Field(None, description="Effective to")
    is_active: bool = Field(True, description="Whether rule is active")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


# =============================================================================
# Graph Query Schemas
# =============================================================================


class PolicyKGQuery(BaseModel):
    """Query parameters for searching the policy KG."""

    query: str | None = Field(None, description="Semantic search query")
    node_types: list[PolicyNodeType] | None = Field(
        None, description="Filter by node types"
    )
    edge_types: list[PolicyEdgeType] | None = Field(
        None, description="Filter by edge types"
    )
    omop_concept_ids: list[int] | None = Field(
        None, description="Filter by OMOP concept IDs"
    )
    evidence_grade: list[EvidenceGrade] | None = Field(
        None, description="Filter by evidence grade"
    )
    effective_at: datetime | None = Field(
        None, description="Filter by effective date"
    )
    include_inactive: bool = Field(
        False, description="Include superseded/inactive nodes"
    )
    max_hops: int = Field(2, ge=1, le=5, description="Max traversal depth")
    limit: int = Field(50, ge=1, le=200, description="Max results")


class PolicyKGSubgraph(BaseModel):
    """A subgraph from the policy knowledge graph."""

    nodes: list[PolicyKGNode] = Field(
        default_factory=list, description="Nodes in the subgraph"
    )
    edges: list[PolicyKGEdge] = Field(
        default_factory=list, description="Edges in the subgraph"
    )
    node_count: int = Field(0, description="Total nodes")
    edge_count: int = Field(0, description="Total edges")
    query_info: dict[str, Any] | None = Field(None, description="Query metadata")


class PolicyRuleMatch(BaseModel):
    """A rule that matches a patient context."""

    rule: PolicyRule = Field(..., description="The matching rule")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Match score")
    matched_conditions: list[str] = Field(
        default_factory=list, description="Conditions that matched"
    )
    unmatched_conditions: list[str] = Field(
        default_factory=list, description="Conditions that didn't match"
    )
    applicable_actions: list[dict[str, Any]] = Field(
        default_factory=list, description="Actions to consider"
    )
    exceptions_triggered: list[str] = Field(
        default_factory=list, description="Triggered exceptions"
    )


class PolicyComplianceResult(BaseModel):
    """Result of checking patient state against policy rules."""

    patient_id: str = Field(..., description="Patient identifier")
    rules_evaluated: int = Field(0, description="Number of rules evaluated")
    compliant_rules: list[PolicyRuleMatch] = Field(
        default_factory=list, description="Rules patient is compliant with"
    )
    non_compliant_rules: list[PolicyRuleMatch] = Field(
        default_factory=list, description="Rules patient is not compliant with"
    )
    recommended_actions: list[dict[str, Any]] = Field(
        default_factory=list, description="Recommended actions based on policy"
    )
    evaluation_timestamp: datetime = Field(
        ..., description="When evaluation was performed"
    )
