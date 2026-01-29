"""ETL core operations API endpoints.

This module provides REST API endpoints for core ETL (Extract, Transform, Load)
job management including creating, listing, and managing ETL jobs.

Endpoints:
    # Jobs
    POST /etl/jobs - Create a new ETL job
    GET /etl/jobs - List all ETL jobs with optional filtering
    GET /etl/jobs/{job_id} - Get status of a specific job
    POST /etl/jobs/{job_id}/cancel - Cancel a running or pending job
    DELETE /etl/jobs/{job_id} - Delete a completed/failed job
    GET /etl/connectors - List available connector types
    GET /etl/stats - Get ETL orchestrator statistics
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.etl_orchestrator import (
    ETLJobConfig,
    ETLJobState,
    get_etl_orchestrator,
)
from app.services.source_config_service import get_source_config_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/etl", tags=["ETL"])

# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# Request/Response Models
# =============================================================================


class ConnectorInfo(BaseModel):
    """Information about an available connector type."""

    type: str = Field(..., description="Connector type identifier")
    name: str = Field(..., description="Human-readable connector name")
    description: str = Field(..., description="Connector description")
    connection_string_hint: str = Field(..., description="Hint for connection string format")
    required_fields: list[str] = Field(default_factory=list, description="Required configuration fields")
    optional_fields: list[str] = Field(default_factory=list, description="Optional configuration fields")


class CreateETLJobRequest(BaseModel):
    """Request body for creating a new ETL job."""

    connector_type: str = Field(
        ...,
        description="Type of source connector (fhir, csv, hl7v2, ccda, database)",
        pattern="^(fhir|csv|hl7v2|ccda|database)$",
    )
    connection_string: str = Field(
        ...,
        description="Connection string or URL for the data source",
        min_length=1,
    )
    source_name: str = Field(
        default="default",
        description="Human-readable name for the data source",
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of records to process per batch",
    )
    max_records: int | None = Field(
        default=None,
        ge=1,
        description="Maximum records to process (None = unlimited)",
    )
    patient_ids: list[str] | None = Field(
        default=None,
        description="Specific patient IDs to process (None = all patients)",
    )
    start_date: datetime | None = Field(
        default=None,
        description="Start date filter for records",
    )
    end_date: datetime | None = Field(
        default=None,
        description="End date filter for records",
    )
    skip_on_error: bool = Field(
        default=True,
        description="Continue processing if individual records fail",
    )
    max_errors: int = Field(
        default=100,
        ge=1,
        description="Stop job after this many errors",
    )
    connector_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional connector-specific options",
    )
    etl_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional ETL-specific options",
    )


class ETLJobProgressResponse(BaseModel):
    """Progress information for an ETL job."""

    current_phase: str
    phase_progress_percent: float
    overall_progress_percent: float
    records_in_phase: int
    total_records_estimate: int
    current_record_id: str | None
    phases_completed: list[str]
    eta_seconds: float | None


class ETLJobStatisticsResponse(BaseModel):
    """Statistics for an ETL job."""

    total_records: int
    patients_processed: int
    visits_processed: int
    conditions_processed: int
    drugs_processed: int
    procedures_processed: int
    measurements_processed: int
    observations_processed: int
    records_created: int
    records_updated: int
    records_skipped: int
    unmapped_codes: int
    retries_performed: int


class ETLJobErrorResponse(BaseModel):
    """Error information from an ETL job."""

    timestamp: str
    phase: str
    record_id: str | None
    error_type: str
    error_message: str
    is_retryable: bool
    retry_count: int


class ETLJobConfigResponse(BaseModel):
    """Configuration of an ETL job."""

    connector_type: str
    connection_string: str
    source_name: str
    batch_size: int
    max_records: int | None
    patient_ids: list[str] | None
    start_date: str | None
    end_date: str | None
    skip_on_error: bool
    max_errors: int


class ETLJobResponse(BaseModel):
    """Response containing ETL job details."""

    job_id: str
    state: str
    config: ETLJobConfigResponse
    progress: ETLJobProgressResponse
    statistics: ETLJobStatisticsResponse
    errors: list[ETLJobErrorResponse]
    warnings: list[str]
    created_at: str
    started_at: str | None
    completed_at: str | None
    duration_seconds: float | None


class ETLJobListResponse(BaseModel):
    """Response containing a list of ETL jobs."""

    jobs: list[ETLJobResponse]
    total: int


class CreateETLJobResponse(BaseModel):
    """Response after creating an ETL job."""

    job_id: str
    state: str
    message: str


class CancelETLJobResponse(BaseModel):
    """Response after cancelling an ETL job."""

    job_id: str
    cancelled: bool
    message: str


class DeleteETLJobResponse(BaseModel):
    """Response after deleting an ETL job."""

    job_id: str
    deleted: bool
    message: str


class ConnectorListResponse(BaseModel):
    """Response containing available connector types."""

    connectors: list[ConnectorInfo]


# =============================================================================
# Helper Functions
# =============================================================================


def _job_to_response(job: Any) -> ETLJobResponse:
    """Convert an ETLJob to an ETLJobResponse."""
    job_dict = job.to_dict()

    return ETLJobResponse(
        job_id=job_dict["job_id"],
        state=job_dict["state"],
        config=ETLJobConfigResponse(
            connector_type=job_dict["config"]["connector_type"],
            connection_string=job_dict["config"]["connection_string"],
            source_name=job_dict["config"]["source_name"],
            batch_size=job_dict["config"]["batch_size"],
            max_records=job_dict["config"]["max_records"],
            patient_ids=job_dict["config"]["patient_ids"],
            start_date=job_dict["config"]["start_date"],
            end_date=job_dict["config"]["end_date"],
            skip_on_error=job_dict["config"]["skip_on_error"],
            max_errors=job_dict["config"]["max_errors"],
        ),
        progress=ETLJobProgressResponse(
            current_phase=job_dict["progress"]["current_phase"],
            phase_progress_percent=job_dict["progress"]["phase_progress_percent"],
            overall_progress_percent=job_dict["progress"]["overall_progress_percent"],
            records_in_phase=job_dict["progress"]["records_in_phase"],
            total_records_estimate=job_dict["progress"]["total_records_estimate"],
            current_record_id=job_dict["progress"]["current_record_id"],
            phases_completed=job_dict["progress"]["phases_completed"],
            eta_seconds=job_dict["progress"]["eta_seconds"],
        ),
        statistics=ETLJobStatisticsResponse(
            total_records=job_dict["statistics"]["total_records"],
            patients_processed=job_dict["statistics"]["patients_processed"],
            visits_processed=job_dict["statistics"]["visits_processed"],
            conditions_processed=job_dict["statistics"]["conditions_processed"],
            drugs_processed=job_dict["statistics"]["drugs_processed"],
            procedures_processed=job_dict["statistics"]["procedures_processed"],
            measurements_processed=job_dict["statistics"]["measurements_processed"],
            observations_processed=job_dict["statistics"]["observations_processed"],
            records_created=job_dict["statistics"]["records_created"],
            records_updated=job_dict["statistics"]["records_updated"],
            records_skipped=job_dict["statistics"]["records_skipped"],
            unmapped_codes=job_dict["statistics"]["unmapped_codes"],
            retries_performed=job_dict["statistics"]["retries_performed"],
        ),
        errors=[
            ETLJobErrorResponse(
                timestamp=e["timestamp"],
                phase=e["phase"],
                record_id=e["record_id"],
                error_type=e["error_type"],
                error_message=e["error_message"],
                is_retryable=e["is_retryable"],
                retry_count=e["retry_count"],
            )
            for e in job_dict["errors"]
        ],
        warnings=job_dict["warnings"],
        created_at=job_dict["created_at"],
        started_at=job_dict["started_at"],
        completed_at=job_dict["completed_at"],
        duration_seconds=job_dict["duration_seconds"],
    )


# =============================================================================
# Available Connectors
# =============================================================================

AVAILABLE_CONNECTORS: list[ConnectorInfo] = [
    ConnectorInfo(
        type="fhir",
        name="FHIR R4",
        description="Connect to FHIR R4 compliant servers to extract clinical data",
        connection_string_hint="https://fhir.server.com/fhir",
        required_fields=["base_url"],
        optional_fields=["auth_token", "client_id", "client_secret", "scope"],
    ),
    ConnectorInfo(
        type="csv",
        name="CSV Files",
        description="Import clinical data from CSV files in a directory",
        connection_string_hint="/path/to/csv/directory",
        required_fields=["base_dir"],
        optional_fields=["encoding", "delimiter", "date_format"],
    ),
    ConnectorInfo(
        type="hl7v2",
        name="HL7 v2 Messages",
        description="Parse HL7 v2.x messages from a directory or message queue",
        connection_string_hint="/path/to/hl7/messages",
        required_fields=["messages_dir"],
        optional_fields=["message_pattern", "encoding"],
    ),
    ConnectorInfo(
        type="ccda",
        name="C-CDA Documents",
        description="Import clinical data from C-CDA/CCD XML documents",
        connection_string_hint="/path/to/ccda/documents",
        required_fields=["documents_path"],
        optional_fields=["schema_validation", "extract_unstructured"],
    ),
    ConnectorInfo(
        type="database",
        name="Database",
        description="Connect directly to a source database (PostgreSQL, MySQL, SQL Server)",
        connection_string_hint="postgresql://user:pass@host:5432/dbname",
        required_fields=["connection_string"],
        optional_fields=["schema", "table_mapping", "query_timeout"],
    ),
]


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/connectors",
    response_model=ConnectorListResponse,
    summary="List available connector types",
    description="Get a list of all available source connector types that can be used for ETL jobs.",
)
async def list_connectors() -> ConnectorListResponse:
    """List all available connector types.

    Returns information about each connector including required and optional
    configuration fields.

    Returns:
        ConnectorListResponse with list of available connectors.
    """
    return ConnectorListResponse(connectors=AVAILABLE_CONNECTORS)


@router.post(
    "/jobs",
    response_model=CreateETLJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ETL job",
    description="Create a new ETL job to extract data from a clinical source.",
)
async def create_etl_job(
    request: CreateETLJobRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> CreateETLJobResponse:
    """Create a new ETL job.

    The job is created in PENDING state and can be started by calling
    the job run endpoint or it will be picked up by the background scheduler.

    Args:
        request: Job configuration.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        CreateETLJobResponse with job ID and initial state.

    Raises:
        HTTPException: If configuration is invalid.
    """
    try:
        orchestrator = get_etl_orchestrator(db)

        config = ETLJobConfig(
            connector_type=request.connector_type,
            connection_string=request.connection_string,
            source_name=request.source_name,
            batch_size=request.batch_size,
            max_records=request.max_records,
            patient_ids=request.patient_ids,
            start_date=request.start_date,
            end_date=request.end_date,
            skip_on_error=request.skip_on_error,
            max_errors=request.max_errors,
            connector_options=request.connector_options,
            etl_options=request.etl_options,
        )

        job = await orchestrator.create_job(config)

        # Schedule job to run in background
        background_tasks.add_task(orchestrator.run_job, job.job_id)

        logger.info(f"Created ETL job {job.job_id} with connector type {request.connector_type}")

        return CreateETLJobResponse(
            job_id=str(job.job_id),
            state=job.state.value,
            message=f"ETL job created and scheduled for execution",
        )

    except ValueError as e:
        logger.warning(f"Invalid ETL job configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create ETL job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ETL job",
        )


@router.get(
    "/jobs",
    response_model=ETLJobListResponse,
    summary="List ETL jobs",
    description="Get a list of all ETL jobs with optional filtering by state.",
)
async def list_etl_jobs(
    db: DbSession,
    state: str | None = Query(
        default=None,
        description="Filter by job state (pending, running, completed, failed, cancelled)",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of jobs to return",
    ),
) -> ETLJobListResponse:
    """List all ETL jobs with optional filtering.

    Args:
        db: Database session.
        state: Optional state filter.
        limit: Maximum jobs to return.

    Returns:
        ETLJobListResponse with list of jobs.

    Raises:
        HTTPException: If state filter is invalid.
    """
    try:
        orchestrator = get_etl_orchestrator(db)

        # Parse state filter
        state_filter: ETLJobState | None = None
        if state:
            try:
                state_filter = ETLJobState(state.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid state filter: {state}. Must be one of: pending, running, completed, failed, cancelled",
                )

        jobs = await orchestrator.list_jobs(state=state_filter, limit=limit)

        return ETLJobListResponse(
            jobs=[_job_to_response(job) for job in jobs],
            total=len(jobs),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list ETL jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list ETL jobs",
        )


@router.get(
    "/jobs/{job_id}",
    response_model=ETLJobResponse,
    summary="Get ETL job status",
    description="Get the current status and details of a specific ETL job.",
)
async def get_etl_job(
    job_id: UUID,
    db: DbSession,
) -> ETLJobResponse:
    """Get status of a specific ETL job.

    Args:
        job_id: UUID of the job.
        db: Database session.

    Returns:
        ETLJobResponse with job details.

    Raises:
        HTTPException: If job is not found.
    """
    try:
        orchestrator = get_etl_orchestrator(db)

        job = await orchestrator.get_job_status(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ETL job {job_id} not found",
            )

        return _job_to_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ETL job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ETL job status",
        )


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=CancelETLJobResponse,
    summary="Cancel ETL job",
    description="Cancel a running or pending ETL job.",
)
async def cancel_etl_job(
    job_id: UUID,
    db: DbSession,
) -> CancelETLJobResponse:
    """Cancel a running or pending ETL job.

    Args:
        job_id: UUID of the job to cancel.
        db: Database session.

    Returns:
        CancelETLJobResponse with cancellation result.

    Raises:
        HTTPException: If job is not found.
    """
    try:
        orchestrator = get_etl_orchestrator(db)

        # First check if job exists
        job = await orchestrator.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ETL job {job_id} not found",
            )

        cancelled = await orchestrator.cancel_job(job_id)

        if cancelled:
            logger.info(f"Cancelled ETL job {job_id}")
            return CancelETLJobResponse(
                job_id=str(job_id),
                cancelled=True,
                message="Job cancellation requested",
            )
        else:
            return CancelETLJobResponse(
                job_id=str(job_id),
                cancelled=False,
                message=f"Job cannot be cancelled (state: {job.state.value})",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel ETL job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel ETL job",
        )


@router.delete(
    "/jobs/{job_id}",
    response_model=DeleteETLJobResponse,
    summary="Delete ETL job",
    description="Delete a completed, failed, or cancelled ETL job from the registry.",
)
async def delete_etl_job(
    job_id: UUID,
    db: DbSession,
) -> DeleteETLJobResponse:
    """Delete a completed ETL job.

    Only jobs that are not pending or running can be deleted.

    Args:
        job_id: UUID of the job to delete.
        db: Database session.

    Returns:
        DeleteETLJobResponse with deletion result.

    Raises:
        HTTPException: If job is not found or cannot be deleted.
    """
    try:
        orchestrator = get_etl_orchestrator(db)

        # First check if job exists
        job = await orchestrator.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ETL job {job_id} not found",
            )

        deleted = await orchestrator.delete_job(job_id)

        if deleted:
            logger.info(f"Deleted ETL job {job_id}")
            return DeleteETLJobResponse(
                job_id=str(job_id),
                deleted=True,
                message="Job deleted successfully",
            )
        else:
            return DeleteETLJobResponse(
                job_id=str(job_id),
                deleted=False,
                message=f"Job cannot be deleted (state: {job.state.value}). Only completed, failed, or cancelled jobs can be deleted.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete ETL job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete ETL job",
        )


@router.get(
    "/stats",
    summary="Get ETL orchestrator statistics",
    description="Get statistics about the ETL orchestrator and job registry.",
)
async def get_etl_stats(db: DbSession) -> dict[str, Any]:
    """Get ETL orchestrator statistics.

    Returns:
        Dictionary with orchestrator statistics.
    """
    try:
        orchestrator = get_etl_orchestrator(db)
        source_service = get_source_config_service()

        etl_stats = orchestrator.get_stats()
        source_stats = source_service.get_stats()

        return {**etl_stats, **source_stats}
    except Exception as e:
        logger.error(f"Failed to get ETL stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ETL statistics",
        )
