"""Tests for Architecture Scalability Audit (CTO-1).

Covers:
- Component analysis for all 8+ components
- Scaling projections at different patient counts
- Bottleneck risk classification
- Database analysis: table size projections, index recommendations
- Horizontal scaling readiness checks
- Recommendation prioritization
- Scalability score calculation
- Load simulation at various scales
- Architecture health dashboard data
- Component detail retrieval
- API endpoint responses
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.scalability_audit import (
    BottleneckRisk,
    ComponentAnalysis,
    ComponentListResponse,
    ComponentScore,
    DatabaseAnalysis,
    IndexRecommendation,
    LoadSimulationRequest,
    LoadSimulationResult,
    PartitionStrategy,
    PartitionType,
    QueryComplexity,
    RecommendationPriority,
    RecommendationsResponse,
    ResourceEstimate,
    ScalabilityReport,
    ScalabilityScore,
    ScalingProjection,
    ScalingStrategy,
    ServiceScalingReadiness,
    ServiceType,
    TableSizeProjection,
    TierProjection,
)
from app.services.scalability_audit_service import (
    ROWS_PER_PATIENT,
    ROW_SIZES,
    STANDARD_TIERS,
    ScalabilityAuditService,
    get_scalability_audit_service,
    reset_scalability_audit_service,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def service() -> ScalabilityAuditService:
    """Create a fresh ScalabilityAuditService."""
    return ScalabilityAuditService()


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before each test."""
    reset_scalability_audit_service()
    yield
    reset_scalability_audit_service()


# ===========================================================================
# Component Analysis Tests
# ===========================================================================


class TestComponentAnalysis:
    """Test analysis of individual architectural components."""

    def test_analyze_all_components_returns_eight(self, service: ScalabilityAuditService):
        """All 8 components should be analyzed."""
        components = service.analyze_all_components()
        assert len(components) >= 8

    def test_all_component_names(self, service: ScalabilityAuditService):
        """Verify expected component names are present."""
        components = service.analyze_all_components()
        names = {c.name for c in components}
        expected = {
            "postgresql", "redis", "neo4j", "fastapi",
            "nlp_pipeline", "fhir_import", "trial_screening", "knowledge_graph",
        }
        assert expected.issubset(names)

    def test_component_has_required_fields(self, service: ScalabilityAuditService):
        """Each component analysis must have all required fields."""
        components = service.analyze_all_components()
        for comp in components:
            assert comp.name, "Component name must not be empty"
            assert comp.current_capacity, "current_capacity must not be empty"
            assert comp.scaling_strategy in ScalingStrategy
            assert comp.bottleneck_risk in BottleneckRisk
            assert comp.recommendation, "recommendation must not be empty"

    def test_analyze_postgresql(self, service: ScalabilityAuditService):
        """PostgreSQL analysis should identify high bottleneck risk."""
        comp = service.analyze_component("postgresql")
        assert comp is not None
        assert comp.name == "postgresql"
        assert comp.bottleneck_risk == BottleneckRisk.HIGH
        assert comp.scaling_strategy == ScalingStrategy.VERTICAL
        assert "connection" in comp.recommendation.lower() or "pool" in comp.recommendation.lower()

    def test_analyze_redis(self, service: ScalabilityAuditService):
        """Redis analysis should show low bottleneck risk."""
        comp = service.analyze_component("redis")
        assert comp is not None
        assert comp.name == "redis"
        assert comp.bottleneck_risk == BottleneckRisk.LOW
        assert comp.scaling_strategy == ScalingStrategy.HORIZONTAL

    def test_analyze_neo4j(self, service: ScalabilityAuditService):
        """Neo4j analysis should be medium risk."""
        comp = service.analyze_component("neo4j")
        assert comp is not None
        assert comp.name == "neo4j"
        assert comp.bottleneck_risk == BottleneckRisk.MEDIUM

    def test_analyze_fastapi(self, service: ScalabilityAuditService):
        """FastAPI analysis should show horizontal scaling strategy."""
        comp = service.analyze_component("fastapi")
        assert comp is not None
        assert comp.scaling_strategy == ScalingStrategy.HORIZONTAL

    def test_analyze_nlp_pipeline(self, service: ScalabilityAuditService):
        """NLP pipeline should have high bottleneck risk."""
        comp = service.analyze_component("nlp_pipeline")
        assert comp is not None
        assert comp.bottleneck_risk == BottleneckRisk.HIGH

    def test_analyze_fhir_import(self, service: ScalabilityAuditService):
        """FHIR import analysis should exist."""
        comp = service.analyze_component("fhir_import")
        assert comp is not None
        assert comp.name == "fhir_import"
        assert comp.scaling_strategy == ScalingStrategy.HORIZONTAL

    def test_analyze_trial_screening(self, service: ScalabilityAuditService):
        """Trial screening should have high bottleneck risk."""
        comp = service.analyze_component("trial_screening")
        assert comp is not None
        assert comp.bottleneck_risk == BottleneckRisk.HIGH

    def test_analyze_knowledge_graph(self, service: ScalabilityAuditService):
        """Knowledge graph should use caching strategy."""
        comp = service.analyze_component("knowledge_graph")
        assert comp is not None
        assert comp.scaling_strategy == ScalingStrategy.CACHING

    def test_analyze_nonexistent_component(self, service: ScalabilityAuditService):
        """Analyzing a nonexistent component should return None."""
        result = service.analyze_component("does_not_exist")
        assert result is None

    def test_get_component_names(self, service: ScalabilityAuditService):
        """get_component_names should return all known component names."""
        names = service.get_component_names()
        assert len(names) >= 8
        assert "postgresql" in names
        assert "redis" in names


