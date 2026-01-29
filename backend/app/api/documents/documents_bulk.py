"""Document Bulk API endpoints - Batch upload/download, reports."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents", "batch"])


# ============================================================================
# Batch Processing Endpoints
# ============================================================================


class BatchDocumentRequest(BaseModel):
    """A document for batch processing."""

    filename: str
    content: str
    content_type: str = "text/plain"


class BatchCreateRequest(BaseModel):
    """Request to create a batch job."""

    documents: list[BatchDocumentRequest]
    patient_id: str | None = None


class BatchProgressResponse(BaseModel):
    """Batch progress response."""

    job_id: str
    status: str
    progress_percent: float
    processed: int
    total: int
    estimated_remaining_seconds: float | None = None


class BatchStatusResponse(BaseModel):
    """Batch status response."""

    job_id: str
    status: str
    total_documents: int
    processed_documents: int
    successful_documents: int
    failed_documents: int
    progress_percent: float
    created_at: str
    completed_at: str | None = None
    summary: dict | None = None
    errors: list[str] = []


@router.post(
    "/batch/create",
    response_model=BatchStatusResponse,
    tags=["batch"],
    summary="Create batch processing job",
)
async def create_batch_job(
    request: BatchCreateRequest,
) -> BatchStatusResponse:
    """Create a new batch processing job."""
    from app.services.batch_processor import BatchProcessorService

    service = BatchProcessorService()

    documents = [
        {
            "filename": d.filename,
            "content": d.content,
            "content_type": d.content_type,
        }
        for d in request.documents
    ]

    job = service.create_batch(documents, patient_id=request.patient_id)

    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        successful_documents=job.successful_documents,
        failed_documents=job.failed_documents,
        progress_percent=job.progress_percent,
        created_at=job.created_at,
    )


@router.get(
    "/batch/{job_id}/status",
    response_model=BatchStatusResponse,
    tags=["batch"],
    summary="Get batch job status",
)
async def get_batch_status(
    job_id: str,
) -> BatchStatusResponse:
    """Get status of a batch processing job."""
    from app.services.batch_processor import BatchProcessorService

    service = BatchProcessorService()
    job = service.get_batch_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        successful_documents=job.successful_documents,
        failed_documents=job.failed_documents,
        progress_percent=job.progress_percent,
        created_at=job.created_at,
        completed_at=job.completed_at,
        summary=job.summary if job.summary else None,
        errors=job.errors,
    )


@router.get(
    "/batch/{job_id}/progress",
    response_model=BatchProgressResponse,
    tags=["batch"],
    summary="Get batch job progress",
)
async def get_batch_progress(
    job_id: str,
) -> BatchProgressResponse:
    """Get progress of a batch processing job."""
    from app.services.batch_processor import BatchProcessorService

    service = BatchProcessorService()
    progress = service.get_batch_progress(job_id)

    if not progress:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return BatchProgressResponse(
        job_id=progress.job_id,
        status=progress.status.value,
        progress_percent=progress.progress_percent,
        processed=progress.processed,
        total=progress.total,
        estimated_remaining_seconds=progress.estimated_remaining_seconds,
    )


# ============================================================================
# Report Generation Endpoints
# ============================================================================


class ReportSectionRequest(BaseModel):
    """A report section."""

    title: str
    content: str = ""
    bullet_points: list[str] = []
    table_data: list[dict] | None = None


class ReportRequest(BaseModel):
    """Request for report generation."""

    title: str = Field(..., description="Report title")
    patient_id: str | None = Field(None, description="Patient ID")
    sections: list[ReportSectionRequest] = Field(..., description="Report sections")
    format: str = Field("html", description="Output format: html, markdown, json, pdf")
    template: str = Field("clinical_summary", description="Report template")


class GeneratedReportResponse(BaseModel):
    """Generated report response."""

    report_id: str
    format: str
    filename: str
    content: str
    content_type: str
    size_bytes: int


@router.post(
    "/reports/generate",
    response_model=GeneratedReportResponse,
    tags=["reports"],
    summary="Generate clinical report",
)
async def generate_report(
    request: ReportRequest,
) -> GeneratedReportResponse:
    """Generate a clinical report in specified format."""
    from app.services.report_generator import (
        ReportGeneratorService,
        ReportData,
        ReportSection,
        ReportFormat,
        ReportTemplate,
    )

    service = ReportGeneratorService()

    format_map = {
        "html": ReportFormat.HTML,
        "markdown": ReportFormat.MARKDOWN,
        "json": ReportFormat.JSON,
        "pdf": ReportFormat.PDF,
    }

    template_map = {
        "clinical_summary": ReportTemplate.CLINICAL_SUMMARY,
        "discharge_summary": ReportTemplate.DISCHARGE_SUMMARY,
        "problem_list": ReportTemplate.PROBLEM_LIST,
        "nlp_extraction": ReportTemplate.NLP_EXTRACTION_REPORT,
    }

    data = ReportData(
        title=request.title,
        patient_id=request.patient_id,
        sections=[
            ReportSection(
                title=s.title,
                content=s.content,
                bullet_points=s.bullet_points,
                table_data=s.table_data,
            )
            for s in request.sections
        ],
    )

    report = service.generate_report(
        data,
        template_map.get(request.template, ReportTemplate.CLINICAL_SUMMARY),
        format_map.get(request.format, ReportFormat.HTML),
    )

    content = report.content
    if isinstance(content, bytes):
        import base64
        content = base64.b64encode(content).decode("utf-8")

    return GeneratedReportResponse(
        report_id=report.report_id,
        format=report.format.value,
        filename=report.filename,
        content=content,
        content_type=report.content_type,
        size_bytes=report.size_bytes,
    )


# ============================================================================
# Quality Metrics Dashboard Endpoints
# ============================================================================


class DashboardResponse(BaseModel):
    """Quality metrics dashboard data."""

    total_documents_processed: int
    total_extractions: int
    avg_processing_time_ms: float
    overall_confidence: float
    error_rate: float
    entity_distribution: dict[str, int]
    confidence_distribution: dict[str, int]
    top_errors: list[dict]
    recent_documents: list[dict]


@router.get(
    "/metrics/dashboard",
    response_model=DashboardResponse,
    tags=["metrics"],
    summary="Get quality metrics dashboard data",
)
async def get_dashboard_metrics(
    time_window: str = "day",
) -> DashboardResponse:
    """Get quality metrics dashboard data."""
    from app.services.quality_metrics import QualityMetricsService, TimeWindow

    service = QualityMetricsService()

    window_map = {
        "hour": TimeWindow.HOUR,
        "day": TimeWindow.DAY,
        "week": TimeWindow.WEEK,
        "month": TimeWindow.MONTH,
    }

    data = service.get_dashboard_data(
        window_map.get(time_window, TimeWindow.DAY)
    )

    return DashboardResponse(
        total_documents_processed=data.total_documents_processed,
        total_extractions=data.total_extractions,
        avg_processing_time_ms=data.avg_processing_time_ms,
        overall_confidence=data.overall_confidence,
        error_rate=data.error_rate,
        entity_distribution=data.entity_distribution,
        confidence_distribution=data.confidence_distribution,
        top_errors=data.top_errors,
        recent_documents=data.recent_documents,
    )
