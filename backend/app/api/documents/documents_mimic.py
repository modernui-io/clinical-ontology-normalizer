"""MIMIC-IV-Note ingestion API endpoints.

Follows the pattern from documents_bulk.py — batch upload, progress tracking,
and validation metrics.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field

from app.schemas.mimic import (
    MimicImportConfig,
    MimicImportResponse,
    MimicImportProgressResponse,
    MimicValidateResponse,
    MimicMetricsResponse,
    MimicPipelineResultsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents/mimic", tags=["Documents", "MIMIC"])


@router.post(
    "/upload",
    response_model=MimicImportResponse,
    summary="Upload MIMIC-IV-Note CSV for ingestion",
)
async def upload_mimic_csv(
    file: UploadFile = File(...),
    chunk_size: int = Query(100, ge=1, le=10000),
    max_rows: int | None = Query(None, ge=1),
    skip_duplicates: bool = Query(True),
    enqueue_processing: bool = Query(True),
) -> MimicImportResponse:
    """Upload a MIMIC-IV-Note CSV and start background ingestion.

    The CSV must contain columns: note_id, subject_id, hadm_id, note_type, text.
    Documents are created in chunks and optionally enqueued for NLP processing.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content_bytes = await file.read()
    try:
        csv_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()

    # Validate CSV structure first
    validation = service.validate_csv(csv_content, max_sample_rows=0)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CSV: {'; '.join(validation.errors)}",
        )

    total_rows = validation.total_rows
    batch_id = str(uuid4())

    # Enqueue background import job
    try:
        from app.core.queue import enqueue_job
        from app.jobs.mimic_ingestion import run_mimic_import

        enqueue_job(
            run_mimic_import,
            csv_content,
            batch_id,
            chunk_size=chunk_size,
            max_rows=max_rows,
            skip_duplicates=skip_duplicates,
            enqueue_processing=enqueue_processing,
            total_rows=total_rows,
            queue_name="document_processing",
            job_timeout=3600,  # 1 hour for large files
            job_id=batch_id,
        )

        return MimicImportResponse(
            batch_id=batch_id,
            status="queued",
            total_rows=total_rows,
            message=f"Import queued: {total_rows} rows to process",
        )

    except ImportError:
        # RQ not available — run synchronously
        logger.warning("RQ not available, running MIMIC import synchronously")
        config = MimicImportConfig(
            chunk_size=chunk_size,
            max_rows=max_rows,
            skip_duplicates=skip_duplicates,
            enqueue_processing=False,  # Can't enqueue without RQ
        )
        result = service.ingest_csv(csv_content, config, batch_id)
        return MimicImportResponse(
            batch_id=batch_id,
            status="completed",
            total_rows=total_rows,
            message=f"Import completed synchronously: {result['created']} created, {result['skipped']} skipped, {result['failed']} failed",
        )


class MimicFilePathRequest(BaseModel):
    """Request to import from a server-side file path."""

    file_path: str = Field(..., description="Absolute path to a MIMIC CSV on the server")
    chunk_size: int = Field(100, ge=1, le=10000)
    max_rows: int | None = Field(None, ge=1)
    skip_duplicates: bool = True
    enqueue_processing: bool = True


