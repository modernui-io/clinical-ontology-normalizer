"""Benchmark Evaluator — runs ClinicalIntelligenceBench through ablation conditions.

Bridges the benchmark question sets with the ablation harness:
1. Loads gold-standard question sets (Tasks A-D)
2. Converts to QAQuestion format
3. Runs through 5-condition ablation harness
4. Computes task-specific metrics (assertion-weighted, temporal, etc.)
5. Produces NeurIPS-ready result tables
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.benchmark import (
    AssertionWeightedMetrics,
    BenchmarkQuestion,
    BenchmarkQuestionSet,
    BenchmarkRunResult,
    BenchmarkTask,
    CalculatorMetrics,
    ConditionResult as BenchConditionResult,
    FusionMetrics,
    QuestionScore,
    TaskResult,
    TemporalMetrics,
)
from app.services.ablation_harness import (
    ABLATION_CONDITIONS,
    AblationHarness,
    AblationResult,
)
from app.services.qa_evaluation import QAQuestion

logger = logging.getLogger(__name__)


def _benchmark_to_qa_question(bq: BenchmarkQuestion) -> QAQuestion:
    """Convert a BenchmarkQuestion to the QAQuestion format used by the executor."""
    return QAQuestion(
        question_id=bq.question_id,
        question=bq.question,
        category=bq.subtype,
        expected_answer=bq.expected_answer,
        assertion_sensitive=bq.task == BenchmarkTask.TASK_A_NEGATION,
        temporal_sensitive=bq.task == BenchmarkTask.TASK_B_TEMPORAL,
        difficulty=bq.difficulty.value,
        clinical_context=bq.clinical_context,
        scoring_rubric=bq.scoring_rubric,
        metadata=bq.metadata,
    )


class BenchmarkEvaluator:
    """Evaluates ClinicalIntelligenceBench across ablation conditions.

    Usage:
        evaluator = BenchmarkEvaluator()
        evaluator.load_questions("backend/data/benchmarks/")
        result = await evaluator.run(patient_id="P001")
        print(result.to_markdown())
    """

    def __init__(self) -> None:
        self._question_sets: dict[str, BenchmarkQuestionSet] = {}
        self._harness = AblationHarness()

    def load_questions(self, data_dir: str = "backend/data/benchmarks") -> None:
        """Load benchmark question sets from JSON files."""
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.warning("Benchmark data directory not found: %s", data_dir)
            return

        for json_file in data_path.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                qs = BenchmarkQuestionSet.model_validate(data)
                self._question_sets[qs.task.value] = qs
                logger.info(
                    "Loaded %d questions for %s from %s",
                    qs.total_count, qs.task.value, json_file.name,
                )
            except Exception as exc:
                logger.warning("Failed to load %s: %s", json_file, exc)

    def set_questions(self, task: str, question_set: BenchmarkQuestionSet) -> None:
        """Directly set a question set (for programmatic use)."""
        self._question_sets[task] = question_set

    async def run(
        self,
        patient_id: str,
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
        use_llm_judge: bool = True,
        tasks: list[str] | None = None,
        condition_ids: list[str] | None = None,
        question_limit: int | None = None,
    ) -> BenchmarkRunResult:
        """Run the full benchmark evaluation.

        Args:
            patient_id: Patient to evaluate against.
            llm_model: LLM to use for QA.
            llm_provider: Provider (anthropic/openai/ollama).
            use_llm_judge: Use LLM judge for scoring.
            tasks: Specific tasks to run (None = all loaded).
            condition_ids: Specific ablation conditions (None = all 5).
            question_limit: Limit questions per task for faster iteration.

        Returns:
            BenchmarkRunResult with all results.
        """
        run_id = f"bench_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        t0 = time.perf_counter()

        selected_tasks = tasks or list(self._question_sets.keys())
        all_conditions: dict[str, BenchConditionResult] = {}
        total_questions = 0

        for task_name in selected_tasks:
            qs = self._question_sets.get(task_name)
            if not qs:
                logger.warning("No questions loaded for task %s, skipping", task_name)
                continue

            # Convert to QAQuestion format
            questions = [_benchmark_to_qa_question(bq) for bq in qs.questions]
            if question_limit:
                questions = questions[:question_limit]

            total_questions += len(questions)

            logger.info(
                "Running benchmark task %s: %d questions × %d conditions",
                task_name, len(questions),
                len(condition_ids) if condition_ids else len(ABLATION_CONDITIONS),
            )

            # Run through ablation harness
            ablation_result = await self._harness.run(
                patient_id=patient_id,
                questions=questions,
                question_set_name=task_name,
                llm_model=llm_model,
                llm_provider=llm_provider,
                use_llm_judge=use_llm_judge,
                condition_ids=condition_ids,
            )

            # Convert ablation results to benchmark format
            for cond_id, cond_result in ablation_result.conditions.items():
                if cond_id not in all_conditions:
                    all_conditions[cond_id] = BenchConditionResult(
                        condition=cond_id,
                    )

                # Build per-question scores
                scores = [
                    QuestionScore(
                        question_id=r.question_id,
                        task=qs.task,
                        subtype=r.category,
                        predicted_answer=r.predicted_answer,
                        expected_answer=r.expected_answer,
                        correct=r.correct,
                        overall_score=r.score,
                        latency_ms=r.latency_ms,
                        error=r.error,
                    )
                    for r in cond_result.report.results
                ]

                task_result = TaskResult(
                    task=qs.task,
                    condition=cond_id,
                    total_questions=cond_result.report.total_questions,
                    correct=cond_result.report.correct,
                    accuracy=cond_result.report.accuracy,
                    subtype_accuracies=cond_result.report.category_accuracies,
                    avg_latency_ms=cond_result.report.avg_latency_ms,
                    safety_score=cond_result.safety_score,
                    scores=scores,
                )

                all_conditions[cond_id].task_results[task_name] = task_result

        # Compute overall metrics per condition
        for cond in all_conditions.values():
            if cond.task_results:
                accs = [tr.accuracy for tr in cond.task_results.values()]
                safes = [tr.safety_score for tr in cond.task_results.values()]
                lats = [tr.avg_latency_ms for tr in cond.task_results.values()]
                cond.overall_accuracy = sum(accs) / len(accs) if accs else 0.0
                cond.overall_safety = sum(safes) / len(safes) if safes else 0.0
                cond.avg_latency_ms = sum(lats) / len(lats) if lats else 0.0

        total_duration = time.perf_counter() - t0

        return BenchmarkRunResult(
            run_id=run_id,
            run_at=datetime.now(timezone.utc),
            llm_model=llm_model,
            total_questions=total_questions,
            conditions=all_conditions,
            total_duration_s=total_duration,
        )

    # ========================================================================
    # Task-specific metric computation
    # ========================================================================

    def compute_assertion_metrics(
        self, scores: list[QuestionScore],
    ) -> AssertionWeightedMetrics:
        """Compute assertion-weighted metrics for Task A."""
        total = len(scores)
        correct = sum(1 for s in scores if s.correct)
        false_pos_negated = sum(
            1 for s in scores
            if s.subtype == "negation" and not s.correct
        )

        # Weighted accuracy: 2x penalty for false positive on negation
        weighted_correct = 0.0
        weighted_total = 0.0
        for s in scores:
            weight = 2.0 if s.subtype == "negation" else 1.0
            weighted_total += weight
            if s.correct:
                weighted_correct += weight

        subtypes = {"negation": [], "uncertainty": [], "family_history": [], "conditional": []}
        for s in scores:
            if s.subtype in subtypes:
                subtypes[s.subtype].append(s.correct)

        return AssertionWeightedMetrics(
            total=total,
            correct=correct,
            raw_accuracy=correct / total if total > 0 else 0.0,
            weighted_accuracy=weighted_correct / weighted_total if weighted_total > 0 else 0.0,
            negation_accuracy=_accuracy(subtypes["negation"]),
            uncertainty_accuracy=_accuracy(subtypes["uncertainty"]),
            family_history_accuracy=_accuracy(subtypes["family_history"]),
            conditional_accuracy=_accuracy(subtypes["conditional"]),
            false_positive_on_negated=false_pos_negated,
        )

    def compute_temporal_metrics(
        self, scores: list[QuestionScore],
    ) -> TemporalMetrics:
        """Compute temporal accuracy metrics for Task B."""
        total = len(scores)
        correct = sum(1 for s in scores if s.correct)

        subtypes = {
            "current_state": [], "historical": [], "sequence": [],
            "duration": [], "change": [],
        }
        for s in scores:
            if s.subtype in subtypes:
                subtypes[s.subtype].append(s.correct)

        return TemporalMetrics(
            total=total,
            correct=correct,
            accuracy=correct / total if total > 0 else 0.0,
            current_state_accuracy=_accuracy(subtypes["current_state"]),
            historical_accuracy=_accuracy(subtypes["historical"]),
            sequence_accuracy=_accuracy(subtypes["sequence"]),
            duration_accuracy=_accuracy(subtypes["duration"]),
            change_accuracy=_accuracy(subtypes["change"]),
        )

    def compute_calculator_metrics(
        self, scores: list[QuestionScore],
    ) -> CalculatorMetrics:
        """Compute calculator accuracy metrics for Task C."""
        total = len(scores)
        calc_correct = sum(1 for s in scores if s.correct)

        per_calc: dict[str, list[bool]] = {}
        for s in scores:
            per_calc.setdefault(s.subtype, []).append(s.correct)

        return CalculatorMetrics(
            total=total,
            calculator_correct=calc_correct,
            decision_correct=calc_correct,  # TODO: separate calc vs decision scoring
            calculator_accuracy=calc_correct / total if total > 0 else 0.0,
            decision_accuracy=calc_correct / total if total > 0 else 0.0,
            per_calculator={k: _accuracy(v) for k, v in per_calc.items()},
        )

    def compute_fusion_metrics(
        self, scores: list[QuestionScore],
    ) -> FusionMetrics:
        """Compute fusion accuracy metrics for Task D."""
        total = len(scores)
        correct = sum(1 for s in scores if s.correct)

        return FusionMetrics(
            total=total,
            correct=correct,
            accuracy=correct / total if total > 0 else 0.0,
        )


def _accuracy(values: list[bool]) -> float:
    """Compute accuracy from a list of bool correctness values."""
    if not values:
        return 0.0
    return sum(values) / len(values)
