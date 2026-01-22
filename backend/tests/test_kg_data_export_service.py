"""Tests for KG Data Export Service."""

import pytest
from datetime import datetime
import json
import xml.etree.ElementTree as ET

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


class TestConceptRecord:
    """Tests for ConceptRecord."""

    def test_create_concept_record(self):
        """Create a concept record."""
        concept = ConceptRecord(
            cui="C0001234",
            name="Diabetes Mellitus",
            semantic_type="T047",
            vocabulary="SNOMED",
            code="73211009"
        )

        assert concept.cui == "C0001234"
        assert concept.name == "Diabetes Mellitus"
        assert concept.semantic_type == "T047"
        assert concept.vocabulary == "SNOMED"

    def test_concept_with_synonyms(self):
        """Create concept with synonyms."""
        concept = ConceptRecord(
            cui="C0001234",
            name="Diabetes Mellitus",
            synonyms=["DM", "Sugar Diabetes", "Diabetes"]
        )

        assert len(concept.synonyms) == 3
        assert "DM" in concept.synonyms

    def test_concept_with_attributes(self):
        """Create concept with custom attributes."""
        concept = ConceptRecord(
            cui="C0001234",
            name="Diabetes Mellitus",
            attributes={"icd10": "E11.9", "custom": "value"}
        )

        assert concept.attributes["icd10"] == "E11.9"


class TestRelationshipRecord:
    """Tests for RelationshipRecord."""

    def test_create_relationship_record(self):
        """Create a relationship record."""
        rel = RelationshipRecord(
            source_cui="C0001234",
            target_cui="C0005678",
            relationship_type="TREATS",
            weight=0.85
        )

        assert rel.source_cui == "C0001234"
        assert rel.target_cui == "C0005678"
        assert rel.relationship_type == "TREATS"
        assert rel.weight == 0.85

    def test_relationship_with_temporal(self):
        """Create relationship with temporal data."""
        rel = RelationshipRecord(
            source_cui="C0001234",
            target_cui="C0005678",
            relationship_type="TREATS",
            valid_from=datetime(2024, 1, 1),
            valid_to=datetime(2024, 12, 31)
        )

        assert rel.valid_from == datetime(2024, 1, 1)
        assert rel.valid_to == datetime(2024, 12, 31)


