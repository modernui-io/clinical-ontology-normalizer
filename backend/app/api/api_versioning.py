"""API Versioning and Deprecation Policy endpoints (CTO-8).

Provides endpoints for managing API version lifecycle, viewing deprecated
endpoints, generating migration guides, tracking client usage, and
checking for breaking changes.

Endpoints:
    GET    /api/v1/api-management/versions                              - List all API versions
    GET    /api/v1/api-management/versions/{version}                    - Version detail
    GET    /api/v1/api-management/versions/{version}/endpoints          - Endpoints in version
    GET    /api/v1/api-management/deprecated                            - All deprecated endpoints
    GET    /api/v1/api-management/migration-guide/{from_version}/{to_version} - Migration guide
    GET    /api/v1/api-management/client-usage                          - Client version usage stats
    POST   /api/v1/api-management/check-breaking-changes                - Check for breaking changes
    GET    /api/v1/api-management/deprecation-policy                    - Current deprecation policy
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.api_versioning import (
    APIVersionListResponse,
    APIVersionRecord,
    BreakingChangeReport,
    BreakingChangeRequest,
    ClientUsageResponse,
    DeprecatedEndpointResponse,
    DeprecationPolicy,
    EndpointVersionListResponse,
    MigrationGuide,
)
from app.services.api_versioning_service import get_api_versioning_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-management",
    tags=["API Versioning & Deprecation"],
)


# ============================================================================
# Version Lifecycle Endpoints
# ============================================================================


@router.get(
    "/versions",
    response_model=APIVersionListResponse,
    summary="List all API versions",
    description="Returns all registered API versions with their lifecycle status.",
)
async def list_versions() -> APIVersionListResponse:
    """List all API versions with lifecycle status."""
    service = get_api_versioning_service()
    return service.list_versions()


@router.get(
    "/versions/{version}",
    response_model=APIVersionRecord,
    summary="Get API version detail",
    description="Returns detailed information about a specific API version.",
)
async def get_version(version: str) -> APIVersionRecord:
    """Get details for a specific API version."""
    service = get_api_versioning_service()
    record = service.get_version(version)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{version}' not found",
        )
    return record


@router.get(
    "/versions/{version}/endpoints",
    response_model=EndpointVersionListResponse,
    summary="List endpoints in a version",
    description="Returns all endpoints registered in a specific API version.",
)
async def get_version_endpoints(version: str) -> EndpointVersionListResponse:
    """Get all endpoints for a specific API version."""
    service = get_api_versioning_service()
    try:
        return service.get_version_endpoints(version)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# Deprecated Endpoints
# ============================================================================


@router.get(
    "/deprecated",
    response_model=DeprecatedEndpointResponse,
    summary="List all deprecated endpoints",
    description="Returns all deprecated endpoints across all API versions.",
)
async def get_deprecated_endpoints() -> DeprecatedEndpointResponse:
    """Get all deprecated endpoints across all versions."""
    service = get_api_versioning_service()
    return service.get_all_deprecated_endpoints()


# ============================================================================
# Migration Guide
# ============================================================================


@router.get(
    "/migration-guide/{from_version}/{to_version}",
    response_model=MigrationGuide,
    summary="Generate migration guide",
    description=(
        "Generates a migration guide with step-by-step instructions "
        "for transitioning between two API versions."
    ),
)
async def get_migration_guide(
    from_version: str,
    to_version: str,
) -> MigrationGuide:
    """Generate a migration guide between two API versions."""
    service = get_api_versioning_service()
    try:
        return service.generate_migration_guide(from_version, to_version)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# Client Usage
# ============================================================================


@router.get(
    "/client-usage",
    response_model=ClientUsageResponse,
    summary="Get client version usage stats",
    description="Returns statistics on which API versions clients are using.",
)
async def get_client_usage() -> ClientUsageResponse:
    """Get client API version usage statistics."""
    service = get_api_versioning_service()
    return service.get_client_usage()


# ============================================================================
# Breaking Change Detection
# ============================================================================


@router.post(
    "/check-breaking-changes",
    response_model=BreakingChangeReport,
    summary="Check for breaking changes",
    description=(
        "Compares two API versions and detects breaking changes including "
        "removed endpoints, schema changes, and auth requirement changes."
    ),
)
async def check_breaking_changes(
    request: BreakingChangeRequest,
) -> BreakingChangeReport:
    """Check for breaking changes between two API versions."""
    service = get_api_versioning_service()
    try:
        return service.detect_breaking_changes(
            from_version=request.from_version,
            to_version=request.to_version,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# Deprecation Policy
# ============================================================================


@router.get(
    "/deprecation-policy",
    response_model=DeprecationPolicy,
    summary="Get deprecation policy",
    description=(
        "Returns the current API deprecation policy including minimum notice "
        "periods, sunset rules, and versioning strategy."
    ),
)
async def get_deprecation_policy() -> DeprecationPolicy:
    """Get the current API deprecation policy."""
    service = get_api_versioning_service()
    return service.get_deprecation_policy()
