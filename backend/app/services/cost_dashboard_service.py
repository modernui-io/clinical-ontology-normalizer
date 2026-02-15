"""Operational Cost Dashboard Service (P3-017).

Tracks compute costs by workload type and tenant, providing a real-time
cost dashboard for operational visibility.

Features:
- Record workload costs per tenant
- Configurable rate per compute-second (COST_PER_COMPUTE_SECOND env var)
- Per-tenant and per-workload cost summaries
- Thread-safe accumulation
"""

from __future__ import annotations

import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

def _get_cost_rate() -> float:
    """Read cost per compute-second from environment, default $0.001/s."""
    raw = os.environ.get("COST_PER_COMPUTE_SECOND", "0.001")
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            f"Invalid COST_PER_COMPUTE_SECOND='{raw}', using default 0.001"
        )
        return 0.001


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class WorkloadCost:
    """Cost summary for a single workload type."""

    workload_type: str
    request_count: int
    compute_seconds: float
    estimated_cost_usd: float


@dataclass
class TenantCost:
    """Cost summary for a single tenant."""

    tenant_id: str
    total_requests: int
    total_compute_seconds: float
    total_cost_usd: float
    cost_breakdown: list[WorkloadCost] = field(default_factory=list)


@dataclass
class CostDashboard:
    """Full cost dashboard aggregation."""

    generated_at: str
    cost_per_compute_second: float
    tenants: list[TenantCost]
    workloads: list[WorkloadCost]
    grand_total_requests: int
    grand_total_compute_seconds: float
    grand_total_cost_usd: float


# ============================================================================
# Internal Accumulator Entry
# ============================================================================


@dataclass
class _AccumulatorEntry:
    """Internal per-(tenant, workload) accumulator."""

    request_count: int = 0
    compute_seconds: float = 0.0


# ============================================================================
# Service
# ============================================================================


class CostDashboardService:
    """Operational cost dashboard service.

    Accumulates workload costs per tenant and provides aggregated views
    for the cost dashboard.
    """

    def __init__(self, cost_per_compute_second: float | None = None):
        self._rate = cost_per_compute_second if cost_per_compute_second is not None else _get_cost_rate()
        # _data[tenant_id][workload_type] -> _AccumulatorEntry
        self._data: dict[str, dict[str, _AccumulatorEntry]] = defaultdict(
            lambda: defaultdict(_AccumulatorEntry)
        )
        self._lock = threading.Lock()
        logger.info(
            f"CostDashboardService initialized (rate=${self._rate}/compute-second)"
        )

    # ========================================================================
    # Public API
    # ========================================================================

    def record_workload_cost(
        self,
        tenant_id: str,
        workload_type: str,
        compute_seconds: float,
    ) -> None:
        """Record a workload cost event.

        Args:
            tenant_id: Identifier for the tenant.
            workload_type: Type of workload (e.g. "nlp_extraction", "graph_build").
            compute_seconds: Number of compute-seconds consumed.
        """
        if compute_seconds < 0:
            raise ValueError("compute_seconds must be non-negative")

        with self._lock:
            entry = self._data[tenant_id][workload_type]
            entry.request_count += 1
            entry.compute_seconds += compute_seconds

        logger.debug(
            f"Recorded cost: tenant={tenant_id} workload={workload_type} "
            f"compute_s={compute_seconds:.3f}"
        )

    def get_cost_dashboard(self) -> CostDashboard:
        """Build and return the full cost dashboard.

        Returns:
            CostDashboard with per-tenant and per-workload breakdowns.
        """
        with self._lock:
            snapshot = {
                tid: {wt: _AccumulatorEntry(e.request_count, e.compute_seconds)
                      for wt, e in workloads.items()}
                for tid, workloads in self._data.items()
            }

        # Per-tenant aggregation
        tenants: list[TenantCost] = []
        # Per-workload global aggregation
        global_workloads: dict[str, _AccumulatorEntry] = defaultdict(_AccumulatorEntry)

        grand_requests = 0
        grand_compute = 0.0

        for tenant_id, workloads in snapshot.items():
            tenant_requests = 0
            tenant_compute = 0.0
            breakdown: list[WorkloadCost] = []

            for workload_type, entry in workloads.items():
                cost = entry.compute_seconds * self._rate
                breakdown.append(WorkloadCost(
                    workload_type=workload_type,
                    request_count=entry.request_count,
                    compute_seconds=round(entry.compute_seconds, 4),
                    estimated_cost_usd=round(cost, 6),
                ))
                tenant_requests += entry.request_count
                tenant_compute += entry.compute_seconds

                gw = global_workloads[workload_type]
                gw.request_count += entry.request_count
                gw.compute_seconds += entry.compute_seconds

            tenant_cost = tenant_compute * self._rate
            tenants.append(TenantCost(
                tenant_id=tenant_id,
                total_requests=tenant_requests,
                total_compute_seconds=round(tenant_compute, 4),
                total_cost_usd=round(tenant_cost, 6),
                cost_breakdown=breakdown,
            ))

            grand_requests += tenant_requests
            grand_compute += tenant_compute

        # Build global workload summary
        workload_summaries: list[WorkloadCost] = []
        for wt, entry in global_workloads.items():
            cost = entry.compute_seconds * self._rate
            workload_summaries.append(WorkloadCost(
                workload_type=wt,
                request_count=entry.request_count,
                compute_seconds=round(entry.compute_seconds, 4),
                estimated_cost_usd=round(cost, 6),
            ))

        grand_cost = grand_compute * self._rate

        return CostDashboard(
            generated_at=datetime.now(timezone.utc).isoformat(),
            cost_per_compute_second=self._rate,
            tenants=tenants,
            workloads=workload_summaries,
            grand_total_requests=grand_requests,
            grand_total_compute_seconds=round(grand_compute, 4),
            grand_total_cost_usd=round(grand_cost, 6),
        )

    def get_tenant_cost(self, tenant_id: str) -> TenantCost | None:
        """Get cost summary for a specific tenant.

        Args:
            tenant_id: Tenant to look up.

        Returns:
            TenantCost or None if tenant has no recorded costs.
        """
        with self._lock:
            if tenant_id not in self._data:
                return None
            workloads = {
                wt: _AccumulatorEntry(e.request_count, e.compute_seconds)
                for wt, e in self._data[tenant_id].items()
            }

        total_requests = 0
        total_compute = 0.0
        breakdown: list[WorkloadCost] = []

        for wt, entry in workloads.items():
            cost = entry.compute_seconds * self._rate
            breakdown.append(WorkloadCost(
                workload_type=wt,
                request_count=entry.request_count,
                compute_seconds=round(entry.compute_seconds, 4),
                estimated_cost_usd=round(cost, 6),
            ))
            total_requests += entry.request_count
            total_compute += entry.compute_seconds

        return TenantCost(
            tenant_id=tenant_id,
            total_requests=total_requests,
            total_compute_seconds=round(total_compute, 4),
            total_cost_usd=round(total_compute * self._rate, 6),
            cost_breakdown=breakdown,
        )

    def reset(self) -> None:
        """Clear all accumulated cost data."""
        with self._lock:
            self._data.clear()
        logger.info("Cost dashboard data cleared")


# ============================================================================
# Singleton
# ============================================================================

_instance: CostDashboardService | None = None
_instance_lock = threading.Lock()


def get_cost_dashboard_service() -> CostDashboardService:
    """Get or create the singleton CostDashboardService."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CostDashboardService()
    return _instance


def reset_cost_dashboard_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    with _instance_lock:
        _instance = None