class TestCSVExporter:
    """Tests for CSV exporter."""

    @pytest.fixture
    def exporter(self):
        return CSVExporter()

    @pytest.fixture
    def sample_concepts(self):
        return [
            ConceptRecord(
                cui="C0001234",
                name="Diabetes Mellitus",
                semantic_type="T047",
                vocabulary="SNOMED",
                code="73211009"
            ),
            ConceptRecord(
                cui="C0005678",
                name="Metformin",
                semantic_type="T121",
                vocabulary="RxNorm",
                code="6809"
            ),
        ]

    @pytest.fixture
    def sample_relationships(self):
        return [
            RelationshipRecord(
                source_cui="C0005678",
                target_cui="C0001234",
                relationship_type="TREATS",
                source_name="Metformin",
                target_name="Diabetes Mellitus",
                weight=0.9
            ),
        ]

    def test_export_concepts(self, exporter, sample_concepts):
        """Export concepts to CSV."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "cui,name,semantic_type" in result
        assert "C0001234" in result
        assert "Diabetes Mellitus" in result

    def test_export_concepts_no_header(self, exporter, sample_concepts):
        """Export concepts without header."""
        config = ExportConfig(include_header=False)
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "cui,name,semantic_type" not in result
        assert "C0001234" in result

    def test_export_concepts_with_include_fields(self, exporter, sample_concepts):
        """Export concepts with field selection."""
        config = ExportConfig(include_fields=["cui", "name"])
        result = exporter.export_concepts(iter(sample_concepts), config)

        lines = result.strip().split("\n")
        header = lines[0]
        assert "cui" in header
        assert "name" in header
        assert "semantic_type" not in header

    def test_export_concepts_with_exclude_fields(self, exporter, sample_concepts):
        """Export concepts excluding fields."""
        config = ExportConfig(exclude_fields=["definition", "synonyms"])
        result = exporter.export_concepts(iter(sample_concepts), config)

        lines = result.strip().split("\n")
        header = lines[0]
        assert "definition" not in header
        assert "synonyms" not in header

    def test_export_concepts_custom_delimiter(self, exporter, sample_concepts):
        """Export concepts with custom delimiter."""
        config = ExportConfig(csv_delimiter="\t")
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "\t" in result

    def test_export_relationships(self, exporter, sample_relationships):
        """Export relationships to CSV."""
        config = ExportConfig()
        result = exporter.export_relationships(iter(sample_relationships), config)

        assert "source_cui,target_cui" in result
        assert "C0005678" in result
        assert "TREATS" in result

    def test_get_content_type(self, exporter):
        """Get CSV content type."""
        assert exporter.get_content_type() == "text/csv"

    def test_get_file_extension(self, exporter):
        """Get CSV file extension."""
        assert exporter.get_file_extension() == "csv"


class TestJSONLinesExporter:
    """Tests for JSON Lines exporter."""

    @pytest.fixture
    def exporter(self):
        return JSONLinesExporter()

    @pytest.fixture
    def sample_concepts(self):
        return [
            ConceptRecord(
                cui="C0001234",
                name="Diabetes Mellitus",
                semantic_type="T047",
                synonyms=["DM", "Diabetes"]
            ),
        ]

    @pytest.fixture
    def sample_relationships(self):
        return [
            RelationshipRecord(
                source_cui="C0005678",
                target_cui="C0001234",
                relationship_type="TREATS",
                weight=0.9
            ),
        ]

    def test_export_concepts(self, exporter, sample_concepts):
        """Export concepts to JSON Lines."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        # Each line should be valid JSON
        for line in result.strip().split("\n"):
            record = json.loads(line)
            assert "cui" in record
            assert "name" in record

    def test_export_concepts_filters_none_values(self, exporter, sample_concepts):
        """JSON Lines filters None values."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        record = json.loads(result.strip())
        assert "definition" not in record  # None values are excluded

    def test_export_relationships(self, exporter, sample_relationships):
        """Export relationships to JSON Lines."""
        config = ExportConfig()
        result = exporter.export_relationships(iter(sample_relationships), config)

        record = json.loads(result.strip())
        assert record["source_cui"] == "C0005678"
        assert record["relationship_type"] == "TREATS"

    def test_get_content_type(self, exporter):
        """Get JSON Lines content type."""
        assert exporter.get_content_type() == "application/x-ndjson"

    def test_get_file_extension(self, exporter):
        """Get JSON Lines file extension."""
        assert exporter.get_file_extension() == "jsonl"


class TestRDFTurtleExporter:
    """Tests for RDF Turtle exporter."""

    @pytest.fixture
    def exporter(self):
        return RDFTurtleExporter()

    @pytest.fixture
    def sample_concepts(self):
        return [
            ConceptRecord(
                cui="C0001234",
                name="Diabetes Mellitus",
                semantic_type="T047",
                definition="A chronic disease of sugar metabolism",
                synonyms=["DM", "Diabetes"]
            ),
        ]

    @pytest.fixture
    def sample_relationships(self):
        return [
            RelationshipRecord(
                source_cui="C0005678",
                target_cui="C0001234",
                relationship_type="TREATS",
                weight=0.9
            ),
        ]

    def test_export_concepts(self, exporter, sample_concepts):
        """Export concepts to Turtle."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "@prefix" in result
        assert "skos:Concept" in result
        assert "C0001234" in result
        assert "Diabetes Mellitus" in result

    def test_export_concepts_has_prefixes(self, exporter, sample_concepts):
        """Turtle export includes prefixes."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "@prefix rdf:" in result
        assert "@prefix rdfs:" in result
        assert "@prefix skos:" in result

    def test_export_concepts_includes_synonyms(self, exporter, sample_concepts):
        """Turtle export includes synonyms as altLabels."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "skos:altLabel" in result
        assert '"DM"' in result

    def test_export_relationships(self, exporter, sample_relationships):
        """Export relationships to Turtle."""
        config = ExportConfig()
        result = exporter.export_relationships(iter(sample_relationships), config)

        assert ":concept_C0005678" in result
        assert ":concept_C0001234" in result
        assert ":treats" in result

    def test_escapes_special_characters(self, exporter):
        """Turtle export escapes special characters."""
        concepts = [
            ConceptRecord(
                cui="C0001234",
                name='Test "Quoted" Name',
                definition="Line1\nLine2"
            )
        ]
        config = ExportConfig()
        result = exporter.export_concepts(iter(concepts), config)

        assert '\\"' in result
        assert "\\n" in result

    def test_get_content_type(self, exporter):
        """Get Turtle content type."""
        assert exporter.get_content_type() == "text/turtle"

    def test_get_file_extension(self, exporter):
        """Get Turtle file extension."""
        assert exporter.get_file_extension() == "ttl"


