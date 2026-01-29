"""FHIR API endpoints for importing, exporting, and interacting with FHIR data.

Includes:
- FHIR import from external servers
- FHIR Bulk Data Export ($export) per HL7 specification

VP-Security-5: Added URL validation to prevent SSRF attacks.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.fhir_import import FHIRImportService
from app.services.bulk_export_service import (
    BulkExportService,
    ExportStatus,
    ExportType,
    ResourceType,
    get_bulk_export_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fhir", tags=["fhir"])

# =============================================================================
# SSRF Prevention - URL Validation
# =============================================================================

# Allowed FHIR servers (from environment variable, comma-separated)
# If not set, all public URLs are allowed (with private IP blocking)
_ALLOWED_FHIR_SERVERS_RAW = os.getenv("ALLOWED_FHIR_SERVERS", "")
ALLOWED_FHIR_SERVERS: set[str] = {
    s.strip().lower().rstrip("/")
    for s in _ALLOWED_FHIR_SERVERS_RAW.split(",")
    if s.strip()
}

# Always allow localhost in development
ALLOW_LOCALHOST = os.getenv("ALLOW_LOCALHOST_FHIR", "true").lower() == "true"


def _is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/internal IP address."""
    try:
        # Try to parse as IP address directly
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        # Not a direct IP, it's a hostname
        # Check for obvious internal hostnames
        internal_patterns = [
            r"^localhost$",
            r"^127\.",
            r"^10\.",
            r"^192\.168\.",
            r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",
            r"^169\.254\.",
            r"\.local$",
            r"\.internal$",
            r"\.localhost$",
            r"^kubernetes",
            r"^k8s",
            r"^metadata\.",
        ]
        hostname_lower = hostname.lower()
        return any(re.match(p, hostname_lower) for p in internal_patterns)


def validate_fhir_url(url: str) -> str:
    """Validate FHIR server URL to prevent SSRF attacks.

    Args:
        url: The FHIR server URL to validate.

    Returns:
        The validated URL (normalized).

    Raises:
        ValueError: If the URL is invalid or not allowed.
    """
    if not url:
        raise ValueError("FHIR URL is required")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError(f"Invalid URL format: {url}")

    # Validate scheme
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

    # Validate hostname exists
    if not parsed.hostname:
        raise ValueError(f"Invalid URL: missing hostname in {url}")

    hostname = parsed.hostname.lower()

    # Check for localhost (allowed in dev mode)
    is_localhost = hostname in ("localhost", "127.0.0.1", "::1")
    if is_localhost:
        if ALLOW_LOCALHOST:
            logger.debug(f"Allowing localhost FHIR server: {url}")
            return url
        else:
            raise ValueError("Localhost FHIR servers are not allowed in this environment")

    # Block private/internal IPs (SSRF protection)
    if _is_private_ip(hostname):
        logger.warning(f"Blocked SSRF attempt to private IP: {url}")
        raise ValueError(
            f"Cannot connect to internal/private addresses: {hostname}"
        )

    # Check allowlist if configured
    if ALLOWED_FHIR_SERVERS:
        normalized_url = f"{parsed.scheme}://{parsed.netloc}".lower().rstrip("/")
        if normalized_url not in ALLOWED_FHIR_SERVERS:
            allowed_list = ", ".join(sorted(ALLOWED_FHIR_SERVERS))
            raise ValueError(
                f"FHIR server not in allowlist. Allowed servers: {allowed_list}"
            )

    logger.debug(f"Validated FHIR URL: {url}")
    return url


class FHIRImportRequest(BaseModel):
    """Request to import a patient from FHIR."""

    fhir_patient_id: str = Field(..., description="FHIR Patient resource ID")
    internal_patient_id: str | None = Field(
        None, description="Optional internal patient ID (defaults to fhir-{id})"
    )
    fhir_base_url: str = Field(
        "http://localhost:8090/fhir", description="FHIR server base URL"
    )

    @field_validator("fhir_base_url")
    @classmethod
    def validate_fhir_url_field(cls, v: str) -> str:
        """Validate FHIR URL to prevent SSRF."""
        return validate_fhir_url(v)


