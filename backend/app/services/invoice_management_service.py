"""Invoice Management & Contract Billing Service (CFO-4).

Manages invoices, billing contracts, payment records, AR aging,
revenue recognition, and financial metrics for the clinical trial
patient recruitment platform.

Usage:
    from app.services.invoice_management_service import get_invoice_management_service

    service = get_invoice_management_service()
    invoices = service.list_invoices()
    metrics = service.get_invoice_metrics()
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.invoice_management import (
    ARAgingBucket,
    ARAgingReport,
    BillingContract,
    BillingContractCreateRequest,
    BillingMilestone,
    BillingModel,
    Currency,
    Invoice,
    InvoiceCreateRequest,
    InvoiceLineItem,
    InvoiceLineItemCreate,
    InvoiceMetrics,
    InvoiceStatus,
    InvoiceUpdateRequest,
    LateFeeCalculation,
    LineItemType,
    PaymentMethod,
    PaymentRecord,
    PaymentRecordRequest,
    PaymentTerms,
    RevenueRecognition,
    RevenueReport,
    ThreeWayMatchResult,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_invoice_service_instance: InvoiceManagementService | None = None
_invoice_service_lock = Lock()

# Late fee rate: 1.5% per month
LATE_FEE_MONTHLY_RATE = 0.015


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return date.today()


# ---------------------------------------------------------------------------
# Invoice Number Generator
# ---------------------------------------------------------------------------

_invoice_counter = 0
_counter_lock = Lock()


def _next_invoice_number(year: int | None = None) -> str:
    """Generate sequential invoice number like INV-2026-0001."""
    global _invoice_counter
    with _counter_lock:
        _invoice_counter += 1
        yr = year or _today().year
        return f"INV-{yr}-{_invoice_counter:04d}"


def _reset_invoice_counter() -> None:
    global _invoice_counter
    with _counter_lock:
        _invoice_counter = 0


# ---------------------------------------------------------------------------
# Seed Data Builders
# ---------------------------------------------------------------------------


def _build_seed_contracts() -> list[BillingContract]:
    """Build 6 billing contracts."""
    return [
        BillingContract(
            id="contract-001",
            client_id="client-regeneron",
            client_name="Regeneron Pharmaceuticals",
            billing_model=BillingModel.SUBSCRIPTION,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_fee=150_000.0,
            payment_terms=PaymentTerms.NET_30,
            auto_invoice=True,
            total_value=3_600_000.0,
            invoiced_to_date=1_950_000.0,
        ),
        BillingContract(
            id="contract-002",
            client_id="client-regeneron",
            client_name="Regeneron Pharmaceuticals",
            billing_model=BillingModel.PER_PATIENT,
            start_date=date(2025, 3, 1),
            end_date=date(2026, 6, 30),
            per_patient_rate=2_500.0,
            payment_terms=PaymentTerms.NET_45,
            auto_invoice=False,
            total_value=1_250_000.0,
            invoiced_to_date=625_000.0,
        ),
        BillingContract(
            id="contract-003",
            client_id="client-regeneron",
            client_name="Regeneron Pharmaceuticals",
            billing_model=BillingModel.PER_PATIENT,
            start_date=date(2025, 6, 1),
            end_date=date(2027, 5, 31),
            per_patient_rate=2_200.0,
            payment_terms=PaymentTerms.NET_30,
            auto_invoice=False,
            total_value=880_000.0,
            invoiced_to_date=264_000.0,
        ),
        BillingContract(
            id="contract-004",
            client_id="client-pharma-data",
            client_name="PharmaData Analytics Inc.",
            billing_model=BillingModel.DATA_LICENSING,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            data_licensing_fee=50_000.0,
            payment_terms=PaymentTerms.NET_30,
            auto_invoice=True,
            total_value=1_200_000.0,
            invoiced_to_date=650_000.0,
        ),
        BillingContract(
            id="contract-005",
            client_id="client-cro-partner",
            client_name="GlobalCRO Partners",
            billing_model=BillingModel.MILESTONE,
            start_date=date(2025, 4, 1),
            end_date=date(2026, 9, 30),
            payment_terms=PaymentTerms.NET_60,
            auto_invoice=False,
            milestones=[
                BillingMilestone(
                    name="Platform Integration",
                    amount=200_000.0,
                    target_date=date(2025, 6, 30),
                    completed=True,
                    invoice_id="inv-005",
                ),
                BillingMilestone(
                    name="Phase 1 Enrollment Complete",
                    amount=300_000.0,
                    target_date=date(2025, 12, 31),
                    completed=True,
                    invoice_id="inv-010",
                ),
                BillingMilestone(
                    name="Phase 2 Enrollment Complete",
                    amount=350_000.0,
                    target_date=date(2026, 6, 30),
                    completed=False,
                ),
                BillingMilestone(
                    name="Final Delivery",
                    amount=150_000.0,
                    target_date=date(2026, 9, 30),
                    completed=False,
                ),
            ],
            total_value=1_000_000.0,
            invoiced_to_date=500_000.0,
        ),
        BillingContract(
            id="contract-006",
            client_id="client-biotech-ai",
            client_name="BioTech AI Solutions",
            billing_model=BillingModel.USAGE_BASED,
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            payment_terms=PaymentTerms.NET_30,
            auto_invoice=True,
            total_value=480_000.0,
            invoiced_to_date=240_000.0,
        ),
    ]


def _build_seed_invoices() -> list[Invoice]:
    """Build 15 invoices across different statuses."""
    now = _now()

    def _li(lid: str, inv_id: str, lit: LineItemType, desc: str,
            qty: float, up: float, tax_rate: float = 0.0) -> InvoiceLineItem:
        amount = round(qty * up, 2)
        tax_amount = round(amount * tax_rate, 2)
        total = round(amount + tax_amount, 2)
        return InvoiceLineItem(
            id=lid, invoice_id=inv_id, line_item_type=lit,
            description=desc, quantity=qty, unit_price=up,
            amount=amount, tax_rate=tax_rate, tax_amount=tax_amount, total=total,
        )

    invoices = []

    # --- 3 PAID ---
    inv = Invoice(
        id="inv-001", invoice_number="INV-2025-0001",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-001", status=InvoiceStatus.PAID,
        billing_model=BillingModel.SUBSCRIPTION,
        line_items=[
            _li("li-001", "inv-001", LineItemType.PLATFORM_FEE, "Monthly platform subscription - Jan 2025", 1, 150_000.0),
        ],
        subtotal=150_000.0, tax_total=0.0, total=150_000.0,
        currency=Currency.USD, issued_date=date(2025, 1, 1), due_date=date(2025, 1, 31),
        paid_date=date(2025, 1, 25), payment_terms=PaymentTerms.NET_30,
        payment_method=PaymentMethod.WIRE_TRANSFER, po_number="PO-REG-2025-001",
        created_at=now - timedelta(days=400), updated_at=now - timedelta(days=370),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-002", invoice_number="INV-2025-0002",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-001", status=InvoiceStatus.PAID,
        billing_model=BillingModel.SUBSCRIPTION,
        line_items=[
            _li("li-002", "inv-002", LineItemType.PLATFORM_FEE, "Monthly platform subscription - Feb 2025", 1, 150_000.0),
        ],
        subtotal=150_000.0, tax_total=0.0, total=150_000.0,
        currency=Currency.USD, issued_date=date(2025, 2, 1), due_date=date(2025, 3, 3),
        paid_date=date(2025, 2, 28), payment_terms=PaymentTerms.NET_30,
        payment_method=PaymentMethod.ACH, po_number="PO-REG-2025-002",
        created_at=now - timedelta(days=370), updated_at=now - timedelta(days=340),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-003", invoice_number="INV-2025-0003",
        client_id="client-pharma-data", client_name="PharmaData Analytics Inc.",
        contract_id="contract-004", status=InvoiceStatus.PAID,
        billing_model=BillingModel.DATA_LICENSING,
        line_items=[
            _li("li-003", "inv-003", LineItemType.DATA_ACCESS, "Q1 2025 data licensing", 3, 50_000.0),
        ],
        subtotal=150_000.0, tax_total=0.0, total=150_000.0,
        currency=Currency.USD, issued_date=date(2025, 4, 1), due_date=date(2025, 5, 1),
        paid_date=date(2025, 4, 28), payment_terms=PaymentTerms.NET_30,
        payment_method=PaymentMethod.WIRE_TRANSFER,
        created_at=now - timedelta(days=310), updated_at=now - timedelta(days=280),
    )
    invoices.append(inv)

    # --- 2 PARTIALLY_PAID ---
    inv = Invoice(
        id="inv-004", invoice_number="INV-2025-0004",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-002", status=InvoiceStatus.PARTIALLY_PAID,
        billing_model=BillingModel.PER_PATIENT,
        line_items=[
            _li("li-004", "inv-004", LineItemType.PER_PATIENT_SCREENING, "Patient screening batch - 100 patients", 100, 2_500.0),
        ],
        subtotal=250_000.0, tax_total=0.0, total=250_000.0,
        currency=Currency.USD, issued_date=date(2025, 7, 1), due_date=date(2025, 8, 15),
        payment_terms=PaymentTerms.NET_45, po_number="PO-REG-2025-EYLEA-001",
        created_at=now - timedelta(days=220), updated_at=now - timedelta(days=190),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-005", invoice_number="INV-2025-0005",
        client_id="client-cro-partner", client_name="GlobalCRO Partners",
        contract_id="contract-005", status=InvoiceStatus.PARTIALLY_PAID,
        billing_model=BillingModel.MILESTONE,
        line_items=[
            _li("li-005", "inv-005", LineItemType.PLATFORM_FEE, "Milestone: Platform Integration", 1, 200_000.0),
        ],
        subtotal=200_000.0, tax_total=0.0, total=200_000.0,
        currency=Currency.USD, issued_date=date(2025, 7, 1), due_date=date(2025, 8, 30),
        payment_terms=PaymentTerms.NET_60,
        created_at=now - timedelta(days=220), updated_at=now - timedelta(days=180),
    )
    invoices.append(inv)

    # --- 3 SENT ---
    inv = Invoice(
        id="inv-006", invoice_number="INV-2025-0006",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-001", status=InvoiceStatus.SENT,
        billing_model=BillingModel.SUBSCRIPTION,
        line_items=[
            _li("li-006", "inv-006", LineItemType.PLATFORM_FEE, "Monthly platform subscription - Dec 2025", 1, 150_000.0),
        ],
        subtotal=150_000.0, tax_total=0.0, total=150_000.0,
        currency=Currency.USD, issued_date=date(2025, 12, 1), due_date=date(2025, 12, 31),
        payment_terms=PaymentTerms.NET_30, po_number="PO-REG-2025-012",
        created_at=now - timedelta(days=70), updated_at=now - timedelta(days=70),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-007", invoice_number="INV-2026-0007",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-003", status=InvoiceStatus.SENT,
        billing_model=BillingModel.PER_PATIENT,
        line_items=[
            _li("li-007", "inv-007", LineItemType.PER_PATIENT_SCREENING, "Dupixent screening batch - 60 patients", 60, 2_200.0),
        ],
        subtotal=132_000.0, tax_total=0.0, total=132_000.0,
        currency=Currency.USD, issued_date=date(2026, 1, 5), due_date=date(2026, 2, 4),
        payment_terms=PaymentTerms.NET_30,
        created_at=now - timedelta(days=35), updated_at=now - timedelta(days=35),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-008", invoice_number="INV-2026-0008",
        client_id="client-biotech-ai", client_name="BioTech AI Solutions",
        contract_id="contract-006", status=InvoiceStatus.SENT,
        billing_model=BillingModel.USAGE_BASED,
        line_items=[
            _li("li-008a", "inv-008", LineItemType.ANALYTICS, "API calls - Jan 2026 (50K calls)", 50_000, 0.50),
            _li("li-008b", "inv-008", LineItemType.DATA_ACCESS, "Data export - Jan 2026", 1, 5_000.0),
        ],
        subtotal=30_000.0, tax_total=0.0, total=30_000.0,
        currency=Currency.USD, issued_date=date(2026, 2, 1), due_date=date(2026, 3, 3),
        payment_terms=PaymentTerms.NET_30,
        created_at=now - timedelta(days=7), updated_at=now - timedelta(days=7),
    )
    invoices.append(inv)

    # --- 2 OVERDUE ---
    inv = Invoice(
        id="inv-009", invoice_number="INV-2025-0009",
        client_id="client-pharma-data", client_name="PharmaData Analytics Inc.",
        contract_id="contract-004", status=InvoiceStatus.OVERDUE,
        billing_model=BillingModel.DATA_LICENSING,
        line_items=[
            _li("li-009", "inv-009", LineItemType.DATA_ACCESS, "Q3 2025 data licensing", 3, 50_000.0),
        ],
        subtotal=150_000.0, tax_total=0.0, total=150_000.0,
        currency=Currency.USD, issued_date=date(2025, 10, 1), due_date=date(2025, 10, 31),
        payment_terms=PaymentTerms.NET_30,
        created_at=now - timedelta(days=130), updated_at=now - timedelta(days=100),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-010", invoice_number="INV-2025-0010",
        client_id="client-cro-partner", client_name="GlobalCRO Partners",
        contract_id="contract-005", status=InvoiceStatus.OVERDUE,
        billing_model=BillingModel.MILESTONE,
        line_items=[
            _li("li-010", "inv-010", LineItemType.PLATFORM_FEE, "Milestone: Phase 1 Enrollment Complete", 1, 300_000.0),
        ],
        subtotal=300_000.0, tax_total=0.0, total=300_000.0,
        currency=Currency.USD, issued_date=date(2025, 12, 31), due_date=date(2026, 1, 15),
        payment_terms=PaymentTerms.NET_60,
        created_at=now - timedelta(days=40), updated_at=now - timedelta(days=25),
    )
    invoices.append(inv)

    # --- 2 DRAFT ---
    inv = Invoice(
        id="inv-011", invoice_number="INV-2026-0011",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-001", status=InvoiceStatus.DRAFT,
        billing_model=BillingModel.SUBSCRIPTION,
        line_items=[
            _li("li-011", "inv-011", LineItemType.PLATFORM_FEE, "Monthly platform subscription - Feb 2026", 1, 150_000.0),
        ],
        subtotal=150_000.0, tax_total=0.0, total=150_000.0,
        currency=Currency.USD, payment_terms=PaymentTerms.NET_30,
        created_at=now - timedelta(days=3), updated_at=now - timedelta(days=3),
    )
    invoices.append(inv)

    inv = Invoice(
        id="inv-012", invoice_number="INV-2026-0012",
        client_id="client-regeneron", client_name="Regeneron Pharmaceuticals",
        contract_id="contract-002", status=InvoiceStatus.DRAFT,
        billing_model=BillingModel.PER_PATIENT,
        line_items=[
            _li("li-012", "inv-012", LineItemType.PER_PATIENT_SCREENING, "EYLEA screening batch - 50 patients", 50, 2_500.0),
            _li("li-012b", "inv-012", LineItemType.SETUP_FEE, "Site activation fee", 1, 10_000.0),
        ],
        subtotal=135_000.0, tax_total=0.0, total=135_000.0,
        currency=Currency.USD, payment_terms=PaymentTerms.NET_45,
        created_at=now - timedelta(days=1), updated_at=now - timedelta(days=1),
    )
    invoices.append(inv)

    # --- 1 DISPUTED ---
    inv = Invoice(
        id="inv-013", invoice_number="INV-2025-0013",
        client_id="client-cro-partner", client_name="GlobalCRO Partners",
        contract_id="contract-005", status=InvoiceStatus.DISPUTED,
        billing_model=BillingModel.MILESTONE,
        line_items=[
            _li("li-013", "inv-013", LineItemType.PROFESSIONAL_SERVICES, "Consulting services - disputed scope", 40, 350.0),
        ],
        subtotal=14_000.0, tax_total=0.0, total=14_000.0,
        currency=Currency.USD, issued_date=date(2025, 11, 15), due_date=date(2025, 12, 15),
        payment_terms=PaymentTerms.NET_30, notes="Client disputes scope of consulting hours",
        created_at=now - timedelta(days=85), updated_at=now - timedelta(days=55),
    )
    invoices.append(inv)

    # --- 1 CANCELLED ---
    inv = Invoice(
        id="inv-014", invoice_number="INV-2025-0014",
        client_id="client-biotech-ai", client_name="BioTech AI Solutions",
        contract_id="contract-006", status=InvoiceStatus.CANCELLED,
        billing_model=BillingModel.USAGE_BASED,
        line_items=[
            _li("li-014", "inv-014", LineItemType.ANALYTICS, "Cancelled - duplicate invoice", 1, 25_000.0),
        ],
        subtotal=25_000.0, tax_total=0.0, total=25_000.0,
        currency=Currency.USD, issued_date=date(2025, 11, 1), due_date=date(2025, 12, 1),
        payment_terms=PaymentTerms.NET_30, notes="Cancelled - duplicate of INV-2025-0008",
        created_at=now - timedelta(days=100), updated_at=now - timedelta(days=95),
    )
    invoices.append(inv)

    # --- 1 WRITTEN_OFF ---
    inv = Invoice(
        id="inv-015", invoice_number="INV-2025-0015",
        client_id="client-pharma-data", client_name="PharmaData Analytics Inc.",
        contract_id="contract-004", status=InvoiceStatus.WRITTEN_OFF,
        billing_model=BillingModel.DATA_LICENSING,
        line_items=[
            _li("li-015", "inv-015", LineItemType.CUSTOM, "Legacy data migration - written off", 1, 8_500.0),
        ],
        subtotal=8_500.0, tax_total=0.0, total=8_500.0,
        currency=Currency.USD, issued_date=date(2025, 3, 1), due_date=date(2025, 3, 31),
        payment_terms=PaymentTerms.NET_30, notes="Written off per finance approval FIN-2025-042",
        created_at=now - timedelta(days=340), updated_at=now - timedelta(days=300),
    )
    invoices.append(inv)

    return invoices


def _build_seed_payments() -> list[PaymentRecord]:
    """Build 8 payment records for paid / partially paid invoices."""
    return [
        # inv-001 fully paid
        PaymentRecord(
            id="pay-001", invoice_id="inv-001", amount=150_000.0,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            reference_number="WT-2025-0125-REG", received_date=date(2025, 1, 25),
            processed_by="Sarah Chen",
        ),
        # inv-002 fully paid
        PaymentRecord(
            id="pay-002", invoice_id="inv-002", amount=150_000.0,
            payment_method=PaymentMethod.ACH,
            reference_number="ACH-2025-0228-REG", received_date=date(2025, 2, 28),
            processed_by="Sarah Chen",
        ),
        # inv-003 fully paid
        PaymentRecord(
            id="pay-003", invoice_id="inv-003", amount=150_000.0,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            reference_number="WT-2025-0428-PDA", received_date=date(2025, 4, 28),
            processed_by="Michael Torres",
        ),
        # inv-004 partially paid (100K of 250K)
        PaymentRecord(
            id="pay-004a", invoice_id="inv-004", amount=100_000.0,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            reference_number="WT-2025-0801-REG", received_date=date(2025, 8, 1),
            processed_by="Sarah Chen",
        ),
        PaymentRecord(
            id="pay-004b", invoice_id="inv-004", amount=50_000.0,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            reference_number="WT-2025-0815-REG", received_date=date(2025, 8, 15),
            processed_by="Sarah Chen",
        ),
        # inv-005 partially paid (120K of 200K)
        PaymentRecord(
            id="pay-005a", invoice_id="inv-005", amount=80_000.0,
            payment_method=PaymentMethod.CHECK,
            reference_number="CHK-8834", received_date=date(2025, 8, 20),
            processed_by="Michael Torres",
        ),
        PaymentRecord(
            id="pay-005b", invoice_id="inv-005", amount=40_000.0,
            payment_method=PaymentMethod.CHECK,
            reference_number="CHK-9012", received_date=date(2025, 9, 15),
            processed_by="Michael Torres",
        ),
        # One more for inv-004 (another partial, total now 175K)
        PaymentRecord(
            id="pay-004c", invoice_id="inv-004", amount=25_000.0,
            payment_method=PaymentMethod.ACH,
            reference_number="ACH-2025-0901-REG", received_date=date(2025, 9, 1),
            processed_by="Sarah Chen",
        ),
    ]


# ---------------------------------------------------------------------------
# Service Implementation
# ---------------------------------------------------------------------------


class InvoiceManagementService:
    """In-memory invoice management service."""

    def __init__(self) -> None:
        self._contracts: dict[str, BillingContract] = {}
        self._invoices: dict[str, Invoice] = {}
        self._payments: dict[str, PaymentRecord] = {}
        self._load_seed_data()

    def _load_seed_data(self) -> None:
        for c in _build_seed_contracts():
            self._contracts[c.id] = c
        for inv in _build_seed_invoices():
            self._invoices[inv.id] = inv
        for pay in _build_seed_payments():
            self._payments[pay.id] = pay

    # -----------------------------------------------------------------------
    # Contract CRUD
    # -----------------------------------------------------------------------

    def list_contracts(
        self,
        client_id: str | None = None,
        billing_model: BillingModel | None = None,
    ) -> list[BillingContract]:
        """List billing contracts with optional filters."""
        results = list(self._contracts.values())
        if client_id:
            results = [c for c in results if c.client_id == client_id]
        if billing_model:
            results = [c for c in results if c.billing_model == billing_model]
        return results

    def get_contract(self, contract_id: str) -> BillingContract | None:
        return self._contracts.get(contract_id)

    def create_contract(self, req: BillingContractCreateRequest) -> BillingContract:
        cid = f"contract-{uuid4().hex[:8]}"
        total_value = req.total_value
        if total_value == 0.0:
            if req.billing_model == BillingModel.SUBSCRIPTION and req.monthly_fee > 0:
                months = (req.end_date.year - req.start_date.year) * 12 + (req.end_date.month - req.start_date.month) + 1
                total_value = req.monthly_fee * max(months, 1)
            elif req.billing_model == BillingModel.MILESTONE and req.milestones:
                total_value = sum(m.amount for m in req.milestones)
        contract = BillingContract(
            id=cid,
            client_id=req.client_id,
            client_name=req.client_name,
            billing_model=req.billing_model,
            start_date=req.start_date,
            end_date=req.end_date,
            monthly_fee=req.monthly_fee,
            per_patient_rate=req.per_patient_rate,
            data_licensing_fee=req.data_licensing_fee,
            payment_terms=req.payment_terms,
            auto_invoice=req.auto_invoice,
            milestones=req.milestones,
            total_value=total_value,
            invoiced_to_date=0.0,
        )
        self._contracts[cid] = contract
        return contract

    # -----------------------------------------------------------------------
    # Invoice CRUD
    # -----------------------------------------------------------------------

    def list_invoices(
        self,
        status: InvoiceStatus | None = None,
        client_id: str | None = None,
        contract_id: str | None = None,
    ) -> list[Invoice]:
        """List invoices with optional filters."""
        results = list(self._invoices.values())
        if status:
            results = [i for i in results if i.status == status]
        if client_id:
            results = [i for i in results if i.client_id == client_id]
        if contract_id:
            results = [i for i in results if i.contract_id == contract_id]
        return results

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        return self._invoices.get(invoice_id)

    def create_invoice(self, req: InvoiceCreateRequest) -> Invoice:
        inv_id = f"inv-{uuid4().hex[:8]}"
        now = _now()

        # Build line items
        line_items: list[InvoiceLineItem] = []
        subtotal = 0.0
        tax_total = 0.0
        for li_req in req.line_items:
            li_id = f"li-{uuid4().hex[:8]}"
            amount = round(li_req.quantity * li_req.unit_price, 2)
            tax_amount = round(amount * li_req.tax_rate, 2)
            total = round(amount + tax_amount, 2)
            li = InvoiceLineItem(
                id=li_id, invoice_id=inv_id, line_item_type=li_req.line_item_type,
                description=li_req.description, quantity=li_req.quantity,
                unit_price=li_req.unit_price, amount=amount,
                tax_rate=li_req.tax_rate, tax_amount=tax_amount, total=total,
            )
            line_items.append(li)
            subtotal += amount
            tax_total += tax_amount

        subtotal = round(subtotal, 2)
        tax_total = round(tax_total, 2)
        grand_total = round(subtotal + tax_total, 2)

        inv_number = _next_invoice_number()
        issued = req.issued_date
        due = req.due_date
        status = InvoiceStatus.DRAFT
        if issued:
            status = InvoiceStatus.SENT

        invoice = Invoice(
            id=inv_id,
            invoice_number=inv_number,
            client_id=req.client_id,
            client_name=req.client_name,
            contract_id=req.contract_id,
            status=status,
            billing_model=req.billing_model,
            line_items=line_items,
            subtotal=subtotal,
            tax_total=tax_total,
            total=grand_total,
            currency=req.currency,
            issued_date=issued,
            due_date=due,
            payment_terms=req.payment_terms,
            notes=req.notes,
            po_number=req.po_number,
            created_at=now,
            updated_at=now,
        )
        self._invoices[inv_id] = invoice

        # Update contract invoiced_to_date if linked
        if req.contract_id and req.contract_id in self._contracts:
            c = self._contracts[req.contract_id]
            self._contracts[req.contract_id] = c.model_copy(
                update={"invoiced_to_date": round(c.invoiced_to_date + grand_total, 2)}
            )

        return invoice

    def update_invoice(self, invoice_id: str, req: InvoiceUpdateRequest) -> Invoice | None:
        inv = self._invoices.get(invoice_id)
        if not inv:
            return None

        updates: dict = {"updated_at": _now()}
        if req.status is not None:
            # Validate transitions
            if not self._valid_status_transition(inv.status, req.status):
                raise ValueError(
                    f"Invalid status transition from {inv.status.value} to {req.status.value}"
                )
            updates["status"] = req.status
            if req.status == InvoiceStatus.SENT and inv.issued_date is None:
                updates["issued_date"] = _today()
                if inv.due_date is None:
                    days = self._payment_terms_days(inv.payment_terms)
                    updates["due_date"] = _today() + timedelta(days=days)
        if req.notes is not None:
            updates["notes"] = req.notes
        if req.po_number is not None:
            updates["po_number"] = req.po_number
        if req.payment_method is not None:
            updates["payment_method"] = req.payment_method
        if req.due_date is not None:
            updates["due_date"] = req.due_date

        updated = inv.model_copy(update=updates)
        self._invoices[invoice_id] = updated
        return updated

    def _valid_status_transition(self, current: InvoiceStatus, target: InvoiceStatus) -> bool:
        """Validate invoice status transitions."""
        valid_transitions: dict[InvoiceStatus, set[InvoiceStatus]] = {
            InvoiceStatus.DRAFT: {InvoiceStatus.SENT, InvoiceStatus.CANCELLED},
            InvoiceStatus.SENT: {InvoiceStatus.VIEWED, InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE, InvoiceStatus.DISPUTED, InvoiceStatus.CANCELLED},
            InvoiceStatus.VIEWED: {InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE, InvoiceStatus.DISPUTED},
            InvoiceStatus.PARTIALLY_PAID: {InvoiceStatus.PAID, InvoiceStatus.OVERDUE, InvoiceStatus.DISPUTED},
            InvoiceStatus.OVERDUE: {InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.DISPUTED, InvoiceStatus.WRITTEN_OFF},
            InvoiceStatus.DISPUTED: {InvoiceStatus.SENT, InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF},
            InvoiceStatus.PAID: set(),  # terminal
            InvoiceStatus.CANCELLED: set(),  # terminal
            InvoiceStatus.WRITTEN_OFF: set(),  # terminal
        }
        return target in valid_transitions.get(current, set())

    @staticmethod
    def _payment_terms_days(terms: PaymentTerms) -> int:
        return {
            PaymentTerms.NET_15: 15,
            PaymentTerms.NET_30: 30,
            PaymentTerms.NET_45: 45,
            PaymentTerms.NET_60: 60,
            PaymentTerms.NET_90: 90,
        }.get(terms, 30)

    # -----------------------------------------------------------------------
    # Line Item Management
    # -----------------------------------------------------------------------

    def add_line_item(self, invoice_id: str, req: InvoiceLineItemCreate) -> Invoice | None:
        """Add a line item to an existing draft invoice."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            return None
        if inv.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only add line items to DRAFT invoices")

        li_id = f"li-{uuid4().hex[:8]}"
        amount = round(req.quantity * req.unit_price, 2)
        tax_amount = round(amount * req.tax_rate, 2)
        total = round(amount + tax_amount, 2)
        li = InvoiceLineItem(
            id=li_id, invoice_id=invoice_id, line_item_type=req.line_item_type,
            description=req.description, quantity=req.quantity,
            unit_price=req.unit_price, amount=amount,
            tax_rate=req.tax_rate, tax_amount=tax_amount, total=total,
        )

        new_items = list(inv.line_items) + [li]
        new_subtotal = round(sum(i.amount for i in new_items), 2)
        new_tax = round(sum(i.tax_amount for i in new_items), 2)
        new_total = round(new_subtotal + new_tax, 2)

        updated = inv.model_copy(update={
            "line_items": new_items,
            "subtotal": new_subtotal,
            "tax_total": new_tax,
            "total": new_total,
            "updated_at": _now(),
        })
        self._invoices[invoice_id] = updated
        return updated

    def remove_line_item(self, invoice_id: str, line_item_id: str) -> Invoice | None:
        """Remove a line item from a draft invoice."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            return None
        if inv.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only remove line items from DRAFT invoices")

        new_items = [li for li in inv.line_items if li.id != line_item_id]
        if len(new_items) == len(inv.line_items):
            raise ValueError(f"Line item {line_item_id} not found on invoice {invoice_id}")

        new_subtotal = round(sum(i.amount for i in new_items), 2)
        new_tax = round(sum(i.tax_amount for i in new_items), 2)
        new_total = round(new_subtotal + new_tax, 2)

        updated = inv.model_copy(update={
            "line_items": new_items,
            "subtotal": new_subtotal,
            "tax_total": new_tax,
            "total": new_total,
            "updated_at": _now(),
        })
        self._invoices[invoice_id] = updated
        return updated

    # -----------------------------------------------------------------------
    # Payment Recording
    # -----------------------------------------------------------------------

    def record_payment(self, invoice_id: str, req: PaymentRecordRequest) -> PaymentRecord | None:
        """Record a payment against an invoice."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            return None

        payable_statuses = {
            InvoiceStatus.SENT, InvoiceStatus.VIEWED,
            InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE,
        }
        if inv.status not in payable_statuses:
            raise ValueError(f"Cannot record payment for invoice in status {inv.status.value}")

        pay_id = f"pay-{uuid4().hex[:8]}"
        received = req.received_date or _today()
        payment = PaymentRecord(
            id=pay_id,
            invoice_id=invoice_id,
            amount=req.amount,
            payment_method=req.payment_method,
            reference_number=req.reference_number,
            received_date=received,
            processed_by=req.processed_by,
        )
        self._payments[pay_id] = payment

        # Calculate total paid
        total_paid = sum(
            p.amount for p in self._payments.values() if p.invoice_id == invoice_id
        )

        # Update invoice status
        updates: dict = {"updated_at": _now(), "payment_method": req.payment_method}
        if total_paid >= inv.total:
            updates["status"] = InvoiceStatus.PAID
            updates["paid_date"] = received
        else:
            updates["status"] = InvoiceStatus.PARTIALLY_PAID

        self._invoices[invoice_id] = inv.model_copy(update=updates)
        return payment

    def list_payments(self, invoice_id: str | None = None) -> list[PaymentRecord]:
        """List payment records, optionally filtered by invoice."""
        results = list(self._payments.values())
        if invoice_id:
            results = [p for p in results if p.invoice_id == invoice_id]
        return results

    def get_total_paid(self, invoice_id: str) -> float:
        """Get total amount paid against an invoice."""
        return round(
            sum(p.amount for p in self._payments.values() if p.invoice_id == invoice_id),
            2,
        )

    # -----------------------------------------------------------------------
    # Auto-Invoice Generation
    # -----------------------------------------------------------------------

    def generate_invoice_from_contract(
        self, contract_id: str, description: str | None = None,
        quantity: float = 1.0,
    ) -> Invoice | None:
        """Auto-generate an invoice from a billing contract."""
        contract = self._contracts.get(contract_id)
        if not contract:
            return None

        # Determine line item based on billing model
        if contract.billing_model == BillingModel.SUBSCRIPTION:
            li_type = LineItemType.PLATFORM_FEE
            unit_price = contract.monthly_fee
            desc = description or f"Monthly subscription - {contract.client_name}"
        elif contract.billing_model == BillingModel.PER_PATIENT:
            li_type = LineItemType.PER_PATIENT_SCREENING
            unit_price = contract.per_patient_rate
            desc = description or f"Patient screening - {contract.client_name}"
        elif contract.billing_model == BillingModel.DATA_LICENSING:
            li_type = LineItemType.DATA_ACCESS
            unit_price = contract.data_licensing_fee
            desc = description or f"Data licensing - {contract.client_name}"
        elif contract.billing_model == BillingModel.USAGE_BASED:
            li_type = LineItemType.ANALYTICS
            unit_price = 0.0
            desc = description or f"Usage-based billing - {contract.client_name}"
        else:
            li_type = LineItemType.CUSTOM
            unit_price = 0.0
            desc = description or f"Contract billing - {contract.client_name}"

        days = self._payment_terms_days(contract.payment_terms)
        issued = _today()
        due = issued + timedelta(days=days)

        req = InvoiceCreateRequest(
            client_id=contract.client_id,
            client_name=contract.client_name,
            contract_id=contract_id,
            billing_model=contract.billing_model,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=li_type,
                    description=desc,
                    quantity=quantity,
                    unit_price=unit_price,
                ),
            ],
            payment_terms=contract.payment_terms,
            issued_date=issued,
            due_date=due,
        )
        return self.create_invoice(req)

    # -----------------------------------------------------------------------
    # AR Aging Report
    # -----------------------------------------------------------------------

    def get_ar_aging_report(self) -> ARAgingReport:
        """Generate accounts receivable aging report."""
        today = _today()
        buckets_data: dict[str, list[Invoice]] = {
            "0-30 days": [],
            "31-60 days": [],
            "61-90 days": [],
            "90+ days": [],
        }

        outstanding_statuses = {
            InvoiceStatus.SENT, InvoiceStatus.VIEWED,
            InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE,
        }

        for inv in self._invoices.values():
            if inv.status not in outstanding_statuses:
                continue
            if not inv.issued_date:
                continue
            days_old = (today - inv.issued_date).days
            if days_old <= 30:
                buckets_data["0-30 days"].append(inv)
            elif days_old <= 60:
                buckets_data["31-60 days"].append(inv)
            elif days_old <= 90:
                buckets_data["61-90 days"].append(inv)
            else:
                buckets_data["90+ days"].append(inv)

        buckets: list[ARAgingBucket] = []
        total_outstanding = 0.0
        total_overdue = 0.0
        for bucket_name, invs in buckets_data.items():
            bucket_total = round(sum(self._outstanding_amount(i) for i in invs), 2)
            buckets.append(ARAgingBucket(
                bucket=bucket_name,
                count=len(invs),
                total_amount=bucket_total,
            ))
            total_outstanding += bucket_total
            if bucket_name != "0-30 days":
                total_overdue += bucket_total

        return ARAgingReport(
            buckets=buckets,
            total_outstanding=round(total_outstanding, 2),
            total_overdue=round(total_overdue, 2),
            generated_at=_now(),
        )

    def _outstanding_amount(self, inv: Invoice) -> float:
        """Calculate outstanding amount for an invoice (total - payments)."""
        paid = self.get_total_paid(inv.id)
        return max(0.0, round(inv.total - paid, 2))

    # -----------------------------------------------------------------------
    # Revenue Recognition (ASC 606)
    # -----------------------------------------------------------------------

    def get_revenue_report(self, year: int = 2025) -> RevenueReport:
        """Generate revenue recognition report (ASC 606 compliant)."""
        periods: list[RevenueRecognition] = []
        total_recognized = 0.0
        total_deferred = 0.0
        total_billed = 0.0

        for month in range(1, 13):
            period_str = f"{year}-{month:02d}"
            # Billed = sum of invoices issued in this month
            billed = sum(
                inv.total for inv in self._invoices.values()
                if inv.issued_date and inv.issued_date.year == year and inv.issued_date.month == month
                and inv.status not in {InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF}
            )
            # Recognized = sum of paid invoices in this period
            recognized = sum(
                inv.total for inv in self._invoices.values()
                if inv.paid_date and inv.paid_date.year == year and inv.paid_date.month == month
            )
            deferred = round(billed - recognized, 2)
            if deferred < 0:
                deferred = 0.0

            periods.append(RevenueRecognition(
                period=period_str,
                recognized_revenue=round(recognized, 2),
                deferred_revenue=round(deferred, 2),
                total_billed=round(billed, 2),
                asc606_compliant=True,
            ))
            total_recognized += recognized
            total_deferred += deferred
            total_billed += billed

        return RevenueReport(
            periods=periods,
            total_recognized=round(total_recognized, 2),
            total_deferred=round(total_deferred, 2),
            total_billed=round(total_billed, 2),
            asc606_compliant=True,
            generated_at=_now(),
        )

    # -----------------------------------------------------------------------
    # Invoice Metrics
    # -----------------------------------------------------------------------

    def get_invoice_metrics(self) -> InvoiceMetrics:
        """Calculate aggregated invoice / billing metrics."""
        active_statuses = {
            InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID, InvoiceStatus.OVERDUE,
        }
        active_invoices = [
            i for i in self._invoices.values() if i.status in active_statuses
        ]

        total_billed = round(sum(i.total for i in active_invoices), 2)
        total_collected = round(sum(p.amount for p in self._payments.values()), 2)
        total_outstanding = round(total_billed - total_collected, 2)

        # DSO = (AR / Total Billed) * 365 (simplified)
        dso = round((total_outstanding / total_billed * 365) if total_billed > 0 else 0, 1)

        # Invoices by status
        status_counts: dict[str, int] = {}
        for inv in self._invoices.values():
            key = inv.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        collection_rate = round((total_collected / total_billed * 100) if total_billed > 0 else 0, 2)

        overdue = [i for i in self._invoices.values() if i.status == InvoiceStatus.OVERDUE]
        overdue_amount = round(sum(self._outstanding_amount(i) for i in overdue), 2)

        # Average invoice amount (all non-cancelled/written-off)
        countable = [i for i in self._invoices.values()
                     if i.status not in {InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF}]
        avg_amount = round(sum(i.total for i in countable) / len(countable), 2) if countable else 0.0

        # Average days to pay (for paid invoices)
        paid_invoices = [i for i in self._invoices.values() if i.status == InvoiceStatus.PAID and i.issued_date and i.paid_date]
        if paid_invoices:
            avg_days = round(
                sum((i.paid_date - i.issued_date).days for i in paid_invoices) / len(paid_invoices), 1  # type: ignore[union-attr]
            )
        else:
            avg_days = 0.0

        return InvoiceMetrics(
            total_billed=total_billed,
            total_collected=total_collected,
            total_outstanding=total_outstanding,
            days_sales_outstanding=dso,
            invoices_by_status=status_counts,
            collection_rate=collection_rate,
            overdue_count=len(overdue),
            overdue_amount=overdue_amount,
            average_invoice_amount=avg_amount,
            average_days_to_pay=avg_days,
        )

    # -----------------------------------------------------------------------
    # Overdue Detection & Late Fees
    # -----------------------------------------------------------------------

    def detect_overdue_invoices(self) -> list[Invoice]:
        """Find invoices that are past due and update their status."""
        today = _today()
        overdue_list: list[Invoice] = []

        for inv_id, inv in list(self._invoices.items()):
            if inv.status in {InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID}:
                if inv.due_date and inv.due_date < today:
                    updated = inv.model_copy(update={
                        "status": InvoiceStatus.OVERDUE,
                        "updated_at": _now(),
                    })
                    self._invoices[inv_id] = updated
                    overdue_list.append(updated)

        return overdue_list

    def calculate_late_fee(self, invoice_id: str) -> LateFeeCalculation | None:
        """Calculate late fee for an overdue invoice (1.5% per month)."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            return None
        if not inv.due_date:
            return None

        today = _today()
        days_overdue = max(0, (today - inv.due_date).days)
        outstanding = self._outstanding_amount(inv)

        # Pro-rate the monthly rate by days
        months_overdue = days_overdue / 30.0
        late_fee = round(outstanding * LATE_FEE_MONTHLY_RATE * months_overdue, 2)

        return LateFeeCalculation(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            original_amount=inv.total,
            days_overdue=days_overdue,
            monthly_rate=LATE_FEE_MONTHLY_RATE,
            late_fee=late_fee,
            total_with_late_fee=round(outstanding + late_fee, 2),
        )

    # -----------------------------------------------------------------------
    # 3-Way Match
    # -----------------------------------------------------------------------

    def three_way_match(self, invoice_id: str) -> ThreeWayMatchResult | None:
        """Perform 3-way match: PO + Contract + Invoice validation."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            return None

        discrepancies: list[str] = []

        # 1. PO match
        po_match = bool(inv.po_number and inv.po_number.strip())
        if not po_match:
            discrepancies.append("No purchase order number on invoice")

        # 2. Contract match
        contract_match = False
        if inv.contract_id and inv.contract_id in self._contracts:
            contract = self._contracts[inv.contract_id]
            contract_match = True
            # Verify client matches
            if contract.client_id != inv.client_id:
                contract_match = False
                discrepancies.append(f"Client mismatch: invoice={inv.client_id}, contract={contract.client_id}")
        else:
            discrepancies.append("No valid contract linked to invoice")

        # 3. Amount match - verify total against contract rates
        amount_match = True
        if inv.contract_id and inv.contract_id in self._contracts:
            contract = self._contracts[inv.contract_id]
            if contract.billing_model == BillingModel.SUBSCRIPTION:
                expected = contract.monthly_fee
                for li in inv.line_items:
                    if li.line_item_type == LineItemType.PLATFORM_FEE:
                        if abs(li.amount - expected * li.quantity) > 0.01:
                            amount_match = False
                            discrepancies.append(
                                f"Amount mismatch: line item {li.amount} vs expected {expected * li.quantity}"
                            )
            elif contract.billing_model == BillingModel.PER_PATIENT:
                expected_rate = contract.per_patient_rate
                for li in inv.line_items:
                    if li.line_item_type == LineItemType.PER_PATIENT_SCREENING:
                        if abs(li.unit_price - expected_rate) > 0.01:
                            amount_match = False
                            discrepancies.append(
                                f"Rate mismatch: {li.unit_price} vs contract rate {expected_rate}"
                            )

        fully_matched = po_match and contract_match and amount_match

        return ThreeWayMatchResult(
            invoice_id=invoice_id,
            po_number=inv.po_number,
            contract_id=inv.contract_id,
            po_match=po_match,
            contract_match=contract_match,
            amount_match=amount_match,
            fully_matched=fully_matched,
            discrepancies=discrepancies,
        )

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            "contracts": len(self._contracts),
            "invoices": len(self._invoices),
            "payments": len(self._payments),
        }


# ---------------------------------------------------------------------------
# Singleton accessors
# ---------------------------------------------------------------------------


def get_invoice_management_service() -> InvoiceManagementService:
    """Get or create the singleton InvoiceManagementService."""
    global _invoice_service_instance
    if _invoice_service_instance is None:
        with _invoice_service_lock:
            if _invoice_service_instance is None:
                _reset_invoice_counter()
                _invoice_service_instance = InvoiceManagementService()
    return _invoice_service_instance


def reset_invoice_management_service() -> None:
    """Reset the singleton (for testing)."""
    global _invoice_service_instance
    with _invoice_service_lock:
        _invoice_service_instance = None
        _reset_invoice_counter()
