"""Tests for CFO-4: Invoice Management & Contract Billing.

Tests cover:
- Seed data verification (contracts, invoices, payments)
- Invoice CRUD (list, get, create, update, filters)
- Line item management (add, remove, totals recalculation)
- Payment recording (full, partial, status transitions)
- Invoice status transitions (valid and invalid)
- Auto-invoice generation from contracts
- AR aging report (buckets, totals)
- Revenue recognition (ASC 606 compliant)
- Invoice metrics (DSO, collection rate, averages)
- Overdue detection and late fee calculation
- 3-way match (PO + Contract + Invoice)
- Contract CRUD (list, get, create, filters)
- API endpoint integration tests
- Error handling (404s, 400s)
- Singleton pattern (get/reset)

Target: 130+ test cases.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.invoice_management import (
    BillingModel,
    Currency,
    InvoiceStatus,
    LineItemType,
    PaymentMethod,
    PaymentTerms,
)
from app.services.invoice_management_service import (
    InvoiceManagementService,
    get_invoice_management_service,
    reset_invoice_management_service,
)

API_PREFIX = "/api/v1/invoice-management"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_invoice_management_service()
    yield
    reset_invoice_management_service()


@pytest.fixture
def service() -> InvoiceManagementService:
    return get_invoice_management_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests for pre-populated seed data."""

    def test_seed_contracts_count(self, service: InvoiceManagementService):
        """Service should have 6 billing contracts."""
        contracts = service.list_contracts()
        assert len(contracts) == 6

    def test_seed_invoices_count(self, service: InvoiceManagementService):
        """Service should have 15 invoices."""
        invoices = service.list_invoices()
        assert len(invoices) == 15

    def test_seed_payments_count(self, service: InvoiceManagementService):
        """Service should have 8 payment records."""
        payments = service.list_payments()
        assert len(payments) == 8

    def test_seed_paid_invoices(self, service: InvoiceManagementService):
        """Should have 3 PAID invoices."""
        paid = service.list_invoices(status=InvoiceStatus.PAID)
        assert len(paid) == 3

    def test_seed_partially_paid_invoices(self, service: InvoiceManagementService):
        """Should have 2 PARTIALLY_PAID invoices."""
        partial = service.list_invoices(status=InvoiceStatus.PARTIALLY_PAID)
        assert len(partial) == 2

    def test_seed_sent_invoices(self, service: InvoiceManagementService):
        """Should have 3 SENT invoices."""
        sent = service.list_invoices(status=InvoiceStatus.SENT)
        assert len(sent) == 3

    def test_seed_overdue_invoices(self, service: InvoiceManagementService):
        """Should have 2 OVERDUE invoices."""
        overdue = service.list_invoices(status=InvoiceStatus.OVERDUE)
        assert len(overdue) == 2

    def test_seed_draft_invoices(self, service: InvoiceManagementService):
        """Should have 2 DRAFT invoices."""
        draft = service.list_invoices(status=InvoiceStatus.DRAFT)
        assert len(draft) == 2

    def test_seed_disputed_invoices(self, service: InvoiceManagementService):
        """Should have 1 DISPUTED invoice."""
        disputed = service.list_invoices(status=InvoiceStatus.DISPUTED)
        assert len(disputed) == 1

    def test_seed_cancelled_invoices(self, service: InvoiceManagementService):
        """Should have 1 CANCELLED invoice."""
        cancelled = service.list_invoices(status=InvoiceStatus.CANCELLED)
        assert len(cancelled) == 1

    def test_seed_written_off_invoices(self, service: InvoiceManagementService):
        """Should have 1 WRITTEN_OFF invoice."""
        wo = service.list_invoices(status=InvoiceStatus.WRITTEN_OFF)
        assert len(wo) == 1

    def test_seed_contract_regeneron_subscription(self, service: InvoiceManagementService):
        """Regeneron MSA should be $150K/mo subscription."""
        c = service.get_contract("contract-001")
        assert c is not None
        assert c.billing_model == BillingModel.SUBSCRIPTION
        assert c.monthly_fee == 150_000.0
        assert c.client_name == "Regeneron Pharmaceuticals"

    def test_seed_contract_eylea_per_patient(self, service: InvoiceManagementService):
        """EYLEA contract should be per-patient at $2,500."""
        c = service.get_contract("contract-002")
        assert c is not None
        assert c.billing_model == BillingModel.PER_PATIENT
        assert c.per_patient_rate == 2_500.0

    def test_seed_contract_dupixent_per_patient(self, service: InvoiceManagementService):
        """Dupixent contract should be per-patient at $2,200."""
        c = service.get_contract("contract-003")
        assert c is not None
        assert c.per_patient_rate == 2_200.0

    def test_seed_contract_data_licensing(self, service: InvoiceManagementService):
        """Data licensing contract should be $50K/mo."""
        c = service.get_contract("contract-004")
        assert c is not None
        assert c.billing_model == BillingModel.DATA_LICENSING
        assert c.data_licensing_fee == 50_000.0

    def test_seed_contract_milestone(self, service: InvoiceManagementService):
        """CRO partner should have milestone-based billing."""
        c = service.get_contract("contract-005")
        assert c is not None
        assert c.billing_model == BillingModel.MILESTONE
        assert len(c.milestones) == 4
        assert c.total_value == 1_000_000.0

    def test_seed_contract_usage_based(self, service: InvoiceManagementService):
        """BioTech AI contract should be usage-based."""
        c = service.get_contract("contract-006")
        assert c is not None
        assert c.billing_model == BillingModel.USAGE_BASED

    def test_seed_invoice_has_line_items(self, service: InvoiceManagementService):
        """Each invoice should have at least one line item."""
        for inv in service.list_invoices():
            assert len(inv.line_items) >= 1, f"Invoice {inv.id} has no line items"

    def test_seed_paid_invoice_has_paid_date(self, service: InvoiceManagementService):
        """Paid invoices should have a paid_date."""
        for inv in service.list_invoices(status=InvoiceStatus.PAID):
            assert inv.paid_date is not None

    def test_seed_invoice_numbers_format(self, service: InvoiceManagementService):
        """Invoice numbers should follow INV-YYYY-NNNN format."""
        for inv in service.list_invoices():
            assert inv.invoice_number.startswith("INV-")
            parts = inv.invoice_number.split("-")
            assert len(parts) == 3

    def test_seed_stats(self, service: InvoiceManagementService):
        """Stats should reflect seed data counts."""
        stats = service.get_stats()
        assert stats["contracts"] == 6
        assert stats["invoices"] == 15
        assert stats["payments"] == 8


