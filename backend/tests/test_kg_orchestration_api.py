"""Tests for Knowledge Graph Orchestration API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestOrchestrationStatus:
    """Test orchestration status endpoints."""

    def test_get_orchestration_status(self) -> None:
        """Test getting orchestration status."""
        response = client.get("/api/v1/kg/orchestration/status")
        assert response.status_code == 200

        status = response.json()
        assert "overall_status" in status
        assert status["overall_status"] in ["healthy", "degraded", "unhealthy"]
        assert "services" in status
        assert "total_services" in status
        assert "healthy_services" in status
        assert isinstance(status["services"], list)

    def test_status_has_expected_services(self) -> None:
        """Test that status includes expected services."""
        response = client.get("/api/v1/kg/orchestration/status")
        assert response.status_code == 200

        status = response.json()
        service_names = {s["name"] for s in status["services"]}

        # Check for key services
        expected_services = {
            "graph_database",
            "graph_analytics",
            "causal_reasoning",
            "provenance",
            "multi_agent_orchestrator",
            "kg_visualization",
            "medagentbench",
            "drknows_benchmark",
        }
        assert expected_services.issubset(service_names)


class TestUnifiedQuery:
    """Test unified query endpoints."""

    def test_concept_lookup_query(self) -> None:
        """Test concept lookup query."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "concept_lookup",
                "query": "asthma",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["query_type"] == "concept_lookup"
        assert result["query"] == "asthma"
        assert "results" in result
        assert "metadata" in result
        assert "executed_at" in result

    def test_relationship_search_query(self) -> None:
        """Test relationship search query."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "relationship_search",
                "query": "asthma treatment",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["query_type"] == "relationship_search"
        assert "results" in result

    def test_path_finding_query(self) -> None:
        """Test path finding query."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "path_finding",
                "query": "diabetes to insulin",
                "max_hops": 3,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["query_type"] == "path_finding"
        assert "metadata" in result
        assert result["metadata"]["max_hops"] == 3

    def test_similarity_search_query(self) -> None:
        """Test similarity search query."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "similarity_search",
                "query": "respiratory disease",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["query_type"] == "similarity_search"
        assert "results" in result

    def test_temporal_query(self) -> None:
        """Test temporal query."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "temporal_query",
                "query": "patient condition history",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["query_type"] == "temporal_query"

    def test_causal_chain_query(self) -> None:
        """Test causal chain query."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "causal_chain",
                "query": "smoking causes lung cancer",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["query_type"] == "causal_chain"
        assert "results" in result

    def test_query_with_provenance(self) -> None:
        """Test query with provenance enabled."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "concept_lookup",
                "query": "diabetes",
                "include_provenance": True,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "provenance" in result
        assert "source" in result["provenance"]

    def test_query_with_semantic_types(self) -> None:
        """Test query with semantic type filter."""
        response = client.post(
            "/api/v1/kg/orchestration/query",
            json={
                "query_type": "concept_lookup",
                "query": "medications",
                "semantic_types": ["Pharmacologic Substance"],
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "results" in result


class TestClinicalQuestionAnswering:
    """Test clinical question answering endpoint."""

    def test_simple_reasoning_mode(self) -> None:
        """Test simple reasoning mode."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "What is the first-line treatment for hypertension?",
                "reasoning_mode": "simple",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["reasoning_mode"] == "simple"
        assert "answer" in result
        assert "confidence" in result
        assert result["confidence"] > 0

    def test_multi_hop_reasoning_mode(self) -> None:
        """Test multi-hop reasoning mode."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "How does metformin work in diabetes treatment?",
                "reasoning_mode": "multi_hop",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["reasoning_mode"] == "multi_hop"
        assert "reasoning_trace" in result
        assert len(result["reasoning_trace"]) > 0

    def test_causal_reasoning_mode(self) -> None:
        """Test causal reasoning mode."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "What are the risk factors for heart disease?",
                "reasoning_mode": "causal",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["reasoning_mode"] == "causal"

    def test_multi_agent_reasoning_mode(self) -> None:
        """Test multi-agent reasoning mode."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "Should this patient receive anticoagulation?",
                "reasoning_mode": "multi_agent",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["reasoning_mode"] == "multi_agent"
        assert "agent_contributions" in result

    def test_include_evidence(self) -> None:
        """Test including evidence in response."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "What is the treatment for COPD?",
                "include_evidence": True,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "evidence" in result
        assert len(result["evidence"]) > 0

    def test_include_alternatives(self) -> None:
        """Test including alternatives in response."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "What medications can treat anxiety?",
                "include_alternatives": True,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "alternatives" in result

    def test_with_patient_context(self) -> None:
        """Test with patient context."""
        response = client.post(
            "/api/v1/kg/orchestration/clinical-question",
            json={
                "question": "What medication adjustments are needed?",
                "patient_context": {
                    "age": 65,
                    "kidney_function": "reduced",
                    "allergies": ["penicillin"],
                },
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "personalization" in result
        assert result["personalization"]["applied"] is True


class TestReasoningPaths:
    """Test reasoning path analysis endpoint."""

    def test_find_reasoning_paths(self) -> None:
        """Test finding reasoning paths."""
        response = client.post(
            "/api/v1/kg/orchestration/reasoning-path",
            json={
                "source_concept": "Diabetes",
                "target_concept": "Insulin",
                "max_hops": 5,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["source_concept"] == "Diabetes"
        assert result["target_concept"] == "Insulin"
        assert "paths" in result
        assert "metadata" in result

    def test_paths_without_target(self) -> None:
        """Test finding paths without specific target."""
        response = client.post(
            "/api/v1/kg/orchestration/reasoning-path",
            json={
                "source_concept": "Asthma",
                "max_hops": 3,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "paths" in result

    def test_paths_with_relationship_filter(self) -> None:
        """Test paths with relationship type filter."""
        response = client.post(
            "/api/v1/kg/orchestration/reasoning-path",
            json={
                "source_concept": "Cancer",
                "relationship_types": ["may_treat", "causes"],
                "max_hops": 4,
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "paths" in result


class TestPatientEndpoints:
    """Test patient-centric endpoints."""

    def test_get_patient_graph(self) -> None:
        """Test getting patient knowledge graph."""
        response = client.get(
            "/api/v1/kg/orchestration/patient/P12345/graph?depth=2"
        )
        assert response.status_code == 200

        result = response.json()
        assert result["patient_id"] == "P12345"
        assert result["depth"] == 2
        assert "graph" in result
        assert "nodes" in result["graph"]
        assert "edges" in result["graph"]
        assert "summary" in result

    def test_get_patient_timeline(self) -> None:
        """Test getting patient timeline."""
        response = client.get(
            "/api/v1/kg/orchestration/patient/P12345/timeline"
        )
        assert response.status_code == 200

        result = response.json()
        assert result["patient_id"] == "P12345"
        assert "frames" in result
        assert "summary" in result


class TestExportEndpoints:
    """Test export endpoints."""

    def test_export_d3js(self) -> None:
        """Test D3.js export."""
        response = client.post(
            "/api/v1/kg/orchestration/export",
            json={
                "patient_id": "P12345",
                "format": "d3js",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["format"] == "d3js"
        assert "data" in result
        assert "metadata" in result

    def test_export_cytoscape(self) -> None:
        """Test Cytoscape.js export."""
        response = client.post(
            "/api/v1/kg/orchestration/export",
            json={
                "format": "cytoscape",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["format"] == "cytoscape"

    def test_export_visjs(self) -> None:
        """Test vis.js export."""
        response = client.post(
            "/api/v1/kg/orchestration/export",
            json={
                "format": "visjs",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert result["format"] == "visjs"


class TestMDTSession:
    """Test MDT session endpoint."""

    def test_start_mdt_session(self) -> None:
        """Test starting MDT session."""
        response = client.post(
            "/api/v1/kg/orchestration/mdt-session",
            params={
                "case_description": "65-year-old male with chest pain and shortness of breath",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "session_id" in result
        assert "consensus" in result
        assert "agent_recommendations" in result
        assert "prioritized_actions" in result

    def test_mdt_session_with_patient(self) -> None:
        """Test MDT session with patient context."""
        response = client.post(
            "/api/v1/kg/orchestration/mdt-session",
            params={
                "case_description": "Patient with new diabetes diagnosis",
                "patient_id": "P12345",
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "session_id" in result


class TestUtilityEndpoints:
    """Test utility endpoints."""

    def test_list_semantic_groups(self) -> None:
        """Test listing semantic groups."""
        response = client.get("/api/v1/kg/orchestration/semantic-groups")
        assert response.status_code == 200

        groups = response.json()
        assert isinstance(groups, dict)
        assert "DISO" in groups  # Disorders
        assert "CHEM" in groups  # Chemicals
        assert len(groups) == 15  # 15 UMLS semantic groups

    def test_list_relationship_types(self) -> None:
        """Test listing relationship types."""
        response = client.get("/api/v1/kg/orchestration/relationship-types")
        assert response.status_code == 200

        types = response.json()
        assert isinstance(types, list)
        assert len(types) > 0

        # Check structure
        rel_type = types[0]
        assert "type" in rel_type
        assert "description" in rel_type

        # Check for key relationships
        type_names = {t["type"] for t in types}
        assert "IS_A" in type_names
        assert "may_treat" in type_names
        assert "causes" in type_names
