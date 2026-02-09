"""Clinical Site Payments & Grant Management Service (CLINICAL-21).

Manages site payment operations including grant definitions, payment line items
(per-patient, milestone, startup, annual, screen failure, protocol deviation
credit, pass-through, holdback release), invoice lifecycle, site payment
summaries, and aggregated payment metrics.

Usage:
    from app.services.site_payments_service import (
        get_site_payments_service,
    )

    svc = get_site_payments_service()
    grants = svc.list_grants()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_payments import (
    CurrencyCode,
    Invoice,
    InvoiceCreate,
    InvoiceUpdate,
    PaymentLineItem,
    PaymentLineItemCreate,
    PaymentLineItemUpdate,
    PaymentMetrics,
    PaymentScheduleType,
    PaymentStatus,
    PaymentType,
    SiteGrant,
    SiteGrantCreate,
    SiteGrantUpdate,
    SitePaymentSummary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Per-patient rates by drug
PER_PATIENT_RATES = {
    "EYLEA": 3500.0,
    "Dupixent": 2800.0,
    "Libtayo": 4200.0,
}

# Overdue threshold: payments accrued > 90 days ago still not paid
OVERDUE_THRESHOLD_DAYS = 90


class SitePaymentsService:
    """In-memory Site Payments & Grant Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._grants: dict[str, SiteGrant] = {}
        self._line_items: dict[str, PaymentLineItem] = {}
        self._invoices: dict[str, Invoice] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic site payment data across clinical trial sites."""
        now = datetime.now(timezone.utc)

        # --- 8 Site Grants ---
        grants_data = [
            {
                "id": "GRT-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "total_budget": 525000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.MONTHLY,
                "per_patient_amount": PER_PATIENT_RATES["EYLEA"],
                "screen_failure_amount": 750.0,
                "startup_fee": 25000.0,
                "annual_fee": 12000.0,
                "holdback_pct": 10.0,
                "effective_date": now - timedelta(days=365),
                "end_date": now + timedelta(days=365),
                "amendment_count": 1,
            },
            {
                "id": "GRT-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "total_budget": 630000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.MONTHLY,
                "per_patient_amount": PER_PATIENT_RATES["EYLEA"],
                "screen_failure_amount": 750.0,
                "startup_fee": 30000.0,
                "annual_fee": 15000.0,
                "holdback_pct": 10.0,
                "effective_date": now - timedelta(days=330),
                "end_date": now + timedelta(days=400),
                "amendment_count": 0,
            },
            {
                "id": "GRT-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "total_budget": 448000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.QUARTERLY,
                "per_patient_amount": PER_PATIENT_RATES["Dupixent"],
                "screen_failure_amount": 600.0,
                "startup_fee": 20000.0,
                "annual_fee": 10000.0,
                "holdback_pct": 15.0,
                "effective_date": now - timedelta(days=300),
                "end_date": now + timedelta(days=430),
                "amendment_count": 2,
            },
            {
                "id": "GRT-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "total_budget": 392000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.QUARTERLY,
                "per_patient_amount": PER_PATIENT_RATES["Dupixent"],
                "screen_failure_amount": 600.0,
                "startup_fee": 20000.0,
                "annual_fee": 10000.0,
                "holdback_pct": 10.0,
                "effective_date": now - timedelta(days=270),
                "end_date": now + timedelta(days=460),
                "amendment_count": 0,
            },
            {
                "id": "GRT-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "total_budget": 756000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.MONTHLY,
                "per_patient_amount": PER_PATIENT_RATES["Libtayo"],
                "screen_failure_amount": 900.0,
                "startup_fee": 35000.0,
                "annual_fee": 18000.0,
                "holdback_pct": 10.0,
                "effective_date": now - timedelta(days=240),
                "end_date": now + timedelta(days=490),
                "amendment_count": 1,
            },
            {
                "id": "GRT-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "site_name": "Cedars-Sinai Medical Center",
                "total_budget": 672000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.MONTHLY,
                "per_patient_amount": PER_PATIENT_RATES["Libtayo"],
                "screen_failure_amount": 900.0,
                "startup_fee": 30000.0,
                "annual_fee": 15000.0,
                "holdback_pct": 12.0,
                "effective_date": now - timedelta(days=210),
                "end_date": now + timedelta(days=520),
                "amendment_count": 0,
            },
            {
                "id": "GRT-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "site_name": "Mass General Brigham",
                "total_budget": 700000.0,
                "currency": CurrencyCode.EUR,
                "payment_schedule_type": PaymentScheduleType.QUARTERLY,
                "per_patient_amount": 3200.0,
                "screen_failure_amount": 700.0,
                "startup_fee": 28000.0,
                "annual_fee": 14000.0,
                "holdback_pct": 10.0,
                "effective_date": now - timedelta(days=350),
                "end_date": now + timedelta(days=380),
                "amendment_count": 3,
            },
            {
                "id": "GRT-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "site_name": "Stanford Health Care",
                "total_budget": 504000.0,
                "currency": CurrencyCode.USD,
                "payment_schedule_type": PaymentScheduleType.UPON_MILESTONE,
                "per_patient_amount": PER_PATIENT_RATES["Dupixent"],
                "screen_failure_amount": 600.0,
                "startup_fee": 22000.0,
                "annual_fee": 11000.0,
                "holdback_pct": 8.0,
                "effective_date": now - timedelta(days=200),
                "end_date": now + timedelta(days=530),
                "amendment_count": 1,
            },
        ]

        for g in grants_data:
            self._grants[g["id"]] = SiteGrant(**g)

        # --- 60 Payment Line Items ---
        li_counter = 0

        # Startup fees (8 items, one per grant)
        for grant in grants_data:
            li_counter += 1
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant["id"],
                site_id=grant["site_id"],
                patient_id=None,
                payment_type=PaymentType.STARTUP_FEE,
                description=f"Startup fee - {grant['site_name']}",
                amount=grant["startup_fee"],
                currency=grant["currency"],
                accrual_date=grant["effective_date"],
                invoice_date=grant["effective_date"] + timedelta(days=15),
                payment_date=grant["effective_date"] + timedelta(days=45),
                status=PaymentStatus.PAID,
                visit_number=None,
            )
            self._line_items[li.id] = li

        # Annual fees (8 items, one per grant)
        for grant in grants_data:
            li_counter += 1
            accrual = grant["effective_date"] + timedelta(days=365)
            is_due = accrual <= now
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant["id"],
                site_id=grant["site_id"],
                patient_id=None,
                payment_type=PaymentType.ANNUAL_FEE,
                description=f"Annual maintenance fee - {grant['site_name']}",
                amount=grant["annual_fee"],
                currency=grant["currency"],
                accrual_date=accrual if is_due else now + timedelta(days=30),
                invoice_date=accrual + timedelta(days=10) if is_due else None,
                payment_date=accrual + timedelta(days=40) if is_due else None,
                status=PaymentStatus.PAID if is_due else PaymentStatus.ACCRUED,
                visit_number=None,
            )
            self._line_items[li.id] = li

        # Per-patient payments (24 items across sites)
        patient_visits = [
            ("GRT-001", "SITE-101", "PAT-1001", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 1),
            ("GRT-001", "SITE-101", "PAT-1002", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 1),
            ("GRT-001", "SITE-101", "PAT-1003", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 2),
            ("GRT-001", "SITE-101", "PAT-1001", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 2),
            ("GRT-002", "SITE-102", "PAT-2001", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 1),
            ("GRT-002", "SITE-102", "PAT-2002", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 1),
            ("GRT-002", "SITE-102", "PAT-2003", PER_PATIENT_RATES["EYLEA"], CurrencyCode.USD, 2),
            ("GRT-003", "SITE-103", "PAT-3001", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 1),
            ("GRT-003", "SITE-103", "PAT-3002", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 1),
            ("GRT-003", "SITE-103", "PAT-3003", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 2),
            ("GRT-004", "SITE-104", "PAT-4001", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 1),
            ("GRT-004", "SITE-104", "PAT-4002", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 1),
            ("GRT-005", "SITE-105", "PAT-5001", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 1),
            ("GRT-005", "SITE-105", "PAT-5002", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 1),
            ("GRT-005", "SITE-105", "PAT-5003", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 2),
            ("GRT-005", "SITE-105", "PAT-5004", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 1),
            ("GRT-006", "SITE-106", "PAT-6001", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 1),
            ("GRT-006", "SITE-106", "PAT-6002", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 1),
            ("GRT-006", "SITE-106", "PAT-6003", PER_PATIENT_RATES["Libtayo"], CurrencyCode.USD, 2),
            ("GRT-007", "SITE-107", "PAT-7001", 3200.0, CurrencyCode.EUR, 1),
            ("GRT-007", "SITE-107", "PAT-7002", 3200.0, CurrencyCode.EUR, 1),
            ("GRT-007", "SITE-107", "PAT-7003", 3200.0, CurrencyCode.EUR, 2),
            ("GRT-008", "SITE-108", "PAT-8001", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 1),
            ("GRT-008", "SITE-108", "PAT-8002", PER_PATIENT_RATES["Dupixent"], CurrencyCode.USD, 1),
        ]

        statuses_cycle = [
            PaymentStatus.PAID,
            PaymentStatus.PAID,
            PaymentStatus.APPROVED,
            PaymentStatus.INVOICE_RECEIVED,
            PaymentStatus.ACCRUED,
        ]

        for i, (grant_id, site_id, patient_id, amount, currency, visit_num) in enumerate(patient_visits):
            li_counter += 1
            days_back = 180 - (i * 7)
            accrual = now - timedelta(days=max(days_back, 1))
            st = statuses_cycle[i % len(statuses_cycle)]
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant_id,
                site_id=site_id,
                patient_id=patient_id,
                payment_type=PaymentType.PER_PATIENT,
                description=f"Per-patient visit {visit_num} - {patient_id}",
                amount=amount,
                currency=currency,
                accrual_date=accrual,
                invoice_date=accrual + timedelta(days=20) if st != PaymentStatus.ACCRUED else None,
                payment_date=accrual + timedelta(days=50) if st == PaymentStatus.PAID else None,
                status=st,
                visit_number=visit_num,
            )
            self._line_items[li.id] = li

        # Screen failure fees (6 items)
        screen_failures = [
            ("GRT-001", "SITE-101", "PAT-1099", 750.0, CurrencyCode.USD),
            ("GRT-002", "SITE-102", "PAT-2099", 750.0, CurrencyCode.USD),
            ("GRT-003", "SITE-103", "PAT-3099", 600.0, CurrencyCode.USD),
            ("GRT-005", "SITE-105", "PAT-5099", 900.0, CurrencyCode.USD),
            ("GRT-006", "SITE-106", "PAT-6099", 900.0, CurrencyCode.USD),
            ("GRT-007", "SITE-107", "PAT-7099", 700.0, CurrencyCode.EUR),
        ]

        for i, (grant_id, site_id, patient_id, amount, currency) in enumerate(screen_failures):
            li_counter += 1
            accrual = now - timedelta(days=120 - i * 15)
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant_id,
                site_id=site_id,
                patient_id=patient_id,
                payment_type=PaymentType.SCREEN_FAILURE_FEE,
                description=f"Screen failure reimbursement - {patient_id}",
                amount=amount,
                currency=currency,
                accrual_date=accrual,
                invoice_date=accrual + timedelta(days=15),
                payment_date=accrual + timedelta(days=45) if i < 4 else None,
                status=PaymentStatus.PAID if i < 4 else PaymentStatus.APPROVED,
                visit_number=None,
            )
            self._line_items[li.id] = li

        # Milestone payments (4 items)
        milestones = [
            ("GRT-001", "SITE-101", 15000.0, CurrencyCode.USD, "First patient enrolled"),
            ("GRT-002", "SITE-102", 15000.0, CurrencyCode.USD, "First patient enrolled"),
            ("GRT-005", "SITE-105", 20000.0, CurrencyCode.USD, "50% enrollment milestone"),
            ("GRT-008", "SITE-108", 10000.0, CurrencyCode.USD, "First patient enrolled"),
        ]

        for i, (grant_id, site_id, amount, currency, desc) in enumerate(milestones):
            li_counter += 1
            accrual = now - timedelta(days=150 - i * 30)
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant_id,
                site_id=site_id,
                patient_id=None,
                payment_type=PaymentType.MILESTONE,
                description=f"Milestone: {desc}",
                amount=amount,
                currency=currency,
                accrual_date=accrual,
                invoice_date=accrual + timedelta(days=10),
                payment_date=accrual + timedelta(days=35) if i < 3 else None,
                status=PaymentStatus.PAID if i < 3 else PaymentStatus.UNDER_REVIEW,
                visit_number=None,
            )
            self._line_items[li.id] = li

        # Pass-through costs (5 items)
        pass_throughs = [
            ("GRT-003", "SITE-103", 2500.0, CurrencyCode.USD, "Lab kit shipping costs Q3"),
            ("GRT-004", "SITE-104", 1800.0, CurrencyCode.USD, "IRB amendment fees"),
            ("GRT-005", "SITE-105", 3200.0, CurrencyCode.USD, "Central lab courier charges Q4"),
            ("GRT-006", "SITE-106", 2100.0, CurrencyCode.USD, "Regulatory filing fees"),
            ("GRT-008", "SITE-108", 1500.0, CurrencyCode.USD, "Pharmacy setup costs"),
        ]

        for i, (grant_id, site_id, amount, currency, desc) in enumerate(pass_throughs):
            li_counter += 1
            accrual = now - timedelta(days=90 - i * 20)
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant_id,
                site_id=site_id,
                patient_id=None,
                payment_type=PaymentType.PASS_THROUGH,
                description=desc,
                amount=amount,
                currency=currency,
                accrual_date=accrual,
                invoice_date=accrual + timedelta(days=7),
                payment_date=accrual + timedelta(days=30) if i < 2 else None,
                status=PaymentStatus.PAID if i < 2 else PaymentStatus.INVOICE_RECEIVED,
                visit_number=None,
            )
            self._line_items[li.id] = li

        # Protocol deviation credits (3 items)
        deviations = [
            ("GRT-003", "SITE-103", -500.0, CurrencyCode.USD, "Protocol deviation credit - missed visit window"),
            ("GRT-005", "SITE-105", -750.0, CurrencyCode.USD, "Protocol deviation credit - dosing error"),
            ("GRT-007", "SITE-107", -400.0, CurrencyCode.EUR, "Protocol deviation credit - consent process"),
        ]

        for i, (grant_id, site_id, amount, currency, desc) in enumerate(deviations):
            li_counter += 1
            accrual = now - timedelta(days=60 - i * 15)
            li = PaymentLineItem(
                id=f"PLI-{li_counter:04d}",
                grant_id=grant_id,
                site_id=site_id,
                patient_id=None,
                payment_type=PaymentType.PROTOCOL_DEVIATION_CREDIT,
                description=desc,
                amount=amount,
                currency=currency,
                accrual_date=accrual,
                invoice_date=None,
                payment_date=None,
                status=PaymentStatus.ACCRUED,
                visit_number=None,
            )
            self._line_items[li.id] = li

        # Holdback releases (1 item)
        li_counter += 1
        li = PaymentLineItem(
            id=f"PLI-{li_counter:04d}",
            grant_id="GRT-001",
            site_id="SITE-101",
            patient_id=None,
            payment_type=PaymentType.HOLDBACK_RELEASE,
            description="Partial holdback release - interim good performance",
            amount=5000.0,
            currency=CurrencyCode.USD,
            accrual_date=now - timedelta(days=30),
            invoice_date=now - timedelta(days=20),
            payment_date=now - timedelta(days=5),
            status=PaymentStatus.PAID,
            visit_number=None,
        )
        self._line_items[li.id] = li

        # Disputed item (1 item)
        li_counter += 1
        li = PaymentLineItem(
            id=f"PLI-{li_counter:04d}",
            grant_id="GRT-004",
            site_id="SITE-104",
            patient_id=None,
            payment_type=PaymentType.PASS_THROUGH,
            description="Disputed: equipment rental charges exceed agreement",
            amount=4500.0,
            currency=CurrencyCode.USD,
            accrual_date=now - timedelta(days=100),
            invoice_date=now - timedelta(days=85),
            payment_date=None,
            status=PaymentStatus.DISPUTED,
            visit_number=None,
        )
        self._line_items[li.id] = li

        assert li_counter == 60, f"Expected 60 line items, got {li_counter}"

        # --- 12 Invoices ---
        invoices_data = [
            {
                "id": "INV-001",
                "site_id": "SITE-101",
                "trial_id": EYLEA_TRIAL,
                "invoice_number": "MHH-2025-Q3-001",
                "period_start": now - timedelta(days=270),
                "period_end": now - timedelta(days=180),
                "line_items": ["PLI-0001", "PLI-0017", "PLI-0018"],
                "subtotal": 32000.0,
                "tax": 0.0,
                "total": 32000.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=170),
                "approved_date": now - timedelta(days=160),
                "paid_date": now - timedelta(days=145),
            },
            {
                "id": "INV-002",
                "site_id": "SITE-101",
                "trial_id": EYLEA_TRIAL,
                "invoice_number": "MHH-2025-Q4-001",
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=90),
                "line_items": ["PLI-0019", "PLI-0020", "PLI-0049"],
                "subtotal": 22750.0,
                "tax": 0.0,
                "total": 22750.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=80),
                "approved_date": now - timedelta(days=70),
                "paid_date": now - timedelta(days=55),
            },
            {
                "id": "INV-003",
                "site_id": "SITE-102",
                "trial_id": EYLEA_TRIAL,
                "invoice_number": "CCF-2025-Q4-001",
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=90),
                "line_items": ["PLI-0002", "PLI-0021", "PLI-0022"],
                "subtotal": 37750.0,
                "tax": 0.0,
                "total": 37750.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=85),
                "approved_date": now - timedelta(days=75),
                "paid_date": now - timedelta(days=60),
            },
            {
                "id": "INV-004",
                "site_id": "SITE-103",
                "trial_id": DUPIXENT_TRIAL,
                "invoice_number": "JHU-2025-Q3-001",
                "period_start": now - timedelta(days=270),
                "period_end": now - timedelta(days=180),
                "line_items": ["PLI-0003", "PLI-0024", "PLI-0025"],
                "subtotal": 25600.0,
                "tax": 0.0,
                "total": 25600.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=165),
                "approved_date": now - timedelta(days=155),
                "paid_date": now - timedelta(days=140),
            },
            {
                "id": "INV-005",
                "site_id": "SITE-104",
                "trial_id": DUPIXENT_TRIAL,
                "invoice_number": "MAYO-2025-Q4-001",
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=90),
                "line_items": ["PLI-0004", "PLI-0027", "PLI-0028"],
                "subtotal": 15600.0,
                "tax": 0.0,
                "total": 15600.0,
                "status": PaymentStatus.APPROVED,
                "submitted_date": now - timedelta(days=75),
                "approved_date": now - timedelta(days=60),
                "paid_date": None,
            },
            {
                "id": "INV-006",
                "site_id": "SITE-105",
                "trial_id": LIBTAYO_TRIAL,
                "invoice_number": "DUKE-2025-Q3-001",
                "period_start": now - timedelta(days=270),
                "period_end": now - timedelta(days=180),
                "line_items": ["PLI-0005", "PLI-0029", "PLI-0030"],
                "subtotal": 43400.0,
                "tax": 0.0,
                "total": 43400.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=160),
                "approved_date": now - timedelta(days=150),
                "paid_date": now - timedelta(days=135),
            },
            {
                "id": "INV-007",
                "site_id": "SITE-105",
                "trial_id": LIBTAYO_TRIAL,
                "invoice_number": "DUKE-2026-Q1-001",
                "period_start": now - timedelta(days=90),
                "period_end": now,
                "line_items": ["PLI-0031", "PLI-0032", "PLI-0051"],
                "subtotal": 12500.0,
                "tax": 0.0,
                "total": 12500.0,
                "status": PaymentStatus.UNDER_REVIEW,
                "submitted_date": now - timedelta(days=10),
                "approved_date": None,
                "paid_date": None,
            },
            {
                "id": "INV-008",
                "site_id": "SITE-106",
                "trial_id": LIBTAYO_TRIAL,
                "invoice_number": "CSMC-2025-Q4-001",
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=90),
                "line_items": ["PLI-0006", "PLI-0033", "PLI-0034"],
                "subtotal": 38400.0,
                "tax": 0.0,
                "total": 38400.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=82),
                "approved_date": now - timedelta(days=72),
                "paid_date": now - timedelta(days=57),
            },
            {
                "id": "INV-009",
                "site_id": "SITE-107",
                "trial_id": EYLEA_TRIAL,
                "invoice_number": "MGB-2025-Q3-001",
                "period_start": now - timedelta(days=270),
                "period_end": now - timedelta(days=180),
                "line_items": ["PLI-0007", "PLI-0036", "PLI-0037"],
                "subtotal": 34400.0,
                "tax": 0.0,
                "total": 34400.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=168),
                "approved_date": now - timedelta(days=158),
                "paid_date": now - timedelta(days=143),
            },
            {
                "id": "INV-010",
                "site_id": "SITE-107",
                "trial_id": EYLEA_TRIAL,
                "invoice_number": "MGB-2026-Q1-001",
                "period_start": now - timedelta(days=90),
                "period_end": now,
                "line_items": ["PLI-0038"],
                "subtotal": 3200.0,
                "tax": 0.0,
                "total": 3200.0,
                "status": PaymentStatus.INVOICE_RECEIVED,
                "submitted_date": now - timedelta(days=5),
                "approved_date": None,
                "paid_date": None,
            },
            {
                "id": "INV-011",
                "site_id": "SITE-108",
                "trial_id": DUPIXENT_TRIAL,
                "invoice_number": "SHC-2025-Q4-001",
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=90),
                "line_items": ["PLI-0008", "PLI-0039", "PLI-0040"],
                "subtotal": 27600.0,
                "tax": 0.0,
                "total": 27600.0,
                "status": PaymentStatus.PAID,
                "submitted_date": now - timedelta(days=78),
                "approved_date": now - timedelta(days=68),
                "paid_date": now - timedelta(days=53),
            },
            {
                "id": "INV-012",
                "site_id": "SITE-103",
                "trial_id": DUPIXENT_TRIAL,
                "invoice_number": "JHU-2026-Q1-001",
                "period_start": now - timedelta(days=90),
                "period_end": now,
                "line_items": ["PLI-0026", "PLI-0041"],
                "subtotal": 5300.0,
                "tax": 0.0,
                "total": 5300.0,
                "status": PaymentStatus.INVOICE_RECEIVED,
                "submitted_date": now - timedelta(days=7),
                "approved_date": None,
                "paid_date": None,
            },
        ]

        for inv in invoices_data:
            self._invoices[inv["id"]] = Invoice(**inv)

    # ------------------------------------------------------------------
    # Grant Management
    # ------------------------------------------------------------------

    def list_grants(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        currency: CurrencyCode | None = None,
    ) -> list[SiteGrant]:
        """List site grants with optional filters."""
        with self._lock:
            result = list(self._grants.values())

        if trial_id is not None:
            result = [g for g in result if g.trial_id == trial_id]
        if site_id is not None:
            result = [g for g in result if g.site_id == site_id]
        if currency is not None:
            result = [g for g in result if g.currency == currency]

        return sorted(result, key=lambda g: g.id)

    def get_grant(self, grant_id: str) -> SiteGrant | None:
        """Get a single grant by ID."""
        with self._lock:
            return self._grants.get(grant_id)

    def create_grant(self, payload: SiteGrantCreate) -> SiteGrant:
        """Create a new site grant."""
        grant_id = f"GRT-{uuid4().hex[:8].upper()}"
        grant = SiteGrant(
            id=grant_id,
            amendment_count=0,
            **payload.model_dump(),
        )
        with self._lock:
            self._grants[grant_id] = grant
        logger.info("Created grant %s for site %s", grant_id, payload.site_id)
        return grant

    def update_grant(self, grant_id: str, payload: SiteGrantUpdate) -> SiteGrant | None:
        """Update an existing site grant (creates an amendment)."""
        with self._lock:
            existing = self._grants.get(grant_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["amendment_count"] = existing.amendment_count + 1
            updated = SiteGrant(**data)
            self._grants[grant_id] = updated
        return updated

    def delete_grant(self, grant_id: str) -> bool:
        """Delete a grant. Returns True if deleted, False if not found."""
        with self._lock:
            if grant_id in self._grants:
                del self._grants[grant_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Payment Line Items
    # ------------------------------------------------------------------

    def list_line_items(
        self,
        *,
        grant_id: str | None = None,
        site_id: str | None = None,
        payment_type: PaymentType | None = None,
        status: PaymentStatus | None = None,
        patient_id: str | None = None,
    ) -> list[PaymentLineItem]:
        """List payment line items with optional filters."""
        with self._lock:
            result = list(self._line_items.values())

        if grant_id is not None:
            result = [li for li in result if li.grant_id == grant_id]
        if site_id is not None:
            result = [li for li in result if li.site_id == site_id]
        if payment_type is not None:
            result = [li for li in result if li.payment_type == payment_type]
        if status is not None:
            result = [li for li in result if li.status == status]
        if patient_id is not None:
            result = [li for li in result if li.patient_id == patient_id]

        return sorted(result, key=lambda li: li.accrual_date, reverse=True)

    def get_line_item(self, item_id: str) -> PaymentLineItem | None:
        """Get a single payment line item by ID."""
        with self._lock:
            return self._line_items.get(item_id)

    def create_line_item(self, payload: PaymentLineItemCreate) -> PaymentLineItem:
        """Create a new payment line item."""
        # Validate grant exists
        if payload.grant_id not in self._grants:
            raise ValueError(f"Grant '{payload.grant_id}' not found")

        item_id = f"PLI-{uuid4().hex[:8].upper()}"
        li = PaymentLineItem(
            id=item_id,
            grant_id=payload.grant_id,
            site_id=payload.site_id,
            patient_id=payload.patient_id,
            payment_type=payload.payment_type,
            description=payload.description,
            amount=payload.amount,
            currency=payload.currency,
            accrual_date=payload.accrual_date,
            invoice_date=None,
            payment_date=None,
            status=PaymentStatus.ACCRUED,
            visit_number=payload.visit_number,
        )
        with self._lock:
            self._line_items[item_id] = li
        logger.info(
            "Created line item %s: type=%s site=%s amount=%.2f",
            item_id, payload.payment_type.value, payload.site_id, payload.amount,
        )
        return li

    def update_line_item(self, item_id: str, payload: PaymentLineItemUpdate) -> PaymentLineItem | None:
        """Update a payment line item."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._line_items.get(item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set payment_date when status transitions to paid
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = PaymentStatus(new_status)
                if new_status == PaymentStatus.PAID and existing.status != PaymentStatus.PAID:
                    if "payment_date" not in updates:
                        updates["payment_date"] = now

            data.update(updates)
            updated = PaymentLineItem(**data)
            self._line_items[item_id] = updated
        return updated

    def delete_line_item(self, item_id: str) -> bool:
        """Delete a payment line item. Returns True if deleted."""
        with self._lock:
            if item_id in self._line_items:
                del self._line_items[item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def list_invoices(
        self,
        *,
        site_id: str | None = None,
        trial_id: str | None = None,
        status: PaymentStatus | None = None,
    ) -> list[Invoice]:
        """List invoices with optional filters."""
        with self._lock:
            result = list(self._invoices.values())

        if site_id is not None:
            result = [inv for inv in result if inv.site_id == site_id]
        if trial_id is not None:
            result = [inv for inv in result if inv.trial_id == trial_id]
        if status is not None:
            result = [inv for inv in result if inv.status == status]

        return sorted(result, key=lambda inv: inv.submitted_date, reverse=True)

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        """Get a single invoice by ID."""
        with self._lock:
            return self._invoices.get(invoice_id)

    def create_invoice(self, payload: InvoiceCreate) -> Invoice:
        """Create a new invoice."""
        now = datetime.now(timezone.utc)
        invoice_id = f"INV-{uuid4().hex[:8].upper()}"

        # Calculate subtotal from referenced line items
        subtotal = 0.0
        with self._lock:
            for li_id in payload.line_item_ids:
                li = self._line_items.get(li_id)
                if li is not None:
                    subtotal += li.amount

        total = subtotal + payload.tax

        invoice = Invoice(
            id=invoice_id,
            site_id=payload.site_id,
            trial_id=payload.trial_id,
            invoice_number=payload.invoice_number,
            period_start=payload.period_start,
            period_end=payload.period_end,
            line_items=payload.line_item_ids,
            subtotal=round(subtotal, 2),
            tax=payload.tax,
            total=round(total, 2),
            status=PaymentStatus.INVOICE_RECEIVED,
            submitted_date=now,
            approved_date=None,
            paid_date=None,
        )
        with self._lock:
            self._invoices[invoice_id] = invoice
        logger.info("Created invoice %s for site %s", invoice_id, payload.site_id)
        return invoice

    def update_invoice(self, invoice_id: str, payload: InvoiceUpdate) -> Invoice | None:
        """Update an invoice status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._invoices.get(invoice_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = PaymentStatus(new_status)
                if new_status == PaymentStatus.APPROVED and existing.status != PaymentStatus.APPROVED:
                    updates["approved_date"] = now
                if new_status == PaymentStatus.PAID and existing.status != PaymentStatus.PAID:
                    updates["paid_date"] = now
                    if existing.approved_date is None:
                        updates["approved_date"] = now

            data.update(updates)
            updated = Invoice(**data)
            self._invoices[invoice_id] = updated
        return updated

    def delete_invoice(self, invoice_id: str) -> bool:
        """Delete an invoice. Returns True if deleted."""
        with self._lock:
            if invoice_id in self._invoices:
                del self._invoices[invoice_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Approve / Pay shortcuts
    # ------------------------------------------------------------------

    def approve_invoice(self, invoice_id: str) -> Invoice | None:
        """Approve an invoice (shortcut for status update)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._invoices.get(invoice_id)
            if existing is None:
                return None
            if existing.status == PaymentStatus.PAID:
                raise ValueError(f"Invoice '{invoice_id}' is already paid")
            if existing.status == PaymentStatus.APPROVED:
                raise ValueError(f"Invoice '{invoice_id}' is already approved")
            data = existing.model_dump()
            data["status"] = PaymentStatus.APPROVED
            data["approved_date"] = now
            updated = Invoice(**data)
            self._invoices[invoice_id] = updated
        return updated

    def pay_invoice(self, invoice_id: str) -> Invoice | None:
        """Pay an invoice (shortcut for status update)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._invoices.get(invoice_id)
            if existing is None:
                return None
            if existing.status == PaymentStatus.PAID:
                raise ValueError(f"Invoice '{invoice_id}' is already paid")
            data = existing.model_dump()
            data["status"] = PaymentStatus.PAID
            data["paid_date"] = now
            if existing.approved_date is None:
                data["approved_date"] = now
            updated = Invoice(**data)
            self._invoices[invoice_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Site Payment Summary
    # ------------------------------------------------------------------

    def get_site_summary(self, site_id: str) -> SitePaymentSummary | None:
        """Compute payment summary for a specific site."""
        # Find grant to get site name
        site_name = None
        holdback_pct = 0.0
        with self._lock:
            for grant in self._grants.values():
                if grant.site_id == site_id:
                    site_name = grant.site_name
                    holdback_pct = grant.holdback_pct
                    break
            line_items = [li for li in self._line_items.values() if li.site_id == site_id]

        if site_name is None:
            return None

        total_accrued = 0.0
        total_invoiced = 0.0
        total_paid = 0.0
        patients: set[str] = set()
        by_type: dict[str, float] = {}

        for li in line_items:
            total_accrued += li.amount
            if li.invoice_date is not None:
                total_invoiced += li.amount
            if li.status == PaymentStatus.PAID:
                total_paid += li.amount
            if li.patient_id and li.payment_type == PaymentType.PER_PATIENT:
                patients.add(li.patient_id)
            key = li.payment_type.value
            by_type[key] = by_type.get(key, 0.0) + li.amount

        holdback_amount = round(total_accrued * holdback_pct / 100.0, 2)
        total_outstanding = round(total_accrued - total_paid, 2)

        return SitePaymentSummary(
            site_id=site_id,
            site_name=site_name,
            total_accrued=round(total_accrued, 2),
            total_invoiced=round(total_invoiced, 2),
            total_paid=round(total_paid, 2),
            total_outstanding=total_outstanding,
            holdback_amount=holdback_amount,
            patients_enrolled=len(patients),
            payments_by_type={k: round(v, 2) for k, v in by_type.items()},
        )

    def list_site_summaries(self) -> list[SitePaymentSummary]:
        """Compute payment summaries for all sites with grants."""
        with self._lock:
            site_ids = list({g.site_id for g in self._grants.values()})

        summaries: list[SitePaymentSummary] = []
        for sid in sorted(site_ids):
            summary = self.get_site_summary(sid)
            if summary is not None:
                summaries.append(summary)
        return summaries

    # ------------------------------------------------------------------
    # Overdue Payments
    # ------------------------------------------------------------------

    def get_overdue_payments(self) -> list[PaymentLineItem]:
        """Get payments that are accrued/invoiced for more than the threshold and not yet paid."""
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=OVERDUE_THRESHOLD_DAYS)
        with self._lock:
            result = [
                li for li in self._line_items.values()
                if li.status in (
                    PaymentStatus.ACCRUED,
                    PaymentStatus.INVOICE_RECEIVED,
                    PaymentStatus.UNDER_REVIEW,
                    PaymentStatus.APPROVED,
                )
                and li.accrual_date < threshold
            ]
        return sorted(result, key=lambda li: li.accrual_date)

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> PaymentMetrics:
        """Compute aggregated payment metrics across all grants and sites."""
        now = datetime.now(timezone.utc)

        with self._lock:
            grants = list(self._grants.values())
            line_items = list(self._line_items.values())

        total_accrued = 0.0
        total_paid = 0.0
        payment_cycle_days: list[float] = []

        site_outstanding: set[str] = set()
        overdue_count = 0
        threshold = now - timedelta(days=OVERDUE_THRESHOLD_DAYS)

        for li in line_items:
            total_accrued += li.amount
            if li.status == PaymentStatus.PAID:
                total_paid += li.amount
                if li.payment_date and li.accrual_date:
                    days = (li.payment_date - li.accrual_date).days
                    if days >= 0:
                        payment_cycle_days.append(days)
            else:
                if li.amount > 0:
                    site_outstanding.add(li.site_id)

            if (
                li.status in (
                    PaymentStatus.ACCRUED,
                    PaymentStatus.INVOICE_RECEIVED,
                    PaymentStatus.UNDER_REVIEW,
                    PaymentStatus.APPROVED,
                )
                and li.accrual_date < threshold
            ):
                overdue_count += 1

        avg_cycle = round(
            sum(payment_cycle_days) / max(1, len(payment_cycle_days)), 1
        )

        # Calculate holdback total
        holdback_total = 0.0
        for grant in grants:
            # Sum accrued for this grant
            grant_accrued = sum(
                li.amount for li in line_items if li.grant_id == grant.id
            )
            holdback_total += grant_accrued * grant.holdback_pct / 100.0

        return PaymentMetrics(
            total_grants=len(grants),
            total_accrued_amount=round(total_accrued, 2),
            total_paid_amount=round(total_paid, 2),
            avg_payment_cycle_days=avg_cycle,
            sites_with_outstanding=len(site_outstanding),
            overdue_payments=overdue_count,
            holdback_total=round(holdback_total, 2),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SitePaymentsService | None = None
_instance_lock = threading.Lock()


def get_site_payments_service() -> SitePaymentsService:
    """Return the singleton SitePaymentsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SitePaymentsService()
    return _instance


def reset_site_payments_service() -> SitePaymentsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SitePaymentsService()
    return _instance