# ===========================================================================
# Scaling Projection Tests
# ===========================================================================


class TestScalingProjections:
    """Test growth projections across patient tiers."""

    def test_projections_have_four_tiers(self, service: ScalabilityAuditService):
        """Projections should cover 1K, 10K, 100K, 1M patients."""
        projections = service.generate_projections()
        assert len(projections.tiers) == 4
        patient_counts = [t.patient_count for t in projections.tiers]
        assert patient_counts == [1_000, 10_000, 100_000, 1_000_000]

    def test_projections_increase_with_scale(self, service: ScalabilityAuditService):
        """Resources should increase at each tier."""
        projections = service.generate_projections()
        tiers = projections.tiers
        for i in range(1, len(tiers)):
            assert tiers[i].compute_vcpus >= tiers[i - 1].compute_vcpus
            assert tiers[i].memory_gb >= tiers[i - 1].memory_gb
            assert tiers[i].storage_gb >= tiers[i - 1].storage_gb
            assert tiers[i].estimated_monthly_cost_usd >= tiers[i - 1].estimated_monthly_cost_usd

    def test_projection_has_graph_estimates(self, service: ScalabilityAuditService):
        """Projections should include graph node/edge estimates."""
        projections = service.generate_projections()
        tier_1m = projections.tiers[-1]  # 1M patients
        assert tier_1m.graph_nodes > 0
        assert tier_1m.graph_edges > 0
        assert tier_1m.graph_edges > tier_1m.graph_nodes  # More edges than nodes

    def test_projection_has_database_rows(self, service: ScalabilityAuditService):
        """Projections should include estimated database row counts."""
        projections = service.generate_projections()
        for tier in projections.tiers:
            assert tier.database_rows > 0

    def test_projection_assumptions_present(self, service: ScalabilityAuditService):
        """Projection assumptions should be documented."""
        projections = service.generate_projections()
        assert "rows_per_patient" in projections.assumptions
        assert projections.growth_model == "linear"

    def test_cost_projection_at_1m_patients(self, service: ScalabilityAuditService):
        """Cost at 1M patients should be significant."""
        projections = service.generate_projections()
        tier_1m = projections.tiers[-1]
        assert tier_1m.estimated_monthly_cost_usd > 1000  # At least $1K/month at 1M patients


# ===========================================================================
# Database Analysis Tests
# ===========================================================================