@router.post(
    "/import-from-path",
    response_model=MimicImportResponse,
    summary="Import MIMIC CSV from a server-side file path",
)
async def import_mimic_from_path(
    request: MimicFilePathRequest,
) -> MimicImportResponse:
    """Import a MIMIC-IV-Note CSV that already exists on the server filesystem.

    Use this instead of upload for large files (e.g. full 331K-row discharge_summaries.csv).
    The file is read directly from disk — no browser upload required.
    """
    file_path = Path(request.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    if not file_path.suffix == ".csv":
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        csv_content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied reading file")

    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()

    # Validate structure
    validation = service.validate_csv(csv_content, max_sample_rows=0)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CSV: {'; '.join(validation.errors)}",
        )

    total_rows = validation.total_rows
    batch_id = str(uuid4())

    try:
        from app.core.queue import enqueue_job
        from app.jobs.mimic_ingestion import run_mimic_import

        enqueue_job(
            run_mimic_import,
            csv_content,
            batch_id,
            chunk_size=request.chunk_size,
            max_rows=request.max_rows,
            skip_duplicates=request.skip_duplicates,
            enqueue_processing=request.enqueue_processing,
            total_rows=total_rows,
            queue_name="document_processing",
            job_timeout=3600,
            job_id=batch_id,
        )

        return MimicImportResponse(
            batch_id=batch_id,
            status="queued",
            total_rows=total_rows,
            message=f"Import queued from {file_path.name}: {total_rows} rows to process",
        )

    except ImportError:
        logger.warning("RQ not available, running MIMIC import synchronously")
        config = MimicImportConfig(
            chunk_size=request.chunk_size,
            max_rows=request.max_rows,
            skip_duplicates=request.skip_duplicates,
            enqueue_processing=False,
        )
        result = service.ingest_csv(csv_content, config, batch_id)
        return MimicImportResponse(
            batch_id=batch_id,
            status="completed",
            total_rows=total_rows,
            message=f"Import completed: {result['created']} created, {result['skipped']} skipped, {result['failed']} failed",
        )


@router.post(
    "/validate-path",
    response_model=MimicValidateResponse,
    summary="Validate a server-side MIMIC CSV without importing",
)
async def validate_mimic_path(
    file_path: str = Query(..., description="Absolute path to CSV on server"),
) -> MimicValidateResponse:
    """Validate a MIMIC CSV from a server-side path without importing."""
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not path.suffix == ".csv":
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        csv_content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()
    return service.validate_csv(csv_content)


@router.post(
    "/validate",
    response_model=MimicValidateResponse,
    summary="Validate MIMIC CSV structure without importing",
)
async def validate_mimic_csv(
    file: UploadFile = File(...),
) -> MimicValidateResponse:
    """Validate a MIMIC-IV-Note CSV without importing any data.

    Returns column validation, row count, and sample rows for preview.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content_bytes = await file.read()
    try:
        csv_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()
    return service.validate_csv(csv_content)


@router.get(
    "/import/{batch_id}/progress",
    response_model=MimicImportProgressResponse,
    summary="Poll MIMIC import progress",
)
async def get_import_progress(
    batch_id: str,
) -> MimicImportProgressResponse:
    """Get the progress of a running MIMIC import batch."""
    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()
    progress = service.get_import_progress(batch_id)

    if not progress:
        raise HTTPException(status_code=404, detail="Import batch not found")

    return progress


@router.get(
    "/metrics",
    response_model=MimicMetricsResponse,
    summary="Get MIMIC validation metrics",
)
async def get_mimic_metrics() -> MimicMetricsResponse:
    """Get validation metrics for all MIMIC-imported documents.

    Returns concept coverage, domain distribution, unmapped terms,
    processing performance, and recent document status.
    """
    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()
    data = service.get_mimic_metrics()
    return MimicMetricsResponse(**data)


@router.get(
    "/{document_id}/pipeline-results",
    response_model=MimicPipelineResultsResponse,
    summary="Get full pipeline results for a single MIMIC document",
)
async def get_pipeline_results(
    document_id: str,
) -> MimicPipelineResultsResponse:
    """Get the full NLP pipeline output for a MIMIC document.

    Returns the document's mentions (with top concept mapping),
    clinical facts, and coverage stats — everything needed to
    verify the pipeline worked correctly for this note.
    """
    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()
    result = service.get_document_pipeline_results(document_id)

    if not result:
        raise HTTPException(status_code=404, detail="Document not found")

    return MimicPipelineResultsResponse(**result)


@router.get(
    "/metrics/export",
    summary="Export validation metrics as JSON",
)
async def export_mimic_metrics() -> dict:
    """Export full validation metrics as a downloadable JSON report."""
    from app.services.mimic_ingestion import MimicIngestionService

    service = MimicIngestionService()
    return service.get_mimic_metrics()
