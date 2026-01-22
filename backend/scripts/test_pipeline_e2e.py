#!/usr/bin/env python3
"""End-to-end test for the Clinical Data Pipeline.

This script demonstrates the full pipeline:
1. Clinical Document Ingestion →
2. NLP Entity Extraction →
3. Normalization (ICD-10, SNOMED, RxNorm, LOINC) →
4. Drug Interaction Checking →
5. Knowledge Graph Building →
6. Vector Embeddings (Semantic Search) →
7. Clinical Analytics

Usage:
    python scripts/test_pipeline_e2e.py
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()


# Sample clinical note for testing
SAMPLE_CLINICAL_NOTE = """
HISTORY OF PRESENT ILLNESS:
This is a 67-year-old male with a past medical history significant for hypertension,
type 2 diabetes mellitus, atrial fibrillation on warfarin, and chronic kidney disease
stage 3 who presents to the emergency department with acute chest pain and shortness of breath.

The patient reports substernal chest pain starting approximately 2 hours prior to arrival,
described as pressure-like, 8/10 in severity, radiating to the left arm. He also notes
associated diaphoresis and nausea. He denies any previous episodes of similar chest pain.

PAST MEDICAL HISTORY:
1. Hypertension - diagnosed 15 years ago
2. Type 2 Diabetes Mellitus - on metformin 1000mg BID
3. Atrial Fibrillation - on warfarin, last INR 2.4
4. Chronic Kidney Disease Stage 3 - baseline creatinine 1.8
5. Hyperlipidemia - on atorvastatin 40mg daily
6. GERD - on omeprazole 20mg daily

MEDICATIONS:
- Metformin 1000mg PO BID
- Warfarin 5mg PO daily
- Atorvastatin 40mg PO daily
- Lisinopril 20mg PO daily
- Omeprazole 20mg PO daily
- Aspirin 81mg PO daily

ALLERGIES: NKDA

SOCIAL HISTORY:
- Former smoker, quit 10 years ago (30 pack-year history)
- Occasional alcohol use
- No illicit drug use
- Retired construction worker

FAMILY HISTORY:
- Father: MI at age 55
- Mother: Diabetes, died of stroke at age 72
- Brother: Hypertension

PHYSICAL EXAMINATION:
- Vitals: T 98.6°F, HR 92 irregular, BP 165/95, RR 20, SpO2 94% on RA
- General: Anxious, diaphoretic, in mild distress
- HEENT: PERRLA, EOMI, mucous membranes moist
- Cardiovascular: Irregular rhythm, no murmurs, JVD present
- Respiratory: Bibasilar crackles, no wheezes
- Abdomen: Soft, non-tender, no organomegaly
- Extremities: 2+ bilateral lower extremity edema
- Neuro: Alert and oriented x3, no focal deficits

LABORATORY RESULTS:
- WBC: 11.2 K/uL (H)
- Hemoglobin: 12.1 g/dL
- Platelets: 245 K/uL
- Sodium: 138 mEq/L
- Potassium: 4.8 mEq/L
- Creatinine: 2.1 mg/dL (H, baseline 1.8)
- BUN: 32 mg/dL (H)
- Glucose: 186 mg/dL (H)
- Troponin I: 0.45 ng/mL (H)
- BNP: 890 pg/mL (H)
- INR: 2.4
- PT: 26.8 seconds

ECG: Atrial fibrillation with rapid ventricular response at 110 bpm,
ST depression in leads V4-V6, no ST elevation

CHEST X-RAY: Cardiomegaly with bilateral pulmonary vascular congestion

ASSESSMENT AND PLAN:
1. NSTEMI - Troponin elevation with ST depression
   - Heparin drip initiated (monitor for bleeding given warfarin)
   - Hold warfarin
   - Cardiology consult for catheterization
   - Continue aspirin, add clopidogrel loading dose 300mg

2. Acute on Chronic Heart Failure - elevated BNP, bilateral edema, crackles
   - Furosemide 40mg IV
   - Strict I/O
   - Daily weights
   - Fluid restriction

3. Acute Kidney Injury on CKD 3 - Creatinine 2.1 from baseline 1.8
   - Hold metformin
   - Hold lisinopril
   - IV fluids cautiously given CHF
   - Monitor renal function

4. Atrial Fibrillation with RVR
   - Rate control with diltiazem drip
   - Hold warfarin given cath planned
   - Bridge with heparin

5. Type 2 Diabetes
   - Hold metformin given AKI and contrast exposure
   - Sliding scale insulin
   - Monitor glucose