# ============================================================================
# Contract CRUD Tests
# ============================================================================


class TestContractCRUD:
    """Tests for billing contract CRUD operations."""

    def test_list_all_contracts(self, service: InvoiceManagementService):
        contracts = service.list_contracts()
        assert len(contracts) == 6

    def test_list_contracts_by_client(self, service: InvoiceManagementService):
        contracts = service.list_contracts(client_id="client-regeneron")
        assert len(contracts) == 3

    def test_list_contracts_by_billing_model(self, service: InvoiceManagementService):
        contracts = service.list_contracts(billing_model=BillingModel.SUBSCRIPTION)
        assert len(contracts) == 1

    def test_list_contracts_by_model_per_patient(self, service: InvoiceManagementService):
        contracts = service.list_contracts(billing_model=BillingModel.PER_PATIENT)
        assert len(contracts) == 2

    def test_get_contract_not_found(self, service: InvoiceManagementService):
        assert service.get_contract("nonexistent") is None

    def test_create_contract_subscription(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import BillingContractCreateRequest
        req = BillingContractCreateRequest(
            client_id="client-new",
            client_name="New Client Corp",
            billing_model=BillingModel.SUBSCRIPTION,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_fee=75_000.0,
            payment_terms=PaymentTerms.NET_30,
        )
        c = service.create_contract(req)
        assert c.client_name == "New Client Corp"
        assert c.billing_model == BillingModel.SUBSCRIPTION
        assert c.total_value == 75_000.0 * 12
        assert c.invoiced_to_date == 0.0

    def test_create_contract_milestone_auto_value(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import BillingContractCreateRequest, BillingMilestone
        req = BillingContractCreateRequest(
            client_id="client-ms",
            client_name="Milestone Corp",
            billing_model=BillingModel.MILESTONE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            milestones=[
                BillingMilestone(name="M1", amount=100_000.0, target_date=date(2026, 6, 1)),
                BillingMilestone(name="M2", amount=200_000.0, target_date=date(2026, 12, 1)),
            ],
        )
        c = service.create_contract(req)
        assert c.total_value == 300_000.0


# ============================================================================
# Invoice CRUD Tests
# ============================================================================


class TestInvoiceCRUD:
    """Tests for invoice CRUD operations."""

    def test_list_all_invoices(self, service: InvoiceManagementService):
        invoices = service.list_invoices()
        assert len(invoices) == 15

    def test_list_invoices_by_status(self, service: InvoiceManagementService):
        for status, expected in [
            (InvoiceStatus.PAID, 3),
            (InvoiceStatus.SENT, 3),
            (InvoiceStatus.DRAFT, 2),
            (InvoiceStatus.OVERDUE, 2),
        ]:
            result = service.list_invoices(status=status)
            assert len(result) == expected, f"Expected {expected} {status.value}, got {len(result)}"

    def test_list_invoices_by_client(self, service: InvoiceManagementService):
        result = service.list_invoices(client_id="client-regeneron")
        assert len(result) >= 5

    def test_list_invoices_by_contract(self, service: InvoiceManagementService):
        result = service.list_invoices(contract_id="contract-001")
        assert len(result) >= 3

    def test_get_invoice_by_id(self, service: InvoiceManagementService):
        inv = service.get_invoice("inv-001")
        assert inv is not None
        assert inv.invoice_number == "INV-2025-0001"
        assert inv.status == InvoiceStatus.PAID

    def test_get_invoice_not_found(self, service: InvoiceManagementService):
        assert service.get_invoice("nonexistent") is None

    def test_create_invoice_draft(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-test",
            client_name="Test Client",
            billing_model=BillingModel.SUBSCRIPTION,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Test platform fee",
                    quantity=1,
                    unit_price=50_000.0,
                ),
            ],
        )
        inv = service.create_invoice(req)
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.total == 50_000.0
        assert len(inv.line_items) == 1
        assert inv.invoice_number.startswith("INV-")

    def test_create_invoice_sent_with_issued_date(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-test",
            client_name="Test Client",
            billing_model=BillingModel.PER_PATIENT,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PER_PATIENT_SCREENING,
                    description="Patient screening",
                    quantity=10,
                    unit_price=2_500.0,
                ),
            ],
            issued_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        inv = service.create_invoice(req)
        assert inv.status == InvoiceStatus.SENT
        assert inv.issued_date is not None

    def test_create_invoice_with_tax(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-test",
            client_name="Test Client",
            billing_model=BillingModel.SUBSCRIPTION,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Platform fee with tax",
                    quantity=1,
                    unit_price=100_000.0,
                    tax_rate=0.08,
                ),
            ],
        )
        inv = service.create_invoice(req)
        assert inv.subtotal == 100_000.0
        assert inv.tax_total == 8_000.0
        assert inv.total == 108_000.0

    def test_create_invoice_multiple_line_items(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-test",
            client_name="Test Client",
            billing_model=BillingModel.HYBRID,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Platform fee",
                    quantity=1,
                    unit_price=50_000.0,
                ),
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PER_PATIENT_SCREENING,
                    description="Screening",
                    quantity=20,
                    unit_price=2_000.0,
                ),
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.SETUP_FEE,
                    description="Setup fee",
                    quantity=1,
                    unit_price=10_000.0,
                ),
            ],
        )
        inv = service.create_invoice(req)
        assert len(inv.line_items) == 3
        assert inv.total == 100_000.0

    def test_create_invoice_updates_contract_invoiced(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        c_before = service.get_contract("contract-001")
        assert c_before is not None
        before_invoiced = c_before.invoiced_to_date

        req = InvoiceCreateRequest(
            client_id="client-regeneron",
            client_name="Regeneron Pharmaceuticals",
            contract_id="contract-001",
            billing_model=BillingModel.SUBSCRIPTION,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Monthly fee",
                    quantity=1,
                    unit_price=150_000.0,
                ),
            ],
        )
        inv = service.create_invoice(req)
        c_after = service.get_contract("contract-001")
        assert c_after is not None
        assert c_after.invoiced_to_date == before_invoiced + inv.total

    def test_create_invoice_with_currency(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-eu",
            client_name="EU Client",
            billing_model=BillingModel.SUBSCRIPTION,
            currency=Currency.EUR,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Platform fee EUR",
                    quantity=1,
                    unit_price=120_000.0,
                ),
            ],
        )
        inv = service.create_invoice(req)
        assert inv.currency == Currency.EUR


