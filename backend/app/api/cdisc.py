"""CDISC Controlled Terminology API endpoints.

This module provides REST API endpoints for CDISC CT operations:
- Codelist browsing and lookup
- Term validation
- Domain-based discovery
- Multi-version support
- Search functionality

CDISC Controlled Terminology is the standard terminology for:
- SDTM (Study Data Tabulation Model)
- ADaM (Analysis Data Model)
- CDASH (Clinical Data Acquisition Standards Harmonization)

API Endpoints:
- GET /api/v1/cdisc/codelists - List all codelists
- GET /api/v1/cdisc/codelists/{c_code} - Get codelist by C-code
- GET /api/v1/cdisc/codelists/{c_code}/terms - Get terms in codelist
- POST /api/v1/cdisc/validate - Validate term against codelist
- GET /api/v1/cdisc/search - Search codelists/terms
- GET /api/v1/cdisc/domains - List SDTM domains
- GET /api/v1/cdisc/domains/{domain}/codelists - Get codelists for domain
- GET /api/v1/cdisc/versions - List available CT versions
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.cdisc_terminology_service import (
    CDISCDomain,
    CodelistType,
    get_cdisc_terminology_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cdisc", tags=["cdisc"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ValidateTermRequest(BaseModel):
    """Request for term validation."""

    codelist: str = Field(
        ...,
        description="Codelist C-code (e.g., 'C66731') or submission value (e.g., 'SEX')"
    )
    value: str = Field(
        ...,
        description="The value to validate"
    )
    strict: bool = Field(
        True,
        description="If True, reject unknown values even for extensible codelists"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "codelist": "SEX",
                "value": "M",
                "strict": True
            }
        }


class ValidateTermResponse(BaseModel):
    """Response for term validation."""

    is_valid: bool
    codelist_code: str
    codelist_name: str
    submitted_value: str
    matched_submission_value: str | None = None
    matched_preferred_term: str | None = None
    message: str
    is_extensible: bool
    suggestions: list[dict[str, Any]] = Field(default_factory=list)


class CodelistSummary(BaseModel):
    """Summary of a codelist for list responses."""

    c_code: str
    name: str
    submission_value: str
    definition: str
    codelist_type: str
    domain: str
    term_count: int
    version: str


class TermSummary(BaseModel):
    """Summary of a term."""

    code: str
    submission_value: str
    preferred_term: str
    definition: str
    synonyms: list[str]
    ordinal: int


class CodelistDetail(BaseModel):
    """Detailed codelist with terms."""

    c_code: str
    name: str
    submission_value: str
    definition: str
    codelist_type: str
    domain: str
    term_count: int
    version: str
    nci_preferred_term: str
    related_codelists: list[str]
    terms: list[TermSummary]


class DomainInfo(BaseModel):
    """Information about an SDTM domain."""

    domain: str
    description: str
    codelist_count: int
    codelists: list[str]


class VersionInfo(BaseModel):
    """Information about a CT version."""

    version: str
    release_date: str
    description: str
    codelist_count: int
    term_count: int
    is_current: bool


class StatsResponse(BaseModel):
    """Statistics about the terminology database."""

    total_codelists: int
    total_terms: int
    extensible_codelists: int
    non_extensible_codelists: int
    current_version: str
    available_versions: list[str]
    by_domain: dict[str, int]


# =============================================================================
# Codelist Endpoints
# =============================================================================

@router.get("/codelists", response_model=None)
async def list_codelists(
    domain: str | None = Query(None, description="Filter by SDTM domain (DM, AE, CM, etc.)"),
    codelist_type: str | None = Query(None, description="Filter by type (extensible, non-extensible)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """List all CDISC codelists with optional filtering.

    Returns paginated list of codelists with summary information.

    Args:
        domain: Filter by SDTM domain (DM, AE, CM, DS, LB, VS, etc.)
        codelist_type: Filter by extensible or non-extensible
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        Dictionary with codelists array and pagination info
    """
    service = get_cdisc_terminology_service()

    # Parse domain filter
    domain_enum = None
    if domain:
        try:
            domain_enum = CDISCDomain[domain.upper()]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain '{domain}'. Valid domains: {[d.name for d in CDISCDomain]}"
            )

    # Get codelists
    codelists = service.list_codelists(domain=domain_enum, limit=limit, offset=offset)

    # Apply type filter if specified
    if codelist_type:
        type_lower = codelist_type.lower()
        if "extensible" in type_lower and "non" not in type_lower:
            codelists = [cl for cl in codelists if cl.codelist_type == CodelistType.EXTENSIBLE]
        elif "non" in type_lower:
            codelists = [cl for cl in codelists if cl.codelist_type == CodelistType.NON_EXTENSIBLE]

    # Build response
    items = []
    for cl in codelists:
        items.append({
            "c_code": cl.c_code,
            "name": cl.name,
            "submission_value": cl.submission_value,
            "definition": cl.definition,
            "codelist_type": cl.codelist_type.value,
            "domain": cl.domain.name,
            "term_count": len(cl.terms),
            "version": cl.version,
        })

    stats = service.get_stats()

    return {
        "items": items,
        "total": stats["total_codelists"],
        "limit": limit,
        "offset": offset,
        "filters": {
            "domain": domain,
            "codelist_type": codelist_type,
        },
    }


@router.get("/codelists/{c_code}", response_model=None)
async def get_codelist(
    c_code: str,
    include_terms: bool = Query(True, description="Include terms in response"),
) -> dict[str, Any]:
    """Get a codelist by C-code or submission value.

    Args:
        c_code: NCI C-code (e.g., 'C66731') or submission value (e.g., 'SEX')
        include_terms: Whether to include terms in response

    Returns:
        Codelist details with optional terms

    Raises:
        HTTPException: 404 if codelist not found
    """
    service = get_cdisc_terminology_service()

    # Try C-code first, then submission value
    codelist = service.get_codelist(c_code)
    if not codelist:
        codelist = service.get_codelist_by_name(c_code)

    if not codelist:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Codelist not found",
                "code": c_code,
                "message": f"No codelist found with C-code or submission value '{c_code}'"
            }
        )

    response: dict[str, Any] = {
        "c_code": codelist.c_code,
        "name": codelist.name,
        "submission_value": codelist.submission_value,
        "definition": codelist.definition,
        "codelist_type": codelist.codelist_type.value,
        "domain": codelist.domain.name,
        "domain_description": codelist.domain.value,
        "term_count": len(codelist.terms),
        "version": codelist.version,
        "nci_preferred_term": codelist.nci_preferred_term,
        "related_codelists": codelist.related_codelists,
    }

    if include_terms:
        response["terms"] = [
            {
                "code": term.code,
                "submission_value": term.submission_value,
                "preferred_term": term.preferred_term,
                "definition": term.definition,
                "synonyms": term.synonyms,
                "ordinal": term.ordinal,
                "nci_code": term.nci_code,
            }
            for term in codelist.terms
        ]

    return response


@router.get("/codelists/{c_code}/terms", response_model=None)
async def get_codelist_terms(
    c_code: str,
    search: str | None = Query(None, description="Filter terms by search query"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> dict[str, Any]:
    """Get terms for a codelist.

    Args:
        c_code: Codelist C-code or submission value
        search: Optional search filter
        limit: Maximum results

    Returns:
        Dictionary with terms array

    Raises:
        HTTPException: 404 if codelist not found
    """
    service = get_cdisc_terminology_service()

    # Try C-code first, then submission value
    codelist = service.get_codelist(c_code)
    if not codelist:
        codelist = service.get_codelist_by_name(c_code)

    if not codelist:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Codelist not found",
                "code": c_code,
            }
        )

    terms = codelist.terms

    # Apply search filter
    if search:
        search_lower = search.lower()
        filtered_terms = []
        for term in terms:
            if (search_lower in term.submission_value.lower() or
                search_lower in term.preferred_term.lower() or
                any(search_lower in s.lower() for s in term.synonyms)):
                filtered_terms.append(term)
        terms = filtered_terms

    # Apply limit
    terms = terms[:limit]

    return {
        "codelist_code": codelist.c_code,
        "codelist_name": codelist.name,
        "codelist_type": codelist.codelist_type.value,
        "total_terms": len(codelist.terms),
        "returned_terms": len(terms),
        "terms": [
            {
                "code": term.code,
                "submission_value": term.submission_value,
                "preferred_term": term.preferred_term,
                "definition": term.definition,
                "synonyms": term.synonyms,
                "ordinal": term.ordinal,
            }
            for term in terms
        ],
    }


# =============================================================================
# Validation Endpoint
# =============================================================================

@router.post("/validate", response_model=ValidateTermResponse)
async def validate_term(request: ValidateTermRequest) -> ValidateTermResponse:
    """Validate a term against a codelist.

    Checks if a value is valid for a given codelist, considering:
    - Exact match on submission value
    - Match on preferred term
    - Match on synonyms
    - Extensibility of the codelist

    Args:
        request: Validation request with codelist and value

    Returns:
        Validation result with match details and suggestions
    """
    service = get_cdisc_terminology_service()

    result = service.validate_term(
        codelist_code=request.codelist,
        value=request.value,
        strict=request.strict,
    )

    suggestions = []
    for term in result.suggestions:
        suggestions.append({
            "code": term.code,
            "submission_value": term.submission_value,
            "preferred_term": term.preferred_term,
        })

    return ValidateTermResponse(
        is_valid=result.is_valid,
        codelist_code=result.codelist_code,
        codelist_name=result.codelist_name,
        submitted_value=result.submitted_value,
        matched_submission_value=result.matched_term.submission_value if result.matched_term else None,
        matched_preferred_term=result.matched_term.preferred_term if result.matched_term else None,
        message=result.message,
        is_extensible=result.is_extensible,
        suggestions=suggestions,
    )


# =============================================================================
# Search Endpoint
# =============================================================================

@router.get("/search", response_model=None)
async def search_terminology(
    q: str = Query(..., min_length=1, description="Search query"),
    search_type: str = Query("all", description="Search type: codelists, terms, or all"),
    domain: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> dict[str, Any]:
    """Search across codelists and terms.

    Args:
        q: Search query (minimum 1 character)
        search_type: What to search: codelists, terms, or all
        domain: Optional domain filter
        limit: Maximum results

    Returns:
        Search results with codelists and/or terms
    """
    service = get_cdisc_terminology_service()

    # Parse domain filter
    domain_enum = None
    if domain:
        try:
            domain_enum = CDISCDomain[domain.upper()]
        except KeyError:
            pass

    response: dict[str, Any] = {
        "query": q,
        "search_type": search_type,
    }

    # Search codelists
    if search_type in ("codelists", "all"):
        codelists = service.search_codelists(q, domain=domain_enum, limit=limit)
        response["codelists"] = [
            {
                "c_code": cl.c_code,
                "name": cl.name,
                "submission_value": cl.submission_value,
                "definition": cl.definition,
                "codelist_type": cl.codelist_type.value,
                "domain": cl.domain.name,
                "term_count": len(cl.terms),
            }
            for cl in codelists
        ]
        response["codelist_count"] = len(codelists)

    # Search terms
    if search_type in ("terms", "all"):
        term_results = service.search_terms(q, limit=limit)
        terms = []
        for codelist, term in term_results:
            terms.append({
                "term": {
                    "code": term.code,
                    "submission_value": term.submission_value,
                    "preferred_term": term.preferred_term,
                    "synonyms": term.synonyms,
                },
                "codelist": {
                    "c_code": codelist.c_code,
                    "name": codelist.name,
                    "submission_value": codelist.submission_value,
                },
            })
        response["terms"] = terms
        response["term_count"] = len(terms)

    return response


# =============================================================================
# Domain Endpoints
# =============================================================================

@router.get("/domains", response_model=None)
async def list_domains() -> dict[str, Any]:
    """List all SDTM domains with codelist counts.

    Returns:
        List of domains with their descriptions and codelist counts
    """
    service = get_cdisc_terminology_service()
    domains = service.list_domains()

    return {
        "domains": domains,
        "total": len(domains),
    }


@router.get("/domains/{domain}/codelists", response_model=None)
async def get_domain_codelists(
    domain: str,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Get all codelists for a specific domain.

    Args:
        domain: SDTM domain code (DM, AE, CM, etc.)
        limit: Maximum results

    Returns:
        Codelists associated with the domain

    Raises:
        HTTPException: 400 if invalid domain
    """
    service = get_cdisc_terminology_service()

    try:
        domain_enum = CDISCDomain[domain.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid domain",
                "domain": domain,
                "valid_domains": [d.name for d in CDISCDomain],
            }
        )

    codelists = service.get_codelists_for_domain(domain_enum)

    return {
        "domain": domain_enum.name,
        "domain_description": domain_enum.value,
        "codelist_count": len(codelists),
        "codelists": [
            {
                "c_code": cl.c_code,
                "name": cl.name,
                "submission_value": cl.submission_value,
                "codelist_type": cl.codelist_type.value,
                "term_count": len(cl.terms),
            }
            for cl in codelists[:limit]
        ],
    }


