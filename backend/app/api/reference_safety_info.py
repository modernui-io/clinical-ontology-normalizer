"""Reference Safety Information Management (RSI-MGT) API endpoints.

Manages reference safety information: safety document lifecycle, Investigator's
Brochure section management, safety updates and labeling changes, safety
narrative authoring, RSI line item tracking, and operational metrics.

Endpoints:
    GET    /reference-safety-info/documents                    - List safety documents
    GET    /reference-safety-info/documents/{document_id}      - Get single document
    POST   /reference-safety-info/documents                    - Create document
    PUT    /reference-safety-info/documents/{document_id}      - Update document
    DELETE /reference-safety-info/documents/{document_id}      - Delete document
    GET    /reference-safety-info/sections                     - List IB sections
    GET    /reference-safety-info/sections/{section_id}        - Get single section
    POST   /reference-safety-info/sections                     - Create section
    PUT    /reference-safety-info/sections/{section_id}        - Update section
    DELETE /reference-safety-info/sections/{section_id}        - Delete section
    GET    /reference-safety-info/updates                      - List safety updates
    GET    /reference-safety-info/updates/{update_id}          - Get single update
    POST   /reference-safety-info/updates                      - Create update
    PUT    /reference-safety-info/updates/{update_id}          - Update safety update
    DELETE /reference-safety-info/updates/{update_id}          - Delete update
    GET    /reference-safety-info/narratives                   - List narratives
    GET    /reference-safety-info/narratives/{narrative_id}    - Get single narrative
    POST   /reference-safety-info/narratives                   - Create narrative
    PUT    /reference-safety-info/narratives/{narrative_id}    - Update narrative
    DELETE /reference-safety-info/narratives/{narrative_id}    - Delete narrative
    GET    /reference-safety-info/line-items                   - List RSI line items
    GET    /reference-safety-info/line-items/{line_item_id}    - Get single line item
    POST   /reference-safety-info/line-items                   - Create line item
    PUT    /reference-safety-info/line-items/{line_item_id}    - Update line item
    DELETE /reference-safety-info/line-items/{line_item_id}    - Delete line item
    GET    /reference-safety-info/metrics                      - RSI metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.reference_safety_info import (
    DocumentCategory,
    IBSection,
    IBSectionCreate,
    IBSectionListResponse,
    IBSectionUpdate,
    NarrativeType,
    RSILineItem,
    RSILineItemCreate,
    RSILineItemListResponse,
    RSILineItemUpdate,
    RSIMetrics,
    ReviewStatus,
    SafetyDocument,
    SafetyDocumentCreate,
    SafetyDocumentListResponse,
    SafetyDocumentUpdate,
    SafetyNarrative,
    SafetyNarrativeCreate,
    SafetyNarrativeListResponse,
    SafetyNarrativeUpdate,
    SafetyUpdate,
    SafetyUpdateCreate,
    SafetyUpdateListResponse,
    SafetyUpdateModify,
    SectionType,
    UpdateType,
)
from app.services.reference_safety_info_service import get_reference_safety_info_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reference-safety-info",
    tags=["Reference Safety Information"],
)


# ---------------------------------------------------------------------------
# Safety Document Management
# ---------------------------------------------------------------------------


@router.get(
    "/documents",
    response_model=SafetyDocumentListResponse,
    summary="List safety documents",
    description="Retrieve safety documents with optional filtering by trial, product, category, and status.",
)
async def list_safety_documents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
    category: Optional[DocumentCategory] = Query(None, description="Filter by document category"),
    status: Optional[ReviewStatus] = Query(None, description="Filter by review status"),
) -> SafetyDocumentListResponse:
    svc = get_reference_safety_info_service()
    items = svc.list_safety_documents(
        trial_id=trial_id, product_name=product_name, category=category, status=status,
    )
    return SafetyDocumentListResponse(items=items, total=len(items))


@router.get(
    "/documents/{document_id}",
    response_model=SafetyDocument,
    summary="Get a safety document",
)
async def get_safety_document(document_id: str) -> SafetyDocument:
    svc = get_reference_safety_info_service()
    document = svc.get_safety_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return document


@router.post(
    "/documents",
    response_model=SafetyDocument,
    status_code=201,
    summary="Create a safety document",
)
async def create_safety_document(payload: SafetyDocumentCreate) -> SafetyDocument:
    svc = get_reference_safety_info_service()
    return svc.create_safety_document(payload)


@router.put(
    "/documents/{document_id}",
    response_model=SafetyDocument,
    summary="Update a safety document",
)
async def update_safety_document(
    document_id: str, payload: SafetyDocumentUpdate
) -> SafetyDocument:
    svc = get_reference_safety_info_service()
    updated = svc.update_safety_document(document_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return updated


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete a safety document",
)
async def delete_safety_document(document_id: str) -> None:
    svc = get_reference_safety_info_service()
    deleted = svc.delete_safety_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


# ---------------------------------------------------------------------------
# IB Section Management
# ---------------------------------------------------------------------------


@router.get(
    "/sections",
    response_model=IBSectionListResponse,
    summary="List IB sections",
    description="Retrieve Investigator's Brochure sections with optional filtering by document and section type.",
)
async def list_ib_sections(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    section_type: Optional[SectionType] = Query(None, description="Filter by section type"),
) -> IBSectionListResponse:
    svc = get_reference_safety_info_service()
    items = svc.list_ib_sections(document_id=document_id, section_type=section_type)
    return IBSectionListResponse(items=items, total=len(items))


@router.get(
    "/sections/{section_id}",
    response_model=IBSection,
    summary="Get an IB section",
)
async def get_ib_section(section_id: str) -> IBSection:
    svc = get_reference_safety_info_service()
    section = svc.get_ib_section(section_id)
    if section is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
    return section


@router.post(
    "/sections",
    response_model=IBSection,
    status_code=201,
    summary="Create an IB section",
)
async def create_ib_section(payload: IBSectionCreate) -> IBSection:
    svc = get_reference_safety_info_service()
    return svc.create_ib_section(payload)


@router.put(
    "/sections/{section_id}",
    response_model=IBSection,
    summary="Update an IB section",
)
async def update_ib_section(
    section_id: str, payload: IBSectionUpdate
) -> IBSection:
    svc = get_reference_safety_info_service()
    updated = svc.update_ib_section(section_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
    return updated


@router.delete(
    "/sections/{section_id}",
    status_code=204,
    summary="Delete an IB section",
)
async def delete_ib_section(section_id: str) -> None:
    svc = get_reference_safety_info_service()
    deleted = svc.delete_ib_section(section_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")


# ---------------------------------------------------------------------------
# Safety Update Management
# ---------------------------------------------------------------------------


@router.get(
    "/updates",
    response_model=SafetyUpdateListResponse,
    summary="List safety updates",
    description="Retrieve safety updates with optional filtering by document, trial, product, and update type.",
)
async def list_safety_updates(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
    update_type: Optional[UpdateType] = Query(None, description="Filter by update type"),
) -> SafetyUpdateListResponse:
    svc = get_reference_safety_info_service()
    items = svc.list_safety_updates(
        document_id=document_id, trial_id=trial_id,
        product_name=product_name, update_type=update_type,
    )
    return SafetyUpdateListResponse(items=items, total=len(items))


@router.get(
    "/updates/{update_id}",
    response_model=SafetyUpdate,
    summary="Get a safety update",
)
async def get_safety_update(update_id: str) -> SafetyUpdate:
    svc = get_reference_safety_info_service()
    update = svc.get_safety_update(update_id)
    if update is None:
        raise HTTPException(status_code=404, detail=f"Update '{update_id}' not found")
    return update


@router.post(
    "/updates",
    response_model=SafetyUpdate,
    status_code=201,
    summary="Create a safety update",
)
async def create_safety_update(payload: SafetyUpdateCreate) -> SafetyUpdate:
    svc = get_reference_safety_info_service()
    return svc.create_safety_update(payload)


@router.put(
    "/updates/{update_id}",
    response_model=SafetyUpdate,
    summary="Update a safety update",
)
async def update_safety_update(
    update_id: str, payload: SafetyUpdateModify
) -> SafetyUpdate:
    svc = get_reference_safety_info_service()
    updated = svc.update_safety_update(update_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Update '{update_id}' not found")
    return updated


@router.delete(
    "/updates/{update_id}",
    status_code=204,
    summary="Delete a safety update",
)
async def delete_safety_update(update_id: str) -> None:
    svc = get_reference_safety_info_service()
    deleted = svc.delete_safety_update(update_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Update '{update_id}' not found")


# ---------------------------------------------------------------------------
# Safety Narrative Management
# ---------------------------------------------------------------------------


@router.get(
    "/narratives",
    response_model=SafetyNarrativeListResponse,
    summary="List safety narratives",
    description="Retrieve safety narratives with optional filtering by trial, narrative type, and status.",
)
async def list_safety_narratives(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    narrative_type: Optional[NarrativeType] = Query(None, description="Filter by narrative type"),
    status: Optional[ReviewStatus] = Query(None, description="Filter by review status"),
) -> SafetyNarrativeListResponse:
    svc = get_reference_safety_info_service()
    items = svc.list_safety_narratives(
        trial_id=trial_id, narrative_type=narrative_type, status=status,
    )
    return SafetyNarrativeListResponse(items=items, total=len(items))


@router.get(
    "/narratives/{narrative_id}",
    response_model=SafetyNarrative,
    summary="Get a safety narrative",
)
async def get_safety_narrative(narrative_id: str) -> SafetyNarrative:
    svc = get_reference_safety_info_service()
    narrative = svc.get_safety_narrative(narrative_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail=f"Narrative '{narrative_id}' not found")
    return narrative


@router.post(
    "/narratives",
    response_model=SafetyNarrative,
    status_code=201,
    summary="Create a safety narrative",
)
async def create_safety_narrative(payload: SafetyNarrativeCreate) -> SafetyNarrative:
    svc = get_reference_safety_info_service()
    return svc.create_safety_narrative(payload)


@router.put(
    "/narratives/{narrative_id}",
    response_model=SafetyNarrative,
    summary="Update a safety narrative",
)
async def update_safety_narrative(
    narrative_id: str, payload: SafetyNarrativeUpdate
) -> SafetyNarrative:
    svc = get_reference_safety_info_service()
    updated = svc.update_safety_narrative(narrative_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Narrative '{narrative_id}' not found")
    return updated


@router.delete(
    "/narratives/{narrative_id}",
    status_code=204,
    summary="Delete a safety narrative",
)
async def delete_safety_narrative(narrative_id: str) -> None:
    svc = get_reference_safety_info_service()
    deleted = svc.delete_safety_narrative(narrative_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Narrative '{narrative_id}' not found")


# ---------------------------------------------------------------------------
# RSI Line Item Management
# ---------------------------------------------------------------------------


@router.get(
    "/line-items",
    response_model=RSILineItemListResponse,
    summary="List RSI line items",
    description="Retrieve RSI line items with optional filtering by document and product.",
)
async def list_rsi_line_items(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> RSILineItemListResponse:
    svc = get_reference_safety_info_service()
    items = svc.list_rsi_line_items(document_id=document_id, product_name=product_name)
    return RSILineItemListResponse(items=items, total=len(items))


@router.get(
    "/line-items/{line_item_id}",
    response_model=RSILineItem,
    summary="Get an RSI line item",
)
async def get_rsi_line_item(line_item_id: str) -> RSILineItem:
    svc = get_reference_safety_info_service()
    line_item = svc.get_rsi_line_item(line_item_id)
    if line_item is None:
        raise HTTPException(status_code=404, detail=f"Line item '{line_item_id}' not found")
    return line_item


@router.post(
    "/line-items",
    response_model=RSILineItem,
    status_code=201,
    summary="Create an RSI line item",
)
async def create_rsi_line_item(payload: RSILineItemCreate) -> RSILineItem:
    svc = get_reference_safety_info_service()
    return svc.create_rsi_line_item(payload)


@router.put(
    "/line-items/{line_item_id}",
    response_model=RSILineItem,
    summary="Update an RSI line item",
)
async def update_rsi_line_item(
    line_item_id: str, payload: RSILineItemUpdate
) -> RSILineItem:
    svc = get_reference_safety_info_service()
    updated = svc.update_rsi_line_item(line_item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Line item '{line_item_id}' not found")
    return updated


@router.delete(
    "/line-items/{line_item_id}",
    status_code=204,
    summary="Delete an RSI line item",
)
async def delete_rsi_line_item(line_item_id: str) -> None:
    svc = get_reference_safety_info_service()
    deleted = svc.delete_rsi_line_item(line_item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Line item '{line_item_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RSIMetrics,
    summary="Get RSI metrics",
    description="Aggregated reference safety information metrics including document counts, "
                "update breakdowns, narrative status, and line item statistics.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> RSIMetrics:
    svc = get_reference_safety_info_service()
    return svc.get_metrics(trial_id=trial_id)