class FHIRImportResponse(BaseModel):
    """Response from FHIR import."""

    success: bool
    patient_id: str | None = None
    patient_name: str | None = None
    conditions: int = 0
    medications: int = 0
    allergies: int = 0
    observations: int = 0
    procedures: int = 0
    nodes: int = 0
    edges: int = 0
    error: str | None = None


@router.post("/import", response_model=FHIRImportResponse)
async def import_fhir_patient(
    request: FHIRImportRequest,
    session: AsyncSession = Depends(get_db),
) -> FHIRImportResponse:
    """Import a patient from FHIR server into the knowledge graph.

    This endpoint fetches a patient and all their clinical data from a FHIR
    server and creates:
    - Clinical facts for each condition, medication, observation, procedure
    - Knowledge graph nodes and edges representing the patient's clinical data

    Args:
        request: Import request with FHIR patient ID and server URL

    Returns:
        Import summary with counts of imported resources
    """
    logger.info(f"Starting FHIR import for patient {request.fhir_patient_id}")

    service = FHIRImportService(fhir_base_url=request.fhir_base_url)
    try:
        result = await service.import_patient(
            session=session,
            fhir_patient_id=request.fhir_patient_id,
            internal_patient_id=request.internal_patient_id,
        )
        return FHIRImportResponse(**result)
    except Exception as e:
        logger.exception(f"FHIR import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await service.close()


@router.get("/patients/{fhir_patient_id}")
async def get_fhir_patient(
    fhir_patient_id: str,
    fhir_base_url: str = Query(
        default="http://localhost:8090/fhir",
        description="FHIR server base URL",
    ),
) -> dict[str, Any]:
    """Fetch a patient directly from the FHIR server.

    This is a convenience endpoint to preview FHIR patient data before import.

    Args:
        fhir_patient_id: FHIR Patient resource ID
        fhir_base_url: FHIR server base URL (validated for SSRF protection)

    Returns:
        FHIR Patient resource
    """
    # Validate URL to prevent SSRF
    try:
        validated_url = validate_fhir_url(fhir_base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    service = FHIRImportService(fhir_base_url=validated_url)
    try:
        patient = await service.fetch_patient(fhir_patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient
    finally:
        await service.close()


@router.get("/patients/{fhir_patient_id}/summary")
async def get_fhir_patient_summary(
    fhir_patient_id: str,
    fhir_base_url: str = Query(
        default="http://localhost:8090/fhir",
        description="FHIR server base URL",
    ),
) -> dict[str, Any]:
    """Get a summary of patient data available in FHIR.

    This previews what would be imported without actually importing.

    Args:
        fhir_patient_id: FHIR Patient resource ID
        fhir_base_url: FHIR server base URL (validated for SSRF protection)

    Returns:
        Summary with counts of each resource type
    """
    # Validate URL to prevent SSRF
    try:
        validated_url = validate_fhir_url(fhir_base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    service = FHIRImportService(fhir_base_url=validated_url)
    try:
        patient = await service.fetch_patient(fhir_patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Fetch counts of each resource type
        conditions = await service.fetch_patient_resources(fhir_patient_id, "Condition")
        medications = await service.fetch_patient_resources(
            fhir_patient_id, "MedicationRequest"
        )
        allergies = await service.fetch_patient_resources(
            fhir_patient_id, "AllergyIntolerance"
        )
        observations = await service.fetch_patient_resources(
            fhir_patient_id, "Observation"
        )
        procedures = await service.fetch_patient_resources(fhir_patient_id, "Procedure")

        return {
            "fhir_patient_id": fhir_patient_id,
            "patient_name": service._extract_patient_name(patient),
            "gender": patient.get("gender"),
            "birth_date": patient.get("birthDate"),
            "conditions": len(conditions),
            "medications": len(medications),
            "allergies": len(allergies),
            "observations": len(observations),
            "procedures": len(procedures),
            "total_resources": (
                len(conditions)
                + len(medications)
                + len(allergies)
                + len(observations)
                + len(procedures)
            ),
        }
    finally:
        await service.close()


# =============================================================================
# Bulk Export Models
# =============================================================================


class BulkExportRequest(BaseModel):
    """Request to start a bulk export."""

    output_format: str | None = Field(
        None,
        alias="_outputFormat",
        description="Output format (only NDJSON supported)",
    )
    resource_type: str | None = Field(
        None,
        alias="_type",
        description="Comma-separated list of resource types to export",
    )
    since: datetime | None = Field(
        None,
        alias="_since",
        description="Only include resources modified since this time",
    )
    type_filter: str | None = Field(
        None,
        alias="_typeFilter",
        description="FHIR search parameters to filter exported resources",
    )
    patient: list[str] | None = Field(
        None,
        description="Patient IDs for patient-level export",
    )

    model_config = {"populate_by_name": True}


class BulkExportFile(BaseModel):
    """Information about an exported file."""

    type: str = Field(..., description="Resource type")
    url: str = Field(..., description="Download URL")
    count: int = Field(..., description="Number of resources")


class BulkExportStatusResponse(BaseModel):
    """Response for bulk export status (completed)."""

    transactionTime: str = Field(..., description="Transaction time")
    request: str = Field(..., description="Original request URL")
    requiresAccessToken: bool = Field(False, description="Whether access token is required")
    output: list[BulkExportFile] = Field(default_factory=list)
    error: list[dict[str, Any]] = Field(default_factory=list)


class BulkExportJobResponse(BaseModel):
    """Response for bulk export job details."""

    job_id: str
    status: str
    export_type: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    expires_at: str | None
    resource_types: list[str]
    since: str | None
    output_files: list[dict[str, Any]]
    errors_count: int
    progress: dict[str, Any]


class BulkExportListResponse(BaseModel):
    """Response for listing bulk export jobs."""

    jobs: list[BulkExportJobResponse]
    total: int


class BulkExportStatsResponse(BaseModel):
    """Response for bulk export service statistics."""

    total_jobs: int
    running_jobs: int
    jobs_by_status: dict[str, int]
    total_files_exported: int
    export_base_dir: str
    file_retention_hours: int


# =============================================================================
# Bulk Export Endpoints (FHIR Bulk Data Access)
# =============================================================================


@router.post(
    "/$export",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Bulk Export",
    description="Initiate a system-level bulk export of FHIR resources.",
    responses={
        202: {
            "description": "Export accepted",
            "headers": {
                "Content-Location": {
                    "description": "URL to poll for export status",
                    "schema": {"type": "string"},
                }
            },
        }
    },
)
async def start_bulk_export(
    request: Request,
    _outputFormat: Annotated[
        str | None,
        Query(description="Output format (only application/fhir+ndjson supported)"),
    ] = None,
    _type: Annotated[
        str | None,
        Query(description="Comma-separated list of resource types to export"),
    ] = None,
    _since: Annotated[
        datetime | None,
        Query(description="Only include resources modified since this time"),
    ] = None,
    _typeFilter: Annotated[
        str | None,
        Query(description="FHIR search parameters to filter resources"),
    ] = None,
) -> Response:
    """Start a FHIR Bulk Data Export.

    This endpoint initiates an asynchronous export of FHIR resources
    in NDJSON format per the FHIR Bulk Data Access specification.

    The export runs asynchronously. Poll the Content-Location URL
    to check status and retrieve results when complete.

    Args:
        _outputFormat: Output format (only NDJSON supported).
        _type: Resource types to export.
        _since: Only resources modified since this time.
        _typeFilter: Additional FHIR search filters.

    Returns:
        202 Accepted with Content-Location header for polling.
    """
    service = get_bulk_export_service()

    # Parse resource types
    resource_types = None
    if _type:
        resource_types = [t.strip() for t in _type.split(",")]

    # Get base URL for status polling
    base_url = str(request.base_url).rstrip("/")
    request_url = f"{base_url}/fhir/$export"

    try:
        job = await service.start_export(
            export_type=ExportType.SYSTEM,
            resource_types=resource_types,
            since=_since,
            type_filter=_typeFilter,
            output_format=_outputFormat or "application/fhir+ndjson",
            request_url=request_url,
        )

        # Return 202 with Content-Location header
        status_url = f"{base_url}/fhir/$export/{job.job_id}"
        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            headers={
                "Content-Location": status_url,
            },
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )


@router.post(
    "/Patient/$export",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Patient-Level Export",
    description="Initiate a patient-level bulk export of FHIR resources.",
)
async def start_patient_export(
    request: Request,
    patient: Annotated[
        list[str] | None,
        Query(description="Patient IDs to export (omit for all patients)"),
    ] = None,
    _outputFormat: Annotated[str | None, Query()] = None,
    _type: Annotated[str | None, Query()] = None,
    _since: Annotated[datetime | None, Query()] = None,
) -> Response:
    """Start a patient-level bulk export.

    Exports resources for specific patients or all patients.

    Args:
        patient: List of patient IDs to export.
        _outputFormat: Output format.
        _type: Resource types to export.
        _since: Only resources modified since this time.

    Returns:
        202 Accepted with Content-Location header.
    """
    service = get_bulk_export_service()

    resource_types = None
    if _type:
        resource_types = [t.strip() for t in _type.split(",")]

    base_url = str(request.base_url).rstrip("/")

    try:
        job = await service.start_export(
            export_type=ExportType.PATIENT,
            resource_types=resource_types,
            since=_since,
            patient_ids=patient,
            request_url=f"{base_url}/fhir/Patient/$export",
        )

        status_url = f"{base_url}/fhir/$export/{job.job_id}"
        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Content-Location": status_url},
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )


@router.get(
    "/$export/{job_id}",
    summary="Get Export Status",
    description="Check the status of a bulk export job.",
    responses={
        200: {"description": "Export complete, files available"},
        202: {"description": "Export in progress"},
        404: {"description": "Job not found"},
    },
)
async def get_export_status(
    job_id: str,
    request: Request,
) -> Response:
    """Get the status of a bulk export job.

    Per FHIR Bulk Data spec:
    - Returns 202 if still in progress
    - Returns 200 with output manifest when complete
    - Returns error details if failed

    Args:
        job_id: The export job ID.

    Returns:
        Status response per FHIR Bulk Data specification.
    """
    service = get_bulk_export_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job not found: {job_id}",
        )

    base_url = str(request.base_url).rstrip("/")

    if job.status == ExportStatus.COMPLETED:
        # Return 200 with output manifest
        status_response = job.to_status_response(base_url)
        return Response(
            status_code=status.HTTP_200_OK,
            content=__import__("json").dumps(status_response),
            media_type="application/json",
        )

    elif job.status == ExportStatus.IN_PROGRESS:
        # Return 202 with progress
        progress = job.progress.percent_complete
        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            headers={
                "X-Progress": f"{progress:.1f}%",
                "Retry-After": "5",
            },
            content=__import__("json").dumps({
                "status": "in-progress",
                "progress": progress,
            }),
            media_type="application/json",
        )

    elif job.status == ExportStatus.FAILED:
        # Return error details
        return Response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=__import__("json").dumps({
                "status": "failed",
                "errors": [
                    {
                        "type": e.error_type,
                        "message": e.error_message,
                    }
                    for e in job.errors
                ],
            }),
            media_type="application/json",
        )

    else:
        # Pending, cancelled, or expired
        return Response(
            status_code=status.HTTP_200_OK,
            content=__import__("json").dumps({
                "status": job.status.value,
            }),
            media_type="application/json",
        )


