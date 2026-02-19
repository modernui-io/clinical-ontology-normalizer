"""Synthea synthetic patient data ingestion API endpoints."""

from __future__ import annotations

import logging
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.synthea import (
    SyntheaImportResponse,
    SyntheaImportProgressResponse,
    SyntheaValidateResponse,
    SyntheaMetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents/synthea", tags=["Documents", "Synthea"])


class SyntheaDirectoryRequest(BaseModel):
    """Request to import from a Synthea CSV output directory."""

    csv_dir: str = Field(..., description="Absolute path to Synthea output/csv/ directory")
    chunk_size: int = Field(100, ge=1, le=10000)
    max_patients: int | None = Field(None, ge=1)
    max_encounters_per_patient: int | None = Field(None, ge=1)
    skip_duplicates: bool = True
    enqueue_processing: bool = True


@router.post(
    "/import-from-path",
    response_model=SyntheaImportResponse,
    summary="Import Synthea data from a server-side directory",
)
async def import_synthea_from_path(
    request: SyntheaDirectoryRequest,
) -> SyntheaImportResponse:
    """Import Synthea synthetic patient data from a server-side directory.

    The directory must contain: patients.csv, encounters.csv, conditions.csv.
    Optional: observations.csv, medications.csv, procedures.csv.
    Each encounter is composed into a clinical note and ingested as a Document.
    """
    dir_path = Path(request.csv_dir)
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.csv_dir}")
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory")

    from app.services.synthea_ingestion import SyntheaIngestionService

    service = SyntheaIngestionService()

    # Validate directory structure
    validation = service.validate_directory(request.csv_dir)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Synthea directory: {'; '.join(validation.errors)}",
        )

    total_encounters = validation.encounter_count
    batch_id = str(uuid4())

    try:
        from app.core.queue import enqueue_job
        from app.jobs.synthea_ingestion import run_synthea_import

        enqueue_job(
            run_synthea_import,
            request.csv_dir,
            batch_id,
            chunk_size=request.chunk_size,
            max_patients=request.max_patients,
            max_encounters_per_patient=request.max_encounters_per_patient,
            skip_duplicates=request.skip_duplicates,
            enqueue_processing=request.enqueue_processing,
            total_rows=total_encounters,
            queue_name="document_processing",
            job_timeout=3600,
            job_id=batch_id,
        )

        return SyntheaImportResponse(
            batch_id=batch_id,
            status="queued",
            total_patients=validation.patient_count,
            total_encounters=total_encounters,
            message=f"Import queued: {validation.patient_count} patients, {total_encounters} encounters",
        )

    except ImportError:
        logger.warning("RQ not available, running Synthea import synchronously")
        from app.schemas.synthea import SyntheaImportConfig

        config = SyntheaImportConfig(
            chunk_size=request.chunk_size,
            max_patients=request.max_patients,
            max_encounters_per_patient=request.max_encounters_per_patient,
            skip_duplicates=request.skip_duplicates,
            enqueue_processing=False,
        )
        result = service.ingest_directory(request.csv_dir, config, batch_id)
        return SyntheaImportResponse(
            batch_id=batch_id,
            status="completed",
            total_patients=validation.patient_count,
            total_encounters=total_encounters,
            message=f"Import completed: {result['created']} created, {result['skipped']} skipped, {result['failed']} failed",
        )


@router.post(
    "/validate-path",
    response_model=SyntheaValidateResponse,
    summary="Validate a Synthea output directory",
)
async def validate_synthea_path(
    csv_dir: str = Query(..., description="Absolute path to Synthea output/csv/ directory"),
) -> SyntheaValidateResponse:
    """Validate a Synthea CSV directory without importing."""
    dir_path = Path(csv_dir)
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {csv_dir}")

    from app.services.synthea_ingestion import SyntheaIngestionService

    service = SyntheaIngestionService()
    return service.validate_directory(csv_dir)


@router.get(
    "/import/{batch_id}/progress",
    response_model=SyntheaImportProgressResponse,
    summary="Poll Synthea import progress",
)
async def get_import_progress(
    batch_id: str,
) -> SyntheaImportProgressResponse:
    """Get the progress of a running Synthea import batch."""
    from app.services.synthea_ingestion import SyntheaIngestionService

    service = SyntheaIngestionService()
    progress = service.get_import_progress(batch_id)

    if not progress:
        raise HTTPException(status_code=404, detail="Import batch not found")

    return progress


@router.get(
    "/metrics",
    response_model=SyntheaMetricsResponse,
    summary="Get Synthea validation metrics",
)
async def get_synthea_metrics() -> SyntheaMetricsResponse:
    """Get validation metrics for all Synthea-imported documents."""
    from app.services.synthea_ingestion import SyntheaIngestionService

    service = SyntheaIngestionService()
    data = service.get_metrics()
    return SyntheaMetricsResponse(**data)


@router.get(
    "/{document_id}/pipeline-results",
    summary="Get full pipeline results for a single Synthea document",
)
async def get_pipeline_results(document_id: str) -> dict:
    """Get NLP pipeline output for a Synthea document."""
    from app.services.synthea_ingestion import SyntheaIngestionService

    service = SyntheaIngestionService()
    result = service.get_document_pipeline_results(document_id)

    if not result:
        raise HTTPException(status_code=404, detail="Document not found")

    return result


@router.get(
    "/metrics/export",
    summary="Export Synthea validation metrics as JSON",
)
async def export_synthea_metrics() -> dict:
    """Export full validation metrics."""
    from app.services.synthea_ingestion import SyntheaIngestionService

    service = SyntheaIngestionService()
    return service.get_metrics()
