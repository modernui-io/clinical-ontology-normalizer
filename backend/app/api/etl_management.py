"""ETL Management API endpoints.

This module provides comprehensive REST API endpoints for managing ETL configurations,
mapping templates, and job logs for the Clinical Ontology Normalizer.

Endpoints:
    # Sources
    GET /api/v1/etl-management/sources - List configured sources
    POST /api/v1/etl-management/sources - Create new source config
    PUT /api/v1/etl-management/sources/{id} - Update source config
    DELETE /api/v1/etl-management/sources/{id} - Delete source
    POST /api/v1/etl-management/sources/{id}/test - Test connection

    # Mappings
    GET /api/v1/etl-management/mappings - List mapping templates
    POST /api/v1/etl-management/mappings - Save mapping template
    GET /api/v1/etl-management/mappings/{id} - Get mapping template
    PUT /api/v1/etl-management/mappings/{id} - Update mapping template
    DELETE /api/v1/etl-management/mappings/{id} - Delete mapping template

    # Jobs
    POST /api/v1/etl-management/jobs - Start new ETL job
    GET /api/v1/etl-management/jobs/{id}/logs - Get job logs
    GET /api/v1/etl-management/jobs/{id}/statistics - Get job statistics

    # Device and Specimen specific
    GET /api/v1/etl-management/device-mappings - Get device code mappings
    GET /api/v1/etl-management/specimen-mappings - Get specimen type mappings
"""

import logging
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

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
    SourceConfig,
    SourceCredentials,
    SourceType,
    get_source_config_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/etl-management", tags=["ETL Management"])

# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# Request/Response Models
# =============================================================================


class MappingField(BaseModel):
    """A field mapping within a template."""

    source_field: str = Field(..., description="Source field name")
    target_field: str = Field(..., description="Target OMOP field name")
    transform: str | None = Field(default=None, description="Transformation expression")
    default_value: Any = Field(default=None, description="Default value if source is null")
    vocabulary_id: str | None = Field(default=None, description="Vocabulary for concept mapping")


