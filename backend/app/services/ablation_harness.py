"""Five-Condition Ablation Harness — NeurIPS 2026.

Orchestrates the core paper experiment: running a question set through
5 progressively richer system conditions and collecting metrics.

Conditions:
  C1: LLM alone          — raw note text, no retrieval
  C2: LLM + vanilla RAG  — document retrieval only, no graph/assertion/temporal
  C3: LLM + KG-RAG       — graph + document retrieval, no assertion/temporal
  C4: LLM + epistemic    — graph + doc + full assertion + bi-temporal
  C5: Full system         — everything + calculators + clinical guidelines

Output:
  - Per-condition accuracy, category breakdown, safety scores
  - Markdown comparison table (for paper)
  - LaTeX table export
  - JSON export for further analysis
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.qa_experiment_executor import (
    QAExperimentExecutor,
    QARunConfig,
    print_ablation_table,
)
from app.services.qa_evaluation import (
    ASSERTION_QUESTIONS,
    RAG_QUESTIONS,
    TEMPORAL_QUESTIONS,
    QAEvaluationReport,
    QAEvaluationService,
    QAQuestion,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Condition definitions
# ============================================================================

ABLATION_CONDITIONS: dict[str, dict[str, Any]] = {
    "C1_llm_alone": {
        "label": "LLM Alone",
        "description": "Raw clinical note sent to LLM, no retrieval or enrichment",
        "raw_note_only": True,
        "retrieval_mode": "doc_only",  # not used when raw_note_only=True
        "assertion_mode": "none",
        "temporal_mode": "no_temporal",
        "calculator_enabled": False,
        "guidelines_enabled": False,
    },
    "C2_vanilla_rag": {
        "label": "LLM + Vanilla RAG",
        "description": "Document retrieval only, no graph traversal or enrichment",
        "raw_note_only": False,
        "retrieval_mode": "doc_only",
        "assertion_mode": "none",
        "temporal_mode": "no_temporal",
        "calculator_enabled": False,
        "guidelines_enabled": False,
    },
    "C3_kg_rag": {
        "label": "LLM + KG-RAG",
        "description": "Graph + document retrieval, no assertion/temporal enrichment",
        "raw_note_only": False,
        "retrieval_mode": "graph_plus_doc",
        "assertion_mode": "none",
        "temporal_mode": "no_temporal",
        "calculator_enabled": False,
        "guidelines_enabled": False,
    },
    "C4_epistemic_kg_rag": {
        "label": "LLM + Epistemic KG-RAG",
        "description": "Graph + doc + full assertion classification + bi-temporal model",
        "raw_note_only": False,
        "retrieval_mode": "graph_plus_doc",
        "assertion_mode": "full",
        "temporal_mode": "full_bitemporal",
        "calculator_enabled": False,
        "guidelines_enabled": False,
    },
    "C5_full_system": {
        "label": "Full System",
        "description": "Everything: graph + doc + guidelines + assertion + temporal + calculators",
        "raw_note_only": False,
        "retrieval_mode": "graph_plus_doc_plus_guidelines",
        "assertion_mode": "full",
        "temporal_mode": "full_bitemporal",
        "calculator_enabled": True,
        "guidelines_enabled": True,
    },
}


@dataclass
class ConditionResult:
    """Result for a single ablation condition."""

    condition_id: str
    condition_label: str
    report: QAEvaluationReport
    safety_score: float
    latency_ms: float
    config_snapshot: dict[str, Any]


@dataclass
class AblationResult:
    """Complete result of a 5-condition ablation run."""

    ablation_id: str
    run_at: datetime
    patient_id: str
    question_set_name: str
    total_questions: int
    llm_model: str
    conditions: dict[str, ConditionResult]
    total_duration_s: float = 0.0

    def to_markdown_table(self) -> str:
        """Generate markdown comparison table for the paper."""
        qa_svc = QAEvaluationService()

        # Collect all categories across conditions
        all_cats = sorted({
            cat
            for cr in self.conditions.values()
            for cat in cr.report.category_accuracies
        })

        # Header
        cat_headers = " | ".join(all_cats) if all_cats else ""
        header = f"| Condition | Accuracy | {cat_headers} | Safety | Latency (ms) |"
        separator = f"|---|---|{'|'.join('---' for _ in all_cats)}|---|---|"

        lines = [header, separator]

        for cid, cr in self.conditions.items():
            acc = f"{cr.report.accuracy:.1%}"
            cat_values = " | ".join(
                f"{cr.report.category_accuracies.get(cat, 0.0):.1%}"
                for cat in all_cats
            )
            safety = f"{cr.safety_score:.3f}"
            latency = f"{cr.latency_ms:.0f}"
            lines.append(
                f"| {cr.condition_label} | {acc} | {cat_values} | {safety} | {latency} |"
            )

        return "\n".join(lines)

    def to_latex_table(self) -> str:
        """Generate LaTeX table for the paper."""
        all_cats = sorted({
            cat
            for cr in self.conditions.values()
            for cat in cr.report.category_accuracies
        })

        n_cols = 3 + len(all_cats)  # Condition + Accuracy + cats... + Safety
        col_spec = "l" + "c" * (n_cols - 1)

        cat_headers = " & ".join(f"\\textbf{{{cat.replace('_', ' ').title()}}}" for cat in all_cats)
        header_row = f"\\textbf{{Condition}} & \\textbf{{Accuracy}} & {cat_headers} & \\textbf{{Safety}}"

        lines = [
            f"\\begin{{tabular}}{{{col_spec}}}",
            "\\toprule",
            f"{header_row} \\\\",
            "\\midrule",
        ]

        for cid, cr in self.conditions.items():
            acc = f"{cr.report.accuracy:.1%}"
            cat_values = " & ".join(
                f"{cr.report.category_accuracies.get(cat, 0.0):.1%}"
                for cat in all_cats
            )
            safety = f"{cr.safety_score:.3f}"
            label = cr.condition_label.replace("&", "\\&")
            lines.append(f"{label} & {acc} & {cat_values} & {safety} \\\\")

        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
        ])

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """Export full result as JSON-serializable dict."""
        conditions_json = {}
        for cid, cr in self.conditions.items():
            conditions_json[cid] = {
                "label": cr.condition_label,
                "accuracy": cr.report.accuracy,
                "total_questions": cr.report.total_questions,
                "correct": cr.report.correct,
                "category_accuracies": cr.report.category_accuracies,
                "safety_score": cr.safety_score,
                "avg_latency_ms": cr.report.avg_latency_ms,
                "config": cr.config_snapshot,
                "per_question": [
                    {
                        "question_id": r.question_id,
                        "category": r.category,
                        "correct": r.correct,
                        "score": r.score,
                        "predicted_answer": r.predicted_answer[:200],
                        "expected_answer": r.expected_answer[:200],
                        "latency_ms": r.latency_ms,
                        "error": r.error,
                    }
                    for r in cr.report.results
                ],
            }

        return {
            "ablation_id": self.ablation_id,
            "run_at": self.run_at.isoformat(),
            "patient_id": self.patient_id,
            "question_set_name": self.question_set_name,
            "total_questions": self.total_questions,
            "llm_model": self.llm_model,
            "total_duration_s": self.total_duration_s,
            "conditions": conditions_json,
        }

    def compute_deltas(self) -> dict[str, dict[str, float]]:
        """Compute accuracy deltas between consecutive conditions.

        Returns dict mapping condition pairs to accuracy improvement.
        """
        cond_list = list(self.conditions.values())
        deltas = {}
        for i in range(1, len(cond_list)):
            prev = cond_list[i - 1]
            curr = cond_list[i]
            delta_key = f"{prev.condition_id}→{curr.condition_id}"
            deltas[delta_key] = {
                "accuracy_delta": curr.report.accuracy - prev.report.accuracy,
                "safety_delta": curr.safety_score - prev.safety_score,
            }
            # Per-category deltas
            all_cats = set(prev.report.category_accuracies) | set(curr.report.category_accuracies)
            for cat in all_cats:
                prev_acc = prev.report.category_accuracies.get(cat, 0.0)
                curr_acc = curr.report.category_accuracies.get(cat, 0.0)
                deltas[delta_key][f"{cat}_delta"] = curr_acc - prev_acc
        return deltas


class AblationHarness:
    """Orchestrates the 5-condition ablation experiment.

    Usage:
        harness = AblationHarness()
        result = await harness.run(
            patient_id="P001",
            questions=ASSERTION_QUESTIONS,
            question_set_name="assertion_50",
        )
        print(result.to_markdown_table())
        print(result.to_latex_table())
    """

    def __init__(
        self,
        conditions: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the ablation harness.

        Args:
            conditions: Override default 5-condition definitions.
        """
        self.conditions = conditions or ABLATION_CONDITIONS
        self.executor = QAExperimentExecutor()
        self.qa_service = QAEvaluationService()

    async def run(
        self,
        patient_id: str,
        questions: list[QAQuestion],
        question_set_name: str = "default",
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
        run_id: str | None = None,
        use_llm_judge: bool = False,
        condition_ids: list[str] | None = None,
        ollama_base_url: str = "http://localhost:11434",
    ) -> AblationResult:
        """Run the full 5-condition ablation.

        Args:
            patient_id: Patient to evaluate against.
            questions: Question set to run.
            question_set_name: Name for logging/export.
            llm_model: LLM model to use for QA.
            llm_provider: LLM provider (anthropic/openai/ollama).
            run_id: Optional research run ID for metric tracking.
            use_llm_judge: Use LLM judge scoring instead of keywords.
            condition_ids: Optional subset of conditions to run (e.g., ["C1_llm_alone", "C5_full_system"]).

        Returns:
            AblationResult with all condition results and export methods.
        """
        ablation_id = f"ablation_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        t0 = time.perf_counter()

        # Select conditions
        selected = self.conditions
        if condition_ids:
            selected = {k: v for k, v in self.conditions.items() if k in condition_ids}

        logger.info("=" * 70)
        logger.info(
            "ABLATION HARNESS: %d conditions × %d questions (model=%s)",
            len(selected), len(questions), llm_model,
        )
        logger.info("=" * 70)

        condition_results: dict[str, ConditionResult] = {}

        for cond_id, cond_def in selected.items():
            logger.info("--- Condition: %s (%s) ---", cond_id, cond_def["label"])
            cond_t0 = time.perf_counter()

            config = QARunConfig(
                patient_id=patient_id,
                condition=cond_id,
                assertion_mode=cond_def["assertion_mode"],
                temporal_mode=cond_def["temporal_mode"],
                retrieval_mode=cond_def["retrieval_mode"],
                llm_model=llm_model,
                llm_provider=llm_provider,
                ollama_base_url=ollama_base_url,
                raw_note_only=cond_def.get("raw_note_only", False),
                calculator_enabled=cond_def.get("calculator_enabled", False),
                guidelines_enabled=cond_def.get("guidelines_enabled", False),
                use_llm_judge=use_llm_judge,
            )

            report = await self.executor.run_question_set(
                questions=questions,
                config=config,
                experiment_name=f"Ablation: {cond_def['label']}",
                run_id=run_id,
            )

            safety = self.qa_service.compute_clinical_safety_score(report.results)
            cond_latency = (time.perf_counter() - cond_t0) * 1000

            condition_results[cond_id] = ConditionResult(
                condition_id=cond_id,
                condition_label=cond_def["label"],
                report=report,
                safety_score=safety,
                latency_ms=cond_latency,
                config_snapshot={
                    "assertion_mode": config.assertion_mode,
                    "temporal_mode": config.temporal_mode,
                    "retrieval_mode": config.retrieval_mode,
                    "raw_note_only": config.raw_note_only,
                    "calculator_enabled": config.calculator_enabled,
                    "guidelines_enabled": config.guidelines_enabled,
                },
            )

            logger.info(
                "  %s: accuracy=%.1f%%, safety=%.3f, latency=%.0fms",
                cond_id, report.accuracy * 100, safety, cond_latency,
            )

        total_duration = time.perf_counter() - t0

        result = AblationResult(
            ablation_id=ablation_id,
            run_at=datetime.now(timezone.utc),
            patient_id=patient_id,
            question_set_name=question_set_name,
            total_questions=len(questions),
            llm_model=llm_model,
            conditions=condition_results,
            total_duration_s=total_duration,
        )

        # Print summary
        logger.info("=" * 70)
        logger.info("ABLATION COMPLETE in %.1fs", total_duration)
        logger.info("=" * 70)
        logger.info("\n%s", result.to_markdown_table())

        # Log deltas
        deltas = result.compute_deltas()
        for pair, delta in deltas.items():
            logger.info(
                "  %s: accuracy Δ=%+.1f%%, safety Δ=%+.3f",
                pair, delta["accuracy_delta"] * 100, delta["safety_delta"],
            )

        return result

    async def run_all_question_sets(
        self,
        patient_id: str,
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
        run_id: str | None = None,
        use_llm_judge: bool = False,
    ) -> dict[str, AblationResult]:
        """Run ablation on all standard question sets.

        Returns dict mapping question set name to AblationResult.
        """
        question_sets = {
            "assertion_50": ASSERTION_QUESTIONS,
            "temporal_30": TEMPORAL_QUESTIONS,
            "rag_25": RAG_QUESTIONS,
        }

        results = {}
        for name, questions in question_sets.items():
            logger.info("=" * 70)
            logger.info("Running ablation on question set: %s (%d questions)", name, len(questions))
            result = await self.run(
                patient_id=patient_id,
                questions=questions,
                question_set_name=name,
                llm_model=llm_model,
                llm_provider=llm_provider,
                run_id=run_id,
                use_llm_judge=use_llm_judge,
            )
            results[name] = result

        return results

    async def smoke_test(
        self,
        patient_id: str,
        n_questions: int = 5,
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
    ) -> AblationResult:
        """Quick smoke test: run all 5 conditions on a small question subset.

        Useful for verifying the harness works before a full run.
        """
        # Take first n questions from assertion set
        questions = ASSERTION_QUESTIONS[:n_questions]
        logger.info(
            "SMOKE TEST: %d conditions × %d questions", len(self.conditions), len(questions),
        )
        return await self.run(
            patient_id=patient_id,
            questions=questions,
            question_set_name=f"smoke_test_{n_questions}",
            llm_model=llm_model,
            llm_provider=llm_provider,
        )
