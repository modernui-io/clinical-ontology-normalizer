"""OpenAPI schemas and examples for Knowledge Graph API endpoints.

This module provides comprehensive Pydantic models with OpenAPI documentation,
examples, and JSON schemas for all KG API endpoints. These models ensure
consistent API documentation and enable client code generation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Common Enums
# ============================================================================

class HealthStatus(str, Enum):
    """Health status levels for components and services."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SemanticGroup(str, Enum):
    """UMLS Semantic Groups for concept categorization."""

    ANAT = "ANAT"  # Anatomy
    CHEM = "CHEM"  # Chemicals & Drugs
    DISO = "DISO"  # Disorders
    GENE = "GENE"  # Genes & Molecular Sequences
    LIVB = "LIVB"  # Living Beings
    OBJC = "OBJC"  # Objects
    OCCU = "OCCU"  # Occupations
    ORGA = "ORGA"  # Organizations
    PHEN = "PHEN"  # Phenomena
    PHYS = "PHYS"  # Physiology
    PROC = "PROC"  # Procedures
    CONC = "CONC"  # Concepts & Ideas
    DEVI = "DEVI"  # Devices
    GEOG = "GEOG"  # Geographic Areas
    ACTV = "ACTV"  # Activities & Behaviors


class RelationshipType(str, Enum):
    """Common UMLS relationship types."""

    IS_A = "is_a"
    PART_OF = "part_of"
    MAY_TREAT = "may_treat"
    MAY_CAUSE = "may_cause"
    CAUSES = "causes"
    PREVENTS = "prevents"
    DIAGNOSES = "diagnoses"
    ASSOCIATED_WITH = "associated_with"
    CONTRAINDICATED_WITH = "contraindicated_with"
    INTERACTS_WITH = "interacts_with"


# ============================================================================
# Concept Models
# ============================================================================

class ConceptSummary(BaseModel):
    """Summary of a UMLS concept."""

    cui: str = Field(
        ...,
        description="UMLS Concept Unique Identifier",
        json_schema_extra={"example": "C0004096"},
    )
    name: str = Field(
        ...,
        description="Preferred term for the concept",
        json_schema_extra={"example": "Asthma"},
    )
    semantic_type: str | None = Field(
        default=None,
        description="UMLS semantic type",
        json_schema_extra={"example": "Disease or Syndrome"},
    )
    semantic_group: SemanticGroup | None = Field(
        default=None,
        description="UMLS semantic group",
        json_schema_extra={"example": "DISO"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "cui": "C0004096",
                "name": "Asthma",
                "semantic_type": "Disease or Syndrome",
                "semantic_group": "DISO",
            }
        }
    }


class ConceptDetail(ConceptSummary):
    """Detailed information about a UMLS concept."""

    sources: list[str] = Field(
        default_factory=list,
        description="Source vocabularies (SNOMEDCT_US, ICD10CM, etc.)",
        json_schema_extra={"example": ["SNOMEDCT_US", "ICD10CM", "NCI"]},
    )
    synonyms: list[str] = Field(
        default_factory=list,
        description="Alternative names and synonyms",
        json_schema_extra={"example": ["Bronchial Asthma", "Asthmatic"]},
    )
    definition: str | None = Field(
        default=None,
        description="Definition from UMLS sources",
    )
    codes: dict[str, str] = Field(
        default_factory=dict,
        description="Mapped codes from other vocabularies",
        json_schema_extra={"example": {"ICD10CM": "J45.909", "SNOMEDCT_US": "195967001"}},
    )


# ============================================================================
# Relationship Models
# ============================================================================

class RelationshipEdge(BaseModel):
    """A relationship between two concepts."""

    source: ConceptSummary = Field(..., description="Source concept")
    target: ConceptSummary = Field(..., description="Target concept")
    relationship_type: str = Field(
        ...,
        description="Type of relationship",
        json_schema_extra={"example": "may_treat"},
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this relationship",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Evidence sources",
    )
    valid_from: datetime | None = Field(
        default=None,
        description="When this relationship became valid",
    )
    valid_to: datetime | None = Field(
        default=None,
        description="When this relationship became invalid",
    )


# ============================================================================
# Path and Reasoning Models
# ============================================================================

class ReasoningStep(BaseModel):
    """A single step in a multi-hop reasoning path."""

    step_number: int = Field(..., description="Step sequence number")
    from_concept: ConceptSummary = Field(..., description="Starting concept")
    to_concept: ConceptSummary = Field(..., description="Ending concept")
    relationship: str = Field(..., description="Relationship type")
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence for this step",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this step",
    )