class MappingTemplate(BaseModel):
    """A mapping template for ETL transformations."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    source_type: str = Field(..., description="Source data type (fhir, csv, hl7v2, ccda)")
    target_table: str = Field(..., description="Target OMOP table (e.g., device_exposure, specimen)")
    fields: list[MappingField] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateMappingRequest(BaseModel):
    """Request body for creating a mapping template."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    source_type: str = Field(..., pattern="^(fhir|csv|hl7v2|ccda|database)$")
    target_table: str = Field(..., description="Target OMOP table")
    fields: list[MappingField] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateMappingRequest(BaseModel):
    """Request body for updating a mapping template."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    fields: list[MappingField] | None = None
    metadata: dict[str, Any] | None = None


class MappingListResponse(BaseModel):
    """Response containing list of mapping templates."""

    mappings: list[MappingTemplate]
    total: int


class JobLogEntry(BaseModel):
    """A single log entry from an ETL job."""

    timestamp: str
    level: str  # INFO, WARNING, ERROR
    phase: str
    message: str
    record_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class JobLogsResponse(BaseModel):
    """Response containing job logs."""

    job_id: str
    logs: list[JobLogEntry]
    total: int
    has_more: bool


class JobStatisticsResponse(BaseModel):
    """Detailed job statistics response."""

    job_id: str
    state: str
    total_records: int
    patients_processed: int
    visits_processed: int
    conditions_processed: int
    drugs_processed: int
    procedures_processed: int
    measurements_processed: int
    observations_processed: int
    devices_processed: int
    specimens_processed: int
    records_created: int
    records_updated: int
    records_skipped: int
    unmapped_codes: int
    errors_count: int
    warnings_count: int
    retries_performed: int
    duration_seconds: float | None
    throughput_records_per_second: float | None


class StartJobRequest(BaseModel):
    """Request body for starting a new ETL job."""

    source_id: str = Field(..., description="UUID of the data source to use")
    connector_type: str = Field(
        default="fhir",
        description="Connector type (fhir, csv, hl7v2, ccda, database)",
        pattern="^(fhir|csv|hl7v2|ccda|database)$",
    )
    mapping_template_id: str | None = Field(
        default=None, description="Optional mapping template to use"
    )
    batch_size: int = Field(default=100, ge=1, le=10000)
    max_records: int | None = Field(default=None, ge=1)
    patient_ids: list[str] | None = None
    include_devices: bool = Field(default=True, description="Extract device data")
    include_specimens: bool = Field(default=True, description="Extract specimen data")
    options: dict[str, Any] = Field(default_factory=dict)


class StartJobResponse(BaseModel):
    """Response after starting a job."""

    job_id: str
    state: str
    message: str
    estimated_records: int | None = None


class DeviceMappingInfo(BaseModel):
    """Information about device code mapping."""

    source_code: str
    source_system: str
    omop_concept_id: int
    omop_concept_name: str
    domain: str = "Device"
    mapped_count: int = 0


class DeviceMappingsResponse(BaseModel):
    """Response containing device mappings."""

    mappings: list[DeviceMappingInfo]
    unmapped_codes: list[str]
    total_mapped: int
    total_unmapped: int


class SpecimenMappingInfo(BaseModel):
    """Information about specimen type mapping."""

    source_code: str
    source_system: str
    omop_concept_id: int
    omop_concept_name: str
    domain: str = "Specimen"
    specimen_type: str | None = None
    mapped_count: int = 0


class SpecimenMappingsResponse(BaseModel):
    """Response containing specimen mappings."""

    mappings: list[SpecimenMappingInfo]
    unmapped_codes: list[str]
    total_mapped: int
    total_unmapped: int


# =============================================================================
# In-Memory Storage (would be replaced with database in production)
# =============================================================================

_mapping_templates: dict[str, MappingTemplate] = {}
_job_logs: dict[str, list[JobLogEntry]] = {}


# Pre-populate with some default mapping templates
DEFAULT_DEVICE_MAPPING = MappingTemplate(
    id="default-device-fhir",
    name="FHIR Device to OMOP Device_Exposure",
    description="Default mapping from FHIR DeviceRequest/DeviceUseStatement to OMOP Device_Exposure",
    source_type="fhir",
    target_table="device_exposure",
    fields=[
        MappingField(
            source_field="id",
            target_field="device_source_value",
            transform="truncate(50)",
        ),
        MappingField(
            source_field="codeCodeableConcept.coding[0].code",
            target_field="device_concept_id",
            vocabulary_id="SNOMED",
        ),
        MappingField(
            source_field="authoredOn",
            target_field="device_exposure_start_date",
            transform="parse_date",
        ),
        MappingField(
            source_field="udiCarrier[0].deviceIdentifier",
            target_field="unique_device_id",
            transform="truncate(255)",
        ),
    ],
    metadata={"version": "1.0", "fhir_version": "R4"},
)

DEFAULT_SPECIMEN_MAPPING = MappingTemplate(
    id="default-specimen-fhir",
    name="FHIR Specimen to OMOP Specimen",
    description="Default mapping from FHIR Specimen to OMOP Specimen table",
    source_type="fhir",
    target_table="specimen",
    fields=[
        MappingField(
            source_field="id",
            target_field="specimen_source_id",
            transform="truncate(50)",
        ),
        MappingField(
            source_field="type.coding[0].code",
            target_field="specimen_concept_id",
            vocabulary_id="SNOMED",
        ),
        MappingField(
            source_field="collection.collectedDateTime",
            target_field="specimen_date",
            transform="parse_date",
        ),
        MappingField(
            source_field="collection.quantity.value",
            target_field="quantity",
        ),
        MappingField(
            source_field="collection.quantity.unit",
            target_field="unit_source_value",
        ),
        MappingField(
            source_field="collection.bodySite.coding[0].code",
            target_field="anatomic_site_concept_id",
            vocabulary_id="SNOMED",
        ),
    ],
    metadata={"version": "1.0", "fhir_version": "R4"},
)

_mapping_templates[DEFAULT_DEVICE_MAPPING.id] = DEFAULT_DEVICE_MAPPING
_mapping_templates[DEFAULT_SPECIMEN_MAPPING.id] = DEFAULT_SPECIMEN_MAPPING


# =============================================================================
# Mapping Template Endpoints
# =============================================================================


@router.get(
    "/mappings",
    response_model=MappingListResponse,
    summary="List mapping templates",
    description="Get all available ETL mapping templates.",
)
async def list_mappings(
    source_type: str | None = Query(default=None, description="Filter by source type"),
    target_table: str | None = Query(default=None, description="Filter by target table"),
) -> MappingListResponse:
    """List all mapping templates with optional filtering.

    Args:
        source_type: Optional filter by source type (fhir, csv, etc.).
        target_table: Optional filter by target OMOP table.

    Returns:
        MappingListResponse with list of templates.
    """
    mappings = list(_mapping_templates.values())

    if source_type:
        mappings = [m for m in mappings if m.source_type == source_type]

    if target_table:
        mappings = [m for m in mappings if m.target_table == target_table]

    return MappingListResponse(mappings=mappings, total=len(mappings))


@router.post(
    "/mappings",
    response_model=MappingTemplate,
    status_code=status.HTTP_201_CREATED,
    summary="Create mapping template",
    description="Create a new ETL mapping template.",
)
async def create_mapping(request: CreateMappingRequest) -> MappingTemplate:
    """Create a new mapping template.

    Args:
        request: Mapping template configuration.

    Returns:
        Created MappingTemplate.
    """
    mapping = MappingTemplate(
        name=request.name,
        description=request.description,
        source_type=request.source_type,
        target_table=request.target_table,
        fields=request.fields,
        metadata=request.metadata,
    )

    _mapping_templates[mapping.id] = mapping

    logger.info(f"Created mapping template {mapping.id}: {mapping.name}")
    return mapping


@router.get(
    "/mappings/{mapping_id}",
    response_model=MappingTemplate,
    summary="Get mapping template",
    description="Get a specific mapping template by ID.",
)
async def get_mapping(mapping_id: str) -> MappingTemplate:
    """Get a specific mapping template.

    Args:
        mapping_id: Template ID.

    Returns:
        MappingTemplate.

    Raises:
        HTTPException: If template not found.
    """
    mapping = _mapping_templates.get(mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping template {mapping_id} not found",
        )
    return mapping


@router.put(
    "/mappings/{mapping_id}",
    response_model=MappingTemplate,
    summary="Update mapping template",
    description="Update an existing mapping template.",
)
async def update_mapping(mapping_id: str, request: UpdateMappingRequest) -> MappingTemplate:
    """Update a mapping template.

    Args:
        mapping_id: Template ID.
        request: Updated configuration.

    Returns:
        Updated MappingTemplate.

    Raises:
        HTTPException: If template not found.
    """
    mapping = _mapping_templates.get(mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping template {mapping_id} not found",
        )

    if request.name is not None:
        mapping.name = request.name
    if request.description is not None:
        mapping.description = request.description
    if request.fields is not None:
        mapping.fields = request.fields
    if request.metadata is not None:
        mapping.metadata = request.metadata

    mapping.updated_at = datetime.now().isoformat()

    logger.info(f"Updated mapping template {mapping_id}")
    return mapping


@router.delete(
    "/mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete mapping template",
    description="Delete a mapping template.",
)
async def delete_mapping(mapping_id: str) -> None:
    """Delete a mapping template.

    Args:
        mapping_id: Template ID.

    Raises:
        HTTPException: If template not found.
    """
    if mapping_id not in _mapping_templates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping template {mapping_id} not found",
        )

    del _mapping_templates[mapping_id]
    logger.info(f"Deleted mapping template {mapping_id}")


# =============================================================================
# Job Management Endpoints
# =============================================================================


@router.post(
    "/jobs",
    response_model=StartJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start new ETL job",
    description="Start a new ETL job with the specified configuration.",
)
async def start_job(
    request: StartJobRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> StartJobResponse:
    """Start a new ETL job.

    Args:
        request: Job configuration.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        StartJobResponse with job ID.

    Raises:
        HTTPException: If configuration is invalid.
    """
    try:
        # Get source config
        source_service = get_source_config_service()
        source_id = UUID(request.source_id)
        source = await source_service.get_source(source_id)

        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {request.source_id} not found",
            )

        orchestrator = get_etl_orchestrator(db)

        # Build connection string from source
        conn_string = ""
        if source.connection_params.host:
            conn_string = f"https://{source.connection_params.host}"
            if source.connection_params.port:
                conn_string += f":{source.connection_params.port}"
            if source.connection_params.path:
                conn_string += source.connection_params.path
        elif source.connection_params.path:
            conn_string = source.connection_params.path

        # Build ETL options to include device and specimen extraction
        etl_options = request.options.copy()
        etl_options["include_devices"] = request.include_devices
        etl_options["include_specimens"] = request.include_specimens

        config = ETLJobConfig(
            connector_type=request.connector_type,
            connection_string=conn_string,
            source_name=source.name,
            batch_size=request.batch_size,
            max_records=request.max_records,
            patient_ids=request.patient_ids,
            etl_options=etl_options,
        )

        job = await orchestrator.create_job(config)

        # Initialize job logs
        _job_logs[str(job.job_id)] = []

        # Schedule job to run in background
        background_tasks.add_task(orchestrator.run_job, job.job_id)

        logger.info(f"Started ETL job {job.job_id} for source {source.name}")

        return StartJobResponse(
            job_id=str(job.job_id),
            state=job.state.value,
            message="ETL job started successfully",
            estimated_records=None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to start ETL job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start ETL job",
        )


@router.get(
    "/jobs/{job_id}/logs",
    response_model=JobLogsResponse,
    summary="Get job logs",
    description="Get logs for a specific ETL job.",
)
async def get_job_logs(
    job_id: UUID,
    db: DbSession,
    level: str | None = Query(default=None, description="Filter by log level"),
    phase: str | None = Query(default=None, description="Filter by ETL phase"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> JobLogsResponse:
    """Get logs for an ETL job.

    Args:
        job_id: Job UUID.
        db: Database session.
        level: Optional log level filter (INFO, WARNING, ERROR).
        phase: Optional phase filter.
        offset: Pagination offset.
        limit: Maximum logs to return.

    Returns:
        JobLogsResponse with log entries.

    Raises:
        HTTPException: If job not found.
    """
    orchestrator = get_etl_orchestrator(db)
    job = await orchestrator.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Get or generate logs from job errors and warnings
    job_id_str = str(job_id)
    if job_id_str not in _job_logs:
        _job_logs[job_id_str] = []

    # Add any new errors to logs
    existing_error_ids = {log.message for log in _job_logs[job_id_str]}
    for error in job.errors:
        error_msg = f"{error.error_type}: {error.error_message}"
        if error_msg not in existing_error_ids:
            _job_logs[job_id_str].append(
                JobLogEntry(
                    timestamp=error.timestamp.isoformat(),
                    level="ERROR",
                    phase=error.phase.value,
                    message=error_msg,
                    record_id=error.record_id,
                    details={"is_retryable": error.is_retryable, "retry_count": error.retry_count},
                )
            )

    logs = _job_logs[job_id_str]

    # Apply filters
    if level:
        logs = [log for log in logs if log.level == level.upper()]
    if phase:
        logs = [log for log in logs if log.phase == phase]

    total = len(logs)
    paginated_logs = logs[offset : offset + limit]
    has_more = offset + limit < total

    return JobLogsResponse(
        job_id=job_id_str,
        logs=paginated_logs,
        total=total,
        has_more=has_more,
    )


@router.get(
    "/jobs/{job_id}/statistics",
    response_model=JobStatisticsResponse,
    summary="Get job statistics",
    description="Get detailed statistics for an ETL job.",
)
async def get_job_statistics(
    job_id: UUID,
    db: DbSession,
) -> JobStatisticsResponse:
    """Get detailed statistics for an ETL job.

    Args:
        job_id: Job UUID.
        db: Database session.

    Returns:
        JobStatisticsResponse with detailed statistics.

    Raises:
        HTTPException: If job not found.
    """
    orchestrator = get_etl_orchestrator(db)
    job = await orchestrator.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Calculate throughput
    throughput = None
    if job.duration_seconds and job.duration_seconds > 0:
        throughput = job.statistics.total_records / job.duration_seconds

    return JobStatisticsResponse(
        job_id=str(job_id),
        state=job.state.value,
        total_records=job.statistics.total_records,
        patients_processed=job.statistics.patients_processed,
        visits_processed=job.statistics.visits_processed,
        conditions_processed=job.statistics.conditions_processed,
        drugs_processed=job.statistics.drugs_processed,
        procedures_processed=job.statistics.procedures_processed,
        measurements_processed=job.statistics.measurements_processed,
        observations_processed=job.statistics.observations_processed,
        devices_processed=job.statistics.devices_processed,
        specimens_processed=job.statistics.specimens_processed,
        records_created=job.statistics.records_created,
        records_updated=job.statistics.records_updated,
        records_skipped=job.statistics.records_skipped,
        unmapped_codes=job.statistics.unmapped_codes,
        errors_count=len(job.errors),
        warnings_count=len(job.warnings),
        retries_performed=job.statistics.retries_performed,
        duration_seconds=job.duration_seconds,
        throughput_records_per_second=throughput,
    )


# =============================================================================
# Device and Specimen Mapping Endpoints
# =============================================================================


@router.get(
    "/device-mappings",
    response_model=DeviceMappingsResponse,
    summary="Get device code mappings",
    description="Get current device code to OMOP concept mappings.",
)
async def get_device_mappings(
    db: DbSession,
    vocabulary_id: str | None = Query(default=None, description="Filter by vocabulary"),
) -> DeviceMappingsResponse:
    """Get device code mappings to OMOP concepts.

    Returns common device code mappings from SNOMED, UDI, and HCPCS.

    Args:
        db: Database session.
        vocabulary_id: Optional vocabulary filter.

    Returns:
        DeviceMappingsResponse with mapping information.
    """
    # Common device SNOMED codes with their OMOP concept IDs
    # In production, this would query the vocabulary tables
    common_device_mappings = [
        DeviceMappingInfo(
            source_code="704125003",
            source_system="SNOMED",
            omop_concept_id=45766999,
            omop_concept_name="Insulin pump",
        ),
        DeviceMappingInfo(
            source_code="714749009",
            source_system="SNOMED",
            omop_concept_id=4207830,
            omop_concept_name="Continuous positive airway pressure device",
        ),
        DeviceMappingInfo(
            source_code="41852007",
            source_system="SNOMED",
            omop_concept_id=4119893,
            omop_concept_name="Cardiac pacemaker",
        ),
        DeviceMappingInfo(
            source_code="72506001",
            source_system="SNOMED",
            omop_concept_id=4035541,
            omop_concept_name="Prosthetic hip",
        ),
        DeviceMappingInfo(
            source_code="360058002",
            source_system="SNOMED",
            omop_concept_id=4035541,
            omop_concept_name="Total knee replacement prosthesis",
        ),
        DeviceMappingInfo(
            source_code="706689003",
            source_system="SNOMED",
            omop_concept_id=4254417,
            omop_concept_name="Coronary artery stent",
        ),
        DeviceMappingInfo(
            source_code="257283004",
            source_system="SNOMED",
            omop_concept_id=4141295,
            omop_concept_name="Central venous catheter",
        ),
        DeviceMappingInfo(
            source_code="468001",
            source_system="SNOMED",
            omop_concept_id=4212097,
            omop_concept_name="Intrauterine device",
        ),
    ]

    if vocabulary_id:
        common_device_mappings = [
            m for m in common_device_mappings if m.source_system == vocabulary_id
        ]

    return DeviceMappingsResponse(
        mappings=common_device_mappings,
        unmapped_codes=[],
        total_mapped=len(common_device_mappings),
        total_unmapped=0,
    )


@router.get(
    "/specimen-mappings",
    response_model=SpecimenMappingsResponse,
    summary="Get specimen type mappings",
    description="Get current specimen type to OMOP concept mappings.",
)
async def get_specimen_mappings(
    db: DbSession,
    specimen_type: str | None = Query(default=None, description="Filter by specimen type"),
) -> SpecimenMappingsResponse:
    """Get specimen type mappings to OMOP concepts.

    Returns common specimen type mappings from SNOMED.

    Args:
        db: Database session.
        specimen_type: Optional specimen type filter.

    Returns:
        SpecimenMappingsResponse with mapping information.
    """
    # Common specimen SNOMED codes with their OMOP concept IDs
    # In production, this would query the vocabulary tables
    common_specimen_mappings = [
        SpecimenMappingInfo(
            source_code="122555007",
            source_system="SNOMED",
            omop_concept_id=4045667,
            omop_concept_name="Venous blood specimen",
            specimen_type="Blood",
        ),
        SpecimenMappingInfo(
            source_code="122556008",
            source_system="SNOMED",
            omop_concept_id=4046280,
            omop_concept_name="Arterial blood specimen",
            specimen_type="Blood",
        ),
        SpecimenMappingInfo(
            source_code="119364003",
            source_system="SNOMED",
            omop_concept_id=4120923,
            omop_concept_name="Serum specimen",
            specimen_type="Blood",
        ),
        SpecimenMappingInfo(
            source_code="119361006",
            source_system="SNOMED",
            omop_concept_id=4045668,
            omop_concept_name="Plasma specimen",
            specimen_type="Blood",
        ),
        SpecimenMappingInfo(
            source_code="122575003",
            source_system="SNOMED",
            omop_concept_id=4045666,
            omop_concept_name="Urine specimen",
            specimen_type="Urine",
        ),
        SpecimenMappingInfo(
            source_code="122580007",
            source_system="SNOMED",
            omop_concept_id=4046282,
            omop_concept_name="Cerebrospinal fluid specimen",
            specimen_type="CSF",
        ),
        SpecimenMappingInfo(
            source_code="119376003",
            source_system="SNOMED",
            omop_concept_id=4119294,
            omop_concept_name="Tissue specimen",
            specimen_type="Tissue",
        ),
        SpecimenMappingInfo(
            source_code="258500001",
            source_system="SNOMED",
            omop_concept_id=4126083,
            omop_concept_name="Nasopharyngeal swab",
            specimen_type="Swab",
        ),
        SpecimenMappingInfo(
            source_code="119339001",
            source_system="SNOMED",
            omop_concept_id=4047433,
            omop_concept_name="Stool specimen",
            specimen_type="Stool",
        ),
        SpecimenMappingInfo(
            source_code="119342007",
            source_system="SNOMED",
            omop_concept_id=4046863,
            omop_concept_name="Saliva specimen",
            specimen_type="Saliva",
        ),
    ]

    if specimen_type:
        common_specimen_mappings = [
            m for m in common_specimen_mappings if m.specimen_type == specimen_type
        ]

    return SpecimenMappingsResponse(
        mappings=common_specimen_mappings,
        unmapped_codes=[],
        total_mapped=len(common_specimen_mappings),
        total_unmapped=0,
    )
