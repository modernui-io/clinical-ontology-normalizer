"""Tissue Tracking Management API endpoints (TISSUE-TRK).

Provides comprehensive tissue specimen operations: tissue collection tracking,
FFPE block management, slide preparation, pathology review workflow, tissue
shipment tracking, and tissue tracking operational metrics.

Endpoints:
    GET    /tissue-tracking/specimens                          - List specimens
    GET    /tissue-tracking/specimens/{specimen_id}            - Get single specimen
    POST   /tissue-tracking/specimens                          - Create specimen
    PUT    /tissue-tracking/specimens/{specimen_id}            - Update specimen
    DELETE /tissue-tracking/specimens/{specimen_id}            - Delete specimen
    GET    /tissue-tracking/blocks                             - List FFPE blocks
    GET    /tissue-tracking/blocks/{block_id}                  - Get single block
    POST   /tissue-tracking/blocks                             - Create block
    PUT    /tissue-tracking/blocks/{block_id}                  - Update block
    DELETE /tissue-tracking/blocks/{block_id}                  - Delete block
    GET    /tissue-tracking/slides                             - List slides
    GET    /tissue-tracking/slides/{slide_id}                  - Get single slide
    POST   /tissue-tracking/slides                             - Create slide
    PUT    /tissue-tracking/slides/{slide_id}                  - Update slide
    DELETE /tissue-tracking/slides/{slide_id}                  - Delete slide
    GET    /tissue-tracking/reviews                            - List reviews
    GET    /tissue-tracking/reviews/{review_id}                - Get single review
    POST   /tissue-tracking/reviews                            - Create review
    PUT    /tissue-tracking/reviews/{review_id}                - Update review
    DELETE /tissue-tracking/reviews/{review_id}                - Delete review
    GET    /tissue-tracking/shipments                          - List shipments
    GET    /tissue-tracking/shipments/{shipment_id}            - Get single shipment
    POST   /tissue-tracking/shipments                          - Create shipment
    PUT    /tissue-tracking/shipments/{shipment_id}            - Update shipment
    DELETE /tissue-tracking/shipments/{shipment_id}            - Delete shipment
    GET    /tissue-tracking/metrics                            - Tissue tracking metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.tissue_tracking import (
    FFPEBlock,
    FFPEBlockCreate,
    FFPEBlockListResponse,
    FFPEBlockUpdate,
    PathologyResult,
    PathologyReview,
    PathologyReviewCreate,
    PathologyReviewListResponse,
    PathologyReviewUpdate,
    SlideStatus,
    SpecimenStatus,
    TissueShipment,
    TissueShipmentCreate,
    TissueShipmentListResponse,
    TissueShipmentUpdate,
    TissueSlide,
    TissueSlideCreate,
    TissueSlideListResponse,
    TissueSlideUpdate,
    TissueSpecimen,
    TissueSpecimenCreate,
    TissueSpecimenListResponse,
    TissueSpecimenUpdate,
    TissueTrackingMetrics,
    TissueType,
)
from app.services.tissue_tracking_service import get_tissue_tracking_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tissue-tracking",
    tags=["Tissue Tracking Management"],
)


# ---------------------------------------------------------------------------
# Specimen CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/specimens",
    response_model=TissueSpecimenListResponse,
    summary="List tissue specimens",
    description="Retrieve tissue specimens with optional filtering by trial, status, and tissue type.",
)
async def list_specimens(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SpecimenStatus] = Query(None, description="Filter by specimen status"),
    tissue_type: Optional[TissueType] = Query(None, description="Filter by tissue type"),
) -> TissueSpecimenListResponse:
    svc = get_tissue_tracking_service()
    items = svc.list_specimens(trial_id=trial_id, status=status, tissue_type=tissue_type)
    return TissueSpecimenListResponse(items=items, total=len(items))


@router.get(
    "/specimens/{specimen_id}",
    response_model=TissueSpecimen,
    summary="Get a tissue specimen",
)
async def get_specimen(specimen_id: str) -> TissueSpecimen:
    svc = get_tissue_tracking_service()
    specimen = svc.get_specimen(specimen_id)
    if specimen is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return specimen


@router.post(
    "/specimens",
    response_model=TissueSpecimen,
    status_code=201,
    summary="Create a tissue specimen",
)
async def create_specimen(payload: TissueSpecimenCreate) -> TissueSpecimen:
    svc = get_tissue_tracking_service()
    return svc.create_specimen(payload)


@router.put(
    "/specimens/{specimen_id}",
    response_model=TissueSpecimen,
    summary="Update a tissue specimen",
)
async def update_specimen(
    specimen_id: str, payload: TissueSpecimenUpdate
) -> TissueSpecimen:
    svc = get_tissue_tracking_service()
    updated = svc.update_specimen(specimen_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return updated


@router.delete(
    "/specimens/{specimen_id}",
    status_code=204,
    summary="Delete a tissue specimen",
)
async def delete_specimen(specimen_id: str) -> None:
    svc = get_tissue_tracking_service()
    deleted = svc.delete_specimen(specimen_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")


# ---------------------------------------------------------------------------
# FFPE Block CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/blocks",
    response_model=FFPEBlockListResponse,
    summary="List FFPE blocks",
    description="Retrieve FFPE blocks with optional filtering by specimen.",
)
async def list_blocks(
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
) -> FFPEBlockListResponse:
    svc = get_tissue_tracking_service()
    items = svc.list_blocks(specimen_id=specimen_id)
    return FFPEBlockListResponse(items=items, total=len(items))


@router.get(
    "/blocks/{block_id}",
    response_model=FFPEBlock,
    summary="Get an FFPE block",
)
async def get_block(block_id: str) -> FFPEBlock:
    svc = get_tissue_tracking_service()
    block = svc.get_block(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail=f"Block '{block_id}' not found")
    return block


@router.post(
    "/blocks",
    response_model=FFPEBlock,
    status_code=201,
    summary="Create an FFPE block",
)
async def create_block(payload: FFPEBlockCreate) -> FFPEBlock:
    svc = get_tissue_tracking_service()
    return svc.create_block(payload)


@router.put(
    "/blocks/{block_id}",
    response_model=FFPEBlock,
    summary="Update an FFPE block",
)
async def update_block(
    block_id: str, payload: FFPEBlockUpdate
) -> FFPEBlock:
    svc = get_tissue_tracking_service()
    updated = svc.update_block(block_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Block '{block_id}' not found")
    return updated


@router.delete(
    "/blocks/{block_id}",
    status_code=204,
    summary="Delete an FFPE block",
)
async def delete_block(block_id: str) -> None:
    svc = get_tissue_tracking_service()
    deleted = svc.delete_block(block_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Block '{block_id}' not found")


# ---------------------------------------------------------------------------
# Tissue Slide CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/slides",
    response_model=TissueSlideListResponse,
    summary="List tissue slides",
    description="Retrieve tissue slides with optional filtering by specimen, block, and status.",
)
async def list_slides(
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
    block_id: Optional[str] = Query(None, description="Filter by block ID"),
    status: Optional[SlideStatus] = Query(None, description="Filter by slide status"),
) -> TissueSlideListResponse:
    svc = get_tissue_tracking_service()
    items = svc.list_slides(specimen_id=specimen_id, block_id=block_id, status=status)
    return TissueSlideListResponse(items=items, total=len(items))


@router.get(
    "/slides/{slide_id}",
    response_model=TissueSlide,
    summary="Get a tissue slide",
)
async def get_slide(slide_id: str) -> TissueSlide:
    svc = get_tissue_tracking_service()
    slide = svc.get_slide(slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail=f"Slide '{slide_id}' not found")
    return slide


@router.post(
    "/slides",
    response_model=TissueSlide,
    status_code=201,
    summary="Create a tissue slide",
)
async def create_slide(payload: TissueSlideCreate) -> TissueSlide:
    svc = get_tissue_tracking_service()
    return svc.create_slide(payload)


@router.put(
    "/slides/{slide_id}",
    response_model=TissueSlide,
    summary="Update a tissue slide",
)
async def update_slide(
    slide_id: str, payload: TissueSlideUpdate
) -> TissueSlide:
    svc = get_tissue_tracking_service()
    updated = svc.update_slide(slide_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Slide '{slide_id}' not found")
    return updated


@router.delete(
    "/slides/{slide_id}",
    status_code=204,
    summary="Delete a tissue slide",
)
async def delete_slide(slide_id: str) -> None:
    svc = get_tissue_tracking_service()
    deleted = svc.delete_slide(slide_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Slide '{slide_id}' not found")


# ---------------------------------------------------------------------------
# Pathology Review CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/reviews",
    response_model=PathologyReviewListResponse,
    summary="List pathology reviews",
    description="Retrieve pathology reviews with optional filtering by trial, specimen, and result.",
)
async def list_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    specimen_id: Optional[str] = Query(None, description="Filter by specimen ID"),
    result: Optional[PathologyResult] = Query(None, description="Filter by pathology result"),
) -> PathologyReviewListResponse:
    svc = get_tissue_tracking_service()
    items = svc.list_reviews(trial_id=trial_id, specimen_id=specimen_id, result=result)
    return PathologyReviewListResponse(items=items, total=len(items))


@router.get(
    "/reviews/{review_id}",
    response_model=PathologyReview,
    summary="Get a pathology review",
)
async def get_review(review_id: str) -> PathologyReview:
    svc = get_tissue_tracking_service()
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return review


@router.post(
    "/reviews",
    response_model=PathologyReview,
    status_code=201,
    summary="Create a pathology review",
)
async def create_review(payload: PathologyReviewCreate) -> PathologyReview:
    svc = get_tissue_tracking_service()
    return svc.create_review(payload)


@router.put(
    "/reviews/{review_id}",
    response_model=PathologyReview,
    summary="Update a pathology review",
)
async def update_review(
    review_id: str, payload: PathologyReviewUpdate
) -> PathologyReview:
    svc = get_tissue_tracking_service()
    updated = svc.update_review(review_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return updated


@router.delete(
    "/reviews/{review_id}",
    status_code=204,
    summary="Delete a pathology review",
)
async def delete_review(review_id: str) -> None:
    svc = get_tissue_tracking_service()
    deleted = svc.delete_review(review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")


# ---------------------------------------------------------------------------
# Tissue Shipment CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/shipments",
    response_model=TissueShipmentListResponse,
    summary="List tissue shipments",
    description="Retrieve tissue shipments with optional filtering by trial and status.",
)
async def list_shipments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[str] = Query(None, description="Filter by shipment status"),
) -> TissueShipmentListResponse:
    svc = get_tissue_tracking_service()
    items = svc.list_shipments(trial_id=trial_id, status=status)
    return TissueShipmentListResponse(items=items, total=len(items))


@router.get(
    "/shipments/{shipment_id}",
    response_model=TissueShipment,
    summary="Get a tissue shipment",
)
async def get_shipment(shipment_id: str) -> TissueShipment:
    svc = get_tissue_tracking_service()
    shipment = svc.get_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return shipment


@router.post(
    "/shipments",
    response_model=TissueShipment,
    status_code=201,
    summary="Create a tissue shipment",
)
async def create_shipment(payload: TissueShipmentCreate) -> TissueShipment:
    svc = get_tissue_tracking_service()
    return svc.create_shipment(payload)


@router.put(
    "/shipments/{shipment_id}",
    response_model=TissueShipment,
    summary="Update a tissue shipment",
)
async def update_shipment(
    shipment_id: str, payload: TissueShipmentUpdate
) -> TissueShipment:
    svc = get_tissue_tracking_service()
    updated = svc.update_shipment(shipment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return updated


@router.delete(
    "/shipments/{shipment_id}",
    status_code=204,
    summary="Delete a tissue shipment",
)
async def delete_shipment(shipment_id: str) -> None:
    svc = get_tissue_tracking_service()
    deleted = svc.delete_shipment(shipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=TissueTrackingMetrics,
    summary="Get tissue tracking metrics",
    description="Aggregated tissue tracking metrics including specimen counts by type/status/"
                "preservation, block and slide totals, review results, and shipment excursions.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> TissueTrackingMetrics:
    svc = get_tissue_tracking_service()
    return svc.get_metrics(trial_id=trial_id)
