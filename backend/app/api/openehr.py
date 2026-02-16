"""OpenEHR API endpoints for importing and exporting OpenEHR data.

Provides:
- Import from OpenEHR server (by patient EHR ID)
- Import a raw COMPOSITION dict
- Export patient facts as OpenEHR COMPOSITION
- List supported archetypes
- Dry-run import (P0-019)
- Round-trip reconciliation (P0-019)
- Batch rollback (P0-019)

VP-Security-5: SSRF protection on base_url fields.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import log_and_raise_internal_error
from app.core.config import settings
from app.core.database import get_db
from app.models.clinical_fact import ClinicalFact
from app.services.openehr_import import OpenEHRImportService, ARCHETYPE_DOMAIN_MAP
from app.services.openehr_exporter import OpenEHRExporterService
from app.services.openehr_reconciliation import OpenEHRReconciliationService
from app.services.openehr_rollback import OpenEHRRollbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/openehr", tags=["OpenEHR"])


# =============================================================================
# SSRF Prevention
# =============================================================================


def _is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/internal IP address."""
    try:
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
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
            r"^metadata\.",
        ]
        hostname_lower = hostname.lower()
        return any(re.match(p, hostname_lower) for p in internal_patterns)


def validate_openehr_url(url: str) -> str:
    """Validate OpenEHR server URL to prevent SSRF attacks."""
    if not url:
        raise ValueError("OpenEHR URL is required")

    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError(f"Invalid URL format: {url}")

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

    if not parsed.hostname:
        raise ValueError(f"Invalid URL: missing hostname in {url}")

    hostname = parsed.hostname.lower()

    is_localhost = hostname in ("localhost", "127.0.0.1", "::1")
    if is_localhost:
        if getattr(settings, "allow_localhost_fhir", False):
            return url
        else:
            raise ValueError("Localhost OpenEHR servers are not allowed in this environment")

    if _is_private_ip(hostname):
        raise ValueError(f"Cannot connect to internal/private addresses: {hostname}")

    return url


# =============================================================================
# Request/Response Models
# =============================================================================


class OpenEHRImportRequest(BaseModel):
    """Request to import a patient from an OpenEHR server."""

    ehr_id: str = Field(..., description="OpenEHR EHR ID for the patient")
    internal_patient_id: str | None = Field(
        None, description="Optional internal patient ID (defaults to openehr-{ehr_id})"
    )
    base_url: str = Field(
        "http://localhost:8080/ehrbase/rest", description="OpenEHR server base URL"
    )

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_openehr_url(v)


class OpenEHRCompositionImportRequest(BaseModel):
    """Request to import a raw COMPOSITION dict."""

    composition: dict[str, Any] = Field(
        ..., description="OpenEHR COMPOSITION JSON"
    )
    patient_id: str = Field(..., description="Internal patient ID")
    source_metadata: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional source metadata for lineage and interoperability contract tracking."
        ),
    )


class OpenEHRExportRequest(BaseModel):
    """Request to export patient facts as OpenEHR COMPOSITION."""

    composer_name: str = Field("System", description="Composer name")
    territory: str = Field("US", description="Territory code")
    language: str = Field("en", description="Language code")


class OpenEHRImportResponse(BaseModel):
    """Response from OpenEHR import."""

    success: bool
    patient_id: str | None = None
    conditions: int = 0
    medications: int = 0
    measurements: int = 0
    procedures: int = 0
    allergies: int = 0
    nodes: int = 0
    edges: int = 0
    skipped: int = 0
    error: str | None = None


class ArchetypeInfo(BaseModel):
    """Information about a supported archetype."""

    archetype_id: str
    domain: str
    node_type: str
    edge_type: str


class ArchetypeListResponse(BaseModel):
    """Response listing supported archetypes."""

    archetypes: list[ArchetypeInfo]
    count: int


class DryRunResponse(BaseModel):
    """Response from a dry-run import (P0-019)."""

    success: bool
    patient_id: str | None = None
    conditions: int = 0
    medications: int = 0
    measurements: int = 0
    procedures: int = 0
    allergies: int = 0
    nodes: int = 0
    edges: int = 0
    skipped: int = 0
    error: str | None = None


