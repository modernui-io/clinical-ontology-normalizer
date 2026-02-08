"""Feature Store API endpoints.

Provides endpoints for managing ML features used in
clinical trial patient screening pipelines:
- List, register, update, and inspect feature definitions
- Compute feature vectors for individual or batch patients
- View feature statistics and importance rankings
- Access feature version history
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.feature_store import (
    BatchComputeRequest,
    BatchComputeResponse,
    FeatureDataType,
    FeatureDefinitionCreate,
    FeatureDefinitionListResponse,
    FeatureDefinitionResponse,
    FeatureDefinitionUpdate,
    FeatureDomain,
    FeatureImportanceListResponse,
    FeatureStatisticsListResponse,
    FeatureVectorResponse,
    FeatureVersionHistory,
)
from app.services.feature_store_service import get_feature_store_service

router = APIRouter(prefix="/feature-store", tags=["Feature Store"])


# ============================================================================
# Feature Definitions — collection endpoints (no path params)
# ============================================================================


@router.get(
    "/features",
    response_model=FeatureDefinitionListResponse,
    summary="List all feature definitions",
    description="Return all registered feature definitions, optionally filtered by domain, data type, or tag.",
)
async def list_features(
    domain: FeatureDomain | None = Query(None, description="Filter by clinical domain"),
    data_type: FeatureDataType | None = Query(None, description="Filter by data type"),
    tag: str | None = Query(None, description="Filter by tag"),
) -> FeatureDefinitionListResponse:
    """List all feature definitions with optional filters."""
    service = get_feature_store_service()
    features = service.list_features(domain=domain, data_type=data_type, tag=tag)
    return FeatureDefinitionListResponse(total=len(features), features=features)


@router.post(
    "/features",
    response_model=FeatureDefinitionResponse,
    status_code=201,
    summary="Register a new feature",
    description="Register a new custom feature definition.",
)
async def register_feature(
    body: FeatureDefinitionCreate,
) -> FeatureDefinitionResponse:
    """Register a new feature definition."""
    service = get_feature_store_service()
    try:
        return service.register_feature(
            name=body.name,
            description=body.description,
            data_type=body.data_type,
            domain=body.domain,
            computation_logic=body.computation_logic,
            freshness_requirements=body.freshness_requirements,
            source_tables=body.source_tables,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ============================================================================
# Feature Statistics & Importance  (static paths — MUST be before /{name})
# ============================================================================


@router.get(
    "/features/statistics",
    response_model=FeatureStatisticsListResponse,
    summary="Get feature statistics",
    description="Return descriptive statistics for all features. Computes from sample if not cached.",
)
async def get_statistics(
    recompute: bool = Query(False, description="Force recomputation of statistics"),
) -> FeatureStatisticsListResponse:
    """Get feature statistics."""
    service = get_feature_store_service()
    if not recompute:
        cached = service.get_cached_statistics()
        if cached is not None:
            return cached
    return service.compute_statistics()


@router.get(
    "/features/importance",
    response_model=FeatureImportanceListResponse,
    summary="Get feature importance ranking",
    description="Return all features ranked by their importance for screening decisions.",
)
async def get_importance() -> FeatureImportanceListResponse:
    """Get feature importance rankings."""
    service = get_feature_store_service()
    return service.get_importance()


# ============================================================================
# Feature Computation  (static prefix paths — MUST be before /{name})
# ============================================================================


@router.post(
    "/features/batch-compute",
    response_model=BatchComputeResponse,
    summary="Batch compute features",
    description="Compute features for multiple patients at once.",
)
async def batch_compute(body: BatchComputeRequest) -> BatchComputeResponse:
    """Compute features for a batch of patients."""
    service = get_feature_store_service()
    return service.batch_compute(body.patient_ids, body.feature_names)


@router.post(
    "/features/compute/{patient_id}",
    response_model=FeatureVectorResponse,
    summary="Compute features for patient",
    description="Compute all or specified features for a single patient.",
)
async def compute_features(
    patient_id: str,
    feature_names: list[str] | None = Query(
        None, description="Specific features to compute; omit for all"
    ),
) -> FeatureVectorResponse:
    """Compute feature vector for a single patient."""
    service = get_feature_store_service()
    return service.compute_features(patient_id, feature_names)


# ============================================================================
# Feature Definitions — item endpoints (path param {name} — MUST be last)
# ============================================================================


@router.get(
    "/features/{name}",
    response_model=FeatureDefinitionResponse,
    summary="Get feature detail",
    description="Return the full definition for a specific feature by name.",
)
async def get_feature(name: str) -> FeatureDefinitionResponse:
    """Get a single feature definition by name."""
    service = get_feature_store_service()
    feature = service.get_feature(name)
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    return feature


@router.put(
    "/features/{name}",
    response_model=FeatureDefinitionResponse,
    summary="Update feature definition",
    description="Update fields of an existing feature definition.",
)
async def update_feature(
    name: str,
    body: FeatureDefinitionUpdate,
) -> FeatureDefinitionResponse:
    """Update a feature definition."""
    service = get_feature_store_service()
    result = service.update_feature(
        name,
        description=body.description,
        data_type=body.data_type,
        domain=body.domain,
        computation_logic=body.computation_logic,
        freshness_requirements=body.freshness_requirements,
        source_tables=body.source_tables,
        tags=body.tags,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    return result


@router.get(
    "/features/{name}/versions",
    response_model=FeatureVersionHistory,
    summary="Get feature version history",
    description="Return the version history for a specific feature.",
)
async def get_feature_versions(name: str) -> FeatureVersionHistory:
    """Get version history for a feature."""
    service = get_feature_store_service()
    result = service.get_feature_versions(name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    return result
