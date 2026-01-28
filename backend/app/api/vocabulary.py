"""Vocabulary management API endpoints.

Provides vocabulary listing, version history, update scanning,
impact analysis, and version update application.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.impact_analysis_service import (
    analyze_concept_retirement,
    analyze_version_update,
    generate_impact_report,
)
from app.services.ontology_scanner import check_all_vocabularies, scan_for_updates
from app.services.vocabulary_version_service import get_vocabulary_version_service

router = APIRouter(prefix="/vocabularies", tags=["Vocabularies"])


# ---- Pydantic schemas ----


class ConceptUpdateItem(BaseModel):
    concept_id: int
    concept_name: str
    domain_id: str = "Unknown"
    concept_class_id: str = "Clinical Finding"
    standard_concept: str | None = None
    status: str = "active"


class VersionUpdateRequest(BaseModel):
    version: str
    concepts: list[ConceptUpdateItem]


class RetirementRequest(BaseModel):
    replacement_concept_id: int | None = None


class MergeRequest(BaseModel):
    old_concept_ids: list[int]
    new_concept_id: int


# ---- Endpoints ----


@router.get("")
async def list_vocabularies(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all vocabularies with version information."""
    result = await check_all_vocabularies(db)
    return result


@router.get("/{vocab_id}/versions")
async def get_vocabulary_versions(
    vocab_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get version history for a vocabulary."""
    service = get_vocabulary_version_service()
    current = await service.get_current_version(db, vocab_id)
    return {
        "vocabulary_id": vocab_id,
        "current_version": current.get("version"),
        "version_date": current.get("version_date"),
    }


@router.post("/{vocab_id}/scan")
async def trigger_vocabulary_scan(
    vocab_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger an update scan for a vocabulary."""
    result = await scan_for_updates(db, vocab_id)
    return result


@router.get("/{vocab_id}/impact")
async def get_vocabulary_impact(
    vocab_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get impact analysis report for a vocabulary."""
    report = await generate_impact_report(db, vocab_id)
    return report


@router.post("/{vocab_id}/apply-update")
async def apply_vocabulary_update(
    vocab_id: str,
    request: VersionUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Apply a vocabulary version update."""
    service = get_vocabulary_version_service()

    # First, analyze impact
    concepts_data = [c.model_dump() for c in request.concepts]
    impact = await analyze_version_update(db, vocab_id, concepts_data)

    # Apply the update
    result = await service.import_version_update(
        db, vocab_id, request.version, concepts_data,
    )

    await db.commit()

    return {
        "update_result": result,
        "impact_analysis": impact,
    }


@router.get("/concepts/{concept_id}/history")
async def get_concept_history(
    concept_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get version history for a specific concept."""
    service = get_vocabulary_version_service()
    history = await service.get_version_history(db, concept_id)
    if not history:
        raise HTTPException(status_code=404, detail="Concept not found")
    return {"concept_id": concept_id, "history": history}


@router.post("/concepts/{concept_id}/retire")
async def retire_concept(
    concept_id: int,
    request: RetirementRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retire a concept with optional replacement."""
    # First analyze impact
    impact = await analyze_concept_retirement(db, concept_id)
    if "error" in impact:
        raise HTTPException(status_code=404, detail=impact["error"])

    # Apply retirement
    service = get_vocabulary_version_service()
    result = await service.apply_retirement(
        db, concept_id, request.replacement_concept_id,
    )

    await db.commit()

    return {
        "retirement_result": result,
        "impact_analysis": impact,
    }


@router.post("/concepts/merge")
async def merge_concepts(
    request: MergeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Merge multiple concepts into one."""
    service = get_vocabulary_version_service()
    result = await service.apply_merge(
        db, request.old_concept_ids, request.new_concept_id,
    )

    await db.commit()

    return result


@router.get("/concepts/{concept_id}/impact")
async def get_concept_retirement_impact(
    concept_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get impact analysis for retiring a specific concept."""
    result = await analyze_concept_retirement(db, concept_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