class ReconciliationReportResponse(BaseModel):
    """Response from round-trip reconciliation (P0-019)."""

    patient_id: str
    match: bool
    import_fingerprint: str
    export_reimport_fingerprint: str
    import_row_counts: dict[str, int] = {}
    reimport_row_counts: dict[str, int] = {}
    mismatches: list[str] = []


class RollbackRequest(BaseModel):
    """Request for batch rollback of OpenEHR imports (P0-019)."""

    patient_id: str = Field(..., description="Patient whose imports to roll back")
    batch_start: datetime = Field(..., description="Start of batch time window")
    batch_end: datetime = Field(..., description="End of batch time window")


class RollbackResponse(BaseModel):
    """Response from batch rollback (P0-019)."""

    patient_id: str
    success: bool
    facts_deleted: int = 0
    nodes_deleted: int = 0
    edges_deleted: int = 0
    error: str | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/import", response_model=OpenEHRImportResponse)
async def import_from_openehr_server(
    request: OpenEHRImportRequest,
    session: AsyncSession = Depends(get_db),
) -> OpenEHRImportResponse:
    """Import patient data from an OpenEHR server.

    Connects to an OpenEHR server, fetches compositions for the given EHR ID,
    and creates ClinicalFacts and KG nodes/edges.
    """
    import httpx

    patient_id = request.internal_patient_id or f"openehr-{request.ehr_id}"
    logger.info(f"Starting OpenEHR import for EHR {request.ehr_id} as {patient_id}")

    try:
        async with httpx.AsyncClient(
            base_url=request.base_url, timeout=30
        ) as client:
            # Fetch compositions for this EHR
            response = await client.get(
                f"/ehr/{request.ehr_id}/composition"
            )
            if response.status_code != 200:
                return OpenEHRImportResponse(
                    success=False,
                    error=f"Failed to fetch compositions: HTTP {response.status_code}",
                )

            compositions = response.json()
            comp_list = (
                compositions
                if isinstance(compositions, list)
                else compositions.get("items", [compositions])
            )

            service = OpenEHRImportService()
            total_stats: dict[str, Any] = {
                "success": True,
                "patient_id": patient_id,
                "conditions": 0,
                "medications": 0,
                "measurements": 0,
                "procedures": 0,
                "allergies": 0,
                "nodes": 0,
                "edges": 0,
                "skipped": 0,
            }

            for comp in comp_list:
                if comp.get("_type") != "COMPOSITION":
                    continue
                result = await service.import_composition(
                    session, comp, patient_id
                )
                if result.get("success"):
                    for key in (
                        "conditions", "medications", "measurements",
                        "procedures", "allergies", "nodes", "edges", "skipped",
                    ):
                        total_stats[key] += result.get(key, 0)

            await session.commit()
            return OpenEHRImportResponse(**total_stats)

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/openehr/import",
            user_message="OpenEHR import failed",
        )


@router.post("/composition", response_model=OpenEHRImportResponse)
async def import_composition(
    request: OpenEHRCompositionImportRequest,
    session: AsyncSession = Depends(get_db),
) -> OpenEHRImportResponse:
    """Import a raw OpenEHR COMPOSITION dict.

    Accepts a COMPOSITION JSON and creates ClinicalFacts and KG nodes/edges.
    """
    logger.info(f"Importing OpenEHR composition for patient {request.patient_id}")

    try:
        service = OpenEHRImportService()
        result = await service.import_composition(
            session,
            request.composition,
            request.patient_id,
            source_metadata=request.source_metadata,
        )
        await session.commit()
        return OpenEHRImportResponse(**result)
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/openehr/composition",
            user_message="OpenEHR composition import failed",
        )


