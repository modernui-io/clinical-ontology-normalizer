"""Tests for research API endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient


@pytest.fixture
def mock_user():
    return {"sub": "test-researcher", "user_id": "test-researcher"}


@pytest.fixture
def mock_research_service():
    with patch("app.api.research.get_research_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


@pytest.fixture
def client(mock_user):
    with patch("app.api.middleware.get_current_user", return_value=mock_user):
        from app.main import app

        return TestClient(app)


class TestExperimentEndpoints:
    def test_create_experiment_schema(self):
        """Test experiment creation payload structure."""
        from app.schemas.research import ExperimentCreate, ExperimentConfig

        payload = ExperimentCreate(
            name="NeurIPS Baseline",
            description="Baseline experiment without assertion awareness",
            hypothesis="Standard NLP pipeline produces adequate KG quality",
            config=ExperimentConfig(
                assertion_aware=False,
                nlp_method="rule_based",
            ),
            tags=["baseline", "neurips-2026"],
        )

        assert payload.name == "NeurIPS Baseline"
        assert payload.config.assertion_aware is False
        assert "baseline" in payload.tags

    def test_experiment_response_model(self):
        """Test experiment response schema."""
        from app.schemas.research import ExperimentResponse

        resp = ExperimentResponse(
            id="exp-123",
            name="Test",
            status="draft",
            created_at=datetime.now(timezone.utc),
            run_count=3,
        )
        assert resp.id == "exp-123"
        assert resp.run_count == 3

    def test_experiment_list_response(self):
        """Test experiment list response."""
        from app.schemas.research import ExperimentListResponse, ExperimentResponse

        resp = ExperimentListResponse(
            experiments=[
                ExperimentResponse(
                    id="e1",
                    name="Exp 1",
                    status="completed",
                    created_at=datetime.now(timezone.utc),
                ),
                ExperimentResponse(
                    id="e2",
                    name="Exp 2",
                    status="draft",
                    created_at=datetime.now(timezone.utc),
                ),
            ],
            total=2,
        )
        assert len(resp.experiments) == 2
        assert resp.total == 2


class TestRunEndpoints:
    def test_run_create_schema(self):
        """Test run creation payload."""
        from app.schemas.research import RunCreate

        payload = RunCreate(
            experiment_id="exp-123",
            mimic_csv_path="/data/mimic-iv/discharge.csv",
            max_rows=500,
            chunk_size=50,
        )
        assert payload.experiment_id == "exp-123"
        assert payload.max_rows == 500

    def test_run_response_model(self):
        """Test run response schema."""
        from app.schemas.research import RunResponse

        resp = RunResponse(
            id="run-456",
            experiment_id="exp-123",
            status="completed",
            created_at=datetime.now(timezone.utc),
            document_ids=["d1", "d2", "d3"],
            patient_ids=["p1", "p2"],
            metric_count=15,
        )
        assert len(resp.document_ids) == 3
        assert resp.metric_count == 15

    def test_run_progress_response(self):
        """Test run progress schema."""
        from app.schemas.research import RunProgressResponse

        resp = RunProgressResponse(
            run_id="run-456",
            experiment_id="exp-123",
            status="processing",
            progress_percent=45.2,
            documents_total=100,
        )
        assert resp.progress_percent == 45.2


class TestMetricsEndpoints:
    def test_assertion_analytics_response(self):
        """Test assertion analytics schema."""
        from app.schemas.research import AssertionAnalytics

        resp = AssertionAnalytics(
            total_mentions=1500,
            assertion_counts={
                "present": 1000,
                "negated": 350,
                "uncertain": 100,
                "hypothetical": 50,
            },
            assertion_by_domain={
                "Condition": {"present": 600, "negated": 200},
                "Drug": {"present": 400, "negated": 150},
            },
        )
        assert resp.total_mentions == 1500
        assert resp.assertion_counts["negated"] == 350
        assert resp.assertion_by_domain["Condition"]["present"] == 600

    def test_mapping_quality_response(self):
        """Test mapping quality schema."""
        from app.schemas.research import MappingQuality

        resp = MappingQuality(
            total_mentions=1000,
            mapped_count=850,
            unmapped_count=150,
            coverage_percent=85.0,
            avg_confidence=0.89,
            domain_coverage={"Condition": 92.0, "Drug": 88.0, "Procedure": 75.0},
            top_unmapped=[
                {"term": "SOB", "count": 15},
                {"term": "NSTEMI", "count": 12},
            ],
        )
        assert resp.coverage_percent == 85.0
        assert len(resp.top_unmapped) == 2

    def test_kg_metrics_response(self):
        """Test KG metrics schema."""
        from app.schemas.research import KGMetrics

        resp = KGMetrics(
            total_nodes=5000,
            total_edges=12000,
            unique_concepts=800,
            patient_count=50,
            avg_nodes_per_patient=100.0,
        )
        assert resp.total_nodes == 5000
        assert resp.avg_nodes_per_patient == 100.0


class TestComparisonExport:
    def test_comparison_response(self):
        """Test comparison response schema."""
        from app.schemas.research import ComparisonResponse, RunComparisonColumn

        resp = ComparisonResponse(
            metric_names=["assertion/total_mentions", "mapping/coverage_percent"],
            runs=[
                RunComparisonColumn(
                    run_id="r1",
                    experiment_name="Baseline",
                    status="completed",
                    metrics={
                        "assertion/total_mentions": 1000,
                        "mapping/coverage_percent": 85.0,
                    },
                ),
                RunComparisonColumn(
                    run_id="r2",
                    experiment_name="Assertion-Aware",
                    status="completed",
                    metrics={
                        "assertion/total_mentions": 1500,
                        "mapping/coverage_percent": 92.0,
                    },
                ),
            ],
        )
        assert len(resp.metric_names) == 2
        assert resp.runs[1].metrics["mapping/coverage_percent"] == 92.0

    def test_export_response(self):
        """Test export response schema."""
        from app.schemas.research import ExportResponse

        resp = ExportResponse(
            format="latex",
            filename="metrics.tex",
            content="\\begin{tabular}{lr}\n...\n\\end{tabular}",
            mime_type="text/plain",
        )
        assert resp.format == "latex"
        assert "tabular" in resp.content
