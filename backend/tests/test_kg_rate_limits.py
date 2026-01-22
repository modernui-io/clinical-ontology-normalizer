"""Tests for Knowledge Graph rate limiting configuration."""

from __future__ import annotations

import pytest

from app.api.middleware.rate_limit import DEFAULT_RATE_LIMITS, RateLimitConfig


class TestKGRateLimits:
    """Test KG-specific rate limit configuration."""

    def test_kg_health_endpoints_configured(self) -> None:
        """Test that KG health endpoints have rate limits."""
        health_endpoints = [
            "/api/v1/kg/health",
            "/api/v1/kg/health/liveness",
            "/api/v1/kg/health/readiness",
            "/api/v1/kg/health/metrics",
        ]
        for endpoint in health_endpoints:
            assert endpoint in DEFAULT_RATE_LIMITS
            assert DEFAULT_RATE_LIMITS[endpoint].requests_per_window > 0

    def test_kg_orchestration_endpoints_configured(self) -> None:
        """Test that KG orchestration endpoints have rate limits."""
        orchestration_endpoints = [
            "/api/v1/kg/orchestration/status",
            "/api/v1/kg/orchestration/query",
            "/api/v1/kg/orchestration/clinical-question",
            "/api/v1/kg/orchestration/reasoning-path",
            "/api/v1/kg/orchestration/patient",
            "/api/v1/kg/orchestration/mdt-session",
            "/api/v1/kg/orchestration/export",
        ]
        for endpoint in orchestration_endpoints:
            assert endpoint in DEFAULT_RATE_LIMITS
            assert DEFAULT_RATE_LIMITS[endpoint].requests_per_window > 0

    def test_kg_benchmark_endpoints_configured(self) -> None:
        """Test that KG benchmark endpoints have rate limits."""
        benchmark_endpoints = [
            "/api/v1/kg/benchmark/run",
            "/api/v1/kg/benchmark/suite",
            "/api/v1/kg/benchmark/drknows",
            "/api/v1/kg/benchmark",
        ]
        for endpoint in benchmark_endpoints:
            assert endpoint in DEFAULT_RATE_LIMITS
            assert DEFAULT_RATE_LIMITS[endpoint].requests_per_window > 0

    def test_health_endpoints_more_permissive(self) -> None:
        """Test that health/monitoring endpoints are more permissive."""
        health_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/health"].requests_per_window
        liveness_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/health/liveness"].requests_per_window
        query_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/orchestration/query"].requests_per_window

        # Health endpoints should allow more requests than query endpoints
        assert health_limit > query_limit
        assert liveness_limit > health_limit

    def test_expensive_operations_more_restricted(self) -> None:
        """Test that expensive operations have lower limits."""
        query_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/orchestration/query"].requests_per_window
        reasoning_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/orchestration/reasoning-path"].requests_per_window
        mdt_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/orchestration/mdt-session"].requests_per_window
        benchmark_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/benchmark/run"].requests_per_window

        # Reasoning paths are expensive
        assert reasoning_limit < query_limit

        # MDT sessions are very expensive (multi-agent)
        assert mdt_limit < reasoning_limit

        # Benchmark runs are resource-intensive
        assert benchmark_limit < reasoning_limit

    def test_benchmark_suite_most_restricted(self) -> None:
        """Test that benchmark suite runs are most restricted."""
        suite_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/benchmark/suite"].requests_per_window
        run_limit = DEFAULT_RATE_LIMITS["/api/v1/kg/benchmark/run"].requests_per_window

        # Suite runs (multiple benchmarks) should be more restricted
        assert suite_limit <= run_limit

    def test_rate_limit_config_has_burst_limit(self) -> None:
        """Test that rate limit configs have burst limits."""
        for endpoint, config in DEFAULT_RATE_LIMITS.items():
            if endpoint.startswith("/api/v1/kg"):
                assert config.burst_limit is not None
                assert config.burst_limit > 0

    def test_rate_limit_window_is_reasonable(self) -> None:
        """Test that rate limit windows are reasonable."""
        for endpoint, config in DEFAULT_RATE_LIMITS.items():
            if endpoint.startswith("/api/v1/kg"):
                # Window should be between 1 second and 24 hours
                assert 1 <= config.window_seconds <= 86400
                # Default window is 60 seconds
                assert config.window_seconds == 60

    def test_kg_limits_summary(self) -> None:
        """Test summary of all KG rate limits."""
        kg_limits = {
            endpoint: config
            for endpoint, config in DEFAULT_RATE_LIMITS.items()
            if endpoint.startswith("/api/v1/kg")
        }

        # Should have at least 10 KG-specific endpoints
        assert len(kg_limits) >= 10

        # Get the range of limits
        min_limit = min(c.requests_per_window for c in kg_limits.values())
        max_limit = max(c.requests_per_window for c in kg_limits.values())

        # There should be differentiation in limits
        assert min_limit < max_limit

        # Most restrictive should be at least 1 request per minute
        assert min_limit >= 1

        # Most permissive should be reasonable for monitoring
        assert max_limit <= 2000


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = RateLimitConfig()
        assert config.requests_per_window == 100
        assert config.window_seconds == 60
        assert config.burst_limit == 100

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RateLimitConfig(
            requests_per_window=50,
            window_seconds=30,
            burst_limit=100,
        )
        assert config.requests_per_window == 50
        assert config.window_seconds == 30
        assert config.burst_limit == 100

    def test_burst_limit_defaults_to_requests(self) -> None:
        """Test that burst_limit defaults to requests_per_window."""
        config = RateLimitConfig(requests_per_window=200)
        assert config.burst_limit == 200


class TestDefaultRateLimits:
    """Test default rate limit configuration."""

    def test_has_default_fallback(self) -> None:
        """Test that there's a default fallback limit."""
        assert "*" in DEFAULT_RATE_LIMITS
        default = DEFAULT_RATE_LIMITS["*"]
        assert default.requests_per_window > 0

    def test_all_configs_valid(self) -> None:
        """Test that all configs are valid RateLimitConfig instances."""
        for endpoint, config in DEFAULT_RATE_LIMITS.items():
            assert isinstance(config, RateLimitConfig)
            assert config.requests_per_window > 0
            assert config.window_seconds > 0
            assert config.burst_limit is not None
            assert config.burst_limit > 0