@router.post("/export/{patient_id}")
async def export_patient_facts(
    patient_id: str,
    request: OpenEHRExportRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export patient facts as an OpenEHR COMPOSITION.

    Fetches all ClinicalFacts for the patient and builds a COMPOSITION
    with appropriate archetype entries for each domain.
    """
    if request is None:
        request = OpenEHRExportRequest()

    logger.info(f"Exporting OpenEHR composition for patient {patient_id}")

    try:
        result = await session.execute(
            select(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        )
        facts = list(result.scalars().all())

        if not facts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No facts found for patient {patient_id}",
            )

        exporter = OpenEHRExporterService()
        composition = exporter.export_facts(
            facts,
            patient_id,
            composer_name=request.composer_name,
            territory=request.territory,
            language=request.language,
        )

        return {
            "success": True,
            "patient_id": patient_id,
            "fact_count": len(facts),
            "composition": composition,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint=f"/openehr/export/{patient_id}",
            user_message="OpenEHR export failed",
        )


@router.get("/archetypes", response_model=ArchetypeListResponse)
async def list_supported_archetypes() -> ArchetypeListResponse:
    """List all supported OpenEHR archetypes.

    Returns the archetypes that the import/export services can handle,
    along with their mapped OMOP domain, KG node type, and edge type.
    """
    archetypes = []
    for key, (domain, node_type, edge_type) in ARCHETYPE_DOMAIN_MAP.items():
        full_id = f"openEHR-EHR-{key}"
        archetypes.append(
            ArchetypeInfo(
                archetype_id=full_id,
                domain=domain.value,
                node_type=node_type.value,
                edge_type=edge_type.value,
            )
        )

    return ArchetypeListResponse(
        archetypes=archetypes,
        count=len(archetypes),
    )


# =============================================================================
# P0-019: Reconciliation & Rollback Endpoints
# =============================================================================


@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run_import(
    request: OpenEHRCompositionImportRequest,
    session: AsyncSession = Depends(get_db),
) -> DryRunResponse:
    """Dry-run import: runs the full import pipeline without persisting.

    Accepts the same payload as /openehr/composition but uses a savepoint
    to roll back after collecting stats. Returns import statistics and
    validation without any database side effects.
    """
    logger.info(f"Dry-run import for patient {request.patient_id}")

    try:
        service = OpenEHRReconciliationService()
        result = await service.dry_run_import(
            session,
            request.composition,
            request.patient_id,
            source_metadata=request.source_metadata,
        )
        return DryRunResponse(**result.to_dict())
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/openehr/dry-run",
            user_message="OpenEHR dry-run import failed",
        )


@router.post("/reconcile/{patient_id}", response_model=ReconciliationReportResponse)
async def reconcile_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
) -> ReconciliationReportResponse:
    """Round-trip reconciliation for a patient.

    Reads existing facts, exports them to a COMPOSITION, re-imports via
    dry-run, and compares row counts + content hashes. Returns a
    ReconciliationReport with match/mismatch details.
    """
    logger.info(f"Reconciliation check for patient {patient_id}")

    try:
        service = OpenEHRReconciliationService()
        report = await service.reconcile_round_trip(session, patient_id)
        return ReconciliationReportResponse(**report.to_dict())
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint=f"/openehr/reconcile/{patient_id}",
            user_message="OpenEHR reconciliation failed",
        )


@router.post("/rollback", response_model=RollbackResponse)
async def rollback_import_batch(
    request: RollbackRequest,
    session: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """Batch rollback of OpenEHR imports for a patient + time range.

    Identifies affected ClinicalFacts via lineage (source_type=OPENEHR_IMPORT),
    soft-deletes facts, and removes KG nodes/edges. Returns a rollback report
    with counts.
    """
    logger.info(
        f"Rollback for patient {request.patient_id} "
        f"[{request.batch_start} - {request.batch_end}]"
    )

    try:
        service = OpenEHRRollbackService()
        report = await service.rollback_import_batch(
            session,
            request.patient_id,
            request.batch_start,
            request.batch_end,
        )
        if report.success:
            await session.commit()
        return RollbackResponse(**report.to_dict())
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/openehr/rollback",
            user_message="OpenEHR rollback failed",
        )
