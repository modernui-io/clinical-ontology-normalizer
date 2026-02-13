"""Inventory Reconciliation API endpoints (INV-REC).

Provides comprehensive inventory reconciliation operations: site inventory
snapshots, reconciliation audits, discrepancy records, lot accountability
logs, and inventory reconciliation metrics.

Endpoints:
    GET    /inventory-reconciliation/site-inventory-snapshots                       - List snapshots
    GET    /inventory-reconciliation/site-inventory-snapshots/{snapshot_id}         - Get single snapshot
    POST   /inventory-reconciliation/site-inventory-snapshots                       - Create snapshot
    PUT    /inventory-reconciliation/site-inventory-snapshots/{snapshot_id}         - Update snapshot
    DELETE /inventory-reconciliation/site-inventory-snapshots/{snapshot_id}         - Delete snapshot
    GET    /inventory-reconciliation/reconciliation-audits                          - List audits
    GET    /inventory-reconciliation/reconciliation-audits/{audit_id}               - Get single audit
    POST   /inventory-reconciliation/reconciliation-audits                          - Create audit
    PUT    /inventory-reconciliation/reconciliation-audits/{audit_id}               - Update audit
    DELETE /inventory-reconciliation/reconciliation-audits/{audit_id}               - Delete audit
    GET    /inventory-reconciliation/discrepancy-records                            - List discrepancies
    GET    /inventory-reconciliation/discrepancy-records/{discrepancy_id}           - Get single discrepancy
    POST   /inventory-reconciliation/discrepancy-records                            - Create discrepancy
    PUT    /inventory-reconciliation/discrepancy-records/{discrepancy_id}           - Update discrepancy
    DELETE /inventory-reconciliation/discrepancy-records/{discrepancy_id}           - Delete discrepancy
    GET    /inventory-reconciliation/lot-accountability-logs                        - List lot logs
    GET    /inventory-reconciliation/lot-accountability-logs/{log_id}               - Get single log
    POST   /inventory-reconciliation/lot-accountability-logs                        - Create log
    PUT    /inventory-reconciliation/lot-accountability-logs/{log_id}               - Update log
    DELETE /inventory-reconciliation/lot-accountability-logs/{log_id}               - Delete log
    GET    /inventory-reconciliation/metrics                                        - Reconciliation metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.inventory_reconciliation import (
    AccountabilityAction,
    AuditOutcome,
    DiscrepancyRecord,
    DiscrepancyRecordCreate,
    DiscrepancyRecordListResponse,
    DiscrepancyRecordUpdate,
    DiscrepancySeverity,
    DiscrepancyType,
    InventoryReconciliationMetrics,
    InventoryStatus,
    LotAccountabilityLog,
    LotAccountabilityLogCreate,
    LotAccountabilityLogListResponse,
    LotAccountabilityLogUpdate,
    ReconciliationAudit,
    ReconciliationAuditCreate,
    ReconciliationAuditListResponse,
    ReconciliationAuditUpdate,
    SiteInventorySnapshot,
    SiteInventorySnapshotCreate,
    SiteInventorySnapshotListResponse,
    SiteInventorySnapshotUpdate,
)
from app.services.inventory_reconciliation_service import get_inventory_reconciliation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inventory-reconciliation",
    tags=["Inventory Reconciliation"],
)


# ---------------------------------------------------------------------------
# Site Inventory Snapshots
# ---------------------------------------------------------------------------


@router.get(
    "/site-inventory-snapshots",
    response_model=SiteInventorySnapshotListResponse,
    summary="List site inventory snapshots",
    description="Retrieve site inventory snapshots with optional filtering by trial, status, and site.",
)
async def list_site_inventory_snapshots(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    inventory_status: Optional[InventoryStatus] = Query(None, description="Filter by inventory status"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> SiteInventorySnapshotListResponse:
    svc = get_inventory_reconciliation_service()
    items = svc.list_site_inventory_snapshots(
        trial_id=trial_id, inventory_status=inventory_status, site_id=site_id
    )
    return SiteInventorySnapshotListResponse(items=items, total=len(items))


@router.get(
    "/site-inventory-snapshots/{snapshot_id}",
    response_model=SiteInventorySnapshot,
    summary="Get a site inventory snapshot",
)
async def get_site_inventory_snapshot(snapshot_id: str) -> SiteInventorySnapshot:
    svc = get_inventory_reconciliation_service()
    record = svc.get_site_inventory_snapshot(snapshot_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Site inventory snapshot '{snapshot_id}' not found"
        )
    return record


@router.post(
    "/site-inventory-snapshots",
    response_model=SiteInventorySnapshot,
    status_code=201,
    summary="Create a site inventory snapshot",
)
async def create_site_inventory_snapshot(
    payload: SiteInventorySnapshotCreate,
) -> SiteInventorySnapshot:
    svc = get_inventory_reconciliation_service()
    return svc.create_site_inventory_snapshot(payload)


@router.put(
    "/site-inventory-snapshots/{snapshot_id}",
    response_model=SiteInventorySnapshot,
    summary="Update a site inventory snapshot",
)
async def update_site_inventory_snapshot(
    snapshot_id: str, payload: SiteInventorySnapshotUpdate
) -> SiteInventorySnapshot:
    svc = get_inventory_reconciliation_service()
    updated = svc.update_site_inventory_snapshot(snapshot_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Site inventory snapshot '{snapshot_id}' not found"
        )
    return updated


@router.delete(
    "/site-inventory-snapshots/{snapshot_id}",
    status_code=204,
    summary="Delete a site inventory snapshot",
)
async def delete_site_inventory_snapshot(snapshot_id: str) -> None:
    svc = get_inventory_reconciliation_service()
    deleted = svc.delete_site_inventory_snapshot(snapshot_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Site inventory snapshot '{snapshot_id}' not found"
        )


# ---------------------------------------------------------------------------
# Reconciliation Audits
# ---------------------------------------------------------------------------


@router.get(
    "/reconciliation-audits",
    response_model=ReconciliationAuditListResponse,
    summary="List reconciliation audits",
    description="Retrieve reconciliation audits with optional filtering by trial, outcome, and site.",
)
async def list_reconciliation_audits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    audit_outcome: Optional[AuditOutcome] = Query(None, description="Filter by audit outcome"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> ReconciliationAuditListResponse:
    svc = get_inventory_reconciliation_service()
    items = svc.list_reconciliation_audits(
        trial_id=trial_id, audit_outcome=audit_outcome, site_id=site_id
    )
    return ReconciliationAuditListResponse(items=items, total=len(items))


@router.get(
    "/reconciliation-audits/{audit_id}",
    response_model=ReconciliationAudit,
    summary="Get a reconciliation audit",
)
async def get_reconciliation_audit(audit_id: str) -> ReconciliationAudit:
    svc = get_inventory_reconciliation_service()
    record = svc.get_reconciliation_audit(audit_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Reconciliation audit '{audit_id}' not found"
        )
    return record


@router.post(
    "/reconciliation-audits",
    response_model=ReconciliationAudit,
    status_code=201,
    summary="Create a reconciliation audit",
)
async def create_reconciliation_audit(
    payload: ReconciliationAuditCreate,
) -> ReconciliationAudit:
    svc = get_inventory_reconciliation_service()
    return svc.create_reconciliation_audit(payload)


@router.put(
    "/reconciliation-audits/{audit_id}",
    response_model=ReconciliationAudit,
    summary="Update a reconciliation audit",
)
async def update_reconciliation_audit(
    audit_id: str, payload: ReconciliationAuditUpdate
) -> ReconciliationAudit:
    svc = get_inventory_reconciliation_service()
    updated = svc.update_reconciliation_audit(audit_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Reconciliation audit '{audit_id}' not found"
        )
    return updated


@router.delete(
    "/reconciliation-audits/{audit_id}",
    status_code=204,
    summary="Delete a reconciliation audit",
)
async def delete_reconciliation_audit(audit_id: str) -> None:
    svc = get_inventory_reconciliation_service()
    deleted = svc.delete_reconciliation_audit(audit_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Reconciliation audit '{audit_id}' not found"
        )


# ---------------------------------------------------------------------------
# Discrepancy Records
# ---------------------------------------------------------------------------


@router.get(
    "/discrepancy-records",
    response_model=DiscrepancyRecordListResponse,
    summary="List discrepancy records",
    description="Retrieve discrepancy records with optional filtering by trial, type, severity, and resolution status.",
)
async def list_discrepancy_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    discrepancy_type: Optional[DiscrepancyType] = Query(None, description="Filter by discrepancy type"),
    discrepancy_severity: Optional[DiscrepancySeverity] = Query(None, description="Filter by discrepancy severity"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
) -> DiscrepancyRecordListResponse:
    svc = get_inventory_reconciliation_service()
    items = svc.list_discrepancy_records(
        trial_id=trial_id,
        discrepancy_type=discrepancy_type,
        discrepancy_severity=discrepancy_severity,
        resolved=resolved,
    )
    return DiscrepancyRecordListResponse(items=items, total=len(items))


@router.get(
    "/discrepancy-records/{discrepancy_id}",
    response_model=DiscrepancyRecord,
    summary="Get a discrepancy record",
)
async def get_discrepancy_record(discrepancy_id: str) -> DiscrepancyRecord:
    svc = get_inventory_reconciliation_service()
    record = svc.get_discrepancy_record(discrepancy_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Discrepancy record '{discrepancy_id}' not found"
        )
    return record


@router.post(
    "/discrepancy-records",
    response_model=DiscrepancyRecord,
    status_code=201,
    summary="Create a discrepancy record",
)
async def create_discrepancy_record(
    payload: DiscrepancyRecordCreate,
) -> DiscrepancyRecord:
    svc = get_inventory_reconciliation_service()
    return svc.create_discrepancy_record(payload)


@router.put(
    "/discrepancy-records/{discrepancy_id}",
    response_model=DiscrepancyRecord,
    summary="Update a discrepancy record",
)
async def update_discrepancy_record(
    discrepancy_id: str, payload: DiscrepancyRecordUpdate
) -> DiscrepancyRecord:
    svc = get_inventory_reconciliation_service()
    updated = svc.update_discrepancy_record(discrepancy_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Discrepancy record '{discrepancy_id}' not found"
        )
    return updated


@router.delete(
    "/discrepancy-records/{discrepancy_id}",
    status_code=204,
    summary="Delete a discrepancy record",
)
async def delete_discrepancy_record(discrepancy_id: str) -> None:
    svc = get_inventory_reconciliation_service()
    deleted = svc.delete_discrepancy_record(discrepancy_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Discrepancy record '{discrepancy_id}' not found"
        )


# ---------------------------------------------------------------------------
# Lot Accountability Logs
# ---------------------------------------------------------------------------


@router.get(
    "/lot-accountability-logs",
    response_model=LotAccountabilityLogListResponse,
    summary="List lot accountability logs",
    description="Retrieve lot accountability logs with optional filtering by trial, action, and site.",
)
async def list_lot_accountability_logs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    accountability_action: Optional[AccountabilityAction] = Query(
        None, description="Filter by accountability action"
    ),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> LotAccountabilityLogListResponse:
    svc = get_inventory_reconciliation_service()
    items = svc.list_lot_accountability_logs(
        trial_id=trial_id, accountability_action=accountability_action, site_id=site_id
    )
    return LotAccountabilityLogListResponse(items=items, total=len(items))


@router.get(
    "/lot-accountability-logs/{log_id}",
    response_model=LotAccountabilityLog,
    summary="Get a lot accountability log",
)
async def get_lot_accountability_log(log_id: str) -> LotAccountabilityLog:
    svc = get_inventory_reconciliation_service()
    record = svc.get_lot_accountability_log(log_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Lot accountability log '{log_id}' not found"
        )
    return record


@router.post(
    "/lot-accountability-logs",
    response_model=LotAccountabilityLog,
    status_code=201,
    summary="Create a lot accountability log",
)
async def create_lot_accountability_log(
    payload: LotAccountabilityLogCreate,
) -> LotAccountabilityLog:
    svc = get_inventory_reconciliation_service()
    return svc.create_lot_accountability_log(payload)


@router.put(
    "/lot-accountability-logs/{log_id}",
    response_model=LotAccountabilityLog,
    summary="Update a lot accountability log",
)
async def update_lot_accountability_log(
    log_id: str, payload: LotAccountabilityLogUpdate
) -> LotAccountabilityLog:
    svc = get_inventory_reconciliation_service()
    updated = svc.update_lot_accountability_log(log_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Lot accountability log '{log_id}' not found"
        )
    return updated


@router.delete(
    "/lot-accountability-logs/{log_id}",
    status_code=204,
    summary="Delete a lot accountability log",
)
async def delete_lot_accountability_log(log_id: str) -> None:
    svc = get_inventory_reconciliation_service()
    deleted = svc.delete_lot_accountability_log(log_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Lot accountability log '{log_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InventoryReconciliationMetrics,
    summary="Get inventory reconciliation metrics",
    description="Aggregated metrics across all inventory reconciliation operations. Optionally filter by trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> InventoryReconciliationMetrics:
    svc = get_inventory_reconciliation_service()
    return svc.get_metrics(trial_id=trial_id)
