"""
Knowledge Graph Data Export Service.

Provides data export functionality for knowledge graph data in multiple formats:
- CSV (for spreadsheet compatibility)
- JSON Lines (for streaming and big data)
- RDF/Turtle (for semantic web interoperability)
- N-Triples (simple RDF format)
- GraphML (for graph visualization tools)

Features:
- Streaming export for large datasets
- Configurable field selection
- UMLS/SNOMED concept export
- Patient graph export
- Relationship export with attributes
- Temporal data preservation
"""
# MODULE: graph_support
# MATURITY: pilot

from __future__ import annotations

import csv
import io
import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Iterator
import uuid

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "csv"
    JSON_LINES = "jsonl"
    JSON = "json"
    RDF_TURTLE = "turtle"
    RDF_NTRIPLES = "ntriples"
    GRAPHML = "graphml"


class ExportEntityType(str, Enum):
    """Types of entities that can be exported."""

    CONCEPTS = "concepts"
    RELATIONSHIPS = "relationships"
    PATIENTS = "patients"
    PATIENT_GRAPHS = "patient_graphs"
    REASONING_PATHS = "reasoning_paths"
    SEMANTIC_TYPES = "semantic_types"


@dataclass
class ExportConfig:
    """Configuration for data export."""

    format: ExportFormat = ExportFormat.CSV
    entity_type: ExportEntityType = ExportEntityType.CONCEPTS

    # Field selection
    include_fields: list[str] = field(default_factory=list)  # Empty = all
    exclude_fields: list[str] = field(default_factory=list)

    # Filtering
    concept_cuis: list[str] = field(default_factory=list)
    patient_ids: list[str] = field(default_factory=list)
    semantic_types: list[str] = field(default_factory=list)
    vocabularies: list[str] = field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None

    # Pagination
    offset: int = 0
    limit: int | None = None  # None = no limit

    # Format-specific options
    csv_delimiter: str = ","
    csv_quotechar: str = '"'
    include_header: bool = True

    # RDF options
    rdf_base_uri: str = "http://example.org/kg/"
    rdf_prefix_umls: str = "http://bioportal.bioontology.org/ontologies/umls/"
    rdf_prefix_snomed: str = "http://snomed.info/id/"

    # Compression
    compress: bool = False


@dataclass
class ExportResult:
    """Result of an export operation."""

    format: ExportFormat
    entity_type: ExportEntityType
    record_count: int
    byte_size: int
    export_time_ms: float
    filename: str | None = None
    content: str | None = None  # For small exports
    stream: AsyncIterator[str] | None = None  # For streaming exports


@dataclass
class ConceptRecord:
    """A concept record for export."""

    cui: str
    name: str
    semantic_type: str | None = None
    semantic_group: str | None = None
    vocabulary: str | None = None
    code: str | None = None
    definition: str | None = None
    synonyms: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationshipRecord:
    """A relationship record for export."""

    source_cui: str
    target_cui: str
    relationship_type: str
    source_name: str | None = None
    target_name: str | None = None
    weight: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


@dataclass
class PatientGraphRecord:
    """A patient graph record for export."""

    patient_id: str
    node_count: int
    edge_count: int
    concepts: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    procedures: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None