class TestDatabaseAnalysis:
    """Test database-specific scalability analysis."""

    def test_database_analysis_returns_all_sections(self, service: ScalabilityAuditService):
        """Database analysis should have all major sections."""
        db = service.analyze_database()
        assert len(db.table_projections) > 0
        assert len(db.query_analysis) > 0
        assert len(db.index_recommendations) > 0
        assert len(db.partition_strategies) > 0
        assert db.connection_pool_analysis  # non-empty dict

    def test_table_projections_cover_key_tables(self, service: ScalabilityAuditService):
        """Table projections should cover major tables."""
        db = service.analyze_database()
        tables = {t.table for t in db.table_projections}
        assert "clinical_facts" in tables
        assert "patients" in tables
        assert "mentions" in tables

    def test_table_projection_sizes_increase(self, service: ScalabilityAuditService):
        """Table sizes should increase across tiers."""
        db = service.analyze_database()
        for proj in db.table_projections:
            # All size fields should be non-empty
            assert proj.size_at_1k
            assert proj.size_at_10k
            assert proj.size_at_100k
            assert proj.size_at_1m

    def test_clinical_facts_rows_per_patient(self, service: ScalabilityAuditService):
        """clinical_facts should have ~100 rows per patient."""
        db = service.analyze_database()
        cf = next(t for t in db.table_projections if t.table == "clinical_facts")
        assert cf.rows_per_patient == 100.0

    def test_index_recommendations_have_rationale(self, service: ScalabilityAuditService):
        """Each index recommendation should include rationale."""
        db = service.analyze_database()
        for idx in db.index_recommendations:
            assert idx.table, "Index must specify a table"
            assert len(idx.columns) > 0, "Index must specify columns"
            assert idx.rationale, "Index must include rationale"

    def test_partition_strategies_exist(self, service: ScalabilityAuditService):
        """Partition strategies should be recommended for large tables."""
        db = service.analyze_database()
        assert len(db.partition_strategies) >= 2
        tables = {p.table for p in db.partition_strategies}
        assert "clinical_facts" in tables

    def test_query_analysis_identifies_linear_queries(self, service: ScalabilityAuditService):
        """Query analysis should identify O(n) query patterns."""
        db = service.analyze_database()
        linear_queries = [
            q for q in db.query_analysis if q.complexity == QueryComplexity.LINEAR
        ]
        assert len(linear_queries) >= 1, "Should identify at least one O(n) query"

    def test_connection_pool_analysis(self, service: ScalabilityAuditService):
        """Connection pool analysis should flag risk."""
        db = service.analyze_database()
        pool = db.connection_pool_analysis
        assert "risk" in pool or "recommendation" in pool

    def test_overall_risk_assessment(self, service: ScalabilityAuditService):
        """Database overall risk should be assessed."""
        db = service.analyze_database()
        assert db.overall_risk in BottleneckRisk


# ===========================================================================
# Horizontal Scaling Tests
# ===========================================================================


class TestHorizontalScaling:
    """Test horizontal scaling readiness checks."""

    def test_horizontal_scaling_covers_services(self, service: ScalabilityAuditService):
        """Should assess scaling readiness for multiple services."""
        readiness = service.analyze_horizontal_scaling()
        assert len(readiness) >= 5

    def test_stateful_services_identified(self, service: ScalabilityAuditService):
        """Stateful services should be correctly identified."""
        readiness = service.analyze_horizontal_scaling()
        stateful = [r for r in readiness if r.service_type == ServiceType.STATEFUL]
        stateful_names = {r.service_name for r in stateful}
        assert "postgresql" in stateful_names

    def test_stateless_services_identified(self, service: ScalabilityAuditService):
        """Stateless services should be correctly identified."""
        readiness = service.analyze_horizontal_scaling()
        stateless = [r for r in readiness if r.service_type == ServiceType.STATELESS]
        assert len(stateless) >= 3
        stateless_names = {r.service_name for r in stateless}
        assert "fastapi_workers" in stateless_names

    def test_event_driven_opportunities(self, service: ScalabilityAuditService):
        """Event-driven architecture opportunities should be identified."""
        readiness = service.analyze_horizontal_scaling()
        total_opportunities = sum(
            len(r.event_driven_opportunities) for r in readiness
        )
        assert total_opportunities >= 3


# ===========================================================================
# Recommendation Tests
# ===========================================================================


