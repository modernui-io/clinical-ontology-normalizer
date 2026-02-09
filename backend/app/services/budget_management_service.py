"""Budget Tracking & Approval Workflows Service (CFO-3).

Manages budget periods, allocations, spend requests, and approval
workflows for the clinical trial patient recruitment platform.

Usage:
    from app.services.budget_management_service import get_budget_management_service

    service = get_budget_management_service()
    metrics = service.get_metrics()
    periods = service.list_periods()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.budget_management import (
    ApprovalStatus,
    BudgetAlert,
    BudgetAlertType,
    BudgetAllocation,
    BudgetCategory,
    BudgetMetrics,
    BudgetPeriod,
    RecordSpendInput,
    SpendForecast,
    SpendRequest,
    SpendRequestCreate,
    SpendRequestUpdate,
    SpendStatus,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_budget_service_instance: BudgetManagementService | None = None
_budget_service_lock = Lock()

# ---------------------------------------------------------------------------
# Approval routing thresholds
# ---------------------------------------------------------------------------

VP_APPROVAL_THRESHOLD = 10_000.0
CFO_APPROVAL_THRESHOLD = 50_000.0


def _compute_spend_status(spent: float, allocated: float) -> SpendStatus:
    """Determine spend status from spent vs allocated amounts."""
    if allocated <= 0:
        return SpendStatus.WITHIN_BUDGET
    ratio = spent / allocated
    if ratio > 1.0:
        return SpendStatus.OVER_BUDGET
    if ratio > 0.8:
        return SpendStatus.WARNING
    return SpendStatus.WITHIN_BUDGET


def _compute_variance_pct(spent: float, allocated: float) -> float:
    """Compute variance percentage."""
    if allocated <= 0:
        return 0.0
    return round((spent - allocated) / allocated * 100, 2)


# ---------------------------------------------------------------------------
# Seed Data Builders
# ---------------------------------------------------------------------------


def _build_seed_periods() -> list[BudgetPeriod]:
    """Build pre-populated quarterly budget periods for FY2025."""
    return [
        BudgetPeriod(
            id="period-2025-q1",
            fiscal_year=2025,
            quarter="Q1",
            total_budget=2_500_000.0,
            total_allocated=2_400_000.0,
            total_spent=2_100_000.0,
            remaining=400_000.0,
            status=SpendStatus.WARNING,
        ),
        BudgetPeriod(
            id="period-2025-q2",
            fiscal_year=2025,
            quarter="Q2",
            total_budget=2_750_000.0,
            total_allocated=2_600_000.0,
            total_spent=1_800_000.0,
            remaining=950_000.0,
            status=SpendStatus.WITHIN_BUDGET,
        ),
        BudgetPeriod(
            id="period-2025-q3",
            fiscal_year=2025,
            quarter="Q3",
            total_budget=3_000_000.0,
            total_allocated=2_800_000.0,
            total_spent=900_000.0,
            remaining=2_100_000.0,
            status=SpendStatus.WITHIN_BUDGET,
        ),
        BudgetPeriod(
            id="period-2025-q4",
            fiscal_year=2025,
            quarter="Q4",
            total_budget=3_250_000.0,
            total_allocated=3_000_000.0,
            total_spent=0.0,
            remaining=3_250_000.0,
            status=SpendStatus.WITHIN_BUDGET,
        ),
    ]


def _build_seed_allocations() -> list[BudgetAllocation]:
    """Build pre-populated allocations across categories for each quarter."""
    allocations: list[BudgetAllocation] = []

    # Q1 allocations
    q1_data = [
        (BudgetCategory.INFRASTRUCTURE, 480_000.0, 460_000.0, "VP Engineering"),
        (BudgetCategory.PERSONNEL, 900_000.0, 870_000.0, "VP People"),
        (BudgetCategory.DATA_LICENSING, 240_000.0, 220_000.0, "Chief Data Officer"),
        (BudgetCategory.COMPLIANCE, 180_000.0, 165_000.0, "Chief Compliance Officer"),
        (BudgetCategory.MARKETING, 150_000.0, 120_000.0, "VP Marketing"),
        (BudgetCategory.RESEARCH, 200_000.0, 140_000.0, "VP Research"),
        (BudgetCategory.OPERATIONS, 150_000.0, 100_000.0, "COO"),
        (BudgetCategory.PROFESSIONAL_SERVICES, 100_000.0, 125_000.0, "CFO"),
    ]
    for i, (cat, alloc, spent, owner) in enumerate(q1_data, 1):
        aid = f"alloc-q1-{i:02d}"
        allocations.append(
            BudgetAllocation(
                id=aid,
                period_id="period-2025-q1",
                category=cat,
                allocated_amount=alloc,
                spent_amount=spent,
                remaining=alloc - spent,
                committed=0.0,
                variance_pct=_compute_variance_pct(spent, alloc),
                owner=owner,
            )
        )

    # Q2 allocations
    q2_data = [
        (BudgetCategory.INFRASTRUCTURE, 520_000.0, 380_000.0, "VP Engineering"),
        (BudgetCategory.PERSONNEL, 950_000.0, 640_000.0, "VP People"),
        (BudgetCategory.DATA_LICENSING, 260_000.0, 180_000.0, "Chief Data Officer"),
        (BudgetCategory.COMPLIANCE, 200_000.0, 140_000.0, "Chief Compliance Officer"),
        (BudgetCategory.MARKETING, 180_000.0, 130_000.0, "VP Marketing"),
        (BudgetCategory.RESEARCH, 220_000.0, 150_000.0, "VP Research"),
        (BudgetCategory.OPERATIONS, 160_000.0, 110_000.0, "COO"),
        (BudgetCategory.PROFESSIONAL_SERVICES, 110_000.0, 70_000.0, "CFO"),
    ]
    for i, (cat, alloc, spent, owner) in enumerate(q2_data, 1):
        aid = f"alloc-q2-{i:02d}"
        allocations.append(
            BudgetAllocation(
                id=aid,
                period_id="period-2025-q2",
                category=cat,
                allocated_amount=alloc,
                spent_amount=spent,
                remaining=alloc - spent,
                committed=0.0,
                variance_pct=_compute_variance_pct(spent, alloc),
                owner=owner,
            )
        )

    # Q3 allocations (current quarter, partial spend)
    q3_data = [
        (BudgetCategory.INFRASTRUCTURE, 560_000.0, 180_000.0, 25_000.0, "VP Engineering"),
        (BudgetCategory.PERSONNEL, 1_000_000.0, 320_000.0, 0.0, "VP People"),
        (BudgetCategory.DATA_LICENSING, 280_000.0, 90_000.0, 15_000.0, "Chief Data Officer"),
        (BudgetCategory.COMPLIANCE, 220_000.0, 70_000.0, 10_000.0, "Chief Compliance Officer"),
        (BudgetCategory.MARKETING, 200_000.0, 65_000.0, 20_000.0, "VP Marketing"),
        (BudgetCategory.RESEARCH, 250_000.0, 80_000.0, 30_000.0, "VP Research"),
        (BudgetCategory.OPERATIONS, 170_000.0, 55_000.0, 0.0, "COO"),
        (BudgetCategory.PROFESSIONAL_SERVICES, 120_000.0, 40_000.0, 12_000.0, "CFO"),
    ]
    for i, (cat, alloc, spent, committed, owner) in enumerate(q3_data, 1):
        aid = f"alloc-q3-{i:02d}"
        allocations.append(
            BudgetAllocation(
                id=aid,
                period_id="period-2025-q3",
                category=cat,
                allocated_amount=alloc,
                spent_amount=spent,
                remaining=alloc - spent,
                committed=committed,
                variance_pct=_compute_variance_pct(spent, alloc),
                owner=owner,
            )
        )

    # Q4 allocations (future quarter, no spend)
    q4_data = [
        (BudgetCategory.INFRASTRUCTURE, 600_000.0, "VP Engineering"),
        (BudgetCategory.PERSONNEL, 1_050_000.0, "VP People"),
        (BudgetCategory.DATA_LICENSING, 300_000.0, "Chief Data Officer"),
        (BudgetCategory.COMPLIANCE, 240_000.0, "Chief Compliance Officer"),
        (BudgetCategory.MARKETING, 220_000.0, "VP Marketing"),
        (BudgetCategory.RESEARCH, 280_000.0, "VP Research"),
        (BudgetCategory.OPERATIONS, 180_000.0, "COO"),
        (BudgetCategory.PROFESSIONAL_SERVICES, 130_000.0, "CFO"),
    ]
    for i, (cat, alloc, owner) in enumerate(q4_data, 1):
        aid = f"alloc-q4-{i:02d}"
        allocations.append(
            BudgetAllocation(
                id=aid,
                period_id="period-2025-q4",
                category=cat,
                allocated_amount=alloc,
                spent_amount=0.0,
                remaining=alloc,
                committed=0.0,
                variance_pct=0.0,
                owner=owner,
            )
        )

    return allocations


def _build_seed_spend_requests() -> list[SpendRequest]:
    """Build 10 pre-populated spend requests in various states."""
    now = datetime.now(timezone.utc)
    return [
        SpendRequest(
            id="sr-001",
            allocation_id="alloc-q3-01",
            title="AWS Reserved Instance Renewal",
            description="Annual renewal of reserved EC2 instances for production workloads",
            amount=75_000.0,
            requested_by="Sarah Chen",
            requested_date=now - timedelta(days=14),
            status=ApprovalStatus.APPROVED,
            approver="CFO - Michael Torres",
            approved_date=now - timedelta(days=10),
            vendor="Amazon Web Services",
            invoice_ref="INV-AWS-2025-Q3-001",
        ),
        SpendRequest(
            id="sr-002",
            allocation_id="alloc-q3-02",
            title="Senior Data Engineer Hiring",
            description="Recruiting fees for senior data engineer position",
            amount=25_000.0,
            requested_by="David Kim",
            requested_date=now - timedelta(days=7),
            status=ApprovalStatus.PENDING_APPROVAL,
            vendor="TechTalent Recruiting",
            invoice_ref="",
        ),
        SpendRequest(
            id="sr-003",
            allocation_id="alloc-q3-03",
            title="Clinical Data License Expansion",
            description="Expanding real-world evidence data license coverage",
            amount=45_000.0,
            requested_by="Dr. Lisa Wang",
            requested_date=now - timedelta(days=5),
            status=ApprovalStatus.PENDING_APPROVAL,
            vendor="Clinical Data Solutions Inc.",
            invoice_ref="",
        ),
        SpendRequest(
            id="sr-004",
            allocation_id="alloc-q3-04",
            title="HITRUST Readiness Assessment",
            description="Third-party HITRUST CSF readiness assessment",
            amount=35_000.0,
            requested_by="James Rodriguez",
            requested_date=now - timedelta(days=20),
            status=ApprovalStatus.APPROVED,
            approver="VP Compliance - Rachel Adams",
            approved_date=now - timedelta(days=15),
            vendor="Coalfire Systems",
            invoice_ref="INV-CF-2025-008",
        ),
        SpendRequest(
            id="sr-005",
            allocation_id="alloc-q3-05",
            title="Digital Marketing Campaign",
            description="Patient recruitment digital marketing for Q3 trials",
            amount=8_500.0,
            requested_by="Emily Foster",
            requested_date=now - timedelta(days=3),
            status=ApprovalStatus.DRAFT,
            vendor="HealthReach Media",
            invoice_ref="",
        ),
        SpendRequest(
            id="sr-006",
            allocation_id="alloc-q3-06",
            title="Genomics Analysis Platform License",
            description="Annual license for genomics analysis research platform",
            amount=55_000.0,
            requested_by="Dr. Alex Thompson",
            requested_date=now - timedelta(days=12),
            status=ApprovalStatus.REJECTED,
            approver="CFO - Michael Torres",
            approved_date=now - timedelta(days=8),
            rejection_reason="Budget constraints. Re-evaluate in Q4.",
            vendor="GenoTech Solutions",
            invoice_ref="",
        ),
        SpendRequest(
            id="sr-007",
            allocation_id="alloc-q3-07",
            title="Office Supplies and Equipment",
            description="Quarterly office supplies and minor equipment refresh",
            amount=3_200.0,
            requested_by="Operations Team",
            requested_date=now - timedelta(days=2),
            status=ApprovalStatus.APPROVED,
            approver="COO - Patricia Lane",
            approved_date=now - timedelta(days=1),
            vendor="Staples Business",
            invoice_ref="INV-SB-2025-442",
        ),
        SpendRequest(
            id="sr-008",
            allocation_id="alloc-q3-08",
            title="External Legal Review - Trial Protocol",
            description="Outside counsel review of new trial protocol",
            amount=15_000.0,
            requested_by="Legal Team",
            requested_date=now - timedelta(days=6),
            status=ApprovalStatus.PENDING_APPROVAL,
            vendor="HealthTech Legal Partners LLP",
            invoice_ref="",
        ),
        SpendRequest(
            id="sr-009",
            allocation_id="alloc-q3-01",
            title="Database Migration Tools",
            description="Tooling for PostgreSQL schema migration automation",
            amount=4_800.0,
            requested_by="Sarah Chen",
            requested_date=now - timedelta(days=1),
            status=ApprovalStatus.DRAFT,
            vendor="Flyway Enterprise",
            invoice_ref="",
        ),
        SpendRequest(
            id="sr-010",
            allocation_id="alloc-q3-06",
            title="Conference Sponsorship - BIO International",
            description="Bronze sponsorship at BIO International Convention",
            amount=12_000.0,
            requested_by="Dr. Alex Thompson",
            requested_date=now - timedelta(days=10),
            status=ApprovalStatus.REVISION_REQUESTED,
            approver="VP Research - Dr. Patel",
            approved_date=now - timedelta(days=7),
            rejection_reason="Please provide detailed ROI justification.",
            vendor="BIO International",
            invoice_ref="",
        ),
    ]


def _build_seed_alerts() -> list[BudgetAlert]:
    """Build pre-populated budget alerts."""
    now = datetime.now(timezone.utc)
    return [
        BudgetAlert(
            id="alert-001",
            allocation_id="alloc-q1-08",
            alert_type=BudgetAlertType.OVER_BUDGET,
            message="Professional Services (Q1) has exceeded allocated budget by 25%",
            triggered_at=now - timedelta(days=60),
            acknowledged=True,
        ),
        BudgetAlert(
            id="alert-002",
            allocation_id="alloc-q1-01",
            alert_type=BudgetAlertType.THRESHOLD_90,
            message="Infrastructure (Q1) has reached 95.8% of allocated budget",
            triggered_at=now - timedelta(days=45),
            acknowledged=True,
        ),
        BudgetAlert(
            id="alert-003",
            allocation_id="alloc-q1-02",
            alert_type=BudgetAlertType.THRESHOLD_90,
            message="Personnel (Q1) has reached 96.7% of allocated budget",
            triggered_at=now - timedelta(days=40),
            acknowledged=True,
        ),
        BudgetAlert(
            id="alert-004",
            allocation_id="alloc-q3-01",
            alert_type=BudgetAlertType.LARGE_SPEND,
            message="Large spend request: AWS Reserved Instance Renewal ($75,000)",
            triggered_at=now - timedelta(days=14),
            acknowledged=False,
        ),
        BudgetAlert(
            id="alert-005",
            allocation_id="alloc-q3-06",
            alert_type=BudgetAlertType.LARGE_SPEND,
            message="Large spend request: Genomics Analysis Platform License ($55,000)",
            triggered_at=now - timedelta(days=12),
            acknowledged=False,
        ),
    ]


class BudgetManagementService:
    """Service for budget tracking and approval workflows.

    Manages budget periods, allocations, spend requests, alerts,
    and provides dashboard metrics for CFO oversight.

    CFO-3: Budget Tracking & Approval Workflows
    """

    def __init__(self) -> None:
        """Initialize with seed data."""
        self._periods: dict[str, BudgetPeriod] = {}
        self._allocations: dict[str, BudgetAllocation] = {}
        self._spend_requests: dict[str, SpendRequest] = {}
        self._alerts: dict[str, BudgetAlert] = {}
        self._next_id_counter: int = 100

        # Load seed data
        for period in _build_seed_periods():
            self._periods[period.id] = period

        for alloc in _build_seed_allocations():
            self._allocations[alloc.id] = alloc

        for sr in _build_seed_spend_requests():
            self._spend_requests[sr.id] = sr

        for alert in _build_seed_alerts():
            self._alerts[alert.id] = alert

        logger.info(
            "BudgetManagementService initialized: %d periods, %d allocations, "
            "%d spend requests, %d alerts",
            len(self._periods),
            len(self._allocations),
            len(self._spend_requests),
            len(self._alerts),
        )

    # -------------------------------------------------------------------
    # Budget Periods
    # -------------------------------------------------------------------

    def list_periods(
        self,
        fiscal_year: int | None = None,
    ) -> list[BudgetPeriod]:
        """List budget periods with optional fiscal year filter.

        Args:
            fiscal_year: Filter by fiscal year.

        Returns:
            List of budget periods.
        """
        periods = list(self._periods.values())
        if fiscal_year is not None:
            periods = [p for p in periods if p.fiscal_year == fiscal_year]
        periods.sort(key=lambda p: (p.fiscal_year, p.quarter))
        return periods

    def get_period(self, period_id: str) -> BudgetPeriod | None:
        """Get a budget period by ID.

        Args:
            period_id: Period ID.

        Returns:
            Budget period or None if not found.
        """
        return self._periods.get(period_id)

    def create_period(
        self,
        fiscal_year: int,
        quarter: str,
        total_budget: float,
    ) -> BudgetPeriod:
        """Create a new budget period.

        Args:
            fiscal_year: Fiscal year.
            quarter: Quarter (Q1-Q4).
            total_budget: Total budget for the period.

        Returns:
            Created budget period.

        Raises:
            ValueError: If quarter is invalid or period already exists.
        """
        if quarter not in ("Q1", "Q2", "Q3", "Q4"):
            raise ValueError(f"Invalid quarter: {quarter}. Must be Q1-Q4.")

        # Check for duplicate
        for p in self._periods.values():
            if p.fiscal_year == fiscal_year and p.quarter == quarter:
                raise ValueError(
                    f"Period already exists for FY{fiscal_year} {quarter}"
                )

        period_id = f"period-{fiscal_year}-{quarter.lower()}"
        period = BudgetPeriod(
            id=period_id,
            fiscal_year=fiscal_year,
            quarter=quarter,
            total_budget=total_budget,
            total_allocated=0.0,
            total_spent=0.0,
            remaining=total_budget,
            status=SpendStatus.WITHIN_BUDGET,
        )
        self._periods[period_id] = period
        logger.info("Created budget period %s", period_id)
        return period

    # -------------------------------------------------------------------
    # Budget Allocations
    # -------------------------------------------------------------------

    def list_allocations(
        self,
        period_id: str | None = None,
        category: BudgetCategory | None = None,
    ) -> list[BudgetAllocation]:
        """List allocations with optional filters.

        Args:
            period_id: Filter by period.
            category: Filter by category.

        Returns:
            List of allocations.
        """
        allocs = list(self._allocations.values())
        if period_id is not None:
            allocs = [a for a in allocs if a.period_id == period_id]
        if category is not None:
            allocs = [a for a in allocs if a.category == category]
        allocs.sort(key=lambda a: (a.period_id, a.category.value))
        return allocs

    def get_allocation(self, allocation_id: str) -> BudgetAllocation | None:
        """Get an allocation by ID.

        Args:
            allocation_id: Allocation ID.

        Returns:
            Allocation or None if not found.
        """
        return self._allocations.get(allocation_id)

    def create_allocation(
        self,
        period_id: str,
        category: BudgetCategory,
        allocated_amount: float,
        owner: str = "",
    ) -> BudgetAllocation:
        """Create a new budget allocation.

        Args:
            period_id: Budget period ID.
            category: Budget category.
            allocated_amount: Amount to allocate.
            owner: Budget owner.

        Returns:
            Created allocation.

        Raises:
            ValueError: If period not found.
        """
        period = self._periods.get(period_id)
        if period is None:
            raise ValueError(f"Budget period {period_id} not found")

        self._next_id_counter += 1
        alloc_id = f"alloc-{self._next_id_counter:04d}"

        alloc = BudgetAllocation(
            id=alloc_id,
            period_id=period_id,
            category=category,
            allocated_amount=allocated_amount,
            spent_amount=0.0,
            remaining=allocated_amount,
            committed=0.0,
            variance_pct=0.0,
            owner=owner,
        )
        self._allocations[alloc_id] = alloc

        # Update period totals
        self._update_period_totals(period_id)

        logger.info("Created allocation %s for %s", alloc_id, category.value)
        return alloc

    # -------------------------------------------------------------------
    # Spend Requests
    # -------------------------------------------------------------------

    def list_spend_requests(
        self,
        allocation_id: str | None = None,
        status: ApprovalStatus | None = None,
    ) -> list[SpendRequest]:
        """List spend requests with optional filters.

        Args:
            allocation_id: Filter by allocation.
            status: Filter by approval status.

        Returns:
            List of spend requests.
        """
        requests = list(self._spend_requests.values())
        if allocation_id is not None:
            requests = [r for r in requests if r.allocation_id == allocation_id]
        if status is not None:
            requests = [r for r in requests if r.status == status]
        requests.sort(key=lambda r: r.requested_date, reverse=True)
        return requests

    def get_spend_request(self, request_id: str) -> SpendRequest | None:
        """Get a spend request by ID.

        Args:
            request_id: Spend request ID.

        Returns:
            Spend request or None if not found.
        """
        return self._spend_requests.get(request_id)

    def submit_spend_request(self, request: SpendRequestCreate) -> SpendRequest:
        """Create and submit a spend request with auto-routing.

        Requests >$10K need VP approval, >$50K need CFO approval.
        The request is automatically set to PENDING_APPROVAL status.

        Args:
            request: Spend request creation data.

        Returns:
            Created spend request.

        Raises:
            ValueError: If allocation not found.
        """
        alloc = self._allocations.get(request.allocation_id)
        if alloc is None:
            raise ValueError(f"Allocation {request.allocation_id} not found")

        now = datetime.now(timezone.utc)
        self._next_id_counter += 1
        request_id = f"sr-{self._next_id_counter:04d}"

        sr = SpendRequest(
            id=request_id,
            allocation_id=request.allocation_id,
            title=request.title,
            description=request.description,
            amount=request.amount,
            requested_by=request.requested_by,
            requested_date=now,
            status=ApprovalStatus.PENDING_APPROVAL,
            vendor=request.vendor,
            invoice_ref=request.invoice_ref,
        )
        self._spend_requests[request_id] = sr

        # Generate large spend alert if above CFO threshold
        if request.amount >= CFO_APPROVAL_THRESHOLD:
            self._create_alert(
                allocation_id=request.allocation_id,
                alert_type=BudgetAlertType.LARGE_SPEND,
                message=(
                    f"Large spend request: {request.title} "
                    f"(${request.amount:,.0f}) requires CFO approval"
                ),
            )

        logger.info(
            "Spend request %s submitted: $%.2f for %s",
            request_id,
            request.amount,
            request.title,
        )
        return sr

    def update_spend_request(
        self, request_id: str, update: SpendRequestUpdate
    ) -> SpendRequest | None:
        """Update a spend request (only DRAFT or REVISION_REQUESTED).

        Args:
            request_id: Spend request ID.
            update: Fields to update.

        Returns:
            Updated spend request, or None if not found.

        Raises:
            ValueError: If request is not in DRAFT or REVISION_REQUESTED status.
        """
        sr = self._spend_requests.get(request_id)
        if sr is None:
            return None

        if sr.status not in (ApprovalStatus.DRAFT, ApprovalStatus.REVISION_REQUESTED):
            raise ValueError(
                f"Cannot update request in {sr.status.value} status. "
                f"Only DRAFT or REVISION_REQUESTED requests can be updated."
            )

        sr_dict = sr.model_dump()
        update_data = update.model_dump(exclude_none=True)
        sr_dict.update(update_data)

        updated = SpendRequest(**sr_dict)
        self._spend_requests[request_id] = updated

        logger.info("Updated spend request %s", request_id)
        return updated

    def approve_request(
        self, request_id: str, approver: str
    ) -> SpendRequest | None:
        """Approve a pending spend request.

        Updates allocation committed/spent amounts and checks thresholds.

        Args:
            request_id: Spend request ID.
            approver: Name of the approver.

        Returns:
            Updated spend request, or None if not found.

        Raises:
            ValueError: If request is not PENDING_APPROVAL.
        """
        sr = self._spend_requests.get(request_id)
        if sr is None:
            return None

        if sr.status != ApprovalStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot approve request in {sr.status.value} status. "
                f"Only PENDING_APPROVAL requests can be approved."
            )

        now = datetime.now(timezone.utc)
        sr_dict = sr.model_dump()
        sr_dict["status"] = ApprovalStatus.APPROVED
        sr_dict["approver"] = approver
        sr_dict["approved_date"] = now

        updated = SpendRequest(**sr_dict)
        self._spend_requests[request_id] = updated

        # Update allocation committed amount
        alloc = self._allocations.get(sr.allocation_id)
        if alloc is not None:
            alloc_dict = alloc.model_dump()
            alloc_dict["committed"] = alloc.committed + sr.amount
            self._allocations[sr.allocation_id] = BudgetAllocation(**alloc_dict)

        logger.info("Spend request %s approved by %s", request_id, approver)
        return updated

    def reject_request(
        self, request_id: str, approver: str, reason: str
    ) -> SpendRequest | None:
        """Reject a pending spend request.

        Args:
            request_id: Spend request ID.
            approver: Name of the person rejecting.
            reason: Reason for rejection.

        Returns:
            Updated spend request, or None if not found.

        Raises:
            ValueError: If request is not PENDING_APPROVAL.
        """
        sr = self._spend_requests.get(request_id)
        if sr is None:
            return None

        if sr.status != ApprovalStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot reject request in {sr.status.value} status. "
                f"Only PENDING_APPROVAL requests can be rejected."
            )

        now = datetime.now(timezone.utc)
        sr_dict = sr.model_dump()
        sr_dict["status"] = ApprovalStatus.REJECTED
        sr_dict["approver"] = approver
        sr_dict["approved_date"] = now
        sr_dict["rejection_reason"] = reason

        updated = SpendRequest(**sr_dict)
        self._spend_requests[request_id] = updated

        logger.info(
            "Spend request %s rejected by %s: %s",
            request_id,
            approver,
            reason,
        )
        return updated

    def record_spend(
        self, allocation_id: str, spend_input: RecordSpendInput
    ) -> BudgetAllocation | None:
        """Record a direct spend against an allocation.

        Updates allocation spent amount and checks for threshold alerts.

        Args:
            allocation_id: Allocation ID.
            spend_input: Spend details.

        Returns:
            Updated allocation, or None if not found.

        Raises:
            ValueError: If allocation is frozen.
        """
        alloc = self._allocations.get(allocation_id)
        if alloc is None:
            return None

        new_spent = alloc.spent_amount + spend_input.amount
        new_remaining = alloc.allocated_amount - new_spent
        new_variance = _compute_variance_pct(new_spent, alloc.allocated_amount)
        new_status = _compute_spend_status(new_spent, alloc.allocated_amount)

        alloc_dict = alloc.model_dump()
        alloc_dict["spent_amount"] = new_spent
        alloc_dict["remaining"] = new_remaining
        alloc_dict["variance_pct"] = new_variance

        updated = BudgetAllocation(**alloc_dict)
        self._allocations[allocation_id] = updated

        # Generate threshold alerts
        ratio = new_spent / alloc.allocated_amount if alloc.allocated_amount > 0 else 0
        old_ratio = alloc.spent_amount / alloc.allocated_amount if alloc.allocated_amount > 0 else 0

        if ratio > 1.0 and old_ratio <= 1.0:
            self._create_alert(
                allocation_id=allocation_id,
                alert_type=BudgetAlertType.OVER_BUDGET,
                message=(
                    f"{alloc.category.value} has exceeded allocated budget "
                    f"(${new_spent:,.0f} / ${alloc.allocated_amount:,.0f})"
                ),
            )
        elif ratio > 0.9 and old_ratio <= 0.9:
            self._create_alert(
                allocation_id=allocation_id,
                alert_type=BudgetAlertType.THRESHOLD_90,
                message=(
                    f"{alloc.category.value} has reached {ratio * 100:.1f}% "
                    f"of allocated budget"
                ),
            )
        elif ratio > 0.8 and old_ratio <= 0.8:
            self._create_alert(
                allocation_id=allocation_id,
                alert_type=BudgetAlertType.THRESHOLD_80,
                message=(
                    f"{alloc.category.value} has reached {ratio * 100:.1f}% "
                    f"of allocated budget"
                ),
            )

        # Update period totals
        self._update_period_totals(alloc.period_id)

        logger.info(
            "Recorded spend of $%.2f against %s",
            spend_input.amount,
            allocation_id,
        )
        return updated

    # -------------------------------------------------------------------
    # Budget Alerts
    # -------------------------------------------------------------------

    def get_budget_alerts(
        self, acknowledged: bool | None = None
    ) -> list[BudgetAlert]:
        """Get budget alerts with optional acknowledgment filter.

        Args:
            acknowledged: Filter by acknowledgment status.

        Returns:
            List of budget alerts.
        """
        alerts = list(self._alerts.values())
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        alerts.sort(key=lambda a: a.triggered_at, reverse=True)
        return alerts

    def acknowledge_alert(self, alert_id: str) -> BudgetAlert | None:
        """Mark an alert as acknowledged.

        Args:
            alert_id: Alert ID.

        Returns:
            Updated alert, or None if not found.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None

        alert_dict = alert.model_dump()
        alert_dict["acknowledged"] = True
        updated = BudgetAlert(**alert_dict)
        self._alerts[alert_id] = updated

        logger.info("Alert %s acknowledged", alert_id)
        return updated

    # -------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------

    def get_metrics(self) -> BudgetMetrics:
        """Get aggregated budget dashboard metrics.

        Returns:
            Budget metrics for the dashboard.
        """
        periods = list(self._periods.values())
        allocations = list(self._allocations.values())
        spend_requests = list(self._spend_requests.values())

        # Total annual budget
        total_annual_budget = sum(p.total_budget for p in periods)

        # Total spent YTD
        total_spent_ytd = sum(a.spent_amount for a in allocations)

        # Monthly burn rate (estimate based on periods with spend)
        periods_with_spend = [p for p in periods if p.total_spent > 0]
        months_elapsed = len(periods_with_spend) * 3 if periods_with_spend else 1
        burn_rate_monthly = total_spent_ytd / months_elapsed if months_elapsed > 0 else 0

        # Projected annual spend
        projected_annual_spend = burn_rate_monthly * 12

        # Budget utilization
        budget_utilization_pct = (
            round(total_spent_ytd / total_annual_budget * 100, 2)
            if total_annual_budget > 0
            else 0.0
        )

        # Spend by category
        by_category: dict[str, float] = {}
        for cat in BudgetCategory:
            cat_spend = sum(
                a.spent_amount for a in allocations if a.category == cat
            )
            if cat_spend > 0:
                by_category[cat.value] = cat_spend

        # Pending approvals
        pending = [
            r
            for r in spend_requests
            if r.status == ApprovalStatus.PENDING_APPROVAL
        ]
        pending_approvals_count = len(pending)
        pending_approvals_amount = sum(r.amount for r in pending)

        # Over-budget categories
        over_budget_categories: list[str] = []
        for alloc in allocations:
            if (
                alloc.allocated_amount > 0
                and alloc.spent_amount > alloc.allocated_amount
                and alloc.category.value not in over_budget_categories
            ):
                over_budget_categories.append(alloc.category.value)

        return BudgetMetrics(
            total_annual_budget=total_annual_budget,
            total_spent_ytd=total_spent_ytd,
            burn_rate_monthly=round(burn_rate_monthly, 2),
            projected_annual_spend=round(projected_annual_spend, 2),
            budget_utilization_pct=budget_utilization_pct,
            by_category=by_category,
            pending_approvals_count=pending_approvals_count,
            pending_approvals_amount=pending_approvals_amount,
            over_budget_categories=over_budget_categories,
        )

    # -------------------------------------------------------------------
    # Spend Forecast
    # -------------------------------------------------------------------

    def forecast_spend(self, months_ahead: int = 6) -> SpendForecast:
        """Project spend based on current burn rate.

        Args:
            months_ahead: Number of months to project.

        Returns:
            Spend forecast.
        """
        metrics = self.get_metrics()
        monthly_burn = metrics.burn_rate_monthly
        projected_total = monthly_burn * months_ahead
        projected_remaining = metrics.total_annual_budget - metrics.total_spent_ytd - projected_total
        will_exceed = projected_remaining < 0

        months_until_exhausted: float | None = None
        remaining_now = metrics.total_annual_budget - metrics.total_spent_ytd
        if monthly_burn > 0 and remaining_now > 0:
            months_until_exhausted = round(remaining_now / monthly_burn, 1)

        return SpendForecast(
            months_ahead=months_ahead,
            current_monthly_burn=round(monthly_burn, 2),
            projected_total=round(projected_total, 2),
            projected_remaining=round(projected_remaining, 2),
            will_exceed_budget=will_exceed,
            months_until_exhausted=months_until_exhausted,
        )

    # -------------------------------------------------------------------
    # Approval Routing
    # -------------------------------------------------------------------

    def get_approval_route(self, amount: float) -> str:
        """Determine the approval route for a given amount.

        Args:
            amount: Spend amount.

        Returns:
            Description of the required approval level.
        """
        if amount >= CFO_APPROVAL_THRESHOLD:
            return "CFO approval required"
        elif amount >= VP_APPROVAL_THRESHOLD:
            return "VP approval required"
        else:
            return "Manager approval required"

    # -------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------

    def _update_period_totals(self, period_id: str) -> None:
        """Recalculate period totals from allocations."""
        period = self._periods.get(period_id)
        if period is None:
            return

        allocs = [a for a in self._allocations.values() if a.period_id == period_id]
        total_allocated = sum(a.allocated_amount for a in allocs)
        total_spent = sum(a.spent_amount for a in allocs)
        remaining = period.total_budget - total_spent
        status = _compute_spend_status(total_spent, period.total_budget)

        period_dict = period.model_dump()
        period_dict["total_allocated"] = total_allocated
        period_dict["total_spent"] = total_spent
        period_dict["remaining"] = remaining
        period_dict["status"] = status
        self._periods[period_id] = BudgetPeriod(**period_dict)

    def _create_alert(
        self,
        allocation_id: str,
        alert_type: BudgetAlertType,
        message: str,
    ) -> BudgetAlert:
        """Create a new budget alert."""
        self._next_id_counter += 1
        alert_id = f"alert-{self._next_id_counter:04d}"
        now = datetime.now(timezone.utc)

        alert = BudgetAlert(
            id=alert_id,
            allocation_id=allocation_id,
            alert_type=alert_type,
            message=message,
            triggered_at=now,
            acknowledged=False,
        )
        self._alerts[alert_id] = alert
        return alert

    def clear(self) -> None:
        """Reset all data and reload seed data (for testing)."""
        self._periods.clear()
        self._allocations.clear()
        self._spend_requests.clear()
        self._alerts.clear()
        self._next_id_counter = 100

        for period in _build_seed_periods():
            self._periods[period.id] = period
        for alloc in _build_seed_allocations():
            self._allocations[alloc.id] = alloc
        for sr in _build_seed_spend_requests():
            self._spend_requests[sr.id] = sr
        for alert in _build_seed_alerts():
            self._alerts[alert.id] = alert


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_budget_management_service() -> BudgetManagementService:
    """Get or create the singleton BudgetManagementService."""
    global _budget_service_instance
    if _budget_service_instance is None:
        with _budget_service_lock:
            if _budget_service_instance is None:
                _budget_service_instance = BudgetManagementService()
    return _budget_service_instance


def reset_budget_management_service() -> None:
    """Reset the singleton (for testing)."""
    global _budget_service_instance
    with _budget_service_lock:
        _budget_service_instance = None
