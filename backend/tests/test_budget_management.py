"""Tests for CFO-3: Budget Tracking & Approval Workflows.

Tests cover:
- Seed data verification (periods, allocations, spend requests, alerts)
- Budget period CRUD (list, get, create, duplicate, invalid quarter)
- Allocation CRUD (list, get, create, filter by period/category)
- Spend request CRUD (list, get, submit, update, filter by status)
- Approval workflows (approve, reject, threshold-based routing)
- Record spend against allocations (threshold alerts 80%/90%/over-budget)
- Variance analysis (variance_pct calculation)
- Forecasting (burn rate projections, budget exhaustion)
- Budget metrics (aggregated dashboard metrics)
- Department summaries (grouped by owner)
- Budget alerts (list, filter, acknowledge)
- Error handling (404s, 400s for invalid operations)
- Singleton pattern (get/reset)

Target: 100+ test cases.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.budget_management import (
    ApprovalStatus,
    BudgetCategory,
    SpendStatus,
)
from app.services.budget_management_service import (
    BudgetManagementService,
    get_budget_management_service,
    reset_budget_management_service,
)

API_PREFIX = "/api/v1/budget-management"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_budget_management_service()
    yield
    reset_budget_management_service()


@pytest.fixture
def service() -> BudgetManagementService:
    return get_budget_management_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests for pre-populated seed data."""

    def test_seed_periods_count(self, service: BudgetManagementService):
        """Service should have 4 quarterly periods for FY2025."""
        periods = service.list_periods()
        assert len(periods) == 4

    def test_seed_periods_quarters(self, service: BudgetManagementService):
        """Seed periods should cover Q1-Q4."""
        periods = service.list_periods()
        quarters = {p.quarter for p in periods}
        assert quarters == {"Q1", "Q2", "Q3", "Q4"}

    def test_seed_periods_fiscal_year(self, service: BudgetManagementService):
        """All seed periods should be FY2025."""
        periods = service.list_periods()
        for p in periods:
            assert p.fiscal_year == 2025

    def test_seed_periods_have_ids(self, service: BudgetManagementService):
        """All seed periods should have period- prefixed IDs."""
        periods = service.list_periods()
        for p in periods:
            assert p.id.startswith("period-")

    def test_seed_allocations_count(self, service: BudgetManagementService):
        """Service should have 32 allocations (8 categories * 4 quarters)."""
        allocs = service.list_allocations()
        assert len(allocs) == 32

    def test_seed_allocations_per_quarter(self, service: BudgetManagementService):
        """Each quarter should have 8 category allocations."""
        for qtr in ["q1", "q2", "q3", "q4"]:
            period_id = f"period-2025-{qtr}"
            allocs = service.list_allocations(period_id=period_id)
            assert len(allocs) == 8

    def test_seed_spend_requests_count(self, service: BudgetManagementService):
        """Service should have 10 pre-populated spend requests."""
        requests = service.list_spend_requests()
        assert len(requests) == 10

    def test_seed_spend_request_statuses(self, service: BudgetManagementService):
        """Seed requests should have various statuses."""
        requests = service.list_spend_requests()
        statuses = {r.status for r in requests}
        assert ApprovalStatus.APPROVED in statuses
        assert ApprovalStatus.PENDING_APPROVAL in statuses
        assert ApprovalStatus.DRAFT in statuses
        assert ApprovalStatus.REJECTED in statuses
        assert ApprovalStatus.REVISION_REQUESTED in statuses

    def test_seed_alerts_count(self, service: BudgetManagementService):
        """Service should have 5 pre-populated alerts."""
        alerts = service.get_budget_alerts()
        assert len(alerts) == 5

    def test_seed_alerts_types(self, service: BudgetManagementService):
        """Seed alerts should have various types."""
        alerts = service.get_budget_alerts()
        types = {a.alert_type for a in alerts}
        assert len(types) >= 3

    def test_q1_period_status_warning(self, service: BudgetManagementService):
        """Q1 should be in WARNING status (>80% spent)."""
        period = service.get_period("period-2025-q1")
        assert period is not None
        assert period.status == SpendStatus.WARNING

    def test_q4_period_no_spend(self, service: BudgetManagementService):
        """Q4 should have zero spend."""
        period = service.get_period("period-2025-q4")
        assert period is not None
        assert period.total_spent == 0.0

    def test_seed_q1_professional_services_over_budget(self, service: BudgetManagementService):
        """Q1 Professional Services should be over budget (125K spent vs 100K allocated)."""
        alloc = service.get_allocation("alloc-q1-08")
        assert alloc is not None
        assert alloc.spent_amount > alloc.allocated_amount
        assert alloc.variance_pct > 0