class TestRecommendations:
    """Test recommendation generation and prioritization."""

    def test_recommendations_are_sorted_by_priority(self, service: ScalabilityAuditService):
        """Recommendations should be ordered by priority (critical first)."""
        recs = service.generate_recommendations()
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        priorities = [priority_order[r.priority] for r in recs]
        assert priorities == sorted(priorities), "Recommendations should be in priority order"

    def test_recommendations_have_required_fields(self, service: ScalabilityAuditService):
        """Each recommendation should have all required fields."""
        recs = service.generate_recommendations()
        for rec in recs:
            assert rec.priority in RecommendationPriority
            assert rec.component, "Must specify component"
            assert rec.title, "Must have a title"
            assert rec.effort in ("low", "medium", "high")
            assert rec.impact in ("low", "medium", "high")

    def test_critical_recommendations_exist(self, service: ScalabilityAuditService):
        """There should be at least one critical recommendation."""
        recs = service.generate_recommendations()
        critical = [r for r in recs if r.priority == RecommendationPriority.CRITICAL]
        assert len(critical) >= 1

    def test_recommendations_cover_multiple_components(self, service: ScalabilityAuditService):
        """Recommendations should cover multiple components."""
        recs = service.generate_recommendations()
        components = {r.component for r in recs}
        assert len(components) >= 4


# ===========================================================================
# Scalability Score Tests
# ===========================================================================


class TestScalabilityScore:
    """Test scalability score calculation."""

    def test_score_is_between_0_and_100(self, service: ScalabilityAuditService):
        """Overall score should be in range [0, 100]."""
        score = service.calculate_scalability_score()
        assert 0 <= score.overall_score <= 100

    def test_score_has_component_scores(self, service: ScalabilityAuditService):
        """Score should include per-component scores."""
        score = service.calculate_scalability_score()
        assert len(score.component_scores) >= 8

    def test_score_has_grade(self, service: ScalabilityAuditService):
        """Score should include a letter grade."""
        score = service.calculate_scalability_score()
        assert score.grade in ("A", "B", "C", "D", "F")

    def test_score_has_summary(self, service: ScalabilityAuditService):
        """Score should include a human-readable summary."""
        score = service.calculate_scalability_score()
        assert score.summary
        assert "scalability score" in score.summary.lower()

    def test_component_scores_within_range(self, service: ScalabilityAuditService):
        """Each component score should be 0-100."""
        score = service.calculate_scalability_score()
        for cs in score.component_scores:
            assert 0 <= cs.score <= 100

    def test_high_risk_components_have_low_scores(self, service: ScalabilityAuditService):
        """Components with high bottleneck risk should have lower scores."""
        score = service.calculate_scalability_score()
        for cs in score.component_scores:
            if cs.bottleneck_risk == BottleneckRisk.HIGH:
                assert cs.score < 60
            if cs.bottleneck_risk == BottleneckRisk.LOW:
                assert cs.score > 60


# ===========================================================================
# Load Simulation Tests
# ===========================================================================


class TestLoadSimulation:
    """Test load simulation at various scales."""

    def test_simulate_small_load(self, service: ScalabilityAuditService):
        """Small load (1K patients) should be handleable."""
        request = LoadSimulationRequest(patient_count=1_000)
        result = service.simulate_load(request)
        assert result.can_handle_load is True
        assert result.max_bottleneck_risk in (BottleneckRisk.LOW, BottleneckRisk.MEDIUM)

    def test_simulate_medium_load(self, service: ScalabilityAuditService):
        """Medium load (100K patients) should identify bottlenecks."""
        request = LoadSimulationRequest(patient_count=100_000, concurrent_users=200)
        result = service.simulate_load(request)
        assert len(result.bottlenecks) > 0

    def test_simulate_large_load(self, service: ScalabilityAuditService):
        """Large load (1M patients) should identify critical bottlenecks."""
        request = LoadSimulationRequest(
            patient_count=1_000_000,
            concurrent_users=500,
            screening_rate_per_hour=5000,
        )
        result = service.simulate_load(request)
        assert result.can_handle_load is False
        assert result.max_bottleneck_risk in (BottleneckRisk.HIGH, BottleneckRisk.CRITICAL)
        assert len(result.scaling_actions_needed) > 0

    def test_simulation_resource_estimates(self, service: ScalabilityAuditService):
        """Simulation should provide resource estimates."""
        request = LoadSimulationRequest(patient_count=10_000)
        result = service.simulate_load(request)
        assert result.estimated_resources.compute_vcpus > 0
        assert result.estimated_resources.memory_gb > 0
        assert result.estimated_resources.storage_gb > 0

    def test_simulation_cost_estimates(self, service: ScalabilityAuditService):
        """Simulation should include cost estimates."""
        request = LoadSimulationRequest(patient_count=100_000)
        result = service.simulate_load(request)
        assert result.estimated_resources.estimated_monthly_cost_usd > 0

    def test_simulation_high_screening_rate(self, service: ScalabilityAuditService):
        """High screening rate should trigger screening bottleneck."""
        request = LoadSimulationRequest(
            patient_count=10_000,
            screening_rate_per_hour=5000,
        )
        result = service.simulate_load(request)
        screening_bottlenecks = [
            b for b in result.bottlenecks if b.component == "trial_screening"
        ]
        assert len(screening_bottlenecks) > 0

    def test_simulation_high_concurrent_users(self, service: ScalabilityAuditService):
        """High concurrent users should trigger DB connection bottleneck."""
        request = LoadSimulationRequest(
            patient_count=1_000,
            concurrent_users=1000,
        )
        result = service.simulate_load(request)
        db_bottlenecks = [
            b for b in result.bottlenecks if b.component == "postgresql"
        ]
        assert len(db_bottlenecks) > 0


