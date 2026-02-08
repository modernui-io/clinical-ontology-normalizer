"""Error budget tracking service for SLA monitoring.

VPE-4: Tracks error budget consumption and burn rate for each service
defined in the Service Level Agreements.

Key concepts:
- **Error Budget:** The maximum allowable errors within an SLA period.
  For a 99.9% SLA, the error budget is 0.1% of total requests.
- **Burn Rate:** The rate at which the error budget is being consumed
  relative to the SLA period. A burn rate of 1.0 means the budget will
  be exactly exhausted at the end of the period.
- **Alert Levels:** Budget consumption thresholds that trigger alerts:
  - >50% consumed: Warning
  - >80% consumed: Critical
  - 100% consumed: Budget exhausted

Usage:
    from app.services.error_budget_service import get_error_budget_service

    service = get_error_budget_service()
    service.record_request("api_gateway", success=True)
    service.record_request("api_gateway", success=False)

    status = service.get_budget_status("api_gateway")
    # {"budget_remaining_pct": 99.5, "burn_rate": 0.5, "alert_level": "ok", ...}
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Constants & Configuration
# =============================================================================


class AlertLevel(str, Enum):
    """Error budget alert level."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


# SLA targets as availability fractions (e.g. 0.999 = 99.9%)
DEFAULT_SLA_TARGETS: dict[str, float] = {
    "api_gateway": 0.999,       # 99.9%
    "trial_screening": 0.995,   # 99.5%
    "fhir_import": 0.995,       # 99.5%
    "nlp_pipeline": 0.990,      # 99.0%
    "database": 0.9999,         # 99.99%
}

# Default reset interval in seconds (30 days)
DEFAULT_RESET_INTERVAL_SECONDS = 30 * 24 * 60 * 60

# Alert thresholds (fraction of budget consumed)
WARNING_THRESHOLD = 0.50
CRITICAL_THRESHOLD = 0.80
EXHAUSTED_THRESHOLD = 1.00


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ServiceBudget:
    """Tracks error budget for a single service.

    Attributes:
        service_name: Name of the service.
        sla_target: Target availability (e.g. 0.999 for 99.9%).
        total_requests: Total requests processed since last reset.
        total_errors: Total error responses since last reset.
        last_reset: Timestamp of the last budget reset.
        alert_callbacks: Optional list of alert callback functions.
    """

    service_name: str
    sla_target: float
    total_requests: int = 0
    total_errors: int = 0
    last_reset: float = field(default_factory=time.time)
    _previous_alert_level: AlertLevel = field(default=AlertLevel.OK, repr=False)

    @property
    def allowed_error_rate(self) -> float:
        """The maximum allowed error rate based on SLA target.

        Returns:
            Error rate as a fraction (e.g. 0.001 for 99.9% SLA).
        """
        return 1.0 - self.sla_target

    @property
    def current_error_rate(self) -> float:
        """The current error rate.

        Returns:
            Error rate as a fraction.
        """
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    @property
    def budget_consumed_pct(self) -> float:
        """Percentage of error budget consumed.

        Returns:
            A value from 0 to 100+. Values > 100 mean the budget is exhausted.
        """
        if self.allowed_error_rate == 0:
            return 100.0 if self.total_errors > 0 else 0.0
        if self.total_requests == 0:
            return 0.0
        consumption = self.current_error_rate / self.allowed_error_rate
        return round(consumption * 100, 4)

    @property
    def budget_remaining_pct(self) -> float:
        """Percentage of error budget remaining.

        Returns:
            A value from 0 to 100. Clamped to 0 minimum.
        """
        return max(0.0, round(100.0 - self.budget_consumed_pct, 4))

    @property
    def burn_rate(self) -> float:
        """Current burn rate relative to the allowed error rate.

        A burn rate of 1.0 means errors are occurring at the exact rate
        that would exhaust the budget at the end of the SLA period.
        Values > 1.0 indicate faster-than-sustainable consumption.

        Returns:
            Burn rate as a multiplier.
        """
        if self.allowed_error_rate == 0 or self.total_requests == 0:
            return 0.0
        return round(self.current_error_rate / self.allowed_error_rate, 4)

    @property
    def alert_level(self) -> AlertLevel:
        """Current alert level based on budget consumption.

        Returns:
            AlertLevel enum value.
        """
        consumed = self.budget_consumed_pct / 100.0
        if consumed >= EXHAUSTED_THRESHOLD:
            return AlertLevel.EXHAUSTED
        if consumed >= CRITICAL_THRESHOLD:
            return AlertLevel.CRITICAL
        if consumed >= WARNING_THRESHOLD:
            return AlertLevel.WARNING
        return AlertLevel.OK

    def record(self, success: bool) -> AlertLevel | None:
        """Record a single request outcome.

        Args:
            success: True if the request succeeded, False if it was an error.

        Returns:
            The new AlertLevel if it changed (indicating an alert should fire),
            or None if the level did not change.
        """
        self.total_requests += 1
        if not success:
            self.total_errors += 1

        new_level = self.alert_level
        if new_level != self._previous_alert_level:
            old_level = self._previous_alert_level
            self._previous_alert_level = new_level
            logger.info(
                "Error budget alert level changed for %s: %s -> %s "
                "(consumed=%.2f%%, requests=%d, errors=%d)",
                self.service_name,
                old_level.value,
                new_level.value,
                self.budget_consumed_pct,
                self.total_requests,
                self.total_errors,
            )
            return new_level
        return None

    def reset(self) -> None:
        """Reset the budget counters for a new period."""
        self.total_requests = 0
        self.total_errors = 0
        self.last_reset = time.time()
        self._previous_alert_level = AlertLevel.OK
        logger.info("Error budget reset for %s", self.service_name)

    def to_dict(self) -> dict[str, Any]:
        """Serialize budget status to a dictionary.

        Returns:
            Dictionary with all budget status values.
        """
        return {
            "service_name": self.service_name,
            "sla_target": self.sla_target,
            "sla_target_pct": f"{self.sla_target * 100:.2f}%",
            "allowed_error_rate": round(self.allowed_error_rate, 6),
            "current_error_rate": round(self.current_error_rate, 6),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "budget_consumed_pct": self.budget_consumed_pct,
            "budget_remaining_pct": self.budget_remaining_pct,
            "burn_rate": self.burn_rate,
            "alert_level": self.alert_level.value,
            "last_reset": self.last_reset,
        }


