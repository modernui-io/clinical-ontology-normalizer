"""Tests for DR.KNOWS Benchmark Service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.drknows_benchmark_service import (
    DRKNOWS_BASELINE,
    UMLS_SEMANTIC_GROUPS,
    DRKNOWSBenchmarkResult,
    DRKNOWSBenchmarkService,
    ExplanationMetrics,
    KnowledgeCoverageMetrics,
    MetricType,
    MultiHopMetrics,
    PathDiscoveryMetrics,
    ReasoningMetrics,
    RelationExtractionMetrics,
    SemanticCoverageMetrics,
    TemporalReasoningMetrics,
    get_drknows_benchmark_service,
)


class TestPathDiscoveryMetrics:
    """Test PathDiscoveryMetrics dataclass."""

    def test_create_path_discovery_metrics(self) -> None:
        """Test creating path discovery metrics."""
        metrics = PathDiscoveryMetrics(
            total_paths_expected=100,
            paths_discovered=85,
            path_coverage=0.85,
            avg_path_length=2.5,
            max_path_length=5,
            unique_relation_types=12,
            semantic_diversity=0.15,
        )
        assert metrics.path_coverage == 0.85
        assert metrics.avg_path_length == 2.5
        assert metrics.max_path_length == 5


class TestReasoningMetrics:
    """Test ReasoningMetrics dataclass."""

    def test_create_reasoning_metrics(self) -> None:
        """Test creating reasoning metrics."""
        metrics = ReasoningMetrics(
            total_queries=100,
            correct_inferences=84,
            accuracy=0.84,
            precision=0.87,
            recall=0.82,
            f1_score=0.845,
            avg_confidence=0.88,
        )
        assert metrics.accuracy == 0.84
        assert metrics.f1_score == 0.845


class TestSemanticCoverageMetrics:
    """Test SemanticCoverageMetrics dataclass."""

    def test_create_semantic_coverage_metrics(self) -> None:
        """Test creating semantic coverage metrics."""
        metrics = SemanticCoverageMetrics(
            total_semantic_types=127,
            covered_types=115,
            coverage_percentage=0.906,
            semantic_groups_covered=15,
            total_semantic_groups=15,
            group_coverage=1.0,
        )
        assert metrics.coverage_percentage == 0.906
        assert metrics.group_coverage == 1.0

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        metrics = SemanticCoverageMetrics()
        assert metrics.total_semantic_types == 127
        assert metrics.total_semantic_groups == 15


class TestMultiHopMetrics:
    """Test MultiHopMetrics dataclass."""

    def test_create_multi_hop_metrics(self) -> None:
        """Test creating multi-hop metrics."""
        metrics = MultiHopMetrics(
            hop_1_accuracy=0.92,
            hop_2_accuracy=0.88,
            hop_3_accuracy=0.84,
            hop_4_accuracy=0.79,
            hop_5_plus_accuracy=0.75,
            avg_accuracy=0.836,
            accuracy_degradation_per_hop=0.0425,
        )
        assert metrics.hop_1_accuracy == 0.92
        assert metrics.avg_accuracy == 0.836
        assert metrics.accuracy_degradation_per_hop == 0.0425

    def test_accuracy_decreases_with_hops(self) -> None:
        """Test that accuracy typically decreases with more hops."""
        metrics = MultiHopMetrics(
            hop_1_accuracy=0.95,
            hop_2_accuracy=0.90,
            hop_3_accuracy=0.85,
            hop_4_accuracy=0.80,
            hop_5_plus_accuracy=0.75,
        )
        assert metrics.hop_1_accuracy > metrics.hop_2_accuracy
        assert metrics.hop_2_accuracy > metrics.hop_3_accuracy
        assert metrics.hop_3_accuracy > metrics.hop_4_accuracy


class TestRelationExtractionMetrics:
    """Test RelationExtractionMetrics dataclass."""

    def test_create_relation_metrics(self) -> None:
        """Test creating relation extraction metrics."""
        metrics = RelationExtractionMetrics(
            total_relations=100,
            extracted_relations=90,
            true_positives=85,
            false_positives=5,
            false_negatives=10,
            precision=0.944,
            recall=0.894,
            f1_score=0.918,
        )
        assert metrics.precision == 0.944
        assert metrics.recall == 0.894


class TestKnowledgeCoverageMetrics:
    """Test KnowledgeCoverageMetrics dataclass."""

    def test_create_knowledge_coverage_metrics(self) -> None:
        """Test creating knowledge coverage metrics."""
        metrics = KnowledgeCoverageMetrics(
            total_concepts=4_500_000,
            indexed_concepts=4_000_000,
            concept_coverage=0.889,
            total_relationships=15_000_000,
            indexed_relationships=13_000_000,
            relationship_coverage=0.867,
            avg_connections_per_concept=3.25,
        )
        assert metrics.concept_coverage == 0.889
        assert metrics.relationship_coverage == 0.867


class TestTemporalReasoningMetrics:
    """Test TemporalReasoningMetrics dataclass."""

    def test_create_temporal_metrics(self) -> None:
        """Test creating temporal reasoning metrics."""
        metrics = TemporalReasoningMetrics(
            temporal_queries=50,
            correct_temporal_inferences=42,
            temporal_accuracy=0.84,
            time_travel_accuracy=0.88,
            bi_temporal_coverage=0.90,
        )
        assert metrics.temporal_accuracy == 0.84
        assert metrics.time_travel_accuracy == 0.88


class TestExplanationMetrics:
    """Test ExplanationMetrics dataclass."""

    def test_create_explanation_metrics(self) -> None:
        """Test creating explanation metrics."""
        metrics = ExplanationMetrics(
            total_explanations=100,
            avg_explanation_length=3.5,
            avg_evidence_count=2.8,
            human_readable_score=0.82,
            causal_chain_coverage=0.78,
        )
        assert metrics.human_readable_score == 0.82
        assert metrics.causal_chain_coverage == 0.78


class TestDRKNOWSBenchmarkService:
    """Test DRKNOWSBenchmarkService class."""

    def test_service_initialization(self) -> None:
        """Test service initializes correctly."""
        service = DRKNOWSBenchmarkService()
        assert service._baseline == DRKNOWS_BASELINE
        assert service._semantic_groups == UMLS_SEMANTIC_GROUPS
        assert len(service._benchmark_history) == 0

    def test_generate_test_queries(self) -> None:
        """Test generating test queries."""
        service = DRKNOWSBenchmarkService()
        queries = service._generate_test_queries()

        assert len(queries) > 0
        # Check various query types
        query_types = {q["type"] for q in queries}
        assert "drug_disease" in query_types
        assert "drug_interaction" in query_types
        assert "causal_chain" in query_types

    @pytest.mark.asyncio
    async def test_benchmark_path_discovery(self) -> None:
        """Test path discovery benchmarking."""
        service = DRKNOWSBenchmarkService()
        queries = service._generate_test_queries()

        metrics = await service._benchmark_path_discovery(None, queries)

        assert isinstance(metrics, PathDiscoveryMetrics)
        assert metrics.total_paths_expected == len(queries)
        assert 0 <= metrics.path_coverage <= 1

    @pytest.mark.asyncio
    async def test_benchmark_reasoning(self) -> None:
        """Test reasoning benchmarking."""
        service = DRKNOWSBenchmarkService()
        queries = service._generate_test_queries()

        metrics = await service._benchmark_reasoning(None, queries)

        assert isinstance(metrics, ReasoningMetrics)
        assert metrics.total_queries == len(queries)
        assert 0 <= metrics.accuracy <= 1
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1

    @pytest.mark.asyncio
    async def test_benchmark_semantic_coverage(self) -> None:
        """Test semantic coverage benchmarking."""
        service = DRKNOWSBenchmarkService()

        metrics = await service._benchmark_semantic_coverage(None)

        assert isinstance(metrics, SemanticCoverageMetrics)
        assert metrics.total_semantic_types == 127
        assert 0 <= metrics.coverage_percentage <= 1

    @pytest.mark.asyncio
    async def test_benchmark_multi_hop(self) -> None:
        """Test multi-hop reasoning benchmarking."""
        service = DRKNOWSBenchmarkService()
        queries = service._generate_test_queries()

        metrics = await service._benchmark_multi_hop(None, queries)

        assert isinstance(metrics, MultiHopMetrics)
        assert 0 <= metrics.hop_1_accuracy <= 1
        assert 0 <= metrics.hop_2_accuracy <= 1

    @pytest.mark.asyncio
    async def test_run_full_benchmark(self) -> None:
        """Test running a complete benchmark suite."""
        service = DRKNOWSBenchmarkService()

        result = await service.run_full_benchmark(None)

        assert isinstance(result, DRKNOWSBenchmarkResult)
        assert result.benchmark_id.startswith("drknows_")
        assert result.path_discovery is not None
        assert result.reasoning is not None
        assert result.semantic_coverage is not None
        assert result.multi_hop is not None
        assert 0 <= result.overall_score <= 1

    @pytest.mark.asyncio
    async def test_benchmark_history_tracking(self) -> None:
        """Test that benchmark history is tracked."""
        service = DRKNOWSBenchmarkService()

        assert len(service.get_benchmark_history()) == 0

        await service.run_full_benchmark(None)

        history = service.get_benchmark_history()
        assert len(history) == 1

        await service.run_full_benchmark(None)
        assert len(service.get_benchmark_history()) == 2

    @pytest.mark.asyncio
    async def test_get_latest_benchmark(self) -> None:
        """Test getting the latest benchmark result."""
        service = DRKNOWSBenchmarkService()

        assert service.get_latest_benchmark() is None

        await service.run_full_benchmark(None)
        latest = service.get_latest_benchmark()

        assert latest is not None
        assert isinstance(latest, DRKNOWSBenchmarkResult)


class TestBaselineComparison:
    """Test baseline comparison functionality."""

    @pytest.mark.asyncio
    async def test_compare_to_baseline(self) -> None:
        """Test comparison to DR.KNOWS baseline."""
        service = DRKNOWSBenchmarkService()

        result = await service.run_full_benchmark(None)

        assert "comparison_to_baseline" in result.__dict__
        comparison = result.comparison_to_baseline

        assert "overall" in comparison
        assert "reasoning" in comparison
        assert "path_discovery" in comparison
        assert "assessment" in comparison
        assert "status" in comparison

    @pytest.mark.asyncio
    async def test_comparison_includes_delta(self) -> None:
        """Test that comparison includes delta values."""
        service = DRKNOWSBenchmarkService()

        result = await service.run_full_benchmark(None)
        comparison = result.comparison_to_baseline

        assert "delta" in comparison["overall"]
        assert "delta" in comparison["reasoning"]


class TestOverallScoreCalculation:
    """Test overall score calculation."""

    def test_calculate_overall_score(self) -> None:
        """Test overall score is calculated correctly."""
        service = DRKNOWSBenchmarkService()

        path = PathDiscoveryMetrics(
            total_paths_expected=100,
            paths_discovered=85,
            path_coverage=0.85,
            avg_path_length=2.5,
            max_path_length=5,
            unique_relation_types=12,
            semantic_diversity=0.15,
        )
        reasoning = ReasoningMetrics(
            total_queries=100,
            correct_inferences=84,
            accuracy=0.84,
            precision=0.87,
            recall=0.82,
            f1_score=0.845,
            avg_confidence=0.88,
        )
        semantic = SemanticCoverageMetrics(
            covered_types=115,
            coverage_percentage=0.906,
            semantic_groups_covered=15,
            group_coverage=1.0,
        )
        relation = RelationExtractionMetrics(
            total_relations=100,
            extracted_relations=90,
            true_positives=85,
            false_positives=5,
            false_negatives=10,
            precision=0.944,
            recall=0.894,
            f1_score=0.918,
        )
        multihop = MultiHopMetrics(
            hop_1_accuracy=0.92,
            hop_2_accuracy=0.88,
            hop_3_accuracy=0.84,
            hop_4_accuracy=0.79,
            hop_5_plus_accuracy=0.75,
            avg_accuracy=0.836,
        )

        score = service._calculate_overall_score(
            path, reasoning, semantic, relation, multihop
        )

        assert 0 <= score <= 1
        # Score should be weighted average
        assert score > 0


class TestTrendAnalysis:
    """Test trend analysis functionality."""

    @pytest.mark.asyncio
    async def test_trend_analysis_insufficient_data(self) -> None:
        """Test trend analysis with insufficient data."""
        service = DRKNOWSBenchmarkService()

        trend = service.get_trend_analysis()
        assert "message" in trend

        await service.run_full_benchmark(None)
        trend = service.get_trend_analysis()
        assert "message" in trend

    @pytest.mark.asyncio
    async def test_trend_analysis_with_data(self) -> None:
        """Test trend analysis with multiple runs."""
        service = DRKNOWSBenchmarkService()

        await service.run_full_benchmark(None)
        await service.run_full_benchmark(None)

        trend = service.get_trend_analysis()

        assert "total_runs" in trend
        assert trend["total_runs"] == 2
        assert "first_score" in trend
        assert "latest_score" in trend
        assert "trend" in trend


class TestBenchmarkExport:
    """Test benchmark export functionality."""

    @pytest.mark.asyncio
    async def test_export_benchmark_report(self) -> None:
        """Test exporting benchmark report."""
        service = DRKNOWSBenchmarkService()

        result = await service.run_full_benchmark(None)
        report = service.export_benchmark_report(result)

        assert "benchmark_id" in report
        assert "run_at" in report
        assert "overall_score" in report
        assert "metrics" in report
        assert "comparison" in report

        # Check metrics structure
        metrics = report["metrics"]
        assert "path_discovery" in metrics
        assert "reasoning" in metrics
        assert "semantic_coverage" in metrics
        assert "multi_hop" in metrics


class TestBaselineValues:
    """Test DR.KNOWS baseline values."""

    def test_baseline_structure(self) -> None:
        """Test baseline has correct structure."""
        assert "path_discovery" in DRKNOWS_BASELINE
        assert "reasoning" in DRKNOWS_BASELINE
        assert "semantic_coverage" in DRKNOWS_BASELINE
        assert "multi_hop" in DRKNOWS_BASELINE
        assert "overall_score" in DRKNOWS_BASELINE

    def test_baseline_values_reasonable(self) -> None:
        """Test baseline values are within expected ranges."""
        assert 0.8 <= DRKNOWS_BASELINE["overall_score"] <= 0.9
        assert 0.8 <= DRKNOWS_BASELINE["reasoning"]["accuracy"] <= 0.9
        assert 0.8 <= DRKNOWS_BASELINE["path_discovery"]["path_coverage"] <= 0.9


class TestUMLSSemanticGroups:
    """Test UMLS semantic groups mapping."""

    def test_all_groups_defined(self) -> None:
        """Test all 15 semantic groups are defined."""
        assert len(UMLS_SEMANTIC_GROUPS) == 15

    def test_key_groups_present(self) -> None:
        """Test key semantic groups are present."""
        assert "DISO" in UMLS_SEMANTIC_GROUPS  # Disorders
        assert "CHEM" in UMLS_SEMANTIC_GROUPS  # Chemicals & Drugs
        assert "PROC" in UMLS_SEMANTIC_GROUPS  # Procedures
        assert "ANAT" in UMLS_SEMANTIC_GROUPS  # Anatomical Structure


class TestMetricTypes:
    """Test MetricType enum."""

    def test_all_metric_types(self) -> None:
        """Test all metric types exist."""
        types = list(MetricType)
        assert MetricType.PATH_DISCOVERY in types
        assert MetricType.REASONING_ACCURACY in types
        assert MetricType.SEMANTIC_COVERAGE in types
        assert MetricType.MULTI_HOP in types
        assert MetricType.TEMPORAL_REASONING in types


class TestSingletonPattern:
    """Test singleton service pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton service instance."""
        service1 = get_drknows_benchmark_service()
        service2 = get_drknows_benchmark_service()
        assert service1 is service2