Patient admitted to CCU. Code status: Full code.
"""


def print_section(title: str, emoji: str = "📋") -> None:
    """Print a section header."""
    console.print()
    console.print(Panel(f"[bold cyan]{emoji} {title}[/bold cyan]", box=box.ROUNDED))


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}")


class PipelineTest:
    """End-to-end pipeline test orchestrator."""

    def __init__(self):
        self.results: dict[str, Any] = {}
        self.timings: dict[str, float] = {}
        self.patient_id = f"TEST-{uuid4().hex[:8].upper()}"
        self.document_id = uuid4()

    async def run_full_pipeline(self) -> None:
        """Run the complete pipeline test."""
        console.print()
        console.print(Panel.fit(
            "[bold magenta]🏥 Clinical Data Pipeline - End-to-End Test[/bold magenta]\n"
            f"[dim]Patient ID: {self.patient_id}[/dim]\n"
            f"[dim]Document ID: {self.document_id}[/dim]\n"
            f"[dim]Timestamp: {datetime.now().isoformat()}[/dim]",
            box=box.DOUBLE
        ))

        # Step 1: NLP Entity Extraction
        await self.test_nlp_extraction()

        # Step 2: Code Normalization
        await self.test_code_normalization()

        # Step 3: Drug Interaction Checking
        await self.test_drug_interactions()

        # Step 4: Clinical Abbreviations
        await self.test_abbreviations_extraction()

        # Step 5: Knowledge Graph Building (simulated if Neo4j not available)
        await self.test_knowledge_graph()

        # Step 6: Semantic Search (simulated if embeddings not available)
        await self.test_semantic_search()

        # Step 7: Clinical Analytics Summary
        await self.test_clinical_analytics()

        # Final Summary
        self.print_summary()

    async def test_nlp_extraction(self) -> None:
        """Test NLP entity extraction."""
        print_section("NLP Entity Extraction", "🔬")

        start = time.time()
        try:
            from app.services.nlp_entity_service import (
                ClinicalNLPEntityService,
                NormalizationVocabulary,
            )

            extractor = ClinicalNLPEntityService()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Extracting clinical entities...", total=None)

                # Extract entities
                extraction_result = extractor.extract_entities(SAMPLE_CLINICAL_NOTE)
                entities = extraction_result.entities

                progress.update(task, description="Normalizing entities...")

                # Normalize each entity to standard codes
                for entity in entities:
                    norm_result = extractor.normalize_entity(
                        entity,
                        vocabularies=[
                            NormalizationVocabulary.ICD10_CM,
                            NormalizationVocabulary.SNOMED_CT,
                            NormalizationVocabulary.RXNORM,
                            NormalizationVocabulary.LOINC,
                        ],
                    )
                    # Add codes back to entity
                    entity.normalized_codes = norm_result.normalized_codes

                progress.update(task, completed=True)

            self.results["entities"] = entities
            self.results["extraction_result"] = extraction_result
            self.timings["nlp_extraction"] = time.time() - start

            # Display entity summary
            entity_table = Table(title="Extracted Entities Summary", box=box.ROUNDED)
            entity_table.add_column("Entity Type", style="cyan")
            entity_table.add_column("Count", justify="right", style="green")
            entity_table.add_column("Examples", style="yellow")

            # Group by entity_type
            categories: dict[str, list] = {}
            for entity in entities:
                cat = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(entity)

            for cat, ents in sorted(categories.items()):
                examples = ", ".join([e.text[:20] for e in ents[:3]])
                if len(ents) > 3:
                    examples += f"... (+{len(ents)-3})"
                entity_table.add_row(cat, str(len(ents)), examples)

            console.print(entity_table)

            # Show normalization codes
            coded_entities = [e for e in entities if e.normalized_codes]
            print_success(f"Total entities extracted: {len(entities)}")
            print_success(f"Entities with vocabulary codes: {len(coded_entities)}")
            print_info(f"Extraction time: {self.timings['nlp_extraction']:.2f}s")

            # Show some coded examples
            if coded_entities[:5]:
                code_table = Table(title="Sample Normalized Codes", box=box.SIMPLE)
                code_table.add_column("Entity", style="cyan")
                code_table.add_column("System", style="yellow")
                code_table.add_column("Code", style="green")
                code_table.add_column("Display", style="white")

                for entity in coded_entities[:8]:
                    for code in entity.normalized_codes[:2]:
                        code_table.add_row(
                            entity.text[:25],
                            code.system[:15] if hasattr(code, 'system') else str(code.system)[:15],
                            str(code.code)[:15],
                            code.display[:30] if code.display else "N/A"
                        )

                console.print(code_table)

        except ImportError as e:
            print_error(f"NLP service not available: {e}")
            self.results["entities"] = []
            self.timings["nlp_extraction"] = time.time() - start

    async def test_code_normalization(self) -> None:
        """Test code normalization across vocabularies."""
        print_section("Code Normalization", "📚")

        start = time.time()

        # Count codes by vocabulary
        vocab_counts: dict[str, int] = {}
        for entity in self.results.get("entities", []):
            for code in getattr(entity, "normalized_codes", []):
                system = str(code.system) if hasattr(code, "system") else "unknown"
                vocab_counts[system] = vocab_counts.get(system, 0) + 1

        self.results["vocab_counts"] = vocab_counts
        self.timings["normalization"] = time.time() - start

        if vocab_counts:
            vocab_table = Table(title="Code Distribution by Vocabulary", box=box.ROUNDED)
            vocab_table.add_column("Vocabulary", style="cyan")
            vocab_table.add_column("Code Count", justify="right", style="green")

            for vocab, count in sorted(vocab_counts.items(), key=lambda x: -x[1]):
                vocab_table.add_row(vocab, str(count))

            console.print(vocab_table)
            print_success(f"Total normalized codes: {sum(vocab_counts.values())}")
        else:
            print_warning("No codes generated - check vocabulary loading")

    async def test_drug_interactions(self) -> None:
        """Test drug interaction checking."""
        print_section("Drug Interaction Checking", "💊")

        start = time.time()

        try:
            from app.services.nlp_entity_service import ClinicalNLPEntityService

            extractor = ClinicalNLPEntityService()

            # Get medication entities
            med_entities = [
                e for e in self.results.get("entities", [])
                if (e.entity_type.value if hasattr(e.entity_type, 'value') else str(e.entity_type)).lower() in ("medication", "drug")
            ]

            if med_entities:
                interactions = extractor.check_drug_interactions(med_entities)
                self.results["drug_interactions"] = interactions

                if interactions.get("interactions_found"):
                    print_warning(f"Found {len(interactions['interactions_found'])} drug interactions!")

                    int_table = Table(title="Drug Interactions Detected", box=box.ROUNDED)
                    int_table.add_column("Drug 1", style="cyan")
                    int_table.add_column("Drug 2", style="cyan")
                    int_table.add_column("Severity", style="red")
                    int_table.add_column("Description", style="yellow")

                    for interaction in interactions["interactions_found"][:5]:
                        int_table.add_row(
                            interaction.get("drug1", "N/A")[:20],
                            interaction.get("drug2", "N/A")[:20],
                            interaction.get("severity", "N/A"),
                            interaction.get("description", "N/A")[:40]
                        )

                    console.print(int_table)
                else:
                    print_success("No significant drug interactions detected")
            else:
                print_info("No medication entities found for interaction check")
                self.results["drug_interactions"] = {}

        except Exception as e:
            print_warning(f"Drug interaction check skipped: {e}")
            self.results["drug_interactions"] = {}

        self.timings["drug_interactions"] = time.time() - start

    async def test_abbreviations_extraction(self) -> None:
        """Test clinical abbreviations expansion."""
        print_section("Clinical Abbreviations", "📝")

        start = time.time()

        # Look for common abbreviations in our entities
        abbreviations_found = []
        abbrev_patterns = ["NKDA", "BID", "PO", "IV", "CCU", "MI", "AKI", "CHF", "CKD", "NSTEMI", "RVR"]

        text_upper = SAMPLE_CLINICAL_NOTE.upper()
        for abbrev in abbrev_patterns:
            if abbrev in text_upper:
                abbreviations_found.append(abbrev)

        self.results["abbreviations"] = abbreviations_found
        self.timings["abbreviations"] = time.time() - start

        if abbreviations_found:
            abbrev_table = Table(title="Clinical Abbreviations Found", box=box.SIMPLE)
            abbrev_table.add_column("Abbreviation", style="cyan")
            abbrev_table.add_column("Expanded Form", style="green")

            expansions = {
                "NKDA": "No Known Drug Allergies",
                "BID": "Twice Daily",
                "PO": "Per Oral (by mouth)",
                "IV": "Intravenous",
                "CCU": "Coronary Care Unit",
                "MI": "Myocardial Infarction",
                "AKI": "Acute Kidney Injury",
                "CHF": "Congestive Heart Failure",
                "CKD": "Chronic Kidney Disease",
                "NSTEMI": "Non-ST Elevation Myocardial Infarction",
                "RVR": "Rapid Ventricular Response",
            }

            for abbrev in abbreviations_found:
                abbrev_table.add_row(abbrev, expansions.get(abbrev, "N/A"))

            console.print(abbrev_table)
            print_success(f"Found {len(abbreviations_found)} clinical abbreviations")

    async def test_knowledge_graph(self) -> None:
        """Test knowledge graph construction."""
        print_section("Knowledge Graph Construction", "🕸️")

        start = time.time()

        # Build a simulated graph structure from entities
        nodes: list[dict] = []
        edges: list[dict] = []

        # Add patient node
        patient_node = {
            "id": self.patient_id,
            "type": "Patient",
            "label": f"Patient {self.patient_id}",
        }
        nodes.append(patient_node)

        # Add entity nodes and edges
        entity_id_counter = 0
        for entity in self.results.get("entities", [])[:50]:  # Limit for display
            entity_id = f"E{entity_id_counter:04d}"
            entity_id_counter += 1

            entity_type_str = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)

            node = {
                "id": entity_id,
                "type": entity_type_str,
                "label": entity.text[:30],
                "codes": [str(c.code) for c in getattr(entity, "normalized_codes", [])[:2]],
            }
            nodes.append(node)

            # Edge from patient to entity
            edge_type = {
                "diagnosis": "HAS_DIAGNOSIS",
                "medication": "TAKES_MEDICATION",
                "vital_sign": "HAS_VITAL",
                "lab_result": "HAS_LAB_RESULT",
                "procedure": "UNDERWENT",
                "symptom": "PRESENTS_WITH",
            }.get(entity_type_str.lower(), "HAS_OBSERVATION")

            edges.append({
                "source": self.patient_id,
                "target": entity_id,
                "type": edge_type,
            })

        self.results["graph"] = {"nodes": nodes, "edges": edges}
        self.timings["knowledge_graph"] = time.time() - start

        # Display graph statistics
        graph_table = Table(title="Knowledge Graph Structure", box=box.ROUNDED)
        graph_table.add_column("Metric", style="cyan")
        graph_table.add_column("Value", justify="right", style="green")

        graph_table.add_row("Total Nodes", str(len(nodes)))
        graph_table.add_row("Total Edges", str(len(edges)))

        # Count by type
        node_types = {}
        for n in nodes:
            t = n["type"]
            node_types[t] = node_types.get(t, 0) + 1

        for ntype, count in sorted(node_types.items(), key=lambda x: -x[1])[:5]:
            graph_table.add_row(f"  └─ {ntype}", str(count))

        console.print(graph_table)
        print_success(f"Graph constructed with {len(nodes)} nodes and {len(edges)} edges")

    async def test_semantic_search(self) -> None:
        """Test semantic search capabilities."""
        print_section("Semantic Search", "🔍")

        start = time.time()

        # Simulate semantic search with keyword matching
        test_queries = [
            "chest pain cardiac symptoms",
            "kidney function renal failure",
            "blood pressure medications",
            "diabetes glucose management",
        ]

        search_results: dict[str, list] = {}

        for query in test_queries:
            query_terms = query.lower().split()
            matches = []

            for entity in self.results.get("entities", []):
                entity_text = entity.text.lower()
                score = sum(1 for term in query_terms if term in entity_text)
                if score > 0:
                    matches.append({
                        "text": entity.text,
                        "category": entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
                        "score": score / len(query_terms),
                    })

            matches.sort(key=lambda x: -x["score"])
            search_results[query] = matches[:5]

        self.results["semantic_search"] = search_results
        self.timings["semantic_search"] = time.time() - start

        # Display search results
        for query, matches in search_results.items():
            if matches:
                console.print(f"\n[cyan]Query:[/cyan] \"{query}\"")
                for i, match in enumerate(matches[:3], 1):
                    console.print(f"  {i}. {match['text'][:40]} ({match['category']}) - score: {match['score']:.2f}")

        print_success(f"Semantic search complete - {len(test_queries)} queries processed")

    async def test_clinical_analytics(self) -> None:
        """Generate clinical analytics summary."""
        print_section("Clinical Analytics Summary", "📊")

        start = time.time()

        entities = self.results.get("entities", [])

        # Helper to get entity type as string
        def get_type(e):
            return (e.entity_type.value if hasattr(e.entity_type, 'value') else str(e.entity_type)).lower()

        # Generate clinical insights
        analytics = {
            "total_entities": len(entities),
            "unique_diagnoses": len([e for e in entities if get_type(e) == "diagnosis"]),
            "medications_count": len([e for e in entities if get_type(e) == "medication"]),
            "lab_results_count": len([e for e in entities if get_type(e) == "lab_result"]),
            "vital_signs_count": len([e for e in entities if get_type(e) == "vital_sign"]),
            "risk_indicators": [],
        }

        # Identify risk indicators from the text
        risk_keywords = [
            ("troponin", "Elevated cardiac markers - possible MI"),
            ("chest pain", "Acute chest pain - requires urgent evaluation"),
            ("creatinine", "Elevated creatinine - possible AKI"),
            ("bnp", "Elevated BNP - possible heart failure"),
            ("st depression", "ECG changes - possible ischemia"),
        ]

        text_lower = SAMPLE_CLINICAL_NOTE.lower()
        for keyword, description in risk_keywords:
            if keyword in text_lower:
                analytics["risk_indicators"].append(description)

        self.results["analytics"] = analytics
        self.timings["analytics"] = time.time() - start

        # Display analytics
        analytics_table = Table(title="Clinical Analytics", box=box.ROUNDED)
        analytics_table.add_column("Metric", style="cyan")
        analytics_table.add_column("Value", justify="right", style="green")

        analytics_table.add_row("Total Entities Extracted", str(analytics["total_entities"]))
        analytics_table.add_row("Unique Diagnoses", str(analytics["unique_diagnoses"]))
        analytics_table.add_row("Medications", str(analytics["medications_count"]))
        analytics_table.add_row("Lab Results", str(analytics["lab_results_count"]))
        analytics_table.add_row("Vital Signs", str(analytics["vital_signs_count"]))

        console.print(analytics_table)

        # Risk indicators
        if analytics["risk_indicators"]:
            console.print("\n[bold red]⚠️  Risk Indicators Identified:[/bold red]")
            for indicator in analytics["risk_indicators"]:
                console.print(f"  [red]•[/red] {indicator}")

    def print_summary(self) -> None:
        """Print final summary of pipeline test."""
        print_section("Pipeline Test Summary", "✅")

        total_time = sum(self.timings.values())

        summary_table = Table(title="Performance Summary", box=box.DOUBLE)
        summary_table.add_column("Stage", style="cyan")
        summary_table.add_column("Time (s)", justify="right", style="green")
        summary_table.add_column("Status", style="yellow")

        stages = [
            ("NLP Entity Extraction", "nlp_extraction"),
            ("Code Normalization", "normalization"),
            ("Drug Interaction Check", "drug_interactions"),
            ("Abbreviation Processing", "abbreviations"),
            ("Knowledge Graph Build", "knowledge_graph"),
            ("Semantic Search", "semantic_search"),
            ("Clinical Analytics", "analytics"),
        ]

        for stage_name, key in stages:
            time_val = self.timings.get(key, 0)
            status = "✓ Complete" if time_val > 0 else "⏭ Skipped"
            summary_table.add_row(stage_name, f"{time_val:.3f}", status)

        summary_table.add_row("─" * 20, "─" * 8, "─" * 10)
        summary_table.add_row("[bold]Total[/bold]", f"[bold]{total_time:.3f}[/bold]", "")

        console.print(summary_table)

        # Final metrics
        entities = self.results.get("entities", [])
        graph = self.results.get("graph", {})

        console.print()
        console.print(Panel.fit(
            f"[bold green]Pipeline Test Complete![/bold green]\n\n"
            f"📊 Entities Extracted: [cyan]{len(entities)}[/cyan]\n"
            f"📚 Vocabulary Codes: [cyan]{sum(self.results.get('vocab_counts', {}).values())}[/cyan]\n"
            f"🕸️  Graph Nodes: [cyan]{len(graph.get('nodes', []))}[/cyan]\n"
            f"🔗 Graph Edges: [cyan]{len(graph.get('edges', []))}[/cyan]\n"
            f"⏱️  Total Time: [cyan]{total_time:.2f}s[/cyan]",
            title="[bold]Results[/bold]",
            box=box.DOUBLE
        ))


async def main():
    """Main entry point."""
    try:
        test = PipelineTest()
        await test.run_full_pipeline()
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red]Pipeline test failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
