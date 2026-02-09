"""Clinical Site Payments & Grant Management API endpoints (CLINICAL-21).

Provides comprehensive site payment operations: grant definitions & management,
payment line item CRUD, invoice lifecycle, site payment summaries, overdue
payment detection, approve/pay invoice shortcuts, and aggregated payment metrics.

Endpoints:
    GET    /site-payments/grants                              - List site grants
    GET    /site-payments/grants/{grant_id}                   - Get single grant
    POST   /site-payments/grants                              - Create site grant
    PUT    /site-payments/grants/{grant_id}                   - Update site grant
    DELETE /site-payments/grants/{grant_id}                   - Delete site grant
    GET    /site-payments/line-items                           - List payment line items
    GET    /site-payments/line-items/{item_id}                 - Get single line item
    POST   /site-payments/line-items                           - Create payment line item
    PUT    /site-payments/line-items/{item_id}                 - Update payment line item
    DELETE /site-payments/line-items/{item_id}                 - Delete payment line item
    GET    /site-payments/invoices                             - List invoices
    GET    /site-payments/invoices/{invoice_id}                - Get single invoice
    POST   /site-payments/invoices                             - Create invoice
    PUT    /site-payments/invoices/{invoice_id}                - Update invoice
    DELETE /site-payments/invoices/{invoice_id}                - Delete invoice
    POST   /site-payments/invoices/{invoice_id}/approve        - Approve invoice
    POST   /site-payments/invoices/{invoice_id}/pay            - Pay invoice
    GET    /site-payments/sites/{site_id}/summary              - Site payment summary
    GET    /site-payments/summaries                            - All site payment summaries
    GET    /site-payments/overdue                              - Overdue payments
    GET    /site-payments/metrics                              - Aggregated payment metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_payments import (
    CurrencyCode,
    Invoice,
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceUpdate,
    PaymentLineItem,
    PaymentLineItemCreate,
    PaymentLineItemListResponse,
    PaymentLineItemUpdate,
    PaymentMetrics,
    PaymentStatus,
    PaymentType,
    SiteGrant,
    SiteGrantCreate,
    SiteGrantListResponse,
    SiteGrantUpdate,
    SitePaymentSummary,
    SitePaymentSummaryListResponse,
)
from app.services.site_payments_service import get_site_payments_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-payments",
    tags=["Site Payments"],
)


# ---------------------------------------------------------------------------
# Grant Management
# ---------------------------------------------------------------------------


@router.get(
    "/grants",
    response_model=SiteGrantListResponse,
    summary="List site grants",
    description="Retrieve site grants with optional filtering by trial, site, and currency.",
)
async def list_grants(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    currency: Optional[CurrencyCode] = Query(None, description="Filter by currency"),
) -> SiteGrantListResponse:
    svc = get_site_payments_service()
    items = svc.list_grants(trial_id=trial_id, site_id=site_id, currency=currency)
    return SiteGrantListResponse(items=items, total=len(items))


@router.get(
    "/grants/{grant_id}",
    response_model=SiteGrant,
    summary="Get a site grant",
)
async def get_grant(grant_id: str) -> SiteGrant:
    svc = get_site_payments_service()
    grant = svc.get_grant(grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail=f"Grant '{grant_id}' not found")
    return grant


@router.post(
    "/grants",
    response_model=SiteGrant,
    status_code=201,
    summary="Create a site grant",
)
async def create_grant(payload: SiteGrantCreate) -> SiteGrant:
    svc = get_site_payments_service()
    return svc.create_grant(payload)


@router.put(
    "/grants/{grant_id}",
    response_model=SiteGrant,
    summary="Update a site grant",
    description="Update grant terms. Automatically increments amendment count.",
)
async def update_grant(grant_id: str, payload: SiteGrantUpdate) -> SiteGrant:
    svc = get_site_payments_service()
    updated = svc.update_grant(grant_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Grant '{grant_id}' not found")
    return updated


@router.delete(
    "/grants/{grant_id}",
    status_code=204,
    summary="Delete a site grant",
)
async def delete_grant(grant_id: str) -> None:
    svc = get_site_payments_service()
    deleted = svc.delete_grant(grant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Grant '{grant_id}' not found")


# ---------------------------------------------------------------------------
# Payment Line Items
# ---------------------------------------------------------------------------


@router.get(
    "/line-items",
    response_model=PaymentLineItemListResponse,
    summary="List payment line items",
    description="Retrieve payment line items with optional filtering by grant, site, type, status, and patient.",
)
async def list_line_items(
    grant_id: Optional[str] = Query(None, description="Filter by grant ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    payment_type: Optional[PaymentType] = Query(None, description="Filter by payment type"),
    status: Optional[PaymentStatus] = Query(None, description="Filter by status"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> PaymentLineItemListResponse:
    svc = get_site_payments_service()
    items = svc.list_line_items(
        grant_id=grant_id, site_id=site_id, payment_type=payment_type,
        status=status, patient_id=patient_id,
    )
    return PaymentLineItemListResponse(items=items, total=len(items))


@router.get(
    "/line-items/{item_id}",
    response_model=PaymentLineItem,
    summary="Get a payment line item",
)
async def get_line_item(item_id: str) -> PaymentLineItem:
    svc = get_site_payments_service()
    li = svc.get_line_item(item_id)
    if li is None:
        raise HTTPException(status_code=404, detail=f"Line item '{item_id}' not found")
    return li


@router.post(
    "/line-items",
    response_model=PaymentLineItem,
    status_code=201,
    summary="Create a payment line item",
)
async def create_line_item(payload: PaymentLineItemCreate) -> PaymentLineItem:
    svc = get_site_payments_service()
    try:
        return svc.create_line_item(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/line-items/{item_id}",
    response_model=PaymentLineItem,
    summary="Update a payment line item",
)
async def update_line_item(item_id: str, payload: PaymentLineItemUpdate) -> PaymentLineItem:
    svc = get_site_payments_service()
    updated = svc.update_line_item(item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Line item '{item_id}' not found")
    return updated


@router.delete(
    "/line-items/{item_id}",
    status_code=204,
    summary="Delete a payment line item",
)
async def delete_line_item(item_id: str) -> None:
    svc = get_site_payments_service()
    deleted = svc.delete_line_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Line item '{item_id}' not found")


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
    description="Retrieve invoices with optional filtering by site, trial, and status.",
)
async def list_invoices(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[PaymentStatus] = Query(None, description="Filter by status"),
) -> InvoiceListResponse:
    svc = get_site_payments_service()
    items = svc.list_invoices(site_id=site_id, trial_id=trial_id, status=status)
    return InvoiceListResponse(items=items, total=len(items))


@router.get(
    "/invoices/{invoice_id}",
    response_model=Invoice,
    summary="Get an invoice",
)
async def get_invoice(invoice_id: str) -> Invoice:
    svc = get_site_payments_service()
    invoice = svc.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")
    return invoice


@router.post(
    "/invoices",
    response_model=Invoice,
    status_code=201,
    summary="Create an invoice",
    description="Create an invoice for a billing period. Subtotal is auto-calculated from referenced line items.",
)
async def create_invoice(payload: InvoiceCreate) -> Invoice:
    svc = get_site_payments_service()
    return svc.create_invoice(payload)


@router.put(
    "/invoices/{invoice_id}",
    response_model=Invoice,
    summary="Update an invoice",
)
async def update_invoice(invoice_id: str, payload: InvoiceUpdate) -> Invoice:
    svc = get_site_payments_service()
    updated = svc.update_invoice(invoice_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")
    return updated


@router.delete(
    "/invoices/{invoice_id}",
    status_code=204,
    summary="Delete an invoice",
)
async def delete_invoice(invoice_id: str) -> None:
    svc = get_site_payments_service()
    deleted = svc.delete_invoice(invoice_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")


@router.post(
    "/invoices/{invoice_id}/approve",
    response_model=Invoice,
    summary="Approve an invoice",
    description="Approve an invoice. Sets approved_date automatically.",
)
async def approve_invoice(invoice_id: str) -> Invoice:
    svc = get_site_payments_service()
    try:
        result = svc.approve_invoice(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")
    return result


@router.post(
    "/invoices/{invoice_id}/pay",
    response_model=Invoice,
    summary="Pay an invoice",
    description="Mark an invoice as paid. Sets paid_date automatically.",
)
async def pay_invoice(invoice_id: str) -> Invoice:
    svc = get_site_payments_service()
    try:
        result = svc.pay_invoice(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Site Payment Summaries
# ---------------------------------------------------------------------------


@router.get(
    "/sites/{site_id}/summary",
    response_model=SitePaymentSummary,
    summary="Get site payment summary",
    description="Compute payment summary for a specific site including accrued, invoiced, paid, and holdback amounts.",
)
async def get_site_summary(site_id: str) -> SitePaymentSummary:
    svc = get_site_payments_service()
    summary = svc.get_site_summary(site_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found or has no grant")
    return summary


@router.get(
    "/summaries",
    response_model=SitePaymentSummaryListResponse,
    summary="Get all site payment summaries",
    description="Compute payment summaries for all sites with active grants.",
)
async def list_site_summaries() -> SitePaymentSummaryListResponse:
    svc = get_site_payments_service()
    items = svc.list_site_summaries()
    return SitePaymentSummaryListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Overdue Payments
# ---------------------------------------------------------------------------


@router.get(
    "/overdue",
    response_model=PaymentLineItemListResponse,
    summary="Get overdue payments",
    description="Retrieve payment line items accrued more than 90 days ago that are not yet paid.",
)
async def get_overdue_payments() -> PaymentLineItemListResponse:
    svc = get_site_payments_service()
    items = svc.get_overdue_payments()
    return PaymentLineItemListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PaymentMetrics,
    summary="Get payment metrics",
    description="Aggregated payment metrics across all grants including accrued, paid, cycle time, and holdback totals.",
)
async def get_metrics() -> PaymentMetrics:
    svc = get_site_payments_service()
    return svc.get_metrics()