class ReasoningPath(BaseModel):
    """A complete reasoning path between concepts."""

    path_id: str = Field(..., description="Unique path identifier")
    source: ConceptSummary = Field(..., description="Starting concept")
    target: ConceptSummary = Field(..., description="Ending concept")
    steps: list[ReasoningStep] = Field(..., description="Reasoning steps")
    total_hops: int = Field(..., description="Number of hops in the path")
    aggregate_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Combined confidence score",
    )
    explanation: str | None = Field(
        default=None,
        description="Natural language explanation of the reasoning",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "path_id": "path_001",
                "source": {"cui": "C0011849", "name": "Diabetes Mellitus"},
                "target": {"cui": "C0027051", "name": "Myocardial Infarction"},
                "steps": [
                    {
                        "step_number": 1,
                        "from_concept": {"cui": "C0011849", "name": "Diabetes Mellitus"},
                        "to_concept": {"cui": "C0004153", "name": "Atherosclerosis"},
                        "relationship": "may_cause",
                        "evidence": ["UMLS:C0004153-C0011849"],
                        "confidence": 0.85,
                    },
                    {
                        "step_number": 2,
                        "from_concept": {"cui": "C0004153", "name": "Atherosclerosis"},
                        "to_concept": {"cui": "C0027051", "name": "Myocardial Infarction"},
                        "relationship": "may_cause",
                        "evidence": ["UMLS:C0027051-C0004153"],
                        "confidence": 0.90,
                    },
                ],
                "total_hops": 2,
                "aggregate_confidence": 0.765,
                "explanation": "Diabetes may cause Atherosclerosis, which may lead to Myocardial Infarction",
            }
        }
    }


# ============================================================================
# Clinical Question Answering Models
# ============================================================================

class ClinicalAnswer(BaseModel):
    """Answer to a clinical question."""

    answer: str = Field(..., description="The answer text")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the answer",
    )
    evidence_paths: list[ReasoningPath] = Field(
        default_factory=list,
        description="Supporting reasoning paths",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Source references",
    )
    alternatives: list[str] = Field(
        default_factory=list,
        description="Alternative answers considered",
    )


class ClinicalQuestionResponse(BaseModel):
    """Response to a clinical question."""

    question: str = Field(..., description="Original question")
    answer: ClinicalAnswer = Field(..., description="Primary answer")
    reasoning_mode: str = Field(
        ...,
        description="Reasoning mode used",
        json_schema_extra={"example": "multi_hop"},
    )
    processing_time_ms: float = Field(
        ...,
        description="Time to process the question",
    )
    timestamp: datetime = Field(..., description="Response timestamp")


# ============================================================================
# Patient Graph Models
# ============================================================================

class PatientGraphNode(BaseModel):
    """A node in a patient knowledge graph."""

    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Display label")
    type: str = Field(
        ...,
        description="Node type (condition, medication, procedure, etc.)",
        json_schema_extra={"example": "condition"},
    )
    concept: ConceptSummary | None = Field(
        default=None,
        description="Associated UMLS concept",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional properties",
    )
    temporal: dict[str, datetime | None] = Field(
        default_factory=dict,
        description="Temporal metadata (onset, resolution, etc.)",
    )


class PatientGraphEdge(BaseModel):
    """An edge in a patient knowledge graph."""

    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(
        ...,
        description="Edge type (treats, causes, etc.)",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional properties",
    )


class PatientGraph(BaseModel):
    """A patient-centric knowledge graph."""

    patient_id: str = Field(..., description="Patient identifier")
    nodes: list[PatientGraphNode] = Field(..., description="Graph nodes")
    edges: list[PatientGraphEdge] = Field(..., description="Graph edges")
    node_count: int = Field(..., description="Total node count")
    edge_count: int = Field(..., description="Total edge count")
    generated_at: datetime = Field(..., description="Generation timestamp")


# ============================================================================
# Benchmark Models
# ============================================================================

class BenchmarkMetrics(BaseModel):
    """Metrics from a benchmark run."""

    accuracy: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall accuracy",
    )
    precision: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Precision score",
    )
    recall: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Recall score",
    )
    f1_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="F1 score",
    )
    processing_time_avg_ms: float = Field(
        ...,
        description="Average processing time per case",
    )


class BenchmarkResult(BaseModel):
    """Result of a benchmark run."""

    benchmark_id: str = Field(..., description="Unique benchmark run ID")
    benchmark_type: str = Field(
        ...,
        description="Type of benchmark (medagentbench, drknows, etc.)",
    )
    suite_name: str = Field(..., description="Test suite name")
    metrics: BenchmarkMetrics = Field(..., description="Benchmark metrics")
    cases_run: int = Field(..., description="Number of test cases run")
    cases_passed: int = Field(..., description="Number of cases passed")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: datetime = Field(..., description="Completion timestamp")


# ============================================================================
# Health Monitoring Models
# ============================================================================

class ComponentHealth(BaseModel):
    """Health status of a single component."""

    name: str = Field(
        ...,
        description="Component name",
        json_schema_extra={"example": "graph_database"},
    )
    status: HealthStatus = Field(..., description="Current health status")
    latency_ms: float | None = Field(
        default=None,
        description="Response latency in milliseconds",
    )
    last_check: datetime = Field(..., description="Last health check timestamp")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional health details",
    )
    error: str | None = Field(
        default=None,
        description="Error message if unhealthy",
    )


