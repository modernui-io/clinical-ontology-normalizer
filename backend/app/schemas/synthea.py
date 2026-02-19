"""Schemas for Synthea ingestion and validation pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SyntheaImportConfig(BaseModel):
    """Configuration for Synthea directory import."""

    chunk_size: int = Field(100, ge=1, le=10000, description="Documents to create per batch")
    max_patients: int | None = Field(None, ge=1, description="Max patients to import (None = all)")
    max_encounters_per_patient: int | None = Field(None, ge=1, description="Max encounters per patient")
    skip_duplicates: bool = Field(True, description="Skip encounters with existing synthea_encounter_id")
    enqueue_processing: bool = Field(True, description="Enqueue NLP processing for each document")


class SyntheaImportResponse(BaseModel):
    """Response after starting a Synthea import."""

    batch_id: str
    status: str
    total_patients: int
    total_encounters: int
    message: str


class SyntheaImportProgressResponse(BaseModel):
    """Progress of a running Synthea import."""

    batch_id: str
    status: str  # queued | processing | completed | failed
    total_rows: int
    processed: int
    created: int
    skipped: int
    failed: int
    progress_percent: float
    error: str | None = None


class SyntheaValidateResponse(BaseModel):
    """Response from Synthea directory validation."""

    valid: bool
    files_found: list[str]
    files_missing: list[str]
    patient_count: int
    encounter_count: int
    condition_count: int
    observation_count: int
    medication_count: int
    procedure_count: int
    errors: list[str]
    sample_patient: dict | None = None


class SyntheaDomainCount(BaseModel):
    """Count of facts by domain."""

    domain: str
    count: int


class SyntheaUnmappedTerm(BaseModel):
    """An unmapped term with occurrence count."""

    term: str
    count: int
    sample_document_ids: list[str] = []


class SyntheaMetricsResponse(BaseModel):
    """Validation metrics for Synthea-imported documents."""

    total_documents: int
    total_mentions: int
    total_facts: int
    concept_coverage_percent: float
    avg_confidence: float
    status_breakdown: dict[str, int]
    domain_distribution: list[SyntheaDomainCount]
    encounter_class_distribution: list[dict]
    top_unmapped_terms: list[SyntheaUnmappedTerm]
    avg_processing_time_ms: float
    p50_processing_time_ms: float
    p95_processing_time_ms: float
    recent_documents: list[dict]
