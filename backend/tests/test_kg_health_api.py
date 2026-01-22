"""Tests for Knowledge Graph Health Monitoring API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestOverallHealth:
    """Test overall health endpoint."""

    def test_get_overall_health(self) -> None:
        """Test getting overall health status."""
        response = client.get("/api/v1/kg/health/")
        assert response.status_code == 200

        health = response.json()
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in health
        assert "components" in health
        assert "dependencies" in health
        assert "summary" in health

    def test_health_includes_all_components(self) -> None:
        """Test that health includes all expected components."""
        response = client.get("/api/v1/kg/health/")
        assert response.status_code == 200

        health = response.json()
        component_names = {c["name"] for c in health["components"]}

        expected_components = {
            "graph_database",
            "graph_analytics",
            "graph_embedding",
            "causal_reasoning",
            "provenance",
            "multi_agent_orchestrator",
            "kg_visualization",
            "medagentbench",
            "drknows_benchmark",
            "kg_partitioning",
            "kg_kafka_streaming",
            "fhir_export",
        }
        assert expected_components.issubset(component_names)

    def test_health_includes_metrics(self) -> None:
        """Test that health includes metrics."""
        response = client.get("/api/v1/kg/health/")
        assert response.status_code == 200

        health = response.json()
        assert "metrics" in health
        assert "avg_component_latency_ms" in health["metrics"]
        assert "max_component_latency_ms" in health["metrics"]

    def test_health_summary_counts(self) -> None:
        """Test that health summary has correct counts."""
        response = client.get("/api/v1/kg/health/")
        assert response.status_code == 200

        health = response.json()
        summary = health["summary"]

        assert "total_components" in summary
        assert "healthy" in summary
        assert "degraded" in summary
        assert "unhealthy" in summary

        # Total should equal sum of all statuses
        total = summary["healthy"] + summary["degraded"] + summary["unhealthy"]
        assert total == summary["total_components"]


class TestComponentHealth:
    """Test individual component health endpoints."""

    def test_get_graph_database_health(self) -> None:
        """Test getting graph database component health."""
        response = client.get("/api/v1/kg/health/component/graph_database")
        assert response.status_code == 200

        health = response.json()
        assert health["name"] == "graph_database"
        assert "status" in health
        assert "latency_ms" in health
        assert "last_check" in health

    def test_get_graph_analytics_health(self) -> None:
        """Test getting graph analytics component health."""
        response = client.get("/api/v1/kg/health/component/graph_analytics")
        assert response.status_code == 200

        health = response.json()
        assert health["name"] == "graph_analytics"

    def test_get_medagentbench_health(self) -> None:
        """Test getting MedAgentBench component health."""
        response = client.get("/api/v1/kg/health/component/medagentbench")
        assert response.status_code == 200

        health = response.json()
        assert health["name"] == "medagentbench"

    def test_get_drknows_health(self) -> None:
        """Test getting DR.KNOWS benchmark component health."""
        response = client.get("/api/v1/kg/health/component/drknows_benchmark")
        assert response.status_code == 200

        health = response.json()
        assert health["name"] == "drknows_benchmark"

    def test_get_unknown_component(self) -> None:
        """Test getting unknown component returns error with available components."""
        response = client.get("/api/v1/kg/health/component/unknown_component")
        assert response.status_code == 200

        result = response.json()
        assert "error" in result
        assert "available_components" in result
        assert len(result["available_components"]) > 0


class TestDependenciesHealth:
    """Test dependencies health endpoint."""

    def test_get_dependencies_health(self) -> None:
        """Test getting dependencies health."""
        response = client.get("/api/v1/kg/health/dependencies")
        assert response.status_code == 200

        health = response.json()
        assert "timestamp" in health
        assert "summary" in health
        assert "dependencies" in health

    def test_dependencies_includes_neo4j(self) -> None:
        """Test that dependencies includes Neo4j."""
        response = client.get("/api/v1/kg/health/dependencies")
        assert response.status_code == 200

        health = response.json()
        dep_names = {d["name"] for d in health["dependencies"]}
        assert "neo4j" in dep_names


class TestProbes:
    """Test Kubernetes probes."""

    def test_liveness_probe(self) -> None:
        """Test liveness probe."""
        response = client.get("/api/v1/kg/health/liveness")
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "alive"
        assert "timestamp" in result

    def test_readiness_probe(self) -> None:
        """Test readiness probe."""
        response = client.get("/api/v1/kg/health/readiness")
        assert response.status_code == 200

        result = response.json()
        assert result["status"] in ["ready", "not_ready"]
        assert "timestamp" in result
        assert "critical_components" in result


class TestMetrics:
    """Test health metrics endpoint."""

    def test_get_health_metrics(self) -> None:
        """Test getting health metrics."""
        response = client.get("/api/v1/kg/health/metrics")
        assert response.status_code == 200

        metrics = response.json()
        assert "timestamp" in metrics
        assert "kg_health_components_total" in metrics
        assert "kg_health_components_healthy" in metrics
        assert "kg_health_check_latency_avg_ms" in metrics
        assert "component_latencies" in metrics
        assert "component_statuses" in metrics

    def test_metrics_have_all_components(self) -> None:
        """Test that metrics include all components."""
        response = client.get("/api/v1/kg/health/metrics")
        assert response.status_code == 200

        metrics = response.json()
        assert len(metrics["component_latencies"]) == metrics["kg_health_components_total"]
        assert len(metrics["component_statuses"]) == metrics["kg_health_components_total"]


class TestAlerts:
    """Test health alerts endpoint."""

    def test_get_health_alerts(self) -> None:
        """Test getting health alerts."""
        response = client.get("/api/v1/kg/health/alerts")
        assert response.status_code == 200

        result = response.json()
        assert "timestamp" in result
        assert "alert_count" in result
        assert "alerts" in result
        assert isinstance(result["alerts"], list)

    def test_alerts_have_correct_structure(self) -> None:
        """Test that alerts have correct structure."""
        response = client.get("/api/v1/kg/health/alerts")
        assert response.status_code == 200

        result = response.json()
        # If there are any alerts, check their structure
        for alert in result["alerts"]:
            assert "severity" in alert
            assert alert["severity"] in ["critical", "warning"]
            assert "component" in alert
            assert "status" in alert
            assert "message" in alert
            assert "timestamp" in alert