class TestNTriplesExporter:
    """Tests for N-Triples exporter."""

    @pytest.fixture
    def exporter(self):
        return NTriplesExporter()

    @pytest.fixture
    def sample_concepts(self):
        return [
            ConceptRecord(
                cui="C0001234",
                name="Diabetes Mellitus",
                semantic_type="T047"
            ),
        ]

    @pytest.fixture
    def sample_relationships(self):
        return [
            RelationshipRecord(
                source_cui="C0005678",
                target_cui="C0001234",
                relationship_type="TREATS"
            ),
        ]

    def test_export_concepts(self, exporter, sample_concepts):
        """Export concepts to N-Triples."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert "<http://example.org/kg/concept_C0001234>" in result
        assert "skos#Concept" in result

    def test_export_relationships(self, exporter, sample_relationships):
        """Export relationships to N-Triples."""
        config = ExportConfig()
        result = exporter.export_relationships(iter(sample_relationships), config)

        assert "concept_C0005678" in result
        assert "concept_C0001234" in result
        assert "treats" in result

    def test_each_line_ends_with_period(self, exporter, sample_concepts):
        """N-Triples lines end with period."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        for line in result.strip().split("\n"):
            assert line.strip().endswith(".")

    def test_get_content_type(self, exporter):
        """Get N-Triples content type."""
        assert exporter.get_content_type() == "application/n-triples"

    def test_get_file_extension(self, exporter):
        """Get N-Triples file extension."""
        assert exporter.get_file_extension() == "nt"


