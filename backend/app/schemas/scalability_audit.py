"""Pydantic schemas for Architecture Scalability Audit (CTO-1).

Defines schemas for component analysis, scaling projections, bottleneck risk
classification, database analysis, and load simulation results.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ScalingStrategy(str, Enum):
    """Strategy for scaling a given component."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    SHARDING = "sharding"
    CACHING = "caching"
    NONE = "none"


class BottleneckRisk(str, Enum):
    """Risk level for a bottleneck in a component."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceType(str, Enum):
    """Whether a service holds state or is stateless."""

    STATEFUL = "stateful"
    STATELESS = "stateless"


class QueryComplexity(str, Enum):
    """Big-O complexity category for a database query."""

    CONSTANT = "O(1)"
    LOGARITHMIC = "O(log n)"
    LINEAR = "O(n)"
    LINEARITHMIC = "O(n log n)"
    QUADRATIC = "O(n^2)"


class RecommendationPriority(str, Enum):
    """Priority for a remediation recommendation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PartitionType(str, Enum):
    """Type of table partitioning strategy."""

    RANGE = "range"
    LIST = "list"
    HASH = "hash"
    NONE = "none"


# ---------------------------------------------------------------------------
# Component Analysis
# ---------------------------------------------------------------------------


class ComponentAnalysis(BaseModel):
    """Analysis of a single architectural component."""

    name: str = Field(..., description="Component name (e.g. 'postgresql', 'redis')")
    description: str = Field(default="", description="Component description")
    current_capacity: str = Field(
        ..., description="Estimated current throughput (e.g. '500 req/s')"
    )
    scaling_strategy: ScalingStrategy = Field(
        ..., description="Recommended scaling approach"
    )
    bottleneck_risk: BottleneckRisk = Field(
        ..., description="Risk level for this component becoming a bottleneck"
    )
    recommendation: str = Field(
        ..., description="Specific action to improve scalability"
    )
    current_usage_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Estimated current utilization percentage",
    )
    max_capacity: str = Field(
        default="", description="Maximum estimated capacity before degradation"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional component-specific details"
    )


class ComponentListResponse(BaseModel):
    """Response containing all component analyses."""

    timestamp: datetime = Field(..., description="When the analysis was generated")
    components: list[ComponentAnalysis] = Field(default_factory=list)
    total: int = Field(default=0, ge=0, description="Total number of components analyzed")


# ---------------------------------------------------------------------------
# Scaling Projections
# ---------------------------------------------------------------------------


class TierProjection(BaseModel):
    """Resource projections for a single patient-count tier."""

    patient_count: int = Field(..., ge=0, description="Number of patients")
    compute_vcpus: int = Field(default=0, ge=0, description="vCPU count needed")
    memory_gb: float = Field(default=0.0, ge=0, description="RAM in GB")
    storage_gb: float = Field(default=0.0, ge=0, description="Storage in GB")
    network_mbps: float = Field(default=0.0, ge=0, description="Network bandwidth in Mbps")
    estimated_monthly_cost_usd: float = Field(
        default=0.0, ge=0, description="Estimated monthly cloud cost (USD)"
    )
    database_rows: int = Field(default=0, ge=0, description="Estimated total DB rows")
    graph_nodes: int = Field(default=0, ge=0, description="Estimated KG node count")
    graph_edges: int = Field(default=0, ge=0, description="Estimated KG edge count")


class ScalingProjection(BaseModel):
    """Growth projections across multiple patient-count tiers."""

    timestamp: datetime = Field(..., description="When projections were calculated")
    tiers: list[TierProjection] = Field(default_factory=list)
    assumptions: dict[str, Any] = Field(
        default_factory=dict,
        description="Assumptions used for projection (e.g. rows per patient)",
    )
    growth_model: str = Field(
        default="linear", description="Growth model used (linear, exponential)"
    )


# ---------------------------------------------------------------------------
# Database Analysis
# ---------------------------------------------------------------------------


