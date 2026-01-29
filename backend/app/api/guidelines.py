"""Clinical guidelines API endpoints.

Provides endpoints for listing and searching clinical guidelines
loaded from the fixture file via the RAG service.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guidelines", tags=["Guidelines"])


@router.get(
    "",
    summary="List all clinical guidelines",
)
async def list_guidelines(
    source: str | None = Query(None, description="Filter by guideline source name"),
    condition: str | None = Query(None, description="Filter by condition"),
    evidence_grade: str | None = Query(None, description="Filter by evidence grade (A/B/C)"),
) -> dict[str, Any]:
    """List all loaded clinical guideline sections with optional filters."""
    try:
        from app.services.guideline_rag_service import get_guideline_rag_service

        rag_svc = get_guideline_rag_service()
        if not rag_svc.is_loaded:
            rag_svc.load()

        sections = rag_svc._sections  # Access internal sections list

        # Apply filters
        filtered = sections
        if source:
            source_lower = source.lower()
            filtered = [s for s in filtered if source_lower in s.guideline.lower()]
        if condition:
            cond_lower = condition.lower()
            filtered = [
                s for s in filtered
                if any(cond_lower in c.lower() for c in s.applies_to_conditions)
            ]
        if evidence_grade:
            grade_upper = evidence_grade.upper()
            filtered = [s for s in filtered if s.evidence_grade == grade_upper]

        # Extract unique guideline sources
        all_sources = sorted({s.guideline for s in sections})
        all_conditions = sorted({
            c for s in sections for c in s.applies_to_conditions
        })
        all_grades = sorted({s.evidence_grade for s in sections if s.evidence_grade})

        return {
            "guidelines": [
                {
                    "section_id": s.section_id,
                    "guideline": s.guideline,
                    "section_title": s.section_title,
                    "recommendation_text": s.recommendation_text,
                    "evidence_grade": s.evidence_grade,
                    "recommendation_level": s.recommendation_level,
                    "applies_to_conditions": s.applies_to_conditions,
                    "applies_to_medications": s.applies_to_medications,
                    "applies_to_measurements": s.applies_to_measurements,
                    "keywords": s.keywords,
                }
                for s in filtered
            ],
            "total": len(filtered),
            "filters": {
                "sources": all_sources,
                "conditions": all_conditions,
                "evidence_grades": all_grades,
            },
        }
    except Exception as e:
        logger.error(f"Failed to list guidelines: {e}")
        return {
            "guidelines": [],
            "total": 0,
            "filters": {"sources": [], "conditions": [], "evidence_grades": []},
            "error": str(e),
        }


@router.get(
    "/search",
    summary="Search clinical guidelines",
)
async def search_guidelines(
    query: str = Query(..., min_length=3, description="Search query"),
    top_k: int = Query(10, ge=1, le=50, description="Max results"),
) -> dict[str, Any]:
    """Semantic search across clinical guidelines."""
    try:
        from app.services.guideline_rag_service import get_guideline_rag_service

        rag_svc = get_guideline_rag_service()
        if not rag_svc.is_loaded:
            rag_svc.load()

        citations = rag_svc.search(query=query, top_k=top_k, min_score=0.2)

        return {
            "query": query,
            "results": [
                {
                    "section_id": c.section.section_id,
                    "guideline": c.section.guideline,
                    "section_title": c.section.section_title,
                    "recommendation_text": c.section.recommendation_text,
                    "evidence_grade": c.section.evidence_grade,
                    "recommendation_level": c.section.recommendation_level,
                    "applies_to_conditions": c.section.applies_to_conditions,
                    "score": round(c.score, 4),
                    "match_reasons": c.match_reasons,
                }
                for c in citations
            ],
            "total": len(citations),
        }
    except Exception as e:
        logger.error(f"Guideline search failed: {e}")
        return {
            "query": query,
            "results": [],
            "total": 0,
            "error": str(e),
        }


@router.get(
    "/stats",
    summary="Get guideline statistics",
)
async def guideline_stats() -> dict[str, Any]:
    """Get statistics about loaded clinical guidelines."""
    try:
        from app.services.guideline_rag_service import get_guideline_rag_service

        rag_svc = get_guideline_rag_service()
        if not rag_svc.is_loaded:
            rag_svc.load()

        sections = rag_svc._sections

        # Count by source
        source_counts: dict[str, int] = {}
        for s in sections:
            source_counts[s.guideline] = source_counts.get(s.guideline, 0) + 1

        # Count by grade
        grade_counts: dict[str, int] = {}
        for s in sections:
            grade = s.evidence_grade or "Unknown"
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        # Count by recommendation level
        level_counts: dict[str, int] = {}
        for s in sections:
            level = s.recommendation_level or "Unknown"
            level_counts[level] = level_counts.get(level, 0) + 1

        return {
            "total_sections": len(sections),
            "total_guidelines": len(source_counts),
            "by_source": dict(sorted(source_counts.items(), key=lambda x: -x[1])),
            "by_evidence_grade": grade_counts,
            "by_recommendation_level": level_counts,
            "is_loaded": rag_svc.is_loaded,
        }
    except Exception as e:
        logger.error(f"Guideline stats failed: {e}")
        return {
            "total_sections": 0,
            "total_guidelines": 0,
            "by_source": {},
            "by_evidence_grade": {},
            "by_recommendation_level": {},
            "is_loaded": False,
            "error": str(e),
        }