@router.get(
    "/$export/{job_id}/download/{filename}",
    summary="Download Export File",
    description="Download an NDJSON file from a completed export.",
)
async def download_export_file(
    job_id: str,
    filename: str,
) -> FileResponse:
    """Download an exported NDJSON file.

    Args:
        job_id: The export job ID.
        filename: The file name (e.g., "Patient.ndjson").

    Returns:
        The NDJSON file content.
    """
    service = get_bulk_export_service()
    result = service.get_export_file(job_id, filename)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}",
        )

    file_path, content_type = result

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=filename,
    )


@router.delete(
    "/$export/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel or Delete Export",
    description="Cancel an in-progress export or delete a completed one.",
)
async def delete_export(job_id: str) -> Response:
    """Cancel or delete a bulk export job.

    If the job is in progress, it will be cancelled.
    If completed or failed, the job and its files will be deleted.

    Args:
        job_id: The export job ID.

    Returns:
        204 No Content on success.
    """
    service = get_bulk_export_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job not found: {job_id}",
        )

    # Try to cancel if running
    if job.status in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]:
        service.cancel_job(job_id)
    else:
        # Delete completed/failed job
        if not service.delete_job(job_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete job in current state",
            )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Admin Endpoints for Bulk Export
# =============================================================================


@router.get(
    "/$export/admin/jobs",
    response_model=BulkExportListResponse,
    summary="List Export Jobs",
    description="List all bulk export jobs.",
    tags=["fhir", "Bulk Export Admin"],
)
async def list_export_jobs(
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status"),
    ] = None,
    limit: Annotated[int, Query(description="Maximum jobs to return")] = 100,
) -> BulkExportListResponse:
    """List bulk export jobs.

    Args:
        status_filter: Filter by export status.
        limit: Maximum number of jobs to return.

    Returns:
        List of export jobs.
    """
    service = get_bulk_export_service()

    export_status = None
    if status_filter:
        try:
            export_status = ExportStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    jobs = service.get_jobs(status=export_status, limit=limit)

    return BulkExportListResponse(
        jobs=[
            BulkExportJobResponse(
                job_id=j.job_id,
                status=j.status.value,
                export_type=j.export_type.value,
                created_at=j.created_at.isoformat(),
                started_at=j.started_at.isoformat() if j.started_at else None,
                completed_at=j.completed_at.isoformat() if j.completed_at else None,
                expires_at=j.expires_at.isoformat() if j.expires_at else None,
                resource_types=j.resource_types,
                since=j.since.isoformat() if j.since else None,
                output_files=[
                    {
                        "resource_type": f.resource_type,
                        "url": f.url,
                        "count": f.count,
                        "size_bytes": f.size_bytes,
                    }
                    for f in j.output_files
                ],
                errors_count=len(j.errors),
                progress={
                    "total_resources": j.progress.total_resources,
                    "exported_resources": j.progress.exported_resources,
                    "percent_complete": j.progress.percent_complete,
                },
            )
            for j in jobs
        ],
        total=len(jobs),
    )


@router.get(
    "/$export/admin/stats",
    response_model=BulkExportStatsResponse,
    summary="Get Export Statistics",
    description="Get bulk export service statistics.",
    tags=["fhir", "Bulk Export Admin"],
)
async def get_export_stats() -> BulkExportStatsResponse:
    """Get bulk export service statistics.

    Returns:
        Service statistics.
    """
    service = get_bulk_export_service()
    stats = service.get_stats()

    return BulkExportStatsResponse(
        total_jobs=stats["total_jobs"],
        running_jobs=stats["running_jobs"],
        jobs_by_status=stats["jobs_by_status"],
        total_files_exported=stats["total_files_exported"],
        export_base_dir=stats["export_base_dir"],
        file_retention_hours=stats["file_retention_hours"],
    )


@router.post(
    "/$export/admin/cleanup",
    summary="Cleanup Expired Exports",
    description="Clean up expired export files.",
    tags=["fhir", "Bulk Export Admin"],
)
async def cleanup_exports() -> dict[str, Any]:
    """Clean up expired export files.

    Returns:
        Number of exports cleaned up.
    """
    service = get_bulk_export_service()
    cleaned = await service.cleanup_expired_exports()

    return {
        "cleaned_exports": cleaned,
        "status": "success",
    }
