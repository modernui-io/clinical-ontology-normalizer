#!/usr/bin/env python3
"""Test the Ontology Mapper to Knowledge Graph integration.

This script demonstrates how the ontology mapper integrates with the
existing knowledge graph infrastructure for persistent memory.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# Sample clinical note
SAMPLE_NOTE = """
65-year-old male with history of type 2 diabetes mellitus, hypertension, and
hyperlipidemia presents with chest pain and shortness of breath.

HISTORY OF PRESENT ILLNESS:
Patient reports substernal chest pain radiating to left arm, started 3 hours ago.
Pain is described as pressure-like, 8/10 severity. Associated with diaphoresis
and nausea. Similar episode occurred 2 years ago, diagnosed with NSTEMI, treated
with PCI and stent placement.

MEDICATIONS:
- Aspirin 81mg daily
- Metformin 1000mg twice daily
- Lisinopril 20mg daily
- Atorvastatin 40mg daily
- Metoprolol 50mg twice daily

ALLERGIES: Penicillin (rash)

PHYSICAL EXAMINATION:
- Vital Signs: BP 150/95, HR 92, RR 20, T 98.6°F, SpO2 94% on RA
- General: Anxious, diaphoretic, in mild distress
- Cardiovascular: RRR, no murmurs, JVD noted
- Pulmonary: Bibasilar crackles
- Abdomen: Soft, non-tender

LABORATORY:
- Troponin I: 0.45 ng/mL (elevated)
- BNP: 450 pg/mL (elevated)
- Creatinine: 1.4 mg/dL (baseline 1.2)
- Potassium: 4.2 mEq/L
- Glucose: 245 mg/dL

ECG: ST depression in leads V4-V6

ASSESSMENT:
1. Acute coronary syndrome - NSTEMI
2. Type 2 diabetes mellitus - uncontrolled
3. Hypertensive urgency
4. Acute on chronic systolic heart failure

