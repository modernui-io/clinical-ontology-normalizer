"""Medical Coding Management (MED-CODE) API endpoints.

Provides comprehensive medical coding operations: dictionary version management,
MedDRA/WHO Drug coding of adverse events and concomitant medications, auto-coding
rules, coding query resolution, batch coding workflow, and medical coding metrics.

Endpoints:
    GET    /medical-coding/dictionary-versions                   - List dictionary versions
    GET    /medical-coding/dictionary-versions/{version_id}      - Get single version
    POST   /medical-coding/dictionary-versions                   - Create version
    PUT    /medical-coding/dictionary-versions/{version_id}      - Update version
    DELETE /medical-coding/dictionary-versions/{version_id}      - Delete version
    GET    /medical-coding/entries                                - List coding entries
    GET    /medical-coding/entries/{entry_id}                     - Get single entry
    POST   /medical-coding/entries                                - Create entry
    PUT    /medical-coding/entries/{entry_id}                     - Update entry
    DELETE /medical-coding/entries/{entry_id}                     - Delete entry
    GET    /medical-coding/auto-coding-rules                     - List auto-coding rules
    GET    /medical-coding/auto-coding-rules/{rule_id}           - Get single rule
    POST   /medical-coding/auto-coding-rules                     - Create rule
    PUT    /medical-coding/auto-coding-rules/{rule_id}           - Update rule
    DELETE /medical-coding/auto-coding-rules/{rule_id}           - Delete rule
    GET    /medical-coding/queries                                - List coding queries
    GET    /medical-coding/queries/{query_id}                     - Get single query
    POST   /medical-coding/queries                                - Create query
    PUT    /medical-coding/queries/{query_id}                     - Update query
    DELETE /medical-coding/queries/{query_id}                     - Delete query
    GET    /medical-coding/batches                                - List coding batches
    GET    /medical-coding/batches/{batch_id}                     - Get single batch
    POST   /medical-coding/batches                                - Create batch
    PUT    /medical-coding/batches/{batch_id}                     - Update batch
    DELETE /medical-coding/batches/{batch_id}                     - Delete batch
    GET    /medical-coding/metrics                                - Medical coding metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_coding import (
    AutoCodingRule,
    AutoCodingRuleCreate,
    AutoCodingRuleListResponse,
    AutoCodingRuleUpdate,
    CodingBatch,
    CodingBatchCreate,
    CodingBatchListResponse,
    CodingBatchUpdate,
    CodingEntry,
    CodingEntryCreate,
    CodingEntryListResponse,
    CodingEntryUpdate,
    CodingPriority,
    CodingQuery,
    CodingQueryCreate,
    CodingQueryListResponse,
    CodingQueryUpdate,
    CodingStatus,
    DictionaryType,
    DictionaryVersion,
    DictionaryVersionCreate,
    DictionaryVersionListResponse,
    DictionaryVersionUpdate,
    MedicalCodingMetrics,
    QueryStatus,
)
from app.services.medical_coding_service import get_medical_coding_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-coding",
    tags=["Medical Coding"],
)


# ---------------------------------------------------------------------------
# Dictionary Version Management
# ---------------------------------------------------------------------------


@router.get(
    "/dictionary-versions",
    response_model=DictionaryVersionListResponse,
    summary="List dictionary versions",
    description="Retrieve dictionary versions with optional filtering by type and active status.",
)
async def list_dictionary_versions(
    dictionary_type: Optional[DictionaryType] = Query(None, description="Filter by dictionary type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> DictionaryVersionListResponse:
    svc = get_medical_coding_service()
    items = svc.list_dictionary_versions(dictionary_type=dictionary_type, active=active)
    return DictionaryVersionListResponse(items=items, total=len(items))


@router.get(
    "/dictionary-versions/{version_id}",
    response_model=DictionaryVersion,
    summary="Get a dictionary version",
)
async def get_dictionary_version(version_id: str) -> DictionaryVersion:
    svc = get_medical_coding_service()
    version = svc.get_dictionary_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Dictionary version '{version_id}' not found")
    return version


@router.post(
    "/dictionary-versions",
    response_model=DictionaryVersion,
    status_code=201,
    summary="Create a dictionary version",
)
async def create_dictionary_version(payload: DictionaryVersionCreate) -> DictionaryVersion:
    svc = get_medical_coding_service()
    return svc.create_dictionary_version(payload)


@router.put(
    "/dictionary-versions/{version_id}",
    response_model=DictionaryVersion,
    summary="Update a dictionary version",
)
async def update_dictionary_version(
    version_id: str, payload: DictionaryVersionUpdate
) -> DictionaryVersion:
    svc = get_medical_coding_service()
    updated = svc.update_dictionary_version(version_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Dictionary version '{version_id}' not found")
    return updated


@router.delete(
    "/dictionary-versions/{version_id}",
    status_code=204,
    summary="Delete a dictionary version",
)
async def delete_dictionary_version(version_id: str) -> None:
    svc = get_medical_coding_service()
    deleted = svc.delete_dictionary_version(version_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dictionary version '{version_id}' not found")


# ---------------------------------------------------------------------------
# Coding Entry Management
# ---------------------------------------------------------------------------


@router.get(
    "/entries",
    response_model=CodingEntryListResponse,
    summary="List coding entries",
    description="Retrieve coding entries with optional filtering by trial, status, dictionary type, and priority.",
)
async def list_coding_entries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CodingStatus] = Query(None, description="Filter by coding status"),
    dictionary_type: Optional[DictionaryType] = Query(None, description="Filter by dictionary type"),
    priority: Optional[CodingPriority] = Query(None, description="Filter by priority"),
) -> CodingEntryListResponse:
    svc = get_medical_coding_service()
    items = svc.list_coding_entries(
        trial_id=trial_id, status=status,
        dictionary_type=dictionary_type, priority=priority,
    )
    return CodingEntryListResponse(items=items, total=len(items))


@router.get(
    "/entries/{entry_id}",
    response_model=CodingEntry,
    summary="Get a coding entry",
)
async def get_coding_entry(entry_id: str) -> CodingEntry:
    svc = get_medical_coding_service()
    entry = svc.get_coding_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Coding entry '{entry_id}' not found")
    return entry


@router.post(
    "/entries",
    response_model=CodingEntry,
    status_code=201,
    summary="Create a coding entry",
)
async def create_coding_entry(payload: CodingEntryCreate) -> CodingEntry:
    svc = get_medical_coding_service()
    return svc.create_coding_entry(payload)


@router.put(
    "/entries/{entry_id}",
    response_model=CodingEntry,
    summary="Update a coding entry",
)
async def update_coding_entry(
    entry_id: str, payload: CodingEntryUpdate
) -> CodingEntry:
    svc = get_medical_coding_service()
    updated = svc.update_coding_entry(entry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Coding entry '{entry_id}' not found")
    return updated


@router.delete(
    "/entries/{entry_id}",
    status_code=204,
    summary="Delete a coding entry",
)
async def delete_coding_entry(entry_id: str) -> None:
    svc = get_medical_coding_service()
    deleted = svc.delete_coding_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Coding entry '{entry_id}' not found")


# ---------------------------------------------------------------------------
# Auto-Coding Rule Management
# ---------------------------------------------------------------------------


@router.get(
    "/auto-coding-rules",
    response_model=AutoCodingRuleListResponse,
    summary="List auto-coding rules",
    description="Retrieve auto-coding rules with optional filtering by trial, dictionary type, and active status.",
)
async def list_auto_coding_rules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    dictionary_type: Optional[DictionaryType] = Query(None, description="Filter by dictionary type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> AutoCodingRuleListResponse:
    svc = get_medical_coding_service()
    items = svc.list_auto_coding_rules(
        trial_id=trial_id, dictionary_type=dictionary_type, active=active,
    )
    return AutoCodingRuleListResponse(items=items, total=len(items))


@router.get(
    "/auto-coding-rules/{rule_id}",
    response_model=AutoCodingRule,
    summary="Get an auto-coding rule",
)
async def get_auto_coding_rule(rule_id: str) -> AutoCodingRule:
    svc = get_medical_coding_service()
    rule = svc.get_auto_coding_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Auto-coding rule '{rule_id}' not found")
    return rule


@router.post(
    "/auto-coding-rules",
    response_model=AutoCodingRule,
    status_code=201,
    summary="Create an auto-coding rule",
)
async def create_auto_coding_rule(payload: AutoCodingRuleCreate) -> AutoCodingRule:
    svc = get_medical_coding_service()
    return svc.create_auto_coding_rule(payload)


@router.put(
    "/auto-coding-rules/{rule_id}",
    response_model=AutoCodingRule,
    summary="Update an auto-coding rule",
)
async def update_auto_coding_rule(
    rule_id: str, payload: AutoCodingRuleUpdate
) -> AutoCodingRule:
    svc = get_medical_coding_service()
    updated = svc.update_auto_coding_rule(rule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Auto-coding rule '{rule_id}' not found")
    return updated


@router.delete(
    "/auto-coding-rules/{rule_id}",
    status_code=204,
    summary="Delete an auto-coding rule",
)
async def delete_auto_coding_rule(rule_id: str) -> None:
    svc = get_medical_coding_service()
    deleted = svc.delete_auto_coding_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Auto-coding rule '{rule_id}' not found")


# ---------------------------------------------------------------------------
# Coding Query Management
# ---------------------------------------------------------------------------


@router.get(
    "/queries",
    response_model=CodingQueryListResponse,
    summary="List coding queries",
    description="Retrieve coding queries with optional filtering by trial, status, and priority.",
)
async def list_coding_queries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[QueryStatus] = Query(None, description="Filter by query status"),
    priority: Optional[CodingPriority] = Query(None, description="Filter by priority"),
) -> CodingQueryListResponse:
    svc = get_medical_coding_service()
    items = svc.list_coding_queries(
        trial_id=trial_id, status=status, priority=priority,
    )
    return CodingQueryListResponse(items=items, total=len(items))


@router.get(
    "/queries/{query_id}",
    response_model=CodingQuery,
    summary="Get a coding query",
)
async def get_coding_query(query_id: str) -> CodingQuery:
    svc = get_medical_coding_service()
    query = svc.get_coding_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Coding query '{query_id}' not found")
    return query


@router.post(
    "/queries",
    response_model=CodingQuery,
    status_code=201,
    summary="Create a coding query",
)
async def create_coding_query(payload: CodingQueryCreate) -> CodingQuery:
    svc = get_medical_coding_service()
    return svc.create_coding_query(payload)


@router.put(
    "/queries/{query_id}",
    response_model=CodingQuery,
    summary="Update a coding query",
)
async def update_coding_query(
    query_id: str, payload: CodingQueryUpdate
) -> CodingQuery:
    svc = get_medical_coding_service()
    updated = svc.update_coding_query(query_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Coding query '{query_id}' not found")
    return updated


@router.delete(
    "/queries/{query_id}",
    status_code=204,
    summary="Delete a coding query",
)
async def delete_coding_query(query_id: str) -> None:
    svc = get_medical_coding_service()
    deleted = svc.delete_coding_query(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Coding query '{query_id}' not found")


# ---------------------------------------------------------------------------
# Coding Batch Management
# ---------------------------------------------------------------------------


@router.get(
    "/batches",
    response_model=CodingBatchListResponse,
    summary="List coding batches",
    description="Retrieve coding batches with optional filtering by trial, dictionary type, and status.",
)
async def list_coding_batches(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    dictionary_type: Optional[DictionaryType] = Query(None, description="Filter by dictionary type"),
    status: Optional[str] = Query(None, description="Filter by batch status"),
) -> CodingBatchListResponse:
    svc = get_medical_coding_service()
    items = svc.list_coding_batches(
        trial_id=trial_id, dictionary_type=dictionary_type, status=status,
    )
    return CodingBatchListResponse(items=items, total=len(items))


@router.get(
    "/batches/{batch_id}",
    response_model=CodingBatch,
    summary="Get a coding batch",
)
async def get_coding_batch(batch_id: str) -> CodingBatch:
    svc = get_medical_coding_service()
    batch = svc.get_coding_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Coding batch '{batch_id}' not found")
    return batch


@router.post(
    "/batches",
    response_model=CodingBatch,
    status_code=201,
    summary="Create a coding batch",
)
async def create_coding_batch(payload: CodingBatchCreate) -> CodingBatch:
    svc = get_medical_coding_service()
    return svc.create_coding_batch(payload)


@router.put(
    "/batches/{batch_id}",
    response_model=CodingBatch,
    summary="Update a coding batch",
)
async def update_coding_batch(
    batch_id: str, payload: CodingBatchUpdate
) -> CodingBatch:
    svc = get_medical_coding_service()
    updated = svc.update_coding_batch(batch_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Coding batch '{batch_id}' not found")
    return updated


@router.delete(
    "/batches/{batch_id}",
    status_code=204,
    summary="Delete a coding batch",
)
async def delete_coding_batch(batch_id: str) -> None:
    svc = get_medical_coding_service()
    deleted = svc.delete_coding_batch(batch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Coding batch '{batch_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MedicalCodingMetrics,
    summary="Get medical coding metrics",
    description="Aggregated medical coding metrics including coding rates, query resolution, "
                "auto-coding performance, and batch progress.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> MedicalCodingMetrics:
    svc = get_medical_coding_service()
    return svc.get_metrics(trial_id=trial_id)