class DataExporter(ABC):
    """Abstract base class for data exporters."""

    @abstractmethod
    def export_concepts(
        self,
        concepts: Iterator[ConceptRecord],
        config: ExportConfig
    ) -> str:
        """Export concepts to string."""
        pass

    @abstractmethod
    def export_relationships(
        self,
        relationships: Iterator[RelationshipRecord],
        config: ExportConfig
    ) -> str:
        """Export relationships to string."""
        pass

    @abstractmethod
    def get_content_type(self) -> str:
        """Get MIME content type for this format."""
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get file extension for this format."""
        pass


class CSVExporter(DataExporter):
    """Export data to CSV format."""

    def export_concepts(
        self,
        concepts: Iterator[ConceptRecord],
        config: ExportConfig
    ) -> str:
        """Export concepts to CSV."""
        output = io.StringIO()
        writer = None

        for concept in concepts:
            row = self._concept_to_row(concept, config)

            if writer is None:
                fieldnames = self._get_concept_fields(config)
                writer = csv.DictWriter(
                    output,
                    fieldnames=fieldnames,
                    delimiter=config.csv_delimiter,
                    quotechar=config.csv_quotechar,
                    quoting=csv.QUOTE_MINIMAL
                )
                if config.include_header:
                    writer.writeheader()

            writer.writerow(row)

        return output.getvalue()

    def export_relationships(
        self,
        relationships: Iterator[RelationshipRecord],
        config: ExportConfig
    ) -> str:
        """Export relationships to CSV."""
        output = io.StringIO()
        writer = None

        for rel in relationships:
            row = self._relationship_to_row(rel, config)

            if writer is None:
                fieldnames = self._get_relationship_fields(config)
                writer = csv.DictWriter(
                    output,
                    fieldnames=fieldnames,
                    delimiter=config.csv_delimiter,
                    quotechar=config.csv_quotechar,
                    quoting=csv.QUOTE_MINIMAL
                )
                if config.include_header:
                    writer.writeheader()

            writer.writerow(row)

        return output.getvalue()

    def _concept_to_row(
        self,
        concept: ConceptRecord,
        config: ExportConfig
    ) -> dict[str, Any]:
        """Convert concept to CSV row."""
        row = {
            "cui": concept.cui,
            "name": concept.name,
            "semantic_type": concept.semantic_type or "",
            "semantic_group": concept.semantic_group or "",
            "vocabulary": concept.vocabulary or "",
            "code": concept.code or "",
            "definition": concept.definition or "",
            "synonyms": "|".join(concept.synonyms),
        }

        if concept.created_at:
            row["created_at"] = concept.created_at.isoformat()
        if concept.updated_at:
            row["updated_at"] = concept.updated_at.isoformat()

        return self._filter_fields(row, config)

    def _relationship_to_row(
        self,
        rel: RelationshipRecord,
        config: ExportConfig
    ) -> dict[str, Any]:
        """Convert relationship to CSV row."""
        row = {
            "source_cui": rel.source_cui,
            "target_cui": rel.target_cui,
            "relationship_type": rel.relationship_type,
            "source_name": rel.source_name or "",
            "target_name": rel.target_name or "",
            "weight": rel.weight,
        }

        if rel.valid_from:
            row["valid_from"] = rel.valid_from.isoformat()
        if rel.valid_to:
            row["valid_to"] = rel.valid_to.isoformat()

        return self._filter_fields(row, config)

    def _get_concept_fields(self, config: ExportConfig) -> list[str]:
        """Get concept field names."""
        all_fields = [
            "cui", "name", "semantic_type", "semantic_group",
            "vocabulary", "code", "definition", "synonyms",
            "created_at", "updated_at"
        ]
        return self._apply_field_filter(all_fields, config)

    def _get_relationship_fields(self, config: ExportConfig) -> list[str]:
        """Get relationship field names."""
        all_fields = [
            "source_cui", "target_cui", "relationship_type",
            "source_name", "target_name", "weight",
            "valid_from", "valid_to"
        ]
        return self._apply_field_filter(all_fields, config)

    def _apply_field_filter(
        self,
        fields: list[str],
        config: ExportConfig
    ) -> list[str]:
        """Apply include/exclude field filters."""
        if config.include_fields:
            fields = [f for f in fields if f in config.include_fields]
        if config.exclude_fields:
            fields = [f for f in fields if f not in config.exclude_fields]
        return fields

    def _filter_fields(
        self,
        row: dict[str, Any],
        config: ExportConfig
    ) -> dict[str, Any]:
        """Filter row fields based on config."""
        if config.include_fields:
            row = {k: v for k, v in row.items() if k in config.include_fields}
        if config.exclude_fields:
            row = {k: v for k, v in row.items() if k not in config.exclude_fields}
        return row

    def get_content_type(self) -> str:
        return "text/csv"

    def get_file_extension(self) -> str:
        return "csv"


class JSONLinesExporter(DataExporter):
    """Export data to JSON Lines format."""

    def export_concepts(
        self,
        concepts: Iterator[ConceptRecord],
        config: ExportConfig
    ) -> str:
        """Export concepts to JSON Lines."""
        lines = []
        for concept in concepts:
            record = self._concept_to_dict(concept, config)
            lines.append(json.dumps(record, default=str))
        return "\n".join(lines)

    def export_relationships(
        self,
        relationships: Iterator[RelationshipRecord],
        config: ExportConfig
    ) -> str:
        """Export relationships to JSON Lines."""
        lines = []
        for rel in relationships:
            record = self._relationship_to_dict(rel, config)
            lines.append(json.dumps(record, default=str))
        return "\n".join(lines)

    def _concept_to_dict(
        self,
        concept: ConceptRecord,
        config: ExportConfig
    ) -> dict[str, Any]:
        """Convert concept to dictionary."""
        record = {
            "cui": concept.cui,
            "name": concept.name,
            "semantic_type": concept.semantic_type,
            "semantic_group": concept.semantic_group,
            "vocabulary": concept.vocabulary,
            "code": concept.code,
            "definition": concept.definition,
            "synonyms": concept.synonyms,
            "attributes": concept.attributes,
        }

        if concept.created_at:
            record["created_at"] = concept.created_at.isoformat()
        if concept.updated_at:
            record["updated_at"] = concept.updated_at.isoformat()

        return self._filter_fields(record, config)

    def _relationship_to_dict(
        self,
        rel: RelationshipRecord,
        config: ExportConfig
    ) -> dict[str, Any]:
        """Convert relationship to dictionary."""
        record = {
            "source_cui": rel.source_cui,
            "target_cui": rel.target_cui,
            "relationship_type": rel.relationship_type,
            "source_name": rel.source_name,
            "target_name": rel.target_name,
            "weight": rel.weight,
            "attributes": rel.attributes,
        }

        if rel.valid_from:
            record["valid_from"] = rel.valid_from.isoformat()
        if rel.valid_to:
            record["valid_to"] = rel.valid_to.isoformat()

        return self._filter_fields(record, config)

    def _filter_fields(
        self,
        record: dict[str, Any],
        config: ExportConfig
    ) -> dict[str, Any]:
        """Filter record fields based on config."""
        if config.include_fields:
            record = {k: v for k, v in record.items() if k in config.include_fields}
        if config.exclude_fields:
            record = {k: v for k, v in record.items() if k not in config.exclude_fields}
        # Remove None values for cleaner output
        return {k: v for k, v in record.items() if v is not None}

    def get_content_type(self) -> str:
        return "application/x-ndjson"

    def get_file_extension(self) -> str:
        return "jsonl"


class RDFTurtleExporter(DataExporter):
    """Export data to RDF Turtle format."""

    def export_concepts(
        self,
        concepts: Iterator[ConceptRecord],
        config: ExportConfig
    ) -> str:
        """Export concepts to Turtle format."""
        lines = self._get_prefixes(config)

        for concept in concepts:
            lines.extend(self._concept_to_turtle(concept, config))

        return "\n".join(lines)

    def export_relationships(
        self,
        relationships: Iterator[RelationshipRecord],
        config: ExportConfig
    ) -> str:
        """Export relationships to Turtle format."""
        lines = self._get_prefixes(config)

        for rel in relationships:
            lines.extend(self._relationship_to_turtle(rel, config))

        return "\n".join(lines)

    def _get_prefixes(self, config: ExportConfig) -> list[str]:
        """Get RDF prefixes."""
        return [
            f"@prefix : <{config.rdf_base_uri}> .",
            f"@prefix umls: <{config.rdf_prefix_umls}> .",
            f"@prefix snomed: <{config.rdf_prefix_snomed}> .",
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
            "@prefix dct: <http://purl.org/dc/terms/> .",
            "",
        ]

    def _concept_to_turtle(
        self,
        concept: ConceptRecord,
        config: ExportConfig
    ) -> list[str]:
        """Convert concept to Turtle triples."""
        uri = f":concept_{concept.cui}"
        lines = [
            f"{uri} a skos:Concept ;",
            f'    skos:notation "{concept.cui}" ;',
            f'    skos:prefLabel "{self._escape_literal(concept.name)}"@en ;',
        ]

        if concept.semantic_type:
            lines.append(f'    :semanticType "{concept.semantic_type}" ;')

        if concept.vocabulary:
            lines.append(f'    :vocabulary "{concept.vocabulary}" ;')

        if concept.code:
            lines.append(f'    :code "{concept.code}" ;')

        if concept.definition:
            lines.append(f'    skos:definition "{self._escape_literal(concept.definition)}"@en ;')

        for synonym in concept.synonyms:
            lines.append(f'    skos:altLabel "{self._escape_literal(synonym)}"@en ;')

        if concept.created_at:
            lines.append(f'    dct:created "{concept.created_at.isoformat()}"^^xsd:dateTime ;')

        # Close the statement
        lines[-1] = lines[-1].rstrip(" ;") + " ."
        lines.append("")

        return lines

    def _relationship_to_turtle(
        self,
        rel: RelationshipRecord,
        config: ExportConfig
    ) -> list[str]:
        """Convert relationship to Turtle triples."""
        source_uri = f":concept_{rel.source_cui}"
        target_uri = f":concept_{rel.target_cui}"
        predicate = f":{self._sanitize_predicate(rel.relationship_type)}"

        lines = [
            f"{source_uri} {predicate} {target_uri} .",
        ]

        # Reification for attributes
        if rel.weight != 1.0 or rel.valid_from or rel.valid_to:
            stmt_id = f":stmt_{uuid.uuid4().hex[:8]}"
            lines.extend([
                f"{stmt_id} a rdf:Statement ;",
                f"    rdf:subject {source_uri} ;",
                f"    rdf:predicate {predicate} ;",
                f"    rdf:object {target_uri} ;",
            ])

            if rel.weight != 1.0:
                lines.append(f'    :weight "{rel.weight}"^^xsd:decimal ;')

            if rel.valid_from:
                lines.append(f'    :validFrom "{rel.valid_from.isoformat()}"^^xsd:dateTime ;')

            if rel.valid_to:
                lines.append(f'    :validTo "{rel.valid_to.isoformat()}"^^xsd:dateTime ;')

            lines[-1] = lines[-1].rstrip(" ;") + " ."

        lines.append("")
        return lines

    def _escape_literal(self, value: str) -> str:
        """Escape special characters in RDF literals."""
        return (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

    def _sanitize_predicate(self, predicate: str) -> str:
        """Sanitize predicate for use in RDF."""
        return predicate.replace(" ", "_").replace("-", "_").lower()

    def get_content_type(self) -> str:
        return "text/turtle"

    def get_file_extension(self) -> str:
        return "ttl"


class NTriplesExporter(DataExporter):
    """Export data to N-Triples format."""

    def export_concepts(
        self,
        concepts: Iterator[ConceptRecord],
        config: ExportConfig
    ) -> str:
        """Export concepts to N-Triples format."""
        lines = []
        for concept in concepts:
            lines.extend(self._concept_to_ntriples(concept, config))
        return "\n".join(lines)

    def export_relationships(
        self,
        relationships: Iterator[RelationshipRecord],
        config: ExportConfig
    ) -> str:
        """Export relationships to N-Triples format."""
        lines = []
        for rel in relationships:
            lines.extend(self._relationship_to_ntriples(rel, config))
        return "\n".join(lines)

    def _concept_to_ntriples(
        self,
        concept: ConceptRecord,
        config: ExportConfig
    ) -> list[str]:
        """Convert concept to N-Triples."""
        subject = f"<{config.rdf_base_uri}concept_{concept.cui}>"
        lines = [
            f'{subject} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2004/02/skos/core#Concept> .',
            f'{subject} <http://www.w3.org/2004/02/skos/core#notation> "{concept.cui}" .',
            f'{subject} <http://www.w3.org/2004/02/skos/core#prefLabel> "{self._escape_literal(concept.name)}"@en .',
        ]

        if concept.semantic_type:
            lines.append(
                f'{subject} <{config.rdf_base_uri}semanticType> "{concept.semantic_type}" .'
            )

        if concept.definition:
            lines.append(
                f'{subject} <http://www.w3.org/2004/02/skos/core#definition> '
                f'"{self._escape_literal(concept.definition)}"@en .'
            )

        for synonym in concept.synonyms:
            lines.append(
                f'{subject} <http://www.w3.org/2004/02/skos/core#altLabel> '
                f'"{self._escape_literal(synonym)}"@en .'
            )

        return lines

    def _relationship_to_ntriples(
        self,
        rel: RelationshipRecord,
        config: ExportConfig
    ) -> list[str]:
        """Convert relationship to N-Triples."""
        subject = f"<{config.rdf_base_uri}concept_{rel.source_cui}>"
        obj = f"<{config.rdf_base_uri}concept_{rel.target_cui}>"
        predicate = f"<{config.rdf_base_uri}{rel.relationship_type.replace(' ', '_').lower()}>"

        return [f"{subject} {predicate} {obj} ."]

    def _escape_literal(self, value: str) -> str:
        """Escape special characters in N-Triples literals."""
        return (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

    def get_content_type(self) -> str:
        return "application/n-triples"

    def get_file_extension(self) -> str:
        return "nt"


class GraphMLExporter(DataExporter):
    """Export data to GraphML format."""

    def export_concepts(
        self,
        concepts: Iterator[ConceptRecord],
        config: ExportConfig
    ) -> str:
        """Export concepts to GraphML (as nodes)."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
            '  <key id="semantic_type" for="node" attr.name="semantic_type" attr.type="string"/>',
            '  <key id="vocabulary" for="node" attr.name="vocabulary" attr.type="string"/>',
            '  <graph id="G" edgedefault="directed">',
        ]

        for concept in concepts:
            lines.extend(self._concept_to_graphml_node(concept))

        lines.extend([
            '  </graph>',
            '</graphml>',
        ])

        return "\n".join(lines)

    def export_relationships(
        self,
        relationships: Iterator[RelationshipRecord],
        config: ExportConfig
    ) -> str:
        """Export relationships to GraphML."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="label" for="edge" attr.name="label" attr.type="string"/>',
            '  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
            '  <graph id="G" edgedefault="directed">',
        ]

        # Collect unique nodes
        nodes = set()
        edges = []
        for rel in relationships:
            nodes.add((rel.source_cui, rel.source_name or rel.source_cui))
            nodes.add((rel.target_cui, rel.target_name or rel.target_cui))
            edges.append(rel)

        # Add nodes
        for cui, name in nodes:
            lines.append(f'    <node id="{self._escape_xml(cui)}">')
            lines.append(f'      <data key="name">{self._escape_xml(name)}</data>')
            lines.append('    </node>')

        # Add edges
        for i, rel in enumerate(edges):
            lines.append(
                f'    <edge id="e{i}" source="{self._escape_xml(rel.source_cui)}" '
                f'target="{self._escape_xml(rel.target_cui)}">'
            )
            lines.append(f'      <data key="label">{self._escape_xml(rel.relationship_type)}</data>')
            lines.append(f'      <data key="weight">{rel.weight}</data>')
            lines.append('    </edge>')

        lines.extend([
            '  </graph>',
            '</graphml>',
        ])

        return "\n".join(lines)

    def _concept_to_graphml_node(self, concept: ConceptRecord) -> list[str]:
        """Convert concept to GraphML node."""
        lines = [
            f'    <node id="{self._escape_xml(concept.cui)}">',
            f'      <data key="name">{self._escape_xml(concept.name)}</data>',
        ]

        if concept.semantic_type:
            lines.append(
                f'      <data key="semantic_type">{self._escape_xml(concept.semantic_type)}</data>'
            )

        if concept.vocabulary:
            lines.append(
                f'      <data key="vocabulary">{self._escape_xml(concept.vocabulary)}</data>'
            )

        lines.append('    </node>')
        return lines

    def _escape_xml(self, value: str) -> str:
        """Escape special XML characters."""
        return (
            value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def get_content_type(self) -> str:
        return "application/graphml+xml"

    def get_file_extension(self) -> str:
        return "graphml"


class KGDataExportService:
    """
    Service for exporting knowledge graph data to various formats.

    Supports:
    - CSV for spreadsheet compatibility
    - JSON Lines for streaming/big data
    - RDF Turtle for semantic web
    - N-Triples for simple RDF
    - GraphML for graph visualization
    """

    def __init__(self):
        """Initialize the export service."""
        self._exporters: dict[ExportFormat, DataExporter] = {
            ExportFormat.CSV: CSVExporter(),
            ExportFormat.JSON_LINES: JSONLinesExporter(),
            ExportFormat.RDF_TURTLE: RDFTurtleExporter(),
            ExportFormat.RDF_NTRIPLES: NTriplesExporter(),
            ExportFormat.GRAPHML: GraphMLExporter(),
        }

    def export_concepts(
        self,
        concepts: list[ConceptRecord],
        config: ExportConfig | None = None
    ) -> ExportResult:
        """
        Export concepts to the specified format.

        Args:
            concepts: List of concept records
            config: Export configuration

        Returns:
            ExportResult with exported data
        """
        import time
        start_time = time.time()

        config = config or ExportConfig()
        exporter = self._get_exporter(config.format)

        # Apply filters
        filtered = self._filter_concepts(concepts, config)

        # Apply pagination
        if config.offset:
            filtered = filtered[config.offset:]
        if config.limit:
            filtered = filtered[:config.limit]

        # Export
        content = exporter.export_concepts(iter(filtered), config)

        export_time_ms = (time.time() - start_time) * 1000

        return ExportResult(
            format=config.format,
            entity_type=ExportEntityType.CONCEPTS,
            record_count=len(filtered),
            byte_size=len(content.encode("utf-8")),
            export_time_ms=export_time_ms,
            filename=f"concepts.{exporter.get_file_extension()}",
            content=content,
        )

    def export_relationships(
        self,
        relationships: list[RelationshipRecord],
        config: ExportConfig | None = None
    ) -> ExportResult:
        """
        Export relationships to the specified format.

        Args:
            relationships: List of relationship records
            config: Export configuration

        Returns:
            ExportResult with exported data
        """
        import time
        start_time = time.time()

        config = config or ExportConfig()
        exporter = self._get_exporter(config.format)

        # Apply filters
        filtered = self._filter_relationships(relationships, config)

        # Apply pagination
        if config.offset:
            filtered = filtered[config.offset:]
        if config.limit:
            filtered = filtered[:config.limit]

        # Export
        content = exporter.export_relationships(iter(filtered), config)

        export_time_ms = (time.time() - start_time) * 1000

        return ExportResult(
            format=config.format,
            entity_type=ExportEntityType.RELATIONSHIPS,
            record_count=len(filtered),
            byte_size=len(content.encode("utf-8")),
            export_time_ms=export_time_ms,
            filename=f"relationships.{exporter.get_file_extension()}",
            content=content,
        )

    def _get_exporter(self, format: ExportFormat) -> DataExporter:
        """Get exporter for format."""
        if format not in self._exporters:
            raise ValueError(f"Unsupported export format: {format}")
        return self._exporters[format]

    def _filter_concepts(
        self,
        concepts: list[ConceptRecord],
        config: ExportConfig
    ) -> list[ConceptRecord]:
        """Filter concepts based on config."""
        result = concepts

        if config.concept_cuis:
            result = [c for c in result if c.cui in config.concept_cuis]

        if config.semantic_types:
            result = [c for c in result if c.semantic_type in config.semantic_types]

        if config.vocabularies:
            result = [c for c in result if c.vocabulary in config.vocabularies]

        if config.date_from:
            result = [
                c for c in result
                if c.created_at and c.created_at >= config.date_from
            ]

        if config.date_to:
            result = [
                c for c in result
                if c.created_at and c.created_at <= config.date_to
            ]

        return result

    def _filter_relationships(
        self,
        relationships: list[RelationshipRecord],
        config: ExportConfig
    ) -> list[RelationshipRecord]:
        """Filter relationships based on config."""
        result = relationships

        if config.concept_cuis:
            result = [
                r for r in result
                if r.source_cui in config.concept_cuis or r.target_cui in config.concept_cuis
            ]

        if config.date_from:
            result = [
                r for r in result
                if r.valid_from and r.valid_from >= config.date_from
            ]

        if config.date_to:
            result = [
                r for r in result
                if r.valid_to is None or r.valid_to <= config.date_to
            ]

        return result

    def get_supported_formats(self) -> list[dict[str, str]]:
        """Get list of supported export formats."""
        return [
            {
                "format": format.value,
                "content_type": exporter.get_content_type(),
                "extension": exporter.get_file_extension(),
            }
            for format, exporter in self._exporters.items()
        ]

    def get_content_type(self, format: ExportFormat) -> str:
        """Get MIME content type for format."""
        return self._get_exporter(format).get_content_type()

    def get_file_extension(self, format: ExportFormat) -> str:
        """Get file extension for format."""
        return self._get_exporter(format).get_file_extension()


# Singleton instance
_export_service: KGDataExportService | None = None
_export_lock = threading.Lock()


def get_data_export_service() -> KGDataExportService:
    """Get or create data export service singleton."""
    global _export_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _export_service is None:
        with _export_lock:
            if _export_service is None:
                _export_service = KGDataExportService()
    return _export_service
