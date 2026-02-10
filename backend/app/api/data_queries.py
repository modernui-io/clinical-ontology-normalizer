"""Data Queries & Discrepancy Management API endpoints (CLINICAL-18).

Provides comprehensive data query operations: query CRUD and lifecycle management,
response tracking, auto-query rule engine, query aging reports, discrepancy
resolution workflow, site query summaries, bulk operations, and query metrics.

Endpoints:
    GET    /data-queries/queries                                - List data queries
    GET    /data-queries/queries/{query_id}                     - Get single query
    POST   /data-queries/queries                                - Create data query
    PUT    /data-queries/queries/{query_id}                     - Update data query
    DELETE /data-queries/queries/{query_id}                     - Delete data query
    POST   /data-queries/queries/{query_id}/respond             - Respond to query
    POST   /data-queries/queries/{query_id}/close               - Close query with resolution
    POST   /data-queries/queries/{query_id}/requery             - Re-query (send back to site)
    POST   /data-queries/queries/{query_id}/cancel              - Cancel query
    GET    /data-queries/queries/{query_id}/responses            - List query responses
    GET    /data-queries/queries/{query_id}/resolution           - Get resolution details
    GET    /data-queries/auto-rules                              - List auto-query rules
    GET    /data-queries/auto-rules/{rule_id}                    - Get single auto-query rule
    POST   /data-queries/auto-rules                              - Create auto-query rule
    PUT    /data-queries/auto-rules/{rule_id}                    - Update auto-query rule
    DELETE /data-queries/auto-rules/{rule_id}                    - Delete auto-query rule
    POST   /data-queries/auto-rules/evaluate                     - Evaluate auto-query rules
    GET    /data-queries/reports/aging                            - Query aging report
    GET    /data-queries/reports/metrics                          - Query metrics dashboard
    GET    /data-queries/reports/site-summary                     - Site query summary
    POST   /data-queries/bulk/close                               - Bulk close queries
    POST   /data-queries/bulk/assign                              - Bulk assign queries
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.data_queries import (
    AutoQueryRule,
    AutoQueryRuleCreate,
    AutoQueryRuleListResponse,
    AutoQueryRuleUpdate,
    BulkAssignRequest,
    BulkCloseRequest,
    BulkOperationResult,
    DataQuery,
    DataQueryCreate,
    DataQueryListResponse,
    DataQueryUpdate,
    DiscrepancyResolution,
    QueryAgingReport,
    QueryCategory,
    QueryMetrics,
    QueryPriority,
    QueryResponse,
    QueryResponseCreate,
    QueryResponseListResponse,
    QuerySource,
    QueryStatus,
    QueryCloseRequest,
    SiteQuerySummary,
    SiteQuerySummaryListResponse,
)
from app.services.data_queries_service import get_data_queries_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data-queries",
    tags=["Data Queries & Discrepancy Management"],
)


# ---------------------------------------------------------------------------
# Query CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/queries",
    response_model=DataQueryListResponse,
    summary="List data queries",
    description="Retrieve data queries with optional filtering by trial, site, status, priority, category, source, and assignee.",
)
async def list_queries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[QueryStatus] = Query(None, description="Filter by query status"),
    priority: Optional[QueryPriority] = Query(None, description="Filter by priority"),
    category: Optional[QueryCategory] = Query(None, description="Filter by category"),
    source: Optional[QuerySource] = Query(None, description="Filter by source"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
) -> DataQueryListResponse:
    svc = get_data_queries_service()
    items = svc.list_queries(
        trial_id=trial_id,
        site_id=site_id,
        status=status,
        priority=priority,
        category=category,
        source=source,
        assigned_to=assigned_to,
    )
    return DataQueryListResponse(items=items, total=len(items))


@router.get(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Get a data query",
)
async def get_query(query_id: str) -> DataQuery:
    svc = get_data_queries_service()
    query = svc.get_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    return query


@router.post(
    "/queries",
    response_model=DataQuery,
    status_code=201,
    summary="Create a data query",
    description="Open a new data query for a clinical data discrepancy.",
)
async def create_query(payload: DataQueryCreate) -> DataQuery:
    svc = get_data_queries_service()
    return svc.create_query(payload)


@router.put(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Update a data query",
)
async def update_query(query_id: str, payload: DataQueryUpdate) -> DataQuery:
    svc = get_data_queries_service()
    updated = svc.update_query(query_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    return updated


@router.delete(
    "/queries/{query_id}",
    status_code=204,
    summary="Delete a data query",
)
async def delete_query(query_id: str) -> None:
    svc = get_data_queries_service()
    deleted = svc.delete_query(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")


# ---------------------------------------------------------------------------
# Query Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/queries/{query_id}/respond",
    response_model=QueryResponse,
    summary="Respond to a data query",
    description="Add a response to a data query and transition its status to 'answered'.",
)
async def respond_to_query(
    query_id: str, payload: QueryResponseCreate
) -> QueryResponse:
    svc = get_data_queries_service()
    try:
        result = svc.respond_to_query(query_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    return result


@router.post(
    "/queries/{query_id}/close",
    response_model=DataQuery,
    summary="Close a data query",
    description="Close a data query with resolution details including resolution type and notes.",
)
async def close_query(query_id: str, payload: QueryCloseRequest) -> DataQuery:
    svc = get_data_queries_service()
    try:
        result = svc.close_query(query_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    return result


@router.post(
    "/queries/{query_id}/requery",
    response_model=DataQuery,
    summary="Re-query a data query",
    description="Send a query back to the site with updated query text when the initial response was insufficient.",
)
async def requery(
    query_id: str,
    query_text: str = Query(..., description="Updated query text for the re-query"),
) -> DataQuery:
    svc = get_data_queries_service()
    try:
        result = svc.requery(query_id, query_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    return result


@router.post(
    "/queries/{query_id}/cancel",
    response_model=DataQuery,
    summary="Cancel a data query",
    description="Cancel a data query that is no longer needed.",
)
async def cancel_query(query_id: str) -> DataQuery:
    svc = get_data_queries_service()
    try:
        result = svc.cancel_query(query_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Query Responses & Resolutions
# ---------------------------------------------------------------------------


@router.get(
    "/queries/{query_id}/responses",
    response_model=QueryResponseListResponse,
    summary="List responses for a query",
    description="Retrieve all responses submitted for a specific data query.",
)
async def list_query_responses(query_id: str) -> QueryResponseListResponse:
    svc = get_data_queries_service()
    query = svc.get_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Data query '{query_id}' not found")
    items = svc.list_responses(query_id)
    return QueryResponseListResponse(items=items, total=len(items))


@router.get(
    "/queries/{query_id}/resolution",
    response_model=DiscrepancyResolution,
    summary="Get resolution details for a query",
    description="Retrieve the discrepancy resolution details for a closed data query.",
)
async def get_resolution(query_id: str) -> DiscrepancyResolution:
    svc = get_data_queries_service()
    resolution = svc.get_resolution(query_id)
    if resolution is None:
        raise HTTPException(
            status_code=404,
            detail=f"Resolution for query '{query_id}' not found",
        )
    return resolution


# ---------------------------------------------------------------------------
# Auto-Query Rules
# ---------------------------------------------------------------------------


@router.get(
    "/auto-rules",
    response_model=AutoQueryRuleListResponse,
    summary="List auto-query rules",
    description="Retrieve auto-query rules with optional filtering by active status.",
)
async def list_auto_rules(
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> AutoQueryRuleListResponse:
    svc = get_data_queries_service()
    items = svc.list_auto_rules(active=active)
    return AutoQueryRuleListResponse(items=items, total=len(items))


@router.get(
    "/auto-rules/{rule_id}",
    response_model=AutoQueryRule,
    summary="Get an auto-query rule",
)
async def get_auto_rule(rule_id: str) -> AutoQueryRule:
    svc = get_data_queries_service()
    rule = svc.get_auto_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Auto-query rule '{rule_id}' not found")
    return rule


@router.post(
    "/auto-rules",
    response_model=AutoQueryRule,
    status_code=201,
    summary="Create an auto-query rule",
    description="Create a new automatic query generation rule for programmatic data checks.",
)
async def create_auto_rule(payload: AutoQueryRuleCreate) -> AutoQueryRule:
    svc = get_data_queries_service()
    return svc.create_auto_rule(payload)


@router.put(
    "/auto-rules/{rule_id}",
    response_model=AutoQueryRule,
    summary="Update an auto-query rule",
)
async def update_auto_rule(rule_id: str, payload: AutoQueryRuleUpdate) -> AutoQueryRule:
    svc = get_data_queries_service()
    updated = svc.update_auto_rule(rule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Auto-query rule '{rule_id}' not found")
    return updated


@router.delete(
    "/auto-rules/{rule_id}",
    status_code=204,
    summary="Delete an auto-query rule",
)
async def delete_auto_rule(rule_id: str) -> None:
    svc = get_data_queries_service()
    deleted = svc.delete_auto_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Auto-query rule '{rule_id}' not found")


@router.post(
    "/auto-rules/evaluate",
    response_model=DataQueryListResponse,
    summary="Evaluate auto-query rules",
    description="Run all active auto-query rules against a trial/site and generate queries for any violations found.",
)
async def evaluate_auto_rules(
    trial_id: str = Query(..., description="Trial ID to evaluate rules against"),
    site_id: str = Query(..., description="Site ID to evaluate rules against"),
) -> DataQueryListResponse:
    svc = get_data_queries_service()
    items = svc.evaluate_auto_rules(trial_id, site_id)
    return DataQueryListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get(
    "/reports/aging",
    response_model=QueryAgingReport,
    summary="Get query aging report",
    description="Generate a report showing open queries grouped by age buckets (0-7d, 8-14d, 15-30d, 30+d).",
)
async def get_aging_report() -> QueryAgingReport:
    svc = get_data_queries_service()
    return svc.get_aging_report()


@router.get(
    "/reports/metrics",
    response_model=QueryMetrics,
    summary="Get query metrics dashboard",
    description="Aggregated data query metrics including counts by status, category, site, and priority.",
)
async def get_query_metrics() -> QueryMetrics:
    svc = get_data_queries_service()
    return svc.get_query_metrics()


@router.get(
    "/reports/site-summary",
    response_model=SiteQuerySummaryListResponse,
    summary="Get site query summaries",
    description="Get query summary per site with counts by status and average resolution time.",
)
async def get_site_query_summary(
    site_id: Optional[str] = Query(None, description="Filter by specific site ID"),
) -> SiteQuerySummaryListResponse:
    svc = get_data_queries_service()
    items = svc.get_site_query_summary(site_id=site_id)
    return SiteQuerySummaryListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------


@router.post(
    "/bulk/close",
    response_model=BulkOperationResult,
    summary="Bulk close queries",
    description="Close multiple data queries at once with the same resolution details.",
)
async def bulk_close_queries(payload: BulkCloseRequest) -> BulkOperationResult:
    svc = get_data_queries_service()
    return svc.bulk_close_queries(payload)


@router.post(
    "/bulk/assign",
    response_model=BulkOperationResult,
    summary="Bulk assign queries",
    description="Assign multiple data queries to a specific person or role.",
)
async def bulk_assign_queries(payload: BulkAssignRequest) -> BulkOperationResult:
    svc = get_data_queries_service()
    return svc.bulk_assign_queries(payload)
