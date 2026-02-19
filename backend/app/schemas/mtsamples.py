"""Schemas for MTSamples ingestion and validation pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MtsamplesImportConfig(BaseModel):
    """Configuration for MTSamples CSV import."""

    chunk_size: int = Field(100, ge=1, le=10000, description="Documents to create per batch")
    max_rows: int | None = Field(None, ge=1, description="Max rows to import (None = all)")
    skip_duplicates: bool = Field(True, description="Skip rows with existing mtsamples_id")
    enqueue_processing: bool = Field(True, description="Enqueue NLP processing for each document")


class MtsamplesImportResponse(BaseModel):
    """Response after starting an MTSamples import."""

    batch_id: str
    status: str
    total_rows: int
    message: str


class MtsamplesImportProgressResponse(BaseModel):
    """Progress of a running MTSamples import."""

    batch_id: str
    status: str  # queued | processing | completed | failed
    total_rows: int
    processed: int
    created: int
    skipped: int
    failed: int
    progress_percent: float
    error: str | None = None


class MtsamplesValidateResponse(BaseModel):
    """Response from CSV validation (no import)."""

    valid: bool
    total_rows: int
    columns_found: list[str]
    columns_missing: list[str]
    sample_rows: list[dict]
    errors: list[str]


class MtsamplesDomainCount(BaseModel):
    """Count of facts by domain."""

    domain: str
    count: int


class MtsamplesUnmappedTerm(BaseModel):
    """An unmapped term with occurrence count."""

    term: str
    count: int
    sample_document_ids: list[str] = []


class MtsamplesMetricsResponse(BaseModel):
    """Validation metrics for MTSamples-imported documents."""

    total_documents: int
    total_mentions: int
    total_facts: int
    concept_coverage_percent: float
    avg_confidence: float
    status_breakdown: dict[str, int]
    domain_distribution: list[MtsamplesDomainCount]
    specialty_distribution: list[dict]
    top_unmapped_terms: list[MtsamplesUnmappedTerm]
    avg_processing_time_ms: float
    p50_processing_time_ms: float
    p95_processing_time_ms: float
    recent_documents: list[dict]
