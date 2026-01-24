#!/usr/bin/env python3
"""Standalone test runner for KG Data Export Service tests."""

import sys
import os
import importlib.util

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create comprehensive mocks for dependencies
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock the problematic modules before any imports
sys.modules["sentence_transformers"] = MockModule()
sys.modules["sentence_transformers"].SentenceTransformer = MockModule()
sys.modules["neo4j"] = MockModule()
sys.modules["neo4j"].GraphDatabase = MockModule()

# Now import and run tests
import traceback
from datetime import datetime
import json
import xml.etree.ElementTree as ET

# Load the data export service module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_data_export_service",
    "app/services/kg_data_export_service.py",
    submodule_search_locations=[]
)
export_module = importlib.util.module_from_spec(spec)
export_module.__package__ = "app.services"
sys.modules["app.services.kg_data_export_service"] = export_module
spec.loader.exec_module(export_module)

# Import the module under test
from app.services.kg_data_export_service import (
    KGDataExportService,
    ExportFormat,
    ExportEntityType,
    ExportConfig,
    ExportResult,
    ConceptRecord,
    RelationshipRecord,
    CSVExporter,
    JSONLinesExporter,
    RDFTurtleExporter,
    NTriplesExporter,
    GraphMLExporter,
    get_data_export_service,
)


def run_test(name, test_func):
    """Run a single test."""
    try:
        test_func()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


# Sample data fixtures
def get_sample_concepts():
    return [
        ConceptRecord(
            cui="C0001234",
            name="Diabetes Mellitus",
            semantic_type="T047",
            vocabulary="SNOMED",
            code="73211009",
            synonyms=["DM", "Diabetes"],
            created_at=datetime(2024, 1, 15)
        ),
        ConceptRecord(
            cui="C0005678",
            name="Metformin",
            semantic_type="T121",
            vocabulary="RxNorm",
            code="6809",
            created_at=datetime(2024, 2, 1)
        ),
        ConceptRecord(
            cui="C0009999",
            name="Aspirin",
            semantic_type="T121",
            vocabulary="RxNorm",
            created_at=datetime(2024, 3, 1)
        ),
    ]


def get_sample_relationships():
    return [
        RelationshipRecord(
            source_cui="C0005678",
            target_cui="C0001234",
            relationship_type="TREATS",
            source_name="Metformin",
            target_name="Diabetes Mellitus",
            weight=0.9,
            valid_from=datetime(2024, 1, 1)
        ),
    ]


# ConceptRecord tests
def test_create_concept_record():
    concept = ConceptRecord(
        cui="C0001234",
        name="Diabetes Mellitus",
        semantic_type="T047",
        vocabulary="SNOMED",
        code="73211009"
    )
    assert concept.cui == "C0001234"
    assert concept.name == "Diabetes Mellitus"


def test_concept_with_synonyms():
    concept = ConceptRecord(
        cui="C0001234",
        name="Diabetes Mellitus",
        synonyms=["DM", "Sugar Diabetes", "Diabetes"]
    )
    assert len(concept.synonyms) == 3


# RelationshipRecord tests
def test_create_relationship_record():
    rel = RelationshipRecord(
        source_cui="C0001234",
        target_cui="C0005678",
        relationship_type="TREATS",
        weight=0.85
    )
    assert rel.source_cui == "C0001234"
    assert rel.relationship_type == "TREATS"


# CSV Exporter tests
def test_csv_export_concepts():
    exporter = CSVExporter()
    concepts = get_sample_concepts()[:2]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert "cui,name,semantic_type" in result
    assert "C0001234" in result


def test_csv_export_no_header():
    exporter = CSVExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig(include_header=False)
    result = exporter.export_concepts(iter(concepts), config)
    assert "cui,name,semantic_type" not in result
    assert "C0001234" in result


