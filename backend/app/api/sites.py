"""Clinical Trial Sites API endpoints.

Endpoints for managing trial sites and viewing site-level patient
screening aggregations. Designed for the Regeneron demo to show
per-site screening results (e.g., "At Emory, we found 14 EYLEA candidates").

Endpoints:
    GET  /api/v1/sites                           - List sites
    POST /api/v1/sites                           - Create a site
    GET  /api/v1/sites/{site_id}                 - Get site details
    GET  /api/v1/sites/{site_id}/patients        - List patients at a site
    GET  /api/v1/sites/{site_id}/screening-summary - Aggregated screening per trial
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, PermissionChecker
from app.models.site import PatientSiteAssignment, Site
from app.models.knowledge_graph import KGNode
from app.schemas.knowledge_graph import NodeType
from app.schemas.site import (
    SiteCreate,
    SitePatient,
    SiteResponse,
    SiteScreeningSummary,
    SiteTrialMatch,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sites", tags=["Sites"])


# ==============================================================================
# Response wrappers
# ==============================================================================


class SiteListResponse(BaseModel):
    """Paginated site list response."""

    sites: list[SiteResponse]
    total: int
    offset: int
    limit: int


class SitePatientListResponse(BaseModel):
    """Patient list for a site."""

    patients: list[SitePatient]
    total: int
    site_id: str
    site_name: str


# ==============================================================================
# Site CRUD
# ==============================================================================


@router.get(
    "",
    response_model=SiteListResponse,
    summary="List trial sites",
    description="Get a paginated list of clinical trial sites.",
)
async def list_sites(
    request: Request,
    search: str | None = Query(None, description="Search in site name or organization"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.READ_TRIALS])),
) -> SiteListResponse:
    """List all trial sites."""
    query = select(Site).where(Site.deleted_at.is_(None))

    if search:
        pattern = f"%{search}%"
        query = query.where(
            Site.name.ilike(pattern) | Site.organization.ilike(pattern)
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Fetch page
    query = query.order_by(Site.name).offset(offset).limit(limit)
    result = await session.execute(query)
    sites = result.scalars().all()

    return SiteListResponse(
        sites=[SiteResponse.model_validate(s) for s in sites],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post(
    "",
    response_model=SiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a trial site",
    description="Create a new clinical trial site/location.",
)
async def create_site(
    request: Request,
    create: SiteCreate,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.WRITE_TRIALS])),
) -> SiteResponse:
    """Create a new trial site."""
    site = Site(
        name=create.name,
        site_code=create.site_code,
        organization=create.organization,
        address=create.address,
        city=create.city,
        state=create.state,
        country=create.country,
    )
    session.add(site)
    await session.flush()
    logger.info(f"Created site via API: {site.id} ({site.name})")
    return SiteResponse.model_validate(site)


@router.get(
    "/{site_id}",
    response_model=SiteResponse,
    summary="Get site details",
    description="Get full details of a clinical trial site.",
)
async def get_site(
    site_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.READ_TRIALS])),
) -> SiteResponse:
    """Get a site by ID."""
    result = await session.execute(
        select(Site).where(Site.id == site_id, Site.deleted_at.is_(None))
    )
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )
    return SiteResponse.model_validate(site)


# ==============================================================================
# Site Patients
# ==============================================================================


@router.get(
    "/{site_id}/patients",
    response_model=SitePatientListResponse,
    summary="List patients at a site",
    description="Get the list of patients assigned to a specific trial site.",
)
async def list_site_patients(
    site_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.READ_PATIENTS])),
) -> SitePatientListResponse:
    """List patients assigned to a site."""
    # Verify site exists
    site_result = await session.execute(
        select(Site).where(Site.id == site_id, Site.deleted_at.is_(None))
    )
    site = site_result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Get patient assignments
    assign_result = await session.execute(
        select(PatientSiteAssignment).where(
            PatientSiteAssignment.site_id == site_id
        )
    )
    assignments = assign_result.scalars().all()

    # Resolve patient names from KGNode patient nodes
    patients: list[SitePatient] = []
    for assignment in assignments:
        # Look up the patient node for a display name
        node_result = await session.execute(
            select(KGNode).where(
                KGNode.patient_id == assignment.patient_id,
                KGNode.node_type == NodeType.PATIENT,
                KGNode.deleted_at.is_(None),
            ).limit(1)
        )
        patient_node = node_result.scalar_one_or_none()
        patient_name = patient_node.label if patient_node else None

        patients.append(
            SitePatient(
                patient_id=assignment.patient_id,
                patient_name=patient_name,
                site_id=site_id,
            )
        )

    return SitePatientListResponse(
        patients=patients,
        total=len(patients),
        site_id=site_id,
        site_name=site.name,
    )


# ==============================================================================
# Screening Summary
# ==============================================================================


@router.get(
    "/{site_id}/screening-summary",
    response_model=SiteScreeningSummary,
    summary="Get site screening summary",
    description=(
        "Aggregated screening results for a site. Shows how many patients "
        "matched each trial. Designed for the Regeneron site-level view."
    ),
)
async def get_site_screening_summary(
    site_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.READ_TRIALS])),
) -> SiteScreeningSummary:
    """Get screening summary for a site across all trials."""
    # Verify site exists
    site_result = await session.execute(
        select(Site).where(Site.id == site_id, Site.deleted_at.is_(None))
    )
    site = site_result.scalar_one_or_none()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Get patient IDs at this site
    assign_result = await session.execute(
        select(PatientSiteAssignment.patient_id).where(
            PatientSiteAssignment.site_id == site_id
        )
    )
    patient_ids = [row[0] for row in assign_result.all()]

    total_patients = len(patient_ids)

    # Screen patients against all trials
    from app.services.trial_eligibility_service import get_trial_service

    trial_service = get_trial_service()
    trials_list, _ = await trial_service.list_trials(
        limit=100, offset=0, session=session
    )

    trial_matches: list[SiteTrialMatch] = []
    patients_matched_set: set[str] = set()
    patients_screened_set: set[str] = set()

    for trial_summary in trials_list:
        trial_id = str(trial_summary.id)
        matched_patient_ids: list[str] = []

        for pid in patient_ids:
            patients_screened_set.add(pid)
            eligibility = await trial_service.check_patient_eligibility(
                trial_id, pid, session=session
            )
            if eligibility and eligibility.eligible:
                matched_patient_ids.append(pid)
                patients_matched_set.add(pid)

        if matched_patient_ids:
            trial_matches.append(
                SiteTrialMatch(
                    trial_id=trial_id,
                    trial_name=trial_summary.name,
                    matched_patients=len(matched_patient_ids),
                    matched_patient_ids=matched_patient_ids,
                )
            )

    return SiteScreeningSummary(
        site_id=site_id,
        site_name=site.name,
        total_patients=total_patients,
        patients_screened=len(patients_screened_set),
        patients_matched=len(patients_matched_set),
        trial_matches=trial_matches,
    )
