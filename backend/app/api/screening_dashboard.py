"""Patient Screening Dashboard API endpoints (VP-Product-8).

Provides saved searches, screening sessions, dashboard summaries,
screening metrics, export, and history for clinical trial patient
recruitment screening.

Endpoints:
    GET    /screening-dashboard/summary              - Dashboard summary
    GET    /screening-dashboard/metrics               - Screening metrics
    GET    /screening-dashboard/history               - Screening history
    GET    /screening-dashboard/stats                 - Service stats
    POST   /screening-dashboard/run                   - Run a screening
    GET    /screening-dashboard/sessions/{session_id} - Get session details
    GET    /screening-dashboard/sessions/{session_id}/export - Export session
    GET    /screening-dashboard/saved-searches        - List saved searches
    POST   /screening-dashboard/saved-searches        - Create saved search
    GET    /screening-dashboard/saved-searches/{id}   - Get saved search
    PUT    /screening-dashboard/saved-searches/{id}   - Update saved search
    DELETE /screening-dashboard/saved-searches/{id}   - Delete saved search
    POST   /screening-dashboard/saved-searches/{id}/execute - Execute saved search
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.screening_dashboard import (
    DashboardSummary,
    ExportResultsResponse,
    RunScreeningRequest,
    SavedSearch,
    SavedSearchCreate,
    SavedSearchUpdate,
    ScreeningHistoryItem,
    ScreeningMetrics,
    ScreeningSession,
)
from app.services.screening_dashboard_service import (
    get_screening_dashboard_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/screening-dashboard",
    tags=["Screening Dashboard"],
)


# ---------------------------------------------------------------------------
# Dashboard Summary & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Dashboard summary",
    description="High-level overview of screening activity: active trials, patient counts, daily trends, and top matching trials.",
)
async def get_dashboard_summary() -> DashboardSummary:
    """Return the dashboard summary."""
    svc = get_screening_dashboard_service()
    return svc.get_dashboard_summary()


@router.get(
    "/metrics",
    response_model=ScreeningMetrics,
    summary="Screening metrics",
    description="Analytics metrics across all screening sessions: averages, exclusion reasons, and daily volume.",
)
async def get_screening_metrics() -> ScreeningMetrics:
    """Return screening metrics."""
    svc = get_screening_dashboard_service()
    return svc.get_screening_metrics()


@router.get(
    "/history",
    response_model=list[ScreeningHistoryItem],
    summary="Screening history",
    description="Recent screening sessions (without per-patient results) sorted by most recent first.",
)
async def get_screening_history(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of history items to return"),
) -> list[ScreeningHistoryItem]:
    """Return screening history."""
    svc = get_screening_dashboard_service()
    return svc.get_screening_history(limit=limit)


@router.get(
    "/stats",
    response_model=dict,
    summary="Service stats",
    description="Internal service statistics: counts of saved searches, sessions, demo patients, and trial criteria.",
)
async def get_stats() -> dict:
    """Return service stats."""
    svc = get_screening_dashboard_service()
    return svc.get_stats()


# ---------------------------------------------------------------------------
# Run Screening
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=ScreeningSession,
    status_code=201,
    summary="Run a screening",
    description="Execute a screening run against a trial with optional filters. Returns a new screening session with per-patient results.",
)
async def run_screening(request: RunScreeningRequest) -> ScreeningSession:
    """Run a screening against a trial."""
    svc = get_screening_dashboard_service()
    session = svc.run_screening(request)
    if session.total_screened == 0 and request.trial_id not in (
        "TRIAL-EYLEA-DME",
        "TRIAL-DUPIXENT-AD",
        "TRIAL-LIBTAYO-CSCC",
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown trial_id: {request.trial_id}",
        )
    return session


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}",
    response_model=ScreeningSession,
    summary="Get session details",
    description="Return full details for a single screening session, including per-patient results.",
)
async def get_session(session_id: str) -> ScreeningSession:
    """Return a screening session by ID."""
    svc = get_screening_dashboard_service()
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@router.get(
    "/sessions/{session_id}/export",
    response_model=ExportResultsResponse,
    summary="Export session results",
    description="Export screening results in JSON or CSV format.",
)
async def export_session_results(
    session_id: str,
    format: str = Query("json", regex="^(json|csv)$", description="Export format: json or csv"),
) -> ExportResultsResponse:
    """Export session results."""
    svc = get_screening_dashboard_service()
    result = svc.export_results(session_id, fmt=format)
    if not result:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return result


# ---------------------------------------------------------------------------
# Saved Searches CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/saved-searches",
    response_model=list[SavedSearch],
    summary="List saved searches",
    description="Return all saved screening searches.",
)
async def list_saved_searches() -> list[SavedSearch]:
    """List all saved searches."""
    svc = get_screening_dashboard_service()
    return svc.list_saved_searches()


@router.post(
    "/saved-searches",
    response_model=SavedSearch,
    status_code=201,
    summary="Create saved search",
    description="Create a new saved screening search with filter criteria.",
)
async def create_saved_search(body: SavedSearchCreate) -> SavedSearch:
    """Create a new saved search."""
    svc = get_screening_dashboard_service()
    return svc.create_saved_search(body)


@router.get(
    "/saved-searches/{search_id}",
    response_model=SavedSearch,
    summary="Get saved search",
    description="Return a single saved search by ID.",
)
async def get_saved_search(search_id: str) -> SavedSearch:
    """Return a saved search by ID."""
    svc = get_screening_dashboard_service()
    search = svc.get_saved_search(search_id)
    if not search:
        raise HTTPException(status_code=404, detail=f"Saved search not found: {search_id}")
    return search


@router.put(
    "/saved-searches/{search_id}",
    response_model=SavedSearch,
    summary="Update saved search",
    description="Update an existing saved search's name, description, or filters.",
)
async def update_saved_search(search_id: str, body: SavedSearchUpdate) -> SavedSearch:
    """Update a saved search."""
    svc = get_screening_dashboard_service()
    search = svc.update_saved_search(search_id, body)
    if not search:
        raise HTTPException(status_code=404, detail=f"Saved search not found: {search_id}")
    return search


@router.delete(
    "/saved-searches/{search_id}",
    status_code=204,
    summary="Delete saved search",
    description="Delete a saved search by ID.",
)
async def delete_saved_search(search_id: str) -> None:
    """Delete a saved search."""
    svc = get_screening_dashboard_service()
    deleted = svc.delete_saved_search(search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Saved search not found: {search_id}")


@router.post(
    "/saved-searches/{search_id}/execute",
    response_model=ScreeningSession,
    status_code=201,
    summary="Execute saved search",
    description="Execute a saved search and return results as a new screening session.",
)
async def execute_saved_search(search_id: str) -> ScreeningSession:
    """Execute a saved search."""
    svc = get_screening_dashboard_service()
    session = svc.execute_saved_search(search_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Saved search not found: {search_id}")
    return session