def test_csv_export_include_fields():
    exporter = CSVExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig(include_fields=["cui", "name"])
    result = exporter.export_concepts(iter(concepts), config)
    header = result.strip().split("\n")[0]
    assert "cui" in header
    assert "semantic_type" not in header


def test_csv_export_relationships():
    exporter = CSVExporter()
    rels = get_sample_relationships()
    config = ExportConfig()
    result = exporter.export_relationships(iter(rels), config)
    assert "source_cui,target_cui" in result
    assert "TREATS" in result


def test_csv_content_type():
    exporter = CSVExporter()
    assert exporter.get_content_type() == "text/csv"
    assert exporter.get_file_extension() == "csv"


# JSON Lines Exporter tests
def test_jsonl_export_concepts():
    exporter = JSONLinesExporter()
    concepts = get_sample_concepts()[:2]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    for line in result.strip().split("\n"):
        record = json.loads(line)
        assert "cui" in record


def test_jsonl_filters_none_values():
    exporter = JSONLinesExporter()
    concepts = [ConceptRecord(cui="C0001234", name="Test")]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    record = json.loads(result.strip())
    assert "definition" not in record


def test_jsonl_export_relationships():
    exporter = JSONLinesExporter()
    rels = get_sample_relationships()
    config = ExportConfig()
    result = exporter.export_relationships(iter(rels), config)
    record = json.loads(result.strip())
    assert record["source_cui"] == "C0005678"


def test_jsonl_content_type():
    exporter = JSONLinesExporter()
    assert exporter.get_content_type() == "application/x-ndjson"
    assert exporter.get_file_extension() == "jsonl"


# RDF Turtle Exporter tests
def test_turtle_export_concepts():
    exporter = RDFTurtleExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert "@prefix" in result
    assert "skos:Concept" in result
    assert "C0001234" in result


def test_turtle_has_prefixes():
    exporter = RDFTurtleExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert "@prefix rdf:" in result
    assert "@prefix skos:" in result


def test_turtle_export_relationships():
    exporter = RDFTurtleExporter()
    rels = get_sample_relationships()
    config = ExportConfig()
    result = exporter.export_relationships(iter(rels), config)
    assert ":concept_C0005678" in result
    assert ":treats" in result


def test_turtle_escapes_special_chars():
    exporter = RDFTurtleExporter()
    concepts = [ConceptRecord(cui="C1", name='Test "Quoted"', definition="Line1\nLine2")]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert '\\"' in result
    assert "\\n" in result


def test_turtle_content_type():
    exporter = RDFTurtleExporter()
    assert exporter.get_content_type() == "text/turtle"
    assert exporter.get_file_extension() == "ttl"


# N-Triples Exporter tests
def test_ntriples_export_concepts():
    exporter = NTriplesExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert "<http://example.org/kg/concept_C0001234>" in result


def test_ntriples_export_relationships():
    exporter = NTriplesExporter()
    rels = get_sample_relationships()
    config = ExportConfig()
    result = exporter.export_relationships(iter(rels), config)
    assert "concept_C0005678" in result
    assert "treats" in result


def test_ntriples_lines_end_with_period():
    exporter = NTriplesExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    for line in result.strip().split("\n"):
        assert line.strip().endswith(".")


def test_ntriples_content_type():
    exporter = NTriplesExporter()
    assert exporter.get_content_type() == "application/n-triples"
    assert exporter.get_file_extension() == "nt"


# GraphML Exporter tests
def test_graphml_export_concepts():
    exporter = GraphMLExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    root = ET.fromstring(result)
    assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"


def test_graphml_includes_node():
    exporter = GraphMLExporter()
    concepts = get_sample_concepts()[:1]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert '<node id="C0001234">' in result


def test_graphml_export_relationships():
    exporter = GraphMLExporter()
    rels = get_sample_relationships()
    config = ExportConfig()
    result = exporter.export_relationships(iter(rels), config)
    root = ET.fromstring(result)
    assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"


