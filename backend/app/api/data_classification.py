"""Data Classification API endpoints.

CLO-3: Data Classification Policy and Handling Procedures for the clinical
trial patient recruitment platform.

Endpoints:
    GET  /governance/classification/assets          - List all data assets
    GET  /governance/classification/assets/{id}     - Asset detail
    POST /governance/classification/assets          - Register new data asset
    PUT  /governance/classification/assets/{id}     - Update classification
    GET  /governance/classification/levels          - Classification level definitions
    GET  /governance/classification/handling-rules  - Handling rules per level
    GET  /governance/classification/overdue-reviews - Assets needing review
    POST /governance/classification/reclassify      - Request reclassification
    GET  /governance/classification/summary         - Classification summary stats
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.data_classification import (
    ClassificationLevel,
    ClassificationLevelDefinition,
    ClassificationSummary,
    DataAssetCreate,
    DataAssetResponse,
    DataAssetUpdate,
    DataRole,
    HandlingRules,
    ReclassificationRequest,
    ReclassificationResponse,
    ReclassificationStatus,
)
from app.services.data_classification_service import get_data_classification_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/governance/classification",
    tags=["Data Classification"],
)


# ---------------------------------------------------------------------------
# Classification Levels
# ---------------------------------------------------------------------------


@router.get(
    "/levels",
    response_model=list[ClassificationLevelDefinition],
    summary="List classification level definitions",
    description="Return all data classification levels with descriptions and examples.",
)
def list_classification_levels() -> list[ClassificationLevelDefinition]:
    """Return all classification level definitions ordered by severity."""
    svc = get_data_classification_service()
    return svc.get_classification_levels()


# ---------------------------------------------------------------------------
# Handling Rules
# ---------------------------------------------------------------------------


@router.get(
    "/handling-rules",
    response_model=list[HandlingRules],
    summary="List handling rules per classification level",
    description=(
        "Return the handling procedures (storage, access, transmission, retention, "
        "incident response, sharing) for each classification level."
    ),
)
def list_handling_rules(
    level: Optional[ClassificationLevel] = Query(
        default=None,
        description="Filter by classification level",
    ),
) -> list[HandlingRules]:
    """Return handling rules, optionally filtered by level."""
    svc = get_data_classification_service()
    return svc.get_handling_rules(level)


# ---------------------------------------------------------------------------
# Data Assets
# ---------------------------------------------------------------------------


@router.get(
    "/assets",
    response_model=list[DataAssetResponse],
    summary="List all data assets",
    description="Return all registered data assets with classification and handling details.",
)
def list_assets(
    classification_level: Optional[ClassificationLevel] = Query(
        default=None,
        description="Filter by classification level",
    ),
    tag: Optional[str] = Query(
        default=None,
        description="Filter by tag",
    ),
    owner: Optional[str] = Query(
        default=None,
        description="Filter by data owner",
    ),
) -> list[DataAssetResponse]:
    """List all data assets with optional filters."""
    svc = get_data_classification_service()
    return svc.list_assets(
        classification_level=classification_level,
        tag=tag,
        owner=owner,
    )


@router.get(
    "/assets/{asset_id}",
    response_model=DataAssetResponse,
    summary="Get data asset detail",
    description="Return a single data asset by ID including classification and handling rules.",
)
def get_asset(asset_id: str) -> DataAssetResponse:
    """Return a data asset by ID."""
    svc = get_data_classification_service()
    asset = svc.get_asset(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data asset not found: {asset_id}",
        )
    return asset


@router.post(
    "/assets",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new data asset",
    description="Register a new data asset in the classification inventory.",
)
def register_asset(create: DataAssetCreate) -> DataAssetResponse:
    """Register a new data asset."""
    svc = get_data_classification_service()
    return svc.register_asset(create)


@router.put(
    "/assets/{asset_id}",
    response_model=DataAssetResponse,
    summary="Update data asset",
    description="Update a data asset's classification, metadata, or handling details.",
)
def update_asset(asset_id: str, update: DataAssetUpdate) -> DataAssetResponse:
    """Update a data asset."""
    svc = get_data_classification_service()
    asset = svc.update_asset(asset_id, update)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data asset not found: {asset_id}",
        )
    return asset


# ---------------------------------------------------------------------------
# Overdue Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/overdue-reviews",
    response_model=list[DataAssetResponse],
    summary="List assets with overdue reviews",
    description="Return data assets that are overdue for classification review.",
)
def list_overdue_reviews() -> list[DataAssetResponse]:
    """Return all assets with overdue reviews."""
    svc = get_data_classification_service()
    return svc.get_overdue_reviews()


# ---------------------------------------------------------------------------
# Reclassification
# ---------------------------------------------------------------------------


@router.post(
    "/reclassify",
    response_model=ReclassificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request data reclassification",
    description="Submit a request to reclassify a data asset to a different level.",
)
def request_reclassification(request: ReclassificationRequest) -> ReclassificationResponse:
    """Submit a reclassification request."""
    svc = get_data_classification_service()
    try:
        return svc.request_reclassification(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=ClassificationSummary,
    summary="Classification summary statistics",
    description="Return aggregate statistics about the data classification inventory.",
)
def get_summary() -> ClassificationSummary:
    """Return classification summary statistics."""
    svc = get_data_classification_service()
    return svc.get_summary()