class TestGraphMLExporter:
    """Tests for GraphML exporter."""

    @pytest.fixture
    def exporter(self):
        return GraphMLExporter()

    @pytest.fixture
    def sample_concepts(self):
        return [
            ConceptRecord(
                cui="C0001234",
                name="Diabetes Mellitus",
                semantic_type="T047",
                vocabulary="SNOMED"
            ),
        ]

    @pytest.fixture
    def sample_relationships(self):
        return [
            RelationshipRecord(
                source_cui="C0005678",
                target_cui="C0001234",
                relationship_type="TREATS",
                source_name="Metformin",
                target_name="Diabetes Mellitus",
                weight=0.9
            ),
        ]

    def test_export_concepts(self, exporter, sample_concepts):
        """Export concepts to GraphML."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        # Should be valid XML
        root = ET.fromstring(result)
        assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"

    def test_export_concepts_includes_node(self, exporter, sample_concepts):
        """GraphML export includes node elements."""
        config = ExportConfig()
        result = exporter.export_concepts(iter(sample_concepts), config)

        assert '<node id="C0001234">' in result
        assert "Diabetes Mellitus" in result

    def test_export_relationships(self, exporter, sample_relationships):
        """Export relationships to GraphML."""
        config = ExportConfig()
        result = exporter.export_relationships(iter(sample_relationships), config)

        # Should be valid XML
        root = ET.fromstring(result)
        assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"

    def test_export_relationships_includes_edges(self, exporter, sample_relationships):
        """GraphML export includes edge elements."""
        config = ExportConfig()
        result = exporter.export_relationships(iter(sample_relationships), config)

        assert 'source="C0005678"' in result
        assert 'target="C0001234"' in result
        assert "TREATS" in result

    def test_escapes_xml_characters(self, exporter):
        """GraphML export escapes XML characters."""
        concepts = [
            ConceptRecord(
                cui="C0001234",
                name="Test <Name> & \"Quoted\""
            )
        ]
        config = ExportConfig()
        result = exporter.export_concepts(iter(concepts), config)

        assert "&lt;" in result
        assert "&amp;" in result
        assert "&quot;" in result

    def test_get_content_type(self, exporter):
        """Get GraphML content type."""
        assert exporter.get_content_type() == "application/graphml+xml"

    def test_get_file_extension(self, exporter):
        """Get GraphML file extension."""
        assert exporter.get_file_extension() == "graphml"


class TestKGDataExportService:
    """Tests for KGDataExportService."""

    @pytest.fixture
    def service(self):
        return KGDataExportService()

    @pytest.fixture
    def sample_concepts(self):
        return [
            ConceptRecord(
                cui="C0001234",
                name="Diabetes Mellitus",
                semantic_type="T047",
                vocabulary="SNOMED",
                created_at=datetime(2024, 1, 15)
            ),
            ConceptRecord(
                cui="C0005678",
                name="Metformin",
                semantic_type="T121",
                vocabulary="RxNorm",
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

    @pytest.fixture
    def sample_relationships(self):
        return [
            RelationshipRecord(
                source_cui="C0005678",
                target_cui="C0001234",
                relationship_type="TREATS",
                valid_from=datetime(2024, 1, 1)
            ),
        ]

    def test_export_concepts_csv(self, service, sample_concepts):
        """Export concepts to CSV."""
        config = ExportConfig(format=ExportFormat.CSV)
        result = service.export_concepts(sample_concepts, config)

        assert result.format == ExportFormat.CSV
        assert result.entity_type == ExportEntityType.CONCEPTS
        assert result.record_count == 3
        assert result.byte_size > 0
        assert result.filename == "concepts.csv"

    def test_export_concepts_jsonl(self, service, sample_concepts):
        """Export concepts to JSON Lines."""
        config = ExportConfig(format=ExportFormat.JSON_LINES)
        result = service.export_concepts(sample_concepts, config)

        assert result.format == ExportFormat.JSON_LINES
        assert result.filename == "concepts.jsonl"

    def test_export_concepts_turtle(self, service, sample_concepts):
        """Export concepts to Turtle."""
        config = ExportConfig(format=ExportFormat.RDF_TURTLE)
        result = service.export_concepts(sample_concepts, config)

        assert result.format == ExportFormat.RDF_TURTLE
        assert result.filename == "concepts.ttl"

    def test_export_concepts_ntriples(self, service, sample_concepts):
        """Export concepts to N-Triples."""
        config = ExportConfig(format=ExportFormat.RDF_NTRIPLES)
        result = service.export_concepts(sample_concepts, config)

        assert result.format == ExportFormat.RDF_NTRIPLES
        assert result.filename == "concepts.nt"

    def test_export_concepts_graphml(self, service, sample_concepts):
        """Export concepts to GraphML."""
        config = ExportConfig(format=ExportFormat.GRAPHML)
        result = service.export_concepts(sample_concepts, config)

        assert result.format == ExportFormat.GRAPHML
        assert result.filename == "concepts.graphml"

    def test_export_concepts_filter_by_cui(self, service, sample_concepts):
        """Export concepts filtered by CUI."""
        config = ExportConfig(concept_cuis=["C0001234"])
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 1
        assert "C0001234" in result.content

    def test_export_concepts_filter_by_semantic_type(self, service, sample_concepts):
        """Export concepts filtered by semantic type."""
        config = ExportConfig(semantic_types=["T121"])
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 2

    def test_export_concepts_filter_by_vocabulary(self, service, sample_concepts):
        """Export concepts filtered by vocabulary."""
        config = ExportConfig(vocabularies=["SNOMED"])
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 1

    def test_export_concepts_filter_by_date(self, service, sample_concepts):
        """Export concepts filtered by date."""
        config = ExportConfig(
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 2, 15)
        )
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 2

    def test_export_concepts_with_offset(self, service, sample_concepts):
        """Export concepts with offset."""
        config = ExportConfig(offset=1)
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 2

    def test_export_concepts_with_limit(self, service, sample_concepts):
        """Export concepts with limit."""
        config = ExportConfig(limit=2)
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 2

    def test_export_concepts_with_offset_and_limit(self, service, sample_concepts):
        """Export concepts with offset and limit."""
        config = ExportConfig(offset=1, limit=1)
        result = service.export_concepts(sample_concepts, config)

        assert result.record_count == 1

    def test_export_relationships(self, service, sample_relationships):
        """Export relationships."""
        config = ExportConfig(format=ExportFormat.CSV)
        result = service.export_relationships(sample_relationships, config)

        assert result.entity_type == ExportEntityType.RELATIONSHIPS
        assert result.record_count == 1
        assert result.filename == "relationships.csv"

    def test_export_relationships_filter_by_cui(self, service, sample_relationships):
        """Export relationships filtered by CUI."""
        config = ExportConfig(concept_cuis=["C0005678"])
        result = service.export_relationships(sample_relationships, config)

        assert result.record_count == 1

    def test_get_supported_formats(self, service):
        """Get list of supported formats."""
        formats = service.get_supported_formats()

        assert len(formats) >= 5
        format_values = [f["format"] for f in formats]
        assert "csv" in format_values
        assert "jsonl" in format_values
        assert "turtle" in format_values

    def test_get_content_type(self, service):
        """Get content type for format."""
        assert service.get_content_type(ExportFormat.CSV) == "text/csv"
        assert service.get_content_type(ExportFormat.JSON_LINES) == "application/x-ndjson"
        assert service.get_content_type(ExportFormat.RDF_TURTLE) == "text/turtle"

    def test_get_file_extension(self, service):
        """Get file extension for format."""
        assert service.get_file_extension(ExportFormat.CSV) == "csv"
        assert service.get_file_extension(ExportFormat.JSON_LINES) == "jsonl"
        assert service.get_file_extension(ExportFormat.RDF_TURTLE) == "ttl"

    def test_unsupported_format_raises_error(self, service, sample_concepts):
        """Unsupported format raises ValueError."""
        config = ExportConfig(format=ExportFormat.JSON)  # JSON not implemented
        with pytest.raises(ValueError) as exc:
            service.export_concepts(sample_concepts, config)
        assert "Unsupported" in str(exc.value)


class TestExportConfig:
    """Tests for ExportConfig."""

    def test_default_config(self):
        """Default config values."""
        config = ExportConfig()

        assert config.format == ExportFormat.CSV
        assert config.entity_type == ExportEntityType.CONCEPTS
        assert config.offset == 0
        assert config.limit is None
        assert config.include_header is True

    def test_config_with_options(self):
        """Config with custom options."""
        config = ExportConfig(
            format=ExportFormat.JSON_LINES,
            include_fields=["cui", "name"],
            limit=100
        )

        assert config.format == ExportFormat.JSON_LINES
        assert config.include_fields == ["cui", "name"]
        assert config.limit == 100

    def test_config_rdf_options(self):
        """Config with RDF options."""
        config = ExportConfig(
            format=ExportFormat.RDF_TURTLE,
            rdf_base_uri="http://myorg.org/kg/"
        )

        assert config.rdf_base_uri == "http://myorg.org/kg/"


class TestSingletonInstance:
    """Tests for singleton pattern."""

    def test_get_data_export_service_returns_same_instance(self):
        """Singleton returns same instance."""
        service1 = get_data_export_service()
        service2 = get_data_export_service()
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