# ============================================================================
# Budget Period API Tests
# ============================================================================


class TestBudgetPeriodAPI:
    """Tests for budget period endpoints."""

    @pytest.mark.anyio
    async def test_list_periods(self, client: AsyncClient):
        """GET /periods should return all periods."""
        resp = await client.get(f"{API_PREFIX}/periods")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_periods_filter_fiscal_year(self, client: AsyncClient):
        """GET /periods?fiscal_year=2025 should return 4 periods."""
        resp = await client.get(f"{API_PREFIX}/periods", params={"fiscal_year": 2025})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_periods_filter_no_match(self, client: AsyncClient):
        """GET /periods?fiscal_year=2099 should return empty."""
        resp = await client.get(f"{API_PREFIX}/periods", params={"fiscal_year": 2099})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_period(self, client: AsyncClient):
        """GET /periods/{id} should return a specific period."""
        resp = await client.get(f"{API_PREFIX}/periods/period-2025-q1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "period-2025-q1"
        assert data["fiscal_year"] == 2025
        assert data["quarter"] == "Q1"

    @pytest.mark.anyio
    async def test_get_period_not_found(self, client: AsyncClient):
        """GET /periods/{id} should return 404 for missing period."""
        resp = await client.get(f"{API_PREFIX}/periods/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_period(self, client: AsyncClient):
        """POST /periods should create a new period."""
        resp = await client.post(
            f"{API_PREFIX}/periods",
            params={
                "fiscal_year": 2026,
                "quarter": "Q1",
                "total_budget": 5000000,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["fiscal_year"] == 2026
        assert data["quarter"] == "Q1"
        assert data["total_budget"] == 5000000
        assert data["total_spent"] == 0.0
        assert data["status"] == "WITHIN_BUDGET"

    @pytest.mark.anyio
    async def test_create_period_duplicate(self, client: AsyncClient):
        """POST /periods should return 400 for duplicate period."""
        resp = await client.post(
            f"{API_PREFIX}/periods",
            params={
                "fiscal_year": 2025,
                "quarter": "Q1",
                "total_budget": 1000000,
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_period_invalid_quarter(self, client: AsyncClient):
        """POST /periods should return 400 for invalid quarter."""
        resp = await client.post(
            f"{API_PREFIX}/periods",
            params={
                "fiscal_year": 2026,
                "quarter": "Q5",
                "total_budget": 1000000,
            },
        )
        assert resp.status_code == 400


# ============================================================================
# Allocation API Tests
# ============================================================================


class TestAllocationAPI:
    """Tests for budget allocation endpoints."""

    @pytest.mark.anyio
    async def test_list_allocations(self, client: AsyncClient):
        """GET /allocations should return all 32 allocations."""
        resp = await client.get(f"{API_PREFIX}/allocations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 32

    @pytest.mark.anyio
    async def test_list_allocations_filter_period(self, client: AsyncClient):
        """GET /allocations?period_id=... should filter by period."""
        resp = await client.get(
            f"{API_PREFIX}/allocations",
            params={"period_id": "period-2025-q3"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        for item in data["items"]:
            assert item["period_id"] == "period-2025-q3"

    @pytest.mark.anyio
    async def test_list_allocations_filter_category(self, client: AsyncClient):
        """GET /allocations?category=INFRASTRUCTURE should return 4 (one per quarter)."""
        resp = await client.get(
            f"{API_PREFIX}/allocations",
            params={"category": "INFRASTRUCTURE"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["category"] == "INFRASTRUCTURE"

    @pytest.mark.anyio
    async def test_list_allocations_filter_both(self, client: AsyncClient):
        """Filter by period AND category should return 1 allocation."""
        resp = await client.get(
            f"{API_PREFIX}/allocations",
            params={
                "period_id": "period-2025-q1",
                "category": "PERSONNEL",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_get_allocation(self, client: AsyncClient):
        """GET /allocations/{id} should return a specific allocation."""
        resp = await client.get(f"{API_PREFIX}/allocations/alloc-q3-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "alloc-q3-01"
        assert data["category"] == "INFRASTRUCTURE"
        assert data["owner"] == "VP Engineering"

    @pytest.mark.anyio
    async def test_get_allocation_not_found(self, client: AsyncClient):
        """GET /allocations/{id} should return 404."""
        resp = await client.get(f"{API_PREFIX}/allocations/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_allocation(self, client: AsyncClient):
        """POST /allocations should create a new allocation."""
        resp = await client.post(
            f"{API_PREFIX}/allocations",
            params={
                "period_id": "period-2025-q4",
                "category": "INFRASTRUCTURE",
                "allocated_amount": 100000,
                "owner": "Test Owner",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["period_id"] == "period-2025-q4"
        assert data["category"] == "INFRASTRUCTURE"
        assert data["allocated_amount"] == 100000
        assert data["owner"] == "Test Owner"
        assert data["spent_amount"] == 0.0

    @pytest.mark.anyio
    async def test_create_allocation_invalid_period(self, client: AsyncClient):
        """POST /allocations with bad period should return 400."""
        resp = await client.post(
            f"{API_PREFIX}/allocations",
            params={
                "period_id": "nonexistent-period",
                "category": "INFRASTRUCTURE",
                "allocated_amount": 100000,
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_spend(self, client: AsyncClient):
        """POST /allocations/{id}/record-spend should update allocation."""
        resp = await client.post(
            f"{API_PREFIX}/allocations/alloc-q4-01/record-spend",
            json={"amount": 50000, "vendor": "TestVendor", "description": "Test spend"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["spent_amount"] == 50000
        assert data["remaining"] == data["allocated_amount"] - 50000

    @pytest.mark.anyio
    async def test_record_spend_not_found(self, client: AsyncClient):
        """POST /allocations/{id}/record-spend for missing alloc should return 404."""
        resp = await client.post(
            f"{API_PREFIX}/allocations/nonexistent/record-spend",
            json={"amount": 100},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_spend_triggers_80_pct_alert(self, service: BudgetManagementService):
        """Recording spend past 80% should create a THRESHOLD_80 alert."""
        from app.schemas.budget_management import RecordSpendInput, BudgetAlertType

        initial_alerts = len(service.get_budget_alerts())
        # alloc-q4-01 has 600K allocated, 0 spent. Spend 490K = 81.7%
        service.record_spend("alloc-q4-01", RecordSpendInput(amount=490000))
        new_alerts = service.get_budget_alerts()
        assert len(new_alerts) > initial_alerts
        latest = new_alerts[0]
        assert latest.alert_type == BudgetAlertType.THRESHOLD_80

    @pytest.mark.anyio
    async def test_record_spend_triggers_90_pct_alert(self, service: BudgetManagementService):
        """Recording spend past 90% should create a THRESHOLD_90 alert."""
        from app.schemas.budget_management import RecordSpendInput, BudgetAlertType

        # alloc-q4-02 has 1,050,000 allocated. Spend 950K = 90.5%
        service.record_spend("alloc-q4-02", RecordSpendInput(amount=950000))
        alerts = service.get_budget_alerts()
        threshold_90 = [a for a in alerts if a.allocation_id == "alloc-q4-02"]
        assert len(threshold_90) > 0
        assert threshold_90[0].alert_type == BudgetAlertType.THRESHOLD_90

    @pytest.mark.anyio
    async def test_record_spend_triggers_over_budget_alert(self, service: BudgetManagementService):
        """Recording spend over 100% should create OVER_BUDGET alert."""
        from app.schemas.budget_management import RecordSpendInput, BudgetAlertType

        # alloc-q4-03 has 300,000 allocated. Spend 310K = 103%
        service.record_spend("alloc-q4-03", RecordSpendInput(amount=310000))
        alerts = service.get_budget_alerts()
        over_alerts = [
            a for a in alerts
            if a.allocation_id == "alloc-q4-03"
            and a.alert_type == BudgetAlertType.OVER_BUDGET
        ]
        assert len(over_alerts) == 1


# ============================================================================
# Spend Request API Tests
# ============================================================================


class TestSpendRequestAPI:
    """Tests for spend request endpoints."""

    @pytest.mark.anyio
    async def test_list_spend_requests(self, client: AsyncClient):
        """GET /spend-requests should return all 10 seed requests."""
        resp = await client.get(f"{API_PREFIX}/spend-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_spend_requests_filter_status(self, client: AsyncClient):
        """GET /spend-requests?status=PENDING_APPROVAL should return 3."""
        resp = await client.get(
            f"{API_PREFIX}/spend-requests",
            params={"status": "PENDING_APPROVAL"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["status"] == "PENDING_APPROVAL"

    @pytest.mark.anyio
    async def test_list_spend_requests_filter_allocation(self, client: AsyncClient):
        """Filter by allocation_id should narrow results."""
        resp = await client.get(
            f"{API_PREFIX}/spend-requests",
            params={"allocation_id": "alloc-q3-01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # sr-001 and sr-009

    @pytest.mark.anyio
    async def test_get_spend_request(self, client: AsyncClient):
        """GET /spend-requests/{id} should return a specific request."""
        resp = await client.get(f"{API_PREFIX}/spend-requests/sr-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sr-001"
        assert data["title"] == "AWS Reserved Instance Renewal"
        assert data["amount"] == 75000.0
        assert data["status"] == "APPROVED"

    @pytest.mark.anyio
    async def test_get_spend_request_not_found(self, client: AsyncClient):
        """GET /spend-requests/{id} should return 404."""
        resp = await client.get(f"{API_PREFIX}/spend-requests/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_spend_request(self, client: AsyncClient):
        """POST /spend-requests should create and auto-set to PENDING_APPROVAL."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests",
            json={
                "allocation_id": "alloc-q3-01",
                "title": "New Cloud Service",
                "description": "Monthly cloud hosting",
                "amount": 5000,
                "requested_by": "Test User",
                "vendor": "CloudCo",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Cloud Service"
        assert data["amount"] == 5000
        assert data["status"] == "PENDING_APPROVAL"
        assert data["id"].startswith("sr-")

    @pytest.mark.anyio
    async def test_submit_spend_request_invalid_allocation(self, client: AsyncClient):
        """POST /spend-requests with bad allocation should return 400."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests",
            json={
                "allocation_id": "nonexistent",
                "title": "Bad",
                "amount": 100,
                "requested_by": "Test",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_large_spend_creates_alert(self, client: AsyncClient):
        """Submit a request >= $50K should create a LARGE_SPEND alert."""
        svc = get_budget_management_service()
        initial_alerts = len(svc.get_budget_alerts())
        resp = await client.post(
            f"{API_PREFIX}/spend-requests",
            json={
                "allocation_id": "alloc-q3-01",
                "title": "Big Purchase",
                "amount": 60000,
                "requested_by": "Test User",
            },
        )
        assert resp.status_code == 201
        new_alerts = svc.get_budget_alerts()
        assert len(new_alerts) > initial_alerts

    @pytest.mark.anyio
    async def test_update_spend_request_draft(self, client: AsyncClient):
        """PUT /spend-requests/{id} should update a DRAFT request."""
        # sr-005 is DRAFT
        resp = await client.put(
            f"{API_PREFIX}/spend-requests/sr-005",
            json={"title": "Updated Title", "amount": 9000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["amount"] == 9000

    @pytest.mark.anyio
    async def test_update_spend_request_revision_requested(self, client: AsyncClient):
        """PUT should work for REVISION_REQUESTED status too."""
        # sr-010 is REVISION_REQUESTED
        resp = await client.put(
            f"{API_PREFIX}/spend-requests/sr-010",
            json={"description": "Added ROI justification"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Added ROI justification"

    @pytest.mark.anyio
    async def test_update_spend_request_approved_fails(self, client: AsyncClient):
        """PUT should fail for APPROVED requests."""
        # sr-001 is APPROVED
        resp = await client.put(
            f"{API_PREFIX}/spend-requests/sr-001",
            json={"title": "Should Fail"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_spend_request_not_found(self, client: AsyncClient):
        """PUT on nonexistent request should return 404."""
        resp = await client.put(
            f"{API_PREFIX}/spend-requests/nonexistent",
            json={"title": "Nope"},
        )
        assert resp.status_code == 404


# ============================================================================
# Approval Workflow Tests
# ============================================================================


class TestApprovalWorkflow:
    """Tests for approval and rejection workflows."""

    @pytest.mark.anyio
    async def test_approve_pending_request(self, client: AsyncClient):
        """POST /spend-requests/{id}/approve should approve."""
        # sr-002 is PENDING_APPROVAL ($25K - VP level)
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-002/approve",
            json={"approver": "VP People - Jane Doe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["approver"] == "VP People - Jane Doe"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_approve_updates_committed(self, service: BudgetManagementService):
        """Approving a request should increase allocation committed amount."""
        alloc_before = service.get_allocation("alloc-q3-02")
        committed_before = alloc_before.committed

        service.approve_request("sr-002", "VP People")

        alloc_after = service.get_allocation("alloc-q3-02")
        assert alloc_after.committed == committed_before + 25000.0

    @pytest.mark.anyio
    async def test_approve_non_pending_fails(self, client: AsyncClient):
        """POST /approve should fail for non-PENDING_APPROVAL request."""
        # sr-001 is already APPROVED
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-001/approve",
            json={"approver": "Someone"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        """POST /approve on nonexistent request should return 404."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/nonexistent/approve",
            json={"approver": "Someone"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_reject_pending_request(self, client: AsyncClient):
        """POST /spend-requests/{id}/reject should reject."""
        # sr-003 is PENDING_APPROVAL ($45K - VP level)
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-003/reject",
            json={
                "approver": "VP Data - Smith",
                "reason": "Budget constraints for data licensing",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "REJECTED"
        assert data["approver"] == "VP Data - Smith"
        assert data["rejection_reason"] == "Budget constraints for data licensing"

    @pytest.mark.anyio
    async def test_reject_non_pending_fails(self, client: AsyncClient):
        """POST /reject should fail for non-PENDING_APPROVAL request."""
        # sr-005 is DRAFT
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-005/reject",
            json={"approver": "Someone", "reason": "No"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_reject_not_found(self, client: AsyncClient):
        """POST /reject on nonexistent request should return 404."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/nonexistent/reject",
            json={"approver": "Someone", "reason": "No"},
        )
        assert resp.status_code == 404


# ============================================================================
# Approval Routing Tests
# ============================================================================


class TestApprovalRouting:
    """Tests for threshold-based approval routing."""

    @pytest.mark.anyio
    async def test_manager_approval_route(self, client: AsyncClient):
        """Amount < $10K should route to manager."""
        resp = await client.get(
            f"{API_PREFIX}/approval-route", params={"amount": 5000}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_route"] == "Manager approval required"

    @pytest.mark.anyio
    async def test_vp_approval_route(self, client: AsyncClient):
        """Amount >= $10K should route to VP."""
        resp = await client.get(
            f"{API_PREFIX}/approval-route", params={"amount": 10000}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_route"] == "VP approval required"

    @pytest.mark.anyio
    async def test_vp_approval_route_midrange(self, client: AsyncClient):
        """Amount between $10K and $50K should route to VP."""
        resp = await client.get(
            f"{API_PREFIX}/approval-route", params={"amount": 30000}
        )
        assert resp.status_code == 200
        assert resp.json()["approval_route"] == "VP approval required"

    @pytest.mark.anyio
    async def test_cfo_approval_route(self, client: AsyncClient):
        """Amount >= $50K should route to CFO."""
        resp = await client.get(
            f"{API_PREFIX}/approval-route", params={"amount": 50000}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_route"] == "CFO approval required"

    @pytest.mark.anyio
    async def test_cfo_approval_route_large(self, client: AsyncClient):
        """Amount > $50K should route to CFO."""
        resp = await client.get(
            f"{API_PREFIX}/approval-route", params={"amount": 100000}
        )
        assert resp.status_code == 200
        assert resp.json()["approval_route"] == "CFO approval required"

    @pytest.mark.anyio
    async def test_approval_route_zero(self, client: AsyncClient):
        """Amount = 0 should route to manager."""
        resp = await client.get(
            f"{API_PREFIX}/approval-route", params={"amount": 0}
        )
        assert resp.status_code == 200
        assert resp.json()["approval_route"] == "Manager approval required"

    def test_approval_route_service_direct(self, service: BudgetManagementService):
        """Direct service call for approval routing."""
        assert service.get_approval_route(9999) == "Manager approval required"
        assert service.get_approval_route(10000) == "VP approval required"
        assert service.get_approval_route(49999) == "VP approval required"
        assert service.get_approval_route(50000) == "CFO approval required"


# ============================================================================
# Variance Analysis Tests
# ============================================================================


class TestVarianceAnalysis:
    """Tests for budget variance calculations."""

    def test_positive_variance_over_budget(self, service: BudgetManagementService):
        """Over-budget allocation should have positive variance."""
        # alloc-q1-08: 100K allocated, 125K spent = +25%
        alloc = service.get_allocation("alloc-q1-08")
        assert alloc is not None
        assert alloc.variance_pct == 25.0

    def test_negative_variance_under_budget(self, service: BudgetManagementService):
        """Under-budget allocation should have negative variance."""
        # alloc-q3-01: 560K allocated, 180K spent
        alloc = service.get_allocation("alloc-q3-01")
        assert alloc is not None
        assert alloc.variance_pct < 0

    def test_zero_variance_no_spend(self, service: BudgetManagementService):
        """Q4 allocations with no spend should have 0% variance."""
        alloc = service.get_allocation("alloc-q4-01")
        assert alloc is not None
        assert alloc.variance_pct == 0.0

    def test_variance_updates_on_spend(self, service: BudgetManagementService):
        """Variance should update when spend is recorded."""
        from app.schemas.budget_management import RecordSpendInput

        alloc_before = service.get_allocation("alloc-q4-01")
        assert alloc_before.variance_pct == 0.0

        service.record_spend("alloc-q4-01", RecordSpendInput(amount=300000))
        alloc_after = service.get_allocation("alloc-q4-01")
        # 300K / 600K = 50%, variance = -50%
        assert alloc_after.variance_pct == -50.0


# ============================================================================
# Forecasting Tests
# ============================================================================


class TestForecasting:
    """Tests for spend forecasting."""

    @pytest.mark.anyio
    async def test_forecast_default(self, client: AsyncClient):
        """GET /forecast should return 6-month default forecast."""
        resp = await client.get(f"{API_PREFIX}/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert data["months_ahead"] == 6
        assert data["current_monthly_burn"] > 0
        assert data["projected_total"] > 0
        assert "will_exceed_budget" in data

    @pytest.mark.anyio
    async def test_forecast_custom_months(self, client: AsyncClient):
        """GET /forecast?months_ahead=12 should project 12 months."""
        resp = await client.get(
            f"{API_PREFIX}/forecast", params={"months_ahead": 12}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["months_ahead"] == 12

    @pytest.mark.anyio
    async def test_forecast_1_month(self, client: AsyncClient):
        """GET /forecast?months_ahead=1 should project 1 month."""
        resp = await client.get(
            f"{API_PREFIX}/forecast", params={"months_ahead": 1}
        )
        assert resp.status_code == 200
        assert resp.json()["months_ahead"] == 1

    def test_forecast_months_until_exhausted(self, service: BudgetManagementService):
        """Forecast should estimate months until budget exhaustion."""
        forecast = service.forecast_spend(months_ahead=12)
        if forecast.months_until_exhausted is not None:
            assert forecast.months_until_exhausted > 0

    def test_forecast_projected_remaining(self, service: BudgetManagementService):
        """Projected remaining should decrease with more months."""
        f6 = service.forecast_spend(months_ahead=6)
        f12 = service.forecast_spend(months_ahead=12)
        assert f12.projected_remaining < f6.projected_remaining

    def test_forecast_burn_rate_consistency(self, service: BudgetManagementService):
        """Monthly burn rate should match projected_total / months_ahead."""
        forecast = service.forecast_spend(months_ahead=6)
        expected_total = forecast.current_monthly_burn * 6
        assert abs(forecast.projected_total - expected_total) < 1.0


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for dashboard metrics."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        """GET /metrics should return aggregated metrics."""
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_annual_budget"] > 0
        assert data["total_spent_ytd"] > 0
        assert data["burn_rate_monthly"] > 0
        assert data["budget_utilization_pct"] > 0
        assert isinstance(data["by_category"], dict)
        assert isinstance(data["over_budget_categories"], list)

    def test_metrics_total_annual_budget(self, service: BudgetManagementService):
        """Total annual budget should sum all period budgets."""
        metrics = service.get_metrics()
        periods = service.list_periods()
        expected = sum(p.total_budget for p in periods)
        assert metrics.total_annual_budget == expected

    def test_metrics_pending_approvals(self, service: BudgetManagementService):
        """Pending approvals count should match PENDING_APPROVAL requests."""
        metrics = service.get_metrics()
        pending = service.list_spend_requests(status=ApprovalStatus.PENDING_APPROVAL)
        assert metrics.pending_approvals_count == len(pending)
        assert metrics.pending_approvals_amount == sum(r.amount for r in pending)

    def test_metrics_over_budget_categories(self, service: BudgetManagementService):
        """Over-budget categories should include PROFESSIONAL_SERVICES."""
        metrics = service.get_metrics()
        assert "PROFESSIONAL_SERVICES" in metrics.over_budget_categories

    def test_metrics_by_category_has_entries(self, service: BudgetManagementService):
        """By-category spend should have entries for categories with spend."""
        metrics = service.get_metrics()
        assert len(metrics.by_category) > 0
        assert "INFRASTRUCTURE" in metrics.by_category
        assert "PERSONNEL" in metrics.by_category

    def test_metrics_utilization_range(self, service: BudgetManagementService):
        """Budget utilization should be between 0 and 100."""
        metrics = service.get_metrics()
        assert 0 <= metrics.budget_utilization_pct <= 100


# ============================================================================
# Department Summary Tests
# ============================================================================


class TestDepartmentSummary:
    """Tests for department budget summaries."""

    @pytest.mark.anyio
    async def test_department_summary_all(self, client: AsyncClient):
        """GET /department-summary should return owner groupings."""
        resp = await client.get(f"{API_PREFIX}/department-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        owners = {d["owner"] for d in data}
        assert "VP Engineering" in owners
        assert "VP People" in owners
        assert "CFO" in owners

    @pytest.mark.anyio
    async def test_department_summary_filter_period(self, client: AsyncClient):
        """GET /department-summary?period_id=... should filter."""
        resp = await client.get(
            f"{API_PREFIX}/department-summary",
            params={"period_id": "period-2025-q3"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8  # 8 unique owners in Q3

    @pytest.mark.anyio
    async def test_department_summary_has_totals(self, client: AsyncClient):
        """Each department entry should have total fields."""
        resp = await client.get(
            f"{API_PREFIX}/department-summary",
            params={"period_id": "period-2025-q3"},
        )
        assert resp.status_code == 200
        for dept in resp.json():
            assert "total_allocated" in dept
            assert "total_spent" in dept
            assert "total_remaining" in dept
            assert "total_committed" in dept
            assert "categories" in dept

    @pytest.mark.anyio
    async def test_department_summary_totals_positive(self, client: AsyncClient):
        """Department totals should be >= 0."""
        resp = await client.get(
            f"{API_PREFIX}/department-summary",
            params={"period_id": "period-2025-q4"},
        )
        assert resp.status_code == 200
        for dept in resp.json():
            assert dept["total_allocated"] >= 0
            assert dept["total_spent"] >= 0


# ============================================================================
# Budget Alerts Tests
# ============================================================================


class TestBudgetAlerts:
    """Tests for budget alert endpoints."""

    @pytest.mark.anyio
    async def test_list_alerts(self, client: AsyncClient):
        """GET /alerts should return all 5 seed alerts."""
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged(self, client: AsyncClient):
        """GET /alerts?acknowledged=true should return acknowledged alerts."""
        resp = await client.get(
            f"{API_PREFIX}/alerts", params={"acknowledged": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged"] is True

    @pytest.mark.anyio
    async def test_list_alerts_filter_unacknowledged(self, client: AsyncClient):
        """GET /alerts?acknowledged=false should return unacknowledged alerts."""
        resp = await client.get(
            f"{API_PREFIX}/alerts", params={"acknowledged": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged"] is False

    @pytest.mark.anyio
    async def test_acknowledge_alert(self, client: AsyncClient):
        """POST /alerts/{id}/acknowledge should mark as acknowledged."""
        resp = await client.post(f"{API_PREFIX}/alerts/alert-004/acknowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["id"] == "alert-004"

    @pytest.mark.anyio
    async def test_acknowledge_alert_not_found(self, client: AsyncClient):
        """POST /alerts/{id}/acknowledge for missing alert should return 404."""
        resp = await client.post(f"{API_PREFIX}/alerts/nonexistent/acknowledge")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_acknowledge_already_acknowledged(self, client: AsyncClient):
        """Re-acknowledging should still return 200."""
        # alert-001 is already acknowledged
        resp = await client.post(f"{API_PREFIX}/alerts/alert-001/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["acknowledged"] is True


# ============================================================================
# Singleton Pattern Tests
# ============================================================================


class TestSingletonPattern:
    """Tests for singleton service pattern."""

    def test_get_service_returns_same_instance(self):
        """Calling get_budget_management_service twice should return same instance."""
        svc1 = get_budget_management_service()
        svc2 = get_budget_management_service()
        assert svc1 is svc2

    def test_reset_service_creates_new_instance(self):
        """Reset should clear the singleton."""
        svc1 = get_budget_management_service()
        reset_budget_management_service()
        svc2 = get_budget_management_service()
        assert svc1 is not svc2

    def test_service_clear_reloads_seed_data(self, service: BudgetManagementService):
        """Service.clear() should restore seed data."""
        # Delete a period
        service._periods.clear()
        assert len(service.list_periods()) == 0

        # Clear restores seed data
        service.clear()
        assert len(service.list_periods()) == 4


# ============================================================================
# Edge Cases & Error Handling Tests
# ============================================================================


class TestEdgeCases:
    """Edge cases and error handling tests."""

    @pytest.mark.anyio
    async def test_create_period_all_quarters_then_fail(self, client: AsyncClient):
        """Creating all Q1-Q4 for a year then trying again should fail."""
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            resp = await client.post(
                f"{API_PREFIX}/periods",
                params={"fiscal_year": 2030, "quarter": q, "total_budget": 1000000},
            )
            assert resp.status_code == 201

        # Duplicate Q1 should fail
        resp = await client.post(
            f"{API_PREFIX}/periods",
            params={"fiscal_year": 2030, "quarter": "Q1", "total_budget": 1000000},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_and_approve_flow(self, client: AsyncClient):
        """Full flow: submit -> approve -> verify status."""
        # Submit
        submit_resp = await client.post(
            f"{API_PREFIX}/spend-requests",
            json={
                "allocation_id": "alloc-q3-05",
                "title": "Marketing Campaign",
                "amount": 7500,
                "requested_by": "Marketing Lead",
            },
        )
        assert submit_resp.status_code == 201
        sr_id = submit_resp.json()["id"]
        assert submit_resp.json()["status"] == "PENDING_APPROVAL"

        # Approve
        approve_resp = await client.post(
            f"{API_PREFIX}/spend-requests/{sr_id}/approve",
            json={"approver": "VP Marketing"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "APPROVED"

        # Verify persisted
        get_resp = await client.get(f"{API_PREFIX}/spend-requests/{sr_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "APPROVED"

    @pytest.mark.anyio
    async def test_submit_and_reject_flow(self, client: AsyncClient):
        """Full flow: submit -> reject -> verify status and reason."""
        submit_resp = await client.post(
            f"{API_PREFIX}/spend-requests",
            json={
                "allocation_id": "alloc-q3-07",
                "title": "Equipment Purchase",
                "amount": 12000,
                "requested_by": "Ops Manager",
            },
        )
        assert submit_resp.status_code == 201
        sr_id = submit_resp.json()["id"]

        reject_resp = await client.post(
            f"{API_PREFIX}/spend-requests/{sr_id}/reject",
            json={"approver": "COO", "reason": "Defer to next quarter"},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "REJECTED"
        assert reject_resp.json()["rejection_reason"] == "Defer to next quarter"

    @pytest.mark.anyio
    async def test_update_only_provided_fields(self, client: AsyncClient):
        """PUT should only update provided fields, not overwrite others."""
        # sr-009 is DRAFT
        original = await client.get(f"{API_PREFIX}/spend-requests/sr-009")
        orig_data = original.json()

        resp = await client.put(
            f"{API_PREFIX}/spend-requests/sr-009",
            json={"vendor": "New Vendor Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vendor"] == "New Vendor Name"
        assert data["title"] == orig_data["title"]  # unchanged
        assert data["amount"] == orig_data["amount"]  # unchanged

    @pytest.mark.anyio
    async def test_approve_draft_fails(self, client: AsyncClient):
        """Cannot approve a DRAFT request directly."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-005/approve",
            json={"approver": "VP"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_reject_draft_fails(self, client: AsyncClient):
        """Cannot reject a DRAFT request directly."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-005/reject",
            json={"approver": "VP", "reason": "No"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_rejected_fails(self, client: AsyncClient):
        """Cannot approve a REJECTED request."""
        resp = await client.post(
            f"{API_PREFIX}/spend-requests/sr-006/approve",
            json={"approver": "CFO"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_pending_fails(self, client: AsyncClient):
        """Cannot update a PENDING_APPROVAL request."""
        resp = await client.put(
            f"{API_PREFIX}/spend-requests/sr-002",
            json={"title": "Should Fail"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_rejected_fails(self, client: AsyncClient):
        """Cannot update a REJECTED request."""
        resp = await client.put(
            f"{API_PREFIX}/spend-requests/sr-006",
            json={"title": "Should Fail"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_multiple_spends_accumulate(self, service: BudgetManagementService):
        """Multiple record_spend calls should accumulate."""
        from app.schemas.budget_management import RecordSpendInput

        service.record_spend("alloc-q4-04", RecordSpendInput(amount=50000))
        service.record_spend("alloc-q4-04", RecordSpendInput(amount=30000))
        alloc = service.get_allocation("alloc-q4-04")
        assert alloc.spent_amount == 80000

    @pytest.mark.anyio
    async def test_period_totals_update_on_spend(self, service: BudgetManagementService):
        """Recording spend should update the parent period totals."""
        from app.schemas.budget_management import RecordSpendInput

        period_before = service.get_period("period-2025-q4")
        assert period_before.total_spent == 0.0

        service.record_spend("alloc-q4-01", RecordSpendInput(amount=100000))
        period_after = service.get_period("period-2025-q4")
        assert period_after.total_spent == 100000.0

    @pytest.mark.anyio
    async def test_period_totals_update_on_allocation_create(
        self, service: BudgetManagementService
    ):
        """Creating an allocation should update period total_allocated."""
        period_before = service.get_period("period-2025-q4")
        alloc_before = period_before.total_allocated

        service.create_allocation(
            period_id="period-2025-q4",
            category=BudgetCategory.MARKETING,
            allocated_amount=50000,
            owner="New Owner",
        )
        period_after = service.get_period("period-2025-q4")
        assert period_after.total_allocated == alloc_before + 50000

    def test_list_spend_requests_sorted_by_date(self, service: BudgetManagementService):
        """Spend requests should be sorted by date descending."""
        requests = service.list_spend_requests()
        dates = [r.requested_date for r in requests]
        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1]

    def test_allocations_sorted(self, service: BudgetManagementService):
        """Allocations should be sorted by period_id and category."""
        allocs = service.list_allocations()
        for i in range(len(allocs) - 1):
            assert (allocs[i].period_id, allocs[i].category.value) <= (
                allocs[i + 1].period_id,
                allocs[i + 1].category.value,
            )
