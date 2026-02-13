"""External Data Integration API endpoints (EXT-DATA).

Provides comprehensive external data integration operations: data source registry,
integration pipeline tracking, data quality validation, mapping configuration,
transfer log management, and integration metrics.

Endpoints:
    GET    /external-data-integration/data-sources                         - List data sources
    GET    /external-data-integration/data-sources/{source_id}             - Get single source
    POST   /external-data-integration/data-sources                         - Create source
    PUT    /external-data-integration/data-sources/{source_id}             - Update source
    DELETE /external-data-integration/data-sources/{source_id}             - Delete source
    GET    /external-data-integration/pipelines                            - List pipelines
    GET    /external-data-integration/pipelines/{pipeline_id}              - Get single pipeline
    POST   /external-data-integration/pipelines                            - Create pipeline
    PUT    /external-data-integration/pipelines/{pipeline_id}              - Update pipeline
    DELETE /external-data-integration/pipelines/{pipeline_id}              - Delete pipeline
    GET    /external-data-integration/validations                          - List validations
    GET    /external-data-integration/validations/{validation_id}          - Get single validation
    POST   /external-data-integration/validations                          - Create validation
    PUT    /external-data-integration/validations/{validation_id}          - Update validation
    DELETE /external-data-integration/validations/{validation_id}          - Delete validation
    GET    /external-data-integration/mappings                             - List mappings
    GET    /external-data-integration/mappings/{mapping_id}                - Get single mapping
    POST   /external-data-integration/mappings                             - Create mapping
    PUT    /external-data-integration/mappings/{mapping_id}                - Update mapping
    DELETE /external-data-integration/mappings/{mapping_id}                - Delete mapping
    GET    /external-data-integration/transfer-logs                        - List transfer logs
    GET    /external-data-integration/transfer-logs/{log_id}               - Get single log
    POST   /external-data-integration/transfer-logs                        - Create log
    PUT    /external-data-integration/transfer-logs/{log_id}               - Update log
    DELETE /external-data-integration/transfer-logs/{log_id}               - Delete log
    GET    /external-data-integration/metrics                              - Integration metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.external_data_integration import (
    ConnectionProtocol,
    DataQualityValidation,
    DataQualityValidationCreate,
    DataQualityValidationListResponse,
    DataQualityValidationUpdate,
    DataSourceRegistry,
    DataSourceRegistryCreate,
    DataSourceRegistryListResponse,
    DataSourceRegistryUpdate,
    ExternalDataIntegrationMetrics,
    IntegrationPipeline,
    IntegrationPipelineCreate,
    IntegrationPipelineListResponse,
    IntegrationPipelineUpdate,
    MappingConfiguration,
    MappingConfigurationCreate,
    MappingConfigurationListResponse,
    MappingConfigurationUpdate,
    PipelineStatus,
    SourceType,
    TransferDirection,
    TransferLog,
    TransferLogCreate,
    TransferLogListResponse,
    TransferLogUpdate,
    ValidationSeverity,
)
from app.services.external_data_integration_service import get_external_data_integration_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/external-data-integration",
    tags=["External Data Integration"],
)


# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------


@router.get(
    "/data-sources",
    response_model=DataSourceRegistryListResponse,
    summary="List data sources",
    description="Retrieve data sources with optional filtering by trial, type, protocol, and active status.",
)
async def list_data_sources(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    source_type: Optional[SourceType] = Query(None, description="Filter by source type"),
    connection_protocol: Optional[ConnectionProtocol] = Query(None, description="Filter by connection protocol"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> DataSourceRegistryListResponse:
    svc = get_external_data_integration_service()
    items = svc.list_data_sources(
        trial_id=trial_id, source_type=source_type,
        connection_protocol=connection_protocol, is_active=is_active,
    )
    return DataSourceRegistryListResponse(items=items, total=len(items))


@router.get(
    "/data-sources/{source_id}",
    response_model=DataSourceRegistry,
    summary="Get a data source",
)
async def get_data_source(source_id: str) -> DataSourceRegistry:
    svc = get_external_data_integration_service()
    record = svc.get_data_source(source_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Data source '{source_id}' not found")
    return record


@router.post(
    "/data-sources",
    response_model=DataSourceRegistry,
    status_code=201,
    summary="Create a data source",
)
async def create_data_source(payload: DataSourceRegistryCreate) -> DataSourceRegistry:
    svc = get_external_data_integration_service()
    return svc.create_data_source(payload)


@router.put(
    "/data-sources/{source_id}",
    response_model=DataSourceRegistry,
    summary="Update a data source",
)
async def update_data_source(
    source_id: str, payload: DataSourceRegistryUpdate
) -> DataSourceRegistry:
    svc = get_external_data_integration_service()
    updated = svc.update_data_source(source_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Data source '{source_id}' not found")
    return updated


@router.delete(
    "/data-sources/{source_id}",
    status_code=204,
    summary="Delete a data source",
)
async def delete_data_source(source_id: str) -> None:
    svc = get_external_data_integration_service()
    deleted = svc.delete_data_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Data source '{source_id}' not found")


# ---------------------------------------------------------------------------
# Integration Pipelines
# ---------------------------------------------------------------------------


@router.get(
    "/pipelines",
    response_model=IntegrationPipelineListResponse,
    summary="List integration pipelines",
    description="Retrieve integration pipelines with optional filtering by trial, status, and source.",
)
async def list_pipelines(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[PipelineStatus] = Query(None, description="Filter by pipeline status"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
) -> IntegrationPipelineListResponse:
    svc = get_external_data_integration_service()
    items = svc.list_pipelines(trial_id=trial_id, status=status, source_id=source_id)
    return IntegrationPipelineListResponse(items=items, total=len(items))


@router.get(
    "/pipelines/{pipeline_id}",
    response_model=IntegrationPipeline,
    summary="Get an integration pipeline",
)
async def get_pipeline(pipeline_id: str) -> IntegrationPipeline:
    svc = get_external_data_integration_service()
    record = svc.get_pipeline(pipeline_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")
    return record


@router.post(
    "/pipelines",
    response_model=IntegrationPipeline,
    status_code=201,
    summary="Create an integration pipeline",
)
async def create_pipeline(payload: IntegrationPipelineCreate) -> IntegrationPipeline:
    svc = get_external_data_integration_service()
    return svc.create_pipeline(payload)


@router.put(
    "/pipelines/{pipeline_id}",
    response_model=IntegrationPipeline,
    summary="Update an integration pipeline",
)
async def update_pipeline(
    pipeline_id: str, payload: IntegrationPipelineUpdate
) -> IntegrationPipeline:
    svc = get_external_data_integration_service()
    updated = svc.update_pipeline(pipeline_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")
    return updated


@router.delete(
    "/pipelines/{pipeline_id}",
    status_code=204,
    summary="Delete an integration pipeline",
)
async def delete_pipeline(pipeline_id: str) -> None:
    svc = get_external_data_integration_service()
    deleted = svc.delete_pipeline(pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")


# ---------------------------------------------------------------------------
# Data Quality Validations
# ---------------------------------------------------------------------------


@router.get(
    "/validations",
    response_model=DataQualityValidationListResponse,
    summary="List data quality validations",
    description="Retrieve data quality validations with optional filtering by trial, severity, pipeline, and resolution status.",
)
async def list_validations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[ValidationSeverity] = Query(None, description="Filter by severity"),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline ID"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
) -> DataQualityValidationListResponse:
    svc = get_external_data_integration_service()
    items = svc.list_validations(
        trial_id=trial_id, severity=severity, pipeline_id=pipeline_id, resolved=resolved,
    )
    return DataQualityValidationListResponse(items=items, total=len(items))


@router.get(
    "/validations/{validation_id}",
    response_model=DataQualityValidation,
    summary="Get a data quality validation",
)
async def get_validation(validation_id: str) -> DataQualityValidation:
    svc = get_external_data_integration_service()
    record = svc.get_validation(validation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return record


@router.post(
    "/validations",
    response_model=DataQualityValidation,
    status_code=201,
    summary="Create a data quality validation",
)
async def create_validation(payload: DataQualityValidationCreate) -> DataQualityValidation:
    svc = get_external_data_integration_service()
    return svc.create_validation(payload)


@router.put(
    "/validations/{validation_id}",
    response_model=DataQualityValidation,
    summary="Update a data quality validation",
)
async def update_validation(
    validation_id: str, payload: DataQualityValidationUpdate
) -> DataQualityValidation:
    svc = get_external_data_integration_service()
    updated = svc.update_validation(validation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return updated


@router.delete(
    "/validations/{validation_id}",
    status_code=204,
    summary="Delete a data quality validation",
)
async def delete_validation(validation_id: str) -> None:
    svc = get_external_data_integration_service()
    deleted = svc.delete_validation(validation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")


# ---------------------------------------------------------------------------
# Mapping Configurations
# ---------------------------------------------------------------------------


@router.get(
    "/mappings",
    response_model=MappingConfigurationListResponse,
    summary="List mapping configurations",
    description="Retrieve mapping configurations with optional filtering by trial, source, and validation status.",
)
async def list_mappings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    validated: Optional[bool] = Query(None, description="Filter by validation status"),
) -> MappingConfigurationListResponse:
    svc = get_external_data_integration_service()
    items = svc.list_mappings(trial_id=trial_id, source_id=source_id, validated=validated)
    return MappingConfigurationListResponse(items=items, total=len(items))


@router.get(
    "/mappings/{mapping_id}",
    response_model=MappingConfiguration,
    summary="Get a mapping configuration",
)
async def get_mapping(mapping_id: str) -> MappingConfiguration:
    svc = get_external_data_integration_service()
    record = svc.get_mapping(mapping_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
    return record


@router.post(
    "/mappings",
    response_model=MappingConfiguration,
    status_code=201,
    summary="Create a mapping configuration",
)
async def create_mapping(payload: MappingConfigurationCreate) -> MappingConfiguration:
    svc = get_external_data_integration_service()
    return svc.create_mapping(payload)


@router.put(
    "/mappings/{mapping_id}",
    response_model=MappingConfiguration,
    summary="Update a mapping configuration",
)
async def update_mapping(
    mapping_id: str, payload: MappingConfigurationUpdate
) -> MappingConfiguration:
    svc = get_external_data_integration_service()
    updated = svc.update_mapping(mapping_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
    return updated


@router.delete(
    "/mappings/{mapping_id}",
    status_code=204,
    summary="Delete a mapping configuration",
)
async def delete_mapping(mapping_id: str) -> None:
    svc = get_external_data_integration_service()
    deleted = svc.delete_mapping(mapping_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")


# ---------------------------------------------------------------------------
# Transfer Logs
# ---------------------------------------------------------------------------


@router.get(
    "/transfer-logs",
    response_model=TransferLogListResponse,
    summary="List transfer logs",
    description="Retrieve transfer logs with optional filtering by trial, pipeline, direction, and status.",
)
async def list_transfer_logs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline ID"),
    direction: Optional[TransferDirection] = Query(None, description="Filter by transfer direction"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> TransferLogListResponse:
    svc = get_external_data_integration_service()
    items = svc.list_transfer_logs(
        trial_id=trial_id, pipeline_id=pipeline_id, direction=direction, status=status,
    )
    return TransferLogListResponse(items=items, total=len(items))


@router.get(
    "/transfer-logs/{log_id}",
    response_model=TransferLog,
    summary="Get a transfer log",
)
async def get_transfer_log(log_id: str) -> TransferLog:
    svc = get_external_data_integration_service()
    record = svc.get_transfer_log(log_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Transfer log '{log_id}' not found")
    return record


@router.post(
    "/transfer-logs",
    response_model=TransferLog,
    status_code=201,
    summary="Create a transfer log",
)
async def create_transfer_log(payload: TransferLogCreate) -> TransferLog:
    svc = get_external_data_integration_service()
    return svc.create_transfer_log(payload)


@router.put(
    "/transfer-logs/{log_id}",
    response_model=TransferLog,
    summary="Update a transfer log",
)
async def update_transfer_log(
    log_id: str, payload: TransferLogUpdate
) -> TransferLog:
    svc = get_external_data_integration_service()
    updated = svc.update_transfer_log(log_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Transfer log '{log_id}' not found")
    return updated


@router.delete(
    "/transfer-logs/{log_id}",
    status_code=204,
    summary="Delete a transfer log",
)
async def delete_transfer_log(log_id: str) -> None:
    svc = get_external_data_integration_service()
    deleted = svc.delete_transfer_log(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Transfer log '{log_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ExternalDataIntegrationMetrics,
    summary="Get external data integration metrics",
    description="Aggregated metrics across all external data integration operations.",
)
async def get_metrics() -> ExternalDataIntegrationMetrics:
    svc = get_external_data_integration_service()
    return svc.get_metrics()