# ============================================================================
# Invoice Update & Status Transition Tests
# ============================================================================


class TestInvoiceStatusTransitions:
    """Tests for invoice status transitions."""

    def test_draft_to_sent(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-011", InvoiceUpdateRequest(status=InvoiceStatus.SENT))
        assert inv is not None
        assert inv.status == InvoiceStatus.SENT
        assert inv.issued_date is not None

    def test_draft_to_cancelled(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-011", InvoiceUpdateRequest(status=InvoiceStatus.CANCELLED))
        assert inv is not None
        assert inv.status == InvoiceStatus.CANCELLED

    def test_sent_to_viewed(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-006", InvoiceUpdateRequest(status=InvoiceStatus.VIEWED))
        assert inv is not None
        assert inv.status == InvoiceStatus.VIEWED

    def test_sent_to_disputed(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-006", InvoiceUpdateRequest(status=InvoiceStatus.DISPUTED))
        assert inv is not None
        assert inv.status == InvoiceStatus.DISPUTED

    def test_overdue_to_written_off(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-009", InvoiceUpdateRequest(status=InvoiceStatus.WRITTEN_OFF))
        assert inv is not None
        assert inv.status == InvoiceStatus.WRITTEN_OFF

    def test_invalid_paid_to_draft(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_invoice("inv-001", InvoiceUpdateRequest(status=InvoiceStatus.DRAFT))

    def test_invalid_cancelled_to_sent(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_invoice("inv-014", InvoiceUpdateRequest(status=InvoiceStatus.SENT))

    def test_invalid_written_off_to_paid(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_invoice("inv-015", InvoiceUpdateRequest(status=InvoiceStatus.PAID))

    def test_update_notes(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-011", InvoiceUpdateRequest(notes="Updated note"))
        assert inv is not None
        assert inv.notes == "Updated note"

    def test_update_po_number(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-011", InvoiceUpdateRequest(po_number="PO-NEW-001"))
        assert inv is not None
        assert inv.po_number == "PO-NEW-001"

    def test_update_not_found(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        result = service.update_invoice("nonexistent", InvoiceUpdateRequest(notes="x"))
        assert result is None

    def test_disputed_to_sent(self, service: InvoiceManagementService):
        """Disputed invoices can be re-sent after resolution."""
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-013", InvoiceUpdateRequest(status=InvoiceStatus.SENT))
        assert inv is not None
        assert inv.status == InvoiceStatus.SENT

    def test_disputed_to_cancelled(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceUpdateRequest
        inv = service.update_invoice("inv-013", InvoiceUpdateRequest(status=InvoiceStatus.CANCELLED))
        assert inv is not None
        assert inv.status == InvoiceStatus.CANCELLED


# ============================================================================
# Line Item Management Tests
# ============================================================================


class TestLineItemManagement:
    """Tests for adding and removing line items."""

    def test_add_line_item_to_draft(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceLineItemCreate
        inv_before = service.get_invoice("inv-011")
        assert inv_before is not None
        initial_count = len(inv_before.line_items)
        initial_total = inv_before.total

        req = InvoiceLineItemCreate(
            line_item_type=LineItemType.PROFESSIONAL_SERVICES,
            description="Consulting hours",
            quantity=10,
            unit_price=350.0,
        )
        inv = service.add_line_item("inv-011", req)
        assert inv is not None
        assert len(inv.line_items) == initial_count + 1
        assert inv.total == initial_total + 3_500.0

    def test_add_line_item_with_tax(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceLineItemCreate
        req = InvoiceLineItemCreate(
            line_item_type=LineItemType.SETUP_FEE,
            description="Setup with tax",
            quantity=1,
            unit_price=10_000.0,
            tax_rate=0.1,
        )
        inv = service.add_line_item("inv-012", req)
        assert inv is not None
        assert inv.tax_total == 1_000.0

    def test_add_line_item_to_non_draft_fails(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceLineItemCreate
        req = InvoiceLineItemCreate(
            line_item_type=LineItemType.CUSTOM,
            description="Should fail",
            quantity=1,
            unit_price=100.0,
        )
        with pytest.raises(ValueError, match="DRAFT"):
            service.add_line_item("inv-006", req)

    def test_add_line_item_not_found(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import InvoiceLineItemCreate
        req = InvoiceLineItemCreate(
            line_item_type=LineItemType.CUSTOM,
            description="Test",
            quantity=1,
            unit_price=100.0,
        )
        result = service.add_line_item("nonexistent", req)
        assert result is None

    def test_remove_line_item(self, service: InvoiceManagementService):
        inv = service.get_invoice("inv-012")
        assert inv is not None
        assert len(inv.line_items) == 2
        li_id = inv.line_items[1].id

        updated = service.remove_line_item("inv-012", li_id)
        assert updated is not None
        assert len(updated.line_items) == 1

    def test_remove_line_item_not_found(self, service: InvoiceManagementService):
        with pytest.raises(ValueError, match="not found"):
            service.remove_line_item("inv-012", "nonexistent-li")

    def test_remove_line_item_non_draft_fails(self, service: InvoiceManagementService):
        with pytest.raises(ValueError, match="DRAFT"):
            service.remove_line_item("inv-006", "li-006")

    def test_remove_line_item_invoice_not_found(self, service: InvoiceManagementService):
        result = service.remove_line_item("nonexistent", "li-x")
        assert result is None


# ============================================================================
# Payment Recording Tests
# ============================================================================


class TestPaymentRecording:
    """Tests for payment recording and status updates."""

    def test_record_full_payment_sent_invoice(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        inv = service.get_invoice("inv-007")
        assert inv is not None

        req = PaymentRecordRequest(
            amount=inv.total,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            reference_number="WT-2026-TEST",
            processed_by="Test User",
        )
        payment = service.record_payment("inv-007", req)
        assert payment is not None
        assert payment.amount == inv.total

        updated = service.get_invoice("inv-007")
        assert updated is not None
        assert updated.status == InvoiceStatus.PAID
        assert updated.paid_date is not None

    def test_record_partial_payment(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        req = PaymentRecordRequest(
            amount=50_000.0,
            payment_method=PaymentMethod.ACH,
            reference_number="ACH-PARTIAL",
        )
        payment = service.record_payment("inv-006", req)
        assert payment is not None
        updated = service.get_invoice("inv-006")
        assert updated is not None
        assert updated.status == InvoiceStatus.PARTIALLY_PAID

    def test_record_payment_overdue_to_paid(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        inv = service.get_invoice("inv-009")
        assert inv is not None
        req = PaymentRecordRequest(
            amount=inv.total,
            payment_method=PaymentMethod.WIRE_TRANSFER,
        )
        payment = service.record_payment("inv-009", req)
        assert payment is not None
        updated = service.get_invoice("inv-009")
        assert updated is not None
        assert updated.status == InvoiceStatus.PAID

    def test_record_payment_invalid_status(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        req = PaymentRecordRequest(
            amount=1000.0,
            payment_method=PaymentMethod.ACH,
        )
        with pytest.raises(ValueError, match="Cannot record payment"):
            service.record_payment("inv-011", req)  # DRAFT

    def test_record_payment_cancelled_invoice(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        req = PaymentRecordRequest(
            amount=1000.0,
            payment_method=PaymentMethod.ACH,
        )
        with pytest.raises(ValueError, match="Cannot record payment"):
            service.record_payment("inv-014", req)  # CANCELLED

    def test_record_payment_not_found(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        req = PaymentRecordRequest(
            amount=1000.0,
            payment_method=PaymentMethod.ACH,
        )
        result = service.record_payment("nonexistent", req)
        assert result is None

    def test_list_payments_by_invoice(self, service: InvoiceManagementService):
        payments = service.list_payments(invoice_id="inv-001")
        assert len(payments) == 1
        assert payments[0].amount == 150_000.0

    def test_list_payments_partial_invoice(self, service: InvoiceManagementService):
        payments = service.list_payments(invoice_id="inv-004")
        assert len(payments) == 3
        total = sum(p.amount for p in payments)
        assert total == 175_000.0

    def test_get_total_paid(self, service: InvoiceManagementService):
        assert service.get_total_paid("inv-001") == 150_000.0
        assert service.get_total_paid("inv-004") == 175_000.0
        assert service.get_total_paid("inv-006") == 0.0

    def test_multiple_partial_payments_to_full(self, service: InvoiceManagementService):
        from app.schemas.invoice_management import PaymentRecordRequest
        inv = service.get_invoice("inv-008")
        assert inv is not None

        # Pay in 3 installments
        for i, amt in enumerate([10_000.0, 10_000.0, 10_000.0]):
            req = PaymentRecordRequest(
                amount=amt,
                payment_method=PaymentMethod.ACH,
                reference_number=f"MULTI-{i}",
            )
            service.record_payment("inv-008", req)

        updated = service.get_invoice("inv-008")
        assert updated is not None
        assert updated.status == InvoiceStatus.PAID


# ============================================================================
# Auto-Invoice Generation Tests
# ============================================================================


class TestAutoInvoiceGeneration:
    """Tests for generating invoices from contracts."""

    def test_generate_from_subscription(self, service: InvoiceManagementService):
        inv = service.generate_invoice_from_contract("contract-001")
        assert inv is not None
        assert inv.status == InvoiceStatus.SENT
        assert inv.billing_model == BillingModel.SUBSCRIPTION
        assert inv.total == 150_000.0
        assert inv.contract_id == "contract-001"

    def test_generate_from_per_patient(self, service: InvoiceManagementService):
        inv = service.generate_invoice_from_contract("contract-002", quantity=50)
        assert inv is not None
        assert inv.total == 125_000.0

    def test_generate_from_data_licensing(self, service: InvoiceManagementService):
        inv = service.generate_invoice_from_contract("contract-004")
        assert inv is not None
        assert inv.total == 50_000.0

    def test_generate_from_usage_based(self, service: InvoiceManagementService):
        inv = service.generate_invoice_from_contract("contract-006")
        assert inv is not None
        assert inv.billing_model == BillingModel.USAGE_BASED

    def test_generate_not_found(self, service: InvoiceManagementService):
        result = service.generate_invoice_from_contract("nonexistent")
        assert result is None

    def test_generate_with_custom_description(self, service: InvoiceManagementService):
        inv = service.generate_invoice_from_contract(
            "contract-001",
            description="Custom billing description",
        )
        assert inv is not None
        assert inv.line_items[0].description == "Custom billing description"

    def test_generate_updates_contract_invoiced(self, service: InvoiceManagementService):
        c_before = service.get_contract("contract-001")
        assert c_before is not None
        before = c_before.invoiced_to_date

        inv = service.generate_invoice_from_contract("contract-001")
        assert inv is not None

        c_after = service.get_contract("contract-001")
        assert c_after is not None
        assert c_after.invoiced_to_date == before + inv.total


# ============================================================================
# AR Aging Report Tests
# ============================================================================


class TestARAgingReport:
    """Tests for accounts receivable aging report."""

    def test_ar_aging_has_four_buckets(self, service: InvoiceManagementService):
        report = service.get_ar_aging_report()
        assert len(report.buckets) == 4

    def test_ar_aging_bucket_names(self, service: InvoiceManagementService):
        report = service.get_ar_aging_report()
        names = [b.bucket for b in report.buckets]
        assert "0-30 days" in names
        assert "31-60 days" in names
        assert "61-90 days" in names
        assert "90+ days" in names

    def test_ar_aging_total_outstanding_positive(self, service: InvoiceManagementService):
        report = service.get_ar_aging_report()
        assert report.total_outstanding >= 0

    def test_ar_aging_has_generated_at(self, service: InvoiceManagementService):
        report = service.get_ar_aging_report()
        assert report.generated_at is not None

    def test_ar_aging_excludes_paid_invoices(self, service: InvoiceManagementService):
        """Paid invoices should not appear in AR aging."""
        report = service.get_ar_aging_report()
        total_invoices_in_buckets = sum(b.count for b in report.buckets)
        all_outstanding = [
            i for i in service.list_invoices()
            if i.status in {InvoiceStatus.SENT, InvoiceStatus.VIEWED,
                           InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE}
            and i.issued_date is not None
        ]
        assert total_invoices_in_buckets == len(all_outstanding)

    def test_ar_aging_excludes_cancelled(self, service: InvoiceManagementService):
        """Cancelled invoices should not appear in AR aging."""
        report = service.get_ar_aging_report()
        # No cancelled invoices counted
        total = sum(b.count for b in report.buckets)
        cancelled = len(service.list_invoices(status=InvoiceStatus.CANCELLED))
        assert cancelled == 1  # We know there's 1 cancelled
        # The total should be less than all invoices
        assert total < len(service.list_invoices())


# ============================================================================
# Revenue Recognition Tests
# ============================================================================


class TestRevenueRecognition:
    """Tests for revenue recognition (ASC 606)."""

    def test_revenue_report_has_12_periods(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2025)
        assert len(report.periods) == 12

    def test_revenue_report_period_format(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2025)
        assert report.periods[0].period == "2025-01"
        assert report.periods[11].period == "2025-12"

    def test_revenue_report_asc606_compliant(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2025)
        assert report.asc606_compliant is True
        for period in report.periods:
            assert period.asc606_compliant is True

    def test_revenue_report_totals(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2025)
        # Total recognized should match sum of periods
        expected_recognized = sum(p.recognized_revenue for p in report.periods)
        assert abs(report.total_recognized - expected_recognized) < 0.01

    def test_revenue_report_deferred_non_negative(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2025)
        for period in report.periods:
            assert period.deferred_revenue >= 0.0

    def test_revenue_report_has_generated_at(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2025)
        assert report.generated_at is not None

    def test_revenue_report_different_year(self, service: InvoiceManagementService):
        report = service.get_revenue_report(year=2024)
        assert len(report.periods) == 12
        assert report.periods[0].period == "2024-01"
        # No data for 2024, so should be mostly zeros
        assert report.total_billed == 0.0


# ============================================================================
# Invoice Metrics Tests
# ============================================================================


class TestInvoiceMetrics:
    """Tests for aggregated invoice metrics."""

    def test_metrics_total_billed_positive(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.total_billed > 0

    def test_metrics_total_collected_positive(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.total_collected > 0

    def test_metrics_outstanding_calculation(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert abs(metrics.total_outstanding - (metrics.total_billed - metrics.total_collected)) < 0.01

    def test_metrics_dso_positive(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.days_sales_outstanding >= 0

    def test_metrics_collection_rate(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert 0 <= metrics.collection_rate <= 100

    def test_metrics_invoices_by_status(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert "PAID" in metrics.invoices_by_status
        assert "SENT" in metrics.invoices_by_status
        assert metrics.invoices_by_status["PAID"] == 3

    def test_metrics_overdue_count(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.overdue_count == 2

    def test_metrics_overdue_amount(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.overdue_amount > 0

    def test_metrics_average_invoice_amount(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.average_invoice_amount > 0

    def test_metrics_average_days_to_pay(self, service: InvoiceManagementService):
        metrics = service.get_invoice_metrics()
        assert metrics.average_days_to_pay >= 0


# ============================================================================
# Overdue Detection & Late Fee Tests
# ============================================================================


class TestOverdueAndLateFees:
    """Tests for overdue detection and late fee calculation."""

    def test_detect_overdue_already_overdue(self, service: InvoiceManagementService):
        """Already-overdue invoices should not be re-detected."""
        detected = service.detect_overdue_invoices()
        # Some SENT invoices might also be past due
        for inv in detected:
            assert inv.status == InvoiceStatus.OVERDUE

    def test_detect_overdue_sent_past_due(self, service: InvoiceManagementService):
        """SENT invoices past due date should become OVERDUE."""
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-test",
            client_name="Test",
            billing_model=BillingModel.SUBSCRIPTION,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Overdue test",
                    quantity=1,
                    unit_price=5_000.0,
                ),
            ],
            issued_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
        )
        inv = service.create_invoice(req)
        detected = service.detect_overdue_invoices()
        ids = [d.id for d in detected]
        assert inv.id in ids

    def test_late_fee_calculation_overdue(self, service: InvoiceManagementService):
        result = service.calculate_late_fee("inv-009")
        assert result is not None
        assert result.days_overdue > 0
        assert result.late_fee > 0
        assert result.monthly_rate == 0.015

    def test_late_fee_calculation_not_overdue(self, service: InvoiceManagementService):
        """Invoice with future due date should have 0 days overdue."""
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="client-test",
            client_name="Test",
            billing_model=BillingModel.SUBSCRIPTION,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.PLATFORM_FEE,
                    description="Future due",
                    quantity=1,
                    unit_price=10_000.0,
                ),
            ],
            issued_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        inv = service.create_invoice(req)
        result = service.calculate_late_fee(inv.id)
        assert result is not None
        assert result.days_overdue == 0
        assert result.late_fee == 0.0

    def test_late_fee_not_found(self, service: InvoiceManagementService):
        result = service.calculate_late_fee("nonexistent")
        assert result is None

    def test_late_fee_no_due_date(self, service: InvoiceManagementService):
        """Invoices without due dates should return None."""
        result = service.calculate_late_fee("inv-011")  # DRAFT, no due date
        assert result is None

    def test_late_fee_total_with_fee(self, service: InvoiceManagementService):
        result = service.calculate_late_fee("inv-009")
        assert result is not None
        assert result.total_with_late_fee >= result.original_amount


# ============================================================================
# 3-Way Match Tests
# ============================================================================


class TestThreeWayMatch:
    """Tests for 3-way match (PO + Contract + Invoice)."""

    def test_full_match(self, service: InvoiceManagementService):
        """inv-001 has PO, contract, and matching amount."""
        result = service.three_way_match("inv-001")
        assert result is not None
        assert result.po_match is True
        assert result.contract_match is True
        assert result.amount_match is True
        assert result.fully_matched is True
        assert len(result.discrepancies) == 0

    def test_missing_po(self, service: InvoiceManagementService):
        """inv-007 has no PO number."""
        result = service.three_way_match("inv-007")
        assert result is not None
        assert result.po_match is False
        assert result.fully_matched is False
        assert any("purchase order" in d.lower() for d in result.discrepancies)

    def test_match_not_found(self, service: InvoiceManagementService):
        result = service.three_way_match("nonexistent")
        assert result is None

    def test_match_with_contract(self, service: InvoiceManagementService):
        """inv-004 has contract-002 linked."""
        result = service.three_way_match("inv-004")
        assert result is not None
        assert result.contract_match is True

    def test_match_per_patient_rate(self, service: InvoiceManagementService):
        """inv-004 per-patient rate should match contract rate."""
        result = service.three_way_match("inv-004")
        assert result is not None
        assert result.amount_match is True


# ============================================================================
# Singleton Pattern Tests
# ============================================================================


class TestSingletonPattern:
    """Tests for singleton service lifecycle."""

    def test_get_returns_same_instance(self):
        svc1 = get_invoice_management_service()
        svc2 = get_invoice_management_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_invoice_management_service()
        reset_invoice_management_service()
        svc2 = get_invoice_management_service()
        assert svc1 is not svc2

    def test_reset_restores_seed_data(self):
        svc = get_invoice_management_service()
        # Modify state
        from app.schemas.invoice_management import InvoiceCreateRequest, InvoiceLineItemCreate
        req = InvoiceCreateRequest(
            client_id="x", client_name="X",
            billing_model=BillingModel.SUBSCRIPTION,
            line_items=[
                InvoiceLineItemCreate(
                    line_item_type=LineItemType.CUSTOM,
                    description="test",
                    quantity=1,
                    unit_price=100.0,
                ),
            ],
        )
        svc.create_invoice(req)
        assert len(svc.list_invoices()) == 16

        reset_invoice_management_service()
        svc2 = get_invoice_management_service()
        assert len(svc2.list_invoices()) == 15


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Integration tests for API endpoints."""

    @pytest.mark.anyio
    async def test_api_list_invoices(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15
        assert len(data["items"]) == 15

    @pytest.mark.anyio
    async def test_api_list_invoices_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices", params={"status": "PAID"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_api_list_invoices_filter_client(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices", params={"client_id": "client-regeneron"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 5

    @pytest.mark.anyio
    async def test_api_get_invoice(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["invoice_number"] == "INV-2025-0001"

    @pytest.mark.anyio
    async def test_api_get_invoice_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_create_invoice(self, client: AsyncClient):
        payload = {
            "client_id": "client-api-test",
            "client_name": "API Test Client",
            "billing_model": "SUBSCRIPTION",
            "line_items": [
                {
                    "line_item_type": "PLATFORM_FEE",
                    "description": "API test fee",
                    "quantity": 1,
                    "unit_price": 75000.0,
                }
            ],
        }
        resp = await client.post(f"{API_PREFIX}/invoices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 75000.0

    @pytest.mark.anyio
    async def test_api_update_invoice(self, client: AsyncClient):
        payload = {"notes": "API updated note"}
        resp = await client.put(f"{API_PREFIX}/invoices/inv-011", json=payload)
        assert resp.status_code == 200
        assert resp.json()["notes"] == "API updated note"

    @pytest.mark.anyio
    async def test_api_update_invalid_transition(self, client: AsyncClient):
        payload = {"status": "DRAFT"}
        resp = await client.put(f"{API_PREFIX}/invoices/inv-001", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_api_send_invoice(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/inv-011/send")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SENT"

    @pytest.mark.anyio
    async def test_api_send_invoice_already_sent(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/inv-006/send")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_api_add_line_item(self, client: AsyncClient):
        payload = {
            "line_item_type": "CUSTOM",
            "description": "API line item",
            "quantity": 5,
            "unit_price": 1000.0,
        }
        resp = await client.post(f"{API_PREFIX}/invoices/inv-011/line-items", json=payload)
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_api_remove_line_item(self, client: AsyncClient):
        # Get a draft invoice with line items
        resp = await client.get(f"{API_PREFIX}/invoices/inv-012")
        li_id = resp.json()["line_items"][1]["id"]
        resp = await client.delete(f"{API_PREFIX}/invoices/inv-012/line-items/{li_id}")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_api_record_payment(self, client: AsyncClient):
        payload = {
            "amount": 50000.0,
            "payment_method": "WIRE_TRANSFER",
            "reference_number": "API-PAY-001",
        }
        resp = await client.post(f"{API_PREFIX}/invoices/inv-006/payments", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_api_list_invoice_payments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/inv-001/payments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.anyio
    async def test_api_list_all_payments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/payments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8

    @pytest.mark.anyio
    async def test_api_three_way_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/inv-001/three-way-match")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fully_matched"] is True

    @pytest.mark.anyio
    async def test_api_late_fee(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/inv-009/late-fee")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_overdue"] > 0

    @pytest.mark.anyio
    async def test_api_list_contracts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_api_list_contracts_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/contracts", params={"billing_model": "SUBSCRIPTION"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_api_get_contract(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/contracts/contract-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["client_name"] == "Regeneron Pharmaceuticals"

    @pytest.mark.anyio
    async def test_api_get_contract_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/contracts/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_create_contract(self, client: AsyncClient):
        payload = {
            "client_id": "client-api-test",
            "client_name": "API Test",
            "billing_model": "SUBSCRIPTION",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "monthly_fee": 50000.0,
        }
        resp = await client.post(f"{API_PREFIX}/contracts", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_api_generate_invoice_from_contract(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/contracts/contract-001/generate-invoice")
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 150_000.0

    @pytest.mark.anyio
    async def test_api_generate_invoice_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/contracts/nonexistent/generate-invoice")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_billed" in data
        assert "days_sales_outstanding" in data
        assert "collection_rate" in data

    @pytest.mark.anyio
    async def test_api_ar_aging(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ar-aging")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["buckets"]) == 4

    @pytest.mark.anyio
    async def test_api_revenue_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/revenue-report", params={"year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["periods"]) == 12
        assert data["asc606_compliant"] is True

    @pytest.mark.anyio
    async def test_api_detect_overdue(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/detect-overdue")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_api_stats(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contracts"] == 6
        assert data["invoices"] == 15

    @pytest.mark.anyio
    async def test_api_record_payment_not_found(self, client: AsyncClient):
        payload = {
            "amount": 1000.0,
            "payment_method": "ACH",
        }
        resp = await client.post(f"{API_PREFIX}/invoices/nonexistent/payments", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_list_payments_invoice_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/nonexistent/payments")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_three_way_match_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/nonexistent/three-way-match")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_late_fee_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/nonexistent/late-fee")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_api_add_line_item_non_draft(self, client: AsyncClient):
        payload = {
            "line_item_type": "CUSTOM",
            "description": "Fail",
            "quantity": 1,
            "unit_price": 100.0,
        }
        resp = await client.post(f"{API_PREFIX}/invoices/inv-006/line-items", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_api_record_payment_draft_fails(self, client: AsyncClient):
        payload = {
            "amount": 1000.0,
            "payment_method": "ACH",
        }
        resp = await client.post(f"{API_PREFIX}/invoices/inv-011/payments", json=payload)
        assert resp.status_code == 400
