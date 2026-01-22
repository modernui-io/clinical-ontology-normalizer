"""
Knowledge Graph FHIR Export Service.

Exports knowledge graph data to FHIR R4 resources:
- Concepts as CodeSystem/ValueSet resources
- Reasoning paths as Provenance resources
- Causal chains as Evidence resources
- Temporal graph state as Bundle resources

Based on:
- FHIR R4 Provenance resource (HL7 standard)
- FHIR R4 Evidence resource (for clinical evidence)
- FHIR R4 Library resource (for knowledge artifacts)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class KGExportResourceType(str, Enum):
    """Knowledge graph FHIR export resource types."""

    PROVENANCE = "Provenance"
    EVIDENCE = "Evidence"
    EVIDENCE_VARIABLE = "EvidenceVariable"
    LIBRARY = "Library"
    ACTIVITY_DEFINITION = "ActivityDefinition"
    BUNDLE = "Bundle"


# FHIR code systems for knowledge graph concepts
FHIR_KG_CODE_SYSTEMS = {
    "umls": "http://www.nlm.nih.gov/research/umls",
    "snomed": "http://snomed.info/sct",
    "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "icd10": "http://hl7.org/fhir/sid/icd-10-cm",
    "loinc": "http://loinc.org",
    "nci": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
    "mesh": "http://id.nlm.nih.gov/mesh",
}

# Provenance activity types for reasoning
PROVENANCE_ACTIVITIES = {
    "extraction": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
        "code": "EXTRACT",
        "display": "Extract",
    },
    "inference": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "INFA",
        "display": "Inference",
    },
    "reasoning": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActClass",
        "code": "LOGIC",
        "display": "Logical reasoning",
    },
    "aggregation": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
        "code": "MERGE",
        "display": "Merge/Aggregate",
    },
}


@dataclass
class KGNode:
    """Knowledge graph node for FHIR export."""

    id: str
    cui: str | None = None
    name: str = ""
    semantic_type: str | None = None
    semantic_group: str | None = None
    vocabulary: str | None = None
    code: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


@dataclass
class KGEdge:
    """Knowledge graph edge for FHIR export."""

    source_id: str
    target_id: str
    relationship_type: str
    confidence: float = 1.0
    source_document: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningChain:
    """A reasoning chain through the knowledge graph."""

    chain_id: str = field(default_factory=lambda: str(uuid4()))
    query: str = ""
    conclusion: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[KGNode] = field(default_factory=list)
    edges: list[KGEdge] = field(default_factory=list)
    confidence: float = 1.0
    source_documents: list[str] = field(default_factory=list)


@dataclass
class FHIRKGResource:
    """A FHIR resource exported from knowledge graph."""

    resource_type: KGExportResourceType
    resource_id: str
    resource: dict[str, Any]
    source_kg_ids: list[str] = field(default_factory=list)


class KnowledgeGraphFHIRExporter:
    """
    Service for exporting knowledge graph data to FHIR R4 resources.

    Exports:
    - Reasoning chains as Provenance resources
    - Causal relationships as Evidence resources
    - Graph concepts as Library resources
    - Full graph state as Bundle resources
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/fhir",
        organization: str = "Clinical Knowledge Graph System",
    ):
        self.base_url = base_url
        self.organization = organization
        self._resource_counter = 0

    def _generate_id(self) -> str:
        """Generate unique resource ID."""
        self._resource_counter += 1
        return f"kg-{uuid4().hex[:12]}"

    # =========================================================================
    # PROVENANCE EXPORT (Reasoning Chains)
    # =========================================================================

    def export_reasoning_chain_as_provenance(
        self,
        chain: ReasoningChain,
        patient_id: str | None = None,
    ) -> FHIRKGResource:
        """
        Export a reasoning chain as FHIR Provenance resource.

        The Provenance resource tracks:
        - What was derived (the conclusion)
        - How it was derived (the reasoning steps)
        - From what sources (the source facts)
        - By whom/what (the reasoning agent)

        Args:
            chain: Reasoning chain to export
            patient_id: Optional patient reference

        Returns:
            FHIRKGResource with Provenance resource
        """
        resource_id = self._generate_id()

        # Build entity references (source facts)
        entities = []
        for node in chain.nodes:
            entity = {
                "role": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/provenance-entity-role",
                        "code": "source",
                        "display": "Source",
                    }]
                },
                "what": {
                    "identifier": {
                        "system": FHIR_KG_CODE_SYSTEMS.get(
                            node.vocabulary.lower() if node.vocabulary else "umls",
                            FHIR_KG_CODE_SYSTEMS["umls"]
                        ),
                        "value": node.cui or node.id,
                    },
                    "display": node.name,
                },
            }
            entities.append(entity)

        # Add conclusion as derived entity
        if chain.conclusion:
            entities.append({
                "role": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/provenance-entity-role",
                        "code": "derivation",
                        "display": "Derivation",
                    }]
                },
                "what": {
                    "display": chain.conclusion,
                },
            })

        # Build agents (the reasoning system)
        agents = [{
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                    "code": "performer",
                    "display": "Performer",
                }]
            },
            "who": {
                "display": self.organization,
            },
            "onBehalfOf": {
                "display": "Knowledge Graph Reasoning Engine",
            },
        }]

        # Build signature (confidence attestation)
        signatures = []
        if chain.confidence < 1.0:
            signatures.append({
                "type": [{
                    "system": "urn:iso-astm:E1762-95:2013",
                    "code": "1.2.840.10065.1.12.1.5",
                    "display": "Verification Signature",
                }],
                "when": datetime.now(timezone.utc).isoformat(),
                "who": {"display": "Knowledge Graph System"},
                "data": f"confidence:{chain.confidence:.3f}",
            })

        resource = {
            "resourceType": "Provenance",
            "id": resource_id,
            "meta": {
                "profile": [
                    "http://hl7.org/fhir/StructureDefinition/Provenance"
                ],
            },
            "recorded": datetime.now(timezone.utc).isoformat(),
            "activity": {
                "coding": [PROVENANCE_ACTIVITIES["reasoning"]],
            },
            "agent": agents,
            "entity": entities,
        }

        # Add target (what the provenance is about)
        if patient_id:
            resource["target"] = [{
                "reference": f"Patient/{patient_id}",
            }]

        # Add reasoning steps as text
        if chain.steps:
            resource["reason"] = [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                    "code": "TREAT",
                    "display": "Treatment",
                }],
                "text": " -> ".join(
                    step.get("description", step.get("concept", ""))
                    for step in chain.steps
                ),
            }]

        # Add source documents
        if chain.source_documents:
            if "entity" not in resource:
                resource["entity"] = []
            for doc_id in chain.source_documents:
                resource["entity"].append({
                    "role": {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/provenance-entity-role",
                            "code": "source",
                        }]
                    },
                    "what": {
                        "reference": f"DocumentReference/{doc_id}",
                    },
                })

        if signatures:
            resource["signature"] = signatures

        return FHIRKGResource(
            resource_type=KGExportResourceType.PROVENANCE,
            resource_id=resource_id,
            resource=resource,
            source_kg_ids=[chain.chain_id],
        )

    # =========================================================================
    # EVIDENCE EXPORT (Causal Chains)
    # =========================================================================

    def export_causal_chain_as_evidence(
        self,
        cause_node: KGNode,
        effect_node: KGNode,
        edge: KGEdge,
        supporting_paths: int = 1,
    ) -> FHIRKGResource:
        """
        Export a causal relationship as FHIR Evidence resource.

        The Evidence resource represents:
        - The causal assertion (cause -> effect)
        - Supporting evidence (confidence, sources)
        - Certainty assessment

        Args:
            cause_node: The cause concept
            effect_node: The effect concept
            edge: The causal relationship edge
            supporting_paths: Number of supporting paths

        Returns:
            FHIRKGResource with Evidence resource
        """
        resource_id = self._generate_id()

        # Determine certainty rating based on confidence
        certainty_rating = "low"
        if edge.confidence >= 0.9:
            certainty_rating = "high"
        elif edge.confidence >= 0.7:
            certainty_rating = "moderate"

        resource = {
            "resourceType": "Evidence",
            "id": resource_id,
            "status": "active",
            "title": f"{cause_node.name} {edge.relationship_type} {effect_node.name}",
            "description": (
                f"Causal relationship: {cause_node.name} ({cause_node.cui}) "
                f"{edge.relationship_type.replace('_', ' ')} "
                f"{effect_node.name} ({effect_node.cui})"
            ),
            "date": datetime.now(timezone.utc).isoformat(),
            "publisher": self.organization,
            # Synthesis type
            "synthesisType": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/synthesis-type",
                    "code": "indirect-NMA",
                    "display": "Indirect NMA",
                }],
                "text": "Knowledge graph inference",
            },
            # Variable definitions
            "variableDefinition": [
                {
                    "variableRole": {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/variable-role",
                            "code": "exposure",
                        }]
                    },
                    "observed": {
                        "display": cause_node.name,
                        "identifier": {
                            "system": FHIR_KG_CODE_SYSTEMS.get(
                                cause_node.vocabulary.lower() if cause_node.vocabulary else "umls",
                                FHIR_KG_CODE_SYSTEMS["umls"]
                            ),
                            "value": cause_node.cui or cause_node.id,
                        },
                    },
                },
                {
                    "variableRole": {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/variable-role",
                            "code": "outcome",
                        }]
                    },
                    "observed": {
                        "display": effect_node.name,
                        "identifier": {
                            "system": FHIR_KG_CODE_SYSTEMS.get(
                                effect_node.vocabulary.lower() if effect_node.vocabulary else "umls",
                                FHIR_KG_CODE_SYSTEMS["umls"]
                            ),
                            "value": effect_node.cui or effect_node.id,
                        },
                    },
                },
            ],
            # Certainty assessment
            "certainty": [{
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/certainty-type",
                        "code": "Overall",
                    }]
                },
                "rating": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/certainty-rating",
                        "code": certainty_rating,
                    }]
                },
                "note": [{
                    "text": f"Confidence: {edge.confidence:.2f}, Supporting paths: {supporting_paths}",
                }],
            }],
        }

        # Add study type if from curated source
        if edge.source_document:
            resource["studyType"] = {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/study-type",
                    "code": "case-report",
                    "display": "Case report",
                }],
                "text": f"Source: {edge.source_document}",
            }

        return FHIRKGResource(
            resource_type=KGExportResourceType.EVIDENCE,
            resource_id=resource_id,
            resource=resource,
            source_kg_ids=[cause_node.id, effect_node.id],
        )

    # =========================================================================
    # LIBRARY EXPORT (Knowledge Artifacts)
    # =========================================================================

    def export_concepts_as_library(
        self,
        nodes: list[KGNode],
        library_name: str = "Clinical Concepts",
        description: str = "",
    ) -> FHIRKGResource:
        """
        Export a set of concepts as FHIR Library resource.

        The Library resource packages related concepts for distribution.

        Args:
            nodes: List of knowledge graph nodes
            library_name: Name for the library
            description: Library description

        Returns:
            FHIRKGResource with Library resource
        """
        resource_id = self._generate_id()

        # Group concepts by vocabulary
        concepts_by_vocab: dict[str, list[KGNode]] = {}
        for node in nodes:
            vocab = node.vocabulary or "UMLS"
            if vocab not in concepts_by_vocab:
                concepts_by_vocab[vocab] = []
            concepts_by_vocab[vocab].append(node)

        # Build related artifacts (one per vocabulary)
        related_artifacts = []
        for vocab, vocab_nodes in concepts_by_vocab.items():
            related_artifacts.append({
                "type": "composed-of",
                "display": f"{vocab} concepts ({len(vocab_nodes)} concepts)",
                "resource": FHIR_KG_CODE_SYSTEMS.get(vocab.lower(), FHIR_KG_CODE_SYSTEMS["umls"]),
            })

        # Build content with concept list
        content_data = {
            "concepts": [
                {
                    "cui": node.cui,
                    "name": node.name,
                    "semanticType": node.semantic_type,
                    "vocabulary": node.vocabulary,
                    "code": node.code,
                }
                for node in nodes
            ],
            "total": len(nodes),
            "vocabularies": list(concepts_by_vocab.keys()),
        }

        resource = {
            "resourceType": "Library",
            "id": resource_id,
            "status": "active",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/library-type",
                    "code": "logic-library",
                    "display": "Logic Library",
                }]
            },
            "name": library_name.replace(" ", ""),
            "title": library_name,
            "description": description or f"Knowledge graph concepts: {len(nodes)} concepts from {len(concepts_by_vocab)} vocabularies",
            "date": datetime.now(timezone.utc).isoformat(),
            "publisher": self.organization,
            "relatedArtifact": related_artifacts,
            "content": [{
                "contentType": "application/json",
                "data": json.dumps(content_data, ensure_ascii=False),
                "title": "Concept definitions",
            }],
        }

        # Add topic tags based on semantic groups
        semantic_groups = set(
            node.semantic_group for node in nodes
            if node.semantic_group
        )
        if semantic_groups:
            resource["topic"] = [
                {"text": group} for group in semantic_groups
            ]

        return FHIRKGResource(
            resource_type=KGExportResourceType.LIBRARY,
            resource_id=resource_id,
            resource=resource,
            source_kg_ids=[node.id for node in nodes],
        )

    # =========================================================================
    # BUNDLE EXPORT (Full Graph State)
    # =========================================================================

    def export_graph_as_bundle(
        self,
        nodes: list[KGNode],
        edges: list[KGEdge],
        reasoning_chains: list[ReasoningChain] | None = None,
        patient_id: str | None = None,
        bundle_type: str = "collection",
    ) -> dict[str, Any]:
        """
        Export full knowledge graph state as FHIR Bundle.

        Args:
            nodes: All graph nodes
            edges: All graph edges
            reasoning_chains: Optional reasoning chains
            patient_id: Optional patient reference
            bundle_type: Bundle type (collection, transaction, etc.)

        Returns:
            FHIR Bundle resource as dict
        """
        bundle_id = f"kg-bundle-{uuid4().hex[:12]}"
        entries: list[dict[str, Any]] = []

        # Export concepts as Library
        if nodes:
            library_resource = self.export_concepts_as_library(
                nodes=nodes,
                library_name="Knowledge Graph Concepts",
            )
            entries.append({
                "fullUrl": f"urn:uuid:{library_resource.resource_id}",
                "resource": library_resource.resource,
            })

        # Export causal edges as Evidence
        causal_relations = ["CAUSES", "MAY_CAUSE", "TREATS", "PREVENTS", "LEADS_TO"]
        node_map = {node.id: node for node in nodes}

        for edge in edges:
            if edge.relationship_type.upper() in causal_relations:
                source_node = node_map.get(edge.source_id)
                target_node = node_map.get(edge.target_id)
                if source_node and target_node:
                    evidence_resource = self.export_causal_chain_as_evidence(
                        cause_node=source_node,
                        effect_node=target_node,
                        edge=edge,
                    )
                    entries.append({
                        "fullUrl": f"urn:uuid:{evidence_resource.resource_id}",
                        "resource": evidence_resource.resource,
                    })

        # Export reasoning chains as Provenance
        if reasoning_chains:
            for chain in reasoning_chains:
                provenance_resource = self.export_reasoning_chain_as_provenance(
                    chain=chain,
                    patient_id=patient_id,
                )
                entries.append({
                    "fullUrl": f"urn:uuid:{provenance_resource.resource_id}",
                    "resource": provenance_resource.resource,
                })

        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": bundle_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(entries),
            "entry": entries,
            "meta": {
                "tag": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                        "code": "KGRAPH",
                        "display": "Knowledge Graph Export",
                    }
                ],
            },
        }

        # Add link for pagination if needed
        if len(entries) > 100:
            bundle["link"] = [{
                "relation": "self",
                "url": f"{self.base_url}/Bundle/{bundle_id}",
            }]

        return bundle

    # =========================================================================
    # PATIENT GRAPH EXPORT
    # =========================================================================

    def export_patient_graph(
        self,
        patient_id: str,
        nodes: list[KGNode],
        edges: list[KGEdge],
        reasoning_chains: list[ReasoningChain] | None = None,
        include_provenance: bool = True,
    ) -> dict[str, Any]:
        """
        Export a patient-specific knowledge graph as FHIR Bundle.

        Args:
            patient_id: Patient identifier
            nodes: Patient-related graph nodes
            edges: Patient-related graph edges
            reasoning_chains: Reasoning chains for patient
            include_provenance: Include provenance for each fact

        Returns:
            FHIR Bundle with patient-scoped resources
        """
        return self.export_graph_as_bundle(
            nodes=nodes,
            edges=edges,
            reasoning_chains=reasoning_chains,
            patient_id=patient_id,
            bundle_type="document",
        )

    def to_json(self, bundle: dict[str, Any], indent: int = 2) -> str:
        """Convert bundle to JSON string."""
        return json.dumps(bundle, indent=indent, ensure_ascii=False)

    # =========================================================================
    # TEMPORAL EXPORT
    # =========================================================================

    def export_temporal_snapshot(
        self,
        nodes: list[KGNode],
        edges: list[KGEdge],
        as_of_time: datetime,
        patient_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Export graph state as of a specific point in time.

        Args:
            nodes: All nodes (will be filtered by valid time)
            edges: All edges (will be filtered by valid time)
            as_of_time: Point in time for snapshot
            patient_id: Optional patient reference

        Returns:
            FHIR Bundle with temporal metadata
        """
        # Filter nodes valid at as_of_time
        valid_nodes = [
            node for node in nodes
            if (node.valid_from is None or node.valid_from <= as_of_time)
            and (node.valid_to is None or node.valid_to > as_of_time)
        ]

        # Filter edges (would need full implementation)
        valid_edges = edges  # Simplified for now

        bundle = self.export_graph_as_bundle(
            nodes=valid_nodes,
            edges=valid_edges,
            patient_id=patient_id,
            bundle_type="collection",
        )

        # Add temporal metadata
        bundle["meta"]["extension"] = [{
            "url": "http://hl7.org/fhir/StructureDefinition/resource-effectivePeriod",
            "valuePeriod": {
                "start": as_of_time.isoformat(),
            },
        }]

        return bundle


# Singleton instance
_kg_fhir_exporter: KnowledgeGraphFHIRExporter | None = None


def get_kg_fhir_exporter() -> KnowledgeGraphFHIRExporter:
    """Get the singleton knowledge graph FHIR exporter."""
    global _kg_fhir_exporter
    if _kg_fhir_exporter is None:
        _kg_fhir_exporter = KnowledgeGraphFHIRExporter()
    return _kg_fhir_exporter
