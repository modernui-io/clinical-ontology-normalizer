"""Tests for research experiment service."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.schemas.research import (
    ExperimentConfig,
    ExperimentCreate,
    ExperimentUpdate,
)
from app.services.research_service import ResearchService


@pytest.fixture
def service():
    return ResearchService()


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    with patch("app.services.research_service.get_sync_engine") as mock_engine:
        mock_eng = MagicMock()
        mock_engine.return_value = mock_eng
        yield mock_eng


class TestExperimentCreate:
    def test_create_experiment_schema(self):
        data = ExperimentCreate(
            name="Assertion-Aware EKG",
            description="Test assertion detection impact on KG quality",
            hypothesis="Assertion-aware NLP improves KG precision by 15%+",
            config=ExperimentConfig(
                assertion_aware=True,
                graph_rag=True,
                nlp_method="ensemble",
            ),
            tags=["neurips", "assertions"],
        )
        assert data.name == "Assertion-Aware EKG"
        assert data.config.assertion_aware is True
        assert data.config.nlp_method == "ensemble"
        assert len(data.tags) == 2

    def test_create_experiment_defaults(self):
        data = ExperimentCreate(name="Baseline")
        assert data.config.assertion_aware is True
        assert data.config.graph_rag is True
        assert data.config.nlp_method == "ensemble"
        assert data.tags is None

    def test_create_experiment_validation(self):
        with pytest.raises(Exception):
            ExperimentCreate(name="")


class TestExperimentUpdate:
    def test_partial_update(self):
        data = ExperimentUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.description is None
        assert data.config is None

    def test_config_update(self):
        data = ExperimentUpdate(
            config=ExperimentConfig(nlp_method="rule_based", assertion_aware=False)
        )
        assert data.config.nlp_method == "rule_based"
        assert data.config.assertion_aware is False


class TestExperimentConfig:
    def test_default_config(self):
        config = ExperimentConfig()
        assert config.assertion_aware is True
        assert config.graph_rag is True
        assert config.nlp_method == "ensemble"
        assert config.kg_construction is True
        assert config.max_documents is None

    def test_custom_config(self):
        config = ExperimentConfig(
            assertion_aware=False,
            nlp_method="ml",
            max_documents=1000,
        )
        assert config.assertion_aware is False
        assert config.nlp_method == "ml"
        assert config.max_documents == 1000

    def test_config_serialization(self):
        config = ExperimentConfig(nlp_method="rule_based")
        dumped = config.model_dump()
        assert dumped["nlp_method"] == "rule_based"
        assert dumped["assertion_aware"] is True


class TestComparisonSchemas:
    def test_comparison_request(self):
        from app.schemas.research import ComparisonRequest

        req = ComparisonRequest(run_ids=["run1", "run2"])
        assert len(req.run_ids) == 2

    def test_comparison_request_min_runs(self):
        from app.schemas.research import ComparisonRequest

        with pytest.raises(Exception):
            ComparisonRequest(run_ids=["run1"])


class TestExportSchemas:
    def test_export_request_csv(self):
        from app.schemas.research import ExportRequest

        req = ExportRequest(run_ids=["run1"], format="csv")
        assert req.format == "csv"

    def test_export_request_latex(self):
        from app.schemas.research import ExportRequest

        req = ExportRequest(run_ids=["run1"], format="latex")
        assert req.format == "latex"

    def test_export_request_json(self):
        from app.schemas.research import ExportRequest

        req = ExportRequest(run_ids=["run1"], format="json")
        assert req.format == "json"


class TestAnalyticsSchemas:
    def test_assertion_analytics_defaults(self):
        from app.schemas.research import AssertionAnalytics

        a = AssertionAnalytics()
        assert a.total_mentions == 0
        assert a.assertion_counts == {}

    def test_mapping_quality_defaults(self):
        from app.schemas.research import MappingQuality

        m = MappingQuality()
        assert m.coverage_percent == 0.0
        assert m.top_unmapped == []

    def test_kg_metrics_defaults(self):
        from app.schemas.research import KGMetrics

        k = KGMetrics()
        assert k.total_nodes == 0
        assert k.avg_nodes_per_patient == 0.0

    def test_pipeline_timing_defaults(self):
        from app.schemas.research import PipelineTimingMetrics

        t = PipelineTimingMetrics()
        assert t.avg_nlp_ms == 0.0
        assert t.documents_timed == 0


class TestResearchServiceExportHelpers:
    def test_export_csv_format(self):
        from app.schemas.research import ComparisonResponse, RunComparisonColumn

        comparison = ComparisonResponse(
            metric_names=["assertion/total_mentions", "mapping/coverage_percent"],
            runs=[
                RunComparisonColumn(
                    run_id="r1",
                    experiment_name="Exp A",
                    status="completed",
                    metrics={"assertion/total_mentions": 100, "mapping/coverage_percent": 85.5},
                ),
                RunComparisonColumn(
                    run_id="r2",
                    experiment_name="Exp B",
                    status="completed",
                    metrics={"assertion/total_mentions": 150, "mapping/coverage_percent": 90.2},
                ),
            ],
        )

        service = ResearchService()
        result = service._export_csv(comparison)
        assert result.format == "csv"
        assert "Exp A" in result.content
        assert "Exp B" in result.content
        assert result.mime_type == "text/csv"

    def test_export_latex_format(self):
        from app.schemas.research import ComparisonResponse, RunComparisonColumn

        comparison = ComparisonResponse(
            metric_names=["kg/total_nodes"],
            runs=[
                RunComparisonColumn(
                    run_id="r1",
                    experiment_name="Baseline",
                    status="completed",
                    metrics={"kg/total_nodes": 500},
                ),
            ],
        )

        service = ResearchService()
        result = service._export_latex(comparison)
        assert result.format == "latex"
        assert "\\begin{tabular}" in result.content
        assert "\\toprule" in result.content
        assert "Baseline" in result.content

    def test_export_json_format(self):
        from app.schemas.research import ComparisonResponse, RunComparisonColumn

        comparison = ComparisonResponse(
            metric_names=["timing/avg_total_ms"],
            runs=[
                RunComparisonColumn(
                    run_id="r1",
                    experiment_name="Fast",
                    status="completed",
                    metrics={"timing/avg_total_ms": 42.5},
                ),
            ],
        )

        service = ResearchService()
        result = service._export_json(comparison)
        assert result.format == "json"
        assert "Fast" in result.content
        assert result.mime_type == "application/json"
