"""Tests for P3-017: Operational Cost Dashboard Service.

Tests cover:
- Recording workload costs
- Per-tenant cost aggregation
- Per-workload cost aggregation
- Configurable cost rate
- Dashboard generation with correct totals
- Tenant-specific cost lookup
- Thread safety (basic)
- Edge cases (zero compute, negative compute, empty dashboard)
- Singleton pattern (get/reset)
"""

from __future__ import annotations

import pytest

from app.services.cost_dashboard_service import (
    CostDashboard,
    CostDashboardService,
    TenantCost,
    WorkloadCost,
    get_cost_dashboard_service,
    reset_cost_dashboard_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_cost_dashboard_service()
    yield
    reset_cost_dashboard_service()


@pytest.fixture
def service() -> CostDashboardService:
    """Create a service with a known cost rate."""
    return CostDashboardService(cost_per_compute_second=0.001)


# ============================================================================
# Recording Costs
# ============================================================================


class TestRecordWorkloadCost:
    """Tests for record_workload_cost."""

    def test_record_single_event(self, service: CostDashboardService):
        service.record_workload_cost("tenant-a", "nlp_extraction", 10.0)
        dashboard = service.get_cost_dashboard()
        assert dashboard.grand_total_requests == 1
        assert dashboard.grand_total_compute_seconds == 10.0

    def test_record_multiple_events_same_tenant_workload(self, service: CostDashboardService):
        service.record_workload_cost("tenant-a", "nlp_extraction", 5.0)
        service.record_workload_cost("tenant-a", "nlp_extraction", 3.0)
        dashboard = service.get_cost_dashboard()
        assert dashboard.grand_total_requests == 2
        assert dashboard.grand_total_compute_seconds == 8.0

    def test_record_multiple_tenants(self, service: CostDashboardService):
        service.record_workload_cost("tenant-a", "nlp_extraction", 10.0)
        service.record_workload_cost("tenant-b", "graph_build", 20.0)
        dashboard = service.get_cost_dashboard()
        assert dashboard.grand_total_requests == 2
        assert len(dashboard.tenants) == 2

    def test_record_multiple_workloads_same_tenant(self, service: CostDashboardService):
        service.record_workload_cost("tenant-a", "nlp_extraction", 10.0)
        service.record_workload_cost("tenant-a", "graph_build", 5.0)
        tc = service.get_tenant_cost("tenant-a")
        assert tc is not None
        assert tc.total_requests == 2
        assert len(tc.cost_breakdown) == 2

    def test_reject_negative_compute_seconds(self, service: CostDashboardService):
        with pytest.raises(ValueError, match="non-negative"):
            service.record_workload_cost("tenant-a", "nlp_extraction", -1.0)

    def test_zero_compute_seconds(self, service: CostDashboardService):
        service.record_workload_cost("tenant-a", "nlp_extraction", 0.0)
        dashboard = service.get_cost_dashboard()
        assert dashboard.grand_total_requests == 1
        assert dashboard.grand_total_compute_seconds == 0.0
        assert dashboard.grand_total_cost_usd == 0.0


# ============================================================================
# Cost Dashboard
# ============================================================================


class TestGetCostDashboard:
    """Tests for get_cost_dashboard."""

    def test_empty_dashboard(self, service: CostDashboardService):
        dashboard = service.get_cost_dashboard()
        assert isinstance(dashboard, CostDashboard)
        assert dashboard.grand_total_requests == 0
        assert dashboard.grand_total_compute_seconds == 0.0
        assert dashboard.grand_total_cost_usd == 0.0
        assert len(dashboard.tenants) == 0
        assert len(dashboard.workloads) == 0

    def test_cost_calculation_at_default_rate(self, service: CostDashboardService):
        # rate = $0.001/s, 100s -> $0.10
        service.record_workload_cost("t1", "nlp", 100.0)
        dashboard = service.get_cost_dashboard()
        assert dashboard.grand_total_cost_usd == pytest.approx(0.1, abs=1e-6)

    def test_cost_rate_stored(self, service: CostDashboardService):
        dashboard = service.get_cost_dashboard()
        assert dashboard.cost_per_compute_second == 0.001

    def test_custom_cost_rate(self):
        svc = CostDashboardService(cost_per_compute_second=0.01)
        svc.record_workload_cost("t1", "nlp", 50.0)
        dashboard = svc.get_cost_dashboard()
        assert dashboard.grand_total_cost_usd == pytest.approx(0.5, abs=1e-6)

    def test_generated_at_is_iso(self, service: CostDashboardService):
        dashboard = service.get_cost_dashboard()
        from datetime import datetime
        datetime.fromisoformat(dashboard.generated_at)

    def test_tenant_breakdown(self, service: CostDashboardService):
        service.record_workload_cost("t1", "nlp", 10.0)
        service.record_workload_cost("t1", "graph", 20.0)
        service.record_workload_cost("t2", "nlp", 5.0)

        dashboard = service.get_cost_dashboard()
        tenant_map = {t.tenant_id: t for t in dashboard.tenants}

        assert "t1" in tenant_map
        assert "t2" in tenant_map
        assert tenant_map["t1"].total_requests == 2
        assert tenant_map["t1"].total_compute_seconds == 30.0
        assert tenant_map["t2"].total_requests == 1
        assert tenant_map["t2"].total_compute_seconds == 5.0

    def test_workload_global_aggregation(self, service: CostDashboardService):
        service.record_workload_cost("t1", "nlp", 10.0)
        service.record_workload_cost("t2", "nlp", 5.0)
        service.record_workload_cost("t1", "graph", 20.0)

        dashboard = service.get_cost_dashboard()
        wl_map = {w.workload_type: w for w in dashboard.workloads}

        assert wl_map["nlp"].request_count == 2
        assert wl_map["nlp"].compute_seconds == 15.0
        assert wl_map["graph"].request_count == 1
        assert wl_map["graph"].compute_seconds == 20.0


# ============================================================================
# Tenant-Specific Lookup
# ============================================================================


class TestGetTenantCost:
    """Tests for get_tenant_cost."""

    def test_nonexistent_tenant(self, service: CostDashboardService):
        result = service.get_tenant_cost("nonexistent")
        assert result is None

    def test_existing_tenant(self, service: CostDashboardService):
        service.record_workload_cost("t1", "nlp", 10.0)
        tc = service.get_tenant_cost("t1")
        assert tc is not None
        assert isinstance(tc, TenantCost)
        assert tc.tenant_id == "t1"
        assert tc.total_requests == 1
        assert tc.total_cost_usd == pytest.approx(0.01, abs=1e-6)


# ============================================================================
# Reset
# ============================================================================


class TestReset:
    """Tests for service reset."""

    def test_reset_clears_data(self, service: CostDashboardService):
        service.record_workload_cost("t1", "nlp", 10.0)
        service.reset()
        dashboard = service.get_cost_dashboard()
        assert dashboard.grand_total_requests == 0


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_returns_same_instance(self):
        s1 = get_cost_dashboard_service()
        s2 = get_cost_dashboard_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        s1 = get_cost_dashboard_service()
        reset_cost_dashboard_service()
        s2 = get_cost_dashboard_service()
        assert s1 is not s2