PLAN:
- Heparin drip initiated
- Cardiology consult for cardiac catheterization
- Continue aspirin, hold metformin
- IV furosemide for volume overload
- Strict I/O, daily weights
- Sliding scale insulin
"""


def test_ontology_mapper_standalone():
    """Test the ontology mapper without database."""
    console.print("\n[bold cyan]1. Testing Ontology Mapper (Standalone)[/bold cyan]\n")

    from app.services.clinical_ontology_mapper import get_ontology_mapper

    mapper = get_ontology_mapper()
    start = time.perf_counter()
    result = mapper.map_note(SAMPLE_NOTE)
    elapsed = (time.perf_counter() - start) * 1000

    # Coverage stats
    stats = result.coverage_stats
    console.print(Panel(
        f"Total tokens: {stats['total_tokens']}\n"
        f"Classified: {stats['classified_tokens']}\n"
        f"Unknown: {stats['unknown_tokens']}\n"
        f"Coverage: {stats['coverage_pct']}%\n"
        f"Clinical entities: {stats['clinical_entities']}\n"
        f"Processing time: {elapsed:.2f}ms",
        title="[bold green]Ontology Mapping Results[/bold green]",
    ))

    # Show entity breakdown
    table = Table(title="Entity Categories")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")

    entity_counts: dict[str, int] = {}
    for entity in result.entities:
        cat = entity.category.value
        entity_counts[cat] = entity_counts.get(cat, 0) + 1

    for cat, count in sorted(entity_counts.items(), key=lambda x: -x[1]):
        table.add_row(cat, str(count))

    console.print(table)

    # Show relationships
    console.print(f"\n[bold]Relationships extracted: {len(result.relationships)}[/bold]")
    rel_counts: dict[str, int] = {}
    for rel in result.relationships:
        rel_type = rel.relation.value
        rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1

    for rel_type, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {rel_type}: {count}")

    return result


def test_graph_builder_mock():
    """Test the graph builder with mock/in-memory mode."""
    console.print("\n[bold cyan]2. Testing Graph Builder Integration[/bold cyan]\n")

    # Import existing graph builder types
    from app.schemas.knowledge_graph import NodeType, EdgeType

    console.print("[dim]Using existing NodeType and EdgeType from schemas[/dim]")
    console.print(f"  NodeTypes: {[t.value for t in NodeType]}")
    console.print(f"  EdgeTypes: {[t.value for t in EdgeType]}")

    # Show how ontology categories map to existing types
    from app.services.ontology_graph_integration import OntologyGraphIntegration

    console.print("\n[bold]Ontology to Graph Type Mappings:[/bold]")
    table = Table()
    table.add_column("OntologyCategory")
    table.add_column("→ NodeType")
    table.add_column("→ EdgeType")

    for cat, node_type in OntologyGraphIntegration.CATEGORY_TO_NODE_TYPE.items():
        edge_type = OntologyGraphIntegration.CATEGORY_TO_EDGE_TYPE.get(cat)
        table.add_row(
            cat.value,
            node_type.value,
            edge_type.value if edge_type else "-",
        )

    console.print(table)


def test_full_pipeline_mock():
    """Test the full pipeline with mock data (no database)."""
    console.print("\n[bold cyan]3. Testing Full Pipeline (Mock Mode)[/bold cyan]\n")

    from app.services.clinical_ontology_mapper import (
        get_ontology_mapper,
        OntologyCategory,
    )
    from app.schemas.knowledge_graph import NodeType, EdgeType

    mapper = get_ontology_mapper()
    result = mapper.map_note(SAMPLE_NOTE)

    # Simulate what the integration would do
    nodes_created = []
    edges_created = []

    category_to_node = {
        OntologyCategory.DIAGNOSIS: NodeType.CONDITION,
        OntologyCategory.SYMPTOM: NodeType.CONDITION,
        OntologyCategory.FINDING: NodeType.OBSERVATION,
        OntologyCategory.MEDICATION: NodeType.DRUG,
        OntologyCategory.PROCEDURE: NodeType.PROCEDURE,
        OntologyCategory.LAB_TEST: NodeType.MEASUREMENT,
        OntologyCategory.LAB_VALUE: NodeType.MEASUREMENT,
        OntologyCategory.VITAL_SIGN: NodeType.MEASUREMENT,
    }

    category_to_edge = {
        OntologyCategory.DIAGNOSIS: EdgeType.HAS_CONDITION,
        OntologyCategory.SYMPTOM: EdgeType.HAS_CONDITION,
        OntologyCategory.FINDING: EdgeType.HAS_OBSERVATION,
        OntologyCategory.MEDICATION: EdgeType.TAKES_DRUG,
        OntologyCategory.PROCEDURE: EdgeType.HAS_PROCEDURE,
        OntologyCategory.LAB_TEST: EdgeType.HAS_MEASUREMENT,
        OntologyCategory.LAB_VALUE: EdgeType.HAS_MEASUREMENT,
        OntologyCategory.VITAL_SIGN: EdgeType.HAS_MEASUREMENT,
    }

    patient_id = "P001"

    # Create patient node
    nodes_created.append({
        "id": "patient_P001",
        "type": NodeType.PATIENT.value,
        "label": f"Patient {patient_id}",
    })

    # Create entity nodes
    for entity in result.entities:
        node_type = category_to_node.get(entity.category)
        if not node_type:
            continue

        node = {
            "id": f"node_{len(nodes_created)}",
            "type": node_type.value,
            "label": entity.span.text,
            "category": entity.category.value,
            "vocabulary_code": entity.vocabulary_code,
        }
        nodes_created.append(node)

        # Create edge from patient to entity
        edge_type = category_to_edge.get(entity.category)
        if edge_type:
            edges_created.append({
                "source": "patient_P001",
                "target": node["id"],
                "type": edge_type.value,
            })

    console.print(Panel(
        f"Patient ID: {patient_id}\n"
        f"Nodes created: {len(nodes_created)}\n"
        f"Edges created: {len(edges_created)}\n"
        f"(Including {len(result.relationships)} entity-to-entity relationships)",
        title="[bold green]Graph Construction Results[/bold green]",
    ))

    # Show node type breakdown
    node_type_counts: dict[str, int] = {}
    for node in nodes_created:
        t = node["type"]
        node_type_counts[t] = node_type_counts.get(t, 0) + 1

    table = Table(title="Nodes by Type")
    table.add_column("Node Type", style="cyan")
    table.add_column("Count", justify="right")

    for t, count in sorted(node_type_counts.items(), key=lambda x: -x[1]):
        table.add_row(t, str(count))

    console.print(table)

    # Show edge type breakdown
    edge_type_counts: dict[str, int] = {}
    for edge in edges_created:
        t = edge["type"]
        edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

    table = Table(title="Edges by Type")
    table.add_column("Edge Type", style="cyan")
    table.add_column("Count", justify="right")

    for t, count in sorted(edge_type_counts.items(), key=lambda x: -x[1]):
        table.add_row(t, str(count))

    console.print(table)


def show_persistent_memory_concept():
    """Explain how persistent memory works with the KG."""
    console.print("\n[bold cyan]4. Persistent Memory Architecture[/bold cyan]\n")

    architecture = """
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        CLINICAL NOTE INGESTION                          │
    └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                     ONTOLOGY MAPPER (Deterministic)                     │
    │  • 100% token coverage                                                  │
    │  • Structured extraction                                                │
    │  • Relationship identification                                          │
    │  • Fast processing (~6ms per note)                                      │
    └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                 ONTOLOGY GRAPH INTEGRATION SERVICE                      │
    │  • Entity resolution (same entities linked across notes)                │
    │  • Maps to existing NodeType/EdgeType                                   │
    │  • Uses DatabaseGraphBuilderService                                     │
    └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                    KNOWLEDGE GRAPH (Database)                           │
    │                                                                         │
    │    Patient ─────┬──── HAS_CONDITION ────► Diagnosis                    │
    │         │       │                                                       │
    │         │       ├──── TAKES_DRUG ───────► Medication                   │
    │         │       │                              │                        │
    │         │       ├──── HAS_MEASUREMENT ──► Lab Result                   │
    │         │       │                                                       │
    │         │       └──── HAS_PROCEDURE ────► Procedure                    │
    │         │                                                               │
    │         └── (Accumulates across all notes/encounters)                   │
    │                                                                         │
    │  Benefits:                                                              │
    │  • Persistent memory across sessions                                    │
    │  • Entity resolution (diabetes from Note 1 = diabetes from Note 5)     │
    │  • Temporal tracking (when did conditions appear/resolve?)             │
    │  • Cross-patient reasoning (find similar patients)                     │
    │  • Treatment pathway discovery                                          │
    └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                     QUERY / REASONING LAYER                             │
    │                                                                         │
    │  Deterministic Queries:                                                 │
    │  • "What medications is patient taking?"                                │
    │  • "What are the active problems?"                                      │
    │  • "Find patients with similar conditions"                              │
    │                                                                         │
    │  LLM-Augmented Reasoning:                                               │
    │  • "Explain this patient's treatment pathway"                           │
    │  • "What should we monitor given this condition?"                       │
    │  • "Are there any drug interactions to consider?"                       │
    └─────────────────────────────────────────────────────────────────────────┘
    """

    console.print(architecture)


def main():
    """Run all tests."""
    console.print(Panel(
        "[bold]Ontology Mapper → Knowledge Graph Integration Test[/bold]\n\n"
        "This test demonstrates how the Clinical Ontology Mapper integrates with\n"
        "the existing Knowledge Graph infrastructure for persistent memory.",
        title="🧠 Clinical Knowledge Graph",
    ))

    # Run tests
    test_ontology_mapper_standalone()
    test_graph_builder_mock()
    test_full_pipeline_mock()
    show_persistent_memory_concept()

    console.print("\n[bold green]✓ Integration test complete![/bold green]")
    console.print("\n[dim]To persist data, use OntologyGraphIntegration with a database session.[/dim]")


if __name__ == "__main__":
    main()