def test_graphml_includes_edges():
    exporter = GraphMLExporter()
    rels = get_sample_relationships()
    config = ExportConfig()
    result = exporter.export_relationships(iter(rels), config)
    assert 'source="C0005678"' in result
    assert 'target="C0001234"' in result


def test_graphml_escapes_xml():
    exporter = GraphMLExporter()
    concepts = [ConceptRecord(cui="C1", name='Test <Name> & "Quoted"')]
    config = ExportConfig()
    result = exporter.export_concepts(iter(concepts), config)
    assert "&lt;" in result
    assert "&amp;" in result


def test_graphml_content_type():
    exporter = GraphMLExporter()
    assert exporter.get_content_type() == "application/graphml+xml"
    assert exporter.get_file_extension() == "graphml"


# KGDataExportService tests
def test_service_export_csv():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(format=ExportFormat.CSV)
    result = service.export_concepts(concepts, config)
    assert result.format == ExportFormat.CSV
    assert result.record_count == 3
    assert result.filename == "concepts.csv"


def test_service_export_jsonl():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(format=ExportFormat.JSON_LINES)
    result = service.export_concepts(concepts, config)
    assert result.format == ExportFormat.JSON_LINES
    assert result.filename == "concepts.jsonl"


def test_service_export_turtle():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(format=ExportFormat.RDF_TURTLE)
    result = service.export_concepts(concepts, config)
    assert result.format == ExportFormat.RDF_TURTLE
    assert result.filename == "concepts.ttl"


def test_service_export_ntriples():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(format=ExportFormat.RDF_NTRIPLES)
    result = service.export_concepts(concepts, config)
    assert result.format == ExportFormat.RDF_NTRIPLES
    assert result.filename == "concepts.nt"


def test_service_export_graphml():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(format=ExportFormat.GRAPHML)
    result = service.export_concepts(concepts, config)
    assert result.format == ExportFormat.GRAPHML
    assert result.filename == "concepts.graphml"


def test_service_filter_by_cui():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(concept_cuis=["C0001234"])
    result = service.export_concepts(concepts, config)
    assert result.record_count == 1


def test_service_filter_by_semantic_type():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(semantic_types=["T121"])
    result = service.export_concepts(concepts, config)
    assert result.record_count == 2


def test_service_filter_by_vocabulary():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(vocabularies=["SNOMED"])
    result = service.export_concepts(concepts, config)
    assert result.record_count == 1


def test_service_filter_by_date():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(
        date_from=datetime(2024, 1, 1),
        date_to=datetime(2024, 2, 15)
    )
    result = service.export_concepts(concepts, config)
    assert result.record_count == 2


def test_service_with_offset():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(offset=1)
    result = service.export_concepts(concepts, config)
    assert result.record_count == 2


def test_service_with_limit():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(limit=2)
    result = service.export_concepts(concepts, config)
    assert result.record_count == 2


def test_service_with_offset_and_limit():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(offset=1, limit=1)
    result = service.export_concepts(concepts, config)
    assert result.record_count == 1


def test_service_export_relationships():
    service = KGDataExportService()
    rels = get_sample_relationships()
    config = ExportConfig(format=ExportFormat.CSV)
    result = service.export_relationships(rels, config)
    assert result.entity_type == ExportEntityType.RELATIONSHIPS
    assert result.record_count == 1


def test_service_get_supported_formats():
    service = KGDataExportService()
    formats = service.get_supported_formats()
    assert len(formats) >= 5
    format_values = [f["format"] for f in formats]
    assert "csv" in format_values
    assert "jsonl" in format_values


def test_service_get_content_type():
    service = KGDataExportService()
    assert service.get_content_type(ExportFormat.CSV) == "text/csv"
    assert service.get_content_type(ExportFormat.JSON_LINES) == "application/x-ndjson"


