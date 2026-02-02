"""Policy management API endpoints.

Provides endpoints for uploading, searching, and managing
institutional clinical policies.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.policy_service import get_policy_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["Policies"])


# =============================================================================
# Request/Response Models
# =============================================================================


class PolicyUploadRequest(BaseModel):
    """Request to upload a new policy."""

    name: str = Field(..., min_length=1, max_length=500, description="Policy name")
    content_text: str = Field(..., min_length=10, description="Full policy text")
    source_organization: str | None = Field(None, description="Source organization")
    version: str | None = Field(None, description="Policy version")
    effective_date: datetime | None = Field(None, description="When policy takes effect")
    description: str | None = Field(None, description="Brief description")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Diabetes Management Protocol v2",
                "content_text": "Section 1: Screening\nAll patients over 45...",
                "source_organization": "Internal Medicine Department",
                "version": "2.0",
            }
        }
    }


class PolicyStatusUpdate(BaseModel):
    """Request to update policy status."""

    status: str = Field(..., pattern="^(draft|active|superseded|retired)$")


class PolicySearchRequest(BaseModel):
    """Request to search policy sections."""

    query: str = Field(..., min_length=3, description="Search query")
    patient_conditions: list[str] = Field(default_factory=list, description="Patient conditions for boosting")
    top_k: int = Field(5, ge=1, le=20, description="Max results")


class PolicyResponse(BaseModel):
    """Policy in API responses."""

    id: str
    name: str
    description: str | None
    source_organization: str | None
    version: str | None
    effective_date: str | None
    status: str
    section_count: int
    uploaded_at: str
    uploaded_by: str | None


class PolicySearchResult(BaseModel):
    """Search result for policy sections."""

    section_id: str
    policy_id: str
    policy_name: str
    section_title: str
    content_text: str
    relevance_score: float


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=201,
    summary="Upload a new policy",
)
async def upload_policy(
    request: PolicyUploadRequest,
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    """Upload a new institutional policy."""
    svc = get_policy_service()

    try:
        policy = await svc.upload_policy(
            session=db,
            name=request.name,
            content_text=request.content_text,
            source_org=request.source_organization,
            version=request.version,
            effective_date=request.effective_date,
            description=request.description,
        )
        await db.flush()

        # Reload with sections count
        policy = await svc.get_policy(db, policy.id)
        if not policy:
            raise HTTPException(
                status_code=500,
                detail="Policy uploaded but could not be loaded",
            )
        section_count = len(policy.sections) if policy.sections else 0

        return PolicyResponse(
            id=str(policy.id),
            name=policy.name,
            description=policy.description,
            source_organization=policy.source_organization,
            version=policy.version,
            effective_date=policy.effective_date.isoformat() if policy.effective_date else None,
            status=policy.status,
            section_count=section_count,
            uploaded_at=policy.uploaded_at.isoformat(),
            uploaded_by=policy.uploaded_by,
        )
    except Exception as e:
        # VP-Security: Log full error, return sanitized message
        logger.error(f"Policy upload failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Policy upload failed. Please try again.")


@router.get(
    "",
    summary="List policies",
)
async def list_policies(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all policies with optional status filter."""
    svc = get_policy_service()
    policies = await svc.list_policies(db, status_filter=status)

    return {
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "source_organization": p.source_organization,
                "version": p.version,
                "status": p.status,
                "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
            }
            for p in policies
        ],
        "total": len(policies),
    }


@router.get(
    "/{policy_id}",
    summary="Get policy details",
)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a policy with its sections."""
    svc = get_policy_service()
    policy = await svc.get_policy(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {
        "id": str(policy.id),
        "name": policy.name,
        "description": policy.description,
        "source_organization": policy.source_organization,
        "version": policy.version,
        "effective_date": policy.effective_date.isoformat() if policy.effective_date else None,
        "status": policy.status,
        "content_hash": policy.content_hash,
        "uploaded_at": policy.uploaded_at.isoformat() if policy.uploaded_at else None,
        "sections": [
            {
                "id": str(s.id),
                "section_number": s.section_number,
                "title": s.title,
                "content_text": s.content_text[:500],
                "keywords": s.keywords,
                "applies_to_conditions": s.applies_to_conditions,
                "has_embedding": s.embedding is not None,
            }
            for s in (policy.sections or [])
        ],
    }


@router.put(
    "/{policy_id}/status",
    summary="Update policy status",
)
async def update_policy_status(
    policy_id: str,
    request: PolicyStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update the status of a policy (draft → active → superseded/retired)."""
    svc = get_policy_service()
    policy = await svc.update_policy_status(db, policy_id, request.status)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {
        "id": str(policy.id),
        "name": policy.name,
        "status": policy.status,
    }


@router.post(
    "/search",
    summary="Search policy sections",
)
async def search_policies(
    request: PolicySearchRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Semantic search across active policy sections."""
    svc = get_policy_service()
    results = await svc.search_policy_sections(
        session=db,
        query=request.query,
        patient_conditions=request.patient_conditions,
        top_k=request.top_k,
    )

    return {
        "query": request.query,
        "results": results,
        "total": len(results),
    }


@router.post(
    "/{policy_id}/link-rules",
    summary="Link policy to alert rules",
)
async def link_policy_to_rules(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Link policy sections to matching alert rules via semantic similarity."""
    svc = get_policy_service()
    mappings = await svc.link_policy_to_rules(db, policy_id)

    return {
        "policy_id": policy_id,
        "mappings_created": len(mappings),
        "mappings": [
            {
                "section_id": m.policy_section_id,
                "rule_id": m.alert_rule_id,
                "confidence": m.mapping_confidence,
                "rationale": m.mapping_rationale,
            }
            for m in mappings
        ],
    }


@router.get(
    "/{policy_id}/rules",
    summary="Get policy-rule mappings",
)
async def get_policy_rule_mappings(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get alert rules linked to a policy."""
    svc = get_policy_service()
    mappings = await svc.get_policy_rule_mappings(db, policy_id)
    return {
        "policy_id": policy_id,
        "mappings": mappings,
        "total": len(mappings),
    }
