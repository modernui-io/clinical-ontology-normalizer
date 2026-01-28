"""
Data Sources API

REST endpoints for managing external data source connections.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.data_source import DataSourceType, HealthStatus
from app.services.data_source_service import (
    ConnectionTestResult,
    DataSourceCreate,
    DataSourceResponse,
    DataSourceService,
    DataSourceUpdate,
)

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


def get_service(db: AsyncSession = Depends(get_db)) -> DataSourceService:
    """Get data source service instance."""
    return DataSourceService(db)


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    data: DataSourceCreate,
    service: DataSourceService = Depends(get_service),
) -> DataSourceResponse:
    """
    Create a new data source.

    Configure a connection to an external data source such as:
    - FHIR Server
    - Health Information Exchange (HIE)
    - Data Aggregator (Particle Health, etc.)
    - HL7 Feed
    - File Upload
    """
    source = await service.create(data)
    return service.to_response(source)


@router.get("", response_model=list[DataSourceResponse])
async def list_data_sources(
    source_type: Optional[DataSourceType] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    service: DataSourceService = Depends(get_service),
) -> list[DataSourceResponse]:
    """
    List all configured data sources.

    Optionally filter by:
    - source_type: fhir_server, hie, aggregator, file_upload, hl7_feed
    - is_active: true/false
    """
    sources = await service.list(
        source_type=source_type,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [service.to_response(s) for s in sources]


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source_id: UUID,
    service: DataSourceService = Depends(get_service),
) -> DataSourceResponse:
    """Get details of a specific data source."""
    source = await service.get(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source not found: {source_id}",
        )
    return service.to_response(source)


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_data_source(
    source_id: UUID,
    data: DataSourceUpdate,
    service: DataSourceService = Depends(get_service),
) -> DataSourceResponse:
    """
    Update a data source configuration.

    Only provided fields will be updated.
    Credentials (client_secret, api_key, password) are re-encrypted if provided.
    """
    source = await service.update(source_id, data)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source not found: {source_id}",
        )
    return service.to_response(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    source_id: UUID,
    service: DataSourceService = Depends(get_service),
) -> None:
    """
    Delete a data source.

    This will also delete all associated pipelines.
    """
    deleted = await service.delete(source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source not found: {source_id}",
        )


@router.post("/{source_id}/test", response_model=ConnectionTestResult)
async def test_connection(
    source_id: UUID,
    service: DataSourceService = Depends(get_service),
) -> ConnectionTestResult:
    """
    Test connection to a data source.

    Attempts to connect and returns:
    - success: whether connection succeeded
    - message: status message
    - latency_ms: connection latency
    - server_info: additional info about the server (if available)

    Also updates the health_status of the data source.
    """
    result = await service.test_connection(source_id)
    return result


@router.get("/{source_id}/health", response_model=ConnectionTestResult)
async def check_health(
    source_id: UUID,
    service: DataSourceService = Depends(get_service),
) -> ConnectionTestResult:
    """
    Check health of a data source.

    Same as test_connection but semantically indicates a health check
    rather than initial connection testing.
    """
    result = await service.test_connection(source_id)
    return result


# Summary endpoint for dashboard
@router.get("/summary/stats")
async def get_data_source_stats(
    service: DataSourceService = Depends(get_service),
) -> dict:
    """
    Get summary statistics about data sources.

    Returns counts by type and health status.
    """
    all_sources = await service.list(limit=1000)

    by_type = {}
    by_health = {}
    total_records = 0

    for source in all_sources:
        # Count by type
        type_key = source.source_type.value
        by_type[type_key] = by_type.get(type_key, 0) + 1

        # Count by health
        health_key = source.health_status.value
        by_health[health_key] = by_health.get(health_key, 0) + 1

        # Sum records
        total_records += source.total_records_imported

    return {
        "total_sources": len(all_sources),
        "active_sources": len([s for s in all_sources if s.is_active]),
        "by_type": by_type,
        "by_health": by_health,
        "total_records_imported": total_records,
    }
