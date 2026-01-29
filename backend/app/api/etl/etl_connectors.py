"""ETL data source connectors and source management API endpoints.

This module provides REST API endpoints for managing data source configurations
used by the ETL system.

Endpoints:
    # Sources
    GET /etl/sources - List configured data sources
    POST /etl/sources - Create new source configuration
    GET /etl/sources/{id} - Get source details
    PUT /etl/sources/{id} - Update source configuration
    DELETE /etl/sources/{id} - Delete source
    POST /etl/sources/{id}/test - Test connection
    GET /etl/sources/{id}/preview - Preview sample data
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.source_config_service import (
    ConnectionParams,
    SourceConfig,
    SourceCredentials,
    SourceType,
    get_source_config_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/etl", tags=["ETL"])


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
# Helper Functions
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
