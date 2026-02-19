"""Pydantic schemas for research experiment tracking."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================================
# Experiment Schemas
# ============================================================================


class ExperimentConfig(BaseModel):
    assertion_aware: bool = Field(True, description="Enable assertion-aware NLP")
    graph_rag: bool = Field(True, description="Enable graph-augmented RAG")
    nlp_method: str = Field("ensemble", description="NLP method: rule_based | ml | ensemble")
    kg_construction: bool = Field(True, description="Build knowledge graph")
    max_documents: int | None = Field(None, ge=1, description="Limit documents per run")


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    hypothesis: str | None = None
    config: ExperimentConfig = Field(default_factory=ExperimentConfig)
    tags: list[str] | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    hypothesis: str | None = None
    config: ExperimentConfig | None = None
    tags: list[str] | None = None


class ExperimentResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    hypothesis: str | None = None
    config: dict = Field(default_factory=dict)
    status: str
    summary_metrics: dict | None = None
    tags: list[str] | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    run_count: int = 0


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentResponse]
    total: int


# ============================================================================
# Run Schemas
# ============================================================================


class RunCreate(BaseModel):
    experiment_id: str
    mimic_csv_path: str | None = Field(None, description="Server path to MIMIC CSV")
    run_config: dict | None = Field(None, description="Config overrides for this run")
    max_rows: int | None = Field(None, ge=1, description="Limit rows from CSV")
    chunk_size: int = Field(100, ge=1, le=10000)


class RunResponse(BaseModel):
    id: str
    experiment_id: str
    mimic_batch_id: str | None = None
    run_config: dict | None = None
    document_ids: list[str] | None = None
    patient_ids: list[str] | None = None
    status: str
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metric_count: int = 0


class RunListResponse(BaseModel):
    runs: list[RunResponse]
    total: int


class RunProgressResponse(BaseModel):
    run_id: str
    experiment_id: str
    status: str
    mimic_batch_id: str | None = None
    mimic_progress: dict | None = None
    documents_total: int = 0
    documents_processed: int = 0
    pipeline_stage: str | None = None
    progress_percent: float = 0.0


# ============================================================================
# Metric Schemas
# ============================================================================


class MetricResponse(BaseModel):
    id: str
    run_id: str
    category: str
    metric_name: str
    metric_value: float
    detail: dict | None = None
    created_at: datetime


class MetricListResponse(BaseModel):
    metrics: list[MetricResponse]
    total: int


class AssertionAnalytics(BaseModel):
    total_mentions: int = 0
    assertion_counts: dict[str, int] = Field(default_factory=dict)
    assertion_by_domain: dict[str, dict[str, int]] = Field(default_factory=dict)
    temporality_counts: dict[str, int] = Field(default_factory=dict)
    experiencer_counts: dict[str, int] = Field(default_factory=dict)


class MappingQuality(BaseModel):
    total_mentions: int = 0
    mapped_count: int = 0
    unmapped_count: int = 0
    coverage_percent: float = 0.0
    avg_confidence: float = 0.0
    domain_coverage: dict[str, float] = Field(default_factory=dict)
    top_unmapped: list[dict] = Field(default_factory=list)


class KGMetrics(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    unique_concepts: int = 0
    patient_count: int = 0
    avg_nodes_per_patient: float = 0.0
    edge_type_distribution: dict[str, int] = Field(default_factory=dict)
    node_type_distribution: dict[str, int] = Field(default_factory=dict)


class PipelineTimingMetrics(BaseModel):
    avg_nlp_ms: float = 0.0
    avg_mapping_ms: float = 0.0
    avg_fact_building_ms: float = 0.0
    avg_kg_construction_ms: float = 0.0
    avg_total_ms: float = 0.0
    p95_total_ms: float = 0.0
    documents_timed: int = 0


# ============================================================================
# Comparison Schemas
# ============================================================================


class ComparisonRequest(BaseModel):
    run_ids: list[str] = Field(..., min_length=2, max_length=10)
    metric_categories: list[str] | None = None


class RunComparisonColumn(BaseModel):
    run_id: str
    experiment_name: str
    status: str
    metrics: dict[str, float] = Field(default_factory=dict)


class ComparisonResponse(BaseModel):
    metric_names: list[str]
    runs: list[RunComparisonColumn]


# ============================================================================
# Export Schemas
# ============================================================================


class ExportRequest(BaseModel):
    run_ids: list[str] = Field(..., min_length=1)
    format: str = Field("csv", pattern="^(csv|json|latex)$")
    metric_categories: list[str] | None = None


class ExportResponse(BaseModel):
    format: str
    filename: str
    content: str
    mime_type: str
