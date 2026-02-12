"""Product Licensure & Market Authorization API endpoints.

Tracks IND/NDA/BLA application lifecycles, country-by-country approval status,
label management, post-approval changes, and market access timelines for
pharmaceutical products across global regulatory authorities.

Endpoints:
    GET    /product-licensure/applications                               - List applications
    GET    /product-licensure/applications/{app_id}                      - Get single application
    POST   /product-licensure/applications                               - Create application
    PUT    /product-licensure/applications/{app_id}                      - Update application
    DELETE /product-licensure/applications/{app_id}                      - Delete application
    POST   /product-licensure/applications/{app_id}/submit               - Submit application
    POST   /product-licensure/applications/{app_id}/approve              - Record approval
    GET    /product-licensure/country-authorizations                     - List country authorizations
    GET    /product-licensure/country-authorizations/{ca_id}             - Get single authorization
    POST   /product-licensure/country-authorizations                     - Create authorization
    PUT    /product-licensure/country-authorizations/{ca_id}             - Update authorization
    DELETE /product-licensure/country-authorizations/{ca_id}             - Delete authorization
    GET    /product-licensure/labels                                     - List product labels
    GET    /product-licensure/labels/{label_id}                          - Get single label
    POST   /product-licensure/labels                                     - Create label
    PUT    /product-licensure/labels/{label_id}                          - Update label
    DELETE /product-licensure/labels/{label_id}                          - Delete label
    GET    /product-licensure/post-approval-changes                      - List changes
    GET    /product-licensure/post-approval-changes/{pac_id}             - Get single change
    POST   /product-licensure/post-approval-changes                      - File a change
    PUT    /product-licensure/post-approval-changes/{pac_id}             - Update change
    DELETE /product-licensure/post-approval-changes/{pac_id}             - Delete change
    GET    /product-licensure/timelines                                  - List milestones
    GET    /product-licensure/timelines/{tl_id}                          - Get single milestone
    POST   /product-licensure/timelines                                  - Create milestone
    PUT    /product-licensure/timelines/{tl_id}                          - Update milestone
    DELETE /product-licensure/timelines/{tl_id}                          - Delete milestone
    GET    /product-licensure/applications/{app_id}/country-status       - Product status by country
    GET    /product-licensure/metrics                                    - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.product_licensure import (
    ApplicationApproval,
    ApplicationStatus,
    ApplicationSubmit,
    ApplicationType,
    ChangeType,
    CountryAuthorization,
    CountryAuthorizationCreate,
    CountryAuthorizationListResponse,
    CountryAuthorizationUpdate,
    LabelStatus,
    LicensureMetrics,
    MarketAccessTimeline,
    MarketAccessTimelineCreate,
    MarketAccessTimelineListResponse,
    MarketAccessTimelineUpdate,
    MarketStatus,
    MilestoneStatus,
    PostApprovalChange,
    PostApprovalChangeCreate,
    PostApprovalChangeListResponse,
    PostApprovalChangeUpdate,
    ProductCountryStatusListResponse,
    ProductLabel,
    ProductLabelCreate,
    ProductLabelListResponse,
    ProductLabelUpdate,
    RegulatoryApplication,
    RegulatoryApplicationCreate,
    RegulatoryApplicationListResponse,
    RegulatoryApplicationUpdate,
)
from app.services.product_licensure_service import get_product_licensure_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/product-licensure",
    tags=["Product Licensure"],
)


# ---------------------------------------------------------------------------
# Regulatory Applications
# ---------------------------------------------------------------------------


@router.get(
    "/applications",
    response_model=RegulatoryApplicationListResponse,
    summary="List regulatory applications",
    description="Retrieve regulatory applications with optional filtering by type, status, product name, and country.",
)
async def list_applications(
    application_type: Optional[ApplicationType] = Query(None, description="Filter by application type"),
    status: Optional[ApplicationStatus] = Query(None, description="Filter by status"),
    product_name: Optional[str] = Query(None, description="Filter by product name (partial match)"),
    country: Optional[str] = Query(None, description="Filter by country code"),
) -> RegulatoryApplicationListResponse:
    svc = get_product_licensure_service()
    items = svc.list_applications(
        application_type=application_type,
        status=status,
        product_name=product_name,
        country=country,
    )
    return RegulatoryApplicationListResponse(items=items, total=len(items))


@router.get(
    "/applications/{app_id}",
    response_model=RegulatoryApplication,
    summary="Get a regulatory application",
)
async def get_application(app_id: str) -> RegulatoryApplication:
    svc = get_product_licensure_service()
    app = svc.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found")
    return app


@router.post(
    "/applications",
    response_model=RegulatoryApplication,
    status_code=201,
    summary="Create a regulatory application",
)
async def create_application(payload: RegulatoryApplicationCreate) -> RegulatoryApplication:
    svc = get_product_licensure_service()
    return svc.create_application(payload)


@router.put(
    "/applications/{app_id}",
    response_model=RegulatoryApplication,
    summary="Update a regulatory application",
)
async def update_application(
    app_id: str, payload: RegulatoryApplicationUpdate
) -> RegulatoryApplication:
    svc = get_product_licensure_service()
    updated = svc.update_application(app_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found")
    return updated


@router.delete(
    "/applications/{app_id}",
    status_code=204,
    summary="Delete a regulatory application",
)
async def delete_application(app_id: str) -> None:
    svc = get_product_licensure_service()
    deleted = svc.delete_application(app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found")


@router.post(
    "/applications/{app_id}/submit",
    response_model=RegulatoryApplication,
    summary="Submit a regulatory application",
    description="Formally submit a pre-submission application to the regulatory authority.",
)
async def submit_application(
    app_id: str, payload: ApplicationSubmit
) -> RegulatoryApplication:
    svc = get_product_licensure_service()
    try:
        result = svc.submit_application(app_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found")
    return result


@router.post(
    "/applications/{app_id}/approve",
    response_model=RegulatoryApplication,
    summary="Record application approval",
    description="Record a regulatory authority's approval of an application.",
)
async def record_approval(
    app_id: str, payload: ApplicationApproval
) -> RegulatoryApplication:
    svc = get_product_licensure_service()
    try:
        result = svc.record_approval(app_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Country Authorizations
# ---------------------------------------------------------------------------


@router.get(
    "/country-authorizations",
    response_model=CountryAuthorizationListResponse,
    summary="List country authorizations",
    description="Retrieve country-level market authorizations with optional filtering.",
)
async def list_country_authorizations(
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    market_status: Optional[MarketStatus] = Query(None, description="Filter by market status"),
) -> CountryAuthorizationListResponse:
    svc = get_product_licensure_service()
    items = svc.list_country_authorizations(
        application_id=application_id,
        country=country,
        market_status=market_status,
    )
    return CountryAuthorizationListResponse(items=items, total=len(items))


@router.get(
    "/country-authorizations/{ca_id}",
    response_model=CountryAuthorization,
    summary="Get a country authorization",
)
async def get_country_authorization(ca_id: str) -> CountryAuthorization:
    svc = get_product_licensure_service()
    ca = svc.get_country_authorization(ca_id)
    if ca is None:
        raise HTTPException(
            status_code=404, detail=f"Country authorization '{ca_id}' not found"
        )
    return ca


@router.post(
    "/country-authorizations",
    response_model=CountryAuthorization,
    status_code=201,
    summary="Create a country authorization",
)
async def create_country_authorization(
    payload: CountryAuthorizationCreate,
) -> CountryAuthorization:
    svc = get_product_licensure_service()
    try:
        return svc.create_country_authorization(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/country-authorizations/{ca_id}",
    response_model=CountryAuthorization,
    summary="Update a country authorization",
)
async def update_country_authorization(
    ca_id: str, payload: CountryAuthorizationUpdate
) -> CountryAuthorization:
    svc = get_product_licensure_service()
    updated = svc.update_country_authorization(ca_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Country authorization '{ca_id}' not found"
        )
    return updated


@router.delete(
    "/country-authorizations/{ca_id}",
    status_code=204,
    summary="Delete a country authorization",
)
async def delete_country_authorization(ca_id: str) -> None:
    svc = get_product_licensure_service()
    deleted = svc.delete_country_authorization(ca_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Country authorization '{ca_id}' not found"
        )


# ---------------------------------------------------------------------------
# Product Labels
# ---------------------------------------------------------------------------


@router.get(
    "/labels",
    response_model=ProductLabelListResponse,
    summary="List product labels",
    description="Retrieve product labels with optional filtering by application, country, and status.",
)
async def list_labels(
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    status: Optional[LabelStatus] = Query(None, description="Filter by label status"),
) -> ProductLabelListResponse:
    svc = get_product_licensure_service()
    items = svc.list_labels(
        application_id=application_id, country=country, status=status
    )
    return ProductLabelListResponse(items=items, total=len(items))


@router.get(
    "/labels/{label_id}",
    response_model=ProductLabel,
    summary="Get a product label",
)
async def get_label(label_id: str) -> ProductLabel:
    svc = get_product_licensure_service()
    label = svc.get_label(label_id)
    if label is None:
        raise HTTPException(status_code=404, detail=f"Label '{label_id}' not found")
    return label


@router.post(
    "/labels",
    response_model=ProductLabel,
    status_code=201,
    summary="Create a product label",
)
async def create_label(payload: ProductLabelCreate) -> ProductLabel:
    svc = get_product_licensure_service()
    try:
        return svc.create_label(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/labels/{label_id}",
    response_model=ProductLabel,
    summary="Update a product label",
)
async def update_label(label_id: str, payload: ProductLabelUpdate) -> ProductLabel:
    svc = get_product_licensure_service()
    updated = svc.update_label(label_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Label '{label_id}' not found")
    return updated


@router.delete(
    "/labels/{label_id}",
    status_code=204,
    summary="Delete a product label",
)
async def delete_label(label_id: str) -> None:
    svc = get_product_licensure_service()
    deleted = svc.delete_label(label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Label '{label_id}' not found")


# ---------------------------------------------------------------------------
# Post-Approval Changes
# ---------------------------------------------------------------------------


@router.get(
    "/post-approval-changes",
    response_model=PostApprovalChangeListResponse,
    summary="List post-approval changes",
    description="Retrieve post-approval changes with optional filtering by application, type, and status.",
)
async def list_post_approval_changes(
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    change_type: Optional[ChangeType] = Query(None, description="Filter by change type"),
    status: Optional[ApplicationStatus] = Query(None, description="Filter by status"),
) -> PostApprovalChangeListResponse:
    svc = get_product_licensure_service()
    items = svc.list_post_approval_changes(
        application_id=application_id, change_type=change_type, status=status
    )
    return PostApprovalChangeListResponse(items=items, total=len(items))


@router.get(
    "/post-approval-changes/{pac_id}",
    response_model=PostApprovalChange,
    summary="Get a post-approval change",
)
async def get_post_approval_change(pac_id: str) -> PostApprovalChange:
    svc = get_product_licensure_service()
    pac = svc.get_post_approval_change(pac_id)
    if pac is None:
        raise HTTPException(
            status_code=404, detail=f"Post-approval change '{pac_id}' not found"
        )
    return pac


@router.post(
    "/post-approval-changes",
    response_model=PostApprovalChange,
    status_code=201,
    summary="File a post-approval change",
)
async def file_post_approval_change(
    payload: PostApprovalChangeCreate,
) -> PostApprovalChange:
    svc = get_product_licensure_service()
    try:
        return svc.file_post_approval_change(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/post-approval-changes/{pac_id}",
    response_model=PostApprovalChange,
    summary="Update a post-approval change",
)
async def update_post_approval_change(
    pac_id: str, payload: PostApprovalChangeUpdate
) -> PostApprovalChange:
    svc = get_product_licensure_service()
    updated = svc.update_post_approval_change(pac_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Post-approval change '{pac_id}' not found"
        )
    return updated


@router.delete(
    "/post-approval-changes/{pac_id}",
    status_code=204,
    summary="Delete a post-approval change",
)
async def delete_post_approval_change(pac_id: str) -> None:
    svc = get_product_licensure_service()
    deleted = svc.delete_post_approval_change(pac_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Post-approval change '{pac_id}' not found"
        )


# ---------------------------------------------------------------------------
# Market Access Timelines
# ---------------------------------------------------------------------------


@router.get(
    "/timelines",
    response_model=MarketAccessTimelineListResponse,
    summary="List market access timeline milestones",
    description="Retrieve timeline milestones with optional filtering by application, country, and status.",
)
async def list_timelines(
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    status: Optional[MilestoneStatus] = Query(None, description="Filter by milestone status"),
) -> MarketAccessTimelineListResponse:
    svc = get_product_licensure_service()
    items = svc.list_timelines(
        application_id=application_id, country=country, status=status
    )
    return MarketAccessTimelineListResponse(items=items, total=len(items))


@router.get(
    "/timelines/{tl_id}",
    response_model=MarketAccessTimeline,
    summary="Get a timeline milestone",
)
async def get_timeline(tl_id: str) -> MarketAccessTimeline:
    svc = get_product_licensure_service()
    tl = svc.get_timeline(tl_id)
    if tl is None:
        raise HTTPException(status_code=404, detail=f"Timeline milestone '{tl_id}' not found")
    return tl


@router.post(
    "/timelines",
    response_model=MarketAccessTimeline,
    status_code=201,
    summary="Create a timeline milestone",
)
async def create_timeline(payload: MarketAccessTimelineCreate) -> MarketAccessTimeline:
    svc = get_product_licensure_service()
    try:
        return svc.create_timeline(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/timelines/{tl_id}",
    response_model=MarketAccessTimeline,
    summary="Update a timeline milestone",
)
async def update_timeline(
    tl_id: str, payload: MarketAccessTimelineUpdate
) -> MarketAccessTimeline:
    svc = get_product_licensure_service()
    updated = svc.update_timeline(tl_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Timeline milestone '{tl_id}' not found")
    return updated


@router.delete(
    "/timelines/{tl_id}",
    status_code=204,
    summary="Delete a timeline milestone",
)
async def delete_timeline(tl_id: str) -> None:
    svc = get_product_licensure_service()
    deleted = svc.delete_timeline(tl_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Timeline milestone '{tl_id}' not found")


# ---------------------------------------------------------------------------
# Product Status by Country & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{app_id}/country-status",
    response_model=ProductCountryStatusListResponse,
    summary="Get product status by country",
    description="Retrieve aggregated product authorization status across all countries for a given application.",
)
async def get_product_country_status(
    app_id: str,
) -> ProductCountryStatusListResponse:
    svc = get_product_licensure_service()
    result = svc.get_product_status_by_country(app_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found")
    return result


@router.get(
    "/metrics",
    response_model=LicensureMetrics,
    summary="Get licensure dashboard metrics",
    description="Aggregated metrics across all regulatory applications, country authorizations, labels, changes, and timelines.",
)
async def get_metrics() -> LicensureMetrics:
    svc = get_product_licensure_service()
    return svc.get_metrics()