def test_service_unsupported_format():
    service = KGDataExportService()
    concepts = get_sample_concepts()
    config = ExportConfig(format=ExportFormat.JSON)
    try:
        service.export_concepts(concepts, config)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported" in str(e)


# ExportConfig tests
def test_default_config():
    config = ExportConfig()
    assert config.format == ExportFormat.CSV
    assert config.offset == 0
    assert config.limit is None


def test_config_with_options():
    config = ExportConfig(
        format=ExportFormat.JSON_LINES,
        include_fields=["cui", "name"],
        limit=100
    )
    assert config.format == ExportFormat.JSON_LINES
    assert config.include_fields == ["cui", "name"]


# Singleton test
def test_singleton():
    service1 = get_data_export_service()
    service2 = get_data_export_service()
    assert service1 is service2


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Data Export Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # Record tests
        ("create_concept_record", test_create_concept_record),
        ("concept_with_synonyms", test_concept_with_synonyms),
        ("create_relationship_record", test_create_relationship_record),

        # CSV Exporter tests
        ("csv_export_concepts", test_csv_export_concepts),
        ("csv_export_no_header", test_csv_export_no_header),
        ("csv_export_include_fields", test_csv_export_include_fields),
        ("csv_export_relationships", test_csv_export_relationships),
        ("csv_content_type", test_csv_content_type),

        # JSON Lines Exporter tests
        ("jsonl_export_concepts", test_jsonl_export_concepts),
        ("jsonl_filters_none_values", test_jsonl_filters_none_values),
        ("jsonl_export_relationships", test_jsonl_export_relationships),
        ("jsonl_content_type", test_jsonl_content_type),

        # RDF Turtle Exporter tests
        ("turtle_export_concepts", test_turtle_export_concepts),
        ("turtle_has_prefixes", test_turtle_has_prefixes),
        ("turtle_export_relationships", test_turtle_export_relationships),
        ("turtle_escapes_special_chars", test_turtle_escapes_special_chars),
        ("turtle_content_type", test_turtle_content_type),

        # N-Triples Exporter tests
        ("ntriples_export_concepts", test_ntriples_export_concepts),
        ("ntriples_export_relationships", test_ntriples_export_relationships),
        ("ntriples_lines_end_with_period", test_ntriples_lines_end_with_period),
        ("ntriples_content_type", test_ntriples_content_type),

        # GraphML Exporter tests
        ("graphml_export_concepts", test_graphml_export_concepts),
        ("graphml_includes_node", test_graphml_includes_node),
        ("graphml_export_relationships", test_graphml_export_relationships),
        ("graphml_includes_edges", test_graphml_includes_edges),
        ("graphml_escapes_xml", test_graphml_escapes_xml),
        ("graphml_content_type", test_graphml_content_type),

        # Service tests
        ("service_export_csv", test_service_export_csv),
        ("service_export_jsonl", test_service_export_jsonl),
        ("service_export_turtle", test_service_export_turtle),
        ("service_export_ntriples", test_service_export_ntriples),
        ("service_export_graphml", test_service_export_graphml),
        ("service_filter_by_cui", test_service_filter_by_cui),
        ("service_filter_by_semantic_type", test_service_filter_by_semantic_type),
        ("service_filter_by_vocabulary", test_service_filter_by_vocabulary),
        ("service_filter_by_date", test_service_filter_by_date),
        ("service_with_offset", test_service_with_offset),
        ("service_with_limit", test_service_with_limit),
        ("service_with_offset_and_limit", test_service_with_offset_and_limit),
        ("service_export_relationships", test_service_export_relationships),
        ("service_get_supported_formats", test_service_get_supported_formats),
        ("service_get_content_type", test_service_get_content_type),
        ("service_unsupported_format", test_service_unsupported_format),

        # Config tests
        ("default_config", test_default_config),
        ("config_with_options", test_config_with_options),

        # Singleton test
        ("singleton", test_singleton),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        if run_test(name, test):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