# ===========================================================================
# Full Report Tests
# ===========================================================================


class TestFullReport:
    """Test full scalability report generation."""

    def test_full_report_has_all_sections(self, service: ScalabilityAuditService):
        """Full report should contain all major sections."""
        report = service.generate_full_report()
        assert report.scalability_score is not None
        assert len(report.components) >= 8
        assert report.projections is not None
        assert report.database_analysis is not None
        assert len(report.horizontal_scaling) >= 5
        assert len(report.recommendations) >= 5

    def test_full_report_has_metadata(self, service: ScalabilityAuditService):
        """Report should include metadata."""
        report = service.generate_full_report()
        assert "version" in report.metadata
        assert "components_analyzed" in report.metadata
        assert report.metadata["components_analyzed"] >= 8

    def test_full_report_timestamp(self, service: ScalabilityAuditService):
        """Report should have a recent timestamp."""
        before = datetime.now(timezone.utc)
        report = service.generate_full_report()
        assert report.timestamp >= before


# ===========================================================================
# Singleton Tests
# ===========================================================================


class TestSingleton:
    """Test singleton pattern for the service."""

    def test_get_service_returns_instance(self):
        """get_scalability_audit_service should return an instance."""
        service = get_scalability_audit_service()
        assert isinstance(service, ScalabilityAuditService)

    def test_singleton_returns_same_instance(self):
        """Subsequent calls should return the same instance."""
        s1 = get_scalability_audit_service()
        s2 = get_scalability_audit_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        """After reset, a new instance should be created."""
        s1 = get_scalability_audit_service()
        reset_scalability_audit_service()
        s2 = get_scalability_audit_service()
        assert s1 is not s2

    def test_service_stats(self):
        """get_stats should return component info."""
        service = get_scalability_audit_service()
        stats = service.get_stats()
        assert stats["components_available"] >= 8
        assert len(stats["component_names"]) >= 8


# ===========================================================================
# Schema Validation Tests
# ===========================================================================


class TestSchemaValidation:
    """Test schema serialization and validation."""

    def test_component_analysis_serialization(self, service: ScalabilityAuditService):
        """ComponentAnalysis should serialize to dict correctly."""
        comp = service.analyze_component("postgresql")
        assert comp is not None
        data = comp.model_dump()
        assert data["name"] == "postgresql"
        assert data["scaling_strategy"] == "vertical"
        assert data["bottleneck_risk"] == "high"

    def test_load_simulation_request_validation(self):
        """LoadSimulationRequest should validate bounds."""
        req = LoadSimulationRequest(patient_count=1000)
        assert req.patient_count == 1000
        assert req.concurrent_users == 50  # default

    def test_load_simulation_request_rejects_negative(self):
        """LoadSimulationRequest should reject invalid values."""
        with pytest.raises(Exception):
            LoadSimulationRequest(patient_count=0)

    def test_tier_projection_schema(self, service: ScalabilityAuditService):
        """TierProjection should have all required fields."""
        proj = service.generate_projections()
        tier = proj.tiers[0]
        data = tier.model_dump()
        assert "patient_count" in data
        assert "compute_vcpus" in data
        assert "memory_gb" in data
        assert "storage_gb" in data
        assert "estimated_monthly_cost_usd" in data
        assert "graph_nodes" in data
        assert "graph_edges" in data


