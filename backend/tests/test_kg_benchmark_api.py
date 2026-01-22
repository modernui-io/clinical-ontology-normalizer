"""Tests for Knowledge Graph Benchmark API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestMedAgentBenchEndpoints:
    """Test MedAgentBench API endpoints."""

    def test_list_benchmark_suites(self) -> None:
        """Test listing benchmark suites."""
        response = client.get("/api/v1/kg/benchmark/medagentbench/suites")
        assert response.status_code == 200

        suites = response.json()
        assert isinstance(suites, list)
        assert len(suites) > 0

        # Check structure
        suite = suites[0]
        assert "suite_id" in suite
        assert "name" in suite
        assert "case_count" in suite

    def test_get_benchmark_suite(self) -> None:
        """Test getting a specific benchmark suite."""
        response = client.get("/api/v1/kg/benchmark/medagentbench/suites/qa_basic")
        assert response.status_code == 200

        suite = response.json()
        assert suite["suite_id"] == "qa_basic"
        assert "cases" in suite
        assert len(suite["cases"]) > 0

    def test_get_nonexistent_suite(self) -> None:
        """Test getting a non-existent suite."""
        response = client.get("/api/v1/kg/benchmark/medagentbench/suites/nonexistent")
        assert response.status_code == 404

    def test_run_benchmark_suite(self) -> None:
        """Test running a benchmark suite."""
        response = client.post("/api/v1/kg/benchmark/medagentbench/run/qa_basic")
        assert response.status_code == 200

        result = response.json()
        assert "suite_id" in result
        assert "total_cases" in result
        assert "passed_cases" in result
        assert "overall_accuracy" in result
        assert result["total_cases"] > 0

    def test_run_nonexistent_suite(self) -> None:
        """Test running a non-existent suite."""
        response = client.post("/api/v1/kg/benchmark/medagentbench/run/nonexistent")
        assert response.status_code == 404

    def test_compare_to_baseline(self) -> None:
        """Test comparing results to baseline."""
        response = client.post(
            "/api/v1/kg/benchmark/medagentbench/compare",
            json={"baseline_name": "DR.KNOWS"},
        )
        assert response.status_code == 200

        comparison = response.json()
        assert "baseline_name" in comparison
        assert comparison["baseline_name"] == "DR.KNOWS"

    def test_list_categories(self) -> None:
        """Test listing benchmark categories."""
        response = client.get("/api/v1/kg/benchmark/medagentbench/categories")
        assert response.status_code == 200

        categories = response.json()
        assert isinstance(categories, list)
        assert len(categories) > 0

        # Check for expected categories
        category_values = [c["value"] for c in categories]
        assert "question_answering" in category_values
        assert "multi_hop_reasoning" in category_values

    def test_list_difficulties(self) -> None:
        """Test listing difficulty levels."""
        response = client.get("/api/v1/kg/benchmark/medagentbench/difficulties")
        assert response.status_code == 200

        levels = response.json()
        assert isinstance(levels, list)
        assert len(levels) == 4  # easy, medium, hard, expert


class TestDRKNOWSEndpoints:
    """Test DR.KNOWS benchmark API endpoints."""

    def test_run_drknows_benchmark(self) -> None:
        """Test running DR.KNOWS benchmark."""
        response = client.post("/api/v1/kg/benchmark/drknows/run")
        assert response.status_code == 200

        result = response.json()
        assert "benchmark_id" in result
        assert "overall_score" in result
        assert "metrics" in result
        assert "comparison" in result

    def test_get_drknows_history(self) -> None:
        """Test getting benchmark history."""
        # First run a benchmark to ensure history exists
        client.post("/api/v1/kg/benchmark/drknows/run")

        response = client.get("/api/v1/kg/benchmark/drknows/history")
        assert response.status_code == 200

        history = response.json()
        assert isinstance(history, list)

    def test_get_drknows_history_with_limit(self) -> None:
        """Test getting benchmark history with limit."""
        response = client.get("/api/v1/kg/benchmark/drknows/history?limit=5")
        assert response.status_code == 200

        history = response.json()
        assert len(history) <= 5

    def test_get_latest_drknows_result(self) -> None:
        """Test getting latest benchmark result."""
        # First run a benchmark
        client.post("/api/v1/kg/benchmark/drknows/run")

        response = client.get("/api/v1/kg/benchmark/drknows/latest")
        assert response.status_code == 200

        result = response.json()
        assert "benchmark_id" in result
        assert "overall_score" in result

    def test_get_drknows_trend(self) -> None:
        """Test getting trend analysis."""
        response = client.get("/api/v1/kg/benchmark/drknows/trend")
        assert response.status_code == 200

        trend = response.json()
        # Either message (insufficient data) or trend data
        assert "message" in trend or "total_runs" in trend

    def test_get_drknows_baseline(self) -> None:
        """Test getting baseline metrics."""
        response = client.get("/api/v1/kg/benchmark/drknows/baseline")
        assert response.status_code == 200

        baseline = response.json()
        assert baseline["baseline_name"] == "DR.KNOWS"
        assert "metrics" in baseline
        assert "reasoning" in baseline["metrics"]
        assert "multi_hop" in baseline["metrics"]

    def test_get_semantic_groups(self) -> None:
        """Test getting UMLS semantic groups."""
        response = client.get("/api/v1/kg/benchmark/drknows/semantic-groups")
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 15  # 15 UMLS semantic groups
        assert "DISO" in groups  # Disorders
        assert "CHEM" in groups  # Chemicals


class TestBenchmarkHealth:
    """Test benchmark health endpoint."""

    def test_benchmark_health(self) -> None:
        """Test benchmark health check."""
        response = client.get("/api/v1/kg/benchmark/health")
        assert response.status_code == 200

        health = response.json()
        assert health["status"] == "healthy"
        assert "services" in health
        assert "medagentbench" in health["services"]
        assert "drknows" in health["services"]
        assert health["services"]["medagentbench"]["available"] is True
        assert health["services"]["drknows"]["available"] is True
