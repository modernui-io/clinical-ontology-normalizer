"""MTSamples medical transcription ingestion API endpoints."""

from __future__ import annotations

import logging
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field

from app.schemas.mtsamples import (
    MtsamplesImportResponse,
    MtsamplesImportProgressResponse,
    MtsamplesValidateResponse,
    MtsamplesMetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents/mtsamples", tags=["Documents", "MTSamples"])


@router.post(
    "/upload",
    response_model=MtsamplesImportResponse,
    summary="Upload MTSamples CSV for ingestion",
)
async def upload_mtsamples_csv(
    file: UploadFile = File(...),
    chunk_size: int = Query(100, ge=1, le=10000),
    max_rows: int | None = Query(None, ge=1),
    skip_duplicates: bool = Query(True),
    enqueue_processing: bool = Query(True),
) -> MtsamplesImportResponse:
    """Upload an MTSamples CSV and start background ingestion."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content_bytes = await file.read()
    try:
        csv_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
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
        from app.jobs.mtsamples_ingestion import run_mtsamples_import

        enqueue_job(
            run_mtsamples_import,
            csv_content,
            batch_id,
            chunk_size=chunk_size,
            max_rows=max_rows,
            skip_duplicates=skip_duplicates,
            enqueue_processing=enqueue_processing,
            total_rows=total_rows,
            queue_name="document_processing",
            job_timeout=3600,
            job_id=batch_id,
        )

        return MtsamplesImportResponse(
            batch_id=batch_id,
            status="queued",
            total_rows=total_rows,
            message=f"Import queued: {total_rows} transcriptions to process",
        )

    except ImportError:
        logger.warning("RQ not available, running MTSamples import synchronously")
        from app.schemas.mtsamples import MtsamplesImportConfig

        config = MtsamplesImportConfig(
            chunk_size=chunk_size,
            max_rows=max_rows,
            skip_duplicates=skip_duplicates,
            enqueue_processing=False,
        )
        result = service.ingest_csv(csv_content, config, batch_id)
        return MtsamplesImportResponse(
            batch_id=batch_id,
            status="completed",
            total_rows=total_rows,
            message=f"Import completed: {result['created']} created, {result['skipped']} skipped, {result['failed']} failed",
        )


class MtsamplesFilePathRequest(BaseModel):
    """Request to import from a server-side file path."""

    file_path: str = Field(..., description="Absolute path to MTSamples CSV on the server")
    chunk_size: int = Field(100, ge=1, le=10000)
    max_rows: int | None = Field(None, ge=1)
    skip_duplicates: bool = True
    enqueue_processing: bool = True


@router.post(
    "/import-from-path",
    response_model=MtsamplesImportResponse,
    summary="Import MTSamples CSV from a server-side file path",
)
async def import_mtsamples_from_path(
    request: MtsamplesFilePathRequest,
) -> MtsamplesImportResponse:
    """Import MTSamples CSV from a server-side path."""
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

    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
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
        from app.jobs.mtsamples_ingestion import run_mtsamples_import

        enqueue_job(
            run_mtsamples_import,
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

        return MtsamplesImportResponse(
            batch_id=batch_id,
            status="queued",
            total_rows=total_rows,
            message=f"Import queued from {file_path.name}: {total_rows} rows to process",
        )

    except ImportError:
        logger.warning("RQ not available, running MTSamples import synchronously")
        from app.schemas.mtsamples import MtsamplesImportConfig

        config = MtsamplesImportConfig(
            chunk_size=request.chunk_size,
            max_rows=request.max_rows,
            skip_duplicates=request.skip_duplicates,
            enqueue_processing=False,
        )
        result = service.ingest_csv(csv_content, config, batch_id)
        return MtsamplesImportResponse(
            batch_id=batch_id,
            status="completed",
            total_rows=total_rows,
            message=f"Import completed: {result['created']} created, {result['skipped']} skipped, {result['failed']} failed",
        )


@router.post(
    "/validate",
    response_model=MtsamplesValidateResponse,
    summary="Validate MTSamples CSV structure without importing",
)
async def validate_mtsamples_csv(
    file: UploadFile = File(...),
) -> MtsamplesValidateResponse:
    """Validate an MTSamples CSV without importing."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content_bytes = await file.read()
    try:
        csv_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
    return service.validate_csv(csv_content)


@router.post(
    "/validate-path",
    response_model=MtsamplesValidateResponse,
    summary="Validate a server-side MTSamples CSV without importing",
)
async def validate_mtsamples_path(
    file_path: str = Query(..., description="Absolute path to CSV on server"),
) -> MtsamplesValidateResponse:
    """Validate an MTSamples CSV from a server-side path."""
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not path.suffix == ".csv":
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        csv_content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
    return service.validate_csv(csv_content)


@router.get(
    "/import/{batch_id}/progress",
    response_model=MtsamplesImportProgressResponse,
    summary="Poll MTSamples import progress",
)
async def get_import_progress(
    batch_id: str,
) -> MtsamplesImportProgressResponse:
    """Get the progress of a running MTSamples import batch."""
    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
    progress = service.get_import_progress(batch_id)

    if not progress:
        raise HTTPException(status_code=404, detail="Import batch not found")

    return progress


@router.get(
    "/metrics",
    response_model=MtsamplesMetricsResponse,
    summary="Get MTSamples validation metrics",
)
async def get_mtsamples_metrics() -> MtsamplesMetricsResponse:
    """Get validation metrics for all MTSamples-imported documents."""
    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
    data = service.get_metrics()
    return MtsamplesMetricsResponse(**data)


@router.get(
    "/{document_id}/pipeline-results",
    summary="Get full pipeline results for a single MTSamples document",
)
async def get_pipeline_results(document_id: str) -> dict:
    """Get NLP pipeline output for an MTSamples document."""
    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
    result = service.get_document_pipeline_results(document_id)

    if not result:
        raise HTTPException(status_code=404, detail="Document not found")

    return result


@router.get(
    "/metrics/export",
    summary="Export MTSamples validation metrics as JSON",
)
async def export_mtsamples_metrics() -> dict:
    """Export full validation metrics."""
    from app.services.mtsamples_ingestion import MtsamplesIngestionService

    service = MtsamplesIngestionService()
    return service.get_metrics()
