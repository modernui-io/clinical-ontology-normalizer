"""Pre-defined load test scenarios for the clinical trial recruitment platform.

Each scenario defines a :class:`LoadTestConfig` with endpoint targets and
user / duration parameters tuned for a specific purpose (smoke, baseline,
stress, spike).
"""

from __future__ import annotations

from tests.load.load_test_runner import EndpointConfig, LoadTestConfig


# ---------------------------------------------------------------------------
# Default endpoint catalogue
# ---------------------------------------------------------------------------

DEFAULT_ENDPOINTS: list[EndpointConfig] = [
    EndpointConfig(
        method="GET",
        path="/api/v1/health",
        sla_ms=50.0,
        name="Health Check",
    ),
    EndpointConfig(
        method="GET",
        path="/api/v1/patients",
        sla_ms=500.0,
        name="List Patients",
    ),
    EndpointConfig(
        method="GET",
        path="/api/v1/trials",
        sla_ms=500.0,
        name="List Trials",
    ),
    EndpointConfig(
        method="POST",
        path="/api/v1/trials/1/screen",
        body={"patient_ids": []},
        sla_ms=3000.0,
        name="Screen Patients",
    ),
    EndpointConfig(
        method="GET",
        path="/api/v1/data-quality/mapping",
        sla_ms=2000.0,
        name="Data Quality Mapping",
    ),
]


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def smoke_test(
    base_url: str = "http://localhost:8000",
    auth_token: str | None = None,
) -> LoadTestConfig:
    """Quick sanity check: 5 users, 30 seconds.

    Verifies endpoints respond under minimal load.
    """
    return LoadTestConfig(
        base_url=base_url,
        endpoints=DEFAULT_ENDPOINTS,
        concurrent_users=5,
        duration_seconds=30,
        ramp_up_seconds=2,
        think_time_seconds=0.5,
        auth_token=auth_token,
    )


def baseline_test(
    base_url: str = "http://localhost:8000",
    auth_token: str | None = None,
) -> LoadTestConfig:
    """Establish performance baseline: 20 users, 60 seconds."""
    return LoadTestConfig(
        base_url=base_url,
        endpoints=DEFAULT_ENDPOINTS,
        concurrent_users=20,
        duration_seconds=60,
        ramp_up_seconds=10,
        think_time_seconds=0.2,
        auth_token=auth_token,
    )


def stress_test(
    base_url: str = "http://localhost:8000",
    auth_token: str | None = None,
) -> LoadTestConfig:
    """Push to breaking point: 100 users, 120 seconds."""
    return LoadTestConfig(
        base_url=base_url,
        endpoints=DEFAULT_ENDPOINTS,
        concurrent_users=100,
        duration_seconds=120,
        ramp_up_seconds=20,
        think_time_seconds=0.1,
        auth_token=auth_token,
    )


def spike_test(
    base_url: str = "http://localhost:8000",
    auth_token: str | None = None,
) -> LoadTestConfig:
    """Spike test: sudden burst of traffic.

    Uses a 60 second duration with aggressive ramp.  The pattern is
    10 -> 100 -> 10 simulated by running 100 users with a very short
    duration so most activity clusters in the middle of the window.
    """
    return LoadTestConfig(
        base_url=base_url,
        endpoints=DEFAULT_ENDPOINTS,
        concurrent_users=100,
        duration_seconds=60,
        ramp_up_seconds=5,
        think_time_seconds=0.05,
        auth_token=auth_token,
    )


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, type[None] | object] = {
    "smoke": smoke_test,
    "baseline": baseline_test,
    "stress": stress_test,
    "spike": spike_test,
}


def get_scenario(
    name: str,
    base_url: str = "http://localhost:8000",
    auth_token: str | None = None,
) -> LoadTestConfig:
    """Look up a named scenario and return its :class:`LoadTestConfig`.

    Raises :class:`ValueError` if the name is unknown.
    """
    builder = SCENARIOS.get(name)
    if builder is None:
        available = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unknown scenario '{name}'. Available: {available}")
    return builder(base_url=base_url, auth_token=auth_token)  # type: ignore[operator]


def list_scenarios() -> list[str]:
    """Return sorted list of available scenario names."""
    return sorted(SCENARIOS.keys())
