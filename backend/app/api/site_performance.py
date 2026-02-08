"""Clinical Site Performance Analytics API endpoints (CMO-8).

Exposes site performance monitoring, benchmarking, scoring, and
recommendations for multi-site clinical trial operations.

Endpoints:
    GET  /site-performance/sites                  - List all sites
    GET  /site-performance/sites/{site_id}         - Get single site
    GET  /site-performance/scores                  - Performance scores for all sites
    GET  /site-performance/scores/{site_id}        - Performance score for one site
    GET  /site-performance/benchmarks/{site_id}    - Benchmark a site against cohort
    GET  /site-performance/compare                 - Head-to-head site comparison
    GET  /site-performance/recommendations/{site_id} - Recommendations for a site
    GET  /site-performance/underperformers         - Sites below threshold
    GET  /site-performance/metrics                 - Program-wide aggregate metrics
    GET  /site-performance/trends/{site_id}        - Enrollment trends for a site
    GET  /site-performance/stats                   - Service health stats
    GET  /site-performance/countries               - Sites grouped by country
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.permissions import Permission, PermissionChecker
from app.schemas.site_performance import (
    ClinicalSite,
    EnrollmentTrendResponse,
    SiteBenchmarksResponse,
    SiteComparison,
    SiteListResponse,
    SiteMetrics,
    SiteRecommendationsResponse,
    SiteScoresResponse,
    UnderperformersResponse,
)
from app.services.site_performance_service import get_site_performance_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-performance",
    tags=["Site Performance Analytics"],
)


# ---------------------------------------------------------------------------
# Permission dependency
# ---------------------------------------------------------------------------

_perm_checker = PermissionChecker([Permission.READ_ANALYTICS])


async def _require_perm(request: Request) -> None:
    return await _perm_checker(request)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sites",
    response_model=SiteListResponse,
    summary="List clinical sites",
    description="List all clinical sites with optional filters for status, country, and trial.",
)
async def list_sites(
    status: Optional[str] = Query(None, description="Filter by site status"),
    country: Optional[str] = Query(None, description="Filter by country code (e.g. US, DE, JP)"),
    trial_id: Optional[str] = Query(None, description="Filter by associated trial ID"),
    _perm: None = Depends(_require_perm),
) -> SiteListResponse:
    """Return a filtered list of clinical sites."""
    svc = get_site_performance_service()
    return svc.list_sites(status=status, country=country, trial_id=trial_id)


@router.get(
    "/sites/{site_id}",
    response_model=ClinicalSite,
    summary="Get a clinical site",
    description="Return detailed information for a single clinical site.",
)
async def get_site(
    site_id: str,
    _perm: None = Depends(_require_perm),
) -> ClinicalSite:
    """Return a single site by ID."""
    svc = get_site_performance_service()
    site = svc.get_site(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return site


@router.get(
    "/scores",
    response_model=SiteScoresResponse,
    summary="Performance scores for all sites",
    description="Calculate and return performance scores for all scorable sites.",
)
async def get_all_scores(
    _perm: None = Depends(_require_perm),
) -> SiteScoresResponse:
    """Return performance scores for all sites."""
    svc = get_site_performance_service()
    return svc.calculate_performance_scores()


@router.get(
    "/scores/{site_id}",
    summary="Performance score for a single site",
    description="Return the performance score for a specific site.",
)
async def get_site_score(
    site_id: str,
    _perm: None = Depends(_require_perm),
) -> dict:
    """Return the performance score for a specific site."""
    svc = get_site_performance_service()
    site = svc.get_site(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")

    scores_resp = svc.calculate_performance_scores()
    for score in scores_resp.scores:
        if score.site_id == site_id:
            return score.model_dump()
    raise HTTPException(status_code=404, detail=f"No score available for site {site_id}")


@router.get(
    "/benchmarks/{site_id}",
    response_model=SiteBenchmarksResponse,
    summary="Benchmark a site against cohort",
    description="Compare a site's metrics against cohort percentiles (p25/p50/p75/p90).",
)
async def get_benchmarks(
    site_id: str,
    _perm: None = Depends(_require_perm),
) -> SiteBenchmarksResponse:
    """Return benchmark comparisons for a site."""
    svc = get_site_performance_service()
    result = svc.get_site_benchmarks(site_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return result


@router.get(
    "/compare",
    response_model=SiteComparison,
    summary="Compare two sites head-to-head",
    description="Return a head-to-head metric comparison between two sites.",
)
async def compare_sites(
    site_a: str = Query(..., description="First site ID"),
    site_b: str = Query(..., description="Second site ID"),
    _perm: None = Depends(_require_perm),
) -> SiteComparison:
    """Compare two sites across key metrics."""
    svc = get_site_performance_service()
    result = svc.compare_sites(site_a, site_b)
    if result is None:
        raise HTTPException(status_code=404, detail="One or both sites not found")
    return result


@router.get(
    "/recommendations/{site_id}",
    response_model=SiteRecommendationsResponse,
    summary="Recommendations for a site",
    description="Auto-generate performance-based recommendations for a site.",
)
async def get_recommendations(
    site_id: str,
    _perm: None = Depends(_require_perm),
) -> SiteRecommendationsResponse:
    """Return recommendations for a site."""
    svc = get_site_performance_service()
    result = svc.get_recommendations(site_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return result


@router.get(
    "/underperformers",
    response_model=UnderperformersResponse,
    summary="Underperforming sites",
    description="Return sites with an overall performance score below the given threshold.",
)
async def get_underperformers(
    threshold: float = Query(50.0, ge=0.0, le=100.0, description="Score threshold"),
    _perm: None = Depends(_require_perm),
) -> UnderperformersResponse:
    """Return sites performing below threshold."""
    svc = get_site_performance_service()
    return svc.get_underperformers(threshold)


@router.get(
    "/metrics",
    response_model=SiteMetrics,
    summary="Program-wide site metrics",
    description="Aggregate metrics across all clinical trial sites.",
)
async def get_metrics(
    _perm: None = Depends(_require_perm),
) -> SiteMetrics:
    """Return program-wide aggregate site metrics."""
    svc = get_site_performance_service()
    return svc.get_metrics()


@router.get(
    "/trends/{site_id}",
    response_model=EnrollmentTrendResponse,
    summary="Enrollment trends for a site",
    description="Monthly enrollment trend for a site over the specified number of months.",
)
async def get_enrollment_trends(
    site_id: str,
    months: int = Query(6, ge=1, le=24, description="Number of months of trend data"),
    _perm: None = Depends(_require_perm),
) -> EnrollmentTrendResponse:
    """Return monthly enrollment trend data for a site."""
    svc = get_site_performance_service()
    result = svc.get_enrollment_trends(site_id, months=months)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return result


@router.get(
    "/stats",
    summary="Service health stats",
    description="Return internal stats for the site performance service.",
)
async def get_stats(
    _perm: None = Depends(_require_perm),
) -> dict:
    """Return service health stats."""
    svc = get_site_performance_service()
    return svc.get_stats()


@router.get(
    "/countries",
    summary="Sites grouped by country",
    description="Return site counts grouped by country code.",
)
async def get_countries(
    _perm: None = Depends(_require_perm),
) -> dict:
    """Return sites grouped by country."""
    svc = get_site_performance_service()
    metrics = svc.get_metrics()
    return {"by_country": metrics.by_country, "total_countries": len(metrics.by_country)}
