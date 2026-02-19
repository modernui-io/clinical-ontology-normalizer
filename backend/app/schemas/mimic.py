"""Schemas for MIMIC-IV-Note ingestion and validation pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MimicImportConfig(BaseModel):
    """Configuration for MIMIC CSV import."""

    chunk_size: int = Field(100, ge=1, le=10000, description="Documents to create per batch")
    max_rows: int | None = Field(None, ge=1, description="Max rows to import (None = all)")
    skip_duplicates: bool = Field(True, description="Skip rows with existing mimic_note_id")
    enqueue_processing: bool = Field(True, description="Enqueue NLP processing for each document")


class MimicImportResponse(BaseModel):
    """Response after starting a MIMIC import."""

    batch_id: str
    status: str
    total_rows: int
    message: str


class MimicImportProgressResponse(BaseModel):
    """Progress of a running MIMIC import."""

    batch_id: str
    status: str  # queued | processing | completed | failed
    total_rows: int
    processed: int
    created: int
    skipped: int
    failed: int
    progress_percent: float
    error: str | None = None


class MimicValidateResponse(BaseModel):
    """Response from CSV validation (no import)."""

    valid: bool
    total_rows: int
    columns_found: list[str]
    columns_missing: list[str]
    sample_rows: list[dict]
    errors: list[str]


class MimicDomainCount(BaseModel):
    """Count of facts by domain."""

    domain: str
    count: int


class MimicUnmappedTerm(BaseModel):
    """An unmapped term with occurrence count."""

    term: str
    count: int
    sample_document_ids: list[str] = []


class MimicPipelineMention(BaseModel):
    """A mention with its top concept mapping."""

    id: str
    text: str
    start_offset: int
    end_offset: int
    section: str | None = None
    assertion: str
    temporality: str
    experiencer: str
    confidence: float
    # Top concept candidate (if mapped)
    concept_name: str | None = None
    omop_concept_id: int | None = None
    vocabulary_id: str | None = None
    domain_id: str | None = None
    mapping_score: float | None = None
    mapping_method: str | None = None


class MimicPipelineFact(BaseModel):
    """A clinical fact created from this document's mentions."""

    id: str
    domain: str
    omop_concept_id: int
    concept_name: str
    assertion: str
    temporality: str
    experiencer: str
    confidence: float


class MimicPipelineResultsResponse(BaseModel):
    """Full pipeline output for a single MIMIC document."""

    document_id: str
    patient_id: str
    note_type: str
    status: str
    mimic_note_id: str | None = None
    text_preview: str
    text_length: int
    mentions: list[MimicPipelineMention]
    facts: list[MimicPipelineFact]
    mention_count: int
    fact_count: int
    mapped_mention_count: int
    unmapped_mention_count: int
    concept_coverage_percent: float


class MimicMetricsResponse(BaseModel):
    """Validation metrics for MIMIC-imported documents."""

    total_documents: int
    total_mentions: int
    total_facts: int
    concept_coverage_percent: float
    avg_confidence: float
    status_breakdown: dict[str, int]  # queued/processing/completed/failed counts
    domain_distribution: list[MimicDomainCount]
    top_unmapped_terms: list[MimicUnmappedTerm]
    avg_processing_time_ms: float
    p50_processing_time_ms: float
    p95_processing_time_ms: float
    recent_documents: list[dict]
