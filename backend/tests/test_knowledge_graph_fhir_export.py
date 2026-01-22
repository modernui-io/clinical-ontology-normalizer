"""Tests for Knowledge Graph FHIR Export Service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.knowledge_graph_fhir_export import (
    KGEdge,
    KGNode,
    KnowledgeGraphFHIRExporter,
    KGExportResourceType,
    ReasoningChain,
    get_kg_fhir_exporter,
)


class TestKGNode:
    """Test KGNode dataclass."""

    def test_create_basic_node(self) -> None:
        """Test creating a basic KG node."""
        node = KGNode(
            id="node_1",
            cui="C0011849",
            name="Diabetes Mellitus",
        )
        assert node.id == "node_1"
        assert node.cui == "C0011849"
        assert node.name == "Diabetes Mellitus"
        assert node.semantic_type is None

    def test_create_node_with_all_fields(self) -> None:
        """Test creating a node with all fields."""
        valid_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
        node = KGNode(
            id="node_2",
            cui="C0027497",
            name="Nausea",
            semantic_type="T184",
            semantic_group="Disorders",
            vocabulary="SNOMED",
            code="422587007",
            valid_from=valid_from,
            properties={"source": "clinical_note"},
        )
        assert node.semantic_type == "T184"
        assert node.vocabulary == "SNOMED"
        assert node.valid_from == valid_from


class TestKGEdge:
    """Test KGEdge dataclass."""

    def test_create_basic_edge(self) -> None:
        """Test creating a basic KG edge."""
        edge = KGEdge(
            source_id="drug_1",
            target_id="condition_1",
            relationship_type="TREATS",
        )
        assert edge.source_id == "drug_1"
        assert edge.target_id == "condition_1"
        assert edge.relationship_type == "TREATS"
        assert edge.confidence == 1.0

    def test_create_edge_with_confidence(self) -> None:
        """Test creating an edge with confidence score."""
        edge = KGEdge(
            source_id="drug_1",
            target_id="condition_1",
            relationship_type="MAY_TREAT",
            confidence=0.85,
            source_document="Note_12345",
        )
        assert edge.confidence == 0.85
        assert edge.source_document == "Note_12345"


class TestReasoningChain:
    """Test ReasoningChain dataclass."""

    def test_create_reasoning_chain(self) -> None:
        """Test creating a reasoning chain."""
        chain = ReasoningChain(
            query="What treats diabetes?",
            conclusion="Metformin treats diabetes",
            steps=[
                {"concept": "Diabetes Mellitus", "relation": "MAY_TREAT"},
                {"concept": "Metformin", "relation": None},
            ],
            confidence=0.9,
        )
        assert chain.query == "What treats diabetes?"
        assert chain.conclusion == "Metformin treats diabetes"
        assert len(chain.steps) == 2
        assert chain.confidence == 0.9


class TestKnowledgeGraphFHIRExporter:
    """Test KnowledgeGraphFHIRExporter class."""

    def test_exporter_initialization(self) -> None:
        """Test exporter initializes correctly."""
        exporter = KnowledgeGraphFHIRExporter()
        assert exporter.base_url == "http://localhost:8000/fhir"
        assert exporter.organization == "Clinical Knowledge Graph System"

    def test_exporter_custom_config(self) -> None:
        """Test exporter with custom configuration."""
        exporter = KnowledgeGraphFHIRExporter(
            base_url="http://example.com/fhir",
            organization="Test Hospital",
        )
        assert exporter.base_url == "http://example.com/fhir"
        assert exporter.organization == "Test Hospital"

    def test_export_reasoning_chain_as_provenance(self) -> None:
        """Test exporting reasoning chain as FHIR Provenance."""
        exporter = KnowledgeGraphFHIRExporter()

        nodes = [
            KGNode(id="n1", cui="C0011849", name="Diabetes Mellitus"),
            KGNode(id="n2", cui="C0025598", name="Metformin"),
        ]
        chain = ReasoningChain(
            query="What treats diabetes?",
            conclusion="Metformin treats diabetes",
            steps=[
                {"concept": "Diabetes Mellitus", "relation": "MAY_TREAT"},
                {"concept": "Metformin", "relation": None},
            ],
            nodes=nodes,
            confidence=0.9,
        )

        resource = exporter.export_reasoning_chain_as_provenance(chain)

        assert resource.resource_type == KGExportResourceType.PROVENANCE
        assert resource.resource["resourceType"] == "Provenance"
        assert "recorded" in resource.resource
        assert "agent" in resource.resource
        assert "entity" in resource.resource

    def test_export_reasoning_chain_with_patient(self) -> None:
        """Test exporting reasoning chain with patient reference."""
        exporter = KnowledgeGraphFHIRExporter()

        chain = ReasoningChain(
            query="Treatment for patient condition",
            conclusion="Recommended treatment",
        )

        resource = exporter.export_reasoning_chain_as_provenance(
            chain=chain,
            patient_id="P12345",
        )

        assert "target" in resource.resource
        assert resource.resource["target"][0]["reference"] == "Patient/P12345"

    def test_export_causal_chain_as_evidence(self) -> None:
        """Test exporting causal relationship as FHIR Evidence."""
        exporter = KnowledgeGraphFHIRExporter()

        cause_node = KGNode(
            id="drug_1",
            cui="C0025598",
            name="Metformin",
            semantic_type="T121",
        )
        effect_node = KGNode(
            id="cond_1",
            cui="C0011849",
            name="Diabetes Mellitus",
            semantic_type="T047",
        )
        edge = KGEdge(
            source_id="drug_1",
            target_id="cond_1",
            relationship_type="TREATS",
            confidence=0.95,
        )

        resource = exporter.export_causal_chain_as_evidence(
            cause_node=cause_node,
            effect_node=effect_node,
            edge=edge,
        )

        assert resource.resource_type == KGExportResourceType.EVIDENCE
        assert resource.resource["resourceType"] == "Evidence"
        assert "variableDefinition" in resource.resource
        assert len(resource.resource["variableDefinition"]) == 2
        assert "certainty" in resource.resource

    def test_export_causal_chain_certainty_levels(self) -> None:
        """Test certainty levels based on confidence."""
        exporter = KnowledgeGraphFHIRExporter()

        cause = KGNode(id="c1", cui="C001", name="Cause")
        effect = KGNode(id="e1", cui="C002", name="Effect")

        # High confidence
        edge_high = KGEdge(
            source_id="c1", target_id="e1",
            relationship_type="CAUSES", confidence=0.95
        )
        resource_high = exporter.export_causal_chain_as_evidence(cause, effect, edge_high)
        assert resource_high.resource["certainty"][0]["rating"]["coding"][0]["code"] == "high"

        # Moderate confidence
        edge_mod = KGEdge(
            source_id="c1", target_id="e1",
            relationship_type="CAUSES", confidence=0.75
        )
        resource_mod = exporter.export_causal_chain_as_evidence(cause, effect, edge_mod)
        assert resource_mod.resource["certainty"][0]["rating"]["coding"][0]["code"] == "moderate"

        # Low confidence
        edge_low = KGEdge(
            source_id="c1", target_id="e1",
            relationship_type="CAUSES", confidence=0.5
        )
        resource_low = exporter.export_causal_chain_as_evidence(cause, effect, edge_low)
        assert resource_low.resource["certainty"][0]["rating"]["coding"][0]["code"] == "low"

    def test_export_concepts_as_library(self) -> None:
        """Test exporting concepts as FHIR Library."""
        exporter = KnowledgeGraphFHIRExporter()

        nodes = [
            KGNode(id="n1", cui="C0011849", name="Diabetes Mellitus", vocabulary="SNOMED"),
            KGNode(id="n2", cui="C0025598", name="Metformin", vocabulary="RxNorm"),
            KGNode(id="n3", cui="C0027497", name="Nausea", vocabulary="SNOMED"),
        ]

        resource = exporter.export_concepts_as_library(
            nodes=nodes,
            library_name="Test Library",
            description="Test concepts",
        )

        assert resource.resource_type == KGExportResourceType.LIBRARY
        assert resource.resource["resourceType"] == "Library"
        assert resource.resource["name"] == "TestLibrary"
        assert resource.resource["title"] == "Test Library"
        assert "content" in resource.resource
        assert "relatedArtifact" in resource.resource

    def test_export_graph_as_bundle(self) -> None:
        """Test exporting full graph as FHIR Bundle."""
        exporter = KnowledgeGraphFHIRExporter()

        nodes = [
            KGNode(id="n1", cui="C0011849", name="Diabetes Mellitus"),
            KGNode(id="n2", cui="C0025598", name="Metformin"),
        ]
        edges = [
            KGEdge(source_id="n2", target_id="n1", relationship_type="TREATS"),
        ]
        chains = [
            ReasoningChain(
                query="Treatment",
                conclusion="Metformin treats diabetes",
            ),
        ]

        bundle = exporter.export_graph_as_bundle(
            nodes=nodes,
            edges=edges,
            reasoning_chains=chains,
        )

        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert "entry" in bundle
        assert len(bundle["entry"]) > 0

    def test_export_patient_graph(self) -> None:
        """Test exporting patient-specific graph."""
        exporter = KnowledgeGraphFHIRExporter()

        nodes = [
            KGNode(id="n1", cui="C0011849", name="Diabetes Mellitus"),
        ]
        edges = []

        bundle = exporter.export_patient_graph(
            patient_id="P12345",
            nodes=nodes,
            edges=edges,
        )

        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "document"

    def test_export_temporal_snapshot(self) -> None:
        """Test exporting temporal snapshot."""
        exporter = KnowledgeGraphFHIRExporter()

        as_of = datetime(2024, 6, 15, tzinfo=timezone.utc)
        nodes = [
            KGNode(
                id="n1",
                cui="C0011849",
                name="Diabetes",
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            KGNode(
                id="n2",
                cui="C0025598",
                name="Metformin",
                valid_from=datetime(2024, 7, 1, tzinfo=timezone.utc),  # After as_of
            ),
        ]
        edges = []

        bundle = exporter.export_temporal_snapshot(
            nodes=nodes,
            edges=edges,
            as_of_time=as_of,
        )

        assert bundle["resourceType"] == "Bundle"
        assert "meta" in bundle
        assert "extension" in bundle["meta"]
        # Only the first node should be included (valid at as_of)
        assert bundle["total"] >= 1

    def test_to_json(self) -> None:
        """Test JSON conversion."""
        exporter = KnowledgeGraphFHIRExporter()

        bundle = {
            "resourceType": "Bundle",
            "id": "test-bundle",
            "type": "collection",
            "entry": [],
        }

        json_str = exporter.to_json(bundle)
        assert '"resourceType": "Bundle"' in json_str
        assert '"id": "test-bundle"' in json_str


class TestGetKGFHIRExporter:
    """Test singleton pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton exporter instance."""
        exporter1 = get_kg_fhir_exporter()
        exporter2 = get_kg_fhir_exporter()
        assert exporter1 is exporter2


class TestFHIRResourceValidity:
    """Test FHIR resource structure validity."""

    def test_provenance_has_required_fields(self) -> None:
        """Test Provenance resource has all required FHIR fields."""
        exporter = KnowledgeGraphFHIRExporter()
        chain = ReasoningChain(query="test", conclusion="test conclusion")

        resource = exporter.export_reasoning_chain_as_provenance(chain)
        r = resource.resource

        # Required fields per FHIR R4
        assert "resourceType" in r
        assert r["resourceType"] == "Provenance"
        assert "recorded" in r
        assert "agent" in r
        assert len(r["agent"]) > 0

    def test_evidence_has_required_fields(self) -> None:
        """Test Evidence resource has all required FHIR fields."""
        exporter = KnowledgeGraphFHIRExporter()
        cause = KGNode(id="c1", cui="C001", name="Cause")
        effect = KGNode(id="e1", cui="C002", name="Effect")
        edge = KGEdge(source_id="c1", target_id="e1", relationship_type="CAUSES")

        resource = exporter.export_causal_chain_as_evidence(cause, effect, edge)
        r = resource.resource

        # Required fields per FHIR R4
        assert "resourceType" in r
        assert r["resourceType"] == "Evidence"
        assert "status" in r

    def test_library_has_required_fields(self) -> None:
        """Test Library resource has all required FHIR fields."""
        exporter = KnowledgeGraphFHIRExporter()
        nodes = [KGNode(id="n1", cui="C001", name="Test Concept")]

        resource = exporter.export_concepts_as_library(nodes)
        r = resource.resource

        # Required fields per FHIR R4
        assert "resourceType" in r
        assert r["resourceType"] == "Library"
        assert "status" in r
        assert "type" in r
