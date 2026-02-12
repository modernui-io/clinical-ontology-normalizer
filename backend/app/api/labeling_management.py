"""Labeling Management (LABEL-MGMT) API endpoints.

Provides comprehensive drug labeling lifecycle management: label content sections,
labeling negotiations with health authorities, label artwork management, labeling
change control, country-specific labeling requirements, and labeling metrics.

Endpoints:
    GET    /labeling-management/labels                              - List label content
    GET    /labeling-management/labels/{label_id}                   - Get single label
    POST   /labeling-management/labels                              - Create label
    PUT    /labeling-management/labels/{label_id}                   - Update label
    DELETE /labeling-management/labels/{label_id}                   - Delete label
    GET    /labeling-management/negotiations                        - List negotiations
    GET    /labeling-management/negotiations/{negotiation_id}       - Get single negotiation
    POST   /labeling-management/negotiations                        - Create negotiation
    PUT    /labeling-management/negotiations/{negotiation_id}       - Update negotiation
    DELETE /labeling-management/negotiations/{negotiation_id}       - Delete negotiation
    GET    /labeling-management/artworks                            - List artworks
    GET    /labeling-management/artworks/{artwork_id}               - Get single artwork
    POST   /labeling-management/artworks                            - Create artwork
    PUT    /labeling-management/artworks/{artwork_id}               - Update artwork
    DELETE /labeling-management/artworks/{artwork_id}               - Delete artwork
    GET    /labeling-management/changes                             - List changes
    GET    /labeling-management/changes/{change_id}                 - Get single change
    POST   /labeling-management/changes                             - Create change
    PUT    /labeling-management/changes/{change_id}                 - Update change
    DELETE /labeling-management/changes/{change_id}                 - Delete change
    GET    /labeling-management/country-labels                      - List country labels
    GET    /labeling-management/country-labels/{country_label_id}   - Get single country label
    POST   /labeling-management/country-labels                      - Create country label
    PUT    /labeling-management/country-labels/{country_label_id}   - Update country label
    DELETE /labeling-management/country-labels/{country_label_id}   - Delete country label
    GET    /labeling-management/metrics                             - Labeling metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.labeling_management import (
    ArtworkStatus,
    ChangeCategory,
    CountryLabel,
    CountryLabelCreate,
    CountryLabelListResponse,
    CountryLabelUpdate,
    LabelArtwork,
    LabelArtworkCreate,
    LabelArtworkListResponse,
    LabelArtworkUpdate,
    LabelChange,
    LabelChangeCreate,
    LabelChangeListResponse,
    LabelChangeUpdate,
    LabelContent,
    LabelContentCreate,
    LabelContentListResponse,
    LabelContentUpdate,
    LabelingMetrics,
    LabelNegotiation,
    LabelNegotiationCreate,
    LabelNegotiationListResponse,
    LabelNegotiationUpdate,
    LabelSection,
    LabelStatus,
    NegotiationStatus,
)
from app.services.labeling_management_service import get_labeling_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/labeling-management",
    tags=["Labeling Management"],
)


# ---------------------------------------------------------------------------
# Label Content Management
# ---------------------------------------------------------------------------


@router.get(
    "/labels",
    response_model=LabelContentListResponse,
    summary="List label content",
    description="Retrieve label content records with optional filtering by trial, status, and section.",
)
async def list_labels(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[LabelStatus] = Query(None, description="Filter by label status"),
    section: Optional[LabelSection] = Query(None, description="Filter by label section"),
) -> LabelContentListResponse:
    svc = get_labeling_management_service()
    items = svc.list_labels(trial_id=trial_id, status=status, section=section)
    return LabelContentListResponse(items=items, total=len(items))


@router.get(
    "/labels/{label_id}",
    response_model=LabelContent,
    summary="Get a label content record",
)
async def get_label(label_id: str) -> LabelContent:
    svc = get_labeling_management_service()
    label = svc.get_label(label_id)
    if label is None:
        raise HTTPException(status_code=404, detail=f"Label '{label_id}' not found")
    return label


@router.post(
    "/labels",
    response_model=LabelContent,
    status_code=201,
    summary="Create a label content record",
)
async def create_label(payload: LabelContentCreate) -> LabelContent:
    svc = get_labeling_management_service()
    return svc.create_label(payload)


@router.put(
    "/labels/{label_id}",
    response_model=LabelContent,
    summary="Update a label content record",
)
async def update_label(label_id: str, payload: LabelContentUpdate) -> LabelContent:
    svc = get_labeling_management_service()
    updated = svc.update_label(label_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Label '{label_id}' not found")
    return updated


@router.delete(
    "/labels/{label_id}",
    status_code=204,
    summary="Delete a label content record",
)
async def delete_label(label_id: str) -> None:
    svc = get_labeling_management_service()
    deleted = svc.delete_label(label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Label '{label_id}' not found")


# ---------------------------------------------------------------------------
# Label Negotiation Management
# ---------------------------------------------------------------------------


@router.get(
    "/negotiations",
    response_model=LabelNegotiationListResponse,
    summary="List label negotiations",
    description="Retrieve label negotiations with optional filtering by trial, label, and status.",
)
async def list_negotiations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    label_id: Optional[str] = Query(None, description="Filter by label ID"),
    status: Optional[NegotiationStatus] = Query(None, description="Filter by negotiation status"),
) -> LabelNegotiationListResponse:
    svc = get_labeling_management_service()
    items = svc.list_negotiations(trial_id=trial_id, label_id=label_id, status=status)
    return LabelNegotiationListResponse(items=items, total=len(items))


@router.get(
    "/negotiations/{negotiation_id}",
    response_model=LabelNegotiation,
    summary="Get a label negotiation",
)
async def get_negotiation(negotiation_id: str) -> LabelNegotiation:
    svc = get_labeling_management_service()
    negotiation = svc.get_negotiation(negotiation_id)
    if negotiation is None:
        raise HTTPException(status_code=404, detail=f"Negotiation '{negotiation_id}' not found")
    return negotiation


@router.post(
    "/negotiations",
    response_model=LabelNegotiation,
    status_code=201,
    summary="Create a label negotiation",
)
async def create_negotiation(payload: LabelNegotiationCreate) -> LabelNegotiation:
    svc = get_labeling_management_service()
    return svc.create_negotiation(payload)


@router.put(
    "/negotiations/{negotiation_id}",
    response_model=LabelNegotiation,
    summary="Update a label negotiation",
)
async def update_negotiation(
    negotiation_id: str, payload: LabelNegotiationUpdate
) -> LabelNegotiation:
    svc = get_labeling_management_service()
    updated = svc.update_negotiation(negotiation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Negotiation '{negotiation_id}' not found")
    return updated


@router.delete(
    "/negotiations/{negotiation_id}",
    status_code=204,
    summary="Delete a label negotiation",
)
async def delete_negotiation(negotiation_id: str) -> None:
    svc = get_labeling_management_service()
    deleted = svc.delete_negotiation(negotiation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Negotiation '{negotiation_id}' not found")


# ---------------------------------------------------------------------------
# Label Artwork Management
# ---------------------------------------------------------------------------


@router.get(
    "/artworks",
    response_model=LabelArtworkListResponse,
    summary="List label artworks",
    description="Retrieve label artworks with optional filtering by label and status.",
)
async def list_artworks(
    label_id: Optional[str] = Query(None, description="Filter by label ID"),
    status: Optional[ArtworkStatus] = Query(None, description="Filter by artwork status"),
) -> LabelArtworkListResponse:
    svc = get_labeling_management_service()
    items = svc.list_artworks(label_id=label_id, status=status)
    return LabelArtworkListResponse(items=items, total=len(items))


@router.get(
    "/artworks/{artwork_id}",
    response_model=LabelArtwork,
    summary="Get a label artwork",
)
async def get_artwork(artwork_id: str) -> LabelArtwork:
    svc = get_labeling_management_service()
    artwork = svc.get_artwork(artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found")
    return artwork


@router.post(
    "/artworks",
    response_model=LabelArtwork,
    status_code=201,
    summary="Create a label artwork",
)
async def create_artwork(payload: LabelArtworkCreate) -> LabelArtwork:
    svc = get_labeling_management_service()
    return svc.create_artwork(payload)


@router.put(
    "/artworks/{artwork_id}",
    response_model=LabelArtwork,
    summary="Update a label artwork",
)
async def update_artwork(
    artwork_id: str, payload: LabelArtworkUpdate
) -> LabelArtwork:
    svc = get_labeling_management_service()
    updated = svc.update_artwork(artwork_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found")
    return updated


@router.delete(
    "/artworks/{artwork_id}",
    status_code=204,
    summary="Delete a label artwork",
)
async def delete_artwork(artwork_id: str) -> None:
    svc = get_labeling_management_service()
    deleted = svc.delete_artwork(artwork_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found")


# ---------------------------------------------------------------------------
# Label Change Management
# ---------------------------------------------------------------------------


@router.get(
    "/changes",
    response_model=LabelChangeListResponse,
    summary="List label changes",
    description="Retrieve label changes with optional filtering by trial, label, and category.",
)
async def list_changes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    label_id: Optional[str] = Query(None, description="Filter by label ID"),
    change_category: Optional[ChangeCategory] = Query(None, description="Filter by change category"),
) -> LabelChangeListResponse:
    svc = get_labeling_management_service()
    items = svc.list_changes(trial_id=trial_id, label_id=label_id, change_category=change_category)
    return LabelChangeListResponse(items=items, total=len(items))


@router.get(
    "/changes/{change_id}",
    response_model=LabelChange,
    summary="Get a label change",
)
async def get_change(change_id: str) -> LabelChange:
    svc = get_labeling_management_service()
    change = svc.get_change(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail=f"Change '{change_id}' not found")
    return change


@router.post(
    "/changes",
    response_model=LabelChange,
    status_code=201,
    summary="Create a label change",
)
async def create_change(payload: LabelChangeCreate) -> LabelChange:
    svc = get_labeling_management_service()
    return svc.create_change(payload)


@router.put(
    "/changes/{change_id}",
    response_model=LabelChange,
    summary="Update a label change",
)
async def update_change(
    change_id: str, payload: LabelChangeUpdate
) -> LabelChange:
    svc = get_labeling_management_service()
    updated = svc.update_change(change_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Change '{change_id}' not found")
    return updated


@router.delete(
    "/changes/{change_id}",
    status_code=204,
    summary="Delete a label change",
)
async def delete_change(change_id: str) -> None:
    svc = get_labeling_management_service()
    deleted = svc.delete_change(change_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Change '{change_id}' not found")


# ---------------------------------------------------------------------------
# Country Label Management
# ---------------------------------------------------------------------------


@router.get(
    "/country-labels",
    response_model=CountryLabelListResponse,
    summary="List country labels",
    description="Retrieve country labels with optional filtering by label and country.",
)
async def list_country_labels(
    label_id: Optional[str] = Query(None, description="Filter by label ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
) -> CountryLabelListResponse:
    svc = get_labeling_management_service()
    items = svc.list_country_labels(label_id=label_id, country=country)
    return CountryLabelListResponse(items=items, total=len(items))


@router.get(
    "/country-labels/{country_label_id}",
    response_model=CountryLabel,
    summary="Get a country label",
)
async def get_country_label(country_label_id: str) -> CountryLabel:
    svc = get_labeling_management_service()
    country_label = svc.get_country_label(country_label_id)
    if country_label is None:
        raise HTTPException(status_code=404, detail=f"Country label '{country_label_id}' not found")
    return country_label


@router.post(
    "/country-labels",
    response_model=CountryLabel,
    status_code=201,
    summary="Create a country label",
)
async def create_country_label(payload: CountryLabelCreate) -> CountryLabel:
    svc = get_labeling_management_service()
    return svc.create_country_label(payload)


@router.put(
    "/country-labels/{country_label_id}",
    response_model=CountryLabel,
    summary="Update a country label",
)
async def update_country_label(
    country_label_id: str, payload: CountryLabelUpdate
) -> CountryLabel:
    svc = get_labeling_management_service()
    updated = svc.update_country_label(country_label_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Country label '{country_label_id}' not found")
    return updated


@router.delete(
    "/country-labels/{country_label_id}",
    status_code=204,
    summary="Delete a country label",
)
async def delete_country_label(country_label_id: str) -> None:
    svc = get_labeling_management_service()
    deleted = svc.delete_country_label(country_label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Country label '{country_label_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=LabelingMetrics,
    summary="Get labeling management metrics",
    description="Retrieve aggregated labeling metrics with optional trial filtering.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> LabelingMetrics:
    svc = get_labeling_management_service()
    return svc.get_metrics(trial_id=trial_id)
