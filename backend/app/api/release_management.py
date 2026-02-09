"""Release Management & Deployment Tracking API endpoints (VPE-8).

Provides release lifecycle management, deployment tracking with
blue-green/canary/rolling strategies, release gates, rollback
capabilities, DORA metrics, and changelog generation.

Endpoints:
    GET    /release-management/releases                                  - List releases
    GET    /release-management/releases/{release_id}                     - Get release detail
    POST   /release-management/releases                                  - Create release
    PUT    /release-management/releases/{release_id}                     - Update release
    DELETE /release-management/releases/{release_id}                     - Delete release
    GET    /release-management/releases/{release_id}/deployments         - List deployments for release
    POST   /release-management/releases/{release_id}/deploy              - Deploy a release
    GET    /release-management/releases/{release_id}/gates               - List gates for release
    PUT    /release-management/releases/{release_id}/gates/{gate_name}   - Update a gate
    GET    /release-management/releases/{release_id}/readiness           - Check release readiness
    GET    /release-management/releases/{release_id}/changelog           - Generate changelog
    GET    /release-management/deployments                               - List all deployments
    GET    /release-management/deployments/{deployment_id}               - Get deployment detail
    POST   /release-management/deployments/{deployment_id}/rollback      - Rollback deployment
    GET    /release-management/metrics/dora                              - DORA metrics
    GET    /release-management/history                                   - Release history
    GET    /release-management/versions/validate                         - Validate semver
    GET    /release-management/versions/next                             - Suggest next version
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.release_management import (
    Deployment,
    DeploymentListResponse,
    DeploymentStatus,
    DeploymentType,
    DeployRequest,
    Environment,
    GateName,
    GateStatus,
    GateUpdateRequest,
    Release,
    ReleaseCreate,
    ReleaseGate,
    ReleaseGateListResponse,
    ReleaseHistoryResponse,
    ReleaseListResponse,
    ReleaseMetrics,
    ReleaseReadinessResponse,
    ReleaseStatus,
    ReleaseType,
    ReleaseUpdate,
    RollbackRequest,
)
from app.services.release_management_service import (
    SEMVER_PATTERN,
    get_release_management_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/release-management",
    tags=["Release Management"],
)


# ---------------------------------------------------------------------------
# Helper to convert records to response schemas
# ---------------------------------------------------------------------------


def _release_to_schema(record) -> Release:
    """Convert a ReleaseRecord to a Release response schema."""
    return Release(
        id=record.id,
        version=record.version,
        title=record.title,
        description=record.description,
        status=record.status,
        release_type=record.release_type,
        features=record.features,
        bug_fixes=record.bug_fixes,
        breaking_changes=record.breaking_changes,
        release_manager=record.release_manager,
        planned_date=record.planned_date,
        actual_date=record.actual_date,
        changelog=record.changelog,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _deployment_to_schema(record) -> Deployment:
    """Convert a DeploymentRecord to a Deployment response schema."""
    return Deployment(
        id=record.id,
        release_id=record.release_id,
        environment=record.environment,
        deployment_type=record.deployment_type,
        status=record.status,
        deployed_by=record.deployed_by,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
        health_check_passed=record.health_check_passed,
        rollback_available=record.rollback_available,
        rollback_to_version=record.rollback_to_version,
        notes=record.notes,
    )


def _gate_to_schema(record) -> ReleaseGate:
    """Convert a GateRecord to a ReleaseGate response schema."""
    return ReleaseGate(
        id=record.id,
        release_id=record.release_id,
        gate_name=record.gate_name,
        status=record.status,
        reviewer=record.reviewer,
        reviewed_at=record.reviewed_at,
        comments=record.comments,
    )


# ---------------------------------------------------------------------------
# Release CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/releases",
    response_model=ReleaseListResponse,
    summary="List releases",
    description="Retrieve releases with optional filtering by status and type.",
)
async def list_releases(
    status: Optional[ReleaseStatus] = Query(None, description="Filter by release status"),
    release_type: Optional[ReleaseType] = Query(None, description="Filter by release type"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ReleaseListResponse:
    """List releases with optional filters and pagination."""
    svc = get_release_management_service()
    records, total = svc.list_releases(
        status=status,
        release_type=release_type,
        limit=limit,
        offset=offset,
    )
    return ReleaseListResponse(
        releases=[_release_to_schema(r) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/releases/{release_id}",
    response_model=Release,
    summary="Get release by ID",
    description="Retrieve a single release by its unique identifier.",
)
async def get_release(release_id: str) -> Release:
    """Get a release by ID."""
    svc = get_release_management_service()
    try:
        record = svc.get_release(release_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")
    return _release_to_schema(record)


@router.post(
    "/releases",
    response_model=Release,
    status_code=201,
    summary="Create a new release",
    description="Create a new release with SemVer version and metadata.",
)
async def create_release(body: ReleaseCreate) -> Release:
    """Create a new release."""
    svc = get_release_management_service()
    try:
        record = svc.create_release(
            version=body.version,
            title=body.title,
            release_type=body.release_type,
            release_manager=body.release_manager,
            description=body.description,
            features=body.features,
            bug_fixes=body.bug_fixes,
            breaking_changes=body.breaking_changes,
            planned_date=body.planned_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _release_to_schema(record)


@router.put(
    "/releases/{release_id}",
    response_model=Release,
    summary="Update a release",
    description="Update release fields including status transitions.",
)
async def update_release(release_id: str, body: ReleaseUpdate) -> Release:
    """Update a release."""
    svc = get_release_management_service()
    try:
        record = svc.update_release(
            release_id=release_id,
            title=body.title,
            description=body.description,
            status=body.status,
            features=body.features,
            bug_fixes=body.bug_fixes,
            breaking_changes=body.breaking_changes,
            planned_date=body.planned_date,
            changelog=body.changelog,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _release_to_schema(record)


@router.delete(
    "/releases/{release_id}",
    status_code=204,
    summary="Delete a release",
    description="Delete a release and all associated gates and deployments.",
)
async def delete_release(release_id: str) -> None:
    """Delete a release."""
    svc = get_release_management_service()
    try:
        svc.delete_release(release_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------


@router.get(
    "/releases/{release_id}/deployments",
    response_model=DeploymentListResponse,
    summary="List deployments for a release",
    description="Retrieve all deployments associated with a release.",
)
async def list_release_deployments(
    release_id: str,
    environment: Optional[Environment] = Query(None, description="Filter by environment"),
    status: Optional[DeploymentStatus] = Query(None, description="Filter by deployment status"),
) -> DeploymentListResponse:
    """List deployments for a specific release."""
    svc = get_release_management_service()
    # Validate release exists
    try:
        svc.get_release(release_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    records = svc.list_deployments(
        release_id=release_id,
        environment=environment,
        status=status,
    )
    deployments = [_deployment_to_schema(d) for d in records]
    return DeploymentListResponse(deployments=deployments, total=len(deployments))


@router.post(
    "/releases/{release_id}/deploy",
    response_model=Deployment,
    status_code=201,
    summary="Deploy a release",
    description="Create a deployment for a release to a target environment.",
)
async def deploy_release(release_id: str, body: DeployRequest) -> Deployment:
    """Deploy a release to an environment."""
    svc = get_release_management_service()
    try:
        record = svc.deploy(
            release_id=release_id,
            environment=body.environment,
            deployment_type=body.deployment_type,
            deployed_by=body.deployed_by,
            notes=body.notes,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _deployment_to_schema(record)


@router.get(
    "/deployments",
    response_model=DeploymentListResponse,
    summary="List all deployments",
    description="Retrieve all deployments with optional filtering.",
)
async def list_deployments(
    release_id: Optional[str] = Query(None, description="Filter by release ID"),
    environment: Optional[Environment] = Query(None, description="Filter by environment"),
    status: Optional[DeploymentStatus] = Query(None, description="Filter by status"),
) -> DeploymentListResponse:
    """List all deployments with optional filters."""
    svc = get_release_management_service()
    records = svc.list_deployments(
        release_id=release_id,
        environment=environment,
        status=status,
    )
    deployments = [_deployment_to_schema(d) for d in records]
    return DeploymentListResponse(deployments=deployments, total=len(deployments))


@router.get(
    "/deployments/{deployment_id}",
    response_model=Deployment,
    summary="Get deployment by ID",
    description="Retrieve a single deployment by its unique identifier.",
)
async def get_deployment(deployment_id: str) -> Deployment:
    """Get a deployment by ID."""
    svc = get_release_management_service()
    try:
        record = svc.get_deployment(deployment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    return _deployment_to_schema(record)


@router.post(
    "/deployments/{deployment_id}/rollback",
    response_model=Deployment,
    status_code=201,
    summary="Rollback a deployment",
    description="Create a rollback deployment for an existing deployment.",
)
async def rollback_deployment(deployment_id: str, body: RollbackRequest) -> Deployment:
    """Rollback a deployment."""
    svc = get_release_management_service()
    try:
        record = svc.rollback(
            deployment_id=deployment_id,
            rolled_back_by=body.rolled_back_by,
            reason=body.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _deployment_to_schema(record)


# ---------------------------------------------------------------------------
# Release Gates
# ---------------------------------------------------------------------------


@router.get(
    "/releases/{release_id}/gates",
    response_model=ReleaseGateListResponse,
    summary="List release gates",
    description="Retrieve all quality gates for a release.",
)
async def list_release_gates(release_id: str) -> ReleaseGateListResponse:
    """List gates for a release."""
    svc = get_release_management_service()
    try:
        records = svc.get_gates_for_release(release_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")
    gates = [_gate_to_schema(g) for g in records]
    return ReleaseGateListResponse(gates=gates, total=len(gates))


@router.put(
    "/releases/{release_id}/gates/{gate_name}",
    response_model=ReleaseGate,
    summary="Update a release gate",
    description="Update the status of a specific release gate.",
)
async def update_release_gate(
    release_id: str,
    gate_name: GateName,
    body: GateUpdateRequest,
) -> ReleaseGate:
    """Update a release gate status."""
    svc = get_release_management_service()
    try:
        record = svc.update_gate(
            release_id=release_id,
            gate_name=gate_name,
            status=body.status,
            reviewer=body.reviewer,
            comments=body.comments,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _gate_to_schema(record)


@router.get(
    "/releases/{release_id}/readiness",
    response_model=ReleaseReadinessResponse,
    summary="Check release readiness",
    description="Check if all quality gates have passed for a release.",
)
async def check_release_readiness(release_id: str) -> ReleaseReadinessResponse:
    """Check release readiness (all gates passed?)."""
    svc = get_release_management_service()
    try:
        return svc.check_release_readiness(release_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------


@router.get(
    "/releases/{release_id}/changelog",
    summary="Generate changelog for a release",
    description="Generate a formatted changelog from release features, bug fixes, and breaking changes.",
)
async def generate_changelog(release_id: str) -> dict:
    """Generate a changelog for a release."""
    svc = get_release_management_service()
    try:
        record = svc.get_release(release_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    # Build changelog from release data
    lines = [f"## {record.version} - {record.title}"]

    if record.description:
        lines.append(f"\n{record.description}")

    if record.features:
        lines.append("\n### Features")
        for feat in record.features:
            lines.append(f"- {feat}")

    if record.bug_fixes:
        lines.append("\n### Bug Fixes")
        for fix in record.bug_fixes:
            lines.append(f"- {fix}")

    if record.breaking_changes:
        lines.append("\n### Breaking Changes")
        for bc in record.breaking_changes:
            lines.append(f"- {bc}")

    changelog_text = "\n".join(lines)

    return {
        "release_id": record.id,
        "version": record.version,
        "changelog": changelog_text,
    }


# ---------------------------------------------------------------------------
# DORA Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/dora",
    response_model=ReleaseMetrics,
    summary="Get DORA metrics",
    description="Compute DORA metrics (deployment frequency, lead time, change failure rate, MTTR).",
)
async def get_dora_metrics() -> ReleaseMetrics:
    """Get DORA metrics from release and deployment data."""
    svc = get_release_management_service()
    return svc.get_dora_metrics()


# ---------------------------------------------------------------------------
# Release History
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=ReleaseHistoryResponse,
    summary="Get release history",
    description="Get recent releases with deployment summaries and gate status.",
)
async def get_release_history(
    limit: int = Query(10, ge=1, le=100, description="Number of recent releases"),
) -> ReleaseHistoryResponse:
    """Get release history with deployment details."""
    svc = get_release_management_service()
    return svc.get_release_history(limit=limit)


# ---------------------------------------------------------------------------
# SemVer Utilities
# ---------------------------------------------------------------------------


@router.get(
    "/versions/validate",
    summary="Validate a semantic version string",
    description="Check if a string is a valid semantic version (SemVer 2.0).",
)
async def validate_version(
    version: str = Query(..., description="Version string to validate"),
) -> dict:
    """Validate a semantic version string."""
    match = SEMVER_PATTERN.match(version)
    if match:
        return {
            "version": version,
            "valid": True,
            "major": int(match.group("major")),
            "minor": int(match.group("minor")),
            "patch": int(match.group("patch")),
            "prerelease": match.group("prerelease"),
            "build": match.group("build"),
        }
    return {"version": version, "valid": False}


@router.get(
    "/versions/next",
    summary="Suggest next version",
    description="Suggest the next semantic version based on the current version and bump type.",
)
async def suggest_next_version(
    current: str = Query(..., description="Current version string"),
    bump: ReleaseType = Query(..., description="Version bump type (MAJOR, MINOR, PATCH, HOTFIX)"),
) -> dict:
    """Suggest the next semantic version."""
    match = SEMVER_PATTERN.match(current)
    if not match:
        raise HTTPException(status_code=400, detail=f"Invalid semantic version: {current}")

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    if bump == ReleaseType.MAJOR:
        next_version = f"{major + 1}.0.0"
    elif bump == ReleaseType.MINOR:
        next_version = f"{major}.{minor + 1}.0"
    elif bump in (ReleaseType.PATCH, ReleaseType.HOTFIX):
        next_version = f"{major}.{minor}.{patch + 1}"
    else:
        next_version = f"{major}.{minor}.{patch + 1}"

    return {
        "current": current,
        "bump": bump.value,
        "next": next_version,
    }
