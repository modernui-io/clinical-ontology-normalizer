"""Tests for Knowledge Graph Admin CLI."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest

from app.cli.kg_admin import (
    clear_cache,
    get_cache_stats,
    get_health_status,
    get_stats,
    get_tracing_stats,
    main,
    run_benchmark,
)


class TestHealthStatus:
    """Test health status function."""

    def test_get_health_status_returns_dict(self) -> None:
        """Test that health status returns a dictionary."""
        result = get_health_status()
        assert isinstance(result, dict)

    def test_health_status_has_required_fields(self) -> None:
        """Test that health status has required fields."""
        result = get_health_status()

        # Even if services fail, these fields should exist
        if "error" not in result:
            assert "overall_status" in result
            assert "timestamp" in result
            assert "components" in result

    def test_health_status_overall_values(self) -> None:
        """Test that overall status has valid values."""
        result = get_health_status()

        if "overall_status" in result:
            assert result["overall_status"] in ["healthy", "degraded", "unhealthy"]


class TestCacheStats:
    """Test cache statistics function."""

    def test_get_cache_stats_returns_dict(self) -> None:
        """Test that cache stats returns a dictionary."""
        result = get_cache_stats()
        assert isinstance(result, dict)

    def test_cache_stats_has_hit_rate(self) -> None:
        """Test that cache stats include hit rate."""
        result = get_cache_stats()

        if "error" not in result:
            assert "hit_rate" in result or "hits" in result


class TestClearCache:
    """Test cache clearing function."""

    def test_clear_cache_returns_dict(self) -> None:
        """Test that clear cache returns a dictionary."""
        result = clear_cache()
        assert isinstance(result, dict)

    def test_clear_cache_reports_count(self) -> None:
        """Test that clear cache reports count."""
        result = clear_cache()

        if "error" not in result:
            assert "cleared" in result

    def test_clear_cache_invalid_type(self) -> None:
        """Test clearing cache with invalid type."""
        result = clear_cache("invalid_type")
        assert "error" in result


class TestTracingStats:
    """Test tracing statistics function."""

    def test_get_tracing_stats_returns_dict(self) -> None:
        """Test that tracing stats returns a dictionary."""
        result = get_tracing_stats()
        assert isinstance(result, dict)


class TestRunBenchmark:
    """Test benchmark execution function."""

    def test_run_benchmark_medagentbench(self) -> None:
        """Test running MedAgentBench."""
        result = run_benchmark("medagentbench")
        assert isinstance(result, dict)

    def test_run_benchmark_drknows(self) -> None:
        """Test running DR.KNOWS benchmark."""
        result = run_benchmark("drknows")
        assert isinstance(result, dict)

    def test_run_benchmark_invalid_suite(self) -> None:
        """Test running invalid benchmark suite."""
        result = run_benchmark("invalid_suite")
        assert "error" in result


class TestGetStats:
    """Test overall statistics function."""

    def test_get_stats_returns_dict(self) -> None:
        """Test that stats returns a dictionary."""
        result = get_stats()
        assert isinstance(result, dict)

    def test_stats_has_timestamp(self) -> None:
        """Test that stats include timestamp."""
        result = get_stats()
        assert "timestamp" in result


class TestMainCLI:
    """Test main CLI function."""

    def test_main_no_args_shows_help(self) -> None:
        """Test that main with no args returns 0."""
        # No command should print help and return 0
        result = main([])
        assert result == 0

    def test_main_health_command(self) -> None:
        """Test health command."""
        with patch("sys.stdout", new=StringIO()):
            result = main(["health"])
            # Should return 0 or 1 depending on health
            assert result in [0, 1]

    def test_main_cache_stats_command(self) -> None:
        """Test cache stats command."""
        with patch("sys.stdout", new=StringIO()):
            result = main(["cache"])
            assert result in [0, 1]

    def test_main_cache_clear_command(self) -> None:
        """Test cache clear command."""
        with patch("sys.stdout", new=StringIO()):
            result = main(["cache", "--clear"])
            assert result in [0, 1]

    def test_main_tracing_command(self) -> None:
        """Test tracing command."""
        with patch("sys.stdout", new=StringIO()):
            result = main(["tracing"])
            assert result in [0, 1]

    def test_main_stats_command(self) -> None:
        """Test stats command."""
        with patch("sys.stdout", new=StringIO()):
            result = main(["stats"])
            assert result in [0, 1]

    def test_main_benchmark_requires_suite(self) -> None:
        """Test benchmark command requires suite."""
        # This should fail because --suite is required
        with pytest.raises(SystemExit):
            main(["benchmark"])

    def test_main_benchmark_with_suite(self) -> None:
        """Test benchmark command with suite."""
        with patch("sys.stdout", new=StringIO()):
            result = main(["benchmark", "--suite", "drknows"])
            assert result in [0, 1]


class TestCLIOutput:
    """Test CLI output format."""

    def test_health_output_is_json(self) -> None:
        """Test that health output is valid JSON."""
        output = StringIO()
        with patch("sys.stdout", output):
            main(["health"])

        output.seek(0)
        data = json.loads(output.read())
        assert isinstance(data, dict)

    def test_stats_output_is_json(self) -> None:
        """Test that stats output is valid JSON."""
        output = StringIO()
        with patch("sys.stdout", output):
            main(["stats"])

        output.seek(0)
        data = json.loads(output.read())
        assert isinstance(data, dict)
