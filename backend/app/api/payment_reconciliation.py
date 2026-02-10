"""Site Payment Reconciliation API endpoints (FINANCE-PR).

Provides comprehensive payment reconciliation between sponsor and clinical sites:
reconciliation batch lifecycle, site-level payment matching, discrepancy
identification and resolution, payment adjustments with approval workflows,
audit trail tracking, financial close processes, auto-matching, and metrics.

Endpoints:
    GET    /payment-reconciliation/batches                                    - List batches
    GET    /payment-reconciliation/batches/{batch_id}                         - Get single batch
    POST   /payment-reconciliation/batches                                    - Create batch
    PUT    /payment-reconciliation/batches/{batch_id}                         - Update batch
    DELETE /payment-reconciliation/batches/{batch_id}                         - Delete batch
    POST   /payment-reconciliation/batches/initiate                           - Initiate reconciliation
    POST   /payment-reconciliation/batches/{batch_id}/auto-match              - Auto-match payments
    GET    /payment-reconciliation/site-reconciliations                       - List site reconciliations
    GET    /payment-reconciliation/site-reconciliations/{recon_id}            - Get single site recon
    POST   /payment-reconciliation/site-reconciliations                       - Create site recon
    PUT    /payment-reconciliation/site-reconciliations/{recon_id}            - Update site recon
    DELETE /payment-reconciliation/site-reconciliations/{recon_id}            - Delete site recon
    GET    /payment-reconciliation/discrepancies                              - List discrepancies
    GET    /payment-reconciliation/discrepancies/{disc_id}                    - Get single discrepancy
    POST   /payment-reconciliation/discrepancies                              - Flag discrepancy
    PUT    /payment-reconciliation/discrepancies/{disc_id}                    - Update discrepancy
    DELETE /payment-reconciliation/discrepancies/{disc_id}                    - Delete discrepancy
    GET    /payment-reconciliation/adjustments                                - List adjustments
    GET    /payment-reconciliation/adjustments/{adj_id}                       - Get single adjustment
    POST   /payment-reconciliation/adjustments                                - Create adjustment
    POST   /payment-reconciliation/adjustments/{adj_id}/approve               - Approve/reject adjustment
    DELETE /payment-reconciliation/adjustments/{adj_id}                       - Delete adjustment
    GET    /payment-reconciliation/audit-trail                                - List audit entries
    GET    /payment-reconciliation/audit-trail/{entry_id}                     - Get single audit entry
    GET    /payment-reconciliation/financial-closes                           - List financial closes
    GET    /payment-reconciliation/financial-closes/{close_id}                - Get single close
    POST   /payment-reconciliation/financial-closes                           - Close a period
    POST   /payment-reconciliation/financial-closes/{close_id}/approve        - Approve financial close
    GET    /payment-reconciliation/metrics                                    - Reconciliation metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.payment_reconciliation import (
    AdjustmentApproval,
    AdjustmentType,
    ApprovalStatus,
    AutoMatchRequest,
    DiscrepancyType,
    FinancialClose,
    FinancialCloseListResponse,
    FinancialCloseRequest,
    PaymentAdjustment,
    PaymentAdjustmentCreate,
    PaymentAdjustmentListResponse,
    PaymentDiscrepancy,
    PaymentDiscrepancyCreate,
    PaymentDiscrepancyListResponse,
    PaymentDiscrepancyUpdate,
    ReconciliationAuditEntry,
    ReconciliationAuditListResponse,
    ReconciliationBatch,
    ReconciliationBatchCreate,
    ReconciliationBatchListResponse,
    ReconciliationBatchUpdate,
    ReconciliationMetrics,
    ReconciliationStatus,
    SiteReconciliation,
    SiteReconciliationCreate,
    SiteReconciliationListResponse,
    SiteReconciliationUpdate,
)
from app.services.payment_reconciliation_service import get_payment_reconciliation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payment-reconciliation",
    tags=["Payment Reconciliation"],
)


# ---------------------------------------------------------------------------
# Reconciliation Batches
# ---------------------------------------------------------------------------


@router.get(
    "/batches",
    response_model=ReconciliationBatchListResponse,
    summary="List reconciliation batches",
    description="Retrieve reconciliation batches with optional filtering by trial and status.",
)
async def list_batches(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ReconciliationStatus] = Query(None, description="Filter by batch status"),
) -> ReconciliationBatchListResponse:
    svc = get_payment_reconciliation_service()
    items = svc.list_batches(trial_id=trial_id, status=status)
    return ReconciliationBatchListResponse(items=items, total=len(items))


@router.get(
    "/batches/{batch_id}",
    response_model=ReconciliationBatch,
    summary="Get a reconciliation batch",
)
async def get_batch(batch_id: str) -> ReconciliationBatch:
    svc = get_payment_reconciliation_service()
    batch = svc.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return batch


@router.post(
    "/batches",
    response_model=ReconciliationBatch,
    status_code=201,
    summary="Create a reconciliation batch",
)
async def create_batch(payload: ReconciliationBatchCreate) -> ReconciliationBatch:
    svc = get_payment_reconciliation_service()
    return svc.create_batch(payload)


@router.put(
    "/batches/{batch_id}",
    response_model=ReconciliationBatch,
    summary="Update a reconciliation batch",
)
async def update_batch(batch_id: str, payload: ReconciliationBatchUpdate) -> ReconciliationBatch:
    svc = get_payment_reconciliation_service()
    updated = svc.update_batch(batch_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return updated


@router.delete(
    "/batches/{batch_id}",
    status_code=204,
    summary="Delete a reconciliation batch",
)
async def delete_batch(batch_id: str) -> None:
    svc = get_payment_reconciliation_service()
    deleted = svc.delete_batch(batch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.post(
    "/batches/initiate",
    response_model=ReconciliationBatch,
    status_code=201,
    summary="Initiate a reconciliation process",
    description="Create and start a new reconciliation batch, setting status to in_progress.",
)
async def initiate_reconciliation(payload: ReconciliationBatchCreate) -> ReconciliationBatch:
    svc = get_payment_reconciliation_service()
    return svc.initiate_reconciliation(payload)


@router.post(
    "/batches/{batch_id}/auto-match",
    response_model=ReconciliationBatch,
    summary="Auto-match payments in a batch",
    description="Run automatic payment matching within a batch using tolerance-based matching.",
)
async def auto_match_payments(batch_id: str, payload: AutoMatchRequest) -> ReconciliationBatch:
    svc = get_payment_reconciliation_service()
    result = svc.auto_match_payments(batch_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Site Reconciliations
# ---------------------------------------------------------------------------


@router.get(
    "/site-reconciliations",
    response_model=SiteReconciliationListResponse,
    summary="List site reconciliations",
    description="Retrieve site reconciliation records with optional filtering.",
)
async def list_site_reconciliations(
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[ReconciliationStatus] = Query(None, description="Filter by status"),
) -> SiteReconciliationListResponse:
    svc = get_payment_reconciliation_service()
    items = svc.list_site_reconciliations(batch_id=batch_id, site_id=site_id, status=status)
    return SiteReconciliationListResponse(items=items, total=len(items))


@router.get(
    "/site-reconciliations/{recon_id}",
    response_model=SiteReconciliation,
    summary="Get a site reconciliation record",
)
async def get_site_reconciliation(recon_id: str) -> SiteReconciliation:
    svc = get_payment_reconciliation_service()
    sr = svc.get_site_reconciliation(recon_id)
    if sr is None:
        raise HTTPException(status_code=404, detail=f"Site reconciliation '{recon_id}' not found")
    return sr


@router.post(
    "/site-reconciliations",
    response_model=SiteReconciliation,
    status_code=201,
    summary="Create a site reconciliation record",
)
async def create_site_reconciliation(payload: SiteReconciliationCreate) -> SiteReconciliation:
    svc = get_payment_reconciliation_service()
    return svc.create_site_reconciliation(payload)


@router.put(
    "/site-reconciliations/{recon_id}",
    response_model=SiteReconciliation,
    summary="Update a site reconciliation record",
)
async def update_site_reconciliation(
    recon_id: str, payload: SiteReconciliationUpdate,
) -> SiteReconciliation:
    svc = get_payment_reconciliation_service()
    updated = svc.update_site_reconciliation(recon_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Site reconciliation '{recon_id}' not found")
    return updated


@router.delete(
    "/site-reconciliations/{recon_id}",
    status_code=204,
    summary="Delete a site reconciliation record",
)
async def delete_site_reconciliation(recon_id: str) -> None:
    svc = get_payment_reconciliation_service()
    deleted = svc.delete_site_reconciliation(recon_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Site reconciliation '{recon_id}' not found")


# ---------------------------------------------------------------------------
# Payment Discrepancies
# ---------------------------------------------------------------------------


@router.get(
    "/discrepancies",
    response_model=PaymentDiscrepancyListResponse,
    summary="List payment discrepancies",
    description="Retrieve payment discrepancies with optional filtering.",
)
async def list_discrepancies(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    reconciliation_id: Optional[str] = Query(None, description="Filter by reconciliation ID"),
    discrepancy_type: Optional[DiscrepancyType] = Query(None, description="Filter by type"),
    status: Optional[ReconciliationStatus] = Query(None, description="Filter by status"),
) -> PaymentDiscrepancyListResponse:
    svc = get_payment_reconciliation_service()
    items = svc.list_discrepancies(
        site_id=site_id,
        reconciliation_id=reconciliation_id,
        discrepancy_type=discrepancy_type,
        status=status,
    )
    return PaymentDiscrepancyListResponse(items=items, total=len(items))


@router.get(
    "/discrepancies/{disc_id}",
    response_model=PaymentDiscrepancy,
    summary="Get a payment discrepancy",
)
async def get_discrepancy(disc_id: str) -> PaymentDiscrepancy:
    svc = get_payment_reconciliation_service()
    disc = svc.get_discrepancy(disc_id)
    if disc is None:
        raise HTTPException(status_code=404, detail=f"Discrepancy '{disc_id}' not found")
    return disc


@router.post(
    "/discrepancies",
    response_model=PaymentDiscrepancy,
    status_code=201,
    summary="Flag a payment discrepancy",
    description="Identify and flag a new payment discrepancy for investigation.",
)
async def flag_discrepancy(payload: PaymentDiscrepancyCreate) -> PaymentDiscrepancy:
    svc = get_payment_reconciliation_service()
    return svc.flag_discrepancy(payload)


@router.put(
    "/discrepancies/{disc_id}",
    response_model=PaymentDiscrepancy,
    summary="Update a payment discrepancy",
    description="Update discrepancy details including resolution and root cause.",
)
async def update_discrepancy(
    disc_id: str, payload: PaymentDiscrepancyUpdate,
) -> PaymentDiscrepancy:
    svc = get_payment_reconciliation_service()
    updated = svc.update_discrepancy(disc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Discrepancy '{disc_id}' not found")
    return updated


@router.delete(
    "/discrepancies/{disc_id}",
    status_code=204,
    summary="Delete a payment discrepancy",
)
async def delete_discrepancy(disc_id: str) -> None:
    svc = get_payment_reconciliation_service()
    deleted = svc.delete_discrepancy(disc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Discrepancy '{disc_id}' not found")


# ---------------------------------------------------------------------------
# Payment Adjustments
# ---------------------------------------------------------------------------


@router.get(
    "/adjustments",
    response_model=PaymentAdjustmentListResponse,
    summary="List payment adjustments",
    description="Retrieve payment adjustments with optional filtering.",
)
async def list_adjustments(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    reconciliation_id: Optional[str] = Query(None, description="Filter by reconciliation ID"),
    adjustment_type: Optional[AdjustmentType] = Query(None, description="Filter by type"),
    approval_status: Optional[ApprovalStatus] = Query(None, description="Filter by approval status"),
) -> PaymentAdjustmentListResponse:
    svc = get_payment_reconciliation_service()
    items = svc.list_adjustments(
        site_id=site_id,
        reconciliation_id=reconciliation_id,
        adjustment_type=adjustment_type,
        approval_status=approval_status,
    )
    return PaymentAdjustmentListResponse(items=items, total=len(items))


@router.get(
    "/adjustments/{adj_id}",
    response_model=PaymentAdjustment,
    summary="Get a payment adjustment",
)
async def get_adjustment(adj_id: str) -> PaymentAdjustment:
    svc = get_payment_reconciliation_service()
    adj = svc.get_adjustment(adj_id)
    if adj is None:
        raise HTTPException(status_code=404, detail=f"Adjustment '{adj_id}' not found")
    return adj


@router.post(
    "/adjustments",
    response_model=PaymentAdjustment,
    status_code=201,
    summary="Create a payment adjustment",
    description="Create a new payment adjustment pending approval.",
)
async def create_adjustment(payload: PaymentAdjustmentCreate) -> PaymentAdjustment:
    svc = get_payment_reconciliation_service()
    return svc.create_adjustment(payload)


@router.post(
    "/adjustments/{adj_id}/approve",
    response_model=PaymentAdjustment,
    summary="Approve or reject a payment adjustment",
    description="Approve or reject a pending payment adjustment.",
)
async def approve_adjustment(adj_id: str, payload: AdjustmentApproval) -> PaymentAdjustment:
    svc = get_payment_reconciliation_service()
    try:
        result = svc.approve_adjustment(adj_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Adjustment '{adj_id}' not found")
    return result


@router.delete(
    "/adjustments/{adj_id}",
    status_code=204,
    summary="Delete a payment adjustment",
)
async def delete_adjustment(adj_id: str) -> None:
    svc = get_payment_reconciliation_service()
    deleted = svc.delete_adjustment(adj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Adjustment '{adj_id}' not found")


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------


@router.get(
    "/audit-trail",
    response_model=ReconciliationAuditListResponse,
    summary="List reconciliation audit entries",
    description="Retrieve audit trail entries for reconciliation activities.",
)
async def list_audit_entries(
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    performed_by: Optional[str] = Query(None, description="Filter by performer"),
) -> ReconciliationAuditListResponse:
    svc = get_payment_reconciliation_service()
    items = svc.list_audit_entries(
        batch_id=batch_id, entity_type=entity_type, performed_by=performed_by,
    )
    return ReconciliationAuditListResponse(items=items, total=len(items))


@router.get(
    "/audit-trail/{entry_id}",
    response_model=ReconciliationAuditEntry,
    summary="Get a single audit trail entry",
)
async def get_audit_entry(entry_id: str) -> ReconciliationAuditEntry:
    svc = get_payment_reconciliation_service()
    entry = svc.get_audit_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Audit entry '{entry_id}' not found")
    return entry


# ---------------------------------------------------------------------------
# Financial Close
# ---------------------------------------------------------------------------


@router.get(
    "/financial-closes",
    response_model=FinancialCloseListResponse,
    summary="List financial close records",
    description="Retrieve financial close records with optional filtering.",
)
async def list_financial_closes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ApprovalStatus] = Query(None, description="Filter by approval status"),
) -> FinancialCloseListResponse:
    svc = get_payment_reconciliation_service()
    items = svc.list_financial_closes(trial_id=trial_id, status=status)
    return FinancialCloseListResponse(items=items, total=len(items))


@router.get(
    "/financial-closes/{close_id}",
    response_model=FinancialClose,
    summary="Get a financial close record",
)
async def get_financial_close(close_id: str) -> FinancialClose:
    svc = get_payment_reconciliation_service()
    fc = svc.get_financial_close(close_id)
    if fc is None:
        raise HTTPException(status_code=404, detail=f"Financial close '{close_id}' not found")
    return fc


@router.post(
    "/financial-closes",
    response_model=FinancialClose,
    status_code=201,
    summary="Close a financial period",
    description="Initiate financial close for a reconciliation period.",
)
async def close_period(payload: FinancialCloseRequest) -> FinancialClose:
    svc = get_payment_reconciliation_service()
    return svc.close_period(payload)


@router.post(
    "/financial-closes/{close_id}/approve",
    response_model=FinancialClose,
    summary="Approve a financial close",
    description="Approve a pending financial close with optional CFO sign-off.",
)
async def approve_financial_close(
    close_id: str,
    approved_by: str = Query(..., description="Name of the approver"),
    sign_off_cfo: Optional[str] = Query(None, description="CFO sign-off name"),
) -> FinancialClose:
    svc = get_payment_reconciliation_service()
    try:
        result = svc.approve_financial_close(close_id, approved_by, sign_off_cfo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Financial close '{close_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ReconciliationMetrics,
    summary="Get reconciliation metrics",
    description="Aggregated payment reconciliation operational metrics.",
)
async def get_metrics() -> ReconciliationMetrics:
    svc = get_payment_reconciliation_service()
    return svc.get_metrics()