class DependencyHealth(BaseModel):
    """Health status of an external dependency."""

    name: str = Field(
        ...,
        description="Dependency name",
        json_schema_extra={"example": "neo4j"},
    )
    type: str = Field(
        ...,
        description="Dependency type (database, cache, external_api, etc.)",
    )
    status: HealthStatus = Field(..., description="Current health status")
    endpoint: str | None = Field(
        default=None,
        description="Connection endpoint",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Connection latency",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional details",
    )


class OverallHealth(BaseModel):
    """Overall health status of the KG system."""

    status: HealthStatus = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: list[ComponentHealth] = Field(
        ...,
        description="Individual component health",
    )
    dependencies: list[DependencyHealth] = Field(
        default_factory=list,
        description="External dependency health",
    )
    summary: dict[str, int] = Field(
        ...,
        description="Count of components by status",
        json_schema_extra={"example": {"total_components": 12, "healthy": 10, "degraded": 1, "unhealthy": 1}},
    )
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Aggregate metrics",
    )


class HealthAlert(BaseModel):
    """A health alert for monitoring."""

    severity: str = Field(
        ...,
        description="Alert severity (critical, warning)",
        json_schema_extra={"example": "warning"},
    )
    component: str = Field(..., description="Affected component")
    status: HealthStatus = Field(..., description="Component status")
    message: str = Field(..., description="Alert message")
    timestamp: datetime = Field(..., description="Alert timestamp")


class HealthAlerts(BaseModel):
    """Collection of health alerts."""

    timestamp: datetime = Field(..., description="Query timestamp")
    alert_count: int = Field(..., description="Total alert count")
    alerts: list[HealthAlert] = Field(..., description="Active alerts")


# ============================================================================
# MDT Session Models
# ============================================================================

class AgentRecommendation(BaseModel):
    """A recommendation from a specialized agent."""

    agent_name: str = Field(
        ...,
        description="Name of the recommending agent",
        json_schema_extra={"example": "diagnostic_agent"},
    )
    recommendation: str = Field(..., description="The recommendation text")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the recommendation",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence",
    )
    reasoning: str | None = Field(
        default=None,
        description="Reasoning explanation",
    )


class MDTConsensus(BaseModel):
    """Consensus result from multi-agent discussion."""

    topic: str = Field(..., description="Discussion topic")
    consensus_level: str = Field(
        ...,
        description="Level of consensus (unanimous, majority, split, none)",
        json_schema_extra={"example": "majority"},
    )
    final_recommendation: str = Field(
        ...,
        description="Final agreed recommendation",
    )
    dissenting_views: list[str] = Field(
        default_factory=list,
        description="Dissenting opinions",
    )


class MDTSessionResponse(BaseModel):
    """Response from an MDT session."""

    session_id: str = Field(..., description="Unique session identifier")
    patient_id: str = Field(..., description="Patient identifier")
    status: str = Field(
        ...,
        description="Session status (active, completed, cancelled)",
    )
    agents_involved: list[str] = Field(
        ...,
        description="Names of participating agents",
    )
    recommendations: list[AgentRecommendation] = Field(
        default_factory=list,
        description="Individual agent recommendations",
    )
    consensus_results: list[MDTConsensus] = Field(
        default_factory=list,
        description="Consensus outcomes",
    )
    created_at: datetime = Field(..., description="Session creation timestamp")
    completed_at: datetime | None = Field(
        default=None,
        description="Session completion timestamp",
    )


# ============================================================================
# Export Format Models
# ============================================================================

class D3JSGraph(BaseModel):
    """D3.js-compatible graph format."""

    nodes: list[dict[str, Any]] = Field(..., description="D3.js nodes")
    links: list[dict[str, Any]] = Field(..., description="D3.js links")


class CytoscapeGraph(BaseModel):
    """Cytoscape.js-compatible graph format."""

    elements: dict[str, list[dict[str, Any]]] = Field(
        ...,
        description="Cytoscape elements (nodes and edges)",
    )


class VisJSGraph(BaseModel):
    """vis.js-compatible graph format."""

    nodes: list[dict[str, Any]] = Field(..., description="vis.js nodes")
    edges: list[dict[str, Any]] = Field(..., description="vis.js edges")


# ============================================================================
# Error Response Models
# ============================================================================

class KGErrorDetail(BaseModel):
    """Details about a KG API error."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )
    path: str | None = Field(
        default=None,
        description="Request path that caused the error",
    )
    timestamp: datetime = Field(..., description="Error timestamp")


class KGErrorResponse(BaseModel):
    """Standard error response for KG API."""

    error: KGErrorDetail = Field(..., description="Error details")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "CONCEPT_NOT_FOUND",
                    "message": "Concept with CUI C9999999 not found",
                    "details": {"cui": "C9999999"},
                    "path": "/api/v1/kg/orchestration/concept/C9999999",
                    "timestamp": "2026-01-22T00:00:00Z",
                }
            }
        }
    }