class IndexRecommendation(BaseModel):
    """Recommendation for a database index."""

    table: str = Field(..., description="Table name")
    columns: list[str] = Field(default_factory=list, description="Columns to index")
    index_type: str = Field(default="btree", description="Index type (btree, gin, gist)")
    rationale: str = Field(default="", description="Why this index is recommended")
    estimated_improvement: str = Field(
        default="", description="Expected performance improvement"
    )


class PartitionStrategy(BaseModel):
    """Recommended partitioning strategy for a table."""

    table: str = Field(..., description="Table name")
    partition_type: PartitionType = Field(..., description="Type of partitioning")
    partition_key: str = Field(default="", description="Column(s) used for partitioning")
    estimated_partitions: int = Field(
        default=0, ge=0, description="Number of partitions at scale"
    )
    rationale: str = Field(default="", description="Why partitioning is recommended")


class TableSizeProjection(BaseModel):
    """Size projection for a database table."""

    table: str = Field(..., description="Table name")
    rows_per_patient: float = Field(
        default=0.0, ge=0, description="Average rows per patient"
    )
    row_size_bytes: int = Field(
        default=0, ge=0, description="Estimated average row size in bytes"
    )
    size_at_1k: str = Field(default="", description="Estimated size at 1K patients")
    size_at_10k: str = Field(default="", description="Estimated size at 10K patients")
    size_at_100k: str = Field(default="", description="Estimated size at 100K patients")
    size_at_1m: str = Field(default="", description="Estimated size at 1M patients")


class QueryPerformanceAnalysis(BaseModel):
    """Performance analysis for a query pattern."""

    query_pattern: str = Field(..., description="Description of the query pattern")
    complexity: QueryComplexity = Field(..., description="Big-O complexity")
    current_tables: list[str] = Field(
        default_factory=list, description="Tables involved"
    )
    concern: str = Field(default="", description="Scalability concern")
    recommendation: str = Field(default="", description="How to optimize")


class DatabaseAnalysis(BaseModel):
    """Comprehensive database scalability analysis."""

    timestamp: datetime = Field(..., description="When analysis was generated")
    table_projections: list[TableSizeProjection] = Field(default_factory=list)
    query_analysis: list[QueryPerformanceAnalysis] = Field(default_factory=list)
    index_recommendations: list[IndexRecommendation] = Field(default_factory=list)
    partition_strategies: list[PartitionStrategy] = Field(default_factory=list)
    connection_pool_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="Connection pooling configuration analysis",
    )
    overall_risk: BottleneckRisk = Field(
        default=BottleneckRisk.MEDIUM, description="Overall database scalability risk"
    )


# ---------------------------------------------------------------------------
# Horizontal Scaling Readiness
# ---------------------------------------------------------------------------


class ServiceScalingReadiness(BaseModel):
    """Horizontal scaling readiness for a single service."""

    service_name: str = Field(..., description="Service or component name")
    service_type: ServiceType = Field(..., description="Stateful or stateless")
    horizontally_scalable: bool = Field(
        default=False, description="Whether the service can be scaled horizontally"
    )
    session_affinity_required: bool = Field(
        default=False, description="Whether sticky sessions are needed"
    )
    shared_state: list[str] = Field(
        default_factory=list,
        description="State dependencies that require coordination",
    )
    event_driven_opportunities: list[str] = Field(
        default_factory=list,
        description="Opportunities to convert to event-driven architecture",
    )
    notes: str = Field(default="", description="Additional notes")


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class ScalabilityRecommendation(BaseModel):
    """A prioritized recommendation for improving scalability."""

    priority: RecommendationPriority = Field(..., description="Priority level")
    component: str = Field(..., description="Which component this applies to")
    title: str = Field(..., description="Short recommendation title")
    description: str = Field(
        default="", description="Detailed description of the recommendation"
    )
    effort: str = Field(
        default="medium",
        description="Implementation effort estimate (low/medium/high)",
    )
    impact: str = Field(
        default="medium",
        description="Expected scalability impact (low/medium/high)",
    )
    category: str = Field(
        default="performance",
        description="Category (performance, reliability, cost, architecture)",
    )


class RecommendationsResponse(BaseModel):
    """Response containing prioritized recommendations."""

    timestamp: datetime = Field(..., description="When recommendations were generated")
    recommendations: list[ScalabilityRecommendation] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Scalability Score & Dashboard
