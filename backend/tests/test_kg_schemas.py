"""Tests for Knowledge Graph API schemas."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.kg_schemas import (
    BenchmarkMetrics,
    BenchmarkResult,
    ClinicalAnswer,
    ClinicalQuestionResponse,
    ComponentHealth,
    ConceptDetail,
    ConceptSummary,
    D3JSGraph,
    DependencyHealth,
    HealthAlert,
    HealthAlerts,
    HealthStatus,
    KGErrorDetail,
    KGErrorResponse,
    MDTConsensus,
    MDTSessionResponse,
    OverallHealth,
    PatientGraph,
    PatientGraphEdge,
    PatientGraphNode,
    ReasoningPath,
    ReasoningStep,
    RelationshipEdge,
    RelationshipType,
    SemanticGroup,
)


class TestEnums:
    """Test enum definitions."""

    def test_health_status_values(self) -> None:
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"

    def test_semantic_group_values(self) -> None:
        """Test SemanticGroup enum values."""
        assert SemanticGroup.DISO.value == "DISO"
        assert SemanticGroup.CHEM.value == "CHEM"
        assert SemanticGroup.ANAT.value == "ANAT"
        assert SemanticGroup.PROC.value == "PROC"

    def test_relationship_type_values(self) -> None:
        """Test RelationshipType enum values."""
        assert RelationshipType.IS_A.value == "is_a"
        assert RelationshipType.MAY_TREAT.value == "may_treat"
        assert RelationshipType.CAUSES.value == "causes"


class TestConceptModels:
    """Test concept-related models."""

    def test_concept_summary_creation(self) -> None:
        """Test ConceptSummary model."""
        concept = ConceptSummary(
            cui="C0004096",
            name="Asthma",
            semantic_type="Disease or Syndrome",
            semantic_group=SemanticGroup.DISO,
        )
        assert concept.cui == "C0004096"
        assert concept.name == "Asthma"
        assert concept.semantic_group == SemanticGroup.DISO

    def test_concept_summary_minimal(self) -> None:
        """Test ConceptSummary with minimal fields."""
        concept = ConceptSummary(cui="C0000001", name="Test Concept")
        assert concept.cui == "C0000001"
        assert concept.semantic_type is None
        assert concept.semantic_group is None

    def test_concept_detail_creation(self) -> None:
        """Test ConceptDetail model."""
        concept = ConceptDetail(
            cui="C0004096",
            name="Asthma",
            semantic_type="Disease or Syndrome",
            semantic_group=SemanticGroup.DISO,
            sources=["SNOMEDCT_US", "ICD10CM"],
            synonyms=["Bronchial Asthma"],
            codes={"ICD10CM": "J45.909"},
        )
        assert len(concept.sources) == 2
        assert "ICD10CM" in concept.codes

    def test_concept_serialization(self) -> None:
        """Test concept JSON serialization."""
        concept = ConceptSummary(
            cui="C0004096",
            name="Asthma",
            semantic_group=SemanticGroup.DISO,
        )
        data = concept.model_dump()
        assert data["cui"] == "C0004096"
        assert data["semantic_group"] == "DISO"


class TestRelationshipModels:
    """Test relationship models."""

    def test_relationship_edge_creation(self) -> None:
        """Test RelationshipEdge model."""
        source = ConceptSummary(cui="C0004096", name="Asthma")
        target = ConceptSummary(cui="C0001927", name="Albuterol")
        edge = RelationshipEdge(
            source=source,
            target=target,
            relationship_type="may_treat",
            confidence=0.95,
            sources=["UMLS"],
        )
        assert edge.relationship_type == "may_treat"
        assert edge.confidence == 0.95

    def test_relationship_edge_temporal(self) -> None:
        """Test RelationshipEdge with temporal info."""
        now = datetime.now(timezone.utc)
        edge = RelationshipEdge(
            source=ConceptSummary(cui="C1", name="Source"),
            target=ConceptSummary(cui="C2", name="Target"),
            relationship_type="associated_with",
            valid_from=now,
        )
        assert edge.valid_from is not None
        assert edge.valid_to is None


class TestReasoningModels:
    """Test reasoning path models."""

    def test_reasoning_step_creation(self) -> None:
        """Test ReasoningStep model."""
        step = ReasoningStep(
            step_number=1,
            from_concept=ConceptSummary(cui="C1", name="Start"),
            to_concept=ConceptSummary(cui="C2", name="End"),
            relationship="may_cause",
            confidence=0.85,
            evidence=["UMLS evidence"],
        )
        assert step.step_number == 1
        assert step.confidence == 0.85

    def test_reasoning_path_creation(self) -> None:
        """Test ReasoningPath model."""
        path = ReasoningPath(
            path_id="path_001",
            source=ConceptSummary(cui="C1", name="Start"),
            target=ConceptSummary(cui="C3", name="End"),
            steps=[
                ReasoningStep(
                    step_number=1,
                    from_concept=ConceptSummary(cui="C1", name="Start"),
                    to_concept=ConceptSummary(cui="C2", name="Middle"),
                    relationship="causes",
                    confidence=0.9,
                ),
                ReasoningStep(
                    step_number=2,
                    from_concept=ConceptSummary(cui="C2", name="Middle"),
                    to_concept=ConceptSummary(cui="C3", name="End"),
                    relationship="leads_to",
                    confidence=0.8,
                ),
            ],
            total_hops=2,
            aggregate_confidence=0.72,
            explanation="Multi-hop reasoning path",
        )
        assert path.total_hops == 2
        assert len(path.steps) == 2
        assert path.aggregate_confidence == 0.72


class TestClinicalQuestionModels:
    """Test clinical QA models."""

    def test_clinical_answer_creation(self) -> None:
        """Test ClinicalAnswer model."""
        answer = ClinicalAnswer(
            answer="Metformin is the first-line treatment for Type 2 Diabetes",
            confidence=0.92,
            sources=["UMLS", "Clinical Guidelines"],
            alternatives=["Insulin therapy"],
        )
        assert "Metformin" in answer.answer
        assert answer.confidence == 0.92

    def test_clinical_question_response(self) -> None:
        """Test ClinicalQuestionResponse model."""
        response = ClinicalQuestionResponse(
            question="What is the first-line treatment for Type 2 Diabetes?",
            answer=ClinicalAnswer(
                answer="Metformin",
                confidence=0.9,
            ),
            reasoning_mode="multi_hop",
            processing_time_ms=150.5,
            timestamp=datetime.now(timezone.utc),
        )
        assert response.reasoning_mode == "multi_hop"
        assert response.processing_time_ms > 0


class TestPatientGraphModels:
    """Test patient graph models."""

    def test_patient_graph_node(self) -> None:
        """Test PatientGraphNode model."""
        node = PatientGraphNode(
            id="node_001",
            label="Diabetes Mellitus",
            type="condition",
            concept=ConceptSummary(cui="C0011849", name="Diabetes Mellitus"),
            properties={"severity": "moderate"},
        )
        assert node.type == "condition"
        assert node.concept is not None

    def test_patient_graph_edge(self) -> None:
        """Test PatientGraphEdge model."""
        edge = PatientGraphEdge(
            id="edge_001",
            source="node_001",
            target="node_002",
            type="treats",
        )
        assert edge.type == "treats"

    def test_patient_graph_creation(self) -> None:
        """Test PatientGraph model."""
        graph = PatientGraph(
            patient_id="P12345",
            nodes=[
                PatientGraphNode(id="n1", label="Condition", type="condition"),
                PatientGraphNode(id="n2", label="Medication", type="medication"),
            ],
            edges=[
                PatientGraphEdge(id="e1", source="n1", target="n2", type="treats"),
            ],
            node_count=2,
            edge_count=1,
            generated_at=datetime.now(timezone.utc),
        )
        assert graph.patient_id == "P12345"
        assert graph.node_count == 2


class TestBenchmarkModels:
    """Test benchmark models."""

    def test_benchmark_metrics(self) -> None:
        """Test BenchmarkMetrics model."""
        metrics = BenchmarkMetrics(
            accuracy=0.85,
            precision=0.88,
            recall=0.82,
            f1_score=0.85,
            processing_time_avg_ms=120.5,
        )
        assert metrics.accuracy == 0.85
        assert metrics.f1_score == 0.85

    def test_benchmark_result(self) -> None:
        """Test BenchmarkResult model."""
        now = datetime.now(timezone.utc)
        result = BenchmarkResult(
            benchmark_id="bench_001",
            benchmark_type="medagentbench",
            suite_name="clinical_qa",
            metrics=BenchmarkMetrics(
                accuracy=0.85,
                precision=0.88,
                recall=0.82,
                f1_score=0.85,
                processing_time_avg_ms=120.5,
            ),
            cases_run=100,
            cases_passed=85,
            started_at=now,
            completed_at=now,
        )
        assert result.cases_passed == 85
        assert result.benchmark_type == "medagentbench"


class TestHealthModels:
    """Test health monitoring models."""

    def test_component_health(self) -> None:
        """Test ComponentHealth model."""
        health = ComponentHealth(
            name="graph_database",
            status=HealthStatus.HEALTHY,
            latency_ms=5.5,
            last_check=datetime.now(timezone.utc),
            details={"connections": 10},
        )
        assert health.status == HealthStatus.HEALTHY
        assert health.latency_ms == 5.5

    def test_dependency_health(self) -> None:
        """Test DependencyHealth model."""
        health = DependencyHealth(
            name="neo4j",
            type="database",
            status=HealthStatus.HEALTHY,
            endpoint="bolt://localhost:7687",
            latency_ms=3.2,
        )
        assert health.type == "database"

    def test_overall_health(self) -> None:
        """Test OverallHealth model."""
        health = OverallHealth(
            status=HealthStatus.HEALTHY,
            timestamp=datetime.now(timezone.utc),
            components=[
                ComponentHealth(
                    name="graph_database",
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(timezone.utc),
                ),
            ],
            summary={"total_components": 1, "healthy": 1, "degraded": 0, "unhealthy": 0},
        )
        assert health.status == HealthStatus.HEALTHY
        assert health.summary["healthy"] == 1

    def test_health_alert(self) -> None:
        """Test HealthAlert model."""
        alert = HealthAlert(
            severity="warning",
            component="graph_embedding",
            status=HealthStatus.DEGRADED,
            message="High latency detected",
            timestamp=datetime.now(timezone.utc),
        )
        assert alert.severity == "warning"


class TestMDTModels:
    """Test MDT session models."""

    def test_mdt_consensus(self) -> None:
        """Test MDTConsensus model."""
        consensus = MDTConsensus(
            topic="Treatment Plan",
            consensus_level="majority",
            final_recommendation="Start insulin therapy",
            dissenting_views=["Consider oral medication first"],
        )
        assert consensus.consensus_level == "majority"

    def test_mdt_session_response(self) -> None:
        """Test MDTSessionResponse model."""
        response = MDTSessionResponse(
            session_id="mdt_001",
            patient_id="P12345",
            status="completed",
            agents_involved=["diagnostic", "treatment", "safety"],
            recommendations=[],
            consensus_results=[
                MDTConsensus(
                    topic="Diagnosis",
                    consensus_level="unanimous",
                    final_recommendation="Type 2 Diabetes confirmed",
                ),
            ],
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        assert len(response.agents_involved) == 3
        assert response.status == "completed"


class TestErrorModels:
    """Test error response models."""

    def test_kg_error_detail(self) -> None:
        """Test KGErrorDetail model."""
        error = KGErrorDetail(
            code="CONCEPT_NOT_FOUND",
            message="Concept not found",
            details={"cui": "C9999999"},
            path="/api/v1/kg/concept/C9999999",
            timestamp=datetime.now(timezone.utc),
        )
        assert error.code == "CONCEPT_NOT_FOUND"

    def test_kg_error_response(self) -> None:
        """Test KGErrorResponse model."""
        response = KGErrorResponse(
            error=KGErrorDetail(
                code="VALIDATION_ERROR",
                message="Invalid input",
                timestamp=datetime.now(timezone.utc),
            )
        )
        assert response.error.code == "VALIDATION_ERROR"


class TestExportModels:
    """Test graph export format models."""

    def test_d3js_graph(self) -> None:
        """Test D3JSGraph model."""
        graph = D3JSGraph(
            nodes=[{"id": "n1", "name": "Node 1"}],
            links=[{"source": "n1", "target": "n2"}],
        )
        assert len(graph.nodes) == 1
        assert len(graph.links) == 1
