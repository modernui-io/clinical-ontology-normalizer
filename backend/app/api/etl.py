"""ETL job management API endpoints.

This module provides REST API endpoints for managing ETL (Extract, Transform, Load)
jobs that process clinical data from various sources into the OMOP CDM format.

Endpoints:
    # Jobs
    POST /etl/jobs - Create a new ETL job
    GET /etl/jobs - List all ETL jobs with optional filtering
    GET /etl/jobs/{job_id} - Get status of a specific job
    POST /etl/jobs/{job_id}/cancel - Cancel a running or pending job
    DELETE /etl/jobs/{job_id} - Delete a completed/failed job
    GET /etl/connectors - List available connector types

    # Sources
    GET /etl/sources - List configured data sources
    POST /etl/sources - Create new source configuration
    GET /etl/sources/{id} - Get source details
    PUT /etl/sources/{id} - Update source configuration
    DELETE /etl/sources/{id} - Delete source
    POST /etl/sources/{id}/test - Test connection
    GET /etl/sources/{id}/preview - Preview sample data

    # Pipelines
    GET /etl/pipelines - List pipelines
    POST /etl/pipelines - Create pipeline
    GET /etl/pipelines/{id} - Get pipeline details
    PUT /etl/pipelines/{id} - Update pipeline
    DELETE /etl/pipelines/{id} - Delete pipeline
    PUT /etl/pipelines/{id}/schedule - Set schedule
    POST /etl/pipelines/{id}/run - Trigger manual run
    GET /etl/pipelines/{id}/runs - Get run history
"""

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
from app.services.source_config_service import (
    ConnectionParams,
    ConnectionStatus,
    PipelineSchedule,
    PipelineStage,
    PipelineStatus,
    ScheduleFrequency,
    SourceConfig,
    SourceCredentials,
    SourceType,
    get_source_config_service,
)

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
# Source Configuration Request/Response Models
# =============================================================================


class CredentialsRequest(BaseModel):
    """Request body for source credentials."""

    username: str | None = Field(default=None, description="Username for authentication")
    password: str | None = Field(default=None, description="Password for authentication")
    api_key: str | None = Field(default=None, description="API key for token-based auth")
    client_id: str | None = Field(default=None, description="OAuth2 client ID")
    client_secret: str | None = Field(default=None, description="OAuth2 client secret")
    auth_token: str | None = Field(default=None, description="Bearer token for FHIR servers")
    extra: dict[str, str] = Field(default_factory=dict, description="Additional credentials")


class ConnectionParamsRequest(BaseModel):
    """Request body for connection parameters."""

    host: str | None = Field(default=None, description="Hostname or IP address")
    port: int | None = Field(default=None, ge=1, le=65535, description="Port number")
    path: str | None = Field(default=None, description="Path (URL path or filesystem path)")
    database: str | None = Field(default=None, description="Database name")
    schema_name: str | None = Field(default=None, alias="schema", description="Schema name")
    ssl_enabled: bool = Field(default=True, description="Whether to use SSL/TLS")
    verify_ssl: bool = Field(default=True, description="Whether to verify SSL certificates")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Connection timeout")
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional parameters")