# =============================================================================
# Version Endpoints
# =============================================================================

@router.get("/versions", response_model=None)
async def list_versions() -> dict[str, Any]:
    """List available CT versions.

    Returns:
        List of CT versions with metadata
    """
    service = get_cdisc_terminology_service()
    versions = service.list_versions()

    return {
        "current_version": service.get_current_version(),
        "versions": [
            {
                "version": v.version,
                "release_date": v.release_date.isoformat(),
                "description": v.description,
                "codelist_count": v.codelist_count,
                "term_count": v.term_count,
                "is_current": v.is_current,
            }
            for v in versions
        ],
    }


# =============================================================================
# Statistics Endpoint
# =============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get statistics about the CDISC terminology database.

    Returns:
        Statistics including counts by type and domain
    """
    service = get_cdisc_terminology_service()
    stats = service.get_stats()

    return StatsResponse(
        total_codelists=stats["total_codelists"],
        total_terms=stats["total_terms"],
        extensible_codelists=stats["extensible_codelists"],
        non_extensible_codelists=stats["non_extensible_codelists"],
        current_version=stats["current_version"],
        available_versions=stats["available_versions"],
        by_domain=stats["by_domain"],
    )


# =============================================================================
# Utility Endpoints
# =============================================================================

@router.get("/lookup/{submission_value}", response_model=None)
async def lookup_by_submission_value(
    submission_value: str,
) -> dict[str, Any]:
    """Quick lookup of a codelist by submission value.

    Args:
        submission_value: Codelist short name (SEX, RACE, AEOUT, etc.)

    Returns:
        Codelist summary

    Raises:
        HTTPException: 404 if not found
    """
    service = get_cdisc_terminology_service()
    codelist = service.get_codelist_by_name(submission_value)

    if not codelist:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Codelist not found",
                "submission_value": submission_value,
            }
        )

    return {
        "c_code": codelist.c_code,
        "name": codelist.name,
        "submission_value": codelist.submission_value,
        "definition": codelist.definition,
        "codelist_type": codelist.codelist_type.value,
        "domain": codelist.domain.name,
        "term_count": len(codelist.terms),
    }
