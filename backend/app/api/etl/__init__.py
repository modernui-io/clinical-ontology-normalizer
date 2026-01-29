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

from fastapi import APIRouter

# Import routers from sub-modules
from app.api.etl.etl_core import router as core_router
from app.api.etl.etl_connectors import router as connectors_router
from app.api.etl.etl_mappings import router as mappings_router

# Re-export all models from sub-modules for backwards compatibility
from app.api.etl.etl_core import (
    ConnectorInfo,
    ConnectorListResponse,
    CreateETLJobRequest,
    CreateETLJobResponse,
    CancelETLJobResponse,
    DeleteETLJobResponse,
    ETLJobConfigResponse,
    ETLJobErrorResponse,
    ETLJobListResponse,
    ETLJobProgressResponse,
    ETLJobResponse,
    ETLJobStatisticsResponse,
    AVAILABLE_CONNECTORS,
)

from app.api.etl.etl_connectors import (
    ConnectionParamsRequest,
    ConnectionParamsResponse,
    ConnectionTestResponse,
    CreateSourceRequest,
    CredentialsRequest,
    CredentialsResponse,
    SampleDataResponse,
    SourceListResponse,
    SourceResponse,
    UpdateSourceRequest,
)

from app.api.etl.etl_mappings import (
    CreatePipelineRequest,
    PipelineListResponse,
    PipelineResponse,
    PipelineRunListResponse,
    PipelineRunResponse,
    PipelineScheduleRequest,
    PipelineScheduleResponse,
    PipelineStageRequest,
    PipelineStageResponse,
    TriggerPipelineResponse,
    UpdatePipelineRequest,
)

# Create combined router that includes all sub-routers
# The sub-routers already have /etl prefix, so we create a parent router without prefix
# and include the sub-routers. The app that includes this router will get all routes
# with their /etl prefix intact.
router = APIRouter(tags=["ETL"])

# Include all sub-routers - they already have /etl prefix
router.include_router(core_router)
router.include_router(connectors_router)
router.include_router(mappings_router)


__all__ = [
    # Main router
    "router",
    # Sub-routers
    "core_router",
    "connectors_router",
    "mappings_router",
    # Core models
    "ConnectorInfo",
    "ConnectorListResponse",
    "CreateETLJobRequest",
    "CreateETLJobResponse",
    "CancelETLJobResponse",
    "DeleteETLJobResponse",
    "ETLJobConfigResponse",
    "ETLJobErrorResponse",
    "ETLJobListResponse",
    "ETLJobProgressResponse",
    "ETLJobResponse",
    "ETLJobStatisticsResponse",
    "AVAILABLE_CONNECTORS",
    # Connector models
    "ConnectionParamsRequest",
    "ConnectionParamsResponse",
    "ConnectionTestResponse",
    "CreateSourceRequest",
    "CredentialsRequest",
    "CredentialsResponse",
    "SampleDataResponse",
    "SourceListResponse",
    "SourceResponse",
    "UpdateSourceRequest",
    # Pipeline models
    "CreatePipelineRequest",
    "PipelineListResponse",
    "PipelineResponse",
    "PipelineRunListResponse",
    "PipelineRunResponse",
    "PipelineScheduleRequest",
    "PipelineScheduleResponse",
    "PipelineStageRequest",
    "PipelineStageResponse",
    "TriggerPipelineResponse",
    "UpdatePipelineRequest",
]