# =============================================================================
# Error Budget Service
# =============================================================================


class ErrorBudgetService:
    """Service for tracking error budgets across all SLA-governed services.

    Thread-safe singleton that manages ServiceBudget instances for each
    configured service. Supports automatic reset on a configurable interval.

    Usage:
        service = ErrorBudgetService()
        service.record_request("api_gateway", success=True)
        status = service.get_budget_status("api_gateway")
    """

    def __init__(
        self,
        sla_targets: dict[str, float] | None = None,
        reset_interval_seconds: int = DEFAULT_RESET_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the error budget service.

        Args:
            sla_targets: Mapping of service names to SLA targets.
                Defaults to DEFAULT_SLA_TARGETS.
            reset_interval_seconds: How often to reset budgets (seconds).
                Defaults to 30 days.
        """
        self._lock = threading.Lock()
        self._reset_interval = reset_interval_seconds
        self._budgets: dict[str, ServiceBudget] = {}

        targets = sla_targets or DEFAULT_SLA_TARGETS
        for service_name, target in targets.items():
            self._budgets[service_name] = ServiceBudget(
                service_name=service_name,
                sla_target=target,
            )

    def record_request(self, service_name: str, success: bool) -> AlertLevel | None:
        """Record a request outcome for a service.

        If the service is not configured, it is silently ignored.

        Args:
            service_name: Name of the service (must match a key in sla_targets).
            success: True if the request succeeded.

        Returns:
            New AlertLevel if it changed, None otherwise.
        """
        with self._lock:
            budget = self._budgets.get(service_name)
            if budget is None:
                return None

            # Check if reset is due
            if time.time() - budget.last_reset > self._reset_interval:
                budget.reset()

            return budget.record(success)

    def get_budget_status(self, service_name: str) -> dict[str, Any] | None:
        """Get the current budget status for a service.

        Args:
            service_name: Name of the service.

        Returns:
            Dictionary with budget status, or None if service not found.
        """
        with self._lock:
            budget = self._budgets.get(service_name)
            if budget is None:
                return None
            return budget.to_dict()

    def get_all_budgets_status(self) -> dict[str, dict[str, Any]]:
        """Get budget status for all configured services.

        Returns:
            Dictionary mapping service names to their budget status.
        """
        with self._lock:
            return {
                name: budget.to_dict()
                for name, budget in self._budgets.items()
            }

    def get_services_at_risk(self) -> list[dict[str, Any]]:
        """Get services whose error budget is at warning or above.

        Returns:
            List of budget status dictionaries for at-risk services.
        """
        with self._lock:
            return [
                budget.to_dict()
                for budget in self._budgets.values()
                if budget.alert_level != AlertLevel.OK
            ]

    def reset_budget(self, service_name: str) -> bool:
        """Manually reset a service's error budget.

        Args:
            service_name: Name of the service.

        Returns:
            True if the service was found and reset, False otherwise.
        """
        with self._lock:
            budget = self._budgets.get(service_name)
            if budget is None:
                return False
            budget.reset()
            return True

    def reset_all_budgets(self) -> None:
        """Reset all error budgets."""
        with self._lock:
            for budget in self._budgets.values():
                budget.reset()


# =============================================================================
# Singleton
# =============================================================================

_error_budget_service: ErrorBudgetService | None = None
_budget_lock = threading.Lock()


def get_error_budget_service(
    sla_targets: dict[str, float] | None = None,
    reset_interval_seconds: int = DEFAULT_RESET_INTERVAL_SECONDS,
) -> ErrorBudgetService:
    """Get or create the singleton ErrorBudgetService.

    Args:
        sla_targets: SLA targets (only used on first call).
        reset_interval_seconds: Reset interval (only used on first call).

    Returns:
        The singleton ErrorBudgetService.
    """
    global _error_budget_service
    if _error_budget_service is None:
        with _budget_lock:
            if _error_budget_service is None:
                _error_budget_service = ErrorBudgetService(
                    sla_targets=sla_targets,
                    reset_interval_seconds=reset_interval_seconds,
                )
    return _error_budget_service


def reset_error_budget_service() -> None:
    """Reset the singleton (for testing)."""
    global _error_budget_service
    with _budget_lock:
        _error_budget_service = None