# ---------------------------------------------------------------------------


class ComponentScore(BaseModel):
    """Scalability score for a single component."""

    name: str = Field(..., description="Component name")
    score: int = Field(
        default=0, ge=0, le=100, description="Scalability score 0-100"
    )
    bottleneck_risk: BottleneckRisk = Field(default=BottleneckRisk.MEDIUM)
    limiting_factor: str = Field(
        default="", description="Primary factor limiting this component's score"
    )


class ScalabilityScore(BaseModel):
    """Overall architecture scalability score."""

    overall_score: int = Field(
        default=0, ge=0, le=100, description="Overall scalability score 0-100"
    )
    component_scores: list[ComponentScore] = Field(default_factory=list)
    grade: str = Field(
        default="C",
        description="Letter grade (A/B/C/D/F)",
    )
    summary: str = Field(
        default="", description="Human-readable summary of scalability posture"
    )


# ---------------------------------------------------------------------------
# Load Simulation
# ---------------------------------------------------------------------------


class LoadSimulationRequest(BaseModel):
    """Request to simulate load at a given patient count."""

    patient_count: int = Field(
        ..., ge=1, le=10_000_000, description="Number of patients to simulate"
    )
    concurrent_users: int = Field(
        default=50, ge=1, le=10_000, description="Concurrent API users"
    )
    screening_rate_per_hour: int = Field(
        default=100,
        ge=0,
        le=100_000,
        description="Patient screening operations per hour",
    )


class ResourceEstimate(BaseModel):
    """Estimated resource requirements for a simulation scenario."""

    compute_vcpus: int = Field(default=0, ge=0)
    memory_gb: float = Field(default=0.0, ge=0)
    storage_gb: float = Field(default=0.0, ge=0)
    network_mbps: float = Field(default=0.0, ge=0)
    estimated_monthly_cost_usd: float = Field(default=0.0, ge=0)


class BottleneckDetail(BaseModel):
    """A specific bottleneck identified during simulation."""

    component: str = Field(..., description="Component where bottleneck occurs")
    risk: BottleneckRisk = Field(..., description="Risk severity")
    description: str = Field(default="", description="What causes the bottleneck")
    mitigation: str = Field(default="", description="How to mitigate")


class LoadSimulationResult(BaseModel):
    """Result of a load simulation at a given patient count."""

    timestamp: datetime = Field(..., description="When simulation was run")
    patient_count: int = Field(..., ge=0)
    concurrent_users: int = Field(default=50, ge=0)
    screening_rate_per_hour: int = Field(default=100, ge=0)
    estimated_resources: ResourceEstimate = Field(default_factory=ResourceEstimate)
    bottlenecks: list[BottleneckDetail] = Field(default_factory=list)
    max_bottleneck_risk: BottleneckRisk = Field(default=BottleneckRisk.LOW)
    can_handle_load: bool = Field(
        default=True,
        description="Whether the current architecture can handle this load",
    )
    scaling_actions_needed: list[str] = Field(
        default_factory=list,
        description="Actions needed to handle this load",
    )


# ---------------------------------------------------------------------------
# Full Report
# ---------------------------------------------------------------------------


class ScalabilityReport(BaseModel):
    """Comprehensive scalability audit report."""

    timestamp: datetime = Field(..., description="When the report was generated")
    scalability_score: ScalabilityScore = Field(
        default_factory=ScalabilityScore,
        description="Overall scalability score and grades",
    )
    components: list[ComponentAnalysis] = Field(
        default_factory=list, description="Per-component analysis"
    )
    projections: ScalingProjection | None = Field(
        None, description="Growth projections across tiers"
    )
    database_analysis: DatabaseAnalysis | None = Field(
        None, description="Database-specific scalability analysis"
    )
    horizontal_scaling: list[ServiceScalingReadiness] = Field(
        default_factory=list, description="Horizontal scaling readiness per service"
    )
    recommendations: list[ScalabilityRecommendation] = Field(
        default_factory=list, description="Prioritized remediation recommendations"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (version, analyzer info, etc.)",
    )
