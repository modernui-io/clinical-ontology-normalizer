#!/usr/bin/env python3
"""Test the Hybrid Clinical Analyzer.

Demonstrates how deterministic ontology mapping combines with LLM reasoning
for grounded clinical analysis.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()


SAMPLE_NOTE = """
65-year-old male with history of type 2 diabetes mellitus, hypertension, and
atrial fibrillation presents with chest pain and shortness of breath.

HISTORY OF PRESENT ILLNESS:
Patient reports substernal chest pain radiating to left arm, started 3 hours ago.
Pain is described as pressure-like, 8/10 severity. Associated with diaphoresis
and nausea. He denies fever, cough, or leg swelling.

MEDICATIONS:
- Aspirin 81mg daily
- Metformin 1000mg twice daily
- Lisinopril 20mg daily
- Warfarin 5mg daily
- Metoprolol 50mg twice daily

ALLERGIES: Penicillin (rash)

PHYSICAL EXAMINATION:
- Vital Signs: BP 150/95, HR 92 irregular, RR 20, SpO2 94% on RA
- General: Anxious, diaphoretic
- Cardiovascular: Irregular rhythm, no murmurs
- Pulmonary: Bibasilar crackles
- Abdomen: Soft, non-tender

LABORATORY:
- Troponin I: 0.45 ng/mL (elevated)
- BNP: 450 pg/mL (elevated)
- Creatinine: 1.4 mg/dL
- INR: 2.3
- Potassium: 4.2 mEq/L
- Glucose: 245 mg/dL

ECG: ST depression in leads V4-V6, atrial fibrillation

