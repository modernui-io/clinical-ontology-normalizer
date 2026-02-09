"""Invoice Management & Contract Billing API (CFO-4).

Provides endpoints for invoice lifecycle management, billing contracts,
payment recording, AR aging reports, revenue recognition, and financial
metrics for the clinical trial patient recruitment platform.

Endpoints:
    GET  /invoice-management/invoices                           - List invoices
    POST /invoice-management/invoices                           - Create invoice
    GET  /invoice-management/invoices/{invoice_id}              - Get invoice
    PUT  /invoice-management/invoices/{invoice_id}              - Update invoice
    POST /invoice-management/invoices/{invoice_id}/line-items   - Add line item
    DELETE /invoice-management/invoices/{invoice_id}/line-items/{line_item_id} - Remove line item
    POST /invoice-management/invoices/{invoice_id}/payments     - Record payment
    GET  /invoice-management/invoices/{invoice_id}/payments     - List invoice payments
    GET  /invoice-management/invoices/{invoice_id}/three-way-match - 3-way match
    GET  /invoice-management/invoices/{invoice_id}/late-fee     - Calculate late fee
    POST /invoice-management/invoices/{invoice_id}/send         - Send invoice
    GET  /invoice-management/contracts                          - List contracts
    POST /invoice-management/contracts                          - Create contract
    GET  /invoice-management/contracts/{contract_id}            - Get contract
    POST /invoice-management/contracts/{contract_id}/generate-invoice - Auto-generate invoice
    GET  /invoice-management/payments                           - List all payments
    GET  /invoice-management/metrics                            - Invoice metrics
    GET  /invoice-management/ar-aging                           - AR aging report
    GET  /invoice-management/revenue-report                     - Revenue recognition report
    POST /invoice-management/detect-overdue                     - Detect overdue invoices
    GET  /invoice-management/stats                              - Service stats
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.invoice_management import (
    ARAgingReport,
    BillingContract,
    BillingContractCreateRequest,
    BillingContractListResponse,
    BillingModel,
    Invoice,
    InvoiceCreateRequest,
    InvoiceLineItemCreate,
    InvoiceListResponse,
    InvoiceMetrics,
    InvoiceStatus,
    InvoiceUpdateRequest,
    LateFeeCalculation,
    PaymentRecord,
    PaymentRecordRequest,
    RevenueReport,
    ThreeWayMatchResult,
)
from app.services.invoice_management_service import get_invoice_management_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoice-management", tags=["Invoice Management"])


# ============================================================================
# Invoice Endpoints
# ============================================================================


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    status: InvoiceStatus | None = Query(default=None, description="Filter by status"),
    client_id: str | None = Query(default=None, description="Filter by client ID"),
    contract_id: str | None = Query(default=None, description="Filter by contract ID"),
) -> InvoiceListResponse:
    """List all invoices with optional filters."""
    svc = get_invoice_management_service()
    items = svc.list_invoices(status=status, client_id=client_id, contract_id=contract_id)
    return InvoiceListResponse(items=items, total=len(items))


@router.post("/invoices", response_model=Invoice, status_code=201)
async def create_invoice(req: InvoiceCreateRequest) -> Invoice:
    """Create a new invoice."""
    svc = get_invoice_management_service()
    return svc.create_invoice(req)


@router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(invoice_id: str) -> Invoice:
    """Get a specific invoice by ID."""
    svc = get_invoice_management_service()
    inv = svc.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return inv


@router.put("/invoices/{invoice_id}", response_model=Invoice)
async def update_invoice(invoice_id: str, req: InvoiceUpdateRequest) -> Invoice:
    """Update an existing invoice (status, notes, PO, etc.)."""
    svc = get_invoice_management_service()
    try:
        inv = svc.update_invoice(invoice_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return inv


@router.post("/invoices/{invoice_id}/send", response_model=Invoice)
async def send_invoice(invoice_id: str) -> Invoice:
    """Send a draft invoice (transitions DRAFT -> SENT)."""
    svc = get_invoice_management_service()
    req = InvoiceUpdateRequest(status=InvoiceStatus.SENT)
    try:
        inv = svc.update_invoice(invoice_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return inv


# ============================================================================
# Line Item Endpoints
# ============================================================================


@router.post("/invoices/{invoice_id}/line-items", response_model=Invoice)
async def add_line_item(invoice_id: str, req: InvoiceLineItemCreate) -> Invoice:
    """Add a line item to a draft invoice."""
    svc = get_invoice_management_service()
    try:
        inv = svc.add_line_item(invoice_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return inv


@router.delete("/invoices/{invoice_id}/line-items/{line_item_id}", response_model=Invoice)
async def remove_line_item(invoice_id: str, line_item_id: str) -> Invoice:
    """Remove a line item from a draft invoice."""
    svc = get_invoice_management_service()
    try:
        inv = svc.remove_line_item(invoice_id, line_item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return inv


# ============================================================================
# Payment Endpoints
# ============================================================================


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentRecord, status_code=201)
async def record_payment(invoice_id: str, req: PaymentRecordRequest) -> PaymentRecord:
    """Record a payment against an invoice."""
    svc = get_invoice_management_service()
    try:
        payment = svc.record_payment(invoice_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not payment:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return payment


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentRecord])
async def list_invoice_payments(invoice_id: str) -> list[PaymentRecord]:
    """List all payments for a specific invoice."""
    svc = get_invoice_management_service()
    inv = svc.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return svc.list_payments(invoice_id=invoice_id)


@router.get("/payments", response_model=list[PaymentRecord])
async def list_all_payments() -> list[PaymentRecord]:
    """List all payment records."""
    svc = get_invoice_management_service()
    return svc.list_payments()


# ============================================================================
# Validation & Late Fees
# ============================================================================


@router.get("/invoices/{invoice_id}/three-way-match", response_model=ThreeWayMatchResult)
async def three_way_match(invoice_id: str) -> ThreeWayMatchResult:
    """Perform 3-way match (PO + Contract + Invoice) validation."""
    svc = get_invoice_management_service()
    result = svc.three_way_match(invoice_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return result


@router.get("/invoices/{invoice_id}/late-fee", response_model=LateFeeCalculation)
async def calculate_late_fee(invoice_id: str) -> LateFeeCalculation:
    """Calculate late fee for an invoice."""
    svc = get_invoice_management_service()
    result = svc.calculate_late_fee(invoice_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found or has no due date")
    return result


# ============================================================================
# Contract Endpoints
# ============================================================================


@router.get("/contracts", response_model=BillingContractListResponse)
async def list_contracts(
    client_id: str | None = Query(default=None, description="Filter by client ID"),
    billing_model: BillingModel | None = Query(default=None, description="Filter by billing model"),
) -> BillingContractListResponse:
    """List all billing contracts."""
    svc = get_invoice_management_service()
    items = svc.list_contracts(client_id=client_id, billing_model=billing_model)
    return BillingContractListResponse(items=items, total=len(items))


@router.post("/contracts", response_model=BillingContract, status_code=201)
async def create_contract(req: BillingContractCreateRequest) -> BillingContract:
    """Create a new billing contract."""
    svc = get_invoice_management_service()
    return svc.create_contract(req)


@router.get("/contracts/{contract_id}", response_model=BillingContract)
async def get_contract(contract_id: str) -> BillingContract:
    """Get a specific billing contract."""
    svc = get_invoice_management_service()
    contract = svc.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return contract


@router.post("/contracts/{contract_id}/generate-invoice", response_model=Invoice, status_code=201)
async def generate_invoice_from_contract(
    contract_id: str,
    description: str | None = Query(default=None, description="Custom line item description"),
    quantity: float = Query(default=1.0, description="Quantity for the line item"),
) -> Invoice:
    """Auto-generate an invoice from a billing contract."""
    svc = get_invoice_management_service()
    invoice = svc.generate_invoice_from_contract(contract_id, description=description, quantity=quantity)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return invoice


# ============================================================================
# Reports & Metrics
# ============================================================================


@router.get("/metrics", response_model=InvoiceMetrics)
async def get_invoice_metrics() -> InvoiceMetrics:
    """Get aggregated invoice / billing metrics (DSO, collection rate, etc.)."""
    svc = get_invoice_management_service()
    return svc.get_invoice_metrics()


@router.get("/ar-aging", response_model=ARAgingReport)
async def get_ar_aging_report() -> ARAgingReport:
    """Get accounts receivable aging report (0-30, 31-60, 61-90, 90+ days)."""
    svc = get_invoice_management_service()
    return svc.get_ar_aging_report()


@router.get("/revenue-report", response_model=RevenueReport)
async def get_revenue_report(
    year: int = Query(default=2025, description="Fiscal year for the report"),
) -> RevenueReport:
    """Get revenue recognition report (ASC 606 compliant)."""
    svc = get_invoice_management_service()
    return svc.get_revenue_report(year=year)


@router.post("/detect-overdue", response_model=list[Invoice])
async def detect_overdue() -> list[Invoice]:
    """Detect and mark overdue invoices."""
    svc = get_invoice_management_service()
    return svc.detect_overdue_invoices()


@router.get("/stats")
async def get_stats() -> dict:
    """Get service statistics."""
    svc = get_invoice_management_service()
    return svc.get_stats()