class CreateSourceRequest(BaseModel):
    """Request body for creating a new data source."""

    name: str = Field(..., min_length=1, max_length=255, description="Source name")
    description: str = Field(default="", max_length=1000, description="Source description")
    source_type: str = Field(
        ...,
        description="Type of data source (fhir, hl7v2, ccda, csv, database)",
        pattern="^(fhir|hl7v2|ccda|csv|database)$",
    )
    connection_params: ConnectionParamsRequest = Field(
        ..., description="Connection parameters"
    )
    credentials: CredentialsRequest | None = Field(
        default=None, description="Authentication credentials"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class UpdateSourceRequest(BaseModel):
    """Request body for updating a data source."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    connection_params: ConnectionParamsRequest | None = None
    credentials: CredentialsRequest | None = None
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class CredentialsResponse(BaseModel):
    """Response containing masked credentials."""

    username: str | None
    password: str | None  # Masked
    api_key: str | None  # Masked
    client_id: str | None
    client_secret: str | None  # Masked
    auth_token: str | None  # Masked
    extra: dict[str, str] | None


class ConnectionParamsResponse(BaseModel):
    """Response containing connection parameters."""

    host: str | None
    port: int | None
    path: str | None
    database: str | None
    schema: str | None
    ssl_enabled: bool
    verify_ssl: bool
    timeout_seconds: int
    extra: dict[str, Any]


class SourceResponse(BaseModel):
    """Response containing data source details."""

    id: str
    name: str
    description: str
    source_type: str
    connection_params: ConnectionParamsResponse
    credentials: CredentialsResponse | None
    status: str
    enabled: bool
    last_tested_at: str | None
    last_sync_at: str | None
    test_result: str | None
    created_at: str
    updated_at: str
    metadata: dict[str, Any]


class SourceListResponse(BaseModel):
    """Response containing list of data sources."""

    sources: list[SourceResponse]
    total: int


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""

    success: bool
    message: str
    latency_ms: float | None
    server_info: dict[str, Any]
    error_details: str | None
    tested_at: str


class SampleDataResponse(BaseModel):
    """Response containing sample data preview."""

    source_id: str
    record_count: int
    records: list[dict[str, Any]]
    schema_info: dict[str, Any]
    fetched_at: str


# =============================================================================
# Pipeline Request/Response Models
# =============================================================================


class PipelineScheduleRequest(BaseModel):
    """Request body for pipeline schedule."""

    frequency: str = Field(
        default="manual",
        description="Schedule frequency",
        pattern="^(manual|hourly|daily|weekly|monthly|custom)$",
    )
    cron_expression: str | None = Field(default=None, description="Cron expression for custom")
    time_of_day: str = Field(default="00:00", pattern="^[0-2][0-9]:[0-5][0-9]$")
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    timezone: str = Field(default="UTC")
    enabled: bool = Field(default=False)


class PipelineStageRequest(BaseModel):
    """Request body for pipeline stage."""

    name: str = Field(..., min_length=1, max_length=100)
    stage_type: str = Field(..., description="Type of stage (extract, transform, load)")
    config: dict[str, Any] = Field(default_factory=dict)
    order: int = Field(default=0, ge=0)
    enabled: bool = Field(default=True)


class CreatePipelineRequest(BaseModel):
    """Request body for creating a new pipeline."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    source_id: str = Field(..., description="UUID of the data source")
    schedule: PipelineScheduleRequest | None = None
    stages: list[PipelineStageRequest] | None = None
    batch_size: int = Field(default=100, ge=1, le=10000)
    max_records: int | None = Field(default=None, ge=1)
    skip_on_error: bool = Field(default=True)


class UpdatePipelineRequest(BaseModel):
    """Request body for updating a pipeline."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|paused|disabled)$")
    schedule: PipelineScheduleRequest | None = None
    stages: list[PipelineStageRequest] | None = None
    batch_size: int | None = Field(default=None, ge=1, le=10000)
    max_records: int | None = None
    skip_on_error: bool | None = None


class PipelineScheduleResponse(BaseModel):
    """Response containing pipeline schedule."""

    frequency: str
    cron_expression: str | None
    time_of_day: str
    day_of_week: int | None
    day_of_month: int | None
    timezone: str
    enabled: bool


class PipelineStageResponse(BaseModel):
    """Response containing pipeline stage."""

    name: str
    stage_type: str
    config: dict[str, Any]
    order: int
    enabled: bool


class PipelineRunResponse(BaseModel):
    """Response containing pipeline run details."""

    id: str
    pipeline_id: str
    status: str
    started_at: str
    completed_at: str | None
    records_processed: int
    records_failed: int
    error_message: str | None
    duration_seconds: float | None


class PipelineResponse(BaseModel):
    """Response containing pipeline details."""

    id: str
    name: str
    description: str
    source_id: str
    status: str
    schedule: PipelineScheduleResponse
    stages: list[PipelineStageResponse]
    batch_size: int
    max_records: int | None
    skip_on_error: bool
    created_at: str
    updated_at: str
    last_run_at: str | None
    last_run_status: str | None
    run_count: int


class PipelineListResponse(BaseModel):
    """Response containing list of pipelines."""

    pipelines: list[PipelineResponse]
    total: int


class PipelineRunListResponse(BaseModel):
    """Response containing list of pipeline runs."""

    runs: list[PipelineRunResponse]
    total: int


class TriggerPipelineResponse(BaseModel):
    """Response after triggering a pipeline run."""

    run_id: str
    pipeline_id: str
    status: str
    message: str


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


# =============================================================================
# Source Configuration Helper Functions
# =============================================================================


def _source_to_response(source: SourceConfig, include_credentials: bool = True) -> SourceResponse:
    """Convert a SourceConfig to a SourceResponse."""
    source_dict = source.to_dict(include_credentials=include_credentials)

    credentials = None
    if include_credentials and "credentials" in source_dict:
        creds = source_dict["credentials"]
        credentials = CredentialsResponse(
            username=creds.get("username"),
            password=creds.get("password"),
            api_key=creds.get("api_key"),
            client_id=creds.get("client_id"),
            client_secret=creds.get("client_secret"),
            auth_token=creds.get("auth_token"),
            extra=creds.get("extra"),
        )

    conn_params = source_dict["connection_params"]
    return SourceResponse(
        id=source_dict["id"],
        name=source_dict["name"],
        description=source_dict["description"],
        source_type=source_dict["source_type"],
        connection_params=ConnectionParamsResponse(
            host=conn_params.get("host"),
            port=conn_params.get("port"),
            path=conn_params.get("path"),
            database=conn_params.get("database"),
            schema=conn_params.get("schema"),
            ssl_enabled=conn_params.get("ssl_enabled", True),
            verify_ssl=conn_params.get("verify_ssl", True),
            timeout_seconds=conn_params.get("timeout_seconds", 30),
            extra=conn_params.get("extra", {}),
        ),
        credentials=credentials,
        status=source_dict["status"],
        enabled=source_dict["enabled"],
        last_tested_at=source_dict["last_tested_at"],
        last_sync_at=source_dict["last_sync_at"],
        test_result=source_dict["test_result"],
        created_at=source_dict["created_at"],
        updated_at=source_dict["updated_at"],
        metadata=source_dict["metadata"],
    )


def _pipeline_to_response(pipeline: Any) -> PipelineResponse:
    """Convert a Pipeline to a PipelineResponse."""
    pipeline_dict = pipeline.to_dict()

    schedule = pipeline_dict["schedule"]
    stages = pipeline_dict["stages"]

    return PipelineResponse(
        id=pipeline_dict["id"],
        name=pipeline_dict["name"],
        description=pipeline_dict["description"],
        source_id=pipeline_dict["source_id"],
        status=pipeline_dict["status"],
        schedule=PipelineScheduleResponse(
            frequency=schedule["frequency"],
            cron_expression=schedule.get("cron_expression"),
            time_of_day=schedule["time_of_day"],
            day_of_week=schedule.get("day_of_week"),
            day_of_month=schedule.get("day_of_month"),
            timezone=schedule["timezone"],
            enabled=schedule["enabled"],
        ),
        stages=[
            PipelineStageResponse(
                name=s["name"],
                stage_type=s["stage_type"],
                config=s["config"],
                order=s["order"],
                enabled=s["enabled"],
            )
            for s in stages
        ],
        batch_size=pipeline_dict["batch_size"],
        max_records=pipeline_dict["max_records"],
        skip_on_error=pipeline_dict["skip_on_error"],
        created_at=pipeline_dict["created_at"],
        updated_at=pipeline_dict["updated_at"],
        last_run_at=pipeline_dict["last_run_at"],
        last_run_status=pipeline_dict["last_run_status"],
        run_count=pipeline_dict["run_count"],
    )


def _run_to_response(run: Any) -> PipelineRunResponse:
    """Convert a PipelineRun to a PipelineRunResponse."""
    run_dict = run.to_dict()

    return PipelineRunResponse(
        id=run_dict["id"],
        pipeline_id=run_dict["pipeline_id"],
        status=run_dict["status"],
        started_at=run_dict["started_at"],
        completed_at=run_dict["completed_at"],
        records_processed=run_dict["records_processed"],
        records_failed=run_dict["records_failed"],
        error_message=run_dict["error_message"],
        duration_seconds=run_dict["duration_seconds"],
    )


# =============================================================================
# Source Configuration API Endpoints
# =============================================================================


@router.get(
    "/sources",
    response_model=SourceListResponse,
    summary="List data sources",
    description="Get a list of all configured data sources.",
)
async def list_sources(
    source_type: str | None = Query(
        default=None,
        description="Filter by source type (fhir, hl7v2, ccda, csv, database)",
    ),
    enabled_only: bool = Query(
        default=False,
        description="Only return enabled sources",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of sources to return",
    ),
) -> SourceListResponse:
    """List all configured data sources.

    Args:
        source_type: Optional filter by type.
        enabled_only: Only return enabled sources.
        limit: Maximum sources to return.

    Returns:
        SourceListResponse with list of sources.
    """
    try:
        service = get_source_config_service()

        type_filter = None
        if source_type:
            try:
                type_filter = SourceType(source_type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid source type: {source_type}",
                )

        sources = await service.list_sources(
            source_type=type_filter,
            enabled_only=enabled_only,
            limit=limit,
        )

        return SourceListResponse(
            sources=[_source_to_response(s) for s in sources],
            total=len(sources),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list sources: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list data sources",
        )


@router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create data source",
    description="Create a new data source configuration.",
)
async def create_source(
    request: CreateSourceRequest,
) -> SourceResponse:
    """Create a new data source configuration.

    Args:
        request: Source configuration.

    Returns:
        Created SourceResponse.
    """
    try:
        service = get_source_config_service()

        # Convert request to service objects
        source_type = SourceType(request.source_type.lower())

        connection_params = ConnectionParams(
            host=request.connection_params.host,
            port=request.connection_params.port,
            path=request.connection_params.path,
            database=request.connection_params.database,
            schema=request.connection_params.schema_name,
            ssl_enabled=request.connection_params.ssl_enabled,
            verify_ssl=request.connection_params.verify_ssl,
            timeout_seconds=request.connection_params.timeout_seconds,
            extra=request.connection_params.extra,
        )

        credentials = None
        if request.credentials:
            credentials = SourceCredentials(
                username=request.credentials.username,
                password=request.credentials.password,
                api_key=request.credentials.api_key,
                client_id=request.credentials.client_id,
                client_secret=request.credentials.client_secret,
                auth_token=request.credentials.auth_token,
                extra=request.credentials.extra,
            )

        source = await service.create_source(
            name=request.name,
            source_type=source_type,
            connection_params=connection_params,
            credentials=credentials,
            description=request.description,
            metadata=request.metadata,
        )

        logger.info(f"Created source {source.id}: {request.name}")
        return _source_to_response(source)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create source: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create data source",
        )


@router.get(
    "/sources/{source_id}",
    response_model=SourceResponse,
    summary="Get data source",
    description="Get details of a specific data source.",
)
async def get_source(
    source_id: UUID,
) -> SourceResponse:
    """Get a specific data source by ID.

    Args:
        source_id: Source UUID.

    Returns:
        SourceResponse with source details.
    """
    try:
        service = get_source_config_service()
        source = await service.get_source(source_id)

        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        return _source_to_response(source)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source {source_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get data source",
        )


@router.put(
    "/sources/{source_id}",
    response_model=SourceResponse,
    summary="Update data source",
    description="Update an existing data source configuration.",
)
async def update_source(
    source_id: UUID,
    request: UpdateSourceRequest,
) -> SourceResponse:
    """Update a data source configuration.

    Args:
        source_id: Source UUID.
        request: Updated configuration.

    Returns:
        Updated SourceResponse.
    """
    try:
        service = get_source_config_service()

        # Check if source exists
        existing = await service.get_source(source_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Convert request to service objects
        connection_params = None
        if request.connection_params:
            connection_params = ConnectionParams(
                host=request.connection_params.host,
                port=request.connection_params.port,
                path=request.connection_params.path,
                database=request.connection_params.database,
                schema=request.connection_params.schema_name,
                ssl_enabled=request.connection_params.ssl_enabled,
                verify_ssl=request.connection_params.verify_ssl,
                timeout_seconds=request.connection_params.timeout_seconds,
                extra=request.connection_params.extra,
            )

        credentials = None
        if request.credentials:
            credentials = SourceCredentials(
                username=request.credentials.username,
                password=request.credentials.password,
                api_key=request.credentials.api_key,
                client_id=request.credentials.client_id,
                client_secret=request.credentials.client_secret,
                auth_token=request.credentials.auth_token,
                extra=request.credentials.extra,
            )

        source = await service.update_source(
            source_id=source_id,
            name=request.name,
            description=request.description,
            connection_params=connection_params,
            credentials=credentials,
            enabled=request.enabled,
            metadata=request.metadata,
        )

        logger.info(f"Updated source {source_id}")
        return _source_to_response(source)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update source {source_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update data source",
        )


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete data source",
    description="Delete a data source configuration.",
)
async def delete_source(
    source_id: UUID,
) -> None:
    """Delete a data source configuration.

    Args:
        source_id: Source UUID.
    """
    try:
        service = get_source_config_service()
        deleted = await service.delete_source(source_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        logger.info(f"Deleted source {source_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete source {source_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete data source",
        )


@router.post(
    "/sources/{source_id}/test",
    response_model=ConnectionTestResponse,
    summary="Test source connection",
    description="Test the connection to a data source.",
)
async def test_source_connection(
    source_id: UUID,
) -> ConnectionTestResponse:
    """Test the connection to a data source.

    Args:
        source_id: Source UUID.

    Returns:
        ConnectionTestResponse with test results.
    """
    try:
        service = get_source_config_service()

        # Check if source exists
        source = await service.get_source(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        result = await service.test_connection(source_id)

        return ConnectionTestResponse(
            success=result.success,
            message=result.message,
            latency_ms=result.latency_ms,
            server_info=result.server_info,
            error_details=result.error_details,
            tested_at=result.tested_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test connection for {source_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test connection",
        )


@router.get(
    "/sources/{source_id}/preview",
    response_model=SampleDataResponse,
    summary="Preview sample data",
    description="Get sample data from a data source for preview.",
)
async def preview_source_data(
    source_id: UUID,
    limit: int = Query(default=10, ge=1, le=100, description="Number of sample records"),
) -> SampleDataResponse:
    """Get sample data from a data source.

    Args:
        source_id: Source UUID.
        limit: Number of sample records to fetch.

    Returns:
        SampleDataResponse with sample records.
    """
    try:
        service = get_source_config_service()

        # Check if source exists
        source = await service.get_source(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        preview = await service.get_sample_data(source_id, limit)

        if not preview:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch sample data",
            )

        return SampleDataResponse(
            source_id=str(preview.source_id),
            record_count=preview.record_count,
            records=preview.records,
            schema_info=preview.schema_info,
            fetched_at=preview.fetched_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview data for {source_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview sample data",
        )


# =============================================================================
# Pipeline API Endpoints
# =============================================================================


@router.get(
    "/pipelines",
    response_model=PipelineListResponse,
    summary="List pipelines",
    description="Get a list of all ETL pipelines.",
)
async def list_pipelines(
    source_id: UUID | None = Query(default=None, description="Filter by source ID"),
    pipeline_status: str | None = Query(
        default=None,
        description="Filter by status (active, paused, disabled, error)",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
) -> PipelineListResponse:
    """List all ETL pipelines.

    Args:
        source_id: Optional filter by source.
        pipeline_status: Optional filter by status.
        limit: Maximum pipelines to return.

    Returns:
        PipelineListResponse with list of pipelines.
    """
    try:
        service = get_source_config_service()

        status_filter = None
        if pipeline_status:
            try:
                status_filter = PipelineStatus(pipeline_status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pipeline status: {pipeline_status}",
                )

        pipelines = await service.list_pipelines(
            source_id=source_id,
            status=status_filter,
            limit=limit,
        )

        return PipelineListResponse(
            pipelines=[_pipeline_to_response(p) for p in pipelines],
            total=len(pipelines),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list pipelines: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list pipelines",
        )


@router.post(
    "/pipelines",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create pipeline",
    description="Create a new ETL pipeline.",
)
async def create_pipeline(
    request: CreatePipelineRequest,
) -> PipelineResponse:
    """Create a new ETL pipeline.

    Args:
        request: Pipeline configuration.

    Returns:
        Created PipelineResponse.
    """
    try:
        service = get_source_config_service()

        # Validate source exists
        try:
            source_uuid = UUID(request.source_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_id: {request.source_id}",
            )

        source = await service.get_source(source_uuid)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {request.source_id} not found",
            )

        # Convert schedule
        schedule = None
        if request.schedule:
            schedule = PipelineSchedule(
                frequency=ScheduleFrequency(request.schedule.frequency),
                cron_expression=request.schedule.cron_expression,
                time_of_day=request.schedule.time_of_day,
                day_of_week=request.schedule.day_of_week,
                day_of_month=request.schedule.day_of_month,
                timezone=request.schedule.timezone,
                enabled=request.schedule.enabled,
            )

        # Convert stages
        stages = None
        if request.stages:
            stages = [
                PipelineStage(
                    name=s.name,
                    stage_type=s.stage_type,
                    config=s.config,
                    order=s.order,
                    enabled=s.enabled,
                )
                for s in request.stages
            ]

        pipeline = await service.create_pipeline(
            name=request.name,
            source_id=source_uuid,
            description=request.description,
            schedule=schedule,
            stages=stages,
            batch_size=request.batch_size,
            max_records=request.max_records,
            skip_on_error=request.skip_on_error,
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create pipeline",
            )

        logger.info(f"Created pipeline {pipeline.id}: {request.name}")
        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pipeline",
        )


@router.get(
    "/pipelines/{pipeline_id}",
    response_model=PipelineResponse,
    summary="Get pipeline",
    description="Get details of a specific pipeline.",
)
async def get_pipeline(
    pipeline_id: UUID,
) -> PipelineResponse:
    """Get a specific pipeline by ID.

    Args:
        pipeline_id: Pipeline UUID.

    Returns:
        PipelineResponse with pipeline details.
    """
    try:
        service = get_source_config_service()
        pipeline = await service.get_pipeline(pipeline_id)

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline",
        )


@router.put(
    "/pipelines/{pipeline_id}",
    response_model=PipelineResponse,
    summary="Update pipeline",
    description="Update an existing pipeline configuration.",
)
async def update_pipeline(
    pipeline_id: UUID,
    request: UpdatePipelineRequest,
) -> PipelineResponse:
    """Update a pipeline configuration.

    Args:
        pipeline_id: Pipeline UUID.
        request: Updated configuration.

    Returns:
        Updated PipelineResponse.
    """
    try:
        service = get_source_config_service()

        # Check if pipeline exists
        existing = await service.get_pipeline(pipeline_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        # Convert status
        pipeline_status = None
        if request.status:
            pipeline_status = PipelineStatus(request.status)

        # Convert schedule
        schedule = None
        if request.schedule:
            schedule = PipelineSchedule(
                frequency=ScheduleFrequency(request.schedule.frequency),
                cron_expression=request.schedule.cron_expression,
                time_of_day=request.schedule.time_of_day,
                day_of_week=request.schedule.day_of_week,
                day_of_month=request.schedule.day_of_month,
                timezone=request.schedule.timezone,
                enabled=request.schedule.enabled,
            )

        # Convert stages
        stages = None
        if request.stages:
            stages = [
                PipelineStage(
                    name=s.name,
                    stage_type=s.stage_type,
                    config=s.config,
                    order=s.order,
                    enabled=s.enabled,
                )
                for s in request.stages
            ]

        pipeline = await service.update_pipeline(
            pipeline_id=pipeline_id,
            name=request.name,
            description=request.description,
            status=pipeline_status,
            schedule=schedule,
            stages=stages,
            batch_size=request.batch_size,
            max_records=request.max_records,
            skip_on_error=request.skip_on_error,
        )

        logger.info(f"Updated pipeline {pipeline_id}")
        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update pipeline {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update pipeline",
        )


@router.delete(
    "/pipelines/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete pipeline",
    description="Delete a pipeline.",
)
async def delete_pipeline(
    pipeline_id: UUID,
) -> None:
    """Delete a pipeline.

    Args:
        pipeline_id: Pipeline UUID.
    """
    try:
        service = get_source_config_service()
        deleted = await service.delete_pipeline(pipeline_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        logger.info(f"Deleted pipeline {pipeline_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete pipeline {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete pipeline",
        )


@router.put(
    "/pipelines/{pipeline_id}/schedule",
    response_model=PipelineResponse,
    summary="Set pipeline schedule",
    description="Update the schedule for a pipeline.",
)
async def set_pipeline_schedule(
    pipeline_id: UUID,
    request: PipelineScheduleRequest,
) -> PipelineResponse:
    """Set or update pipeline schedule.

    Args:
        pipeline_id: Pipeline UUID.
        request: Schedule configuration.

    Returns:
        Updated PipelineResponse.
    """
    try:
        service = get_source_config_service()

        schedule = PipelineSchedule(
            frequency=ScheduleFrequency(request.frequency),
            cron_expression=request.cron_expression,
            time_of_day=request.time_of_day,
            day_of_week=request.day_of_week,
            day_of_month=request.day_of_month,
            timezone=request.timezone,
            enabled=request.enabled,
        )

        pipeline = await service.update_pipeline_schedule(pipeline_id, schedule)

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        logger.info(f"Updated schedule for pipeline {pipeline_id}")
        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set schedule for {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set pipeline schedule",
        )


@router.post(
    "/pipelines/{pipeline_id}/run",
    response_model=TriggerPipelineResponse,
    summary="Trigger pipeline run",
    description="Manually trigger a pipeline execution.",
)
async def trigger_pipeline_run(
    pipeline_id: UUID,
    background_tasks: BackgroundTasks,
) -> TriggerPipelineResponse:
    """Manually trigger a pipeline execution.

    Args:
        pipeline_id: Pipeline UUID.
        background_tasks: FastAPI background tasks.

    Returns:
        TriggerPipelineResponse with run details.
    """
    try:
        service = get_source_config_service()

        # Check if pipeline exists
        pipeline = await service.get_pipeline(pipeline_id)
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        # Create a new run
        run = await service.create_pipeline_run(pipeline_id)

        if not run:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create pipeline run",
            )

        # In production, this would trigger the actual ETL job
        # For now, we just simulate scheduling it
        logger.info(f"Triggered run {run.id} for pipeline {pipeline_id}")

        return TriggerPipelineResponse(
            run_id=str(run.id),
            pipeline_id=str(pipeline_id),
            status=run.status,
            message="Pipeline run triggered successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger run for {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger pipeline run",
        )


@router.get(
    "/pipelines/{pipeline_id}/runs",
    response_model=PipelineRunListResponse,
    summary="Get pipeline run history",
    description="Get the execution history for a pipeline.",
)
async def get_pipeline_runs(
    pipeline_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
) -> PipelineRunListResponse:
    """Get run history for a pipeline.

    Args:
        pipeline_id: Pipeline UUID.
        limit: Maximum runs to return.

    Returns:
        PipelineRunListResponse with run history.
    """
    try:
        service = get_source_config_service()

        # Check if pipeline exists
        pipeline = await service.get_pipeline(pipeline_id)
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        runs = await service.get_pipeline_runs(pipeline_id, limit)

        return PipelineRunListResponse(
            runs=[_run_to_response(r) for r in runs],
            total=len(runs),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get runs for {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline runs",
        )