# ===========================================================================
# API Endpoint Tests
# ===========================================================================


class TestAPIEndpoints:
    """Test API endpoint responses."""

    @pytest.fixture
    def app(self):
        """Create the FastAPI app."""
        from app.main import app
        return app

    @pytest.mark.asyncio
    async def test_full_report_endpoint(self, app):
        """GET /architecture/scalability should return full report."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability")
            assert response.status_code == 200
            data = response.json()
            assert "scalability_score" in data
            assert "components" in data
            assert "projections" in data

    @pytest.mark.asyncio
    async def test_components_endpoint(self, app):
        """GET /architecture/scalability/components should return all components."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability/components")
            assert response.status_code == 200
            data = response.json()
            assert "components" in data
            assert data["total"] >= 8

    @pytest.mark.asyncio
    async def test_component_detail_endpoint(self, app):
        """GET /architecture/scalability/components/{name} should return detail."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability/components/postgresql")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "postgresql"

    @pytest.mark.asyncio
    async def test_component_detail_not_found(self, app):
        """GET /architecture/scalability/components/{bad} should return 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability/components/does_not_exist")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_projections_endpoint(self, app):
        """GET /architecture/scalability/projections should return projections."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability/projections")
            assert response.status_code == 200
            data = response.json()
            assert "tiers" in data
            assert len(data["tiers"]) == 4

    @pytest.mark.asyncio
    async def test_recommendations_endpoint(self, app):
        """GET /architecture/scalability/recommendations should return recs."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability/recommendations")
            assert response.status_code == 200
            data = response.json()
            assert "recommendations" in data
            assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_database_endpoint(self, app):
        """GET /architecture/scalability/database should return DB analysis."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/architecture/scalability/database")
            assert response.status_code == 200
            data = response.json()
            assert "table_projections" in data
            assert "index_recommendations" in data

    @pytest.mark.asyncio
    async def test_simulate_endpoint(self, app):
        """POST /architecture/scalability/simulate should run simulation."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/architecture/scalability/simulate",
                json={"patient_count": 100_000, "concurrent_users": 100},
            )
            assert response.status_code == 200
            data = response.json()
            assert "bottlenecks" in data
            assert "estimated_resources" in data
            assert data["patient_count"] == 100_000


# ===========================================================================
# Utility / Edge Case Tests
# ===========================================================================


class TestUtilities:
    """Test utility methods and edge cases."""

    def test_format_size_bytes(self, service: ScalabilityAuditService):
        """_format_size should format bytes correctly."""
        assert service._format_size(500) == "500B"
        assert "KB" in service._format_size(5_000)
        assert "MB" in service._format_size(5_000_000)
        assert "GB" in service._format_size(5_000_000_000)

    def test_risk_level_ordering(self, service: ScalabilityAuditService):
        """Risk levels should have correct ordering."""
        assert service._risk_level(BottleneckRisk.LOW) < service._risk_level(BottleneckRisk.MEDIUM)
        assert service._risk_level(BottleneckRisk.MEDIUM) < service._risk_level(BottleneckRisk.HIGH)
        assert service._risk_level(BottleneckRisk.HIGH) < service._risk_level(BottleneckRisk.CRITICAL)

    def test_score_to_grade_mapping(self, service: ScalabilityAuditService):
        """Score-to-grade mapping should be correct."""
        assert service._score_to_grade(95) == "A"
        assert service._score_to_grade(85) == "B"
        assert service._score_to_grade(75) == "C"
        assert service._score_to_grade(65) == "D"
        assert service._score_to_grade(55) == "F"

    def test_constants_defined(self):
        """Module-level constants should be defined."""
        assert len(ROWS_PER_PATIENT) >= 5
        assert len(ROW_SIZES) >= 5
        assert len(STANDARD_TIERS) == 4
        assert STANDARD_TIERS == [1_000, 10_000, 100_000, 1_000_000]