ASSESSMENT:
1. Acute coronary syndrome - likely NSTEMI
2. Atrial fibrillation with RVR
3. Acute on chronic heart failure
4. Type 2 diabetes - uncontrolled
"""


def test_deterministic_extraction():
    """Test the deterministic extraction layer (no LLM)."""
    console.print("\n[bold cyan]1. DETERMINISTIC EXTRACTION (No LLM)[/bold cyan]\n")

    from app.services.hybrid_clinical_analyzer import HybridClinicalAnalyzer

    analyzer = HybridClinicalAnalyzer()

    # Extract without LLM
    import time
    start = time.perf_counter()
    context = analyzer.extract_only(SAMPLE_NOTE)
    elapsed = (time.perf_counter() - start) * 1000

    console.print(Panel(
        f"Processing time: {elapsed:.2f}ms\n"
        f"Coverage: {context.coverage_pct}%\n"
        f"Total entities: {context.entity_count}",
        title="[bold green]Extraction Stats[/bold green]",
    ))

    # Show extracted entities
    table = Table(title="Extracted Entities")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Examples")

    categories = [
        ("Diagnoses", context.diagnoses),
        ("Medications", context.medications),
        ("Labs", context.labs),
        ("Vitals", context.vitals),
        ("Symptoms", context.symptoms),
        ("Findings", context.findings),
        ("Procedures", context.procedures),
    ]

    for name, items in categories:
        if items:
            examples = ", ".join([i["name"] for i in items[:3]])
            if len(items) > 3:
                examples += f" (+{len(items)-3} more)"
            table.add_row(name, str(len(items)), examples)

    console.print(table)

    # Show negated findings
    if context.negated_findings:
        console.print(f"\n[yellow]Negated findings:[/yellow] {', '.join(context.negated_findings)}")

    # Show relationships
    if context.relationships:
        console.print(f"\n[bold]Relationships ({len(context.relationships)}):[/bold]")
        for rel in context.relationships[:5]:
            console.print(f"  {rel['subject']} → {rel['relation']} → {rel['object']}")

    return context


def test_structured_context_format():
    """Show the structured context format sent to LLM."""
    console.print("\n[bold cyan]2. STRUCTURED CONTEXT (Sent to LLM)[/bold cyan]\n")

    from app.services.hybrid_clinical_analyzer import HybridClinicalAnalyzer

    analyzer = HybridClinicalAnalyzer()
    context = analyzer.extract_only(SAMPLE_NOTE)

    prompt_context = context.to_prompt_context()

    console.print(Panel(
        prompt_context,
        title="[bold green]Context for LLM Grounding[/bold green]",
        border_style="green",
    ))

    console.print("\n[dim]This structured context is provided to the LLM, which can ONLY reason over these extracted entities.[/dim]")


async def test_hybrid_analysis():
    """Test the full hybrid analysis (with LLM if available)."""
    console.print("\n[bold cyan]3. HYBRID ANALYSIS (Deterministic + LLM)[/bold cyan]\n")

    from app.services.hybrid_clinical_analyzer import (
        HybridClinicalAnalyzer,
        AnalysisType,
    )

    analyzer = HybridClinicalAnalyzer()

    try:
        # Try clinical summary
        console.print("[dim]Calling LLM for clinical summary...[/dim]")
        result = await analyzer.analyze(
            note_text=SAMPLE_NOTE,
            analysis_type=AnalysisType.CLINICAL_SUMMARY,
        )

        console.print(Panel(
            f"Extraction time: {result.extraction_time_ms}ms\n"
            f"LLM time: {result.llm_time_ms}ms\n"
            f"Total time: {result.total_time_ms}ms\n"
            f"Model: {result.llm_model}\n"
            f"Tokens: {result.llm_tokens_used}\n"
            f"Cost: ${result.llm_cost_usd:.4f}",
            title="[bold green]Analysis Stats[/bold green]",
        ))

        console.print("\n[bold]LLM Analysis (grounded in structured extraction):[/bold]\n")
        console.print(Markdown(result.analysis))

    except Exception as e:
        console.print(f"\n[yellow]LLM not available: {e}[/yellow]")
        console.print("[dim]Falling back to structured extraction only...[/dim]\n")

        # Show what the LLM would receive
        context = analyzer.extract_only(SAMPLE_NOTE)
        console.print(Panel(
            context.to_prompt_context(),
            title="[bold yellow]Structured Data (LLM would reason over this)[/bold yellow]",
        ))


async def test_question_answering():
    """Test question answering capability."""
    console.print("\n[bold cyan]4. QUESTION ANSWERING[/bold cyan]\n")

    from app.services.hybrid_clinical_analyzer import HybridClinicalAnalyzer

    analyzer = HybridClinicalAnalyzer()

    questions = [
        "What medications is this patient taking?",
        "Are there any abnormal lab values?",
        "What is the patient's cardiac status?",
    ]

    for question in questions:
        console.print(f"\n[bold]Q: {question}[/bold]")

        try:
            result = await analyzer.answer_question(SAMPLE_NOTE, question)
            console.print(f"[green]A: {result.analysis[:500]}...[/green]" if len(result.analysis) > 500 else f"[green]A: {result.analysis}[/green]")
        except Exception as e:
            # Fall back to showing extracted data
            context = analyzer.extract_only(SAMPLE_NOTE)
            if "medication" in question.lower():
                meds = [m["name"] for m in context.medications]
                console.print(f"[yellow]A (from extraction): {', '.join(meds)}[/yellow]")
            elif "lab" in question.lower():
                labs = [f"{l['name']}" for l in context.labs]
                console.print(f"[yellow]A (from extraction): {', '.join(labs)}[/yellow]")
            else:
                console.print(f"[yellow]LLM unavailable, but extracted {context.entity_count} entities[/yellow]")


def show_architecture():
    """Show the hybrid architecture."""
    console.print("\n[bold cyan]5. HYBRID ARCHITECTURE[/bold cyan]\n")

    architecture = """
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HYBRID CLINICAL ANALYZER                             │
│                                                                             │
│  Combines deterministic extraction with LLM reasoning for grounded analysis │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: DETERMINISTIC EXTRACTION (Ontology Mapper)                         │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • 100% token coverage                                                      │
│  • ~1ms processing time                                                     │
│  • No hallucination risk                                                    │
│  • Reproducible output                                                      │
│                                                                             │
│  Output: StructuredContext                                                  │
│    ├── diagnoses: [{name, code, negated}, ...]                             │
│    ├── medications: [{name, dose, frequency}, ...]                         │
│    ├── labs: [{name, value, unit}, ...]                                    │
│    ├── vitals: [{name, value}, ...]                                        │
│    ├── symptoms: [{name, negated}, ...]                                    │
│    └── relationships: [{subject, relation, object}, ...]                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: LLM REASONING (Grounded in Structured Data)                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • System prompt enforces grounding                                         │
│  • LLM can ONLY cite extracted entities                                     │
│  • Clinical reasoning over verified facts                                   │
│  • Multiple analysis types:                                                 │
│    - Clinical Summary                                                       │
│    - Risk Assessment                                                        │
│    - Medication Review                                                      │
│    - Lab Interpretation                                                     │
│    - Question Answering                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: HybridAnalysisResult                                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • Grounded analysis text                                                   │
│  • Full structured context                                                  │
│  • Timing breakdown (extraction vs LLM)                                     │
│  • Token usage and cost                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

BENEFITS:
─────────
✓ Reduced hallucination - LLM cites extracted entities
✓ Deterministic foundation - Reproducible extraction
✓ Fast extraction - ~1ms for structure, LLM for reasoning
✓ Auditable - Clear separation of fact vs inference
✓ Graceful degradation - Works without LLM (extraction only)
"""

    console.print(architecture)


async def main():
    """Run all tests."""
    console.print(Panel(
        "[bold]Hybrid Clinical Analyzer Test[/bold]\n\n"
        "Demonstrates how deterministic ontology mapping combines with\n"
        "LLM reasoning for grounded clinical analysis.",
        title="🧠 Hybrid Analysis",
    ))

    # Run tests
    test_deterministic_extraction()
    test_structured_context_format()
    await test_hybrid_analysis()
    await test_question_answering()
    show_architecture()

    console.print("\n[bold green]✓ Hybrid analyzer test complete![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
